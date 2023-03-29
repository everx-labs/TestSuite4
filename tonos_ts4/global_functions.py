"""
    This file is part of Ever OS.

    Ever OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2023 (c) EverX
"""

import os
import base64
import ed25519
import hashlib

from abi import *
from address import *
from globals import EVER
from util import *

def version() -> str:
    """Returns current version of TestSuite4.

    :return: Current version
    :rtype: str
    """
    return globals.version


def reset_all():
    """Resets entire TS state. Useful when starting new testset.
    """
    globals.core.reset_all()
    globals.QUEUE           = []
    globals.EVENTS          = []
    globals.ALL_MESSAGES    = []
    globals.NICKNAMES       = dict()

def set_tests_path(path):
    """Sets the directory where the system will look for compiled contracts.

    :param str path: The path to contract artifacts
    """
    globals.G_TESTS_PATH = path

def init(path, verbose = False, time = None, show_getters = False):
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
    globals.G_SHOW_GETTERS = show_getters
    if time is not None:
        globals.core.set_now(time)

def set_verbose(verbose = True):
    """Sets verbosity mode. When verbosity is enabled all the messages
    and some additional stuff is printed to console. Useful for debugging.

    :param bool verbose: Toggle to print additional execution info
    """
    globals.G_VERBOSE = verbose

def set_stop_at_crash(do_stop):
    """Sets `G_STOP_AT_CRASH` global flag.
    By default the system stops at the first exception (unexpected exit code) raised by a contract.
    Use `expect_ec` parameter if you expected an exception in a given call.
    When `G_STOP_AT_CRASH` is disabled the system only warns user and does not stop.

    :param bool do_stop: Toggle for crash stop mode
    """
    globals.G_STOP_AT_CRASH = do_stop

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
    if globals.G_VERBOSE or show_always:
        if color_red:
            msg = red(str(msg))
        print(msg)

def pop_msg() -> Msg:
    """Removes first message from the unprocessed messages globals.QUEUE and returns it.

    :return: Object
    :rtype: Msg
    """
    assert ne(0, len(globals.QUEUE), msg = "message queue is empty")
    return globals.QUEUE.pop(0)

def peek_msg():
    """Returns first message from the unprocessed messages globals.QUEUE and leaves the globals.QUEUE unchanged.

    :return: Object
    :rtype: Msg
    """
    return globals.QUEUE[0] if len(globals.QUEUE) != 0 else None

def pop_event():
    """Removes first event from the unprocessed events globals.QUEUE and returns it.

    :return: Object
    :rtype: Msg
    """
    assert ne(0, len(globals.EVENTS), msg = "event queue is empty")
    return globals.EVENTS.pop(0)

def peek_event():
    """Returns first event from the unprocessed events globals.QUEUE and leaves the globals.QUEUE unchanged.

    :return: Object
    :rtype: Msg
    """
    return globals.EVENTS[0] if len(globals.EVENTS) > 0 else None

def queue_length():
    """Returns the size of the unprocessed messages globals.QUEUE.

    :return: globals.QUEUE length
    :rtype: num
    """
    return len(globals.QUEUE)

def ensure_queue_empty():
    """Checks if the unprocessed messages globals.QUEUE is empty
    and raises an error if it is not. Useful for debugging.
    """
    assert eq(0, len(globals.QUEUE), msg = 'message queue is not empty')

def dump_queue():
    """Dumps messages globals.QUEUE to the console.
    """
    print(white("globals.QUEUE:")) # revise print
    for i in range(len(globals.QUEUE)):
        print("  {}: {}".format(i, globals.QUEUE[i]))

def set_msg_filter(filter):
    if filter is True:  filter = lambda msg: True
    if filter is False: filter = None
    globals.G_MSG_FILTER = filter

def register_nickname(addr, nickname):
    """Registers human readable name for a given address.
    This name is used in verbose output.

    :param Address addr: An address of the account
    :param str nickname: A nickname for the account
    """
    Address.ensure_address(addr)
    globals.NICKNAMES[addr.str()] = nickname

