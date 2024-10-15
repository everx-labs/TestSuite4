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

use ever_block::{
    CurrencyCollection, Deserializable,
    MsgAddressInt,
    OutActions,
    Serializable, StateInit,
};

use ever_block::{
    SliceData, Cell,
};

use ever_vm::stack::{
    StackItem, Stack, savelist::SaveList, integer::IntegerData,
};

use ever_vm::error::tvm_exception;
use ever_vm::{int, SmartContractInfo};

use ever_vm::executor::{
    Engine, EngineTraceInfo, EngineTraceInfoType, gas::gas_state::Gas
};

use crate::global_state::{
    make_config_params, ContractInfo, GlobalState
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
    gs:             &GlobalState,
    contract_info:  &ContractInfo,
    msg_info:       &MessageInfo2,
) -> ExecutionResult {

    if gs.trace {
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
        gs,
        data,
        addr,
        (contract_balance, CurrencyCollection::with_grams(contract_balance)),
    );

    let mut stack = Stack::new();
    if func_selector > -2 {     // internal or external
        let msg = msg_info.ton_msg().unwrap();
        let msg_cell = StackItem::Cell(msg.serialize().unwrap().into());

        let body = msg.body().unwrap_or_default();

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

    let code = SliceData::load_cell(code).unwrap_or_default();
    let mut engine = Engine::with_capabilities(gs.capabilities).setup(code, Some(registers), Some(stack), Some(gas));

    let debug_info = if gs.trace || gs.trace_on {
        load_debug_info(debug_info_filename, gs.trace)
    } else {
        None
    };

    let trace = Arc::new(Mutex::new(vec![]));
    let trace1 = trace.clone();

    let debug = gs.trace;
    let trace_on = gs.trace_on;
    engine.set_trace_callback(move |engine, info| {
        trace_callback(engine, info, debug, trace_on, true, debug_info.as_ref(), &mut trace.clone().lock().unwrap());
    });

    let mut error_msg = None;

    let exit_code = match engine.execute() {
        Err(exc) => match tvm_exception(exc) {
            Ok(exc) => {
                error_msg = Some(format!("Unhandled exception: {}", exc));
                if gs.trace {
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

    if gs.trace {
        println!("TVM terminated with exit code {}", exit_code);
        println!("Gas used: {}", gas_usage);
        println!("");
        println!("{}", engine.dump_stack("Post-execution stack state", false));
        println!("{}", engine.dump_ctrls(false));
    }

    let gas_credit = engine.get_gas().get_gas_credit();

    if gs.trace {
        println!("credit = {}", gas_credit);
    }

    let mut state_init = state_init.clone();
    if gas_credit == 0 {
        match engine.get_committed_state().get_root() {
            StackItem::Cell(root_cell) => {
                state_init.data = Some(root_cell.clone());
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
        StackItem::Cell(ref cell) => OutActions::construct_from_cell(cell.clone()).unwrap(),
        _ => OutActions::default(),
    };

    let info_ex = ExecutionResultEx {
        state_init:     state_init,
        out_actions:    actions,
    };

    let info = ExecutionResultInfo {
        run_id:         None,
        address:        AddressWrapper::with_int(addr.clone()),
        inbound_msg_id: None,
        exit_code,
        error_msg,
        gas:            gas_usage,
    };

    ExecutionResult {
        info,
        info_ex,
        info_msg,
        trace: Some(trace),
    }
}

fn load_code_and_data(state_init: &StateInit) -> (Cell, Cell) {
    let code = state_init.code.clone().unwrap_or_default();
    let data = state_init.data.clone().unwrap_or_default();
    (code, data)
}

fn initialize_registers(
    gs: &GlobalState,
    data: Cell,
    myself: &MsgAddressInt,
    balance: (u64, CurrencyCollection),
) -> SaveList {
    let mut ctrls = SaveList::new();
    let mut info = SmartContractInfo::with_myself(myself.write_to_bitstring().unwrap());
    info.balance_remaining_grams = balance.0 as u128;
    info.balance_remaining_other = balance.1.other_as_hashmap();
    info.unix_time = gs.get_now() as u32;
    info.config_params = make_config_params(gs);
    info.block_lt = gs.lt;
    info.trans_lt = gs.lt;
    info.capabilities = gs.capabilities;
    ctrls.put(4, &mut StackItem::Cell(data)).unwrap();
    ctrls.put(7, &mut info.into_temp_data_item()).unwrap();
    ctrls
}

fn trace_callback(
    _engine: &Engine,
    info: &EngineTraceInfo,
    trace: bool,
    trace2: bool,
    extended: bool,
    debug_info: Option<&ContractDebugInfo>,
    result: &mut Vec<TraceStepInfo>,
) {

    let fname = get_function_name(debug_info, info);

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

