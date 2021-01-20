/*
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
*/

use std::sync::Arc;

use serde::{Serialize};

use ton_block::{
    CurrencyCollection, Deserializable,
    Message as TonBlockMessage,
    MsgAddressInt,
    OutAction, OutActions,
    Serializable, StateInit,
};

use ton_types::{
    SliceData, BuilderData, Cell,
};

use ton_vm::stack::{
    StackItem, Stack, savelist::SaveList, integer::IntegerData,
};

use ton_vm::error::tvm_exception;
use ton_vm::SmartContractInfo;

use ton_vm::executor::{
    Engine, EngineTraceInfo, gas::gas_state::Gas
};

use crate::global_state::{
    GlobalState, MessageInfo, ContractInfo,
};

use crate::util::{
    bigint_to_u64, get_msg_value, substitute_address,
};

use crate::debug_info::{
    load_debug_info, ContractDebugInfo
};

use crate::{
    make_message_json,
};

////////////////////////////////////////////////////////////////////////////////////////////

#[derive(Clone, Debug)]
pub struct ExecutionResult {
    pub info: ExecutionResultInfo,
    pub info_ex: ExecutionResultEx,
}

#[derive(Clone, Debug, Serialize)]
pub struct ExecutionResultInfo {
    pub run_id: Option<u32>,
    pub address: String, // TODO: Option<MsgAddressInt>,
    pub inbound_msg_id: Option<u32>,
    pub exit_code: i32,
    pub gas: i64,
}

#[derive(Clone, Debug)]
pub struct ExecutionResultEx {
    pub state_init: StateInit,
    pub out_actions: OutActions,
}

pub fn call_contract_ex(
    contract_info: &ContractInfo,
    msg: Option<TonBlockMessage>,
    msg_value: Option<u64>,
    debug: bool,
    config_params: Option<Cell>,
    now: u64,
    ticktock: Option<i8>,
) -> ExecutionResult {
    let addr = contract_info.address();
    let state_init = contract_info.state_init();
    let smc_balance = contract_info.balance();
    let debug_info_filename = contract_info.debug_info_filename();

    let (func_selector, value) = match msg_value {
        Some(value) => (0, value),
        None => (if ticktock.is_some() { -2 } else { -1 }, 0)
    };

    let (code, data) = load_code_and_data(&state_init);

    let registers = initialize_registers(
        data,
        addr,
        now,
        (smc_balance, CurrencyCollection::with_grams(smc_balance)),
        config_params,
    );

    let mut stack = Stack::new();
    if func_selector > -2 {
        let msg = msg.unwrap();
        let msg_cell = StackItem::Cell(msg.clone().write_to_new_cell().unwrap().into());

        let body: SliceData = match msg.body() {
            Some(b) => b.into(),
            None => BuilderData::new().into(),
        };

        stack
            .push(int!(smc_balance))
            .push(int!(value))              //msg balance
            .push(msg_cell)                 //msg
            .push(StackItem::Slice(body))   //msg.body
            .push(int!(func_selector));     //selector
    } else {
        stack
            .push(int!(smc_balance))
            // .push(StackItem::Integer(Arc::new(addr_int))) //contract address
            .push(int!(0)) // TODO: contract address
            .push(int!(ticktock.unwrap())) //tick or tock
            .push(int!(func_selector));
    }

    let mut engine = Engine::new().setup(code, Some(registers), Some(stack), Some(Gas::test()));
    // engine.set_trace(Engine::TRACE_ALL);
    if debug {
        let debug_info = load_debug_info(&state_init, debug_info_filename);
        engine.set_trace_callback(move |engine, info| { trace_callback(engine, info, true, &debug_info); })
    }
    let exit_code = match engine.execute() {
        Err(exc) => match tvm_exception(exc) {
            Ok(exc) => {
                println!("Unhandled exception: {}", exc);
                exc.exception_or_custom_code()
            }
            _ => -1
        }
        Ok(code) => code as i32
    };
    let gas_usage = engine.get_gas().get_gas_used();
    if debug {
        println!("TVM terminated with exit code {}", exit_code);
        println!("Gas used: {}", gas_usage);
        println!("");
        println!("{}", engine.dump_stack("Post-execution stack state", false));
        println!("{}", engine.dump_ctrls(false));
    }

    let mut state_init = state_init.clone();
    // TODO: Add test with COMMIT and failure...
    if exit_code == 0 || exit_code == 1 {
        state_init.data = match engine.get_committed_state().get_root() {
            StackItem::Cell(root_cell) => Some(root_cell),
            _ => panic!("cannot get root data: c4 register is not a cell."),
        };
    }

    let actions = if let StackItem::Cell(cell) = engine.get_actions() {
        OutActions::construct_from(&mut cell.into()).unwrap()
    } else {
        OutActions::default()
    };

    let info_ex = ExecutionResultEx {
        state_init:     state_init,
        out_actions:    actions,
    };

    let info = ExecutionResultInfo {
        run_id:         None,
        address:        format!("{}", addr),
        inbound_msg_id: None,
        exit_code:      exit_code,
        gas:            gas_usage,
    };

    ExecutionResult {
        info:    info,
        info_ex: info_ex,
    }
}

fn load_code_and_data(state_init: &StateInit) -> (SliceData, SliceData) {
    let code: SliceData = state_init.code
            .clone()
            .unwrap_or(BuilderData::new().into())
            .into();
    let data = state_init.data
            .clone()
            .unwrap_or(BuilderData::new().into())
            .into();
    (code, data)
}

