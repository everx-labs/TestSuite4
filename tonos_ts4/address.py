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
    def __eq__(self, other):
        """Сompares the object with the passed value.

        :param Address other: Address object
        :return: Result of check
        :rtype: bool
        """
        ensure_address(other)
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

def zero_addr(wc):
    """Creates a zero address instance in a given workchain.

    :param num wc: Workchain ID
    :return: Object
    :rtype: Address
    """
    addr = '{}:{}'.format(wc, '0'*64)
    return Address(addr)

def ensure_address(addr):
    """Raises an error if a given object is not of :class:`Address <Address>` class.

    :param Address addr: Object of class Address
    """
    assert isinstance(addr, Address), red('Expected Address got {}'.format(addr))

