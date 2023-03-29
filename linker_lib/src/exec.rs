/*
    This file is part of Ever OS.

    Ever OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2023 (c) EverX
*/

use ed25519_dalek::Keypair;

use serde::Serialize;

use ton_block::{
    Message as TonBlockMessage,
    MsgAddressInt,
    StateInit,
    GetRepresentationHash, Deserializable,
};

use ton_types::{Cell, SliceData};

use crate::decode_cell;
use crate::util::{
    decode_address, load_from_file, get_msg_value,
    convert_address,
};

use crate::global_state::{
    GlobalState,
    ContractInfo,
    make_config_params,
};

use crate::actions::{
    process_actions,
};

use crate::call_contract::{
    call_contract_ex,
    is_success_exit_code, ExecutionResult,
};

use crate::messages::{
    MsgAbiInfo,
    MsgInfo, CallContractMsgInfo,
    create_bounced_msg, create_inbound_msg,
};

use crate::abi::{
    decode_body,
    build_abi_body, set_public_key, AbiInfo,
};

use crate::debots::{
    prepare_ext_in_message, debot_build_on_success, debot_build_on_error,
};

use crate::debug_info::{
    TraceStepInfo,
};

const XMODEM: crc::Crc<u16> = crc::Crc::<u16>::new(&crc::CRC_16_XMODEM);

#[derive(Default, Serialize)]
pub struct ExecutionResult2 {
    exit_code: i32,
    aborted: bool,
    stack: Vec<String>,
    out_actions: Vec<String>,
    gas: i64,
    info: Option<String>,
    pub trace: Option<Vec<TraceStepInfo>>,
    debot_answer_msg: Option<String>,
    accept_in_getter: bool,
}

impl ExecutionResult2 {
    fn with_actions(result: ExecutionResult, out_actions: Vec<String>) -> ExecutionResult2 {
        ExecutionResult2 {
            exit_code:   result.info.exit_code,
            aborted:     false,
            gas:         result.info.gas,
            info:        result.info_msg,
            trace:       result.trace,
            stack:       result.info.stack,
            out_actions,
            debot_answer_msg: None,
            accept_in_getter: result.info.accept_in_getter,
        }
    }
    fn with_aborted(reason: String) -> ExecutionResult2 {
        ExecutionResult2 {
            aborted: true,
            info: Some(reason),
            ..ExecutionResult2::default()
        }
    }
}

impl std::fmt::Display for ExecutionResult2 {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&serde_json::to_string(self).unwrap())
    }
}

pub fn generate_contract_address(
    state_init: &StateInit,
    wc: i8,
) -> MsgAddressInt {
    convert_address(state_init.hash().unwrap(), wc)
}

pub fn deploy_contract_impl(
    gs: &mut GlobalState,
    contract_name: Option<String>,
    state_init: StateInit,
    address: Option<MsgAddressInt>,
    abi_info: AbiInfo,
    wc: i8,
    mut balance: u64
) -> Result<String, String> {

    let address0 = generate_contract_address(&state_init, wc);
    let address = address.unwrap_or(address0);
    // println!("address = {:?}", address);

    if gs.is_trace(1) {
        println!("deploy_contract_impl: {:?} {}", contract_name, address);
    }

    if let Some(balance2) = gs.dummy_balances.get(&address) {
        balance = *balance2;
        gs.dummy_balances.remove(&address);
    }

    let contract_info = ContractInfo::create(address.clone(), contract_name, state_init, abi_info, balance);

    if gs.address_exists(&address) {
        return Err("Deploy failed, address exists".to_string());
    }

    let addr_str = format!("{}", address);
    gs.set_contract(address, contract_info);

    Ok(addr_str)
}

