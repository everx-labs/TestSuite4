/*
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
*/

use crate::{global_state::GlobalState, messages::MsgAbiInfo};
use ever_abi::json_abi::{
    decode_unknown_function_call, decode_unknown_function_response, encode_function_call,
};
use ever_block::{
    BuilderData, Ed25519PrivateKey, Message, SliceData, StateInit
};
use std::{collections::HashMap, convert::TryInto};

#[derive(Default)]
pub struct AllAbis {
    all_abis: HashMap<String, AbiInfo>,
}

impl AllAbis {
    pub fn register_abi(&mut self, abi: AbiInfo) {
        self.all_abis.insert(abi.filename.clone(), abi);
    }

    fn values(&self) -> Vec<String> {
        self.all_abis.values().map(|abi| abi.text().to_string()).collect()
    }

    fn decode_function_call(&self, body: &SliceData, internal: bool) -> Option<ever_abi::DecodedMessage> {
        for abi_str in self.values() {
            // println!("contract: {}", &contract.name);
            if let Ok(res) = decode_unknown_function_call(&abi_str, body.clone(), internal, false) {
                return Some(res);
            }
        }
        None
    }

    pub fn from_file(&mut self, filename: &String) -> Result<AbiInfo, String> {
        if !self.all_abis.contains_key(filename) {
            let info = AbiInfo::from_file(filename.clone())?;
            self.register_abi(info);
        }
        Ok(self.all_abis[filename].clone())
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
    pub fn text(&self) -> &str {
        self.text.as_str()
    }

    pub fn filename(&self) -> &str {
        self.filename.as_str()
    }
}

pub fn decode_body(
    gs: &GlobalState,
    abi_info: &AbiInfo,
    method: Option<String>,
    out_msg: &Message,
) -> MsgAbiInfo {

    let internal = out_msg.is_internal();
    let body = out_msg.body();

    // TODO: refactor this function

    if gs.trace {
        println!("decode_body {:?} {:?} {} {}", body, &method, abi_info.filename(), internal);
    }

    let Some(body) = body else {
        return MsgAbiInfo::create_empty();
    };

    // if gs.trace {
    //     println!("decode_body {:#.100}", body.cell());
    // }
    let abi_str = abi_info.text();

    // Check for answer from getter
    if let Some(method) = method {
        
        // if gs.trace {
        //     let mut data = body.clone();
        //     let function_id = data.get_next_u32().unwrap();
            
        //     let contract = ever_abi::Contract::load(abi_str.as_bytes()).unwrap();
        //     let function = contract.function(&method).unwrap();
        //     let result = function.decode_output(body.clone(), internal, false);
        //     match result {
        //         Ok(tokens) => {
        //             println!("decode params function_id: {:x} => {:x} {:?}", function_id, function.get_output_id(), tokens);
        //         }
        //         Err(e) => {
        //             println!("cannot decode params function_id: {:x} => {:x} {}", function_id, function.get_output_id(), e);
        //         }
        //     }

        //     let params = function.output_params();
        //     let mut cursor = data.clone().into();
        //     for param in params {
        //         let last = Some(param) == params.last();
        //         let result = ever_abi::TokenValue::read_from(&param.kind, cursor, last, &function.abi_version, false);
        //         match result {
        //             Ok((token_value, new_cursor)) => {
        //                 cursor = new_cursor;
        //                 println!("parsed param {}: {:?}", param.name, token_value);
        //             }
        //             Err(e) => {
        //                 println!("cannot parse param {}: {}", param.name, e);
        //                 break;
        //             }
        //         }
        //     }
        //     // if let Ok(set) = ever_block::ValidatorSet::construct_from(&mut data.clone()) {
        //     //     // for descr in set.list() {
        //     //     //     println!("validator: {:?}", descr);
        //     //     // }
        //     //     set.write_to_file("D:\\set.boc").unwrap();
        //     //     out_msg.write_to_file("D:\\msg.boc").unwrap();
        //     // }
        // }

        let contract = ever_abi::Contract::load(abi_str.as_bytes()).unwrap();
        let result = contract.decode_output(body.clone(), internal, false)
            .and_then(|result| ever_abi::token::Detokenizer::detokenize(&result.tokens));
        match result {
            Ok(s) => {
                if gs.trace {
                    println!("parsed params for method {}: {}", method, s);
                }
                return MsgAbiInfo::create_answer(s, method);
            }
            Err(e) => {
                if gs.trace {
                    println!("cannot decode params for method: {} {}", method, e);
                }
            }
        }
    }

    // Check for a call to a remote method
    if let Some(res) = gs.all_abis.decode_function_call(&body, internal) {
        // println!(">> {} {}", res.function_name, res.params);
        return MsgAbiInfo::create_call(res.params, res.function_name);
    }

    // Check for event
    let s = decode_unknown_function_response(abi_str, body.clone(), internal, true);
    if let Ok(s) = s {
        return MsgAbiInfo::create_event(s.params, s.function_name);
    }

    return MsgAbiInfo::create_unknown();
}

pub fn build_abi_body(
    abi_info: &AbiInfo,
    method: &str,
    params: &str,
    header: Option<&str>,
    internal: bool,
    sign_key: Option<&Ed25519PrivateKey>,
) -> Result<BuilderData, String> {
    encode_function_call(
        abi_info.text(),
        method,
        header,
        params,
        internal,
        sign_key,
        None, // TODO: check here
    ).map_err(|e| format!("cannot encode abi body: {:?}", e))
}

pub fn set_public_key(state_init: &mut StateInit, pubkey: String) -> Result<(), String> {
    let pubkey = hex::decode(pubkey)
        .map_err(|e| format!("cannot decode public key: {}", e))?;
    let data = SliceData::load_cell(state_init.data.clone().unwrap_or_default()).unwrap();
    let new_data = ever_abi::Contract::insert_pubkey(data, pubkey.as_slice().try_into().unwrap()).unwrap();
    state_init.set_data(new_data.into_cell());
    Ok(())
}

fn load_abi_json_string(abi_file: &str) -> Result<String, String> {
    std::fs::read_to_string(abi_file)
        .map_err(|e| format!("unable to read ABI file '{}': {}", abi_file, e))
}

#[test]
fn test_load_set() {
    let filename = "D:\\work/TestSuite4/elector/tests/binaries/Config.abi.json";
    let abi_info = AbiInfo::from_file(filename.to_string()).unwrap();
    let mut gs = GlobalState::default();
    gs.trace = true;
    let out_msg = Message::construct_from_file("D:\\msg.boc").unwrap();
    let info = decode_body(
        &gs,
        &abi_info,
        Some("get_next_vset".to_string()),
        &out_msg
    );
    println!("result: {:?}", info);
}