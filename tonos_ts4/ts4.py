"""
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
"""

__version__ = '0.2.1'

import sys
import base64
import secrets
import json
import numbers
import re
import copy
import os.path
import importlib
from glob import glob

from .util import *
from .address import *

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
G_STOP_ON_NO_ACCEPT = True

G_ABI_FIXER     = None


def version():
    """Returns current version of TestSuite4.

    :return: Current version
    :rtype: str
    """
    return __version__

def reset_all():
    """Resets entire TS4 state. Useful when starting new testset.
    """
    global QUEUE, EVENTS, ALL_MESSAGES, NICKNAMES
    core.reset_all()
    QUEUE           = []
    EVENTS          = []
    ALL_MESSAGES    = []
    NICKNAMES       = dict()


class Msg:
    """The :class:`Msg <Msg>` object, which represents a blockchain message.

    :ivar str id: Message ID
    :ivar Address src: Source address
    :ivar Address dst: Destionation address
    :ivar str type: Type of message (`empty`, `unknown`, `bounced`, `event`, `answer`, `external_call`, `call_getter`)
    :ivar value: The value attached to an internal message
    :ivar str method: Called method/getter
    :ivar dict params: A dictionary with parameters of the called method/getter
    """
    def __init__(self, data):
        """Constructs Msg object.

        :param dict data: Dictionary with message data
        """
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

        if self.is_unknown() and self.bounced:
            self.type = 'bounced'


    def is_type(self, type1, type2 = None, type3 = None, type4 = None, type5 = None):
        """Checks if a given message has one of requested types.

        :param str type1: A name of desired type
        :param str type2: optional - A name of desired type
        :param str type3: optional - A name of desired type
        :param str type4: optional - A name of desired type
        :param str type5: optional - A name of desired type
        :return: Result of check
        :rtype: bool
        """
        return self.type in [type1, type2, type3, type4, type5]

    def is_type_in(self, types):
        """Checks if a given message is one of requested types.

        :param list types: A list of strings of type names
        :return: Result of check
        :rtype: bool
        """
        return self.type in types

    def is_answer(self, method = None):
        """Checks if a given message is of an *answer* type.

        :param str method: optional - Desired name of a function answered
        :return: Result of check
        :rtype: bool
        """
        return self.is_type('answer') and (method is None or self.method == method)

    def is_call(self, method = None):
        """Checks if a given message is of a *call* type.

        :param str method: optional - Desired name of a function called
        :return: Result of check
        :rtype: bool
        """
        return self.is_type('call') and (method is None or self.method == method)

    def is_empty(self):
        """Checks if a given message is of an *empty* type.

        :return: Result of check
        :rtype: bool
        """
        return self.is_type('empty')

    def is_event(self, name = None, src = None, dst = None):
        """Checks if a given message is of an *event* type.

        :param str name: Desired name of event to check
        :param str src: Desired source address of event to check
        :param str dst: Desired destination address of event to check
        :return: Result of check
        :rtype: bool
        """
        if self.is_type('event') and (name is None or self.event == name):
            if src is None or eq(src, self.src, msg = 'event.src:'):
                if dst is None or eq(dst, self.dst, msg = 'event.dst:'):
                    return True
        return False

    def is_unknown(self):
        """Checks if a current message is of an *unknown* type.

        :return: Result of check
        :rtype: bool
        """
        return self.type == 'unknown'

    def is_bounced(self):
        """Checks if a current message is bounced.

        :return: Result of check
        :rtype: bool
        """
        return self.type == 'bounced'

    def dump_data(self):
        """Dumps message data.
        """
        dump_struct(self.data)

    def __str__(self):
        return dump_struct_str(self.data)

class Bytes():
    """The :class:`Bytes <Bytes>` object, which represents bytes type.
    """
    def __init__(self, value):
        """Constructs :class:`Bytes <Bytes>` object.

        :param str value: A hexadecimal string representing array of bytes
        """
        self.raw_ = value

    def __str__(self):
        return bytes2str(self.raw_)

    def __repr__(self):
        return "Bytes('{}')".format(self.raw_)

    def __eq__(self, other):
        if isinstance(other, Bytes):
            return self.raw_ == other.raw_
        elif isinstance(other, str):
            return self.raw_ == str2bytes(other)
        return False

