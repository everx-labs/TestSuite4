import os
import base64
import hashlib

from . import globals as g
from .globals import EVER, GRAM, EMPTY_CELL
from .util import *
from .address import *
from .abi import *
from . import ts4

def version():
    """Returns current version of TestSuite4.

    :return: Current version
    :rtype: str
    """
    return g.G_VERSION


def reset_all():
    """Resets entire TS4 state. Useful when starting new testset.
    """
    g.core.reset_all()
    g.QUEUE           = []
    g.EVENTS          = []
    g.ALL_MESSAGES    = []
    g.NICKNAMES       = dict()

def set_tests_path(path):
    """Sets the directory where the system will look for compiled contracts.

    :param str path: The path to contract artifacts
    """
    g.G_TESTS_PATH = path

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
        g.core.set_now(time)

def set_verbose(verbose = True):
    """Sets verbosity mode. When verbosity is enabled all the messages
    and some additional stuff is printed to console. Useful for debugging.

    :param bool verbose: Toggle to print additional execution info
    """
    g.G_VERBOSE = verbose

def set_stop_at_crash(do_stop):
    """Sets `G_STOP_AT_CRASH` global flag.
    By default the system stops at the first exception (unexpected exit code) raised by a contract.
    Use `expect_ec` parameter if you expected an exception in a given call.
    When `G_STOP_AT_CRASH` is disabled the system only warns user and does not stop.

    :param bool do_stop: Toggle for crash stop mode
    """
    g.G_STOP_AT_CRASH = do_stop

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
    if g.G_VERBOSE or show_always:
        if color_red:
            msg = red(str(msg))
        print(msg)

def pop_msg():
    """Removes first message from the unprocessed messages g.QUEUE and returns it.

    :return: Object
    :rtype: Msg
    """
    assert len(g.QUEUE) > 0
    return g.QUEUE.pop(0)

def peek_msg():
    """Returns first message from the unprocessed messages g.QUEUE and leaves the g.QUEUE unchanged.

    :return: Object
    :rtype: Msg
    """
    return g.QUEUE[0] if len(g.QUEUE) > 0 else None

def pop_event():
    """Removes first event from the unprocessed events g.QUEUE and returns it.

    :return: Object
    :rtype: Msg
    """
    assert len(g.EVENTS) > 0
    return g.EVENTS.pop(0)

def peek_event():
    """Returns first event from the unprocessed events g.QUEUE and leaves the g.QUEUE unchanged.

    :return: Object
    :rtype: Msg
    """
    return g.EVENTS[0] if len(g.EVENTS) > 0 else None

def queue_length():
    """Returns the size of the unprocessed messages g.QUEUE.

    :return: g.QUEUE length
    :rtype: num
    """
    return len(g.QUEUE)

def ensure_queue_empty():
    """Checks if the unprocessed messages g.QUEUE is empty
    and raises an error if it is not. Useful for debugging.
    """
    assert eq(0, len(g.QUEUE), msg = ('ensure_queue_empty() -'))

def dump_queue():
    """Dumps messages g.QUEUE to the console.
    """
    print(white("g.QUEUE:")) # revise print
    for i in range(len(g.QUEUE)):
        print("  {}: {}".format(i, g.QUEUE[i]))

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

def gen_addr(name, initial_data = None, keypair = None, wc = 0):
    """Generates contract addresss.

    :param str name: Name used to load contract's bytecode and ABI
    :param dict initial_data: Initial data for the contract (static members)
    :param keypair: Keypair containing private and public keys
    :param num wc: workchain_id to deploy contract to
    :return: Expected contract address
    :rtype: Address
    """
    if keypair is not None:
        # TODO: copy-paste below!
        (private_key, pubkey) = keypair
        if pubkey is not None:
            assert pubkey[0:2] == '0x'
            pubkey = pubkey.replace('0x', '')
    else:
        (private_key, pubkey) = (None, None)

    abi = Abi(name)

    if initial_data is not None:
        initial_data = ts4.check_method_params(abi, '.data', initial_data)

    result = ts4.core.gen_addr(
            make_path(name, '.tvc'),
            abi.path_,
            ts4.json_dumps(initial_data) if initial_data is not None else None,
            pubkey,
            private_key,
            wc
        )
    return Address(result)

def make_keypair(seed = None):
    """Generates random keypair.

    :param str seed: Seed to be used to generate keys. Useful when constant keypair is needed
    :return: The key pair
    :rtype: (str, str)
    """
    if isinstance(seed, str):
        hash = hashlib.sha256(seed.encode('utf-8'))
        seed = decode_int('0x' + hash.hexdigest())
        seed = seed % (2**64)
    (secret_key, public_key) = globals.core.make_keypair(seed)
    public_key = '0x' + public_key
    return (secret_key, public_key)

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

def make_path(name, ext):
    fn = os.path.join(globals.G_TESTS_PATH, name)
    if not fn.endswith('.boc'):
        if not fn.endswith(ext):
            fn += ext
    return fn

# TODO: Shouldn't this function return Cell?
def load_tvc(fn):
    """Loads a compiled contract image (`.tvc`) with a given name.

    :param str fn: The file name
    :return: Cell object loaded from a given file
    :rtype: Cell
    """
    fn = make_path(fn, '.tvc')
    with open(fn, 'rb') as fp:
        str = base64.b64encode(fp.read(1_000_000)).decode('utf-8')
        return Cell(str)

def load_code_cell(fn):
    """Loads contract code cell from a compiled contract image with a given name.

    :param str fn: The file name
    :return: Cell object containing contract's code cell
    :rtype: Cell
    """
    fn = make_path(fn, '.tvc')
    return Cell(globals.core.load_code_cell(fn))

def load_data_cell(fn):
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
    :param num got: Сurrent balance value
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
    return globals.core.sign_cell(cell.raw_, private_key)

def encode_message_body(abi_name, method, params):
    """Encode given message body.

    :param str abi_name: The contract name the ABI of which should be used for encoding
    :param str method: A name of the encoded method
    :param dict params: A dictionary with parameters for the encoded method
    :return: Cell object containing encoded message
    :rtype: Cell
    """
    abi_file = make_path(abi_name, '.abi.json')
    encoded = globals.core.encode_message_body(
        abi_file,
        method,
        ts4.json_dumps(params)
    )
    return Cell(encoded)

# TODO: finalize and add docs
def build_int_msg(src, dst, abi_file, method, params, value):
    assert isinstance(src, Address)
    assert isinstance(dst, Address)

    msg_body = ts4.encode_message_body(abi_file, method, params)

    # src = zero_addr(-1)
    msg = ts4.core.build_int_msg(src.str(), dst.str(), msg_body.raw_, value)
    # verbose_(msg)
    msg = Msg(json.loads(msg))
    verbose_(msg)
    ts4.globals.QUEUE.append(msg)
    return msg

def last_gas():
    return ts4.globals.G_LAST_GAS_USED

def set_config_param(index, value):
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
    assert isinstance(contract, ts4.BaseContract)

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
