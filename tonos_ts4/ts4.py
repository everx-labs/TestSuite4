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
from .core      import *
from .address   import *
from .abi       import *
from .decoder   import *
from .dump      import *
from .global_functions  import *

from .globals       import core
from .BaseContract  import BaseContract, decode_contract_answer

__version__ = version()

core = load_linker_lib()
globals.set_core(core)

class BaseException(Exception):
    def __init__(self, msg):
        super(Exception, self).__init__(msg)


# TODO: Global decoding params. Add documentation
decoder = Decoder.defaults()

def check_exitcode(expected_ec, real_ec):
    assert isinstance(expected_ec, list)
    if real_ec not in expected_ec:
        xtra = None
        if real_ec == 51:   xtra = 'Calling of contract\'s constructor that has already been called.'
        if real_ec == 52:   xtra = 'Replay protection exception.'
        if real_ec == 60:   xtra = 'Inbound message has wrong function id.'
        if real_ec == 76:   xtra = 'Public function was called before constructor.'
        # TODO: add more codes here...

        if xtra is not None:
            xtra = ': ' + xtra
        else:
            xtra = ''
        last_error = globals.core.get_last_error_msg()
        if last_error is not None:
            verbose_('{}{}'.format(last_error, xtra))
        if globals.G_STOP_AT_CRASH:
            raise BaseException('Unexpected exit code: {}, expected {}'.format(real_ec, expected_ec))

def process_actions(result: ExecutionResult, expect_ec = [0]):
    # print('process_actions: expect_ec = {}'.format(expect_ec))
    assert isinstance(expect_ec, list)
    assert isinstance(result, ExecutionResult)
    ec = result.exit_code

    if globals.G_VERBOSE:
        if ec != 0:
            print(grey('    exit_code: ') + yellow(ec) + '\n')

    if ec not in expect_ec:
        verbose_(globals.core.get_last_error_msg())

    check_exitcode(expect_ec, ec)

    if result.error is not None:
        raise ts4.BaseException("Transaction aborted: {}".format(result.error))

    answer = None

    for j in result.actions:
        # print(j)
        msg = Msg(json.loads(j))
        # if globals.G_VERBOSE:
            # print('process msg:', msg)
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
            globals.QUEUE.append(msg)
    return (result.gas_used, answer)

def dispatch_messages(callback = None, limit = None):
    """Dispatches all messages in the queue one by one until the queue becomes empty.

    :param callback: Callback to be called for each processed message.
        If callback returns False then the given message is skipped.
    :param num limit: Limit the number of processed messages by a given value.
    :return: False if queue was empty, True otherwise
    :rtype: bool

    """
    count = 0
    while len(globals.QUEUE) > 0:
        count = count + 1
        msg = peek_msg()
        if callback is not None and callback(msg, False) == False:
            pop_msg()
            continue
        dispatch_one_message()
        if callback is not None:
            callback(msg, True)
        if limit is not None:
            if count >= limit:
                break
    return count > 0

def dispatch_one_message(expect_ec = 0):
    """Takes first unprocessed message from the queue and dispatches it.
    Use `expect_ec` parameter if you expect non-zero exit code.

    :param num expect_ec: Expected exit code
    :return: The amount of gas spent on the execution of the transaction
    :rtype: num
    """
    if isinstance(expect_ec, int):
        expect_ec = [expect_ec]
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

    # dump_struct(msg.data)

    CONFIRM_INPUT_ADDR = Address('-31:16653eaf34c921467120f2685d425ff963db5cbb5aa676a62a2e33bfc3f6828a')
    if msg.dst == CONFIRM_INPUT_ADDR:
        verbose_('!!!!!!!!!!!!')

    result = globals.core.dispatch_message(msg.id)
    result = ExecutionResult(result)

    globals.G_LAST_GAS_USED = result.gas_used

    # print('actions =', result.actions)
    error_msg = None
    try:
        gas, answer = process_actions(result, expect_ec)
    except Exception as err:
        print(err)
        error_msg = str(err)
    if error_msg is not None:
        verbose_('!!!' + error_msg)
        raise ts4.BaseException(error_msg)
    if result.debot_answer_msg is not None:
        answer_msg = Msg(json.loads(result.debot_answer_msg))
        # verbose_(answer_msg)
        globals.QUEUE.append(answer_msg)
    if answer is not None:
        # verbose_('debot_answer = {}'.format(answer))
        translated_msg = core.debot_translate_getter_answer(answer.id)
        # verbose_('translated_msg = {}'.format(translated_msg))
        translated_msg = Msg(json.loads(translated_msg))
        # verbose_(translated_msg)
        globals.QUEUE.append(translated_msg)

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

