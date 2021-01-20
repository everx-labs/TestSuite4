/*
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify 
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
*/

use serde_json::Value as JsonValue;

use ed25519_dalek::{
    Keypair, PublicKey, /*SecretKey*/
};

use ton_types::{
    SliceData, BuilderData,
};

use ton_block::{
    StateInit,
};

use ton_abi::json_abi::{
    encode_function_call,
    decode_function_response,
    decode_unknown_function_response,
};

use crate::global_state::{
    GlobalState,
};

pub struct AbiInfo {
    _filename: String,
    pub text: String,
}

impl AbiInfo {
    pub fn from_file(filename: String) -> AbiInfo {
        let abi_str = load_abi_json_string(&filename).unwrap();
        AbiInfo {
            _filename: filename,
            text: abi_str,
        }
    }
}

pub fn decode_body(
    gs: &GlobalState,
    abi_json: &str,
    method: Option<String>,
    body: Option<SliceData>,
    internal: bool,
) -> JsonValue {

    if gs.trace {
        println!("decode_body {:?} {:?}", body, &method);
    }

    if body.is_none() {
        return json!({
            "type": "empty",
        });
    }
    let body = body.unwrap();

    // Check for answer from getter
    if let Some(method) = method {
        let s = decode_function_response(
            abi_json.to_string(),
            method.clone(),
            body.clone(),
            internal
        );
        if s.is_ok() {
            let s = s.unwrap();
            let params: JsonValue = serde_json::from_str(&s).unwrap();
            return json!({
                "type": "answer",
                "method": method,
                "params": params,
            })
        }
    }

    // Check for a call to a remote method
    if let Some(res) = gs.decode_function_call(&body, internal) {
        // println!(">> {} {}", res.function_name, res.params);

        let params: JsonValue = serde_json::from_str(&res.params).unwrap();
        return json!({
            "type": "call",
            "method": res.function_name,
            "params": params,
        })
    }

    // Check for event
    let s = decode_unknown_function_response(abi_json.to_string(), body.clone(), internal);
    if s.is_ok() {
        let s = s.unwrap();
        let params: JsonValue = serde_json::from_str(&s.params).unwrap();
        let j = json!({
            "type": "event",
            "event": s.function_name,
            "params": params,
        });
        return j;
    }

    let j = json!({
        "type": "unknown",
    });
    return j;
}

pub fn build_abi_body(
    abi_str: &str,
    method: &str,
    params: &str,
    header: Option<String>,
    internal: bool,
    pair: Option<&Keypair>,
) -> Result<BuilderData, String> {
    encode_function_call(
        abi_str.to_owned(),
        method.to_owned(),
        header,
        params.to_owned(),
        internal,
        pair,
    ).map_err(|e| format!("cannot encode abi body: {:?}", e))
}

pub fn set_public_key(state_init: &mut StateInit, pubkey: String) -> Result<(), String> {
    let pubkey = hex::decode(pubkey)
        .map_err(|e| format!("cannot decode public key: {}", e))?;
    let pubkey = PublicKey::from_bytes(&pubkey).unwrap();
    let data = state_init.data.clone().unwrap().into();
    let new_data = ton_abi::Contract::insert_pubkey(data, pubkey.as_bytes()).unwrap();
    state_init.set_data(new_data.into_cell());
    Ok(())
}

fn load_abi_json_string(abi_file: &str) -> Result<String, String> {
    std::fs::read_to_string(abi_file)
        .map_err(|e| format!("unable to read ABI file: {}", e))
}
