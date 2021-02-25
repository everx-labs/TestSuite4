"""
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
"""

__version__ = '0.1.2'

import sys
import base64, binascii
import secrets
import json
import re
import copy
import os.path
import importlib
from glob import glob

PACKAGE_DIR = os.path.basename(os.path.dirname(__file__))
CORE = '.' + sys.platform + '.linker_lib'

try:
    core = importlib.import_module(CORE, PACKAGE_DIR)
except ImportError as err:
    print('Error: {}'.format(err))
    exit()
except:
    print('Unsupported platform:', sys.platform)
    exit()

QUEUE           = []
EVENTS          = []
ALL_MESSAGES    = []
NICKNAMES       = dict()

GRAM            = 1_000_000_000
EMPTY_CELL      = 'te6ccgEBAQEAAgAAAA=='

G_TESTS_PATH    = 'contracts/'

G_VERBOSE           = False
G_DUMP_MESSAGES     = False
G_STOP_AT_CRASH     = True
G_SHOW_EVENTS       = False
G_MSG_FILTER        = None
G_WARN_ON_UNEXPECTED_ANSWERS = False

def version():
    return __version__


class BColors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def green(msg):     return colorize(BColors.OKGREEN, str(msg))
def blue(msg):      return colorize(BColors.OKBLUE,  str(msg))
def red(msg):       return colorize(BColors.FAIL,    str(msg))
def yellow(msg):    return colorize(BColors.WARNING, str(msg))
def white(msg):     return colorize(BColors.BOLD,    str(msg))


class Msg:
    def __init__(self, data):
        assert isinstance(data, dict)
        # print(data)
        self.data       = data
        self.id         = data['id']
        if 'src' in data:
            self.src    = Address(data['src'])
        self.dst        = Address(data['dst'])
        self.type       = data['msg_type']
        self.timestamp  = data['timestamp']
        self.log_str    = data['log_str']

        if self.is_event():
            self.event  = data['name']

        if self.is_call() or self.is_answer():
            self.method = data['name']

        if not self.is_type('empty', 'unknown'):
            self.params  = data['params']

        self.value = None
        if not self.is_type('event', 'answer', 'external_call', 'call_getter'):
            self.value   = data['value']
            self.bounced = data['bounced']

    def is_type(self, type1, type2 = None, type3 = None, type4 = None, type5 = None):
        return self.type in [type1, type2, type3, type4, type5]
    def is_type_in(self, types):
        return self.type in types
    def is_answer(self):
        return self.is_type('answer')
    def is_call(self, method = None):
        return self.is_type('call') and (method is None or self.method == method)
    def is_empty(self):
        return self.is_type('empty')
    def is_event(self, e = None, src = None):
        if self.is_type('event') and (e is None or self.event == e):
            if src is None or eq(src, self.src, msg = 'event.src:'):
                return True
        return False
    def is_unknown(self):
        return self.type == 'unknown'
    def dump_data(self):
        dump_struct(self.data)
    def __str__(self):
        return dump_struct_str(self.data)

class Address:
    def __init__(self, addr):
        if addr is None:
            addr = ''
        assert isinstance(addr, str), "{}".format(addr)
        # TODO: check that it is a correct address string
        self.addr_ = addr
    def __str__(self):
        # used by print()
        return 'Addr({})'.format(self.addr_)
    def __eq__(self, other):
        ensure_address(other)
        return self.str() == other.str()
    def str(self):
        return self.addr_
    def empty(self):
        return self.str() == ''
    def is_none(self):
        return self.str() == ''
    def fix_wc(self):
        assert eq(':', self.addr_[0])
        self.addr_ = '0' + self.addr_
        return self

def ensure_address(addr):
    assert isinstance(addr, Address), red('Expected Address got {}'.format(addr))

class JsonEncoder(json.JSONEncoder):
    def default(self, o):
        # verbose_(o)
        if isinstance(o, Address):
            return o.str()
        else:
            assert False


def _json_dumps(j):
    return json.dumps(j, cls = JsonEncoder)


class ExecutionResult:
    def __init__(self, result):
        (ec, actions, gas, err) = result
        self.exit_code = ec
        self.actions = actions
        self.gas_used = gas
        self.error = err


def set_verbose(f):
    global G_VERBOSE
    G_VERBOSE = f

