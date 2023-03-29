"""
    This file is part of Ever OS.

    Ever OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2023 (c) EverX
"""

import os
import json

from util import *
from address import *
from abi import *
from globals import EVER
from global_functions import *

def dump_struct(struct, compact = False):
    if compact:
        print(json.dumps(struct))
    else:
        print(dump_struct_str(struct))

class JsonEncoder(json.JSONEncoder):
    def default(self, o):
        # verbose_(o)
        if isinstance(o, Address):
            return o.str()
        elif isinstance(o, Bytes):
            return o.raw_
        else:
            assert False

def dump_struct_str(struct):
    return json.dumps(struct, indent = 2, cls = JsonEncoder)

def _fix_large_ints(v):
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

def json_dumps(j: dict, indent = None) -> str:
    j = _fix_large_ints(j)
    return json.dumps(j, indent = indent) #, cls = JsonEncoder)


#########################################################################################################


def dump_all_messages():
    prev_time = 0
    for msg in globals.ALL_MESSAGES:
        cur_time = msg['timestamp']
        if cur_time == prev_time:
            print('---------------')
        else:
            print('--------------- {} ------------ ------------ ------------'
                .format(colorize(BColors.BOLD, str(cur_time))))
            prev_time = cur_time
        print_int_msg(msg)

def dump_last_message():
    assert ne(0, len(globals.QUEUE))
    msg = globals.QUEUE[-1]
    print_int_msg(msg)

def print_ext_in_msg(addr, method, params):
    print(blue('> ext_in_msg') + grey(': '), end='')
    print(cyan('      '), grey('->'), bright_cyan(format_addr(addr)))
    print(cyan(grey('    method: ') + bright_cyan('{}'.format(method))
    + grey('\n    params: ') + cyan('{}'.format(Params.stringify(prettify_dict(params))))) + '\n')

def print_int_msg(msg: Msg):
    assert isinstance(msg, Msg)
    value = str(msg.value / EVER) if msg.value is not None else 'n/a'
    #print(msg)

    msg_type = ''
    ttt = ''
    if msg.is_type('call',  'empty', 'bounced'):
        # ttt = "{}".format(msg)
        if msg.is_call():
            # print(msg)
            ttt = bright_cyan(msg.method) + grey('\n    params: ') + cyan(Params.stringify(msg.params) + '\n')
            ttt = grey('    method: ') + ttt
        elif msg.is_bounced():
            msg_type = yellow(' <bounced>')
        elif msg.is_type('empty') and value != "0":
            msg_type = cyan(' <transfer>')
        else:
            msg_type = cyan(' <empty>')
        #print(grey('    method:'), ttt)
    elif msg.is_unknown():
        #print(msg)
        ttt = "> " + yellow('<unknown>') #TODO to highlight the print
        ttt = ttt + ' body = {}'.format(ellipsis(globals.core.get_msg_body(msg.id), 64))
        #print("> " + ttt)
    else:
        assert msg.is_answer()
        ttt = "> " + green('{}'.format(msg.data))
        #print("> " + green(ttt))

    if msg.value is None:
        msg_value_is_correct = True
        msg_value = 'None'
    else:
        msg_value_is_correct = msg.value < 2**63
        msg_value = '{:,}'.format(msg.value)
    msg_value = cyan(msg_value) if msg_value_is_correct else red(msg_value)

    print(blue('> int_msg' + msg_type) + grey(': '), end='')

    src = format_addr_colored(msg.src, BColors.BRIGHT_CYAN, BColors.RESET)
    dst = format_addr_colored(msg.dst, BColors.BRIGHT_CYAN, BColors.RESET)

    print(src, grey('->'), dst, end='')
    print(grey(', value:'), msg_value)
    if ttt != '':
        print(ttt)

    assert msg_value_is_correct

def print_tick_tock(addr, is_tock):
    print(blue('> tick tock') + grey(': '), end='')
    print(cyan('       '), grey('->'), bright_cyan(format_addr(addr)))

#########################################################################################################

def dump_js_data(path = '.'):
    fn = os.path.join(path, 'msg_data.js')
    all_runs = get_all_runs()
    msgs = get_all_messages()
    def truncate_long_strings(msg):
        if msg['params'] is not None:
            msg['params'] = prettify_dict(msg['params'])
        return msg
    msgs = [truncate_long_strings(msg) for msg in msgs]
    with open(fn, 'w') as f:
        print('var allMessages = ' + dump_struct_str(msgs) + ';', file = f)
        print('var nicknames = ' + dump_struct_str(globals.NICKNAMES) + ';', file = f)
        print('var allRuns = ' + dump_struct_str(all_runs) + ';', file = f)