def ensure_address(addr):
    """Raises an error if a given object is not of :class:`Address <Address>` class.

    :param Address addr: Object of class Address
    """
    Address.ensure_address(addr)

def zero_addr(wc):
    """Creates a zero address instance in a given workchain.

    :param num wc: Workchain ID
    :return: Object
    :rtype: Address
    """
    return Address.zero_addr(wc)

def format_addr(addr, compact = True):
    Address.ensure_address(addr)
    if addr.is_none():
        return 'addr_none'
    addr = addr.str()
    s = addr[:10]
    if addr in globals.NICKNAMES:
        s = "{} ({})".format(globals.NICKNAMES[addr], s)
    else:
        if not compact:
            s = 'Addr({})'.format(s)
    return s

def format_addr_colored(addr, color1, color2):
    Address.ensure_address(addr)
    if addr.is_none():
        return colorize(color1, 'addr_none')
    addr = addr.str()
    s = addr[:10]
    if addr in globals.NICKNAMES:
        s = colorize(color1, globals.NICKNAMES[addr]) + colorize(color2, ' ({})'.format(s))
        # s = "{} ({})".format(globals.NICKNAMES[addr], s)
    else:
        s = colorize(color1, '{}'.format(s))
    return s

def make_keypair(seed = None) -> tuple[str, str]:
    """Generates random keypair.

    :param str seed: Seed to be used to generate keys. Useful when constant keypair is needed
    :return: The key pair
    :rtype: (str, str)
    """
    if isinstance(seed, str):
        hash = hashlib.sha256(seed.encode('utf-8'))
        seed = decode_int('0x' + hash.hexdigest())
        seed = seed % (2**64)
    (private_key, public_key) = ed25519.create_keypair()
    private_key = private_key.to_ascii(encoding='hex').decode()
    public_key = public_key.to_ascii(encoding='hex').decode()
    return (private_key + public_key, public_key)

def save_keypair(keypair, filename):
    """Saves keypair to file.

    :param keypair: Keypair to be saved
    :param str filename: File name
    """
    d = dict(
        public = keypair[1].replace('0x', ''),
        secret = keypair[0]
    )
    str = json.dumps(d, indent = 2)
    f = open(filename, "w")
    f.write(str)
    f.close()

def load_keypair(filename):
    """Loads keypair from a file.

    :param str filename: File name
    :return: The loaded keypair
    :rtype: (str, str)
    """
    with open(filename, 'rt') as f:
        j = json.load(f)
    public = j['public']
    secret = j['secret']
    return (secret, '0x' + public)

def load_tvc(fn, extension = '.tvc') -> Cell:
    """Loads a compiled contract image (`.tvc`) with a given name.

    :param str fn: The file name
    :return: Cell object loaded from a given file
    :rtype: Cell
    """
    fn = make_path(fn, extension)
    with open(fn, 'rb') as fp:
        str = base64.b64encode(fp.read(1_000_000)).decode('utf-8')
        return Cell(str)

def load_code_cell(fn) -> Cell:
    """Loads contract code cell from a compiled contract image with a given name.

    :param str fn: The file name
    :return: Cell object containing contract's code cell
    :rtype: Cell
    """
    fn = make_path(fn, '.tvc')
    return Cell(globals.core.load_code_cell(fn))

def load_data_cell(fn) -> Cell:
    """Loads contract data cell from a compiled contract image with a given name.

    :param str fn: The file name
    :return: Cell object containing contract's data cell
    :rtype: Cell
    """
    fn = make_path(fn, '.tvc')
    return Cell(globals.core.load_data_cell(fn))

def evers(n):
    if n is None: return None
    return '{:.3f}'.format(n / EVER).replace('.000', '')

# deprecated
def grams(n):
    return evers(n)

