"""
    This file is part of Ever OS.

    Ever OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
"""

'''

    This tutorial demonstrates how a contract can deploy another contract.
    Besides, it shows how these contract can be accessed via wrappers.

'''


from tonos_ts4 import ts4

eq = ts4.eq

# Initialize TS4 by specifying where the artifacts of the used contracts are located
# verbose: toggle to print additional execution info
ts4.init('contracts/', verbose = True)

# Load code and data of the second contract
code = ts4.load_code_cell('tutorial05_2.tvc')
data = ts4.load_data_cell('tutorial05_2.tvc')

# Register ABI of the second contract in the system beforehand
ts4.register_abi('tutorial05_2')

# Deploy the first contract and register nickname to be used in the output
contract1 = ts4.BaseContract('tutorial05_1', dict(code = code, data = data), nickname = 'Parent')

zero_address = ts4.Address('0:' + '0'*64)
assert eq(zero_address, contract1.call_getter('m_address'))

# Ask contract1 to deploy contract2 with a given key
contract1.call_method('deploy', dict(key = 123))

# Fetch the address of the contract to be deployed
address2 = contract1.call_getter('m_address')
ts4.Address.ensure_address(address2)

# We register nickname for this contract so see it in the verbose output
ts4.register_nickname(address2, 'Child')

print('Deploying at {}'.format(address2))

# Dispatch unprocessed messages to actually construct a second contract
ts4.dispatch_messages()

# At this point contract2 is deployed at a known address,
# so we create a wrapper to access it.
contract2 = ts4.BaseContract('tutorial05_2', ctor_params = None, address = address2)

# Ensure the second contract has correct key and balance
assert eq(123, contract2.call_getter('m_key'))
assert eq(1_000_000_000, contract2.balance)