class Cell():
    """The :class:`Cell <Cell>` object, which represents a cell.
    """
    def __init__(self, value):
        """Constructs :class:`Cell <Cell>` object.

        :param str value: A base64 string representing the cell
        """
        self.raw_ = value

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "Cell('{}')".format(self.raw_)

    def __eq__(self, other):
        if isinstance(other, Cell):
            return self.raw_ == other.raw_
        return False

    def is_empty(self):
        """Checks if the cell is empty.

        :return: Result of check
        :rtype: bool
        """
        return EMPTY_CELL == self.raw_

class AbiType:
    def __init__(self, type):
        assert isinstance(type, dict)
        self.raw_ = type
        self.name = type['name']
        self.type = type['type']
        if self.type == 'tuple':
            self.components = [AbiType(t) for t in self.raw_['components']]
        self.dont_decode = 'dont_decode' in self.raw_

    def is_array(self):
        return self.type[-2:] == '[]'

    def is_int(self):
        return re.match(r'^(u)?int\d+$', self.type)

    def remove_array(self):
        assert self.is_array()
        type2 = copy.deepcopy(self.raw_)
        type2['type'] = self.type[:-2]
        return AbiType(type2)

class JsonEncoder(json.JSONEncoder):
    def default(self, o):
        # verbose_(o)
        if isinstance(o, Address):
            return o.str()
        elif isinstance(o, Bytes):
            return o.raw_
        else:
            assert False

class Params:
    def __init__(self, params):
        assert isinstance(params, dict), '{}'.format(params)
        self.__raw__ = params
        self.transform(params)

    def transform(self, params):
        if isinstance(params, dict):
            for key in params:
                value = params[key]
                if isinstance(value, dict):
                    value = Params(value)
                if isinstance(value, Bytes):
                    value = str(value)
                if isinstance(value, list):
                    value = [self.tr(x) for x in value]
                setattr(self, key, value)

    def tr(self, x):
        if isinstance(x, dict):
            return Params(x)
        return x

def make_params(data):
    if isinstance(data, dict):
        return Params(data)
    if isinstance(data, list):
        return [make_params(x) for x in data]
    return data


def fix_large_ints(v):
    def transform_value(v):
        if isinstance(v, Address):
            return v.str()
        if isinstance(v, Bytes):
            return v.raw_
        if isinstance(v, Cell):
            return v.raw_
        if isinstance(v, int):
            if v > 0xffffFFFFffffFFFF:
                v = hex(v)
            return v
        return v
    return transform_structure(v, transform_value)

def _json_dumps(j):
    j = fix_large_ints(j)
    return json.dumps(j) #, cls = JsonEncoder)


class ExecutionResult:
    def __init__(self, result):
        (ec, actions, gas, err) = result
        self.exit_code  = ec
        self.actions    = actions
        self.gas_used   = gas
        self.error      = err


def init(path, verbose = False, time = None):
    """Initializes the library.

    :param str path: Directory where the artifacts of the used contracts are located
    :param bool verbose: Toggle to print additional execution info
    :param num time: Time in seconds (unixtime).
        TS4 uses either real-clock or virtual time. Once you set time you switch
        to the virtual time mode.
    """
    script_path = os.path.dirname(sys.argv[0])
    path = os.path.join(
        script_path if not os.path.isabs(path) else '',
        path
    )
    set_tests_path(path)
    set_verbose(verbose)
    if time is not None:
        core.set_now(time)

def set_verbose(verbose = True):
    """Sets verbosity mode. When verbosity is enabled all the messages
    and some additional stuff is printed to console. Useful for debugging.

    :param bool verbose: Toggle to print additional execution info
    """
    global G_VERBOSE
    G_VERBOSE = verbose

def set_stop_at_crash(do_stop):
    """Sets `G_STOP_AT_CRASH` global flag.
    By default the system stops at the first exception (unexpected exit code) raised by a contract.
    Use `expect_ec` parameter if you expected an exception in a given call.
    When `G_STOP_AT_CRASH` is disabled the system only warns user and does not stop.

    :param bool do_stop: Toggle for crash stop mode
    """
    global G_STOP_AT_CRASH
    G_STOP_AT_CRASH = do_stop

