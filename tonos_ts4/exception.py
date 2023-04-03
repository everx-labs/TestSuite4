"""
    This file is part of Ever OS.

    Ever OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2023 (c) EverX
"""

import os
import base64
import hashlib

from abi import *
from address import *
from decoder import Decoder
from globals import EVER, GRAM, EMPTY_CELL
from util import *
from global_functions import ensure_balance, verbose_


#########################################################################################################

# TODO: add docs?
class BalanceWatcher:
    def __init__(self, contract):
        self.contract_  = contract
        self.balance_   = contract.balance
        self.epsilon_   = 2

    def ensure_change(self, expected_diff, epsilon = None):
        cur_balance     = self.contract_.balance
        prev_balance    = self.balance_
        ensure_balance(prev_balance + expected_diff, cur_balance, epsilon = either_or(epsilon, self.epsilon_))
        self.balance_   = cur_balance


#########################################################################################################

class BaseException(Exception):
    def __init__(self, msg):
        super(Exception, self).__init__(msg)
    def clone(self):
        return BaseException(str(self))

class UnexpectedExitCodeException(BaseException):
    def __init__(self, expected, real):
        self.expected   = expected
        self.real       = real
        super(BaseException, self).__init__(
            'Unexpected exit code: {}, expected {}'.format(real, expected))
    def clone(self):
        return UnexpectedExitCodeException(self.expected, self.real)

def translate_exception(exception: Exception) -> Exception:
    # print('translate_exception:', exception)
    if globals.G_SHOW_FULL_STACKTRACE:
        return exception
    verbose_(exception)
    if isinstance(exception, BaseException):
        return exception.clone()
    return exception

# TODO: Global decoding params. Add documentation
decoder = Decoder.defaults()

G_SOLC_ERRORS = {
    40: 'External inbound message has an invalid signature.',
    50: 'Array index is out of range.',
    51: 'Contract\'s constructor has already been called.',
    52: 'Replay protection exception.',
#    53: 'See [\<address\>.unpack()](#addressunpack).
    54: 'pop() called for an empty array.',
#    55: 'See [tvm.insertPubkey()](#tvminsertpubkey).
    57: 'External inbound message is expired.',
    58: 'External inbound message has no signature but has public key.',
    60: 'Inbound message has wrong function id.',
    61: 'Deploying `StateInit` has no public key in `data` field.',
#    62: 'Reserved for internal usage.
#    63: 'See [\<optional(Type)\>.get()](#optionaltypeget).
    64: 'tvm.buildExtMSg() called with wrong parameters.',
    65: 'Call of the unassigned variable of function type.',
    66: 'Convert an integer to a string with width less than number length.',
#    67: 'See [gasToValue](#gastovalue) and [valueToGas](#valuetogas).
    68: 'There is no config parameter 20 or 21.',
    69: 'Zero to the power of zero calculation.',
    70: 'string method substr was called with substr longer than the whole string.',
    71: 'Function marked by `externalMsg` was called by internal message.',
    72: 'Function marked by `internalMsg` was called by external message.',
    73: 'The value can\'t be converted to enum type.',
    74: 'Await answer message has wrong source address.',
    75: 'Await answer message has wrong function id.',
    76: 'Public function was called before constructor.',
}

def check_exitcode(expected_ec, real_ec):
    expected_ec = either_or(globals.G_OVERRIDE_EXPECT_EC, expected_ec)
    assert isinstance(expected_ec, list)
    if real_ec not in expected_ec:
        xtra = None
        if real_ec in G_SOLC_ERRORS:
            xtra = G_SOLC_ERRORS[real_ec]
        if xtra is not None:
            xtra = ': ' + xtra
        else:
            xtra = ''
        last_error = globals.core.get_last_error_msg()
        if last_error is not None:
            verbose_('{}{}'.format(last_error, xtra))
        if globals.G_STOP_AT_CRASH:
            raise UnexpectedExitCodeException(expected_ec, real_ec)
