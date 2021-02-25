/*
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
*/

use ed25519_dalek::{
    Keypair,
};

use ton_block::{
    Message as TonBlockMessage,
    MsgAddressInt,
    StateInit,
    GetRepresentationHash,
};

use crate::util::{
    decode_address, load_from_file, get_msg_value,
    convert_address,
};

use crate::global_state::{
    GlobalState,
    ContractInfo,
    make_config_params,
};

use crate::call_contract::{
    call_contract_ex, process_actions,
    is_success_exit_code, ExecutionResult,
};

use crate::messages::{
    MsgAbiInfo,
    MsgInfo, MessageInfo2,
    create_bounced_msg, create_inbound_msg,
};

use crate::abi::{
    decode_body,
    build_abi_body, set_public_key, AbiInfo,
};

use crate::debug_info::{
    TraceStepInfo,
};

#[derive(Default)]
pub struct ExecutionResult2 {
    exit_code: i32,
    out_actions: Vec<String>,
    gas: i64,
    info: Option<String>,
    pub trace: Option<Vec<TraceStepInfo>>,
}

impl ExecutionResult2 {
    pub fn unpack(self) -> (i32, Vec<String>, i64, Option<String>) {
        (self.exit_code, self.out_actions, self.gas, self.info)
    }
    fn with_actions(result: ExecutionResult, out_actions: Vec<String>) -> ExecutionResult2 {
        ExecutionResult2 {
            exit_code:   result.info.exit_code,
            gas:         result.info.gas,
            info:        result.info_msg,
            trace:       result.trace,
            out_actions: out_actions,
        }
    }
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

    let address0 = convert_address(state_init.hash().unwrap(), wc);
    let address = address.unwrap_or(address0);
    // println!("address = {:?}", address);