pub fn apply_constructor(
    state_init: StateInit,
    abi_file: &str,
    abi_info: &AbiInfo,
    ctor_params : &str,
    private_key: Option<String>,
    global_gas_limit: u64,
    trace_level: u64,
    debug: bool,
    trace1: bool,
    trace2: bool,
    time_header: Option<String>,
    now: u64,
    lt: u64,
    error_msg: &mut Option<String>,
) -> Result<StateInit, String> {

    let keypair = decode_private_key(&private_key);
    let address = Some("-1:0000000000000000000000000000000000000000000000000000000000000000".to_string());

    let body = SliceData::load_builder(build_abi_body(
        abi_info,
        "constructor",
        ctor_params,
        time_header,
        false,  // is_internal
        keypair.as_ref(),
        address,
    )?).unwrap();

    let address = MsgAddressInt::default();

    let contract_info = ContractInfo::create(
        address.clone(),
        Some(abi_file.to_string()),
        state_init,
        abi_info.clone(),
        0,  // balance
    );

    let msg_info = CallContractMsgInfo::with_offchain_ctor(
        create_inbound_msg(address.clone(), body, now)
    );

    let result = call_contract_ex(
        &address,
        &contract_info,
        &msg_info,
        global_gas_limit,
        trace_level,
        debug, trace1, trace2,
        None,
        now,
        lt,
    );

    *error_msg = result.info.error_msg.clone();

    if is_success_exit_code(result.info.exit_code) {
        // TODO: check that no action is fired. Add a test
        // TODO: remove constructor from dictionary of methods?
        Ok(result.info_ex.state_init)
    } else {
        Err(format!("Constructor failed. ec = {}", result.info.exit_code))
    }
}

fn increase_dummy_balance(
    gs: &mut GlobalState,
    addr: MsgAddressInt,
    value: u64
) {
    let prev = *gs.dummy_balances.get(&addr).unwrap_or(&0);
    gs.dummy_balances.insert(addr, prev + value);
}


fn bounce_msg(
    gs: &mut GlobalState,
    msg: &MsgInfo,
) -> ExecutionResult2 {

    let contract = gs.get_contract(&msg.src());
    let mut msgs = vec![];
    if let (Some(contract), true) = (contract, msg.bounce()) {
        msgs.push(create_bounced_msg2(gs, msg, contract.abi_info()));
    } else {
        increase_dummy_balance(gs, msg.dst(), msg.value().unwrap());
    }
    ExecutionResult2 {
        out_actions: gs.add_messages(msgs),
        ..ExecutionResult2::default()
    }
}

fn dispatch_message_on_error(
    gs: &mut GlobalState,
    msg: &MsgInfo,
    mut result: ExecutionResult2,
    gas_fee: u64,
) -> ExecutionResult2 {

    if gs.is_trace(5) {
        println!("dispatch_message_on_error: msg.value = {:?}, gas_fee = {}", msg.value(), gas_fee);
    }

    let dst = msg.dst();

    let mut contract = gs.get_contract(&dst).unwrap();
    let abi_info = contract.abi_info().clone();     // TODO: Arc?
    if msg.value().is_none() {
        // the dispatched message comes from Debot, but it should be handled before
        println!("!!!!! dispatch_message_on_error: msg.value().is_none()");
        return result;
    }

    let msg_value = msg.value().unwrap();

    if msg_value <= gas_fee {
        // no money to send error message, do nothing
        if gs.is_trace(1) {
            println!("dispatch_message_on_error: no money for reply on error");
        }
        return result;        
    }

    contract.change_balance(-1, msg_value - gas_fee, gs.config.trace_level);
    gs.set_contract(dst, contract);

    if msg.bounce() {
        // TODO: account gas fee here
        let msg = create_bounced_msg2(gs, msg, &abi_info);
        result.out_actions = gs.add_messages(vec![msg]);
    }

    result
}

