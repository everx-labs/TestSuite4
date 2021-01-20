/*
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
*/

use ton_block::*;
use ton_types::cells_serialization::serialize_tree_of_cells;
use ton_types::Cell;

pub fn state_init_printer(state: &StateInit) -> String {
    format!("StateInit\n split_depth: {}\n special: {}\n data: {}\n code: {}\n lib:  {}\n",
        state.split_depth.as_ref().map(|x| format!("{:?}", x)).unwrap_or("None".to_string()),
        state.special.as_ref().map(|x| format!("{:?}", x)).unwrap_or("None".to_string()),
        tree_of_cells_into_base64(state.data.as_ref()),
        tree_of_cells_into_base64(state.code.as_ref()),
        tree_of_cells_into_base64(state.library.root()),
    )
}

fn tree_of_cells_into_base64(root_cell: Option<&Cell>) -> String {
    match root_cell {
        Some(cell) => {
            let mut bytes = Vec::new();
            serialize_tree_of_cells(cell, &mut bytes).unwrap();
            base64::encode(&bytes)
        }
        None => "None".to_string()
    }
}

pub fn msg_printer(msg: &Message) -> String {
    format!("message header\n{}init  : {}\nbody  : {}\nbody_hex: {}\nbody_base64: {}\n",
        print_msg_header(&msg.header()),
        msg.state_init().as_ref().map(|x| {
            format!("{}", state_init_printer(x))
        }).unwrap_or("None".to_string()),
        match msg.body() {
            Some(slice) => format!("{:.2}", slice.into_cell()),
            None => "None".to_string(),
        },
        msg.body()
            .map(|b| hex::encode(b.get_bytestring(0)))
            .unwrap_or("None".to_string()),
        tree_of_cells_into_base64(
            msg.body()
                .map(|slice| slice.into_cell())
                .as_ref(),
        ),
    )
}

fn print_msg_header(header: &CommonMsgInfo) -> String {
    match header {
        CommonMsgInfo::IntMsgInfo(header) => {
            format!("   ihr_disabled: {}\n", header.ihr_disabled) +
            &format!("   bounce      : {}\n", header.bounce) +
            &format!("   bounced     : {}\n", header.bounced) +
            &format!("   source      : {}\n", &header.src) +
            &format!("   destination : {}\n", &header.dst) +
            &format!("   value       : {}\n", header.value) +
            &format!("   ihr_fee     : {}\n", header.ihr_fee) +
            &format!("   fwd_fee     : {}\n", header.fwd_fee) +
            &format!("   created_lt  : {}\n", header.created_lt) +
            &format!("   created_at  : {}\n", header.created_at)
        },
        CommonMsgInfo::ExtInMsgInfo(header) => {
            format!( "   source      : {}\n", &header.src) +
            &format!("   destination : {}\n", &header.dst) +
            &format!("   import_fee  : {}\n", header.import_fee)
        },
        CommonMsgInfo::ExtOutMsgInfo(header) => {
            format!( "   source      : {}\n", &header.src) +
            &format!("   destination : {}\n", &header.dst) +
            &format!("   created_lt  : {}\n", header.created_lt) +
            &format!("   created_at  : {}\n", header.created_at)
        }
    }
}