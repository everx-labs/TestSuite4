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

use global_state::{
    GlobalState, MessageInfo, ContractInfo, GLOBAL_STATE,
    make_config_params,
};

use util::{
    decode_address, load_from_file, get_msg_value,
    create_external_inbound_msg, create_internal_msg,
    convert_address,
};

use abi::{
    decode_body, build_abi_body, set_public_key, AbiInfo,
};

use crate::printer::msg_printer;

use serde_json::Value as JsonValue;

use ed25519_dalek::{
    Keypair, Signer,
};

use rand::rngs::OsRng;

use pyo3::prelude::*;
use pyo3::wrap_pyfunction;
use pyo3::exceptions::RuntimeError;

use std::io::Cursor;

use ton_types::{
    SliceData, BuilderData,
    cells_serialization::{deserialize_cells_tree},
};

use ton_block::{
    CurrencyCollection,
    Message as TonBlockMessage,
    MsgAddressExt, MsgAddressInt,
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
            return Err(RuntimeError::py_err(result.err()));
        }
    }

    let abi_info = AbiInfo::from_file(abi_file.clone());
    let abi_str = abi_info.text; // TODO

    if let Some(ctor_params) = ctor_params {
        let time_header = gs.make_time_header();
        state_init = apply_constructor(
                        state_init, &abi_file, &abi_str, &ctor_params,
                        trace, time_header, gs.get_now()
                    ).unwrap();
    }

    let address = override_address.map(|addr| decode_address(&addr));
    deploy_contract2(&mut gs, Some(contract_file), state_init, address, abi_str, wc, balance)
}

fn deploy_contract2(    // TODO: bad function name
    gs: &mut GlobalState,
    contract_name: Option<String>,
    state_init: StateInit,
    address: Option<MsgAddressInt>,
    abi_str: String,
    wc: i8,
    balance: u64
) -> PyResult<String> {

    let address0 = convert_address(state_init.hash().unwrap(), wc);
    let address = address.unwrap_or(address0);
    // println!("address = {:?}", address);

    if gs.trace {
        println!("deploy_contract2: {:?} {}", contract_name, address);
    }

    let contract_info = ContractInfo::create(address.clone(), contract_name, state_init, abi_str, balance);

    if gs.address_exists(&address) {
        return Err(RuntimeError::py_err("Deploy failed, address exists"));
    }

    let addr_str = format!("{}", address);
    gs.set_contract(address, contract_info);

    Ok(addr_str)
}

fn apply_constructor(
    state_init: StateInit,
    abi_file: &str,
    abi_str: &str,
    ctor_params : &str,
    trace: bool,
    time_header: Option<String>,
    now: u64,
) -> Result<StateInit, String> {
    let body = build_abi_body(
        abi_str,
        "constructor",
        ctor_params,
        time_header,
        false,  // is_internal
        None,   // keypair
    )?;

    let addr = MsgAddressInt::default();
    let msg = create_inbound_msg(addr.clone(), &body, now);

    let contract_info = ContractInfo::create(
        addr.clone(),   // TODO
        Some(abi_file.to_string()),
        state_init,
        abi_str.to_string(),
        0,  // balance
    );

    let result = call_contract_ex(
        &contract_info,
        Some(msg),
        None, // msg_value,
        trace,
        None,
        now,
        None, // ticktock
    );

    if result.info.exit_code == 0 || result.info.exit_code == 1 {
        // TODO: check that no action is fired.
        // TODO: remove constructor...
        Ok(result.info_ex.state_init)
    } else {
        Err(format!("Constructor failed ec = {}", result.info.exit_code))
    }
}

#[pyfunction]
fn get_balance(address: String) -> PyResult<u64> {
    let address = decode_address(&address);
    let gs = GLOBAL_STATE.lock().unwrap();
    Ok(gs.get_contract(&address).balance())
}