pub fn dispatch_message_impl(
    gs: &mut GlobalState,
    msg_id: u32,        // TODO: pass MsgInfo instead?
) -> ExecutionResult2 {

    let mut msg_info: MsgInfo = (*gs.messages.get(msg_id)).clone();

    let ton_msg = msg_info.ton_msg().unwrap().clone();

    if gs.is_trace(1) {
        println!("dispatch_message_impl: msg_id = {}", msg_id);
    }
    if gs.is_trace(5) {
        println!("ton_msg = {:?}", ton_msg);
    }

    let mut is_debot_call = false;
    let mut debot_call_info = None;

    if ton_msg.ext_in_header().is_some() {      // TODO: move this to process_actions?
        /*
        println!("=================");
        println!("src2 = {}", msg_info.src2());
        println!("{:?}", ton_msg);
        */
        let (new_msg, info) = 
            prepare_ext_in_message(ton_msg.clone(), gs.get_now_ms(), gs.debot_keypair.clone()).unwrap();
        msg_info.set_ton_msg(new_msg);
        is_debot_call = true;
        let mut info = info;
        if msg_info.has_src() {
            info.debot_addr = Some(msg_info.src());
        } else {
            info.debot_addr = Some(msg_info.json.debot_info.as_ref().unwrap().debot_addr.to_int().unwrap());
        }
        debot_call_info = Some(info);
        
        msg_info.debot_call_info = debot_call_info.clone();
        gs.messages.set_debot_call_info(msg_id, debot_call_info.clone().unwrap());
    }

    let address = msg_info.dst();

    if let Some(state_init) = ton_msg.state_init() {
        if gs.address_exists(&address) {
            return bounce_msg(gs, &msg_info);
        }
        let wc = address.workchain_id() as i8;
        deploy_contract_impl(gs, None, state_init.clone(), None, AbiInfo::default(), wc, 0).unwrap();
    }

    if !gs.address_exists(&address) {
        return bounce_msg(gs, &msg_info);
    }

    let mut result = exec_contract_and_process_actions(
        gs,
        &CallContractMsgInfo::with_info(&msg_info),
        None, // method
        is_debot_call,
    );
    
    if is_debot_call && gs.is_trace(5) {
        println!("!!!!!!!!!!!! debot_call_info = {:?}", debot_call_info);
    }

    // println!("!!!!!! debot_call_info = {:?}", msg_info.debot_call_info.is_some());

    if !is_success_exit_code(result.exit_code) {
        if is_debot_call {
            if gs.is_trace(5) {
                println!("!!!!!!!!!!!! on_error = {:?}", result.exit_code);
            }
            let info = debot_call_info.unwrap();
            let src = decode_address(&info.dst_addr);
            let dst = info.debot_addr.as_ref().unwrap();

            let msg = debot_build_on_error(src, dst.clone(), info.onerror_id, result.exit_code as u32);

            let debot_abi = gs.get_contract(dst).unwrap().abi_info().clone();

            let j = decode_message(gs, &debot_abi, None, &msg, 0, false);
            let mut msg_info2 = MsgInfo::create(msg, j);

            msg_info2.debot_call_info = Some(info);

            let msg_info2 = gs.messages.add(msg_info2);
            result.debot_answer_msg = Some(msg_info2.json_str());

            result
        } else {
            let gas_fee = if gs.config.gas_fee { result.gas*1000 } else { 0 };
            dispatch_message_on_error(gs, &msg_info, result, gas_fee as u64)
        }
    } else {
        let out_actions = &result.out_actions;
        if is_debot_call && out_actions.is_empty() {
            let info = debot_call_info.unwrap();
            let answer_id = info.answer_id;
            let src = decode_address(&info.dst_addr);
            let dst = info.debot_addr.clone().unwrap();

            let msg = debot_build_on_success(src, dst.clone(), answer_id);

            let debot_abi = gs.get_contract(&dst).unwrap().abi_info().clone();

            let j = decode_message(gs, &debot_abi, None, &msg, 0, false);
            let mut msg_info2 = MsgInfo::create(msg, j);

            msg_info2.debot_call_info = Some(info);

            let msg_info2 = gs.messages.add(msg_info2);
            result.debot_answer_msg = Some(msg_info2.json_str());
        }
        result
    }
}

fn create_bounced_msg2(gs: &GlobalState, msg_info: &MsgInfo, abi_info: &AbiInfo) -> MsgInfo {
    let msg2 = create_bounced_msg(msg_info, gs.get_now());
    let j = decode_message(gs, abi_info, None, &msg2, 0, false);
    MsgInfo::create(msg2, j)
}

