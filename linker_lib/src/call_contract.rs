/*
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
*/

use std::sync::{Arc, Mutex};

use serde::{
    Serialize,
};

use ton_block::{
    CurrencyCollection, Deserializable,
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
    Engine, EngineTraceInfo, EngineTraceInfoType, gas::gas_state::Gas
};

use crate::global_state::{
    GlobalState, ContractInfo,
};

use crate::util::{
    bigint_to_u64, get_msg_value, substitute_address,
};

use crate::debug_info::{
    load_debug_info, ContractDebugInfo, TraceStepInfo,
    get_function_name,
};

use crate::abi::{
    AbiInfo
};

use crate::messages::{
    AddressWrapper,
    MsgInfo, MessageInfo2,
};

use crate::exec::{
    decode_message,
};

////////////////////////////////////////////////////////////////////////////////////////////

#[derive(Clone, Debug)]
pub struct ExecutionResult {
    pub info: ExecutionResultInfo,
    pub info_ex: ExecutionResultEx,
    pub info_msg: Option<String>,
    pub trace: Option<Vec<TraceStepInfo>>,
}

// TODO: unify these structures. Or give better names

#[derive(Clone, Debug, Serialize)]
pub struct ExecutionResultInfo {
    pub run_id: Option<u32>,
    pub address: AddressWrapper,
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
    msg_info: &MessageInfo2,
    debug: bool,
    trace2: bool,
    config_params: Option<Cell>,
    now: u64,
    lt: u64,
) -> ExecutionResult {

    if debug {
        println!("call_contract_ex");
    }

    // TODO: Too long function

    let msg_value = msg_info.value();
    let ticktock  = &msg_info.ticktock;

    let addr                = contract_info.address();
    let state_init          = contract_info.state_init();
    let contract_balance    = contract_info.balance();
    let debug_info_filename = contract_info.debug_info_filename();

    //  0   - internal msg
    // -1   - external msg
    // -2   - tick-tock
    // -3   - Split Prepare Transaction
    // -4   - Merge Transaction

    let func_selector =
        if ticktock.is_some() { -2 } else {
            if msg_value.is_some() { 0 } else { -1 }
        };

    let value = msg_value.unwrap_or(0);

    let (code, data) = load_code_and_data(&state_init);

    let registers = initialize_registers(
        data,
        addr,
        now, lt,
        (contract_balance, CurrencyCollection::with_grams(contract_balance)),
        config_params,
    );

    let mut stack = Stack::new();
    if func_selector > -2 {     // internal or external
        let msg = msg_info.ton_msg().unwrap();
        let msg_cell = StackItem::Cell(msg.clone().write_to_new_cell().unwrap().into());

        let body: SliceData = match msg.body() {
            Some(b) => b.into(),
            None => BuilderData::new().into(),
        };

        stack
            .push(int!(contract_balance))
            .push(int!(value))              //msg balance
            .push(msg_cell)                 //msg
            .push(StackItem::Slice(body))   //msg.body
            .push(int!(func_selector));     //selector
    } else {
        stack
            .push(int!(contract_balance))
            // .push(StackItem::Integer(Arc::new(addr_int))) //contract address
            .push(int!(0)) // TODO: contract address
            .push(int!(ticktock.unwrap())) //tick or tock
            .push(int!(func_selector));
    }

    let gas = if msg_info.is_external_call() {
        Gas::test_with_credit(10_000)
    } else {
        Gas::test()
    };

    let mut engine = Engine::new().setup(code, Some(registers), Some(stack), Some(gas));

    let debug_info = if debug || trace2 {
        load_debug_info(&state_init, debug_info_filename, debug)
    } else {
        None
    };

    let trace = Arc::new(Mutex::new(vec![]));
    let trace1 = trace.clone();

    engine.set_trace_callback(move |engine, info| {
        trace_callback(engine, info, debug, trace2, true, &debug_info, &mut trace.clone().lock().unwrap());
    });

    let exit_code = match engine.execute() {
        Err(exc) => match tvm_exception(exc) {
            Ok(exc) => {
                if debug {
                    println!("Unhandled exception: {}", exc);
                }
                exc.exception_or_custom_code()
            }
            _ => -1
        }
        Ok(code) => code as i32
    };

    let trace: Vec<TraceStepInfo> = trace1.lock().unwrap().clone();

    let gas_usage = engine.get_gas().get_gas_used();

    if debug {
        println!("TVM terminated with exit code {}", exit_code);
        println!("Gas used: {}", gas_usage);
        println!("");
        println!("{}", engine.dump_stack("Post-execution stack state", false));
        println!("{}", engine.dump_ctrls(false));
    }

    let gas_credit = engine.get_gas().get_gas_credit();

    if debug {
        println!("credit = {}", gas_credit);
    }

    let mut state_init = state_init.clone();
    if gas_credit == 0 {
        match engine.get_committed_state().get_root() {
            StackItem::Cell(root_cell) => {
                state_init.data = Some(root_cell);
            },
            StackItem::None => {
                // do nothing
            },
            _ => panic!("cannot get root data: c4 register is not a cell."),
        };
    }

    let info_msg = if is_success_exit_code(exit_code) && gas_credit > 0 {
        Some("no_accept".to_string())
    } else {
        None
    };

    let actions = match engine.get_actions() {
        StackItem::Cell(cell) =>
            OutActions::construct_from(&mut cell.into()).unwrap(),
        _ =>
            OutActions::default(),
    };

    let info_ex = ExecutionResultEx {
        state_init:     state_init,
        out_actions:    actions,
    };

    let info = ExecutionResultInfo {
        run_id:         None,
        address:        AddressWrapper::with_int(addr.clone()),
        inbound_msg_id: None,
        exit_code:      exit_code,
        gas:            gas_usage,
    };

    ExecutionResult {
        info:     info,
        info_ex:  info_ex,
        info_msg: info_msg,
        trace:    Some(trace),
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
    lt: u64,
    balance: (u64, CurrencyCollection),
    config_params: Option<Cell>,
) -> SaveList {
    let mut ctrls = SaveList::new();
    let mut info = SmartContractInfo::with_myself(myself.write_to_new_cell().unwrap().into());
    *info.balance_remaining_grams_mut() = balance.0 as u128;
    *info.balance_remaining_other_mut() = balance.1.other_as_hashmap().clone();
    *info.unix_time_mut() = now as u32;
    if let Some(config_params) = config_params {
        info.set_config_params(config_params)
    }
    *info.block_lt_mut() = lt;
    *info.trans_lt_mut() = lt;
    ctrls.put(4, &mut StackItem::Cell(data.into_cell())).unwrap();
    ctrls.put(7, &mut info.into_temp_data()).unwrap();
    ctrls
}

fn trace_callback(
    _engine: &Engine,
    info: &EngineTraceInfo,
    trace: bool,
    trace2: bool,
    extended: bool,
    debug_info: &Option<ContractDebugInfo>,
    result: &mut Vec<TraceStepInfo>,
) {

    let fname = get_function_name(&debug_info, &info.cmd_code);

    if trace2 {
        let info2 = TraceStepInfo::from(&info, fname.clone());
        result.push(info2);
    }

    if trace {
        println!("{}: {}", info.step, info.cmd_str);

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

        if debug_info.is_some() {
            let fname = fname.unwrap_or("n/a".to_string());
            println!("function: {}", fname);
        }

        println!("\n--- Stack trace ------------------------");
        for item in info.stack.iter() {
            println!("{}", item);
        }
        println!("----------------------------------------\n");
    }

    if info.info_type == EngineTraceInfoType::Dump {
        println!("logstr: {}", info.cmd_str);
    }
}

pub fn process_actions(
    gs: &mut GlobalState,
    mut contract_info: ContractInfo,
    result: &ExecutionResult,
    method: Option<String>,
    msg_value: Option<u64>,
) -> Vec<MsgInfo> {

    let mut msg_value = msg_value.unwrap_or_default();

    let address: &MsgAddressInt = contract_info.address();

    let mut balance = contract_info.balance();
    let abi_info = contract_info.abi_info();

    let mut msgs = vec![];
    let mut code = None;
    let mut reserved_balance = 0;

    let info_ex = &result.info_ex;

    for act in &info_ex.out_actions {
        // TODO!: refactor it - remove mut params...
        if let Some(msg_info) = process_action(
                 gs, act, &address, &mut balance, &method,
            &abi_info, &mut msg_value,
            &mut reserved_balance, &mut code,
        ) {
            msgs.push(msg_info);
        }
    }

    let mut state_init = info_ex.state_init.clone();
    if let Some(c) = code {
        state_init.set_code(c);
    }

    let address = address.clone();

    contract_info.set_balance(balance);
    contract_info.set_state_init(state_init);
    gs.set_contract(address, contract_info);

    msgs
}

// TODO!!: move to actions.rs
fn process_action(
    gs: &GlobalState,
    action: &OutAction,
    address: &MsgAddressInt,
    balance: &mut u64,
    method: &Option<String>,
    abi_info: &AbiInfo,
    msg_value: &mut u64,
    reserved_balance: &mut u64,
    code: &mut Option<Cell>,
) -> Option<MsgInfo> {
    // TODO!: refactor this function! Too many parameters
    // TODO: remove .clone()
    match action.clone() {
        OutAction::SendMsg{ mode, out_msg } => {
            if gs.trace {
                println!("Action(SendMsg):");
            }
            let error_str = "\n!!!!!!!!!!!! Message makes balance negative !!!!!!!!!!!!!\nBalance:   ".to_string();
            if let Some(value) = get_msg_value(&out_msg) {
                // TODO!: refactor, handle error
                if *balance < value {
                    // TODO: add a test
                    println!("{}{b:>w1$}\nMsg value: {v:>w2$}\n", error_str, b = *balance, w1 = 19, v = value, w2 = 19);
                    assert!(*balance >= value);
                }
                *balance -= value;
            }

            let mut additional_value = 0;
            if mode == 64 {
                // TODO!: refactor, handle error
                if *balance < *msg_value {
                    // TODO: add a test
                    println!("{}{b:>w1$}\nMsg value: {v:>w2$}\n", error_str, b = *balance, w1 = 19, v = *msg_value, w2 = 19);
                    assert!(*balance < *msg_value);
                }
                *balance -= *msg_value;
                additional_value = *msg_value;
                *msg_value = 0;
            }

            if mode == 128 {
                additional_value = *balance - *reserved_balance;
                *balance = *reserved_balance;
                *reserved_balance = 0;
            }

            let out_msg = substitute_address(out_msg, &address);

            // TODO: is this code needed here? Should it be moved?
            let j = decode_message(&gs, abi_info, method.clone(), &out_msg, additional_value);
            let msg_info2 = MsgInfo::create(out_msg, j);

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
                let orig_balance = gs.get_contract(&address).unwrap().balance();
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

pub fn is_success_exit_code(exit_code: i32) -> bool {
    exit_code == 0 || exit_code == 1
}