def set_stop_at_crash(f):
    global G_STOP_AT_CRASH
    G_STOP_AT_CRASH = f

def verbose_(msg):
    verbose(msg, show_always = True, color_red = True)

def verbose(msg, show_always = False, color_red = False):
    if G_VERBOSE or show_always:
        if color_red:
            msg = red(str(msg))
        print(msg)

def prettify_dict(d, max_str_len = 67):
    nd = {}
    for k, v in d.items():
        if isinstance(v, dict):
            nd[k] = prettify_dict(v, max_str_len = max_str_len)
        elif isinstance(v, str):
            nd[k] = v if len(v) <= max_str_len else v[:max_str_len] + '...'
        elif isinstance(v, Address):
            nd[k] = _format_addr(v, compact = False)
        else:
            nd[k] = v

    return nd

def process_actions(result: ExecutionResult, expect_ec = 0):
    assert isinstance(result, ExecutionResult)
    ec = result.exit_code

    if G_VERBOSE:
        if ec != 0:
            print(yellow('exit_code = {}'.format(ec)))

    assert eq(expect_ec, ec, dismiss = not G_STOP_AT_CRASH)
    assert eq(None, result.error)

    for j in result.actions:
        msg = Msg(json.loads(j))
        # if G_VERBOSE:
            # print('process msg:', msg)
        if msg.is_event():
            if G_VERBOSE or G_SHOW_EVENTS:
                xtra = ''
                params = msg.params
                if msg.is_event('DebugEvent'):
                    xtra = ' ={}'.format(decode_int(params['x']))
                elif msg.is_event('LogEvent'):
                    params['comment'] = bytearray.fromhex(params['comment']).decode()
                print(yellow("{} {}{}".format(msg.event, params, xtra)))
            EVENTS.append(msg)
        else:
            if msg.is_unknown():
                if G_VERBOSE:
                    print(yellow("WARNING! Unknown message!"))
            elif G_WARN_ON_UNEXPECTED_ANSWERS and msg.is_answer():
                verbose_('WARNING! Unexpected answer!')
                continue
            else:
                assert msg.is_call() or msg.is_empty(), red('Unexpected type: {}'.format(msg.type))
            QUEUE.append(msg)
    return result.gas_used

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
        dump_message(msg)

def register_nickname(addr, nickname):
    ensure_address(addr)
    NICKNAMES[addr.str()] = nickname

def _format_addr(addr, compact = True):
    ensure_address(addr)
    if addr.empty():
        return 'addr_none'
    addr = addr.str()
    s = addr[:10]
    if addr in NICKNAMES:
        s = "{} ({})".format(NICKNAMES[addr], s)
    else:
        if not compact:
            s = 'Addr({})'.format(s)
    return s

def dump_message(msg: Msg):
    assert isinstance(msg, Msg)
    value = msg.value / GRAM if msg.value is not None else 'n/a'
    # print(msg)
    print(yellow('> {} -> {}'.format(
        _format_addr(msg.src),
        _format_addr(msg.dst)
    )) + ', v: {}'.format(value))
    if msg.is_type('call',  'empty'):
        # ttt = "{}".format(msg)
        if msg.is_call():
            ttt = "{} {}".format(green(msg.method), msg.params)
        else:
            ttt = green('<empty>')
        print("> " + ttt)
    elif msg.is_unknown():
        ttt = green('<unknown>')
        print("> " + ttt)
    else:
        assert msg.is_answer()
        ttt = '{}'.format(msg.data)
        print("> " + green(ttt))

def dispatch_one_message(expect_ec = 0):
    msg = pop_msg()
    ALL_MESSAGES.append(msg)
    # if is_method_call(msg, 'onRoundComplete'):
        # dump_message(msg)
    dump1 = G_VERBOSE or G_DUMP_MESSAGES
    dump2 = G_MSG_FILTER is not None and G_MSG_FILTER(msg.data)
    if dump1 or dump2:
        dump_message(msg)
    if msg.dst.empty():
        # TODO: a getter's reply. Add a test for that
        return
    # if msg['id'] == 2050: core.set_trace(True)
    result = core.dispatch_message(msg.id)
    result = ExecutionResult(result)
    gas = process_actions(result, expect_ec)
    # if msg['id'] == 2050: quit()
    return gas

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