def verbose_(msg):
    """Helper function to show text colored red in console. Useful when debugging.

    :param str msg: String message to be printed
    """
    verbose(msg, show_always = True, color_red = True)

def verbose(msg, show_always = False, color_red = False):
    """Helper function to print text message in verbose mode.

    :param str msg: String message to be printed
    :param bool show_always: When enabled forces to show message even when verbose mode is off
    :param bool color_red: Emphasize the message in color
    """
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

    answer = None

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
            # not event
            if msg.is_unknown():
                if G_VERBOSE:
                    print(yellow('WARNING! Unknown message!'))
            elif msg.is_bounced():
                pass
            elif msg.is_answer():
                # We expect only one answer
                assert answer is None
                answer = msg
                continue
            else:
                assert msg.is_call() or msg.is_empty(), red('Unexpected type: {}'.format(msg.type))
            QUEUE.append(msg)
    return (result.gas_used, answer)

def pop_msg():
    """Removes first message from the unprocessed messages queue and returns it.

    :return: Object
    :rtype: Msg
    """
    assert len(QUEUE) > 0
    return QUEUE.pop(0)

def peek_msg():
    """Returns first message from the unprocessed messages queue and leaves the queue unchanged.

    :return: Object
    :rtype: Msg
    """
    assert len(QUEUE) > 0
    return QUEUE[0]

def pop_event():
    """Removes first event from the unprocessed events queue and returns it.

    :return: Object
    :rtype: Msg
    """
    assert len(EVENTS) > 0
    return EVENTS.pop(0)

def peek_event():
    """Returns first event from the unprocessed events queue and leaves the queue unchanged.

    :return: Object
    :rtype: Msg
    """
    assert len(EVENTS) > 0
    return EVENTS[0]

def queue_length():
    """Returns the size of the unprocessed messages queue.

    :return: Queue length
    :rtype: num
    """
    return len(QUEUE)

def ensure_queue_empty():
    """Checks if the unprocessed messages queue is empty
    and raises an error if it is not. Useful for debugging.
    """
    assert eq(0, len(QUEUE), msg = ('ensure_queue_empty() -'))

def dump_queue():
    """Dumps messages queue to the console.
    """
    print(colorize(BColors.BOLD, "QUEUE:"))
    for i in range(len(QUEUE)):
        print("  {}: {}".format(i, QUEUE[i]))

def dispatch_messages(callback = None):
    """Dispatches all messages in the queue one by one until the queue becomes empty.

    :param callback: Callback to be called to each processed message.
        If callback returns False the given message is skipped.
    """
    while len(QUEUE) > 0:
        if callback is not None and callback(peek_msg()) == False:
            pop_msg()
            continue
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
    """Registers human readable name for a given address.
    This name is used in verbose output.

    :param Address addr: An address of the account
    :param str nickname: A nickname for the account
    """
    ensure_address(addr)
    NICKNAMES[addr.str()] = nickname

def _format_addr(addr, compact = True):
    ensure_address(addr)
    if addr.is_none():
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
    if msg.is_type('call',  'empty', 'bounced'):
        # ttt = "{}".format(msg)
        if msg.is_call():
            ttt = "{} {}".format(green(msg.method), msg.params)
        elif msg.is_bounced():
            ttt = green('<bounced>')
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
    """Takes first unprocessed message from the queue and dispatches it.
    Use `expect_ec` parameter if you expect non-zero exit code.

    :param num expect_ec: Expected exit code
    :return: The amount of gas spent on the execution of the transaction
    :rtype: num
    """
    msg = pop_msg()
    ALL_MESSAGES.append(msg)
    # if is_method_call(msg, 'onRoundComplete'):
        # dump_message(msg)
    dump1 = G_VERBOSE or G_DUMP_MESSAGES
    dump2 = G_MSG_FILTER is not None and G_MSG_FILTER(msg.data)
    if dump1 or dump2:
        dump_message(msg)
    if msg.dst.is_none():
        # TODO: a getter's reply. Add a test for that
        return
    result = core.dispatch_message(msg.id)
    result = ExecutionResult(result)
    gas, answer = process_actions(result, expect_ec)
    assert answer is None
    return gas

def set_msg_filter(filter):
    global G_MSG_FILTER
    if filter is True:  filter = lambda msg: True
    if filter is False: filter = None
    G_MSG_FILTER = filter

