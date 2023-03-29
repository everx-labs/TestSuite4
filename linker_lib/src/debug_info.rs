/*
    This file is part of Ever OS.

    Ever OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2023 (c) EverX
*/

use serde::{Deserialize, Serialize};
use ton_labs_assembler::DbgInfo;
use ton_vm::executor::{
    EngineTraceInfo,
};

pub struct ContractDebugInfo {
    hash2function: DbgInfo,
}

#[derive(Clone, Serialize, Deserialize, Debug)]
pub struct TraceStepInfo {
    pub id: u32,
    pub cmd: String,
    pub gas: i64,
    pub func: Option<String>,
    pub stack: Vec<String>,
}

impl ContractDebugInfo {
    pub fn find_function(&self, info: &EngineTraceInfo) -> Result<String, &'static str> {
        let cell_hash = info.cmd_code.cell().repr_hash();
        let offset = info.cmd_code.pos();
        match self.hash2function.get(&cell_hash) {
            Some(offset_map) => match offset_map.get(&offset) {
                Some(pos) => Ok(format!("{}:{}", pos.filename, pos.line)),
                None => Err("-:0 (offset not found))")
            },
            None => Err("-:0 (cell hash not found)")
        }
    }
}

impl TraceStepInfo {
    #[allow(dead_code)]
    pub fn from(info: &EngineTraceInfo, fname: Option<String>) -> TraceStepInfo {
        let stack = info.stack.iter().map(|x| x.to_string()).collect();
        TraceStepInfo {
            id: info.step,
            cmd: info.cmd_str.clone(),
            gas: info.gas_cmd,
            func: fname,
            stack,
        }
    }
}

pub fn load_debug_info(
    filename: String,
    verbose: bool,
) -> Option<ContractDebugInfo> {

    if verbose {
        println!("---- load_debug_info ({})----", filename);
    }
    let hash2function = match std::fs::read_to_string(&filename) {
        Ok(debug_info_str) => {
            serde_json::from_str::<DbgInfo>(&debug_info_str)
                .unwrap_or_else(|err| panic!("cannot parse {} - {}", filename, err))
        }
        Err(_) => return None
    };
    Some(ContractDebugInfo{hash2function})
}

pub fn get_function_name(
    debug_info: Option<&ContractDebugInfo>,
    info: &EngineTraceInfo,
) -> Option<String> {
    debug_info?.find_function(info).ok()
}

