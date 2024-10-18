/*
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify 
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
*/

use std::time::SystemTime;
use std::str::FromStr;

use ever_block::{
    UInt256, SliceData, AccountId,
};

use ever_block::{
    CommonMsgInfo, MsgAddressIntOrNone,
    CurrencyCollection, Deserializable, ExternalInboundMessageHeader, Grams,
    InternalMessageHeader, Message, MsgAddressExt, MsgAddressInt,
    StateInit, UnixTime32,
};

pub fn get_msg_value(msg: &Message) -> Option<u64> {
    msg.get_value()?.grams.as_u64()
}

fn get_src_addr_mut<'a>(msg: &'a mut Message) -> Option<&'a mut MsgAddressIntOrNone> {
    match msg.header_mut() {
        CommonMsgInfo::IntMsgInfo(hdr)      => Some(&mut hdr.src),
        CommonMsgInfo::ExtOutMsgInfo(hdr)   => Some(&mut hdr.src),
        CommonMsgInfo::ExtInMsgInfo(_)      => None
    }
}

pub fn substitute_address(mut msg: Message, address: &MsgAddressInt) -> Message {
    let src = get_src_addr_mut(&mut msg).unwrap();
    if *src == MsgAddressIntOrNone::None {
        *src = MsgAddressIntOrNone::Some(address.clone());
    }
    msg
}

pub fn convert_address(address: UInt256, wc: i8) -> MsgAddressInt {
    MsgAddressInt::with_standart(None, wc, AccountId::from(address)).unwrap()
}

pub fn load_from_file(contract_file: &str) -> StateInit {
    let content = std::fs::read(contract_file)
        .map_err(|e| format!("Cannot load {}: {}", contract_file, e))
        .unwrap();      // TODO!: return error
    StateInit::construct_from_bytes(&content).unwrap()
}

pub fn create_external_inbound_msg(src_addr: MsgAddressExt, dst_addr: MsgAddressInt, body: Option<SliceData>) -> Message {
    let mut hdr = ExternalInboundMessageHeader::default();
    hdr.dst = dst_addr;
    hdr.src = src_addr;
    hdr.import_fee = 0x1234.into();   // TODO: what's that?
    let mut msg = Message::with_ext_in_header(hdr);
    if let Some(body) = body {
        msg.set_body(body);
    }
    msg
}

pub fn create_internal_msg(
    src_addr: MsgAddressInt,
    dst_addr: MsgAddressInt,
    value: CurrencyCollection,
    lt: u64,
    at: u32,
    body: Option<SliceData>,
    bounced: bool,
) -> Message {
    let mut hdr = InternalMessageHeader::with_addresses(
        src_addr,
        dst_addr,
        value,
    );
    hdr.bounce = !bounced;
    hdr.bounced = bounced;
    hdr.ihr_disabled = true;
    hdr.ihr_fee = Grams::from(0u64);
    hdr.created_lt = lt;
    hdr.created_at = UnixTime32::new(at);
    let mut msg = Message::with_int_header(hdr);
    if let Some(body) = body {
        msg.set_body(body);
    }
    msg
}

pub fn get_now() -> u64 {
    SystemTime::now().duration_since(SystemTime::UNIX_EPOCH).unwrap().as_secs() as u64
}

pub fn decode_address(address: &String) -> MsgAddressInt {
    MsgAddressInt::from_str(&address).unwrap()
}

