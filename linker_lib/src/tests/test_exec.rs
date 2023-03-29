/*
    This file is part of Ever OS.

    Ever OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2022 (c) TON LABS
*/

use std::sync::Arc;

use crate::sign_cell;

use super::*;
use serde_json::Value;
use ton_block::Deserializable;
use ton_types::{deserialize_tree_of_cells_inmem, serialize_toc};

const GRAM: u64 = 1_000_000_000;

fn deploy_abi_config(gs: &mut GlobalState, address: &str) {
    let address = decode_address(address);
    let contract_file = "boc/Config.tvc".to_string();
    let abi_file = "boc/Config.abi.json".to_string();
    let abi_info = gs.all_abis.read_from_file(&abi_file).unwrap();
    let ctor_params = serde_json::json!({
        "elector_addr"       : "0x3333333333333333333333333333333333333333333333333333333333333333",
        "elect_for"          : 65536,
        "elect_begin_before" : 32768,
        "elect_end_before"   : 8192,
        "stake_held"         : 32768,
        "max_validators"     : 3,
        "main_validators"    : 100,
        "min_validators"     : 3,
        "min_stake"          : 10 * GRAM,
        "max_stake"          : 10000 * GRAM,
        "min_total_stake"    : 100 * GRAM,
        "max_stake_factor"   : 0x30000,
        "utime_since"        : 0,
        "utime_until"        : 86400,
    }).to_string();

    let state_init = load_state_init(
        gs,
        &contract_file,
        &abi_file,
        &abi_info,
        &Some(ctor_params),
        &None,
        &None,
        &None,
    ).unwrap();
    let contract = ContractInfo::create(address.clone(), None, state_init, abi_info, 1 << 32);
    gs.set_contract(address, contract);
}

fn get_answer(result: ExecutionResult2) -> Value {
    let answer: Value = result.out_actions[0].parse().unwrap();
    assert_eq!(answer["msg_type"], "answer");
    answer["params"]["value0"].clone()
}

fn run_method(gs: &mut GlobalState, address_str: &str, method: &str, params: Value) -> Value {
    let result = call_contract_impl(
        gs,
        address_str,
        method,
        true,
        false,
        &params.to_string(),
        None
    ).unwrap();
    get_answer(result)
}

#[test]
fn test_run_get_config() {
    let mut gs = crate::global_state::GLOBAL_STATE.lock().unwrap();

    let abi_config = "-1:7777777777777777777777777777777777777777777777777777777777777777";
    deploy_abi_config(&mut gs, abi_config);

    // gs.trace_on = true;
    // gs.config.trace_tvm = true;
    let address_str = "-1:5555555555555555555555555555555555555555555555555555555555555555";
    let address = decode_address(address_str);

    // private and public key
    let secret = "e0989f07c5c61b85d5977a1d7b45d661a332408785a89ae5cce192af78fd7bca3f43df88f25976a25a8dd1355c46e751503556e966d94ce8172105abc0d68f47";
    let state_init = StateInit::construct_from_file("boc/Config.FunC.tvc").unwrap();
    let abi_file = "boc/Config.abi.json".to_string();
    let abi_info = gs.all_abis.read_from_file(&abi_file).unwrap();
    let contract = ContractInfo::create(address.clone(), None, state_init, abi_info, 1 << 32);
    gs.set_contract(address, contract);
    let result = run_get_contract_impl(&mut gs, address_str, "seqno", "").unwrap();
    assert_eq!(result.stack, vec!("18"));

    let msg_seqno: u32 = result.stack[0].parse().unwrap();

    // prepare cell for siging
    let method = "upgrade_code_sign_helper";
    let state_init = StateInit::construct_from_file("boc/Config.tvc").unwrap();
    let code = state_init.code.unwrap();
    let code = base64::encode(serialize_toc(&code).unwrap());
    let params = serde_json::json!({
        "msg_seqno": msg_seqno,
        "valid_until": 2000000001,
        "code": code,
    });
    let answer = run_method(&mut gs, abi_config, method, params);
    let cell = answer.as_str().unwrap().to_string();
    let signature = sign_cell(cell, secret.to_string()).unwrap();
    assert_eq!(128, signature.len());

    // prepare cell with message body
    let method = "upgrade_code_func_builder";
    let params = serde_json::json!({
        "signature": signature,
        "msg_seqno": msg_seqno,
        "valid_until": 2000000001,
        "code": code,
    });
    let answer = run_method(&mut gs, abi_config, method, params);
    let body = answer.as_str().unwrap().to_string();

    gs.config.trace_tvm = true;
    // call external message to upgrade code
    let _result = send_external_message_impl(&mut gs, address_str, &body);
    // let cell = base64::decode(answer.as_str().unwrap()).unwrap();
    // let cell = deserialize_tree_of_cells_inmem(Arc::new(cell)).unwrap();
    // panic!("{}", result.to_string())
}

#[test]
fn test_call_contract_config() {
    let mut gs = crate::global_state::GLOBAL_STATE.lock().unwrap();
    let address_str = "-1:5555555555555555555555555555555555555555555555555555555555555555";
    deploy_abi_config(&mut gs, address_str);
    let method = "get_config_1";
    let result = call_contract_impl(&mut gs, address_str, method, true, false, "{}", None).unwrap();
    let answer = get_answer(result);
    let bytes = base64::decode(answer.as_str().unwrap()).unwrap();
    let cell = deserialize_tree_of_cells_inmem(Arc::new(bytes)).unwrap();
    let addr = hex::encode(cell.data());
    assert_eq!("3333333333333333333333333333333333333333333333333333333333333333", &addr);
}