class DecodingParams:
    def __init__(self,
        decode_ints = True,
        decode_tuples = True,
        dont_decode_fields = [],
    ):
        self.decode_ints        = decode_ints
        self.decode_tuples      = decode_tuples
        self.dont_decode_fields = dont_decode_fields

def decode_json_value(value, abi_type, params):
    assert isinstance(abi_type, AbiType)
    type = abi_type.type

    if abi_type.is_int():
        return decode_int(value) if params.decode_ints else value

    if abi_type.is_array():
        type2 = abi_type.remove_array()
        return [decode_json_value(v, type2, params) for v in value]

    if type == 'bool':
        return bool(value)

    if type == 'address':
        return Address(value)

    if type == 'cell':
        return Cell(value)

    if type == 'bytes':
        return Bytes(value)

    if type == 'tuple':
        assert isinstance(value, dict)
        res = {}
        for c in abi_type.components:
            field = c.name
            if c.dont_decode or field in params.dont_decode_fields:
                res[field] = value[field]
            else:
                res[field] = decode_json_value(value[field], c, params)
        return res

    print(type, abi_type, value)
    verbose_("Unsupported type '{}'".format(type))
    return value

def make_keypair():
    """Generates random keypair.

    :return: The key pair
    :rtype: (str, str)
    """
    (secret_key, public_key) = core.make_keypair()
    public_key = '0x' + public_key
    return (secret_key, public_key)

def set_tests_path(path):
    """Sets the directory where the system will look for compiled contracts.

    :param str path: The path to contract artifacts
    """
    global G_TESTS_PATH
    G_TESTS_PATH = path

def dump_struct_str(struct):
    return json.dumps(struct, indent = 2, cls = JsonEncoder)

def dump_struct(struct, compact = False):
    if compact:
        print(json.dumps(struct))
    else:
        print(dump_struct_str(struct))

def _make_path(name, ext):
    fn = os.path.join(G_TESTS_PATH, name)
    if not fn.endswith(ext):
        fn += ext
    return fn

def load_tvc(fn):
    """Loads a compiled contract image (`.tvc`) with a given name.

    :param str fn: The file name
    :return: Base64-encoded tvc-file contents
    :rtype: str
    """
    fn = _make_path(fn, '.tvc')
    with open(fn, 'rb') as fp:
        return base64.b64encode(fp.read(1_000_000)).decode('utf-8')

def load_code_cell(fn):
    """Loads contract code cell from a compiled contract image with a given name.
    Returns cell encoded to string.

    :param str fn: The file name
    :return: Base64-encoded string
    :rtype: str
    """
    fn = _make_path(fn, '.tvc')
    return core.load_code_cell(fn)

def load_data_cell(fn):
    """Loads contract data cell from a compiled contract image with a given name.
    Returns cell encoded to string

    :param str fn: The file name
    :return: Base64-encoded string
    :rtype: str
    """
    fn = _make_path(fn, '.tvc')
    return core.load_data_cell(fn)

def grams(n):
    return '{:.3f}'.format(n / GRAM).replace('.000', '')

def ensure_balance(expected, got, dismiss = False, epsilon = 0, msg = None):
    """Checks the contract balance for exact match.
    In case of mismatch prints the difference in a convenient form.

    :param num expected: Expected balance value
    :param num got: Сurrent balance value
    :param bool dismiss: When False don't stop the execution in case of mismatch
    :param num epsilon: Allowed difference between requested and actual balances
    :param str msg: Optional message to print in case of mismatch
    """
    diff = got - int(expected)
    if abs(diff) <= epsilon:
        return
    xtra = ", diff = {}g ({})".format(grams(diff), diff)
    assert eq(int(expected), got, xtra = xtra, dismiss = dismiss, msg = msg)

def register_abi(contract_name):
    """Loads an ABI for a given contract without its construction.
    Useful when some contracts are deployed indirectly (i.e. from other contracts).

    :param str contract_name: The contract name the ABI of which should be uploaded
    """
    fn = _make_path(contract_name, '.abi.json')
    if G_VERBOSE:
        print(blue("Loading ABI " + fn))
    core.set_contract_abi(None, fn)

