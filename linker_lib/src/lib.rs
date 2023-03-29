/*
    This file is part of Ever OS.

    Ever OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2023 (c) EverX
*/

/*

    TODO:
        - move [pyfunction] code to separate file

*/

use global_state::ContractInfo;
use serde_json::Value as JsonValue;

use ed25519::Signature;
use ed25519_dalek::{
    Keypair, Signer
};

use rand::{rngs::{OsRng, StdRng}, SeedableRng};

use pyo3::prelude::{PyModule, PyResult, Python, pyfunction, pymodule};
use pyo3::wrap_pyfunction;
use pyo3::exceptions::PyRuntimeError;

use ton_block_json::{parse_config_with_mandatory_params, serialize_known_config_param, SerializationMode};
use std::sync::Arc;

use ton_block::{
    Serializable, CurrencyCollection, Deserializable,
};

use ton_types::{
    SliceData, Cell,
    serialize_toc,
    deserialize_tree_of_cells_inmem,
};

mod printer;
mod util;
mod abi;
mod actions;
mod debots;
mod debug_info;
mod global_state;
mod exec;
mod call_contract;
mod messages;

use global_state::{
    GlobalState, GlobalConfig, GLOBAL_STATE,
};

use util::{
    decode_address, load_from_file,
};

use messages::{
    CallContractMsgInfo,
    MsgInfo,
};

use debots::{
    build_internal_message, build_external_message,
};

use exec::{
    exec_contract_and_process_actions,
    generate_contract_address,
    dispatch_message_impl,
    deploy_contract_impl,
    call_contract_impl,
    run_get_contract_impl,
    load_state_init,
    encode_message_body_impl,
    decode_message, send_external_message_impl,
};

#[pyfunction]
fn trace_on() -> PyResult<()> {
    GLOBAL_STATE.lock().unwrap().trace_on = true;
    Ok(())
}

#[pyfunction]
fn set_debot_keypair(secret: Option<String>, pubkey: Option<String>) -> PyResult<()> {
    let keypair = secret.map(|secret| ton_client::crypto::KeyPair::new(pubkey.unwrap(), secret));
    GLOBAL_STATE.lock().unwrap().debot_keypair = keypair;
    Ok(())
}

#[pyfunction]
fn get_global_config() -> PyResult<GlobalConfig> {
    let config = GLOBAL_STATE.lock().unwrap().config.clone();
    Ok(config)
}

#[pyfunction]
fn set_global_config(cfg: GlobalConfig) -> PyResult<()> {
    let mut gs = GLOBAL_STATE.lock().unwrap();
    gs.config = cfg;
    Ok(())
}

#[pyfunction]
fn gen_addr(
    contract_file: String,
    abi_file: String,
    initial_data: Option<String>,
    pubkey: Option<String>,
    private_key: Option<String>,
    wc: i8
) -> PyResult<String> {
    let mut gs = GLOBAL_STATE.lock().unwrap();
    // let trace = gs.is_trace(1);

    let abi_info = gs.all_abis.read_from_file(&abi_file).map_err(PyRuntimeError::new_err)?;

    let state_init = load_state_init(
        &mut gs,
        &contract_file,
        &abi_file,
        &abi_info,
        &None,  // ctor_params
        &initial_data,
        &pubkey,
        &private_key,
    ).map_err(PyRuntimeError::new_err)?;
    
    let addr = generate_contract_address(&state_init, wc);
    let addr_str = format!("{}", addr);

    Ok(addr_str)
}

#[pyfunction]
fn deploy_contract(
    contract_file: String,
    abi_file: String,
    ctor_params: Option<String>,
    initial_data: Option<String>,
    pubkey: Option<String>,
    private_key: Option<String>,
    wc: i8,
    override_address: Option<String>,
    balance: u64,
) -> PyResult<String> {
    let mut gs = GLOBAL_STATE.lock().unwrap();
    // let trace = gs.is_trace(1);

    let abi_info = gs.all_abis.read_from_file(&abi_file).map_err(PyRuntimeError::new_err)?;

    let state_init = load_state_init(
        &mut gs,
        &contract_file,
        &abi_file,
        &abi_info,
        &ctor_params,
        &initial_data,
        &pubkey,
        &private_key,
    ).map_err(PyRuntimeError::new_err)?;

    let target_address = override_address.map(decode_address);
    deploy_contract_impl(
        &mut gs,
        Some(contract_file),
        state_init,
        target_address,
        abi_info,
        wc,
        balance,
    ).map_err(PyRuntimeError::new_err)
}

