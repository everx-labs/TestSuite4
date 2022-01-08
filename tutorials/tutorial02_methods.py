"""
    This file is part of Ever OS.

    Ever OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
"""

'''

    This tutorial demonstrates how to work with external methods
    for passing various types of parameters (number, address, bool, bytes,
    string, array, struct).

'''


import tonos_ts4.ts4 as ts4

eq = ts4.eq


def test1():
    # Deploy a contract to virtual blockchain
    tut02 = ts4.BaseContract('tutorial02', {})

    # Call method to set integer value
    t_number = 3735928559
    tut02.call_method('set_number', {'value': t_number})
    # Call a getter and ensure that we received correct integer value
    assert eq(t_number, tut02.call_getter('m_number'))

    # Call method to set address
    t_address = ts4.Address('0:c4a31362f0dd98a8cc9282c2f19358c888dfce460d93adb395fa138d61ae5069')
    tut02.call_method('set_address', {'value': t_address})
    assert eq(t_address, tut02.call_getter('m_address'))

    # Call method to set boolean value
    t_bool = True
    tut02.call_method('set_bool', {'value': t_bool})
    assert eq(t_bool, tut02.call_getter('m_bool'))

    # Call method to set bytes value. In ABI `bytes` type is represented as a hex string
    t_bytes = ts4.Bytes('d090d091d092')
    tut02.call_method('set_bytes', {'value': t_bytes})
    assert eq(t_bytes, tut02.call_getter('m_bytes'))

    # String values are automatically converted to hex back and forth
    t_string = 'coffeeАБВ'
    tut02.call_method('set_string', {'value': t_string})
    # Call the getter and ensure that we received correct string value.
    assert eq(t_string, tut02.call_getter('m_string'))

    # Call method to set array.
    t_array = [1, 2, 3, 4, 5]
    tut02.call_method('set_array', {'value': t_array})
    assert eq(t_array, tut02.call_getter('m_array'))

    # Check using structures
    t_struct = dict(
        s_number = t_number,
        s_address = t_address,
        s_array = t_array
    )
    tut02.call_method('set_struct', {'someStruct': t_struct})
    assert eq(t_struct, tut02.call_getter('get_struct'))


# Initialize TS4 by specifying where the artifacts of the used contracts are located
# verbose: toggle to print additional execution info
ts4.init('contracts/', verbose = True)

# Run a test
test1()
