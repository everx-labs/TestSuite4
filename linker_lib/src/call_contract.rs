/*
    This file is part of Ever OS.

    Ever OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2023 (c) EverX
*/

use std::sync::{Arc, Mutex};
use std::cmp::min;
use serde::Serialize;

use ton_block::{
    ConfigParam8, CurrencyCollection, Deserializable, GlobalCapabilities, MsgAddressInt,
    OutActions, Serializable, StateInit,
};
use ton_types::{Cell, HashmapE, SliceData};
use ton_vm::{
    boolean, int,
    error::tvm_exception,
    executor::{gas::gas_state::Gas, Engine, EngineTraceInfo, EngineTraceInfoType},
    stack::{integer::IntegerData, savelist::SaveList, Stack, StackItem},
    SmartContractInfo,
};

use crate::global_state::ContractInfo;
use crate::debug_info::{get_function_name, load_debug_info, ContractDebugInfo, TraceStepInfo};
use crate::messages::{AddressWrapper, CallContractMsgInfo};
use crate::util::format3;

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
    pub accept_in_getter:   bool,
    pub stack:          Vec<String>,
}

#[derive(Clone, Debug)]
pub struct ExecutionResultEx {
    pub state_init:     StateInit,
    pub out_actions:    OutActions,
}

pub fn call_contract_ex(
    _address:        &MsgAddressInt,
    contract_info:  &ContractInfo,
    msg_info:       &CallContractMsgInfo,
    global_gas_limit:   u64,
    trace_level:    u64,
    debug:          bool,
    trace_tvm_1:    bool,
    trace_tvm_2:    bool,
    config_params:  Option<Cell>,
    now:            u64,
    lt:             u64,
) -> ExecutionResult {

    // TODO: Too long function

    let msg_value = msg_info.value();

    let address             = contract_info.address();
    let state_init          = contract_info.state_init();
    let contract_balance    = contract_info.balance();
    let debug_info_filename = contract_info.debug_info_filename();

    if trace_level >= 5 {
        println!("call_contract_ex: balance = {}", format3(contract_balance));
    }

    //  0   - internal msg
    // -1   - external msg
    // -2   - tick-tock
    // -3   - Split Prepare Transaction
    // -4   - Merge Transaction

    let value = msg_value.unwrap_or(0);

    let code = state_init.code.clone().unwrap_or_default();
    let data = state_init.data.clone().unwrap_or_default();
    let mut capabilities = GlobalCapabilities::CapInitCodeHash as u64 | GlobalCapabilities::CapMycode as u64;
    if let Some(root) = config_params.clone() {
        let config_params = HashmapE::with_hashmap(32, Some(root));
        let key = SliceData::load_builder(8u32.write_to_new_cell().unwrap()).unwrap();
        if let Ok(Some(value)) = config_params.get(key) {
            if let Some(cell) = value.reference_opt(0) {
                if let Ok(param) = ConfigParam8::construct_from_cell(cell) {
                    capabilities |= param.global_version.capabilities;
                }
            }
        }
    }

    let registers = initialize_registers(
        code.clone(),
        data,
        SliceData::load_cell(address.serialize().unwrap()).unwrap(),
        now, lt,
        CurrencyCollection::with_grams(contract_balance),
        capabilities,
        config_params,
    );

    let mut stack = Stack::new();
    if let Some(ticktock) = &msg_info.ticktock {
        stack
            .push(int!(contract_balance))
            // .push(StackItem::Integer(Arc::new(addr_int))) //contract address
            .push(int!(0_i32)) // TODO: contract address
            .push(int!(*ticktock)) //tick or tock
            .push(int!(-2));
    } else if let Some(body) = msg_info.ton_msg_body() {
        let msg_cell = StackItem::cell(Cell::default());
        stack
            .push(int!(contract_balance))
            .push(int!(0))              //msg balance
            .push(msg_cell)                 //msg
            .push(StackItem::Slice(body.clone()))   //msg.body
            .push(boolean!(true));                     //selector
    } else if let Some(msg) = msg_info.ton_msg() {
        let msg_cell = StackItem::Cell(msg.serialize().unwrap());

        let body = msg.body().unwrap_or_default();

        stack
            .push(int!(contract_balance))
            .push(int!(value))              //msg balance
            .push(msg_cell)                 //msg
            .push(StackItem::Slice(body))   //msg.body
            .push(boolean!(msg_value.is_none()));     //selector
    } else if let Some(id) = msg_info.id() {
        stack.push(int!(id));                          //selector
    } else {
        unreachable!()
    }

    let value_gas: i64 = value as i64 / 1000;
    let balance_gas: i64 = contract_balance as i64 / 1000;

    let global_gas_limit: i64 = if global_gas_limit > 0 { global_gas_limit as i64 } else { 1_000_000 };

    let gas = if msg_info.is_external_call() {
        let max_gas = min(global_gas_limit, balance_gas);
        Gas::new(0, 10_000, max_gas, 10)
    } else if msg_info.is_getter_call() {
        Gas::new(0, 1_000_000_000, 1_000_000_000, 10)
    } else if msg_info.is_offchain_ctor_call() || msg_info.is_debot_call() {
        Gas::test()
    } else if msg_info.ticktock.is_some() {
        // TODO: not sure if that is correct
        Gas::test()
    } else {
        let max_gas = min(global_gas_limit, balance_gas);
        // TODO: is first param correct here?
        Gas::new(value_gas, 0, max_gas, 10)
    };

    if trace_level >= 5 {
        println!("call_contract_ex: value = {}, gas_credit = {}, gas_limit = {}, max = {}", 
                format3(value),
                format3(gas.get_gas_credit()),
                format3(gas.get_gas_limit()),
                format3(gas.get_gas_limit_max()),
            );
    }

    let mut engine = Engine::with_capabilities(capabilities)
        .setup(SliceData::load_cell(code).unwrap(), Some(registers), Some(stack), Some(gas));

    let debug_info = if debug || trace_tvm_1 || trace_tvm_2 {
        load_debug_info(debug_info_filename, debug)
    } else {
        None
    };

    let trace = Arc::new(Mutex::new(vec![]));
    let trace1 = trace.clone();

    engine.set_trace_callback(move |engine, info| {
        trace_callback(engine, info, trace_tvm_1, trace_tvm_2, true, debug_info.as_ref(), &mut trace.clone().lock().unwrap());
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
        Ok(code) => code
    };

    let trace: Vec<TraceStepInfo> = trace1.lock().unwrap().clone();

    let gas_usage = engine.get_gas().get_gas_used();

    if trace_level >= 10 || trace_tvm_1 {
        println!("TVM terminated with exit code {}", exit_code);
        println!("Gas used: {}", gas_usage);
        println!();
        if trace_level >= 15 {
            println!("{}", engine.dump_stack("Post-execution stack state", false));
            println!("{}", engine.dump_ctrls(false));
        }
    }

    let gas_credit = engine.get_gas().get_gas_credit();

    if trace_level >= 10 {
        println!("credit = {}", gas_credit);
    }

    let accept_in_getter = msg_info.is_getter_call() && gas_credit == 0;

    let gas_credit = if msg_info.is_getter_call() { 0 } else { gas_credit };

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

    let stack = engine.stack().iter().map(|s| s.to_string()).collect();

    let info_msg = if is_success_exit_code(exit_code) && gas_credit > 0 {
        Some("no_accept".to_string())
    } else {
        None
    };

    let out_actions = match engine.get_committed_state().get_actions() {
        StackItem::Cell(cell) => OutActions::construct_from_cell(cell).unwrap(),
        _ => OutActions::default(),
    };

    let info_ex = ExecutionResultEx {
        state_init,
        out_actions,
    };

    let info = ExecutionResultInfo {
        run_id:         None,
        address:        AddressWrapper::with_int(address.clone()),
        inbound_msg_id: None,
        stack,
        exit_code,
        error_msg,
        gas:            gas_usage,
        accept_in_getter,
    };

    ExecutionResult {
        info,
        info_ex,
        info_msg,
        trace:    Some(trace),
    }
}

fn initialize_registers(
    mycode: Cell,
    data: Cell,
    myself: SliceData,
    now: u64,
    lt: u64,
    balance: CurrencyCollection,
    capabilities: u64,
    config_params: Option<Cell>,
) -> SaveList {
    let mut ctrls = SaveList::new();
    let info = SmartContractInfo {
        unix_time: now as u32,
        block_lt: lt,
        trans_lt: lt,
        config_params,
        capabilities,
        mycode,
        myself,
        balance,
        ..Default::default()
    };
    ctrls.put(4, &mut StackItem::cell(data)).unwrap();
    ctrls.put(7, &mut info.into_temp_data_item()).unwrap();
    ctrls
}

fn trace_callback(
    _engine: &Engine,
    info: &EngineTraceInfo,
    trace_tvm_1: bool,
    trace_tvm_2: bool,
    extended: bool,
    debug_info: Option<&ContractDebugInfo>,
    result: &mut Vec<TraceStepInfo>,
) {

    let fname = get_function_name(debug_info, info);

    if trace_tvm_2 {
        let info2 = TraceStepInfo::from(info, fname.clone());
        result.push(info2);
    }

    if trace_tvm_1 {
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
            let fname = fname.unwrap_or_else(|| "n/a".to_string());
            println!("function: {}", fname);
        }

        println!("\n--- Stack trace ------------------------");
        for item in info.stack.iter() {
            println!("{}", item);
        }
        println!("----------------------------------------\n");
    }

    if info.info_type == EngineTraceInfoType::Dump {
        let s = &info.cmd_str;
        if s.ends_with('\n') {
            print!("logstr: {}", s);
        } else {
            println!("logstr: {}", s);
        }
    }
}

pub fn is_success_exit_code(exit_code: i32) -> bool {
    exit_code == 0 || exit_code == 1
}