#[pyfunction]
fn fetch_contract_state(address: String) -> PyResult<(Option<String>, Option<String>)> {
    let address = decode_address(&address);
    let gs = GLOBAL_STATE.lock().unwrap();
    let contract = gs.get_contract(&address);
    if contract.is_none() {
        return Ok((None, None))
    }
    let contract = contract.unwrap();
    let state_init = contract.state_init();

    let code = state_init.code.as_ref().unwrap();
    let code = serialize_toc(code).unwrap();
    let code = base64::encode(code);
    let data = state_init.data.as_ref().unwrap();
    let data = serialize_toc(data).unwrap();
    let data = base64::encode(data);

    Ok((Some(code), Some(data)))
}

#[pyfunction]
fn store_contract_state(address: String, code: String, data: String) -> PyResult<()> {
    let address = decode_address(&address);
    let mut gs = GLOBAL_STATE.lock().unwrap();
    let mut contract = match gs.get_contract(&address) {
        Some(contract) => contract,
        None => ContractInfo::with_address(address.clone())
    };
    let mut state_init = contract.state_init().clone();
    if !code.is_empty() {
        state_init.set_code(decode_cell(&code));
    }
    if !data.is_empty() {
        state_init.set_data(decode_cell(&data));
    }
    contract.set_state_init(state_init);
    gs.set_contract(address, contract);

    Ok(())
}

