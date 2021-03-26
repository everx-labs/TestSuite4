"""
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
"""

'''

    This tutorial demonstrates how to work with getters to receive different
    types of data (number, address, bool, bytes, string, array and struct).

'''


import tonos_ts4.ts4 as ts4

eq = ts4.eq

# Initialize TS4 by specifying where the artifacts of the used contracts are located
# verbose: toggle to print additional execution info
ts4.init('contracts/', verbose = False)

# Load a contract from .tvc-file and deploy it into a virtual blockchain.
# Constructor is called automatically.
# After deployment, "logstr: Constructor" will appear in the output to facilitate the debugging process.
tut01 = ts4.BaseContract('tutorial01', {})

# Call an integer getter and ensure that we received correct value
print("Fetching 'm_number'... ", end='')
expected_value = 3735928559
assert eq(expected_value, tut01.call_getter('m_number'))
print('ok')

# Call the getter and ensure that we received correct address
print("Fetching 'm_address'... ", end='')
expected_address = ts4.Address('0:c4a31362f0dd98a8cc9282c2f19358c888dfce460d93adb395fa138d61ae5069')
assert eq(expected_address, tut01.call_getter('m_address'))
print('ok')

# Call the getter and ensure that we received correct boolean value
print("Fetching 'm_bool'... ", end='')
assert eq(True, tut01.call_getter('m_bool'))
print('ok')

# Call string getter and check the returned value. We `bytes2str()` helper
# to decode string value from bytes
print("Fetching 'm_string'... ", end='')
assert eq('green tea', tut01.call_getter('m_string'))
print('ok')

# Working with bytes-type is very similar to working with strings
print("Fetching 'm_bytes'... ", end='')
assert eq('coffee', tut01.call_getter('m_bytes'))
print('ok')

# Call the getter and ensure that we received correct array value
print("Fetching 'm_array'... ", end='')
expected_array = [1, 2, 3, 4, 5]
assert eq(expected_array, tut01.call_getter('m_array'))
print('ok')

# Structures are represented as dictionaries on Python side
print("Fetching 'get_struct'... ", end='')
expected_struct = dict(
    s_number  = expected_value,
    s_address = expected_address,
    s_array   = expected_array
)
assert eq(expected_struct, tut01.call_getter('get_struct'))
print('ok')
