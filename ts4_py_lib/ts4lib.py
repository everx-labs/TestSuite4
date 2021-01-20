"""
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
"""

import linker_lib as core
import sys
import base64, binascii
import secrets
import json
import re

GRAM = 1_000_000_000
EMPTY_CELL = 'te6ccgEBAQEAAgAAAA=='

QUEUE = []
EVENTS = []

G_VERBOSE       = False
G_DUMP_MESSAGES = False
G_STOP_AT_CRASH = True
G_WARN_ON_UNEXPECTED_ANSWERS = False

G_SHOW_EVENTS   = False

G_MSG_FILTER    = None


class BColors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def set_verbose(f):
    global G_VERBOSE
    G_VERBOSE = f

def set_stop_at_crash(f):
    global G_STOP_AT_CRASH
    G_STOP_AT_CRASH = f

def verbose_(msg):
    verbose(msg, show_always = True, red = True)

def verbose(msg, show_always = False, red = False):
    if G_VERBOSE or show_always:
        if red:
            msg = colorize(BColors.FAIL, str(msg))
        print(msg)

def process_actions(result):
    (ec, actions, gas) = result
    assert eq(0, ec, dismiss = not G_STOP_AT_CRASH)
    actions = [json.loads(j) for j in actions]
    # print('actions =', actions)
    for msg in actions:
        # if G_VERBOSE:
            # print('process msg:', msg)
        msg_type = msg['type']
        if msg_type == 'event':
            if G_VERBOSE or G_SHOW_EVENTS:
                xtra = ''
                if msg['event'] == "DebugEvent":
                    xtra = ' ={}'.format(decode_int(msg['params']['x']))
                elif msg['event'] == 'LogEvent':
                    msg['params']['comment'] = bytearray.fromhex(msg['params']['comment']).decode()
                print(colorize(BColors.WARNING, "{} {}{}".format(msg['event'], msg['params'], xtra)))
            EVENTS.append(msg)
        else:
            if msg_type == 'unknown':
                if G_VERBOSE:
                    print(colorize(BColors.WARNING, "WARNING! Unknown message!"))
            elif G_WARN_ON_UNEXPECTED_ANSWERS and msg_type == 'answer':
                verbose_('WARNING! Unexpected answer!')
                continue
            else:
                assert (msg_type == 'call') or (msg_type == 'empty')
            QUEUE.append(msg)
    return gas

def pop_msg():
    assert len(QUEUE) > 0
    return QUEUE.pop(0)

def peek_msg():
    assert len(QUEUE) > 0
    return QUEUE[0]

def pop_event():
    assert len(EVENTS) > 0
    return EVENTS.pop(0)

def peek_event():
    assert len(EVENTS) > 0
    return EVENTS[0]

def queue_length():
    return len(QUEUE)

def ensure_queue_empty():
    assert len(QUEUE) == 0

def dump_queue():
    print(colorize(BColors.BOLD, "QUEUE:"))
    for i in range(len(QUEUE)):
        print("  {}: {}".format(i, QUEUE[i]))

ALL_MESSAGES = []

def dispatch_messages():
    while len(QUEUE) > 0:
        dispatch_one_message()

def dump_all_messages():
    prev_time = 0
    for msg in ALL_MESSAGES:
        cur_time = msg['timestamp']
        if cur_time == prev_time:
            print('---------------')
        else:
            print('--------------- {} ------------ ------------ ------------'
                .format(colorize(BColors.BOLD, str(cur_time))))
            prev_time = cur_time
        # dump_struct(msg)
        dump_message(msg)

NICKNAMES = dict()

def register_nickname(address, nickname):
    NICKNAMES[address] = nickname

def addr_to_str(address):
    if address == '':
        return 'addr_none'
    s = address[:10]
    if address in NICKNAMES:
        s = "{} ({})".format(NICKNAMES[address], s)
    return s

def dump_message(msg):
    type = msg['type']
    value = msg['value'] / GRAM if 'value' in msg else 'n/a'
    # print(msg)
    print(colorize(BColors.WARNING, '> {} -> {}'.format(
        addr_to_str(msg['src']),
        addr_to_str(msg['dst'])
    )) + ', v: {}'.format(value))
    if type == 'call' or type == 'empty':
        # ttt = "{}".format(msg)
        if type == 'call':
            method = msg['method']
            params = msg['params']
            ttt = "{} {}".format(colorize(BColors.OKGREEN, method), params)
        else:
            ttt = colorize(BColors.OKGREEN, '<empty>')
        print("> " + ttt)
    elif type == 'unknown':
        ttt = colorize(BColors.OKGREEN, '<unknown>')
        print("> " + ttt)
    else:
        ttt = '{}'.format(msg)
        print("> " + colorize(BColors.OKGREEN, ttt))

