/*
    This file is part of Ever OS.

    Ever OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2023 (c) EverX
*/

use std::collections::HashMap;

use ed25519_dalek::{
    Keypair, PublicKey, /*SecretKey*/
};

use ton_types::{
    SliceData, BuilderData,
};

use ton_block::{
    Message as TonBlockMessage,
    StateInit,
};

use ton_abi::json_abi::{
    encode_function_call,
    decode_function_response,
    decode_unknown_function_response,
    decode_unknown_function_call,
};

use crate::global_state::{
    GlobalState,
};

use crate::messages::{
    MsgAbiInfo,
};

#[derive(Default)]
pub struct AllAbis {
    all_abis: HashMap<String, AbiInfo>,
}

impl AllAbis {
    pub fn register_abi(&mut self, abi: AbiInfo) {
        self.all_abis.insert(abi.filename.clone(), abi);
    }

    fn values(&self) -> Vec<String> {
        self.all_abis.iter().map(|pair| pair.1.text().clone()).collect()
    }

    fn decode_function_call(&self, body: &SliceData, internal: bool, abi_str: &str) -> Option<ton_abi::DecodedMessage> {
        let res = decode_unknown_function_call(abi_str.to_owned(), body.clone(), internal, false);
        if let Ok(res) = res {
            return Some(res);
        }
        for abi_str in self.values() {
            // println!("contract: {}", &contract.name);
            let res = decode_unknown_function_call(abi_str, body.clone(), internal, false);
            if let Ok(res) = res {
                return Some(res);
            }
        }
        None
    }

    pub fn read_from_file(&mut self, filename: &String) -> Result<AbiInfo, String> {
        if let Some(abi_info) = self.all_abis.get(filename) {
            Ok(abi_info.clone())
        } else {
            let abi_info = AbiInfo::from_file(filename.clone())?;
            self.all_abis.insert(filename.clone(), abi_info.clone());
            Ok(abi_info)
        }
    }

}

#[derive(Default, Clone)]
pub struct AbiInfo {
    filename: String,
    text: String,
}

impl AbiInfo {
    fn from_file(filename: String) -> Result<AbiInfo, String> {
        let abi_str = load_abi_json_string(&filename)?;
        let abi_info = AbiInfo {
            filename,
            text: abi_str,
        };
        Ok(abi_info)
    }
    pub fn text(&self) -> &String {
        &self.text
    }
}

pub fn decode_body(
    gs: &GlobalState,
    abi_info: &AbiInfo,
    method: Option<String>,
    out_msg: &TonBlockMessage,
    is_debot_call: bool,
) -> MsgAbiInfo {

    let internal = out_msg.is_internal();
    let body = out_msg.body();

    // TODO: refactor this function

    if gs.is_trace(3) {
        println!("decode_body: {:?} {:?}", &method, body);
    }

    if body.is_none() {
        return MsgAbiInfo::create_empty();
    }
    
    let body = body.unwrap();

    let abi_str = abi_info.text();

    // Check for answer from getter
    if let Some(method) = method {
        let s = decode_function_response(
            abi_str.clone(),
            method.clone(),
            body.clone(),
            internal,
            false,
        );
        if let Ok(s) = s {
            return MsgAbiInfo::create_answer(s, method);
        }
    }

    // Check for a call to a remote method
    if let Some(res) = gs.all_abis.decode_function_call(&body, internal, abi_str) {
        if gs.is_trace(5) {
            println!("decode_function_call - {} {}", res.function_name, res.params);
        }
        return MsgAbiInfo::create_call(res.params, res.function_name);
    }

    // Check for event
    let s = decode_unknown_function_response(abi_str.clone(), body.clone(), internal, false);
    if let Ok(s) = s {
        if gs.is_trace(5) {
            println!("decode_unknown_function_response - {} {}", s.function_name, s.params);
        }
        if is_debot_call {
            let mut abi_info = MsgAbiInfo::create_answer(s.params, s.function_name);
            abi_info.set_debot_mode();
            return abi_info;
        } else {
            return MsgAbiInfo::create_event(s.params, s.function_name);
        }
    }

    if gs.is_trace(1) {
        println!("Unknown message! body = {:?}", body);
    }
    
    MsgAbiInfo::create_unknown()
}

pub fn build_abi_body(
    abi_info: &AbiInfo,
    method: &str,
    params: &str,
    header: Option<String>,
    internal: bool,
    pair: Option<&Keypair>,
    address: Option<String>,
) -> Result<BuilderData, String> {
    assert!(internal || address.is_some());
    encode_function_call(
        abi_info.text().clone(),
        method.to_owned(),
        header,
        params.to_owned(),
        internal,
        pair,
        address
    ).map_err(|e| format!("cannot encode abi body: {:?}", e))
}

pub fn set_public_key(state_init: &mut StateInit, pubkey: String) -> Result<(), String> {
    let pubkey = hex::decode(pubkey)
        .map_err(|e| format!("cannot decode public key: {}", e))?;
    let pubkey = PublicKey::from_bytes(&pubkey).unwrap();
    let data = SliceData::load_cell(state_init.data.clone().unwrap()).unwrap();
    let new_data = ton_abi::Contract::insert_pubkey(data, pubkey.as_bytes()).unwrap();
    state_init.set_data(new_data.into_cell());
    Ok(())
}

fn load_abi_json_string(abi_file: &str) -> Result<String, String> {
    std::fs::read_to_string(abi_file)
        .map_err(|e| format!("unable to read ABI file '{}': {}", abi_file, e))
}