def set_contract_abi(contract, new_abi_name):
    """Sets new ABI for a given contract. Useful when contract code was upgraded.

    :param BaseContract contract: An instance of the contract where the ABI will be set
    :param str new_abi_name: Name of the file containing the ABI
    """
    assert isinstance(contract, BaseContract)
    fn = _make_path(new_abi_name, '.abi.json')
    core.set_contract_abi(contract.addr().str(), fn)
    with open(fn, 'rb') as fp:
        contract.abi_ = json.load(fp)

def sign_cell(cell, private_key):
    """Signs cell with a given key and returns signature.

    :param Cell value: Cell to be signed
    :param str private_key: Hexadecimal representation of 1024-bits long private key
    :return: Hexadecimal string representing resulting signature
    :rtype: str
    """
    assert isinstance(cell, Cell)
    assert isinstance(private_key, str)
    assert eq(128, len(private_key))
    # TODO: check that it is hexadecimal number
    return core.sign_cell(cell.raw_, private_key)

def set_config_param(index, value):
    """Sets global config parameter.

    :param num index: Parameter index
    :param Cell value: Cell object containing desired value.
    """
    assert isinstance(value, Cell)
    core.set_config_param(index, value.raw_)

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

def get_all_messages(show_all = False):
    def filter(msg):
        msg = Msg(msg)
        # TODO: support getters/answers
        assert isinstance(msg, Msg), "{}".format(msg)
        if show_all:
            return True
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

class AbiTraversalHelper:
    def __init__(self, abi_name, abi_json):
        self.name_ = abi_name
        self.json_ = abi_json

    def travel_fields(self, cb):
        for f in self.json_['functions']:
            self.recFunc(self.name_ + '.functions', f, cb)
        for e in self.json_['events']:
            self.recEvent(self.name_ + '.events', e, cb)

    def recFunc(self, path, json, cb):
        path = path + '.' + json['name']
        # print(path)
        for j in json['outputs']:
            self.recVar(path + '.outputs', j, cb)

    def recEvent(self, path, json, cb):
        path = path + '.' + json['name']
        # print(path)
        for j in json['inputs']:
            self.recVar(path + '.inputs', j, cb) # TODO: do we need inputs here?

    def recVar(self, path, json, cb):
        path = path + '.' + json['name']
        type = json['type']
        while type.endswith('[]'):
            type = type[:len(type)-2]
        # print(path, type)
        if type == 'tuple':
            for j in json['components']:
                self.recVar(path, j, cb)
        cb(path, json)

def fix_abi(name, abi, callback):
    """Travels through given ABI calling a callback function for each node

    :param str name: Contract name
    :param dict abi: Contract ABI
    :param callback: Transformation function called for each node
    """
    traveller = AbiTraversalHelper(name, abi)
    traveller.travel_fields(callback)


#########################################################################################################

def get_balance(addr):
    """Retrieves the balance of a given address.

    :param Address addr: The address of a contract
    :return: Current account balance
    :rtype: num
    """
    ensure_address(addr)
    return core.get_balance(addr.str())