    if gs.trace {
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
    trace: bool,
    trace2: bool,
    time_header: Option<String>,
    now: u64,
) -> Result<StateInit, String> {

    let keypair = decode_private_key(&private_key);

    let body = build_abi_body(
        abi_info,
        "constructor",
        ctor_params,
        time_header,
        false,  // is_internal
        keypair.as_ref(),
    )?;

    let addr = MsgAddressInt::default();

    let contract_info = ContractInfo::create(
        addr.clone(),
        Some(abi_file.to_string()),
        state_init,
        abi_info.clone(),
        0,  // balance
    );

    let msg_info = MessageInfo2::with_offchain_ctor(
        create_inbound_msg(addr.clone(), &body, now)
    );

    let result = call_contract_ex(
        &contract_info,
        &msg_info,
        trace, trace2,
        None,
        now,
    );

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

    let contract = gs.get_contract(&msg.src()).unwrap();

    let mut msgs = vec![];
    if msg.bounce() {
        msgs.push(create_bounced_msg2(&gs, &msg, &contract.abi_info()));
    } else {
        increase_dummy_balance(gs, msg.dst(), msg.value());
    }
    let mut result = ExecutionResult2::default();
    result.out_actions = gs.add_messages(msgs);
    result
}

fn dispatch_message_on_error(
    gs: &mut GlobalState,
    msg: &MsgInfo,
    mut result: ExecutionResult2
) -> ExecutionResult2 {

    let dst = msg.dst();

    let mut contract = gs.get_contract(&dst).unwrap();
    let abi_info = contract.abi_info().clone();     // TODO!!: Arc?
    contract.change_balance(-1, msg.value());
    gs.set_contract(dst, contract);

    if msg.bounce() {
        let msg = create_bounced_msg2(&gs, &msg, &abi_info);
        result.out_actions = gs.add_messages(vec![msg]);
    }

    result
}

pub fn dispatch_message_impl(
    gs: &mut GlobalState,
    msg_id: u32,        // TODO!: pass MsgInfo instead?
) -> ExecutionResult2 {

    let msg_info = &*gs.messages.get(msg_id);
    let ton_msg = &msg_info.ton_msg().unwrap();

    let address = msg_info.dst();

    if let Some(state_init) = ton_msg.state_init() {
        let wc = address.workchain_id() as i8;
        deploy_contract_impl(gs, None, state_init.clone(), None, AbiInfo::default(), wc, 0).unwrap();
    }

    if !gs.address_exists(&address) {
        return bounce_msg(gs, msg_info);
    }

    let result = exec_contract_and_process_actions(
        gs,
        &MessageInfo2::with_info(&msg_info),
        None, // method
    );

    if !is_success_exit_code(result.exit_code) {
        dispatch_message_on_error(gs, msg_info, result)
    } else {
        result
    }
}

fn create_bounced_msg2(gs: &GlobalState, msg_info: &MsgInfo, abi_info: &AbiInfo) -> MsgInfo {
    let msg2 = create_bounced_msg(&msg_info, gs.get_now());
    let j = decode_message(&gs, &abi_info, None, &msg2, 0);
    MsgInfo::create(msg2.clone(), j)
}

pub fn exec_contract_and_process_actions(
    gs: &mut GlobalState,
    msg_info: &MessageInfo2,
    method: Option<String>,
) -> ExecutionResult2 {

    // TODO: Too long function

    let address = msg_info.dst();
    let mut contract_info = gs.get_contract(&address).unwrap();

    if let Some(msg_value) = msg_info.value() {
        contract_info.change_balance(1, msg_value);
    }

    let mut result = call_contract_ex(
        &contract_info,
        &msg_info,
        gs.trace, gs.trace_on,
        make_config_params(&gs),
        gs.get_now(),
    );

    result.info.inbound_msg_id = msg_info.id();
    gs.register_run_result(result.info.clone());

    if result.info_msg == Some("no_accept".to_string()) {
        return ExecutionResult2::with_actions(result, vec![])
    }

    let msgs = process_actions(
        gs,
        contract_info,
        &result,
        method,
        msg_info.value(),
    );

    let out_actions = gs.add_messages(msgs);

    ExecutionResult2::with_actions(result, out_actions)
}

pub fn call_contract_impl(
    gs: &mut GlobalState,
    address_str: String,
    method: String,
    is_getter: bool,
    params: String,
    private_key: Option<String>,
) -> Result<ExecutionResult2, String> {
    // TODO: Too long function
    let addr = decode_address(&address_str);

    let contract_info = gs.get_contract(&addr).unwrap();

    if gs.trace {
        println!("encode_function_call(\"{}\",\"{}\")", method, params);
        // println!("private_key {:?}", private_key);
    }

    let keypair = decode_private_key(&private_key);

    let abi_info = contract_info.abi_info();

    let body = build_abi_body(
        abi_info,
        &method,
        &params,
        gs.make_time_header(),
        false, // internal
        keypair.as_ref(),
    );

    if body.is_err() {
        return Err(body.err().unwrap());
    }

    let body = body.unwrap();

    let msg = create_inbound_msg(addr.clone(), &body, gs.get_now());

    // TODO: move to function
    let mut msg_abi = decode_message(&gs, &abi_info, Some(method.clone()), &msg, 0);
    msg_abi.fix_call(is_getter);
    let msg_info = MsgInfo::create(msg.clone(), msg_abi);
    gs.messages.add(msg_info);

    let msg_info = MessageInfo2::with_getter(msg, is_getter);

    let result = exec_contract_and_process_actions(
        gs, &msg_info, Some(method.clone()),
    );

    Ok(result)
}

pub fn load_state_init(
    gs: &mut GlobalState,
    contract_file: &String,
    abi_file: &String,
    abi_info: &AbiInfo,
    ctor_params: &Option<String>,
    pubkey: &Option<String>,
    private_key: &Option<String>,
    trace: bool,
) -> Result<StateInit, String> {
    let mut state_init = load_from_file(&contract_file);
    if let Some(pubkey) = pubkey {
        let result = set_public_key(&mut state_init, pubkey.clone());
        if result.is_err() {
            return Err(result.err().unwrap());
        }
    }

    if let Some(ctor_params) = ctor_params {
        let time_header = gs.make_time_header();
        let result = apply_constructor(
                        state_init, &abi_file, &abi_info, &ctor_params,
                        private_key.clone(),
                        trace, gs.trace_on,
                        time_header, gs.get_now(),
                    );
        if result.is_err() {
            return Err(result.err().unwrap());
        }
        state_init = result.unwrap();
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
) -> MsgAbiInfo {
    let mut decoded_msg = decode_body(gs, abi_info, getter_name, out_msg);
    if let Some(value) = get_msg_value(&out_msg) {
        decoded_msg.fix_value(value + additional_value);
    }
    decoded_msg.fix_timestamp(gs.get_now());
    decoded_msg
}
