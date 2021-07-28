/*
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
*/

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
    MsgInfo, 
};

use crate::util::{
    bigint_to_u64, get_msg_value, substitute_address,
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
    balance: u64,
    code: Option<Cell>,
    reserved_balance: u64,
    destroy: bool,
    msg_value: u64,
    verbose: bool,
}

pub fn process_actions(
    gs: &mut GlobalState,
    mut contract_info: ContractInfo,
    result: &ExecutionResult,
    method: Option<String>,
    msg_value: Option<u64>,
) -> Result<Vec<MsgInfo>, String> {

    // let mut msg_value = msg_value.unwrap_or_default();

    let address: &MsgAddressInt = contract_info.address();

    let abi_info = contract_info.abi_info();
    // let mut balance = contract_info.balance();

    let mut msgs = vec![];
    let mut state = ActionsProcessor::default();
    state.verbose = gs.trace;
    state.balance = contract_info.balance();
    state.msg_value = msg_value.unwrap_or_default();

    let info_ex = &result.info_ex;

    for act in &info_ex.out_actions {
        if let Some(msg_info) = process_action(
                 gs, act, &address, &mut state, &method,
                &abi_info, 
        )? {
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

        contract_info.set_balance(state.balance);
        contract_info.set_state_init(state_init);
        gs.set_contract(address, contract_info);
    }

    Ok(msgs)
}

impl ActionsProcessor {
    
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
            self.decrease_balance(self.msg_value)?;
            additional_value = self.msg_value;
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
}

fn process_action(
    gs: &GlobalState,
    action: &OutAction,
    address: &MsgAddressInt,
    state: &mut ActionsProcessor,
    method: &Option<String>,
    abi_info: &AbiInfo,
) -> Result<Option<MsgInfo>, String> {
    // TODO!: refactor this function! Too many parameters
    // TODO: remove .clone()
    match action.clone() {
        OutAction::SendMsg{ mode, out_msg } => {
            if gs.trace {
                println!("Action(SendMsg):");
            }

            let additional_value = state.process_send_msg(mode, &out_msg)?;
            let out_msg = substitute_address(out_msg, &address);

            // TODO: is this code needed here? Should it be moved?
            let j = decode_message(&gs, abi_info, method.clone(), &out_msg, additional_value);
            let msg_info2 = MsgInfo::create(out_msg, j);

            return Ok(Some(msg_info2));
        },
        OutAction::SetCode { new_code } => {
            if gs.trace {
                println!("Action(SetCode)");
            }
            state.code = Some(new_code);
        },
        OutAction::ReserveCurrency { mode, value } => {
            if gs.trace {
                println!("Action(ReserveCurrency)");
            }
            // TODO: support other modes when needed. Add more tests. Refactor balance logic
            if mode == 0 {
                // TODO: support other currencies
                state.reserved_balance = value.grams.0 as u64;
                if gs.trace {
                    println!("reserving balance {}", state.reserved_balance);
                }
            } else if mode == 4 {
                let orig_balance = gs.get_contract(&address).unwrap().balance();
                state.reserved_balance = orig_balance + bigint_to_u64(&value.grams.value());
            } else {
                println!("OutAction::ReserveCurrency - Unsupported mode {}", mode);
            }
        },
        OutAction::ChangeLibrary { .. } => {
            println!("Action(ChangeLibrary)");
        },
        _ => println!("Action(Unknown)"),
    };
    Ok(None)
}

