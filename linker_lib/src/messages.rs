/*
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
*/

use std::sync::Arc;
use serde_json::Value as JsonValue;

use serde::{
    Serialize, Serializer
};


use ton_block::{
    Message as TonBlockMessage,
    CommonMsgInfo, CurrencyCollection,
    MsgAddress, MsgAddressExt, MsgAddressInt, MsgAddressIntOrNone,
};

use ton_types::{
    BuilderData, IBitstring,
};

use crate::util::{
    create_external_inbound_msg, create_internal_msg,
};

use crate::debots::{
    DebotCallInfo,
};

///////////////////////////////////////////////////////////////////////////////////////

#[derive(Clone, Debug)]
pub struct AddressWrapper {
    pub addr: MsgAddress
}

impl AddressWrapper {
    pub fn with_int(addr: MsgAddressInt) -> AddressWrapper {
        let addr = match addr {
            MsgAddressInt::AddrStd(a) => MsgAddress::AddrStd(a),
            MsgAddressInt::AddrVar(a) => MsgAddress::AddrVar(a)
        };
        AddressWrapper{ addr }
    }
    pub fn with_ext(addr: MsgAddressExt) -> AddressWrapper {
        let addr = match addr {
            MsgAddressExt::AddrNone      => MsgAddress::AddrNone,
            MsgAddressExt::AddrExtern(a) => MsgAddress::AddrExt(a)
        };
        AddressWrapper{ addr }
    }
    pub fn to_int(&self) -> Option<MsgAddressInt> {
        match self.addr.clone() {
            MsgAddress::AddrStd(a) => Some(MsgAddressInt::AddrStd(a)),
            MsgAddress::AddrVar(a) => Some(MsgAddressInt::AddrVar(a)),
            _ => None
        }
    }
}

impl Serialize for AddressWrapper {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
        where S: Serializer
    {
        serializer.serialize_str(&format!("{}", self.addr))
    }
}

///////////////////////////////////////////////////////////////////////////////////////

#[derive(Clone, Debug, PartialEq)]
pub enum MsgType {
    MsgUndefined,
    MsgUnknown,
    MsgEmpty,
    MsgCall,
    MsgCallGetter,
    MsgExtCall,
    MsgAnswer,
    MsgEvent,
    MsgLog,
}

// for sending to Python
#[derive(Clone, Debug, Default, Serialize)]
pub struct MsgInfoJson {
    id:         Option<u32>,
    pub parent_id:  Option<u32>,
    msg_type:   MsgType,
    src:        Option<AddressWrapper>,
    dst:        Option<AddressWrapper>,
    name:       Option<String>,
    params:     Option<JsonValue>,
    value:      Option<u64>,
    timestamp:  Option<u64>,
    bounce:     Option<bool>,
    bounced:    Option<bool>,
    log_str:    Option<String>,
    pub debot_info: Option<MsgInfoJsonDebot>,
}

// for sending to Python
#[derive(Clone, Debug, Serialize)]
pub struct MsgInfoJsonDebot {
    pub debot_addr:  AddressWrapper,
}

// from ABI
#[derive(Default, Debug)]
pub struct MsgAbiInfo {
    t: MsgType,
    params:     Option<JsonValue>,
    is_getter:  Option<bool>,
    name:       Option<String>,
    value:      Option<u64>,
    timestamp:  Option<u64>,
    is_debot:   bool,
}

// for storing in all messages
#[derive(Clone, Debug)]
pub struct MsgInfo {
    ton_msg:        Option<TonBlockMessage>,
    pub json:           MsgInfoJson,
    pub debot_call_info:    Option<DebotCallInfo>,
}

// for call_contract_ex()
#[derive(Default)]
pub struct CallContractMsgInfo {        // TODO: move
    id:                     Option<u32>,
    ton_msg:                Option<TonBlockMessage>,
    dst:                    Option<MsgAddressInt>,
    value:                  Option<u64>,
    pub ticktock:           Option<i8>,
    is_getter_call:         bool,
    is_offchain_ctor_call:  bool,
    is_debot_call:          bool,
}

#[derive(Default)]
pub struct MessageStorage {
    messages: Vec<Arc<MsgInfo>>,
}

///////////////////////////////////////////////////////////////////////////////////////

impl Default for MsgType {
    fn default() -> Self {
        MsgType::MsgUndefined
    }
}