pub fn exec_contract_and_process_actions(
    gs: &mut GlobalState,
    msg_info: &CallContractMsgInfo,
    method: Option<String>,
    is_debot_call: bool,
) -> ExecutionResult2 {

    // TODO: Too long function
    if gs.is_trace(5) {
        println!("exec_contract_and_process_actions: method={:?}", method);
    }

    gs.lt += 1;

    let address = msg_info.dst();
    let mut contract_info = gs.get_contract(&address).unwrap();

    if let Some(msg_value) = msg_info.value() {
        contract_info.change_balance(1, msg_value, gs.config.trace_level);
    }

    let mut result = call_contract_ex(
        &address,
        &contract_info,
        msg_info,
        gs.config.global_gas_limit,
        gs.config.trace_level,
        gs.is_trace(5), gs.config.trace_tvm, gs.trace_on,
        make_config_params(gs),
        gs.get_now(),
        gs.lt,
    );

    gs.last_error_msg = result.info.error_msg.clone();

    result.info.inbound_msg_id = msg_info.id();

    gs.register_run_result(result.info.clone());

    if result.info_msg == Some("no_accept".to_string()) {
        return ExecutionResult2::with_actions(result, vec![])
    }

    let gas_fee = if gs.config.gas_fee && !msg_info.is_getter_call() {
        if gs.is_trace(5) {
            println!("exec_contract_and_process_actions: charge for gas - {}", result.info.gas);
        }
        let fee = 1000*result.info.gas as u64;
        contract_info.change_balance(-1, fee, gs.config.trace_level);
        Some(fee)
    } else {
        None
    };

    let msgs = process_actions(
        gs,
        &address,
        contract_info,
        &result,
        method,
        msg_info.value(),
        is_debot_call,
        gas_fee,
    );

    if let Err(reason) = msgs {
        return ExecutionResult2::with_aborted(reason);
    }

    let out_actions = gs.add_messages(msgs.unwrap());

    ExecutionResult2::with_actions(result, out_actions)
}

pub fn encode_message_body_impl(
    abi_info: &AbiInfo,
    method: String,
    params: String,
) -> Result<Cell, String> {
    let body = build_abi_body(
        abi_info,
        &method,
        &params,
        None,
        true,
        None,
        None,
    )?;
    Ok(body.into_cell().unwrap())
}

pub fn call_contract_impl(
    gs: &mut GlobalState,
    address_str: &str,
    method: &str,
    is_getter: bool,
    is_debot: bool,
    params: &str,
    private_key: Option<String>,
) -> Result<ExecutionResult2, String> {
    // TODO: Too long function
    let addr = decode_address(address_str);

    let contract_info = match gs.get_contract(&addr) {
        Some(contract_info) => contract_info,
        None => return Err(format!("Account does not exist: {}", addr))
    };

    if gs.is_trace(1) {
        println!("call_contract_impl: \"{}\" - \"{}\"", method, params);
        // println!("private_key {:?}", private_key);
    }

    let keypair = decode_private_key(&private_key);

    let abi_info = contract_info.abi_info();

    let body = SliceData::load_builder(build_abi_body(
        abi_info,
        method,
        params,
        gs.make_time_header(),
        false, // internal
        keypair.as_ref(),
        Some(address_str.to_string()),
    )?).unwrap();

    let msg = create_inbound_msg(addr, body, gs.get_now());

    // TODO: move to function
    let mut msg_abi = decode_message(gs, abi_info, Some(method.to_string()), &msg, 0, false);
    msg_abi.fix_call(is_getter);
    let msg_info = MsgInfo::create(msg.clone(), msg_abi);
    let msg_id = gs.messages.add(msg_info).id();

    let mut msg_info = CallContractMsgInfo::with_getter(msg, is_getter, is_debot);
    msg_info.set_id(msg_id);

    let result = exec_contract_and_process_actions(
        gs, &msg_info, Some(method.to_string()), false,
    );

    Ok(result)
}