#[pyfunction]
fn save_tvc(address: String, filename: String) -> PyResult<()> {
    let address = decode_address(&address);
    let gs = GLOBAL_STATE.lock().unwrap();
    let contract = gs.get_contract(&address).unwrap();

    contract
        .state_init()
        .write_to_file(&filename)
        .unwrap_or_else(|e| panic!("Write to file {} failed: {}", filename, e));
    Ok(())
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
fn dispatch_message(msg_id: u32) -> PyResult<String> {
    let mut gs = GLOBAL_STATE.lock().unwrap();
    let result = dispatch_message_impl(&mut gs, msg_id);
    gs.last_trace = result.trace.clone();
    Ok(result.to_string())
}

#[pyfunction]
fn set_contract_abi(address_str: Option<String>, abi_file: String) -> PyResult<()> {
    let mut gs = GLOBAL_STATE.lock().unwrap();
    let abi_info = gs.all_abis.read_from_file(&abi_file).map_err(PyRuntimeError::new_err)?;
    if let Some(address_str) = address_str {
        let addr = decode_address(&address_str);
        let contract_info = gs.get_contract(&addr);
        if contract_info.is_none() {
            let err = format!("Unable to set ABI for non-existent address {}", addr);
            return Err(PyRuntimeError::new_err(err));
        }
        let mut contract_info = contract_info.unwrap();
        contract_info.set_abi(abi_info);
        gs.set_contract(addr, contract_info);
    }
    Ok(())
}

#[pyfunction]
fn call_ticktock(
    address_str: String,
    is_tock: bool,
) -> PyResult<String> {
    let address = decode_address(&address_str);

    let mut gs = GLOBAL_STATE.lock().unwrap();
    // TODO: move to call_ticktock_impl()
    let msg_info = CallContractMsgInfo::with_ticktock(is_tock, address);

    let result = exec_contract_and_process_actions(
        &mut gs,
        &msg_info,
        None, // method
        false, // is_debot_call
    );

    // TODO: register in gs.messages?

    Ok(result.to_string())
}

#[pyfunction]
fn log_str(
    msg: String,
) -> PyResult<()> {

    let mut gs = GLOBAL_STATE.lock().unwrap();
    gs.log_str(msg);

    Ok(())
}

#[pyfunction]
fn call_contract(                   // TODO: is this message added to message store?
    address_str: String,
    method: String,
    is_getter: bool,
    is_debot: bool,
    params: String,
    private_key: Option<String>,
) -> PyResult<String> {
    let mut gs = GLOBAL_STATE.lock().unwrap();
    let result =
        call_contract_impl(&mut gs, &address_str, &method,
                           is_getter, is_debot, &params, private_key);
    if let Ok(ref result) = result {
        gs.last_trace = result.trace.clone();
    }
    let result = result.map_err(PyRuntimeError::new_err)?;
    Ok(result.to_string())
}

#[pyfunction]
fn run_get(
    address_str: String,
    method: String,
    params: String,
) -> PyResult<String> {
    let mut gs = GLOBAL_STATE.lock().unwrap();
    match run_get_contract_impl(&mut gs, &address_str, &method, &params) {
        Ok(result) => {
            gs.last_trace = result.trace.clone();
            Ok(result.to_string())
        }
        Err(e) => Err(PyRuntimeError::new_err(e))
    }
}

#[pyfunction]
fn send_external_message(
    address_str: String,
    message: String,
) -> PyResult<String> {
    let mut gs = GLOBAL_STATE.lock().unwrap();
    let result = send_external_message_impl(&mut gs, &address_str, &message);
    Ok(result.to_string())
}

// ---------------------------------------------------------------------------------------

#[pyfunction]
fn set_now(now: u64) -> PyResult<()> {
    let mut gs = GLOBAL_STATE.lock().unwrap();
    gs.set_now(now);
    Ok(())
}

#[pyfunction]
fn get_now() -> PyResult<u64> {
    let gs = GLOBAL_STATE.lock().unwrap();
    let result = gs.get_now();

    Ok(result)
}

#[pyfunction]
fn set_config_param(idx: u32, cell: String) -> PyResult<()> {
    let mut gs = GLOBAL_STATE.lock().unwrap();

    let cell = decode_cell(&cell);

    let is_empty = cell.bit_length() == 0;
    if gs.is_trace(1) {
        println!("set_config_param {} is_empty={}", idx, is_empty);
    }
    if is_empty {
        gs.config_params.remove(&idx);
    } else {
        gs.config_params.insert(idx, cell);
    }

    Ok(())
}

#[pyfunction]
fn parse_config_param(json: String) -> PyResult<String> {
    let config_json = serde_json::from_str::<serde_json::Value>(&json)
        .unwrap_or_else(|e| panic!("failed to parse {}", e));
    let config_json = config_json.as_object()
        .unwrap_or_else(|| panic!("config param is not object"));
    let (key, _value) = config_json.iter().next()
        .unwrap_or_else(|| panic!("no p parameter"));
    let index = key.strip_prefix('p')
        .unwrap_or_else(|| panic!("parameter index must start with p"));
    let index = index.parse::<u32>()
        .unwrap_or_else(|err| panic!("param index wrong {}: {}", index, err));
    // let value = value.as_object()
    //     .unwrap_or_else(|| panic!("param is not object"));
    let config_params = parse_config_with_mandatory_params(config_json, &[index])
        .unwrap_or_else(|err| panic!("cannot parse config param {}", err));
    let index = SliceData::load_builder(index.write_to_new_cell().unwrap()).unwrap();
    let cell = match config_params.config_params.get(index) {
        Ok(Some(param)) => {
            param.reference_opt(0)
                .unwrap_or_else(|| panic!("param doesn't have reference"))
        }
        Ok(None) => panic!("no parameter after parsing"),
        Err(err) => panic!("parsing parameter error {}", err),
    };
    match ton_types::serialize_toc(&cell) {
        Ok(bytes) => Ok(base64::encode(bytes)),
        Err(err) => panic!("cannot create TOC {}", err)
    }
}

#[pyfunction]
fn print_config_param(index: u32, cell: String) -> PyResult<String> {
    // let bytes = base64::decode(&param)
    //     .unwrap_or_else(|err| panic!("cannot parse base64 {}", err));
    //     .unwrap_or_else(|err| panic!("cannot deserialize TOC {}", err));
    let cell = decode_cell(&cell);
    if cell == Cell::default() {
        return Ok("no parameter".to_string())
    }
    let mut slice = SliceData::load_cell(cell).unwrap();
    match serialize_known_config_param(index, &mut slice, SerializationMode::Debug) {
        Ok(Some(config_param)) => Ok(config_param.to_string()),
        Ok(None) => Ok("None".to_string()),
        Err(err) => Ok(err.to_string())
    }
}

#[pyfunction]
fn reset_all() -> PyResult<()> {
    use std::ops::DerefMut;
    let mut gs = GLOBAL_STATE.lock().unwrap();
    *gs.deref_mut() = GlobalState::default();
    Ok(())
}

#[pyfunction]
fn make_keypair(seed : Option<u64>) -> PyResult<(String, String)> {
    let keypair = match seed {
        Some(seed) => {
            let mut csprng = StdRng::seed_from_u64(seed);
            Keypair::generate(&mut csprng)
        },
        None => {
            let mut csprng = OsRng{};
            Keypair::generate(&mut csprng)
        }
    };
    let secret = keypair.to_bytes();
    let secret = hex::encode(secret);
    let public = hex::encode(keypair.public.as_bytes());
    Ok((secret, public))
}

#[pyfunction]
fn sign_cell(cell: String, secret: String) -> PyResult<String> {
    let cell = decode_cell(&cell);
    if cell.references_count() != 0 {
        return Ok("use sign_cell_hash to sign cell with references".to_string())
    }

    let secret = hex::decode(secret).unwrap();
    let keypair = Keypair::from_bytes(&secret).expect("error: invalid key");

    let signature = keypair.sign(cell.data()).to_bytes();

    keypair.verify(cell.data(), &Signature::from_bytes(&signature).unwrap()).unwrap();

    Ok(hex::encode(signature))
}

#[pyfunction]
fn sign_cell_hash(cell: String, secret: String) -> PyResult<String> {
    let cell = decode_cell(&cell);

    let secret = hex::decode(secret).unwrap();
    let keypair = Keypair::from_bytes(&secret).expect("error: invalid key");

    let hash = cell.repr_hash();
    let signature = keypair.sign(hash.as_slice()).to_bytes();

    keypair.verify(hash.as_slice(), &Signature::from_bytes(&signature).unwrap()).unwrap();

    Ok(hex::encode(signature))
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
    let jsons: JsonValue = gs.messages.to_json();
    let result = serde_json::to_string(&jsons).unwrap();
    Ok(result)
}

#[pyfunction]
fn get_last_trace() -> PyResult<String> {
    let gs = GLOBAL_STATE.lock().unwrap();
    let result = serde_json::to_string(&gs.last_trace).unwrap();
    Ok(result)
}

#[pyfunction]
fn get_last_error_msg() -> PyResult<Option<String>> {
    let gs = GLOBAL_STATE.lock().unwrap();
    Ok(gs.last_error_msg.clone())
}

fn dump_cell_rec(cell: Cell, pfx: String) {
    let slice = SliceData::load_cell(cell).unwrap();
    println!("{}> {:x}", pfx, slice);
    let n = slice.remaining_references();
    let pfx = pfx + "  ";
    for i in 0..n {
        dump_cell_rec(slice.reference(i).unwrap(), pfx.clone());
    }
}

#[pyfunction]
fn dump_cell(cell: String) -> PyResult<()> {
    let cell = decode_cell(&cell);
    // println!("cell = {:?}", cell);
    // println!("cell = {}", cell);
    // println!("cell = {:x}", cell);
    // let slice: SliceData = cell.clone().into();

    // println!("slice = {:?}", slice);
    // println!("slice = {}", slice);
    // println!("slice = {:x}", slice);

    dump_cell_rec(cell, "".to_string());

    Ok(())
}

#[pyfunction]
fn load_account_state(address: String, filename: String, abi_file: String) -> PyResult<()> {
    let address = address.parse::<ton_block::MsgAddressInt>()
        .map_err(|_| PyRuntimeError::new_err(format!("Failed to parse address: {address}")))?;
    let mut gs = GLOBAL_STATE.lock().unwrap();

    let account = ton_block::Account::construct_from_file(&filename)
        .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;

    let balance = account.balance().map_or(0, |cc| cc.grams.as_u64().unwrap());
    let state_init = account.state_init().unwrap().to_owned();
    let abi_info = gs.all_abis.read_from_file(&abi_file).map_err(PyRuntimeError::new_err)?;
    
    let info = ContractInfo::create(address.clone(), None, state_init, abi_info, balance);

    gs.set_contract(address, info);
    Ok(())
}

#[pyfunction]
fn load_state_cell(filename: String) -> PyResult<String> {
    let state_init = load_from_file(&filename).map_err(PyRuntimeError::new_err)?;
    let bytes = state_init.write_to_bytes().unwrap();
    Ok(base64::encode(bytes))
}

#[pyfunction]
fn load_code_cell(filename: String) -> PyResult<String> {
    let state_init = load_from_file(&filename).map_err(PyRuntimeError::new_err)?;
    let bytes = serialize_toc(&state_init.code.unwrap()).unwrap();
    Ok(base64::encode(bytes))
}

#[pyfunction]
fn load_data_cell(filename: String) -> PyResult<String> {
    // TODO: add tests for that
    match load_from_file(&filename) {
        Ok(state_init) => {
            let bytes = serialize_toc(&state_init.data.unwrap()).unwrap();
            Ok(base64::encode(bytes))
        }
        Err(e) => Err(PyRuntimeError::new_err(e))
    }
}

fn decode_cell(cell: &str) -> Cell {
    let cell = Arc::new(base64::decode(cell).unwrap());
    deserialize_tree_of_cells_inmem(cell).unwrap()
}

#[pyfunction]
fn get_compiler_version_from_cell(cell: String) -> PyResult<Option<String>> {
    let cell = decode_cell(&cell);
    let result = ton_client::boc::get_compiler_version_from_cell(cell).unwrap();
    Ok(result)
}

#[pyfunction]
fn get_cell_repr_hash(cell: String) -> PyResult<String> {
    // TODO: make CellWrapper class interoperable with Python
    let cell = decode_cell(&cell);
    let hash = cell.repr_hash().as_hex_string();
    Ok(hash)
}

#[pyfunction]
fn get_msg_body(msg_id: u32) -> PyResult<String> {
    let gs = GLOBAL_STATE.lock().unwrap();
    let msg_info: MsgInfo = (*gs.messages.get(msg_id)).clone();
    let ton_msg = msg_info.ton_msg().unwrap().clone();
    let body = ton_msg.body().unwrap();
    let body_str = format!("{:?}", body);
    Ok(body_str)
}


#[pyfunction]
fn encode_message_body(_adress: String, abi_file: String, method: String, params: String) -> PyResult<String> {
    let mut gs = GLOBAL_STATE.lock().unwrap();
    let abi_info = gs.all_abis.read_from_file(&abi_file).map_err(PyRuntimeError::new_err)?;
    let cell = encode_message_body_impl(&abi_info, method, params);
    let result = serialize_toc(&cell.unwrap()).unwrap();
    Ok(base64::encode(result))
}

#[pyfunction]
fn debot_translate_getter_answer(msg_id: u32) -> PyResult<String> {
    let mut gs = GLOBAL_STATE.lock().unwrap();
    let msg_info = debots::debot_translate_getter_answer_impl(&mut gs, msg_id)
        .map_err(PyRuntimeError::new_err)?;
    Ok(msg_info.json_str())
}

#[pyfunction]
fn build_int_msg(src: String, dst: String, body: String, value: u64) -> PyResult<String> {
    let mut gs = GLOBAL_STATE.lock().unwrap();

    let src = decode_address(&src);
    let dst = decode_address(&dst);

    let contract = gs.get_contract(&dst).unwrap();

    let body = decode_cell(&body);
    let body = SliceData::load_cell(body).unwrap();

    let msg = build_internal_message(src, dst, body, CurrencyCollection::with_grams(value));

    let j = decode_message(&gs, contract.abi_info(), None, &msg, 0, false);
    let msg_info = MsgInfo::create(msg, j);
    let msg_info = gs.messages.add(msg_info);

    Ok(msg_info.json_str())
}

#[pyfunction]
fn build_ext_msg(src: String, dst: String, body: String) -> PyResult<String> {
    let src = src.parse().unwrap();
    let dst = decode_address(&dst);
    let body = decode_cell(&body);
    let body = SliceData::load_cell(body).unwrap();

    let msg = build_external_message(src, dst, body);

    let bytes = msg.write_to_bytes().unwrap();

    Ok(base64::encode(bytes))
}


/////////////////////////////////////////////////////////////////////////////////////
/// A Python module implemented in Rust.
#[pymodule]
fn linker_lib(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_wrapped(wrap_pyfunction!(reset_all))?;

    m.add_wrapped(wrap_pyfunction!(deploy_contract))?;
    m.add_wrapped(wrap_pyfunction!(gen_addr))?;
    m.add_wrapped(wrap_pyfunction!(run_get))?;
    m.add_wrapped(wrap_pyfunction!(call_contract))?;
    m.add_wrapped(wrap_pyfunction!(call_ticktock))?;
    m.add_wrapped(wrap_pyfunction!(send_external_message))?;
    m.add_wrapped(wrap_pyfunction!(log_str))?;
    m.add_wrapped(wrap_pyfunction!(get_balance))?;
    m.add_wrapped(wrap_pyfunction!(set_balance))?;
    m.add_wrapped(wrap_pyfunction!(fetch_contract_state))?;
    m.add_wrapped(wrap_pyfunction!(store_contract_state))?;

    m.add_wrapped(wrap_pyfunction!(dispatch_message))?;
    m.add_wrapped(wrap_pyfunction!(debot_translate_getter_answer))?;
    m.add_wrapped(wrap_pyfunction!(build_int_msg))?;
    m.add_wrapped(wrap_pyfunction!(build_ext_msg))?;

    m.add_wrapped(wrap_pyfunction!(get_global_config))?;
    m.add_wrapped(wrap_pyfunction!(set_global_config))?;

    m.add_wrapped(wrap_pyfunction!(set_now))?;
    m.add_wrapped(wrap_pyfunction!(get_now))?;
    m.add_wrapped(wrap_pyfunction!(trace_on))?;
    m.add_wrapped(wrap_pyfunction!(set_contract_abi))?;
    m.add_wrapped(wrap_pyfunction!(set_config_param))?;
    m.add_wrapped(wrap_pyfunction!(parse_config_param))?;
    m.add_wrapped(wrap_pyfunction!(print_config_param))?;

    m.add_wrapped(wrap_pyfunction!(make_keypair))?;
    m.add_wrapped(wrap_pyfunction!(sign_cell))?;
    m.add_wrapped(wrap_pyfunction!(sign_cell_hash))?;
    m.add_wrapped(wrap_pyfunction!(load_account_state))?;
    m.add_wrapped(wrap_pyfunction!(load_state_cell))?;
    m.add_wrapped(wrap_pyfunction!(load_code_cell))?;
    m.add_wrapped(wrap_pyfunction!(load_data_cell))?;
    m.add_wrapped(wrap_pyfunction!(get_compiler_version_from_cell))?;
    m.add_wrapped(wrap_pyfunction!(get_cell_repr_hash))?;
    m.add_wrapped(wrap_pyfunction!(encode_message_body))?;
    m.add_wrapped(wrap_pyfunction!(dump_cell))?;
    m.add_wrapped(wrap_pyfunction!(get_msg_body))?;

    m.add_wrapped(wrap_pyfunction!(get_all_runs))?;
    m.add_wrapped(wrap_pyfunction!(get_all_messages))?;
    m.add_wrapped(wrap_pyfunction!(get_last_trace))?;
    m.add_wrapped(wrap_pyfunction!(get_last_error_msg))?;

    m.add_wrapped(wrap_pyfunction!(set_debot_keypair))?;
    m.add_wrapped(wrap_pyfunction!(save_tvc))?;

    Ok(())
}

