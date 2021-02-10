/*
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
*/

/*

    TODO:
        - move [pyfunction] code to separate file

*/

extern crate base64;
extern crate ed25519_dalek;
extern crate hex;
#[macro_use]
extern crate lazy_static;
extern crate num;
extern crate rand;
#[macro_use]
extern crate serde_json;

extern crate ton_block;
extern crate ton_types;
#[macro_use]
extern crate ton_vm;
extern crate ton_abi;

mod printer;
mod util;
mod abi;
mod debug_info;
mod global_state;
mod call_contract;
mod messages;

use global_state::{
    GlobalState, ContractInfo, GLOBAL_STATE,
    make_config_params,
};

use util::{
    decode_address, load_from_file, get_msg_value,
    convert_address,
};

use abi::{
    decode_body, build_abi_body, set_public_key, AbiInfo,
};

use messages::{
    DecodedMessageInfo, MessageInfo, MessageInfo2,
    create_bounced_msg, create_inbound_msg,
};

use crate::printer::msg_printer;

use serde_json::Value as JsonValue;

use ed25519_dalek::{
    Keypair, Signer,
};

use rand::rngs::OsRng;

use pyo3::prelude::*;
use pyo3::wrap_pyfunction;
use pyo3::exceptions::PyRuntimeError;

use std::io::Cursor;

use ton_types::{
    SliceData,
    cells_serialization::{deserialize_cells_tree},
};

use ton_block::{
    Message as TonBlockMessage,
    MsgAddressInt,
    StateInit,
    GetRepresentationHash,
};

use ton_types::serialize_toc;

use call_contract::{
    call_contract_ex, process_actions
};

#[pyfunction]
fn set_trace(trace: bool) -> PyResult<()> {
    GLOBAL_STATE.lock().unwrap().trace = trace;
    Ok(())
}

#[pyfunction]
fn deploy_contract(
    contract_file: String,
    abi_file: String,
    ctor_params: Option<String>,
    pubkey: Option<String>,
    private_key: Option<String>,
    wc: i8,
    override_address: Option<String>,
    balance: u64,
) -> PyResult<String> {
    let mut gs = GLOBAL_STATE.lock().unwrap();
    let trace = gs.trace;

    let mut state_init = load_from_file(&contract_file);
    if let Some(pubkey) = pubkey {
        let result = set_public_key(&mut state_init, pubkey);
        if result.is_err() {
            return Err(PyRuntimeError::new_err(result.err()));
        }
    }

    let abi_info = gs.all_abis.from_file(&abi_file);

    if let Some(ctor_params) = ctor_params {
        let time_header = gs.make_time_header();
        let result = apply_constructor(
                        state_init, &abi_file, &abi_info, &ctor_params,
                        private_key,
                        trace, time_header, gs.get_now()
                    );
        if result.is_err() {
            return Err(PyRuntimeError::new_err(result.err()));
        }
        state_init = result.unwrap();
    }

    let address = override_address.map(|addr| decode_address(&addr));
    deploy_contract_impl(&mut gs, Some(contract_file), state_init, address, abi_info, wc, balance)
}

// TODO: move to call_contract?
fn deploy_contract_impl(
    gs: &mut GlobalState,
    contract_name: Option<String>,
    state_init: StateInit,
    address: Option<MsgAddressInt>,
    abi_info: AbiInfo,
    wc: i8,
    mut balance: u64
) -> PyResult<String> {

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
        return Err(PyRuntimeError::new_err("Deploy failed, address exists"));
    }

    let addr_str = format!("{}", address);
    gs.set_contract(address, contract_info);

    Ok(addr_str)
}