impl MsgType {
    fn to_string(&self) -> &str {
        match self {
            Self::MsgUndefined  => "undefined",
            Self::MsgUnknown    => "unknown",
            Self::MsgEmpty      => "empty",
            Self::MsgCall       => "call",
            Self::MsgCallGetter => "call_getter",
            Self::MsgExtCall    => "external_call",
            Self::MsgAnswer     => "answer",
            Self::MsgEvent      => "event",
            Self::MsgLog        => "log",
        }
    }
}

impl Serialize for MsgType {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
        where S: Serializer
    {
        serializer.serialize_str(self.to_string())
    }
}

///////////////////////////////////////////////////////////////////////////////////////

impl MsgInfoJson {
    fn with_decoded_info(ton_msg: &TonBlockMessage, msg: MsgAbiInfo) -> MsgInfoJson {

        let (src, dst) = fetch_src_dst(&ton_msg);

        // TODO: move
        // TODO: get_int_header()
        let (bounce, bounced) = match ton_msg.header() {
            CommonMsgInfo::IntMsgInfo(header) =>
                 (Some(header.bounce), Some(header.bounced)),
            _ => (None, None)
        };

        MsgInfoJson {
            id:         None,
            parent_id:  None,
            msg_type:   msg.msg_type(),
            src:        src.clone(),
            dst:        dst.clone(),
            params:     msg.params,
            name:       msg.name,
            value:      msg.value,
            timestamp:  msg.timestamp,
            bounce:     bounce,
            bounced:    bounced,
            log_str:    None,
            debot_info: None,
        }
    }

    pub fn with_log_str(s: String, timestamp: u64) -> MsgInfoJson {
        let mut msg_json = Self::default();
        msg_json.msg_type   = MsgType::MsgLog;
        msg_json.log_str    = Some(s);
        msg_json.timestamp  = Some(timestamp);
        msg_json
    }

    fn to_json(&self) -> JsonValue {
        serde_json::to_value(&self).unwrap()
    }
}

///////////////////////////////////////////////////////////////////////////////////////

impl CallContractMsgInfo {      // TODO: move to call_contract.rs

    pub fn id(&self) -> Option<u32> {
        self.id.clone()
    }

    pub fn ton_msg(&self) -> Option<&TonBlockMessage> {
        self.ton_msg.as_ref()
    }

    // pub fn set_ton_msg(&mut self, ton_msg: TonBlockMessage) {
        // self.ton_msg = Some(ton_msg);
    // }

    pub fn value(&self) -> Option<u64> {
        self.value.clone()
    }

    pub fn dst(&self) -> MsgAddressInt {
        self.dst.clone().unwrap()
    }

    pub fn is_ext_msg(&self) -> bool {
        match self.ton_msg() {
            Some(msg) => {
                match msg.header() {
                    CommonMsgInfo::ExtInMsgInfo(_header) => true,
                    _ => false
                }
            },
            None => false
        }
    }

    pub fn is_external_call(&self) -> bool {
        self.is_ext_msg() && !self.is_getter_call && !self.is_offchain_ctor_call && !self.is_debot_call
    }

    pub fn is_offchain_ctor_call(&self) -> bool {
        self.is_offchain_ctor_call
    }

    pub fn is_getter_call(&self) -> bool {
        self.is_getter_call
    }

    pub fn is_debot_call(&self) -> bool {
        self.is_debot_call
    }

    fn with_ton_msg(msg: TonBlockMessage) -> CallContractMsgInfo {
        let dst = msg.dst().clone().unwrap();
        let mut msg_info = Self::default();
        msg_info.dst     = Some(dst);
        msg_info.ton_msg = Some(msg);
        msg_info
    }

    pub fn with_info(msg: &MsgInfo) -> CallContractMsgInfo {
        let mut info = Self::with_ton_msg(msg.ton_msg().unwrap().clone());     // TODO: ton_msg to Arc
        info.id    = Some(msg.id());
        info.value = msg.value();
        info.is_debot_call = msg.debot_call_info.is_some();
        info
    }

    pub fn with_ticktock(is_tock: bool, address: MsgAddressInt) -> CallContractMsgInfo {
        let mut msg_info = Self::default();
        msg_info.ticktock = Some(if is_tock { -1 } else { 0 });
        msg_info.dst = Some(address);
        msg_info
    }

    pub fn with_offchain_ctor(msg: TonBlockMessage) -> CallContractMsgInfo {
        let mut msg_info = Self::with_ton_msg(msg);
        msg_info.is_offchain_ctor_call = true;
        msg_info
    }

    pub fn with_getter(msg: TonBlockMessage, is_getter: bool, is_debot: bool) -> CallContractMsgInfo {
        let mut msg_info = Self::with_ton_msg(msg);
        msg_info.is_getter_call = is_getter;
        msg_info.is_debot_call  = is_debot;
        msg_info
    }

}