def decode_json_value(value, full_type, decode_ints, dont_decode_fields):
    type = full_type['type']

    if re.match(r'^(u)?int\d+$', type):
        return decode_int(value) if decode_ints else value

    if type[-2:] == '[]':
        type2 = copy.deepcopy(full_type)
        type2['type'] = type[:-2]
        res = []
        for v in value:
            res.append(decode_json_value(v, type2, decode_ints, dont_decode_fields))
        return res

    if type == 'bool':
        return bool(value)

    if type == 'address':
        return Address(value)

    if type in ['cell', 'bytes']:
        return value

    if type == 'tuple':
        assert isinstance(value, dict)
        res = {}
        for c in full_type['components']:
            field = c['name']
            if field in dont_decode_fields:
                res[field] = value[field]
            else:
                res[field] = decode_json_value(value[field], c, decode_ints, dont_decode_fields)
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

def eq(v1, v2, dismiss = False, msg = None, xtra = ''):
    if v1 == v2:
        return True
    else:
        if msg is None:
            msg = ''
        else:
            msg = msg + ' '
        print(msg + red('exp: {}, got: {}.'.format(v1, v2)) + xtra)
        return True if dismiss else False

def set_tests_path(path):
    global G_TESTS_PATH
    G_TESTS_PATH = path

def str2bytes(s: str) -> str:
    assert isinstance(s, str), 'Expected string got {}'.format(s)
    ss = str(binascii.hexlify(s.encode()))[1:]
    return ss.replace("'", "")

def bytes2str(b: str) -> str:
    return binascii.unhexlify(b).decode('utf-8')

def make_secret_token(n):
    return '0x' + secrets.token_hex(n)

def fix_uint256(s):
    assert s[0:2] == '0x', 'Expected hexadecimal, got {}'.format(s)
    t = s[2:]
    if len(t) < 64:
        s = '0x' + ('0' * (64-len(t))) + t
    return s

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

def register_abi(contract_name):
    fn = G_TESTS_PATH + contract_name + '.abi.json'
    if G_VERBOSE:
        print(blue("Loading ABI " + fn))
    core.set_contract_abi(None, fn)

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
        msg = Msg(msg)
        # TODO: support getters/answers
        assert isinstance(msg, Msg), "{}".format(msg)
        return msg.is_type_in(['call', 'external_call', 'empty', 'event', 'unknown', 'log'])
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

def get_balance(addr):
    ensure_address(addr)
    return core.get_balance(addr.str())

