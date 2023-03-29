/*
    This file is part of Ever OS.

    Ever OS is free software: you can redistribute it and/or modify 
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2022 (c) TON LABS
*/

use num_format::{Locale, ToFormattedString, ToFormattedStr};

use std::time::SystemTime;

use ton_types::{UInt256, SliceData, AccountId, Cell};

use ton_block::{
    CommonMsgInfo, MsgAddressIntOrNone,
    CurrencyCollection, Deserializable, ExternalInboundMessageHeader, Grams,
    InternalMessageHeader, Message, MsgAddressExt, MsgAddressInt,
    StateInit, Account,
};

pub fn grams_to_u64(n: &Grams) -> Option<u64> {
    let value = n.as_u128();
    if value <= u64::MAX as u128 {
        Some(value as u64)
    } else {
        None
    }
}

pub fn get_msg_value(msg: &Message) -> Option<u64> {
    grams_to_u64(&msg.get_value()?.grams)
}

fn get_src_addr_mut(msg: &mut Message) -> Option<&mut MsgAddressIntOrNone> {
    match msg.header_mut() {
        CommonMsgInfo::IntMsgInfo(hdr)      => Some(&mut hdr.src),
        CommonMsgInfo::ExtOutMsgInfo(hdr)   => Some(&mut hdr.src),
        CommonMsgInfo::ExtInMsgInfo(_)      => None
    }
}

pub fn substitute_address(mut msg: Message, address: &MsgAddressInt) -> Message {
    let src = get_src_addr_mut(&mut msg);
    if src.is_none() {  // possible for debots
        return msg;
    }
    let src = src.unwrap();
    if *src == MsgAddressIntOrNone::None {
        *src = MsgAddressIntOrNone::Some(address.clone());
    }
    msg
}

pub fn convert_address(address: UInt256, wc: i8) -> MsgAddressInt {
    MsgAddressInt::with_standart(None, wc, AccountId::from(address)).unwrap()
}

pub fn load_from_file(contract_file: &str) -> Result<StateInit, String> {
    let cell = Cell::read_from_file(contract_file);
    if let Ok(state_init) = StateInit::construct_from_cell(cell.clone()) {
        Ok(state_init)
    } else if let Ok(account) = Account::construct_from_cell(cell) {
        match account.state_init() {
            Some(state_init) => Ok(state_init.clone()),
            None => Err(format!("account is bad from {}", contract_file))
        }
    } else {
        Err(format!("bad file for state {}", contract_file))
    }
}

pub fn create_external_inbound_msg(src_addr: MsgAddressExt, dst_addr: MsgAddressInt, body: Option<SliceData>) -> Message {
    let hdr = ExternalInboundMessageHeader::new(src_addr, dst_addr);
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
    hdr.created_at = at.into();
    let mut msg = Message::with_int_header(hdr);
    if let Some(body) = body {
        msg.set_body(body);
    }
    msg
}

pub fn get_now() -> u64 {
    SystemTime::now().duration_since(SystemTime::UNIX_EPOCH).unwrap().as_secs()
}

pub fn get_now_ms() -> u64 {
    SystemTime::now().duration_since(SystemTime::UNIX_EPOCH).unwrap().as_millis() as u64
}

pub fn decode_address(address: impl AsRef<str>) -> MsgAddressInt {
    address.as_ref().parse().unwrap()
}

pub fn format3<T: ToFormattedStr>(value: T) -> String {
    value.to_formatted_string(&Locale::en)
}