def dispatch_one_message():
    msg = pop_msg()
    ALL_MESSAGES.append(msg)
    # if is_method_call(msg, 'onRoundComplete'):
        # dump_message(msg)
    dump1 = G_VERBOSE or G_DUMP_MESSAGES
    dump2 = G_MSG_FILTER is not None and G_MSG_FILTER(msg)
    if dump1 or dump2:
        dump_message(msg)
    if msg['dst'] == '':
        # TODO: a getter's reply. Add a test for that
        return
    # if msg['id'] == 2050: core.set_trace(True)
    result = process_actions(core.dispatch_message(msg['id']))
    # if msg['id'] == 2050: quit()
    return result

def set_msg_filter(filter):
    global G_MSG_FILTER
    if filter is True:  filter = lambda msg: True
    if filter is False: filter = None
    G_MSG_FILTER = filter

def decode_int(v):
    if v[0:2] == '0x':
        return int(v.replace('0x', ''), 16)
    else:
        return int(v)

def decode_json_value(value, full_type, decode_ints):
    type = full_type['type']

    if re.match(r'^(u)?int\d+$', type):
        return decode_int(value) if decode_ints else value

    if type[-2:] == '[]':
        type2 = full_type
        type2['type'] = type[:-2]
        res = []
        for v in value:
            res.append(decode_json_value(v, type2, decode_ints))
        return res

    if type == 'bool':
        return bool(value)

    if type in ['cell', 'bytes', 'address']:
        return value

    if type == 'tuple':
        res = {}
        for c in full_type['components']:
            field = c['name']
            res[field] = decode_json_value(value[field], c, decode_ints)
        return res

    print(type, full_type, value)
    verbose_("Unsupported type '{}'".format(type))
    return value

def make_keypair():
    (secret_key, public_key) = core.make_keypair()
    public_key = '0x' + public_key
    return (secret_key, public_key)

def colorize(color, text):
    if sys.stdout.isatty():
        return color + text + BColors.ENDC
    else:
        return text

def eq(v1, v2, dismiss = False, msg = None, xtra = ""):
    if v1 == v2:
        return True
    else:
        if msg is None:
            msg = ''
        else:
            msg = msg + ' '
        print(msg + colorize(BColors.FAIL, "exp: {}, got: {}".format(v1, v2)) + xtra)
        return True if dismiss else False

def set_tests_path(path):
    global G_TESTS_PATH
    G_TESTS_PATH = path

def str2bytes(s: str) -> str:
    ss = str(binascii.hexlify(s.encode()))[1:]
    return ss.replace("'", "")

def bytes2str(b: str) -> str:
    return binascii.unhexlify(b).decode('utf-8')

def make_secret_token(n):
    return '0x' + secrets.token_hex(n)

def fix_uint256(s):
    assert s[0:2] == '0x', "Expected hexadecimal, got {}".format(s)
    t = s[2:]
    if len(t) < 64:
        s = '0x' + ('0' * (64-len(t))) + t
    return s

def is_method_call(msg, method):
    return msg['type'] == 'call' and msg['method'] == method

def dump_struct_str(struct):
    return json.dumps(struct, indent = 2);

def dump_struct(struct, compact = False):
    if compact:
        print(json.dumps(struct))
    else:
        print(dump_struct_str(struct))

def load_tvc(fn):
    bytes = open(fn, 'rb').read(1_000_000)
    return base64.b64encode(bytes).decode('utf-8')

def grams(n):
    return '{:.3f}'.format(n / GRAM).replace('.000', '')

def ensure_balance(expected, got, dismiss = False, epsilon = 0, msg = None):
    diff = got - int(expected)
    if abs(diff) <= epsilon:
        return
    xtra = ", diff = {}g ({})".format(grams(diff), diff)
    assert eq(int(expected), got, xtra = xtra, dismiss = dismiss, msg = msg)


#########################################################################################################

def dump_js_data():
    all_runs = get_all_runs()
    msgs = get_all_messages()
    with open('msg_data.js', 'w') as f:
        print('var allMessages = ' + dump_struct_str(msgs) + ';', file = f)
        print('var nicknames = ' + dump_struct_str(NICKNAMES) + ';', file = f)
        print('var allRuns = ' + dump_struct_str(all_runs) + ';', file = f)

def get_all_runs():
    return json.loads(core.get_all_runs())

def get_all_messages():
    def filter(msg):
        # TODO: support getters/answers
        return msg['type'] in ['call', 'external_call', 'empty', 'event', 'unknown']
    msgs = json.loads(core.get_all_messages())
    return [m for m in msgs if filter(m)]

#########################################################################################################

