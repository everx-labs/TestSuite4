/*
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
*/

use std::cmp::min;

use ton_types::{
    Cell,
};

use ton_block::{
    Message as TonBlockMessage,
    MsgAddressInt,
    OutAction, 
};

use crate::global_state::{
    GlobalState, ContractInfo,
};

use crate::messages::{
    MsgInfo, MsgInfoJsonDebot,
    AddressWrapper,
};

use crate::util::{
    bigint_to_u64, get_msg_value, substitute_address, format3,
};

use crate::call_contract::{
    ExecutionResult,
};

use crate::abi::{
    AbiInfo
};

use crate::exec::{
    decode_message,
};

#[derive(Default)]
struct ActionsProcessor {
    verbose:            bool,
    msg_value:          u64,
    gas_fee:            Option<u64>,
    balance:            u64,
    original_balance:   u64,

    code:               Option<Cell>,
    reserved_balance:   u64,
    destroy:            bool,
}

impl ActionsProcessor {
    
    fn create(gs: &GlobalState, orig_balance: u64, balance: u64, msg_value: u64, gas_fee: Option<u64>) -> ActionsProcessor {
        let mut st = ActionsProcessor::default();
        st.verbose   = gs.is_trace(3);
        st.balance   = balance;
        st.original_balance = orig_balance;
        st.msg_value = msg_value;
        st.gas_fee   = gas_fee;
        st
    }

    fn decrease_balance(&mut self, value: u64) -> Result<(), String> {
        let error_str = "\n!!!!!!!!!!!! Message makes balance negative !!!!!!!!!!!!!\nBalance:   ".to_string();
        // TODO!: refactor, handle error
        if self.balance < value + self.reserved_balance {
            if self.verbose {
                println!("{}{b:>w1$}\nMsg value: {v:>w2$}, reserved = {r}\n", 
                    error_str, b = self.balance, w1 = 19, v = value, w2 = 19, r = self.reserved_balance);
            }
            return Err("not enough funds".to_string());
        }
        self.balance -= value;
        Ok(())
    }
    
    fn process_send_msg(&mut self, mode: u8, out_msg: &TonBlockMessage) -> Result<u64, String> {
        // TODO: why not to pass the value instead of `out_msg`?
        if let Some(value) = get_msg_value(&out_msg) {
            self.decrease_balance(value)?;
        }

        let mut additional_value = 0;
        if mode == 64 {
            // send money back
            let fee = self.gas_fee.unwrap_or_default();
            self.decrease_balance(self.msg_value - fee)?;
            additional_value = self.msg_value - fee;
            self.msg_value = 0;
        }

        if (mode & 128) != 0 {
            // send all money
            additional_value = self.balance - self.reserved_balance;
            self.balance = self.reserved_balance;
            self.reserved_balance = 0;
        }

        if (mode & 32) != 0 {
            // self-destroy
            self.destroy = true;
        }
        Ok(additional_value)
    }

    fn reserve(&mut self, mode: u8, value: u64) {

        if self.verbose {
            println!("Action(ReserveCurrency) - mode = {}, value = {}", mode, format3(value));
        }
        if mode == 0 {
            self.reserved_balance = value;
        } else if mode == 2 {
            self.reserved_balance = min(value, self.balance);
        } else if mode == 4 {
            // println!("orig_balance: {} vs {}", format3(orig_balance), format3(self.original_balance));
            self.reserved_balance = self.original_balance + value;
        } else {
            println!("OutAction::ReserveCurrency - Unsupported mode {}", mode);
        }
        if self.verbose {
            println!("reserving balance {}", format3(self.reserved_balance));
        }
    }
}

pub fn process_actions(
    gs: &mut GlobalState,
    mut contract_info: ContractInfo,
    result: &ExecutionResult,
    method: Option<String>,
    msg_value: Option<u64>,
    is_debot_call: bool,
    gas_fee: Option<u64>,
) -> Result<Vec<MsgInfo>, String> {

    let address: &MsgAddressInt = contract_info.address();

    let abi_info = contract_info.abi_info();

    let orig_balance = gs.get_contract(&address).unwrap().balance();


    let mut state = ActionsProcessor::create(
        &gs, orig_balance, contract_info.balance(), msg_value.unwrap_or_default(), gas_fee);

    let info_ex = &result.info_ex;
    let parent_msg_id = result.info.inbound_msg_id;

    let mut msgs = vec![];

    for act in &info_ex.out_actions {
        if let Some(mut msg_info) = process_action(
                 gs, act, &address, &mut state, &method,
                &abi_info, is_debot_call,
        )? {
            if parent_msg_id.is_some() {
                msg_info.set_parent_id(parent_msg_id.unwrap());
            }
            msgs.push(msg_info);
        }
    }

    let address = address.clone();
    
    if state.destroy {
        gs.remove_contract(&address);
    } else {

        let mut state_init = info_ex.state_init.clone();

        if let Some(c) = state.code {
            state_init.set_code(c);
        }
        contract_info.set_state_init(state_init);

        contract_info.set_balance(state.balance);
        gs.set_contract(address, contract_info);

    }

    Ok(msgs)
}

fn process_action(
    gs: &GlobalState,
    action: &OutAction,
    address: &MsgAddressInt,
    state: &mut ActionsProcessor,
    method: &Option<String>,
    abi_info: &AbiInfo,
    is_debot_call: bool,
) -> Result<Option<MsgInfo>, String> {
    // TODO: remove .clone()
    match action.clone() {
        OutAction::SendMsg{ mode, out_msg } => {
            if gs.is_trace(3) {
                println!("Action(SendMsg):");
            }

            let additional_value = state.process_send_msg(mode, &out_msg)?;
            // println!("{:?}", out_msg);
            let out_msg = substitute_address(out_msg, &address);

            let is_debot_call2 = out_msg.src().is_none();

            // TODO: is this code needed here? Should it be moved?
            let j = decode_message(&gs, abi_info, method.clone(), &out_msg, additional_value, is_debot_call);
            let mut msg_info2 = MsgInfo::create(out_msg, j);
            
            if is_debot_call2 {
                msg_info2.json.debot_info = Some(MsgInfoJsonDebot{debot_addr: AddressWrapper::with_int(address.clone())});
            }

            // println!("!!!!! msg_info2.json.debot_info = {:?}", msg_info2.json.debot_info);

            return Ok(Some(msg_info2));
        },
        OutAction::SetCode { new_code } => {
            if gs.is_trace(3) {
                println!("Action(SetCode)");
            }
            state.code = Some(new_code);
        },
        OutAction::ReserveCurrency { mode, value } => {
            let value = bigint_to_u64(&value.grams.value());
            state.reserve(mode, value);
        },
        OutAction::ChangeLibrary { .. } => {
            println!("Action(ChangeLibrary)");
        },
        _ => println!("Action(Unknown)"),
    };
    Ok(None)
}