class ContractWrapper:
    def __init__(self, name, address, nickname = None, just_deployed = False):
        # self.name_ = name
        ensure_address(address)
        self.addr_ = address
        name = G_TESTS_PATH + name
        if not just_deployed:
            if G_VERBOSE:
                print(colorize(BColors.OKBLUE, 'Creating wrapper for ' + name))
            core.set_contract_abi(self.address().str(), name + '.abi.json')

        # Load ABI
        self.abi_ = json.loads(open(name + '.abi.json').read())

    def balance(self):
        return get_balance(self.address())

    def address(self):
        return self.addr_

    def addr(self):
        return self.addr_

    def ensure_balance(self, v, dismiss = False):
        # TODO: is this method needed here?
        ensure_balance(v, self.balance(), dismiss)

    def call_getter_raw(self, method, params = dict(), private_key = None):
        if G_VERBOSE:
            print('getter: {}'.format(green(method)))   # TODO!: print full info
        # TODO: do we need private_key for getters?
        assert isinstance(method, str)
        assert isinstance(params, dict)
        # print("getter: {} {}".format(method, params))
        result = core.call_contract(
            self.address().str(),
            method,
            True,   # is_getter
            _json_dumps(params),
            private_key
        )
        result = ExecutionResult(result)
        assert eq(None, result.error)
        # print(actions)
        assert eq(0, result.exit_code)
        assert eq(1, len(result.actions)), "len(actions) == 1"
        msg = Msg(json.loads(result.actions[0]))
        assert msg.is_answer()
        assert eq(method, msg.method)
        return msg.params

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
        dont_decode_fields = [],
    ):

        values = self.call_getter_raw(method, params, private_key)
        keys = list(values.keys())

        # TODO!: move decoding to function
        if key is None and len(keys) == 1:
            key = keys[0]

        if key is None:
            return self._make_tuple_result(method, values, decode_ints, decode_tuples, dont_decode_fields)

        assert key is not None
        assert key in values, red("No '{}' in {}".format(key, values))

        value     = values[key]
        full_type = self.find_getter_output_type(method, key)

        return decode_json_value(value, full_type, decode_ints, dont_decode_fields)

    def decode_event(self, event_msg, dont_decode_fields = []):
        assert isinstance(event_msg, Msg), '{}'.format(event_msg)

        values      =   event_msg.data['params']
        event_name  =   event_msg.event
        event_def   =   self.find_event_def(event_name)

        assert event_def is not None, red('Cannot find event: {}'.format(event_name))

        # TODO!!: copy/paste - refactor!
        res = {}
        for type in event_def['inputs']:
            # TODO!: Add class for Type
            name  = type['name']
            value = values[name]
            if not name in dont_decode_fields:
                decode_ints = True
                value = decode_json_value(value, type, decode_ints, dont_decode_fields)
            res[name] = value

        return res

    def dump_event_type(self, msg):
        assert msg.is_event()
        dump_struct(self.find_event_def(msg.event))

    def find_event_def(self, event_name):
        assert isinstance(event_name, str)
        for event_def in self.abi_['events']:
            if event_def['name'] == event_name:
                return event_def
        return None

    def _make_tuple_result(self, method, values, decode_ints, decode_tuples, dont_decode_fields):
        types = self.find_getter_output_types(method)
        res_dict = {}
        res_arr  = []
        for type in types:
            # TODO!: Add class for Type
            name  = type['name']
            value = decode_json_value(values[name], type, decode_ints, dont_decode_fields)
            res_dict[name] = value
            res_arr.append(value)
        if decode_tuples and types[0]['name'] == 'value0':
            return tuple(res_arr)
        else:
            return res_dict

    def call_method(self, method, params = dict(), private_key = None, expect_ec = 0):
        # TODO: check param types. In particular, that `private_key` looks correct.
        #       Or introduce special type for keys...
        assert isinstance(params, dict)
        if G_VERBOSE:
            print(green("{} {}".format(method, prettify_dict(params))))
        try:
            result = core.call_contract(
                self.address().str(),
                method,
                False, # is_getter
                _json_dumps(params),
                private_key,
            )
            result = ExecutionResult(result)
        except:
            print(_json_dumps(params))
            raise

        if result.error == 'no_accept':
            verbose_('WARNING! No ACCEPT in contract')
        else:
            process_actions(result, expect_ec)

    def call_method_signed(self, method, params = dict(), expect_ec = 0):
        self.call_method(method, params, private_key = self.private_key_, expect_ec = expect_ec)

    def ticktock(self, is_tock):
        if G_VERBOSE:
            print('ticktock {}'.format(_format_addr(self.address())))
        result = core.call_ticktock(self.address().str(), is_tock);
        result = ExecutionResult(result)
        return process_actions(result)

    def create_keypair(self):
        (self.private_key_, self.public_key_) = make_keypair()

    def keypair(self):
        return (self.private_key_, self.public_key_);

class BaseContract(ContractWrapper):
    def __init__(self,
        name,
        ctor_params,
        wc = 0,
        address             = None,
        override_address    = None,
        pubkey              = None,
        private_key         = None,
        balance             = 100 * GRAM,
        nickname            = None,
    ):
        full_name = G_TESTS_PATH + name
        just_deployed = False
        if override_address is not None:
            ensure_address(override_address)
            override_address = override_address.str()
        if address is None:
            if G_VERBOSE:
                print(blue("Deploying " + full_name))
            if pubkey is not None:
                assert pubkey[0:2] == '0x'
                pubkey = pubkey.replace('0x', '')
            address = core.deploy_contract(
                full_name + '.tvc',
                full_name + '.abi.json',
                _json_dumps(ctor_params) if ctor_params is not None else None,
                pubkey,
                private_key,
                wc,
                override_address,
                balance,
            )
            address = Address(address)
            just_deployed = True
        super(BaseContract, self).__init__(name, address, just_deployed = just_deployed)
        if nickname is not None:
            register_nickname(self.address(), nickname)