class BaseContract:
    """The :class:`BaseContract <BaseContract>` object, which is responsible
    for deploying contracts and interaction with deployed contracts.
    """
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
        """Constructs :class:`BaseContract <BaseContract>` object.

        :param str name: Name used to load contract's bytecode and ABI
        :param dict ctor_params: Parameters for offchain constructor call
            If None, constructor is not called and can be called with
            separate `call_method()` call (onchain constructed)
        :param num wc: workchain_id to deploy contract to
        :param Address address: If this parameter is specified no new contract is created
            but instead a wrapper for an existing contract is created
        :param Address override_address: When specified this address will be used for deploying
            the contract. Otherwise the address is generated according to real blockchain rules
        :param str pubkey: Public key used in contract construction
        :param str private_key: Private key used to sign construction message
        :param num balance: Desired contract balance
        :param str nickname: Nickname of the contract used in verbose output
        """
        full_name = os.path.join(G_TESTS_PATH, name)
        just_deployed = False
        if override_address is not None:
            ensure_address(override_address)
            override_address = override_address.str()
        if address is None:
            if G_VERBOSE:
                print(blue('Deploying {} ({})'.format(full_name, nickname)))
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
        self._init2(name, address, just_deployed = just_deployed)
        if nickname is not None:
            register_nickname(self.address(), nickname)

    def _init2(self, name, address, nickname = None, just_deployed = False):
        self.name_ = name
        ensure_address(address)
        self.addr_ = address
        name = os.path.join(G_TESTS_PATH, name)
        if not just_deployed:
            if G_VERBOSE:
                print(colorize(BColors.OKBLUE, 'Creating wrapper for ' + name))
            core.set_contract_abi(self.address().str(), name + '.abi.json')

        # Load ABI
        with open(name + '.abi.json', 'rb') as fp:
            self.abi_ = json.load(fp)

        if G_ABI_FIXER is not None:
            fix_abi(self.name_, self.abi_, G_ABI_FIXER)

    def balance(self):
        """Retreives balance of a given contract.

        :return: Account balance
        :rtype: num
        """
        return get_balance(self.address())

    def address(self):
        """Returns address of a given contract.

        :return: Address of contract
        :rtype: Address
        """
        return self.addr_

    def addr(self):
        """Returns address of a given contract. Shorter version of `address()`.

        :return: Address of contract
        :rtype: Address
        """
        return self.addr_

    def ensure_balance(self, v, dismiss = False):
        # TODO: is this method needed here?
        ensure_balance(v, self.balance(), dismiss)

    def call_getter_raw(self, method, params = dict(), expect_ec = 0):
        """Calls a given getter and returns an answer in raw JSON format.

        :param str method: Name of a getter
        :param dict params: A dictionary with getter parameters
        :param num expect_ec: Expected exit code. Use non-zero value
            if you expect a getter to raise an exception
        :return: Message parameters
        :rtype: JSON
        """
        if G_VERBOSE:
            print('getter: {}'.format(green(method)))   # TODO: print full info
            # print("getter: {} {}".format(method, params))

        assert isinstance(method,    str)
        assert isinstance(params,    dict)
        assert isinstance(expect_ec, int)

        result = core.call_contract(
            self.addr().str(),
            method,
            True,   # is_getter
            False,  # is_debot
            _json_dumps(params),
            None,   # private_key
        )

        result = ExecutionResult(result)
        assert eq(None, result.error)
        # print(actions)
        assert eq(expect_ec, result.exit_code)

        if expect_ec != 0:
            return

        actions = [Msg(json.loads(a)) for a in result.actions]

        for msg in actions:
            if not msg.is_answer():
                raise Exception("Unexpected message type '{}' in getter output".format(msg.type))

        assert eq(1, len(result.actions)), 'len(actions) == 1'
        msg = Msg(json.loads(result.actions[0]))
        assert msg.is_answer(method)
        return msg.params

    def _find_getter_output_types(self, method):
        for rec in self.abi_['functions']:
            if rec['name'] == method:
                return [AbiType(t) for t in rec['outputs']]
        assert False

    def _find_getter_output_type(self, method, key):
        types = self._find_getter_output_types(method)
        for t in types:
            if t.name == key:
                return t
        assert False

    def call_getter(self,
        method,
        params = dict(),
        key = None,
        expect_ec = 0,
        decode = False,
        decode_ints = True,
        decode_tuples = True,
        dont_decode_fields = [],
    ):
        """Calls a given getter and decodes an answer.

        :param str method: Name of a getter
        :param dict params: A dictionary with getter parameters
        :param str key: (optional) If function returns tuple this parameter forces to return only one value under the desired key.
        :param num expect_ec: Expected exit code. Use non-zero value
            if you expect a getter to raise an exception
        :param list dont_decode_fields: A list of fields in answer that should not be decoded
        :return: A returned value in decoded form (exact type depends on the type of getter)
        :rtype: type
        """
        values = self.call_getter_raw(method, params, expect_ec)

        if expect_ec > 0:
            # TODO: ensure values is empty?
            return

        decoding_params = DecodingParams(decode_ints, decode_tuples, dont_decode_fields)
        answer = self._decode_answer(values, method, key, decoding_params)
        return make_params(answer) if decode else answer

    def _decode_answer(self,
        values,
        method,
        key,
        params,
    ):
        keys = list(values.keys())

        if key is None and len(keys) == 1:
            key = keys[0]

        if key is None:
            return self._make_tuple_result(method, values, params)

        assert key is not None
        assert key in values, red("No '{}' in {}".format(key, values))

        value     = values[key]
        abi_type = self._find_getter_output_type(method, key)

        return decode_json_value(value, abi_type, params)

    def decode_event(self, event_msg):
        """Experimental feature. Decodes event parameters

        :param Msg event_msg: An event message
        :return: Event parameters in decoded form
        :rtype: Params
        """
        assert isinstance(event_msg, Msg), '{}'.format(event_msg)

        values      =   event_msg.data['params']
        event_name  =   event_msg.event
        event_def   =   self._find_event_def(event_name)

        assert event_def is not None, red('Cannot find event: {}'.format(event_name))

        res = {}
        for type in event_def['inputs']:
            type = AbiType(type)
            name  = type.name
            value = values[name]
            if not type.dont_decode:
                value = decode_json_value(value, type, DecodingParams())
            res[name] = value

        return Params(res)

    def _dump_event_type(self, msg):
        assert msg.is_event()
        dump_struct(self._find_event_def(msg.event))

    def _find_event_def(self, event_name):
        assert isinstance(event_name, str)
        for event_def in self.abi_['events']:
            if event_def['name'] == event_name:
                return event_def
        return None

    def _make_tuple_result(self, method, values, params):
        types = self._find_getter_output_types(method)
        res_dict = {}
        res_arr  = []
        for type in types:
            value = decode_json_value(values[type.name], type, params)
            res_dict[type.name] = value
            res_arr.append(value)
        if params.decode_tuples and types[0].name == 'value0':
            return tuple(res_arr)
        else:
            return res_dict

    def call_method(self, method, params = dict(), private_key = None, expect_ec = 0, is_debot = False):
        """Calls a given method.

        :param str method: Name of the method to be called
        :param dict params: A dictionary with parameters for calling the contract function
        :param str private_key: A private key to be used to sign the message
        :param num expect_ec: Expected exit code. Use non-zero value
            if you expect a method to raise an exception
        :param bool is_debot: Enables special debot mode
        :return: Value in decoded form (if method returns something)
        :rtype: dict
        """
        # TODO: check param types. In particular, that `private_key` looks correct.
        #       Or introduce special type for keys...
        assert isinstance(params, dict)
        if G_VERBOSE:
            print(green("{} {}".format(method, prettify_dict(params))))
        try:
            result = core.call_contract(
                self.addr().str(),
                method,
                False, # is_getter
                is_debot,
                _json_dumps(params),
                private_key,
            )
            result = ExecutionResult(result)
        except:
            print(_json_dumps(params))
            raise

        if result.error == 'no_accept':
            severity = 'ERROR' if G_STOP_ON_NO_ACCEPT else 'WARNING'
            err_msg = '{}! No ACCEPT in the contract method `{}`'.format(severity, method)
            assert not G_STOP_ON_NO_ACCEPT, err_msg
            verbose_(err_msg)
        else:
            _gas, answer = process_actions(result, expect_ec)
            if answer is not None:
                assert answer.is_answer(method)
                key = None
                return self._decode_answer(answer.params, method, key, DecodingParams())

    def call_method_signed(self, method, params = dict(), expect_ec = 0):
        """Calls a given method using contract's private key.

        :param str method: Name of the method to be called
        :param dict params: A dictionary with parameters for calling the contract function
        :param num expect_ec: Expected exit code. Use non-zero value
            if you expect a method to raise an exception
        """
        self.call_method(method, params, private_key = self.private_key_, expect_ec = expect_ec)

    def ticktock(self, is_tock):
        """Simulates tick-tock call.

        :param bool is_tock: False for Tick and True for Tock
        :return: The amount of gas spent on the execution of the transaction
        :rtype: num
        """
        if G_VERBOSE:
            print('ticktock {}'.format(_format_addr(self.address())))
        result = core.call_ticktock(self.address().str(), is_tock)
        result = ExecutionResult(result)
        gas, answer = process_actions(result)
        assert answer is None
        return gas

    def create_keypair(self):
        """Creates new keypair and assigns it to the contract.
        """
        (self.private_key_, self.public_key_) = make_keypair()

    def keypair(self):
        """Returns keypair assigned to the contract.

        :return: Account keypair
        :rtype: (str, str)
        """
        return (self.private_key_, self.public_key_)
