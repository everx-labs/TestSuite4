"""
    This file is part of Ever OS.

    Ever OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2022 (c) TON LABS
"""

import base64
import os
import sys
import binascii

from .address import *

class BColors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    BRIGHT_BLUE = '\033[94;1m'
    OKGREEN = '\033[92m'
    BRIGHT_GREEN = '\033[92;1m'
    RESET = '\033[90m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    CYAN = '\033[36m'
    BRIGHT_CYAN = '\033[36;1m'
    WHITE = '\033[37m'

def colorize(color, text):
    if sys.stdout.isatty():
        return color + text + BColors.ENDC
    else:
        return text

def green(msg):        return colorize(BColors.OKGREEN,      str(msg))
def bright_green(msg): return colorize(BColors.BRIGHT_GREEN, str(msg))
def blue(msg):         return colorize(BColors.OKBLUE,       str(msg))
def bright_blue(msg):  return colorize(BColors.BRIGHT_BLUE,  str(msg))
def red(msg):          return colorize(BColors.FAIL,         str(msg))
def yellow(msg):       return colorize(BColors.WARNING,      str(msg))
def white(msg):        return colorize(BColors.BOLD,         str(msg))
def grey(msg):         return colorize(BColors.RESET,        str(msg))
def cyan(msg):         return colorize(BColors.CYAN,         str(msg))
def bright_cyan(msg):  return colorize(BColors.BRIGHT_CYAN,  str(msg))

def transform_structure(value, callback):
    if isinstance(value, dict):
        nd = {}
        for key, v in value.items():
            nd[key] = transform_structure(v, callback)
        return nd
    if isinstance(value, list):
        return [transform_structure(x, callback) for x in value]
    return callback(value)

def decode_int(v: str) -> int:
    """Decodes integer value from hex string. Helper function useful when decoding data from contracts.

    :param str v: Hexadecimal string
    :return: Decoded number
    :rtype: num
    """
    if isinstance(v, int):
        return v
    assert isinstance(v, str)
    if v[0:2] == '0x':
        return int(v.replace('0x', ''), 16)
    else:
        return int(v)

def str2bytes(s: str) -> str:
    """Converts string to hex representations.

    :param str s: A string to convert
    :return: Hexadecimal string
    :rtype: str
    """
    assert isinstance(s, str), 'Expected string got {}'.format(s)
    ss = str(binascii.hexlify(s.encode()))[1:]
    return ss.replace("'", "")

def bytes2str(b: str) -> str:
    """Decodes utf-8 string from hex representation

    :param str b: Hexadecimal string to convert
    :return: Decoded string
    :rtype: str
    """
    return binascii.unhexlify(b).decode('utf-8')

def make_secret_token(n):
    return '0x' + secrets.token_hex(n)

def fix_uint256(s):
    assert s[0:2] == '0x', 'Expected hexadecimal, got {}'.format(s)
    t = s[2:]
    if len(t) < 64:
        s = '0x' + ('0' * (64-len(t))) + t
    return s

def eq(v1, v2, dismiss = False, msg = None, xtra = ''):
    """Helper function to check that two values are equal.
    Prints the message in case of mismatch, and optionally stops tests execution.

    :param Any v1: Expected value
    :param Any v2: Actual value
    :param bool dismiss: When False stops the entire execution in case of mismatch.
        When True only error message is shown
    :param str msg: Optional additional message to be printed in case of mismatch
    :param str xtra: Another optional additional message to be printed
    :return: Result of check
    :rtype: bool
    """
    if v1 == v2:
        return True
    else:
        msg = '' if msg is None else msg + ' '
        v1 = v1.__repr__()
        v2 = v2.__repr__()
        print(msg + red('exp: {}, got: {}.'.format(v1, v2)) + xtra)
        return True if dismiss else False

def ne(v1, v2, dismiss = False, msg = None, xtra = ''):
    """Helper function to check that two values are not equal.
    Prints the message in case of mismatch, and optionally stops tests execution.

    :param Any v1: Expected value
    :param Any v2: Actual value
    :param bool dismiss: When False stops the entire execution in case of match.
        When True only error message is shown
    :param str msg: Optional additional message to be printed in case of match
    :param str xtra: Another optional additional message to be printed
    :return: Result of check
    :rtype: bool
    """
    if v1 != v2:
        return True
    else:
        msg = '' if msg is None else msg + ' '
        v1 = v1.__repr__()
        v2 = v2.__repr__()
        print(msg + red('unexp: {}.'.format(v1)) + xtra)
        return True if dismiss else False

def leq(v1, v2):
    """Helper function to check that one value is less or equal than enother.
    Prints the message in case of mismatch.

    :param Any v1: First value
    :param Any v2: Second value
    :return: Result of check
    :rtype: bool
    """
    if v1 <= v2:
        return True
    print(red('expected {} <= {}'.format(v1, v2)))
    return False

def either_or(value, default):
    return value if value is not None else default

def ellipsis(s, max_len):
    if len(s) > max_len:
        s = s[:max_len-3] + '...'
    return s

def check_err(v1: str, v2: str, dismiss = False, msg = None, xtra = ''):
    """Helper function to check that two values are not equal.
    Prints the message in case of mismatch, and optionally stops tests execution.

    :param Any v1: Expected value
    :param Any v2: Actual value
    :param bool dismiss: When False stops the entire execution in case of match.
        When True only error message is shown
    :param str msg: Optional additional message to be printed in case of match
    :param str xtra: Another optional additional message to be printed
    :return: Result of check
    :rtype: bool
    """
    if v2.startswith(v1):
        return True
    else:
        msg = '' if msg is None else msg + ' '
        v1 = v1.__repr__()
        v2 = v2.__repr__()
        print(msg + red('exp: {}, got: {}.'.format(v1, v2)) + xtra)
        return True if dismiss else False

def base64_to_hex(b64: str) -> str:
    # decode base64 to bytes
    bytes = base64.b64decode(b64)

    # convert bytes to hex string
    return binascii.hexlify(bytes).decode('utf-8')

def make_path(name, ext = "") -> str:
    fn = os.path.join(globals.G_TESTS_PATH, name)
    if ext != "":
        assert ext.find('.') != -1
    if ext == '.abi.json' and os.path.exists(fn + '.abi'):
        ext = '.abi'
    elif ext == ".abi" and not os.path.exists(fn + '.abi'):
        assert os.path.exists(fn + '.abi.json')
        ext = '.abi.json'
    if not fn.endswith('.boc'):
        if not fn.endswith(ext):
            fn += ext
    return fn
