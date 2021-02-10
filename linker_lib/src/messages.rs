/*
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
*/

use serde_json::Value as JsonValue;

use ton_block::{
    Message as TonBlockMessage,
    CommonMsgInfo, CurrencyCollection,
    MsgAddressExt, MsgAddressInt,
};

use ton_types::{
    BuilderData, IBitstring,
};

use crate::util::{
    create_external_inbound_msg, create_internal_msg,
};

#[derive(PartialEq)]
pub enum MsgType {
    MsgUnknown,
    MsgEmpty,
    MsgCall,
    MsgAnswer,
    MsgEvent
}

#[derive(Default)]
pub struct DecodedMessageInfo {
    t: MsgType,
    params: Option<JsonValue>,
    is_getter: Option<bool>,
    // bounce: Option<bool>,
    method: Option<String>,
    event: Option<String>,
    value: Option<u64>,
    timestamp: Option<u64>,
}

#[derive(Clone, Debug, Default)]
pub struct MessageInfo {
    message_id: u32,
    pub ton_msg: TonBlockMessage,
    pub src: Option<MsgAddressInt>,
    pub dst: Option<MsgAddressInt>,
    pub bounce: Option<bool>,
    pub bounced: Option<bool>,
    json: JsonValue,    // TODO! change it to DecodedMessageInfo to know type when needed...
}

#[derive(Default)]
pub struct MessageInfo2 {
    pub id: Option<u32>,
    pub msg: Option<TonBlockMessage>,
    pub value: Option<u64>,
    pub ticktock: Option<i8>,
}

#[derive(Default)]
pub struct MessageStorage {
    messages: Vec<MessageInfo>,
}

impl Default for MsgType {
    fn default() -> Self {
        MsgType::MsgUnknown
    }
}

impl DecodedMessageInfo {

    fn type_str(&self) -> String {
        if self.t == MsgType::MsgUnknown {
            return "unknown".to_string();
        }
        if self.t == MsgType::MsgEmpty {
            return "empty".to_string();
        }
        if self.t == MsgType::MsgCall {
            return "call".to_string();
        }
        if self.t == MsgType::MsgAnswer {
            return "answer".to_string();
        }
        if self.t == MsgType::MsgEvent {
            return "event".to_string();
        }
        panic!("Unexpected type");
    }

    fn with_type(t: MsgType) -> DecodedMessageInfo {
        let mut j = DecodedMessageInfo::default();
        j.t = t;
        j
    }

    pub fn create_empty() -> DecodedMessageInfo {
        DecodedMessageInfo::with_type(MsgType::MsgEmpty)
    }

    pub fn create_unknown() -> DecodedMessageInfo {
        DecodedMessageInfo::with_type(MsgType::MsgUnknown)
    }

    fn set_params(&mut self, s: String) {
        let params: JsonValue = serde_json::from_str(&s).unwrap();
        self.params = Some(params);
    }

    pub fn create_answer(s : String, method: String) -> DecodedMessageInfo {
        let mut j = DecodedMessageInfo::with_type(MsgType::MsgAnswer);
        j.set_params(s);
        j.method = Some(method);
        j
    }

    pub fn create_call(s : String, method: String) -> DecodedMessageInfo {
        let mut j = DecodedMessageInfo::with_type(MsgType::MsgCall);
        j.set_params(s);
        j.method = Some(method);
        j
    }

