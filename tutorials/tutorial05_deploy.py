"""
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
"""

'''

    This tutorial demonstrates how a contract can deploy another contracts.
    Besides, it shows how these contract can be accessed via wrappers.

'''


import sys
sys.path.append('../ts4_py_lib')
import ts4lib as ts4
from ts4lib import eq

# Set a directory where the artifacts of the used contracts are located
ts4.set_tests_path('contracts/')

# Toggle to print additional execution info
ts4.set_verbose(True)

# Load code and data of the second contract
code = ts4.core.load_code_cell('contracts/tutorial05_2.tvc')
data = ts4.core.load_data_cell('contracts/tutorial05_2.tvc')

# Deploy the first contract
contract1 = ts4.BaseContract('tutorial05_1', dict(code = code, data = data), nickname = 'contract1')

zero_address = '0:0000000000000000000000000000000000000000000000000000000000000000'
assert eq(zero_address, contract1.call_getter('m_address'))

# Ask contract1 to deploy contract2 with a given key
contract1.call_method('deploy', dict(key = 123))

# Fetch the address of the contract to be deployed
address2 = contract1.call_getter('m_address')

print('Deployed at {}'.format(address2))

# Dispatch unprocessed messages to actually construct a second contract
ts4.dispatch_messages()

# Create wrapper for already existing contract
contract2 = ts4.BaseContract('tutorial05_2', ctor_params = None, address = address2)

# Ensure the second contract has correct key and balance
assert eq(123, contract2.call_getter('m_key'))
assert eq(1_000_000_000, contract2.balance())
