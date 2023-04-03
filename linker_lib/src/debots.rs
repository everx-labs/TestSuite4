/*
    This file is part of Ever OS.

    Ever OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2022 (c) TON LABS
*/

// use std::convert::TryFrom;
// use std::fmt::Display;
// use failure::format_err;

// use ed25519_dalek::Keypair;

use ton_block::{
    Message as TonBlockMessage,
    MsgAddressInt,
    // MsgAddressExt, 
    CurrencyCollection, MsgAddressExt,
};

use ton_types::{
    BuilderData,
    // Cell,
    IBitstring,
    SliceData,
};

use ton_client::crypto::KeyPair;
use ton_client::debot::calltype::{
    prepare_ext_in_message as prepare_ext_in_message2,
};

use crate::global_state::{
    GlobalState,
};

use crate::exec::{
    decode_message,
};

use crate::messages::{
    MsgInfo, 
    // MsgAbiInfo,
    // MsgInfoJson,
};

#[derive(Clone, Debug)]
pub struct DebotCallInfo {
    pub answer_id: u32,
    pub onerror_id: u32,
    pub func_id: u32,
    pub debot_addr: Option<MsgAddressInt>,
    pub dst_addr: String,      // why not MsgAddressInt?
}

pub fn prepare_ext_in_message(
    msg: TonBlockMessage, 
    now_ms: u64,
    debot_keypair: Option<KeyPair>,
) -> Result<(TonBlockMessage, DebotCallInfo), String> {

    // println!("!!!! prepare_ext_in_message: body = {:?}, sz = {}", msg.body().unwrap(), msg.body().unwrap().remaining_bits());

    let (func_id, answer_id, onerror_id, dst_addr, message) = prepare_ext_in_message2(&msg, now_ms, debot_keypair)?;

    // println!("!!!! prepare_ext_in_message: func_id = {}, answer_id = {}", func_id, answer_id);

    let info = DebotCallInfo {
        answer_id,
        onerror_id,
        func_id,
        debot_addr: None,
        dst_addr: format!("{}", dst_addr),
    };

    Ok((message, info))

}

/*
fn msg_err(err: impl Display) -> ClientError {
    format_err!("{}", err)
}
*/


pub fn debot_translate_getter_answer_impl(
    gs: &mut GlobalState,
    msg_id: u32
) -> Result<MsgInfo, String> {

    if gs.is_trace(1) {
        println!("debot_translate_getter_answer_impl({})", msg_id);
    }

    let msg_info: MsgInfo = (*gs.messages.get(msg_id)).clone();

    let parent_msg_id = msg_info.parent_id().unwrap();

    let msg_info_prev: MsgInfo = (*gs.messages.get(parent_msg_id)).clone();

    // println!("!!! msg_info = {:?}", msg_info);
    // println!("!!! msg_info_prev = {:?}", msg_info_prev);

    assert!(msg_info_prev.debot_call_info.is_some());
    assert!(!msg_info_prev.has_src());

    let debot_call_info = msg_info_prev.debot_call_info.as_ref().unwrap();
    // println!("{:?}", debot_call_info);

    let debot_addr    = debot_call_info.debot_addr.clone().unwrap();
    let contract_addr = msg_info_prev.dst();

    // TODO: translate message here!
    let answer_msg = build_answer_msg(msg_info.ton_msg().unwrap(),
        debot_call_info.answer_id, debot_call_info.func_id,
        contract_addr.clone(), debot_addr, gs.config.trace_level).unwrap();

    // println!("answer_msg = {:?}", answer_msg);

    let debot_info = gs.get_contract(&contract_addr).unwrap();
    let debot_abi = debot_info.abi_info();

    let j = decode_message(gs, debot_abi, None, &answer_msg, 0, false);
    let mut msg_info = MsgInfo::create(answer_msg, j);

    msg_info.debot_call_info = Some(debot_call_info.clone());

    let result = gs.messages.add(msg_info);

    Ok((*result).clone())
}

pub fn build_internal_message(
    src: MsgAddressInt,
    dst: MsgAddressInt,
    body: SliceData,
    value: CurrencyCollection,
) -> TonBlockMessage {
    let mut msg = TonBlockMessage::with_int_header(ton_block::InternalMessageHeader::with_addresses(
        src,
        dst,
        value, // Default::default(),
    ));
    msg.set_body(body);
    msg
}

pub fn build_external_message(
    src: MsgAddressExt,
    dst: MsgAddressInt,
    body: SliceData,
) -> TonBlockMessage {
    let h = ton_block::ExternalInboundMessageHeader::new(src, dst);
    TonBlockMessage::with_ext_in_header_and_body(h, body)
}

pub fn debot_build_on_success(
    src: MsgAddressInt, 
    dst: MsgAddressInt, 
    answer_id: u32,
) -> TonBlockMessage {
    let mut new_body = BuilderData::new();
    new_body.append_u32(answer_id).unwrap();
    build_internal_message(
        src,
        dst,
        SliceData::load_builder(new_body).unwrap(),
        Default::default()
    )
}

pub fn debot_build_on_error(
    src: MsgAddressInt, 
    dst: MsgAddressInt, 
    onerror_id: u32,
    exitcode: u32,
) -> TonBlockMessage {
    let mut new_body = BuilderData::new();
    new_body.append_u32(onerror_id).unwrap();
    new_body.append_u32(0).unwrap();    // SDK error
    new_body.append_u32(exitcode).unwrap();
    build_internal_message(
        src,
        dst,
        SliceData::load_builder(new_body).unwrap(),
        Default::default()
    )
}

fn build_answer_msg(
    out_message: &TonBlockMessage,
    answer_id: u32,
    func_id: u32,
    dest_addr: MsgAddressInt,
    debot_addr: MsgAddressInt,
    trace_level: u64,
) -> Option<TonBlockMessage> {
    if trace_level >= 5 {
        println!("!!! build_answer_msg: dest_addr = {}, debot_addr = {}", dest_addr, debot_addr);
    }
    if out_message.is_internal() {
        return None;
    }
    let mut new_body = BuilderData::new();
    new_body.append_u32(answer_id).ok()?;

    if let Some(body_slice) = out_message.body().as_mut() {
        let response_id = body_slice.get_next_u32().ok()?;
        let request_id = response_id & !(1u32 << 31);
        if func_id != request_id {
            return None;
        }
        new_body
            .append_builder(&BuilderData::from_slice(body_slice))
            .ok()?;
    } 

    Some(build_internal_message(
        dest_addr,
        debot_addr,
        SliceData::load_builder(new_body).unwrap(),
        Default::default()
    ))
}


