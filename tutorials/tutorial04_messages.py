"""
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
"""

'''

    This tutorial shows how to dispatch internal messages between contracts,
    as well as how to catch events fired by a contract.

'''


import tonos_ts4.ts4 as ts4

eq = ts4.eq


def test1():
    # In this scenario we are processing messages step by step

    print('Starting call chain (step by step)...')
    t_value = 4276994270
    contract1.call_method('ping_neighbor', dict(neighbor=neighbor2, value=t_value))

    # Get internal message that was created by previous call
    msg_ping = ts4.peek_msg()
    print(msg_ping)
    assert eq(neighbor1, msg_ping.src)
    assert eq(neighbor2, msg_ping.dst)
    assert msg_ping.is_call('ping')
    assert eq(t_value, int(msg_ping.params['request']))

    # Dispatch created message
    ts4.dispatch_one_message()

    # Pick up event that was created by called method of the callee contract
    msg_event1 = ts4.pop_event()
    # Ensure that dst address is empty
    assert msg_event1.dst.empty()
    assert msg_event1.is_event('ReceivedRequest', neighbor2)
    assert eq(t_value, int(msg_event1.params['request']))

    # Get internal message that was created by last call
    msg_pong = ts4.peek_msg()
    assert eq(neighbor2, msg_pong.src)
    assert eq(neighbor1, msg_pong.dst)
    assert msg_pong.is_call('pong')
    assert eq(t_value, int(msg_pong.params['reply']))

    # Dispatch next message
    ts4.dispatch_one_message()

    # Pick up last event
    msg_event2 = ts4.pop_event()
    # Ensure that dst address is empty (other variant)
    assert eq(ts4.Address(None), msg_event2.dst)
    assert msg_event2.is_event('ReceivedReply', neighbor1)
    assert eq(t_value, int(msg_event2.params['reply']))


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
    # Ensure that dst address is empty (one more variant)
    assert eq(ts4.Address(''), msg_event.dst)
    assert msg_event.is_event('ReceivedReply', neighbor1)
    assert eq(t_value, int(msg_event.params['reply']))


# Set a directory where the artifacts of the used contracts are located
ts4.set_tests_path('contracts/')

# Toggle to print additional execution info
ts4.set_verbose(True)

# Deploy contracts
contract1 = ts4.BaseContract('tutorial04_1', {})
neighbor1 = contract1.addr()
contract2 = ts4.BaseContract('tutorial04_2', {})
neighbor2 = contract2.addr()

# Register nicknames to be used in the output
ts4.register_nickname(neighbor1, 'Alice')
ts4.register_nickname(neighbor2, 'Bob')

print('Contract 1 deployed at {}'.format(neighbor1))
print('Contract 2 deployed at {}'.format(neighbor2))

test1()

# Ensure we have no undispatched messages
ts4.ensure_queue_empty()

test2()
