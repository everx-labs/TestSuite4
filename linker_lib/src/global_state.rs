/*
    This file is part of Ever OS.

    Ever OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
*/

use std::sync::{Arc, Mutex};
use std::collections::HashMap;

use num_format::{Locale, ToFormattedString};

use serde::{
    Serialize, Deserialize
};

use pyo3::prelude::*;

use ton_client::crypto::KeyPair;

use ton_block::{
    MsgAddressInt, StateInit,
};

use ton_types::{
    BuilderData, Cell, HashmapE, IBitstring,
    HashmapType,
};

use crate::util::{
    get_now, get_now_ms,
};

use crate::call_contract::{
    ExecutionResultInfo,
};

use crate::abi::{
    AbiInfo, AllAbis,
};

use crate::messages::{
    MsgInfo, MessageStorage,
};

use crate::debug_info::{
    TraceStepInfo,
};

////////////////////////////////////////////////////////////////////////////////////////////

#[pyclass]
#[derive(Default, Clone, Serialize, Deserialize)]
pub struct GlobalConfig {
    #[pyo3(get, set)]
                        pub trace_level: u64,
    #[pyo3(get, set)]
                        pub trace_tvm: bool,
    #[pyo3(get, set)]
                        pub gas_fee: bool,
    #[pyo3(get, set)]
                        pub global_gas_limit: u64,
    // pub trace_on: bool,
    // pub config_params: HashMap<u32, Cell>,
    // pub debot_keypair: Option<KeyPair>,
}

////////////////////////////////////////////////////////////////////////////////////////////

#[derive(Default)]
pub struct GlobalState {
    pub config: GlobalConfig,
    contracts: HashMap<MsgAddressInt, ContractInfo>,
    pub dummy_balances: HashMap<MsgAddressInt, u64>,
    pub all_abis: AllAbis,
    pub messages: MessageStorage,
    pub trace_on: bool,
    pub last_trace: Option<Vec<TraceStepInfo>>,
    pub last_error_msg: Option<String>,
    pub config_params: HashMap<u32, Cell>,
    pub debot_keypair: Option<KeyPair>,
    now: Option<u64>,
    now2: u64,
    pub lt: u64,
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
    abi_info: AbiInfo,
    balance: u64,
}

impl ContractInfo {

    pub fn create(
        address: MsgAddressInt,
        contract_name: Option<String>,
        state_init: StateInit,
        abi_info: AbiInfo,
        balance: u64,
    ) -> ContractInfo {
        ContractInfo {
            addr: address,
            name: contract_name.unwrap_or("n/a".to_string()),
            state_init: state_init,
            abi_info: abi_info,
            balance: balance,
        }
    }
    pub fn address(&self) -> &MsgAddressInt {
        &self.addr
    }

    pub fn abi_info(&self) -> &AbiInfo {
        &self.abi_info
    }

    pub fn set_abi(&mut self, abi: AbiInfo) {
        self.abi_info = abi;
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
    pub fn change_balance(&mut self, sign: i64, diff: u64, trace_level: u64) {
        if trace_level >= 10 {
            println!("!!!!! change_balance: {} {}", sign, diff.to_formatted_string(&Locale::en));
            println!("!!!!!   before : {}", self.balance.to_formatted_string(&Locale::en));
        }
        self.balance = if sign < 0 {
            assert!(diff <= self.balance);
            self.balance - diff
        } else {
            self.balance + diff
        };
        if trace_level >= 10 {
            println!("!!!!!   after  : {}", self.balance.to_formatted_string(&Locale::en));
        }
    }
    pub fn state_init(&self) -> &StateInit {
        &self.state_init
    }
    pub fn set_state_init(&mut self, state_init: StateInit) {
        self.state_init = state_init;
    }
}

impl GlobalState {

    pub fn is_trace(&self, level: u64) -> bool {
        level <= self.config.trace_level
    }

    pub fn set_contract(&mut self, address: MsgAddressInt, info: ContractInfo) {
        assert!(address == *info.address());
        self.all_abis.register_abi(info.abi_info().clone());
        self.contracts.insert(address, info);

    }
    pub fn remove_contract(&mut self, address: &MsgAddressInt) {
        self.contracts.remove(address);
    }
    pub fn address_exists(&self, address: &MsgAddressInt) -> bool {
        self.contracts.contains_key(&address)

    }
    pub fn get_contract(&self, address: &MsgAddressInt) -> Option<ContractInfo> {
        let state = self.contracts.get(&address);
        state.map(|info| (*info).clone())
    }

    pub fn add_messages(&mut self, msgs: Vec<MsgInfo>) -> Vec<String> {
        let msgs = msgs.into_iter().map(|msg|
            self.messages.add(msg)
        ).collect();
        messages_to_out_actions(msgs)       // TODO: refactor
    }

    pub fn get_now(&self) -> u64 {
        self.now.unwrap_or(get_now())
    }

    pub fn get_now_ms(&mut self) -> u64 {
        if self.now.is_none() {
            // Add sleep to avoid Replay Protection Error issue
            std::thread::sleep(std::time::Duration::from_millis(1));
        }
        self.now.map(|v| {
            self.now2 += 1;
            v*1000 + self.now2
        }).unwrap_or(get_now_ms())
    }
    
    pub fn make_time_header(&mut self) -> Option<String> {
        Some(format!("{{\"time\": {}}}", self.get_now_ms()))
    }

    pub fn set_now(&mut self, now: u64) {
        self.now  = Some(now);
        self.now2 = 0;
    }

    pub fn register_run_result(&mut self, mut result: ExecutionResultInfo) {
        result.run_id = Some(self.runs.len() as u32);
        self.runs.push(result);
    }

    pub fn log_str(&mut self, text: String) {
        let msg_info = MsgInfo::with_log_str(text, self.get_now());
        self.messages.add(msg_info);
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

fn messages_to_out_actions(msgs: Vec<Arc<MsgInfo>>) -> Vec<String> {
    msgs.iter().map(|msg| msg.json_str()).collect()
}