///////////////////////////////////////////////////////////////////////////////////////

impl MsgAbiInfo {

    fn with_type(t: MsgType) -> MsgAbiInfo {
        let mut j = MsgAbiInfo::default();
        j.t = t;
        j
    }

    fn with_params(msg_type: MsgType, params: String, name: String) -> MsgAbiInfo {
        let mut info = Self::with_type(msg_type);
        info.set_params(params);
        info.name = Some(name);
        info
    }

    fn msg_type(&self) -> MsgType {
        match self.is_getter {
            Some(is_getter) => {
                assert!(MsgType::MsgCall == self.t);
                if is_getter { MsgType::MsgCallGetter } else { MsgType::MsgExtCall }
            },
            None => self.t.clone()
        }
    }

    pub fn create_empty() -> MsgAbiInfo {
        MsgAbiInfo::with_type(MsgType::MsgEmpty)
    }

    pub fn create_unknown() -> MsgAbiInfo {
        MsgAbiInfo::with_type(MsgType::MsgUnknown)
    }

    fn set_params(&mut self, s: String) {
        let params: JsonValue = serde_json::from_str(&s).unwrap();
        self.params = Some(params);
    }

    pub fn create_answer(s: String, method: String) -> MsgAbiInfo {
        Self::with_params(MsgType::MsgAnswer, s, method)
    }

    pub fn create_call(s: String, method: String) -> MsgAbiInfo {
        Self::with_params(MsgType::MsgCall, s, method)
    }

    pub fn create_event(s: String, event: String) -> MsgAbiInfo {
        Self::with_params(MsgType::MsgEvent, s, event)
    }

    pub fn fix_call(&mut self, is_getter: bool) {
        assert!(self.t == MsgType::MsgCall);
        self.is_getter = Some(is_getter);
    }

    pub fn fix_value(&mut self, value: u64) {
        self.value = Some(value);
    }

    pub fn fix_timestamp(&mut self, timestamp: u64) {
        self.timestamp = Some(timestamp);
    }
    
    pub fn set_debot_mode(&mut self) {
        self.is_debot = true;
    }

}

///////////////////////////////////////////////////////////////////////////////////////

impl MsgInfo {

    pub fn create(ton_msg: TonBlockMessage, msg: MsgAbiInfo) -> MsgInfo {
        let msg_json = MsgInfoJson::with_decoded_info(&ton_msg, msg);
        MsgInfo { ton_msg: Some(ton_msg), json: msg_json, debot_call_info: None }
    }

    pub fn with_log_str(text: String, timestamp: u64) -> MsgInfo {
        let msg_json = MsgInfoJson::with_log_str(text, timestamp);
        MsgInfo { ton_msg: None, json: msg_json, debot_call_info: None }
    }

    pub fn id(&self) -> u32 {
        self.json.id.unwrap()
    }

    pub fn parent_id(&self) -> Option<u32> {
        self.json.parent_id
    }

    pub fn ton_msg(&self) -> Option<&TonBlockMessage> {
        self.ton_msg.as_ref()
    }

    pub fn set_ton_msg(&mut self, ton_msg: TonBlockMessage) {
        self.ton_msg = Some(ton_msg);
    }

    pub fn src(&self) -> MsgAddressInt {        // TODO: use AddressWrapper
        self.json.src.as_ref().unwrap().to_int().unwrap()
    }

    pub fn has_src(&self) -> bool {
        return !self.json.src.as_ref().is_none();
    }

    pub fn dst(&self) -> MsgAddressInt {        // TODO: use AddressWrapper
        self.json.dst.as_ref().unwrap().to_int().unwrap()
    }

    pub fn bounce(&self) -> bool {
        self.json.bounce.unwrap_or(false)
    }

    pub fn json(&self) -> JsonValue {
        self.json.to_json()
    }

    pub fn json_str(&self) -> String {
        self.json().to_string()
    }

    pub fn set_id(&mut self, id: u32) {
        assert!(self.json.id.is_none());
        self.json.id = Some(id);
    }

    pub fn set_parent_id(&mut self, parent_id: u32) {
        assert!(self.json.parent_id.is_none());
        self.json.parent_id = Some(parent_id);
    }

    pub fn value(&self) -> Option<u64> {
        self.json.value
    }

}

///////////////////////////////////////////////////////////////////////////////////////

