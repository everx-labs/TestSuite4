/*
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
*/

use std::io::Write;
use std::collections::HashMap;
use ton_types::dictionary::HashmapE;
use serde::{Deserialize, Serialize};
use ton_block::{Serializable, StateInit};
use ton_types::{UInt256, Cell};

pub struct ContractDebugInfo {
    pub hash2function: HashMap<UInt256, String>
}

#[derive(Serialize, Deserialize, Debug)]
pub struct DebugInfoFunction {
    pub id: i64,  // actually either i32 or u32.
    pub name: String
}

#[derive(Serialize, Deserialize, Debug)]
pub struct DebugInfo {
    pub internals: Vec<DebugInfoFunction>,
    pub publics: Vec<DebugInfoFunction>,
    pub privates: Vec<DebugInfoFunction>,
}

impl DebugInfo {
    pub fn _new() -> Self {
        DebugInfo { internals: vec![], publics: vec![], privates: vec![] }
    }
}


pub fn _save_debug_info(
    info: DebugInfo,
    filename: String
) {
    let s = serde_json::to_string_pretty(&info).unwrap();
    let mut f = std::fs::File::create(filename).unwrap();
    write!(f, "{}", s).unwrap();
}

pub fn load_debug_info(
    state_init: &StateInit,
    filename: String
) -> Option<ContractDebugInfo> {

    println!("---- load_debug_info ({})----", filename);

    let mut hash2function = HashMap::new();

    let debug_info_str = std::fs::read_to_string(filename);
    if debug_info_str.is_err() {
        return None;
    }
    let debug_info_json : DebugInfo = serde_json::from_str(&debug_info_str.unwrap()).unwrap();

    let root_cell = state_init.code.as_ref().unwrap();
    let dict1 = HashmapE::with_hashmap(32, Some(root_cell.reference(0).unwrap()));
    let dict2 = HashmapE::with_hashmap(32, Some(root_cell.reference(1).unwrap().reference(0).unwrap()));

    for func in debug_info_json.internals.iter() {
        let id = &(func.id as i32);
        let key = id.clone().write_to_new_cell().unwrap().into();
        let val = dict1.get(key).unwrap();
        if val.is_some() {
            let val = val.unwrap();
            let mut c = val.cell();
            let mut cc;
            loop {
                let hash = c.repr_hash();
                hash2function.insert(hash, func.name.clone());
                if c.references_count() == 0 {
                    break;
                }
                cc = c.reference(0).unwrap();
                c = &cc;
            }
        }
    }

    for func in debug_info_json.publics.iter() {
        let id = &(func.id as u32);
        let key = id.clone().write_to_new_cell().unwrap().into();
        let val = dict1.get(key).unwrap();
        if val.is_some() {
            let val = val.unwrap();
            let mut c = val.cell();
            let mut cc;
            loop {
                let hash = c.repr_hash();
                hash2function.insert(hash, func.name.clone());
                if c.references_count() == 0 {
                    break;
                }
                cc = c.reference(0).unwrap();
                c = &cc;
            }
        }
    }

    for func in debug_info_json.privates.iter() {
        let id = &(func.id as u32);
        let key = id.clone().write_to_new_cell().unwrap().into();
        if let Some(val) = dict2.get(key).unwrap() {
            set_function_hashes(&mut hash2function, &func.name, &val.cell());
        }
    }

    hash2function.insert(root_cell.repr_hash(), "selector".to_owned());
    if let Ok(selector2) = root_cell.reference(1) {
        hash2function.insert(selector2.repr_hash(), "selector2".to_owned());
    }

    Some(ContractDebugInfo{hash2function: hash2function})
}

fn set_function_hashes(
    mut hash2function: &mut HashMap<UInt256, String>,
    fname: &String,
    cell: &Cell,
) {
    let hash = cell.repr_hash();
    hash2function.insert(hash, fname.clone());
    for i in 0..cell.references_count() {
        set_function_hashes(&mut hash2function, fname, &cell.reference(i).unwrap());
    }
}
