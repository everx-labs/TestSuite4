"""
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
"""

import sys
import base64
import secrets
import json
import numbers
import re
import copy
import os.path
from glob import glob

from .util      import *
from .address   import *
from .abi       import *
from .decoder   import *
from .dump      import *
from .global_functions  import *

from .globals       import core
from .BaseContract  import BaseContract

__version__ = version()

# TODO: Global decoding params. Add documentation
decoder = Decoder.defaults()

def check_exitcode(expected_ec, real_ec):
    if expected_ec != real_ec:
        xtra = ''
        if real_ec == 76:
            xtra = ': Contructor was not called'
        if real_ec == 51:
            xtra = ': Constructor was already called'
        verbose_('{}{}'.format(globals.core.get_last_error_msg(), xtra))
    assert eq(expected_ec, real_ec, dismiss = not globals.G_STOP_AT_CRASH)

def process_actions(result: ExecutionResult, expect_ec = 0):
    assert isinstance(result, ExecutionResult)
    ec = result.exit_code

    if globals.G_VERBOSE:
        if ec != 0:
            print(grey('    exit_code: ') + yellow(ec) + '\n')

    if expect_ec != ec:
        verbose_(globals.core.get_last_error_msg())

    check_exitcode(expect_ec, ec)

    if result.error is not None:
        raise Exception("Transaction aborted: {}".format(result.error))

    answer = None

    for j in result.actions:
        msg = Msg(json.loads(j))
        # if globals.G_VERBOSE:
            # print('process msg:', msg)
        if msg.is_event():
            if globals.G_VERBOSE or globals.G_SHOW_EVENTS:
                # TODO: move this printing code to a separate function and file
                xtra = ''
                params = msg.params
                if msg.is_event('DebugEvent'):
                    xtra = ' ={}'.format(decode_int(params['x']))
                elif msg.is_event('LogEvent'):
                    params['comment'] = bytearray.fromhex(params['comment']).decode()
                print(bright_blue('< event') + grey(': '), end='')
                print(cyan('          '), grey('<-'), bright_cyan(format_addr(msg.src)))
                print(cyan(grey('    name:   ') + cyan('{}'.format(bright_cyan(msg.event)))))
                print(grey('    params: ') + cyan(Params.stringify(params)), cyan(xtra), '\n')
            globals.EVENTS.append(msg)
        else:
            # not event
            if msg.is_unknown():
                #print(msg)
                if globals.G_VERBOSE:
                    print(yellow('WARNING! Unknown message!')) #TODO to highlight the print
            elif msg.is_bounced():
                pass
            elif msg.is_answer():
                # We expect only one answer
                assert answer is None
                answer = msg
                continue
            else:
                assert msg.is_call() or msg.is_empty(), red('Unexpected type: {}'.format(msg.type))
            globals.QUEUE.append(msg)
    return (result.gas_used, answer)

def dispatch_messages(callback = None):
    """Dispatches all messages in the queue one by one until the queue becomes empty.

    :param callback: Callback to be called for each processed message.
        If callback returns False then the given message is skipped.
    """
    while len(globals.QUEUE) > 0:
        if callback is not None and callback(peek_msg()) == False:
            pop_msg()
            continue
        dispatch_one_message()

def dispatch_one_message(expect_ec = 0):
    """Takes first unprocessed message from the queue and dispatches it.
    Use `expect_ec` parameter if you expect non-zero exit code.

    :param num expect_ec: Expected exit code
    :return: The amount of gas spent on the execution of the transaction
    :rtype: num
    """
    msg = pop_msg()
    globals.ALL_MESSAGES.append(msg)
    # if is_method_call(msg, 'onRoundComplete'):
        # dump_message(msg)
    dump1 = globals.G_VERBOSE or globals.G_DUMP_MESSAGES
    dump2 = globals.G_MSG_FILTER is not None and globals.G_MSG_FILTER(msg.data)
    if dump1 or dump2:
        dump_message(msg)
    if msg.dst.is_none():
        # TODO: a getter's reply. Add a test for that
        return
    result = globals.core.dispatch_message(msg.id)
    result = ExecutionResult(result)
    gas, answer = process_actions(result, expect_ec)
    assert answer is None
    return gas


#########################################################################################################

# TODO: add docs?
class BalanceWatcher:
    def __init__(self, contract):
        self.contract_  = contract
        self.balance_   = contract.balance
        self.epsilon_   = 2

    def ensure_change(self, expected_diff):
        cur_balance     = self.contract_.balance
        prev_balance    = self.balance_
        ensure_balance(prev_balance + expected_diff, cur_balance, epsilon = self.epsilon_)
        self.balance_   = cur_balance


#########################################################################################################