pub fn run_get_contract_impl(
    gs: &mut GlobalState,
    address_str: &str,
    method: &str,
    _params: &str,
) -> Result<ExecutionResult2, String> {
    let addr = decode_address(address_str);

    let contract_info = gs.get_contract(&addr)
        .ok_or_else(|| format!("Account does not exist: {}", addr))?;

    let crc = XMODEM.checksum(method.as_bytes());
    let function_id = ((crc as u32) & 0xffff) | 0x10000;

    let msg_info = CallContractMsgInfo::with_get_id(function_id);
    let result = call_contract_ex(
        &address_str.parse().unwrap(),
        &contract_info,
        &msg_info,
        gs.config.global_gas_limit,
        gs.config.trace_level,
        gs.is_trace(5), gs.config.trace_tvm, gs.trace_on,
        make_config_params(gs),
        gs.get_now(),
        gs.lt,
    );

    // *error_msg = result.info.error_msg.clone();

    if is_success_exit_code(result.info.exit_code) {
        // TODO: check that no action is fired. Add a test
        // TODO: remove constructor from dictionary of methods?
        Ok(ExecutionResult2::with_actions(result, Vec::new()))
    } else {
        Err(format!("get failed. ec = {}", result.info.exit_code))
    }
}

pub fn send_external_message_impl(
    gs: &mut GlobalState,
    _address_str: &str,
    message: &str,
) -> ExecutionResult2 {
    let message = TonBlockMessage::construct_from_cell(decode_cell(message)).unwrap();
    let msg_info = CallContractMsgInfo::with_ton_msg(message);

    exec_contract_and_process_actions(gs, &msg_info, None, false)
}

pub fn load_state_init(
    gs: &mut GlobalState,
    contract_file: &str,
    abi_file: &str,
    abi_info: &AbiInfo,
    ctor_params: &Option<String>,
    initial_data: &Option<String>,
    pubkey: &Option<String>,
    private_key: &Option<String>,
) -> Result<StateInit, String> {
    let mut state_init = load_from_file(contract_file)?;
    if let Some(pubkey) = pubkey {
        set_public_key(&mut state_init, pubkey.clone())?;
    }

    if let Some(initial_data) = initial_data {
        let new_data = ton_abi::json_abi::update_contract_data(
            abi_info.text(),
            initial_data,
            SliceData::load_cell(state_init.data.clone().unwrap_or_default()).unwrap(),
        ).map_err(|e| e.to_string())?;

        state_init.set_data(new_data.into_cell());
    }

    if let Some(ctor_params) = ctor_params {
        let time_header = gs.make_time_header();
        if gs.is_trace(3) {
            println!("apply_constructor: {}", ctor_params);
        }
        let mut error_msg = None;
        let result = apply_constructor(
            state_init, abi_file, abi_info, ctor_params,
            private_key.clone(),
            gs.config.global_gas_limit,
            gs.config.trace_level,
            gs.is_trace(5), gs.config.trace_tvm, gs.trace_on,
            time_header, gs.get_now(),
            gs.lt,
            &mut error_msg,
        );
        gs.last_error_msg = error_msg;
        state_init = result?;
    }
    Ok(state_init)
}

pub fn decode_private_key(private_key: &Option<String>) -> Option<Keypair> {
    private_key.as_ref().map(|key| {
        let secret = hex::decode(key).unwrap();
        Keypair::from_bytes(&secret).expect("error: invalid key")
    })
}

pub fn decode_message(
    gs: &GlobalState,
    abi_info: &AbiInfo,
    getter_name: Option<String>,
    out_msg: &TonBlockMessage,
    additional_value: u64,
    is_debot_call: bool,
) -> MsgAbiInfo {
    let mut abi_info = abi_info.clone();
    if let Some(dst) = out_msg.dst_ref() {
        if let Some(contract_info) = gs.get_contract(dst) {
            abi_info = contract_info.abi_info().clone();
        }
    }
    let mut decoded_msg = decode_body(gs, &abi_info, getter_name, out_msg, is_debot_call);
    if let Some(value) = get_msg_value(out_msg) {
        decoded_msg.fix_value(value + additional_value);
    }
    decoded_msg.fix_timestamp(gs.get_now());
    decoded_msg
}

#[cfg(test)]
#[path = "tests/test_exec.rs"]
mod tests;
