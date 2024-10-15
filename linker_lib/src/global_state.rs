/*
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
*/

use crate::{
    abi::{AbiInfo, AllAbis},
    call::ExecutionResultInfo,
    debug_info::TraceStepInfo,
    messages::{MessageStorage, MsgInfo},
    util::get_now,
};
use ever_block::{Cell, HashmapE, HashmapType, MsgAddressInt, Serializable, StateInit};
use std::collections::HashMap;
use std::sync::{Arc, LazyLock, Mutex};

////////////////////////////////////////////////////////////////////////////////////////////

#[derive(Default)]
pub struct GlobalState {
    contracts: HashMap<MsgAddressInt, ContractInfo>,
    pub dummy_balances: HashMap<MsgAddressInt, u64>,
    pub all_abis: AllAbis,
    pub messages: MessageStorage,
    pub trace: bool,
    pub trace_on: bool,
    pub last_trace: Option<Vec<TraceStepInfo>>,
    pub last_error_msg: Option<String>,
    pub config_params: HashMap<u32, Cell>,
    pub capabilities: u64,
    now: Option<u64>,
    now2: u64,
    pub lt: u64,
    pub runs: Vec<ExecutionResultInfo>,
}

pub static GLOBAL_STATE: LazyLock<Mutex<GlobalState>> = LazyLock::new(Default::default);

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
        if let Some(name) = self.name.strip_suffix("tvc") {
            format!("{}{}", name, "debug.json")
        } else if let Some(name) = self.name.strip_suffix("abi.json") {
            format!("{}{}", name, "debug.json")
        } else {
            format!("{}.debug.json", self.name)
        }
    }
    pub fn balance(&self) -> u64 {
        self.balance
    }
    pub fn set_balance(&mut self, balance: u64) {
        self.balance = balance;
    }
    pub fn change_balance(&mut self, sign: i64, diff: u64) {
        self.balance = if sign < 0 {
            self.balance - diff
        } else {
            self.balance + diff
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

    pub fn make_time_header(&mut self) -> Option<String> {
        if self.now.is_none() {
            // Add sleep to avoid Replay Protection Error issue
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

    pub fn log_str(&mut self, text: String) {
        let msg_info = MsgInfo::with_log_str(text, self.get_now());
        self.messages.add(msg_info);
    }

}

pub fn make_config_params(gs: &GlobalState) -> Option<Cell> {
    let mut map = HashmapE::with_hashmap(32, None);
    for (key, value) in gs.config_params.clone() {
        let key = key.write_to_bitstring().unwrap();
        map.setref(key, &value).unwrap();
    }
    map.data().map(|v| v.clone())
}

fn messages_to_out_actions(msgs: Vec<Arc<MsgInfo>>) -> Vec<String> {
    msgs.iter().map(|msg| msg.json_str()).collect()
}

