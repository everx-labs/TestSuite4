import os
import base64

from . import globals as g
from .globals import GRAM, EMPTY_CELL
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
    assert len(g.QUEUE) > 0
    return g.QUEUE[0]

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
    assert len(g.EVENTS) > 0
    return g.EVENTS[0]

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

def make_keypair(seed = None):
    """Generates random keypair.

    :param num seed: Seed to be used to generate keys. Useful when constant keypair is needed
    :return: The key pair
    :rtype: (str, str)
    """
    (secret_key, public_key) = globals.core.make_keypair(seed)
    public_key = '0x' + public_key
    return (secret_key, public_key)

def make_path(name, ext):
    fn = os.path.join(globals.G_TESTS_PATH, name)
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
    Returns cell encoded to string.

    :param str fn: The file name
    :return: Cell object containing contract's code cell
    :rtype: Cell
    """
    fn = make_path(fn, '.tvc')
    return Cell(globals.core.load_code_cell(fn))

def load_data_cell(fn):
    """Loads contract data cell from a compiled contract image with a given name.
    Returns cell encoded to string

    :param str fn: The file name
    :return: Cell object containing contract's data cell
    :rtype: Cell
    """
    fn = make_path(fn, '.tvc')
    return Cell(globals.core.load_data_cell(fn))

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
    if expected is None or got is None:
        assert eq(expected, got, dismiss = dismiss, msg = msg)
        return
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
    fn = make_path(new_abi_name, '.abi.json')
    globals.core.set_contract_abi(contract.addr.str(), fn)
    with open(fn, 'rb') as fp:
        contract.abi_ = json.load(fp)


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