#[pyfunction]
fn set_balance(address: String, balance: u64) -> PyResult<()> {
    let address = decode_address(&address);
    let mut gs = GLOBAL_STATE.lock().unwrap();
    let mut contract_info = gs.get_contract(&address);
    contract_info.set_balance(balance);
    gs.set_contract(address, contract_info);
    Ok(())
}

#[pyfunction]
fn dump_message(msg_id: u32) -> PyResult<()> {
    let gs = GLOBAL_STATE.lock().unwrap();
    let msg = gs.get_message(msg_id);
    println!("MSG #{}:\n{}", msg_id, msg_printer(&msg.ton_msg));
    println!("{}", msg.json.to_string());
    Ok(())
}

#[pyfunction]
fn dispatch_message(msg_id: u32) -> PyResult<(i32, Vec<String>, i64)> {
    let mut gs = GLOBAL_STATE.lock().unwrap();
    let msg = gs.get_message(msg_id);
    let ton_msg = msg.ton_msg.clone();

    let msg_value = msg.value();
    let address = ton_msg.dst().unwrap();

    if let Some(state_init) = ton_msg.state_init() {
        let wc = address.workchain_id() as i8;
        deploy_contract2(&mut gs, None, state_init.clone(), None, "".to_owned(), wc, 0).unwrap();
    }

    let (exit_code, out_actions, gas) = exec_contract(
        &mut gs, address,
        ton_msg, Some(msg_id),
        None, Some(msg_value),
    );

    Ok((exit_code, out_actions, gas))
}

fn exec_contract(
    gs: &mut GlobalState,
    address: MsgAddressInt,
    ton_msg: TonBlockMessage,
    msg_id: Option<u32>,
    method: Option<String>,
    message_value: Option<u64>,
) -> (i32, Vec<String>, i64) {

    let mut contract_info = gs.get_contract(&address);

    let message_value2 = message_value.unwrap_or(
        get_msg_value(&ton_msg).unwrap_or(0)
    );

    if message_value2 > 0 {
        contract_info.set_balance(contract_info.balance() + message_value2);
    }

    let mut result = call_contract_ex(
        &contract_info,
        Some(ton_msg),
        message_value,
        gs.trace,
        make_config_params(&gs),
        gs.get_now(),
        None, // ticktock
    );

    result.info.inbound_msg_id = msg_id;
    gs.register_run_result(result.info.clone());

    let msgs = process_actions(
        gs,
        contract_info,
        &result,
        method,
        message_value2,
    );

    let msgs = gs.add_messages(msgs);
    let out_actions = messages_to_out_actions(msgs);

    (result.info.exit_code, out_actions, result.info.gas)
}

#[pyfunction]
fn set_contract_abi(address_str: String, abi_file: String) -> PyResult<()> {
    let addr = decode_address(&address_str);
    let abi = AbiInfo::from_file(abi_file);
    let mut gs = GLOBAL_STATE.lock().unwrap();
    let mut contract_info = gs.get_contract(&addr);
    contract_info.set_abi(abi);
    gs.set_contract(addr, contract_info);
    Ok(())
}

#[pyfunction]
fn call_ticktock(
    address_str: String,
    is_tock: bool,
) -> PyResult<(i32, Vec<String>, i64)> {
    let addr = decode_address(&address_str);

    let mut gs = GLOBAL_STATE.lock().unwrap();
    let trace = gs.trace;
    let contract_info = gs.get_contract(&addr);

    let result = call_contract_ex(
        &contract_info,
        None,
        None, // msg_value
        trace,
        make_config_params(&gs),
        gs.get_now(),
        Some(if is_tock { -1 } else { 0 }),
    );

    let msgs = process_actions(
        &mut gs,
        contract_info,
        &result,
        None, // method
        0, // message_value
    );

    let msgs = gs.add_messages(msgs);
    let out_actions = messages_to_out_actions(msgs);

    Ok((result.info.exit_code, out_actions, result.info.gas))
}

