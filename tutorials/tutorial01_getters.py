"""
    This file is part of Ever OS.

    Ever OS is free software: you can redistribute it and/or modify
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
print("Fetching 'm_number'   : ", end='')
expected_value = 3735928559
answer = tut01.call_getter('m_number')
print(ts4.cyan(answer))
assert eq(expected_value, answer)

# Call the getter and ensure that we received correct address
print("Fetching 'm_address'  : ", end='')
expected_address = ts4.Address('0:c4a31362f0dd98a8cc9282c2f19358c888dfce460d93adb395fa138d61ae5069')
answer = tut01.call_getter('m_address')
print(ts4.cyan(answer))
assert eq(expected_address, answer)

# Call the getter and ensure that we received correct boolean value
print("Fetching 'm_bool'     : ", end='')
answer = tut01.call_getter('m_bool')
print(ts4.cyan(answer))
assert eq(True, answer)

# Call string getter and check the returned value
print("Fetching 'm_string'   : ", end='')
answer = tut01.call_getter('m_string')
print(ts4.cyan(answer))
assert eq('green tea', answer)

# Working with bytes-type is very similar to working with strings
print("Fetching 'm_bytes'    : ", end='')
answer = tut01.call_getter('m_bytes')
print(ts4.cyan(answer))
assert eq('coffee', answer)

# Call the getter and ensure that we received correct array value
print("Fetching 'm_array'    : ", end='')
answer = tut01.call_getter('m_array')
print(ts4.cyan(answer))
expected_array = [1, 2, 3, 4, 5]
assert eq(expected_array, answer)

# Structures are represented as dictionaries on Python side
print("Fetching 'm_struct'   : ", end='')
answer = tut01.call_getter('m_struct')
print(ts4.cyan(answer))
expected_struct = dict(
    s_number  = expected_value,
    s_address = expected_address,
    s_array   = expected_array
)
assert eq(expected_struct, answer)

# Now consider getters returning tuples. Tuples are mapped to python tuples by default
print("Fetching 'get_tuple'  : ", end='')
answer = tut01.call_getter('get_tuple')
print(ts4.cyan(answer))
assert eq((111,222,333), answer)

# But if you want to obtain a named structure, you can use `decoder` parameter
expected_dict = dict(one = 111, two = 222, three = 333)
assert eq(expected_dict, tut01.call_getter('get_tuple', decoder = ts4.Decoder(tuples = False)))

# Alternatively you can set this mode globally
ts4.decoder.tuples = False
assert eq(expected_dict, tut01.call_getter('get_tuple'))

# mappings
print("Fetching 'm_uint_addr':")

exp = tut01.call_getter('m_uint_addr')
[print(ts4.cyan(f'    {i} => {exp[i]}')) for i in exp]
assert eq(expected_address, exp[expected_value])
