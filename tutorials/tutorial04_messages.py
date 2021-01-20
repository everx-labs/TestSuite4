"""
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
"""

import sys
sys.path.append('../ts4_py_lib')
import ts4lib as ts4  # noqa: E402
from ts4lib import eq  # noqa: E402


def test1():
    # In this scenario we are processing messages step by step

    print('Starting call chain (step by step)...')
    t_value = 4276994270
    contract1.call_method('ping_neighbor', dict(neighbor=neighbor2, value=t_value))

    # Get internal message that was created by previous call
    msg_ping = ts4.peek_msg()
    assert eq(neighbor1, msg_ping['src'])
    assert eq(neighbor2, msg_ping['dst'])
    assert eq('ping', msg_ping['method'])
    assert eq(t_value, int(msg_ping['params']['request']))

    # Dispatch created message
    ts4.dispatch_one_message()

    # Pick up event that was created by called method of the callee contract
    msg_event1 = ts4.pop_event()
    assert eq(neighbor2, msg_event1['src'])
    assert eq('', msg_event1['dst'])
    assert eq('ReceivedRequest', msg_event1['event'])
    assert eq(t_value, int(msg_event1['params']['request']))

    # Get internal message that was created by last call
    msg_pong = ts4.peek_msg()
    assert eq(neighbor2, msg_pong['src'])
    assert eq(neighbor1, msg_pong['dst'])
    assert eq('pong', msg_pong['method'])
    assert eq(t_value, int(msg_pong['params']['reply']))

    # Dispatch next message
    ts4.dispatch_one_message()

    # Pick up last event
    msg_event2 = ts4.pop_event()
    assert eq(neighbor1, msg_event2['src'])
    assert eq('', msg_event2['dst'])
    assert eq('ReceivedReply', msg_event2['event'])
    assert eq(t_value, int(msg_event2['params']['reply']))


def test2():
    # In most cases it is not necessary to control each message (while possible),
    # so here is the shorter version of the same scenario

    print('Starting call chain (in one step)...')
    t_value = 255
    contract1.call_method('ping_neighbor', dict(neighbor=neighbor2, value=t_value))

    # Dispatch all internal messages in one step
    ts4.dispatch_messages()

    # Skip first event
    ts4.pop_event()

    # Processing last event
    msg_event = ts4.pop_event()
    assert eq(neighbor1, msg_event['src'])
    assert eq('', msg_event['dst'])
    assert eq('ReceivedReply', msg_event['event'])
    assert eq(t_value, int(msg_event['params']['reply']))


# Set a directory where the artifacts of the used contracts are located
ts4.set_tests_path('contracts/')

# Toggle to print additional execution info
ts4.set_verbose(True)

# Deploy contracts
contract1 = ts4.BaseContract('tutorial04_1', {})
neighbor1 = contract1.address()
contract2 = ts4.BaseContract('tutorial04_2', {})
neighbor2 = contract2.address()

print('Contract 1 deployed at {}'.format(neighbor1))
print('Contract 2 deployed at {}'.format(neighbor2))

test1()

# Ensure we have no undispatched messages
ts4.ensure_queue_empty()

test2()