fn messages_to_out_actions(msgs: Vec<MessageInfo>) -> Vec<String> {
    msgs.iter().map(|msg| msg.json.to_string()).collect()
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
    let contract_info = gs.get_contract(&addr);

    if gs.trace {
        println!("encode_function_call(\"{}\",\"{}\")", method, params);
        // println!("private_key {:?}", private_key);
    }

    // TODO: to util?
    let keypair = private_key.map(|secret| {
        let secret = hex::decode(secret).unwrap();
        Keypair::from_bytes(&secret).expect("error: invalid key")
    });

    let abi_str = &contract_info.abi_str();

    let body = build_abi_body(
        abi_str,
        &method,
        &params,
        gs.make_time_header(),
        false, // internal
        keypair.as_ref(),
    );

    if body.is_err() {
        return Err(RuntimeError::py_err(body.err()));
    }

    let body = body.unwrap();

    let msg = create_inbound_msg(addr.clone(), &body, gs.get_now());

    // TODO: move to function
    let mut j = make_message_json(&gs, &abi_str, Some(method.clone()), &msg, 0);
    assert!(j["type"] == "call");
    j["type"] = JsonValue::from(if is_getter { "call_getter" } else { "external_call" });
    let msg_info = MessageInfo::create(msg.clone(), j);
    gs.add_message(msg_info);

    let (exit_code, out_actions, gas) = exec_contract(
        &mut gs, addr, msg,
        None, // msg_id
        Some(method.clone()), None,
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

// TODO: get rid of this structure
pub struct MsgInfo {
    pub ton_value: Option<u64>,
    pub src: Option<MsgAddressInt>,
    pub now: u64,
    pub bounced: bool,
    pub body: Option<SliceData>,
}

impl MsgInfo {
    pub fn from_body(body: &BuilderData, now: u64) -> Self {
        MsgInfo {
            ton_value: None,
            src: None,
            now: now,
            bounced: false,
            body: Some(body.into()),
        }
    }
}

fn create_inbound_msg(
    addr: MsgAddressInt,
    body: &BuilderData,
    now: u64,
) -> TonBlockMessage {
    let msg_info = MsgInfo::from_body(&body, now);
    create_inbound_msg2(-1, &msg_info, addr, now).unwrap()
}

//util?
fn create_inbound_msg2(         // TODO: bad function name and this function is used in only one place
    selector: i32,
    msg_info: &MsgInfo,
    dst: MsgAddressInt,
    now: u64
) -> Option<TonBlockMessage> {
    match selector {
        0 => {
            let src = match &msg_info.src {
                Some(addr) => addr.clone(),
                None => MsgAddressInt::with_standart(None, 0, [0u8; 32].into()).unwrap(),
            };
            Some(create_internal_msg(
                src,
                dst,
                CurrencyCollection::with_grams(0),
                1,
                now as u32,
                msg_info.body.clone(),
                msg_info.bounced,
            ))
        },
        -1 => {
            let src = match &msg_info.src {
                Some(_addr) => {
                    // TODO: rewrite this code
                    panic!("Unexpected address");
                },
                None => {
                    // TODO: Use MsgAdressNone?
                    MsgAddressExt::with_extern(
                        BuilderData::with_raw(vec![0x55; 8], 64).unwrap().into()
                    ).unwrap()
                },
            };
            Some(create_external_inbound_msg(
                src,
                dst,
                msg_info.body.clone(),
            ))
        },
        _ => None,
    }
}

// TODO: move!
pub fn make_message_json(
    gs: &GlobalState,
    abi_str: &String,
    method: Option<String>,
    out_msg: &TonBlockMessage,
    additional_value: u64,
) -> JsonValue {
    let mut j = decode_body(gs, &abi_str, method, out_msg.body(),
                            out_msg.is_internal());
    if let Some(value) = get_msg_value(&out_msg) {
        j["value"] = JsonValue::from(value + additional_value);
    }

    j["timestamp"] = JsonValue::from(gs.get_now());
    j
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
    let jsons : JsonValue = gs.messages.iter().map(|msg| msg.json.clone()).collect();
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

