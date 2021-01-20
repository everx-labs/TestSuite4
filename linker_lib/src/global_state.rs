/*
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
*/

use std::sync::Mutex;
use std::collections::HashMap;
// use std::collections::HashSet;

use serde_json::Value as JsonValue;

use ton_block::{
    Message as TonBlockMessage,
    MsgAddressInt, CommonMsgInfo, StateInit,
};

use ton_types::{
    SliceData, BuilderData, Cell, HashmapE, IBitstring,
    HashmapType,
};

use ton_abi::json_abi::{
    decode_unknown_function_call,
};

use crate::util::{
    get_now,
};

use crate::call_contract::{
    ExecutionResultInfo,
};

use crate::abi::{
    AbiInfo,
};

////////////////////////////////////////////////////////////////////////////////////////////

#[derive(Default)]
pub struct GlobalState {
    contracts: HashMap<MsgAddressInt, ContractInfo>,
    // all_abis: HashSet<String>,
    pub messages: Vec<MessageInfo>,
    pub trace: bool,
    pub config_params: HashMap<u32, Cell>,
    now: Option<u64>,
    now2: u64,
    pub runs: Vec<ExecutionResultInfo>,
}

lazy_static! {
    pub static ref GLOBAL_STATE: Mutex<GlobalState> = Mutex::new(GlobalState::default());
}

#[derive(Clone)]
pub struct ContractInfo {
    name: String,
    addr: MsgAddressInt,
    state_init: StateInit,
    abi_str: String,
    balance: u64,
}

impl ContractInfo {

    pub fn create(
        address: MsgAddressInt,
        contract_name: Option<String>,
        state_init: StateInit,
        abi_str: String,
        balance: u64,
    ) -> ContractInfo {
        ContractInfo {
            addr: address,
            name: contract_name.unwrap_or("n/a".to_string()),
            state_init: state_init,
            abi_str: abi_str,
            balance: balance,
        }
    }
    pub fn address(&self) -> &MsgAddressInt {
        &self.addr
    }

    pub fn abi_str(&self) -> &String {
        &self.abi_str
    }
    pub fn set_abi(&mut self, abi: AbiInfo) {
        self.abi_str = abi.text;
    }
    pub fn debug_info_filename(&self) -> String {
        format!("{}{}", self.name.trim_end_matches("tvc"), "debug.json")
    }
    pub fn balance(&self) -> u64 {
        self.balance
    }
    pub fn set_balance(&mut self, balance: u64) {
        self.balance = balance;
    }
    pub fn state_init(&self) -> &StateInit {
        &self.state_init
    }
    pub fn set_state_init(&mut self, state_init: StateInit) {
        self.state_init = state_init;
    }
}

#[derive(Clone, Debug)]
pub struct MessageInfo {
    message_id: u32,
    pub ton_msg: TonBlockMessage,
    pub json: JsonValue,
}

impl GlobalState {
    pub fn set_contract(&mut self, address: MsgAddressInt, info: ContractInfo) {
        assert!(address == *info.address());
        self.contracts.insert(address, info);
    }
    pub fn address_exists(&self, address: &MsgAddressInt) -> bool {
        self.contracts.contains_key(&address)
    }
    pub fn get_message(&self, id: u32) -> &MessageInfo {
        &self.messages[id as usize]
    }
    pub fn get_contract(&self, address: &MsgAddressInt) -> ContractInfo {
        // TODO: return an error in case of contact absense
        let state = self.contracts.get(&address);
        if state.is_none() {
            println!("Wrong contract address: {:?}\n", &address);
            assert!(state.is_some());
        }
        let info = state.unwrap();
        (*info).clone()
    }
    pub fn add_message(&mut self, msg_info: MessageInfo) -> MessageInfo {
        let mut msg_info = msg_info;
        msg_info.set_id(self.messages.len() as u32);
        self.messages.push(msg_info.clone());
        msg_info
    }
    pub fn add_messages(&mut self, msgs: Vec<MessageInfo>) -> Vec<MessageInfo> {
        msgs.into_iter().map(|msg| self.add_message(msg)).collect()
    }
    pub fn decode_function_call(&self, body: &SliceData, internal: bool) -> Option<ton_abi::DecodedMessage> {
        for contract in self.contracts.values() {
            // println!("contract: {}", &contract.name);
            let abi_str = contract.abi_str.clone();
            // TODO: move to abi.rs...
            let res = decode_unknown_function_call(abi_str, body.clone(), internal);
            if let Ok(res) = res {
                return Some(res);
            }
        }
        None
    }
    pub fn get_now(&self) -> u64 {
        self.now.unwrap_or(get_now())
    }
    pub fn make_time_header(&mut self) -> Option<String> {
        if self.now.is_none() {
            // Add sleep to avoid Replay Protection Error issue
            // TODO: investigate if it slows down tests or not
            std::thread::sleep(std::time::Duration::from_millis(1));
        }
        self.now.map(|v| {
            self.now2 += 1;
            format!("{{\"time\": {}}}", v*1000 + self.now2)
        })
    }
    pub fn set_now(&mut self, now: u64) {
        self.now  = Some(now);
        self.now2 = 0;
    }
    pub fn register_run_result(&mut self, mut result: ExecutionResultInfo) {
        result.run_id = Some(self.runs.len() as u32);
        self.runs.push(result);
    }
}

impl MessageInfo {
    pub fn create(ton_msg: TonBlockMessage, json: JsonValue) -> MessageInfo {
        MessageInfo {message_id: 0, ton_msg: ton_msg, json: json}
    }

    fn extended_json(&self) -> JsonValue {
        let mut j = self.json.clone();
        j["id"] = JsonValue::from(self.message_id);
        let hdr = self.ton_msg.header();
        if let CommonMsgInfo::IntMsgInfo(header) = hdr {
            j["src"] = JsonValue::from(format!("{}", header.src));
            j["dst"] = JsonValue::from(format!("{}", header.dst));
        }
        if let CommonMsgInfo::ExtInMsgInfo(header) = hdr {
            j["dst"] = JsonValue::from(format!("{}", header.dst));
        }
        if let CommonMsgInfo::ExtOutMsgInfo(header) = hdr {
            j["src"] = JsonValue::from(format!("{}", header.src));
            j["dst"] = JsonValue::from(format!("{}", header.dst));
        }
        j
    }

    pub fn set_id(&mut self, id: u32) {
        assert!(self.message_id == 0);
        self.message_id = id;
        self.json = self.extended_json();
    }

    pub fn value(&self) -> u64 {
        self.json["value"].as_u64().unwrap()
    }
}

pub fn make_config_params(gs: &GlobalState) -> Option<Cell> {
    let mut map = HashmapE::with_hashmap(32, None);
    for (key, value) in gs.config_params.clone() {
        let mut b = BuilderData::new();
        b.append_u32(key).unwrap();
        let key = b.into();
        map.setref(key, &value).unwrap();
    }
    map.data().map(|v| v.clone())
}