def ensure_balance(expected, got, dismiss = False, epsilon = 0, msg = None):
    """Checks the contract balance for exact match.
    In case of mismatch prints the difference in a convenient form.

    :param num expected: Expected balance value
    :param num got: Current balance value
    :param bool dismiss: When False don't stop the execution in case of mismatch
    :param num epsilon: Allowed difference between requested and actual balances
    :param str msg: Optional message to print in case of mismatch
    """
    if expected is None or got is None:
        assert eq(expected, got, dismiss = dismiss, msg = msg)
        return
    diff = got - int(expected)
    if abs(diff) <= epsilon:
        return
    xtra = ", diff = {}g ({})".format(evers(diff), diff)
    assert eq(int(expected), got, xtra = xtra, dismiss = dismiss, msg = msg)

def register_abi(contract_name):
    """Loads an ABI for a given contract without its construction.
    Useful when some contracts are deployed indirectly (i.e. from other contracts).

    :param str contract_name: The contract name the ABI of which should be uploaded
    """
    fn = make_path(contract_name, '.abi.json')
    if globals.G_VERBOSE:
        print(blue("Loading ABI " + fn))
    globals.core.set_contract_abi(None, fn)

def sign_cell(cell: Cell, private_key: str) -> str:
    """Signs cell with a given key and returns signature.

    :param Cell value: Cell to be signed
    :param str private_key: Hexadecimal representation of 1024-bits long private key
    :return: Hexadecimal string representing resulting signature
    :rtype: str
    """
    assert isinstance(cell, Cell)
    assert isinstance(private_key, str)
    assert eq(128, len(private_key))
    return globals.core.sign_cell(cell.raw_, private_key)

def sign_cell_hash(cell: Cell, private_key: str) -> str:
    """Signs cell's repr_hash with a given key and returns signature.

    :param Cell value: Cell to be signed
    :param str private_key: Hexadecimal representation of 1024-bits long private key
    :return: Hexadecimal string representing resulting signature
    :rtype: str
    """
    assert isinstance(cell, Cell)
    assert isinstance(private_key, str)
    assert eq(128, len(private_key))
    return globals.core.sign_cell_hash(cell.raw_, private_key)

def last_gas():
    """Returns the gas used in the last contract execution.

    :return: gas used in the last contract execution
    :rtype: num
    """
    return globals.G_LAST_GAS_USED

def set_config_param(index: int, value: Cell):
    """Sets global config parameter.

    :param num index: Parameter index
    :param Cell value: Cell object containing desired value.
    """
    assert isinstance(value, Cell)
    globals.core.set_config_param(index, value.raw_)

#########################################################################################################

def get_all_runs():
    return json.loads(globals.core.get_all_runs())

#########################################################################################################

def fix_abi(name, abi, callback):
    """Travels through given ABI calling a callback function for each node

    :param str name: Contract name
    :param dict abi: Contract ABI
    :param callback: Transformation function called for each node
    """
    traveller = AbiTraversalHelper(name, abi)
    traveller.travel_fields(callback)

def set_contract_abi(contract, new_abi_name):
    """Sets new ABI for a given contract. Useful when contract code was upgraded.

    :param BaseContract contract: An instance of the contract where the ABI will be set
    :param str new_abi_name: Name of the file containing the ABI
    """
    assert isinstance(contract, BaseContract)

    contract.abi = Abi(new_abi_name)
    globals.core.set_contract_abi(contract.addr.str(), contract.abi.path_)


#########################################################################################################

def get_all_messages(show_all = False):
    def filter(msg):
        msg = Msg(msg)
        # TODO: support getters/answers
        assert isinstance(msg, Msg), "{}".format(msg)
        if show_all:
            return True
        return msg.is_type_in(['call', 'external_call', 'empty', 'event', 'unknown', 'log'])
    msgs = json.loads(globals.core.get_all_messages())
    return [m for m in msgs if filter(m)]

#########################################################################################################

def get_balance(addr):
    """Retrieves the balance of a given address.

    :param Address addr: The address of a contract
    :return: Current account balance
    :rtype: num
    """
    Address.ensure_address(addr)
    return globals.core.get_balance(addr.str())

#########################################################################################################