fn initialize_registers(
    data: SliceData,
    myself: &MsgAddressInt,
    now: u64,
    balance: (u64, CurrencyCollection),
    config_params: Option<Cell>
) -> SaveList {
    let mut ctrls = SaveList::new();
    let mut info = SmartContractInfo::with_myself(myself.write_to_new_cell().unwrap().into());
    *info.balance_remaining_grams_mut() = balance.0 as u128;
    *info.balance_remaining_other_mut() = balance.1.other_as_hashmap().clone();
    *info.unix_time_mut() = now as u32;
    if let Some(config_params) = config_params {
        info.set_config_params(config_params)
    }
    ctrls.put(4, &mut StackItem::Cell(data.into_cell())).unwrap();
    ctrls.put(7, &mut info.into_temp_data()).unwrap();
    ctrls
}

fn trace_callback(_engine: &Engine, info: &EngineTraceInfo, extended: bool, debug_info: &Option<ContractDebugInfo>) {
    println!("{}: {}",
        info.step,
        info.cmd_str
    );
    if extended {
        println!("{} {}",
            info.cmd_code.remaining_bits(),
            info.cmd_code.to_hex_string()
        );
    }
    println!("\nGas: {} ({})",
        info.gas_used,
        info.gas_cmd
    );

    if let Some(debug_info) = debug_info {
        // TODO: move
        let fname = match debug_info.hash2function.get(&info.cmd_code.cell().repr_hash()) {
            Some(fname) => fname,
            None => "n/a"
        };
        println!("function: {}", fname);
    }

    println!("\n--- Stack trace ------------------------");
    for item in info.stack.iter() {
        println!("{}", item);
    }
    println!("----------------------------------------\n");
}

pub fn process_actions(
    gs: &mut GlobalState,
    mut contract_info: ContractInfo,
    result: &ExecutionResult,
    method: Option<String>,
    mut message_value: u64,
) -> Vec<MessageInfo> {

    let address = contract_info.address().clone();  // TODO: get rid of clone

    let mut balance = contract_info.balance();
    let abi_str = contract_info.abi_str();

    let mut msgs = vec![];
    let mut code = None;
    let mut reserved_balance = 0;

    let info_ex = &result.info_ex;

    for act in &info_ex.out_actions {
        // TODO: refactor it - remove mut params...
        if let Some(msg_info2) = process_action(
                 gs, act, &address, &mut balance, method.clone(),
            &abi_str.to_owned(), &mut message_value,
            &mut reserved_balance, &mut code,
        ) {
            msgs.push(msg_info2);
        }
    }

    let mut state_init = info_ex.state_init.clone();
    if let Some(c) = code {
        state_init.set_code(c);
    }
    contract_info.set_balance(balance);
    contract_info.set_state_init(state_init);
    gs.set_contract(address.clone(), contract_info);

    msgs
}

fn process_action(
    gs: &GlobalState,
    action: &OutAction,
    address: &MsgAddressInt,
    balance: &mut u64,
    method: Option<String>,
    abi_str: &String,
    message_value: &mut u64,
    reserved_balance: &mut u64,
    code: &mut Option<Cell>,
) -> Option<MessageInfo> {
    // TODO: remove .clone()
    match action.clone() {
        OutAction::SendMsg{ mode, out_msg } => {
            if gs.trace {
                println!("Action(SendMsg):");
            }
            let error_str = "\n!!!!!!!!!!!! Message makes balance negative !!!!!!!!!!!!!\nBalance:   ".to_string();
            if let Some(value) = get_msg_value(&out_msg) {
                if *balance < value {
                    println!("{}{b:>w1$}\nMsg value: {v:>w2$}\n", error_str, b = *balance, w1 = 19, v = value, w2 = 19);
                    assert!(*balance >= value);
                }
                *balance -= value;
            }

            let mut additional_value = 0;
            if mode == 64 {
                if *balance < *message_value {
                    println!("{}{b:>w1$}\nMsg value: {v:>w2$}\n", error_str, b = *balance, w1 = 19, v = *message_value, w2 = 19);
                    assert!(*balance < *message_value);
                }
                *balance -= *message_value;
                additional_value = *message_value;
                *message_value = 0;
            }

            if mode == 128 {
                additional_value = *balance - *reserved_balance;
                *balance = *reserved_balance;
                *reserved_balance = 0;
            }

            let out_msg = substitute_address(out_msg, &address);

            let j = make_message_json(&gs, &abi_str, method.clone(), &out_msg, additional_value);
            let msg_info2 = MessageInfo::create(out_msg, j);

            return Some(msg_info2);
        },
        OutAction::SetCode { new_code } => {
            if gs.trace {
                println!("Action(SetCode)");
            }
            *code = Some(new_code);
        },
        OutAction::ReserveCurrency { mode, value } => {
            if gs.trace {
                println!("Action(ReserveCurrency)");
            }
            // TODO: support other modes when needed. Add more tests. Refactor balance logic
            if mode == 0 {
                // TODO: support other currencies
                *reserved_balance = value.grams.0 as u64;
                if gs.trace {
                    println!("reserving balance {}", *reserved_balance);
                }
            } else if mode == 4 {
                let orig_balance = gs.get_contract(&address).balance();
                *reserved_balance = orig_balance + bigint_to_u64(&value.grams.value());
            } else {
                println!("OutAction::ReserveCurrency - Unsupported mode {}", mode);
            }
        },
        OutAction::ChangeLibrary { .. } => {
            println!("Action(ChangeLibrary)");
        },
        _ => println!("Action(Unknown)"),
    };
    None
}