    pub fn create_event(s : String, event: String) -> DecodedMessageInfo {
        let mut j = DecodedMessageInfo::with_type(MsgType::MsgEvent);
        j.set_params(s);
        j.event = Some(event);
        j
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

}

impl MessageInfo {
    pub fn create(ton_msg: TonBlockMessage, msg: DecodedMessageInfo) -> MessageInfo {
        let mut j = json!({});
        j["type"] = JsonValue::from(msg.type_str());
        if let Some(params) = msg.params {
            j["params"] = params
        }
        if let Some(is_getter) = msg.is_getter {
            let t = if is_getter { "call_getter" } else { "external_call" };
            j["type"] = JsonValue::from(t);
        }
        if let Some(method) = msg.method {
            j["method"] = JsonValue::from(method);
        }
        if let Some(event) = msg.event {
            j["event"] = JsonValue::from(event);
        }
        if let Some(value) = msg.value {
            j["value"] = JsonValue::from(value);
        }
        if let Some(timestamp) = msg.timestamp {
            j["timestamp"] = JsonValue::from(timestamp);
        }
        let (src, dst) = fetch_src_dst(&ton_msg);
        let bounce = if let CommonMsgInfo::IntMsgInfo(header) = ton_msg.header() {
            Some(header.bounce)
        } else {
            None
        };
        let bounced = if let CommonMsgInfo::IntMsgInfo(header) = ton_msg.header() {
            Some(header.bounced)
        } else {
            None
        };
        if let Some(bounced) = bounced {
            j["bounced"] = JsonValue::from(bounced);
        }

        j = fetch_addresses(&ton_msg, j);
        let mut msg_info = MessageInfo::default();
        msg_info.ton_msg = ton_msg;
        msg_info.json = j;
        msg_info.src = src;
        msg_info.dst = dst;
        msg_info.bounce = bounce;
        msg_info.bounced = bounced;
        msg_info
    }

    pub fn json(&self) -> &JsonValue {
        &self.json
    }

    pub fn json_str(&self) -> String {
        self.json.to_string()
    }

    pub fn set_id(&mut self, id: u32) {
        assert!(self.message_id == 0);
        self.message_id = id;
        self.json["id"] = JsonValue::from(id);
    }

    pub fn value(&self) -> u64 {
        // TODO!: is this decoding needed?
        self.json["value"].as_u64().unwrap()
    }
}

fn fetch_addresses(ton_msg: &TonBlockMessage, mut j: JsonValue) -> JsonValue {
    let hdr = ton_msg.header();
    if let CommonMsgInfo::IntMsgInfo(header) = hdr {
        j["src"] = JsonValue::from(format!("{}", header.src));
        j["dst"] = JsonValue::from(format!("{}", header.dst));
    }
    if let CommonMsgInfo::ExtInMsgInfo(header) = hdr {
        j["dst"] = JsonValue::from(format!("{}", header.dst));
    }
    if let CommonMsgInfo::ExtOutMsgInfo(header) = hdr {
        j["src"] = JsonValue::from(format!("{}", header.src));
        j["dst"] = JsonValue::from(format!("{}", header.dst));
    }
    j
}

fn fetch_src_dst(ton_msg: &TonBlockMessage) -> (Option<MsgAddressInt>, Option<MsgAddressInt>) {
    let hdr = ton_msg.header();
    if let CommonMsgInfo::IntMsgInfo(header) = hdr {
        let src = if let ton_block::MsgAddressIntOrNone::Some(src) = &header.src {
            Some(src.clone())
        } else {
            None
        };
        let dst = Some(header.dst.clone());
        (src, dst)
    } else {
        (None, None)
    }
}

impl MessageStorage {
    pub fn add(&mut self, msg_info: MessageInfo) -> MessageInfo {
        let mut msg_info = msg_info;
        msg_info.set_id(self.messages.len() as u32);
        self.messages.push(msg_info.clone());
        msg_info
    }
    pub fn get(&self, id: u32) -> &MessageInfo {
        &self.messages[id as usize]
    }
    pub fn to_json(&self) -> JsonValue {
        self.messages.iter().map(|msg| msg.json().clone()).collect()
    }
}

pub fn create_bounced_msg(msg: &MessageInfo, now: u64) -> TonBlockMessage {
    let ton_msg = msg.ton_msg.clone();
    let msg_value = msg.value();
    let bounce = msg.bounce.unwrap_or(false);
    assert!(bounce);
    let src = msg.src.clone().unwrap();
    let dst = ton_msg.dst().unwrap();

    let mut b = BuilderData::new();
    b.append_u32(0xffffffff).unwrap();
    if let Some(body) = ton_msg.body() {
        // TODO: handle possible overflow here
        b.append_bytestring(&body).unwrap();
    }
    let body = b.into();

    create_internal_msg(
        dst,
        src,
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

fn create_inbound_msg_impl(         // TODO!!: this function is used in only one place
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