# TODO: is it needed here?
class BalanceWatcher:
    def __init__(self, contract):
        self.contract_  = contract
        self.balance_   = contract.balance()
        self.epsilon_   = 2
    def ensure_change(self, expected_diff):
        cur_balance     = self.contract_.balance()
        prev_balance    = self.balance_
        ensure_balance(prev_balance + expected_diff, cur_balance, epsilon = self.epsilon_)
        self.balance_   = cur_balance


#########################################################################################################

class ContractWrapper:
    def __init__(self, name, address, nickname = None, just_deployed = False):
        # self.name_ = name
        self.address_ = address
        name = G_TESTS_PATH + name
        if not just_deployed:
            if G_VERBOSE:
                print(colorize(BColors.OKBLUE, 'Creating wrapper for ' + name))
            core.set_contract_abi(self.address(), name + '.abi.json')

        # Load ABI
        self.abi_ = json.loads(open(name + '.abi.json').read())

    def balance(self):
        return core.get_balance(self.address())

    def address(self):
        return self.address_

    def ensure_balance(self, v, dismiss = False):
        # TODO: is this method needed here?
        ensure_balance(v, self.balance(), dismiss)

    def call_getter_raw(self, method, params = dict(), private_key = None):
        # TODO: do we need private_key for getters?
        assert isinstance(method, str)
        assert isinstance(params, dict)
        # print("getter: {} {}".format(method, params))
        (ec, actions, gas) = core.call_contract(self.address(), method, True, json.dumps(params), private_key)
        # print(actions)
        assert eq(0, ec)
        assert eq(1, len(actions)), "len(actions) == 1"
        return json.loads(actions[0])['params']

    def find_getter_output_types(self, method):
        for rec in self.abi_['functions']:
            if rec['name'] == method:
                return rec['outputs']
        assert False

    def find_getter_output_type(self, method, key):
        types = self.find_getter_output_types(method)
        for t in types:
            if t['name'] == key:
                return t
        assert False

    def call_getter(self,
        method,
        params = dict(),
        key = None,
        private_key = None,
        decode_ints = True,
        decode_tuples = True,
    ):
        # TODO: do we need private_key for getters?

        values = self.call_getter_raw(method, params, private_key)
        keys = list(values.keys())

        if key is None and len(keys) == 1:
            key = keys[0]

        if key is None:
            types = self.find_getter_output_types(method)
            res = {}
            res2 = []
            for t in types:
                n = t['name']
                v = decode_json_value(values[n], t, decode_ints)
                res[n] = v
                res2.append(v)
            if decode_tuples and types[0]['name'] == 'value0':
                return tuple(res2)
            else:
                return res

        assert key is not None
        assert key in values, colorize(BColors.FAIL, "No '{}' in {}".format(key, values))

        value     = values[key]
        full_type = self.find_getter_output_type(method, key)

        return decode_json_value(value, full_type, decode_ints)

    def call_method(self, method, params = dict(), private_key = None):
        # TODO: check param types. In particular, that `private_key` looks correct.
        #       Or introduce special type for keys...
        assert isinstance(params, dict)
        if G_VERBOSE:
            print(colorize(BColors.OKGREEN, "{} {}".format(method,json.dumps(params))))
        try:
            result = core.call_contract(self.address(), method, False, json.dumps(params), private_key)
        except:
            print(json.dumps(params))
            raise

        process_actions(result)

    def call_method_signed(self, method, params = dict()):
        self.call_method(method, params, private_key = self.private_key_)

    def ticktock(self, is_tock):
        if G_VERBOSE:
            print('ticktock {}'.format(addr_to_str(self.address())))
        return process_actions(core.call_ticktock(self.address(), is_tock))

    def create_keypair(self):
        (self.private_key_, self.public_key_) = make_keypair()

class BaseContract(ContractWrapper):
    def __init__(self,
        name,
        ctor_params,
        wc = 0,
        address = None,
        override_address = None,
        pubkey = None,
        balance = 100 * GRAM,
        nickname = None,
    ):
        full_name = G_TESTS_PATH + name
        just_deployed = False
        if address is None:
            if G_VERBOSE:
                print(colorize(BColors.OKBLUE, "Deploying " + full_name))
            if pubkey is not None:
                assert pubkey[0:2] == '0x'
                pubkey = pubkey.replace('0x', '')
            address = core.deploy_contract(
                full_name + '.tvc',
                full_name + '.abi.json',
                json.dumps(ctor_params) if ctor_params is not None else None,
                pubkey,
                wc,
                override_address,
                balance,
            )
            just_deployed = True
        super(BaseContract, self).__init__(name, address, just_deployed = just_deployed)
        if nickname is not None:
            register_nickname(self.address(), nickname)

