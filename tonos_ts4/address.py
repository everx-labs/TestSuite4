import json

from . import globals
from . import ts4
from .util import *


class Address:
    """The :class:`Address <Address>` object, which contains an
    Address entity.
    """
    def __init__(self, addr):
        """Constructs :class:`Address <Address>` object.

        :param str addr: A string representing the address or None
        """
        if addr is None:
            addr = ''
        assert isinstance(addr, str), "{}".format(addr)
        if addr.startswith(':'):
            addr = '0' + addr
        # TODO: check that it is a correct address string
        self.addr_ = addr

    def __str__(self):
        """Used by print().

        :return: A string representing the address
        :rtype: str
        """
        return 'Addr({})'.format(self.addr_)

    def __repr__(self):
        return "Address('{}')".format(self.addr_)

    def __hash__(self):
        return hash(self.addr_)

    def __eq__(self, other):
        """Сompares the object with the passed value.

        :param Address other: Address object
        :return: Result of check
        :rtype: bool
        """
        Address.ensure_address(other)
        return self.str() == other.str()

    def str(self):
        """Returns string representing given address.

        :return: A string representing the address
        :rtype: str
        """
        return self.addr_

    def is_none(self):
        """Checks if address is None.

        :return: Result of check
        :rtype: bool
        """
        return self.str() == ''

    def fix_wc(self):
        """Adds workchain_id if it was missing.

        :return: Object
        :rtype: Address
        """
        assert eq(':', self.addr_[0])
        self.addr_ = '0' + self.addr_
        return self

    @staticmethod
    def zero_addr(wc = 0):
        """Creates a zero address instance in a given workchain.

        :param num wc: Workchain ID
        :return: Object
        :rtype: Address
        """
        if wc is None: wc = 0

        addr = '{}:{}'.format(wc, '0'*64)
        return Address(addr)

    @staticmethod
    def ensure_address(addr):
        """Raises an error if a given object is not of :class:`Address <Address>` class.

        :param Address addr: Object of class Address
        """
        assert isinstance(addr, Address), red('Expected Address got {}'.format(addr))


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

    def str(self):
        return bytes2str(self.raw_)

    def __repr__(self):
        return "Bytes('{}')".format(self.raw_)

    def __eq__(self, other):
        if isinstance(other, Bytes):
            return self.raw_.lower() == other.raw_.lower()
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
        assert isinstance(value, str)
        self.raw_ = value

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "Cell('{}')".format(self.short_raw())

    def short_raw(self):
        t = self.raw_;
        if (len(t) > 16):
            t = t[:13] + '...'
        return t

    def __eq__(self, other):
        if isinstance(other, Cell):
            return self.raw_ == other.raw_
        return False

    def is_empty(self):
        """Checks if the cell is empty.

        :return: Result of check
        :rtype: bool
        """
        return globals.EMPTY_CELL == self.raw_


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
        """Checks if the given message is bounced.

        :return: Result of check
        :rtype: bool
        """
        return self.type == 'bounced'

    def is_getter(self):
        """Checks if the given message is a getter call.

        :return: Result of check
        :rtype: bool
        """
        return self.type == 'call_getter'

    def dump_data(self):
        """Dumps message data.
        """
        dump_struct(self.data)

    def __str__(self):
        return ts4.dump_struct_str(self.data)


class Params:
    def __init__(self, params):
        assert isinstance(params, dict), '{}'.format(params)
        # String key means structure. Integer keys means mapping
        for key in params.keys():
            assert isinstance(key, str)
        self.__raw__ = params
        self.transform(params)

    def transform(self, params):
        if isinstance(params, dict):
            for key in params:
                value = params[key]
                if isinstance(value, dict):
                    value = Params(value)
                if isinstance(value, Bytes) and ts4.decoder.strings is True:
                    value = str(value)
                if isinstance(value, list):
                    value = [self.tr(x) for x in value]
                setattr(self, key, value)

    @staticmethod
    def stringify(d):
        arr = []
        for k, v in d.items():
            if isinstance(v, dict):
                arr.append(f'{(k)}: {{{Params.stringify(v)}}}')
            else:
                arr.append(f'{(k)}: {(v)}')

        return (', ').join(arr)

    def tr(self, x):
        if isinstance(x, dict):
            return Params(x)
        return x

def make_params(data):
    if isinstance(data, dict):
        keys = list(data.keys())
        # String key means structure. Integer keys means mapping
        if keys != [] and isinstance(keys[0], str):
            return Params(data)
        else:
            res = dict()
            for k in keys:
                res[k] = make_params(data[k])
            return res
    if isinstance(data, list):
        return [make_params(x) for x in data]
    return data


class ExecutionResult:
    def __init__(self, result):
        (ec, actions, gas, err, debot_answer_msg) = result
        self.exit_code  = ec
        self.actions    = actions
        self.gas_used   = gas
        self.error      = err
        self.debot_answer_msg = debot_answer_msg

def prettify_dict(d, max_str_len = 67):
    nd = {}
    for k, v in d.items():
        if isinstance(v, dict):
            nd[k] = prettify_dict(v, max_str_len = max_str_len)
        elif isinstance(v, str):
            nd[k] = v if len(v) <= max_str_len else v[:max_str_len] + '...'
        elif isinstance(v, Address):
            nd[k] = ts4.format_addr(v, compact = False)
        else:
            nd[k] = v

    return nd