fn addr_int_to_wrapper(addr: &MsgAddressIntOrNone) -> Option<AddressWrapper> {
    if let MsgAddressIntOrNone::Some(src) = addr {
        Some(AddressWrapper::with_int(src.clone()))
    } else {
        None
    }
}

fn fetch_src_dst(ton_msg: &TonBlockMessage) -> (Option<AddressWrapper>, Option<AddressWrapper>) {
    match ton_msg.header() {
        CommonMsgInfo::IntMsgInfo(header) => {
            let src = addr_int_to_wrapper(&header.src);
            let dst = Some(AddressWrapper::with_int(header.dst.clone()));
            (src, dst)
        },
        CommonMsgInfo::ExtOutMsgInfo(header) => {
            let src = addr_int_to_wrapper(&header.src);
            let dst = Some(AddressWrapper::with_ext(header.dst.clone()));
            (src, dst)
        },
        CommonMsgInfo::ExtInMsgInfo(header) => {
            let dst = Some(AddressWrapper::with_int(header.dst.clone()));
            (None, dst)
        },
    }
}

fn substitute_created_at(msg: &TonBlockMessage, now: u32) -> TonBlockMessage {
    let mut msg = msg.clone();
    if let Some(int_header) = msg.int_header_mut() {
        int_header.created_at = now.into();
    }
    msg
}

impl MessageStorage {
    pub fn add(&mut self, msg_info: MsgInfo) -> Arc<MsgInfo> {
        let mut msg_info = msg_info;
        let timestamp = msg_info.json.timestamp.unwrap();
        msg_info.ton_msg = msg_info.ton_msg.map(
            |msg| substitute_created_at(&msg, timestamp as u32)
        );
        msg_info.set_id(self.messages.len() as u32);
        let msg_info = Arc::new(msg_info);
        self.messages.push(msg_info.clone());
        msg_info
    }
    pub fn get(&self, id: u32) -> Arc<MsgInfo> {
        self.messages[id as usize].clone()
    }
    pub fn to_json(&self) -> JsonValue {
        self.messages.iter().map(|msg| msg.json().clone()).collect()
    }
    pub fn set_debot_call_info(&mut self, id: u32, debot_call_info: DebotCallInfo) {
        let mut msg_info = (*self.get(id)).clone();
        msg_info.debot_call_info = Some(debot_call_info);
        let msg_info = Arc::new(msg_info);
        self.messages[id as usize] = msg_info;
    }
}

///////////////////////////////////////////////////////////////////////////////////////

pub fn create_bounced_msg(msg: &MsgInfo, now: u64) -> TonBlockMessage {

    let ton_msg     = msg.ton_msg().unwrap().clone();
    let msg_value   = msg.value().unwrap();
    let bounce      = msg.bounce();

    assert!(bounce);

    let mut b = BuilderData::new();
    b.append_u32(0xffffffff).unwrap();
    if let Some(body) = ton_msg.body() {
        // TODO: handle possible overflow here
        b.append_bytestring(&body).unwrap();
    }
    let body = b.into();

    create_internal_msg(
        msg.dst(),
        msg.src(),
        CurrencyCollection::with_grams(msg_value),
        1,
        now as u32,
        Some(body),
        true, // bounced
    )
}

pub fn create_inbound_msg(
    addr: MsgAddressInt,
    body: &BuilderData,
    now: u64,
) -> TonBlockMessage {
    create_inbound_msg_impl(-1, &body, addr, now).unwrap()
}

fn create_inbound_msg_impl(         // TODO: this function is used in only one place
    selector: i32,
    body: &BuilderData,
    dst: MsgAddressInt,
    now: u64
) -> Option<TonBlockMessage> {
    let src: Option<MsgAddressInt> = None;
    let bounced = false;
    match selector {
        0 => {
            let src = match &src {
                Some(addr) => addr.clone(),
                None => MsgAddressInt::with_standart(None, 0, [0u8; 32].into()).unwrap(),
            };
            Some(create_internal_msg(
                src,
                dst,
                CurrencyCollection::with_grams(0),
                1,
                now as u32,
                Some(body.into()),
                bounced,
            ))
        },
        -1 => {
            let src = match &src {
                Some(_addr) => {
                    // TODO: rewrite this code
                    panic!("Unexpected address");
                },
                None => {
                    // TODO: Use MsgAdressNone?
                    MsgAddressExt::with_extern(
                        BuilderData::with_raw(vec![0x55; 8], 64).unwrap().into()
                    ).unwrap()
                },
            };
            Some(create_external_inbound_msg(
                src,
                dst,
                Some(body.into()),
            ))
        },
        _ => None,
    }
}