// TODO: move to call_contract2?
fn apply_constructor(
    state_init: StateInit,
    abi_file: &str,
    abi_info: &AbiInfo,
    ctor_params : &str,
    private_key: Option<String>,
    trace: bool,
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
    let msg = create_inbound_msg(addr.clone(), &body, now);

    let contract_info = ContractInfo::create(
        addr,
        Some(abi_file.to_string()),
        state_init,
        abi_info.clone(),
        0,  // balance
    );

    let mut msg_info = MessageInfo2::default();
    msg_info.msg = Some(msg);
    let result = call_contract_ex(
        &contract_info,
        &msg_info,
        trace,
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

fn is_success_exit_code(exit_code: i32) -> bool {
    exit_code == 0 || exit_code == 1
}

#[pyfunction]
fn get_balance(address: String) -> PyResult<Option<u64>> {
    let address = decode_address(&address);
    let gs = GLOBAL_STATE.lock().unwrap();
    let contract = gs.get_contract(&address);
    let balance = if gs.dummy_balances.contains_key(&address) {
        assert!(contract.is_none());
        Some(gs.dummy_balances[&address])
    } else {
        contract.map(|c| c.balance())
    };
    Ok(balance)
}

#[pyfunction]
fn set_balance(address: String, balance: u64) -> PyResult<()> {
    let address = decode_address(&address);
    let mut gs = GLOBAL_STATE.lock().unwrap();
    let mut contract_info = gs.get_contract(&address).unwrap();
    contract_info.set_balance(balance);
    gs.set_contract(address, contract_info);
    Ok(())
}

#[pyfunction]
fn dump_message(msg_id: u32) -> PyResult<()> {
    let gs = GLOBAL_STATE.lock().unwrap();
    let msg = gs.messages.get(msg_id);
    println!("MSG #{}:\n{}", msg_id, msg_printer(&msg.ton_msg));
    println!("{}", msg.json_str());
    Ok(())
}

// TODO: move
#[pyfunction]
fn dispatch_message(msg_id: u32) -> PyResult<(i32, Vec<String>, i64)> {
    let mut gs = GLOBAL_STATE.lock().unwrap();
    let msg = gs.messages.get(msg_id);
    let ton_msg = msg.ton_msg.clone();

    let msg_value = msg.value();
    let bounce = msg.bounce.unwrap_or(false);
    let address = ton_msg.dst().unwrap();

    let src = msg.src.clone();

    if let Some(state_init) = ton_msg.state_init() {
        let wc = address.workchain_id() as i8;
        deploy_contract_impl(&mut gs, None, state_init.clone(), None, AbiInfo::default(), wc, 0).unwrap();
    }

    let msg = gs.messages.get(msg_id).clone();

    if gs.get_contract(&address).is_none() {
        let src = src.unwrap();
        let contract = gs.get_contract(&src).unwrap();
        let abi_info = contract.abi_info();
        let mut msgs = vec![];
        if bounce {
            let msg2 = create_bounced_msg(&msg, gs.get_now());
            let j = decode_message(&gs, &abi_info, None, &msg2, 0);
            let msg_info2 = MessageInfo::create(msg2.clone(), j);
            msgs.push(msg_info2);
        } else {
            let prev = *gs.dummy_balances.get(&address).unwrap_or(&0);
            gs.dummy_balances.insert(address, prev + msg_value);
        }
        let out_actions = gs.add_messages(msgs);
        return Ok((0, out_actions, 0));
    }

    let mut msg_info = MessageInfo2::default();
    msg_info.msg = Some(ton_msg);
    msg_info.id = Some(msg_id);
    msg_info.value = Some(msg_value);
    let (exit_code, out_actions, gas) = exec_contract_and_process_actions(
        &mut gs, address,
        &msg_info,
        None, // method
    );

    if !is_success_exit_code(exit_code) {
        let dst = msg.dst.clone().unwrap();
        let mut contract = gs.get_contract(&dst).unwrap();
        contract.set_balance(contract.balance() - msg_value);
        let abi_info = contract.abi_info().clone();
        gs.set_contract(dst, contract);
        let mut msgs = vec![];
        // TODO!!: copy-paste, refactor
        if bounce {
            let msg2 = create_bounced_msg(&msg, gs.get_now());
            let j = decode_message(&gs, &abi_info, None, &msg2, 0);
            let msg_info2 = MessageInfo::create(msg2.clone(), j);
            msgs.push(msg_info2);
        }
        let out_actions = gs.add_messages(msgs);
        return Ok((exit_code, out_actions, gas))
    }

    Ok((exit_code, out_actions, gas))
}

// TODO: move
fn exec_contract_and_process_actions(
    gs: &mut GlobalState,
    address: MsgAddressInt,
    msg_info: &MessageInfo2,
    method: Option<String>,
) -> (i32, Vec<String>, i64) {

    let ton_msg = &msg_info.msg;
    let msg_id = &msg_info.id;
    let message_value = &msg_info.value;

    let mut contract_info = gs.get_contract(&address).unwrap();

    let message_value2 = match message_value {
        Some(value) => *value,
        None => {
            if let Some(ton_msg) = &ton_msg {
                get_msg_value(&ton_msg).unwrap_or(0)
            } else {
                0
            }
        }
    };

    if message_value2 > 0 {
        contract_info.set_balance(contract_info.balance() + message_value2);
    }

    let mut result = call_contract_ex(
        &contract_info,
        &msg_info,
        gs.trace,
        make_config_params(&gs),
        gs.get_now(),
    );

    result.info.inbound_msg_id = *msg_id;
    gs.register_run_result(result.info.clone());

    let msgs = process_actions(
        gs,
        contract_info,
        &result,
        method,
        message_value2,
    );

    let out_actions = gs.add_messages(msgs);

    (result.info.exit_code, out_actions, result.info.gas)
}

#[pyfunction]
fn set_contract_abi(address_str: Option<String>, abi_file: String) -> PyResult<()> {
    let mut gs = GLOBAL_STATE.lock().unwrap();
    let abi_info = gs.all_abis.from_file(&abi_file);
    if let Some(address_str) = address_str {
        let addr = decode_address(&address_str);
        let mut contract_info = gs.get_contract(&addr).unwrap();
        contract_info.set_abi(abi_info);
        gs.set_contract(addr, contract_info);
    }
    Ok(())
}

#[pyfunction]
fn call_ticktock(
    address_str: String,
    is_tock: bool,
) -> PyResult<(i32, Vec<String>, i64)> {
    let address = decode_address(&address_str);

    let mut gs = GLOBAL_STATE.lock().unwrap();
    let mut msg_info = MessageInfo2::default();
    msg_info.ticktock = Some(if is_tock { -1 } else { 0 });
    let (exit_code, out_actions, gas) = exec_contract_and_process_actions(
        &mut gs, address,
        &msg_info,
        None, // method
    );

    // TODO: register in gs.messages?

    Ok((exit_code, out_actions, gas))

}

// TODO: move to util?
fn decode_private_key(private_key: &Option<String>) -> Option<Keypair> {
    private_key.as_ref().map(|key| {
        let secret = hex::decode(key).unwrap();
        Keypair::from_bytes(&secret).expect("error: invalid key")
    })
}

#[pyfunction]
fn call_contract(
    address_str: String,
    method: String,
    is_getter: bool,
    params: String,
    private_key: Option<String>,
) -> PyResult<(i32, Vec<String>, i64)> {
    let addr = decode_address(&address_str);

    let mut gs = GLOBAL_STATE.lock().unwrap();
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
        return Err(PyRuntimeError::new_err(body.err()));
    }

    let body = body.unwrap();

    let msg = create_inbound_msg(addr.clone(), &body, gs.get_now());

    // TODO!!: move to function
    let mut j = decode_message(&gs, &abi_info, Some(method.clone()), &msg, 0);
    j.fix_call(is_getter);
    let msg_info = MessageInfo::create(msg.clone(), j);
    gs.messages.add(msg_info);

    let mut msg_info = MessageInfo2::default();
    msg_info.msg = Some(msg);
    let (exit_code, out_actions, gas) = exec_contract_and_process_actions(
        &mut gs, addr, &msg_info,
        Some(method.clone()),
    );

    Ok((exit_code, out_actions, gas))
}

// ---------------------------------------------------------------------------------------

#[pyfunction]
fn set_now(now: u64) -> PyResult<()> {
    let mut gs = GLOBAL_STATE.lock().unwrap();
    gs.set_now(now);
    Ok(())
}

#[pyfunction]
fn set_config_param(idx: u32, cell: String) -> PyResult<()> {
    let mut gs = GLOBAL_STATE.lock().unwrap();

    let cell = base64::decode(&cell).unwrap();
    let mut csor = Cursor::new(cell);
    let cell = deserialize_cells_tree(&mut csor).unwrap().remove(0);

    let is_empty = cell.bit_length() == 0;
    if gs.trace {
        println!("set_config_param {} is_empty={}", idx, is_empty);
    }
    if is_empty {
        gs.config_params.remove(&idx);
    } else {
        gs.config_params.insert(idx, cell);
    }

    Ok(())
}

pub fn decode_message(
    gs: &GlobalState,
    abi_info: &AbiInfo,
    getter_name: Option<String>,
    out_msg: &TonBlockMessage,
    additional_value: u64,
) -> DecodedMessageInfo {
    let mut decoded_msg = decode_body(gs, abi_info, getter_name, out_msg);
    if let Some(value) = get_msg_value(&out_msg) {
        decoded_msg.fix_value(value + additional_value);
    }
    decoded_msg.fix_timestamp(gs.get_now());
    decoded_msg
}

#[pyfunction]
fn reset_all() -> PyResult<()> {
    use std::ops::DerefMut;
    let mut gs = GLOBAL_STATE.lock().unwrap();
    *gs.deref_mut() = GlobalState::default();
    Ok(())
}

#[pyfunction]
fn make_keypair() -> PyResult<(String, String)> {
    let mut csprng = OsRng{};
    let keypair = Keypair::generate(&mut csprng);
    let secret = keypair.to_bytes();
    let secret = hex::encode(secret.to_vec());
    let public = hex::encode(keypair.public.to_bytes());
    Ok((secret, public))
}

#[pyfunction]
fn sign_cell(cell: String, secret: String) -> PyResult<String> {
    let cell = base64::decode(&cell).unwrap();
    // TODO: util?
    let mut csor = Cursor::new(cell);
    let cell = deserialize_cells_tree(&mut csor).unwrap().remove(0);

    let secret = hex::decode(secret).unwrap();
    let keypair = Keypair::from_bytes(&secret).expect("error: invalid key");

    let data = SliceData::from(cell).get_bytestring(0);
    let signature = keypair.sign(&data).to_bytes();
    let signature = hex::encode(signature.to_vec());

    Ok(signature)
}

#[pyfunction]
fn get_all_runs() -> PyResult<String> {
    let gs = GLOBAL_STATE.lock().unwrap();
    let result = serde_json::to_string(&gs.runs).unwrap();
    Ok(result)
}

#[pyfunction]
fn get_all_messages() -> PyResult<String> {
    let gs = GLOBAL_STATE.lock().unwrap();
    let jsons : JsonValue = gs.messages.to_json();
    let result = serde_json::to_string(&jsons).unwrap();
    Ok(result)
}

#[pyfunction]
fn load_code_cell(filename: String) -> PyResult<String> {
    let state_init = load_from_file(&filename);
    let code = state_init.code.unwrap();
    let bytes = serialize_toc(&code).unwrap();
    Ok(base64::encode(&bytes))
}

#[pyfunction]
fn load_data_cell(filename: String) -> PyResult<String> {
    // TODO: add tests for that
    let state_init = load_from_file(&filename);
    let data = state_init.data.unwrap();
    let bytes = serialize_toc(&data).unwrap();
    Ok(base64::encode(&bytes))
}

/////////////////////////////////////////////////////////////////////////////////////
/// A Python module implemented in Rust.
#[pymodule]
fn linker_lib(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_wrapped(wrap_pyfunction!(deploy_contract))?;
    m.add_wrapped(wrap_pyfunction!(get_balance))?;
    m.add_wrapped(wrap_pyfunction!(set_balance))?;
    m.add_wrapped(wrap_pyfunction!(call_contract))?;
    m.add_wrapped(wrap_pyfunction!(dump_message))?;
    m.add_wrapped(wrap_pyfunction!(dispatch_message))?;
    m.add_wrapped(wrap_pyfunction!(set_trace))?;
    m.add_wrapped(wrap_pyfunction!(set_contract_abi))?;
    m.add_wrapped(wrap_pyfunction!(set_config_param))?;
    m.add_wrapped(wrap_pyfunction!(set_now))?;
    m.add_wrapped(wrap_pyfunction!(call_ticktock))?;
    m.add_wrapped(wrap_pyfunction!(reset_all))?;
    m.add_wrapped(wrap_pyfunction!(make_keypair))?;
    m.add_wrapped(wrap_pyfunction!(sign_cell))?;
    m.add_wrapped(wrap_pyfunction!(load_code_cell))?;
    m.add_wrapped(wrap_pyfunction!(load_data_cell))?;
    m.add_wrapped(wrap_pyfunction!(get_all_runs))?;
    m.add_wrapped(wrap_pyfunction!(get_all_messages))?;

    Ok(())
}

