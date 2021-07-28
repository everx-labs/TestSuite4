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
    OutActions,
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
    // GlobalState,
    ContractInfo,
};

use crate::debug_info::{
    load_debug_info, ContractDebugInfo, TraceStepInfo,
    get_function_name,
};

use crate::messages::{
    AddressWrapper,
    MessageInfo2,
};

////////////////////////////////////////////////////////////////////////////////////////////

#[derive(Clone, Debug)]
pub struct ExecutionResult {
    pub info:       ExecutionResultInfo,
    pub info_ex:    ExecutionResultEx,
    pub info_msg:   Option<String>,
    pub trace:      Option<Vec<TraceStepInfo>>,
}

// TODO: unify these structures. Or give better names

#[derive(Clone, Debug, Serialize)]
pub struct ExecutionResultInfo {
    pub run_id:         Option<u32>,
    pub address:        AddressWrapper,
    pub inbound_msg_id: Option<u32>,
    pub exit_code:      i32,
    pub error_msg:      Option<String>,
    pub gas:            i64,
}

#[derive(Clone, Debug)]
pub struct ExecutionResultEx {
    pub state_init:     StateInit,
    pub out_actions:    OutActions,
}

pub fn call_contract_ex(
    contract_info:  &ContractInfo,
    msg_info:       &MessageInfo2,
    debug:          bool,
    trace2:         bool,
    config_params:  Option<Cell>,
    now:            u64,
    lt:             u64,
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
        let msg_cell = StackItem::Cell(msg.serialize().unwrap().into());

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

    let mut error_msg = None;

    let exit_code = match engine.execute() {
        Err(exc) => match tvm_exception(exc) {
            Ok(exc) => {
                error_msg = Some(format!("Unhandled exception: {}", exc));
                if debug {
                    println!("{}", error_msg.clone().unwrap());
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
        error_msg:      error_msg,
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
    let mut info = SmartContractInfo::with_myself(myself.serialize().unwrap().into());
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

pub fn is_success_exit_code(exit_code: i32) -> bool {
    exit_code == 0 || exit_code == 1
}

