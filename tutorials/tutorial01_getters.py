"""
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
"""

import sys
sys.path.append('../ts4_py_lib')
import ts4lib as ts4
from ts4lib import eq


def test1():
    # Deploy a contract
    tut01 = ts4.BaseContract('tutorial01', {})

    # Call a getter and ensure that we received correct integer value
    print("Fetching 'm_number'... ", end='')
    assert eq(3735928559, tut01.call_getter('m_number'))
    print('ok')

    # Call the getter and ensure that we received correct address
    print("Fetching 'm_address'... ", end='')
    expected_address = '0:c4a31362f0dd98a8cc9282c2f19358c888dfce460d93adb395fa138d61ae5069'
    assert eq(expected_address, tut01.call_getter('m_address'))
    print('ok')

    # Call the getter and ensure that we received correct boolean value
    print("Fetching 'm_bool'... ", end='')
    assert eq(True, tut01.call_getter('m_bool'))
    print('ok')

    # Call the getter and ensure that we received correct bytes value
    #   we use `bytes2str()` helper to decode string value from bytes
    print("Fetching 'm_bytes'... ", end='')
    assert eq('coffee', ts4.bytes2str(tut01.call_getter('m_bytes')))
    print('ok')


# Set a directory where the artifacts of the used contracts are located
ts4.set_tests_path('contracts/')

# Toggle to print additional execution info
ts4.set_verbose(True)

# Run a test
test1()
