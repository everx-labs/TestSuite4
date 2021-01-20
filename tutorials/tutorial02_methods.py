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
    # Deploy a contract
    tut02 = ts4.BaseContract('tutorial02', {})

    t_number = 3735928559
    # Call method to set integer value
    tut02.call_method('set_number', {'value': t_number})
    # Call a getter and ensure that we received correct integer value
    assert eq(t_number, tut02.call_getter('m_number'))

    t_address = '0:c4a31362f0dd98a8cc9282c2f19358c888dfce460d93adb395fa138d61ae5069'
    # Call method to set address
    tut02.call_method('set_address', {'value': t_address})
    # Call the getter and ensure that we received correct address
    assert eq(t_address, tut02.call_getter('m_address'))

    t_bool = True
    # Call method to set boolean value
    tut02.call_method('set_bool', {'value': t_bool})
    # Call the getter and ensure that we received correct boolean value
    assert eq(t_bool, tut02.call_getter('m_bool'))

    # A Solidity contracts requires that string values be passed as a hex
    t_string = 'coffee'
    # Call method to set string value. We need to use `str2bytes` helper for strings
    tut02.call_method('set_string', {'value': ts4.str2bytes(t_string)})
    # Call the getter and ensure that we received correct string value
    #   returned string values encoded as a hex, so we need to decode it.
    assert eq(t_string, ts4.bytes2str(tut02.call_getter('m_string')))

    t_array = [1, 2, 3, 4, 5]
    # Call method to set array
    tut02.call_method('set_array', {'value': t_array})
    # Call the getter and ensure that we received correct array
    assert eq(t_array, tut02.call_getter('m_array'))


# Set a directory where the artifacts of the used contracts are located
ts4.set_tests_path('contracts/')

# Toggle to print additional execution info
ts4.set_verbose(True)

# Run a test
test1()
