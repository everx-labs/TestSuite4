"""
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
"""

'''

    This tutorial shows you how to check the balance
    of accounts with different states.

'''


import sys
sys.path.append('../ts4_py_lib')
import ts4
from ts4 import eq


# Set a directory where the artifacts of the used contracts are located
ts4.set_tests_path('contracts/')

# Toggle to print additional execution info
ts4.set_verbose(True)

# The address of a non-existing contract
empty_account = '0:c4a31362f0dd98a8cc9282c2f19358c888dfce460d93adb395fa138d61ae5069'

# Check balance of non-existing address
assert eq(None, ts4.core.get_balance(empty_account))

default_balance = 100 * ts4.GRAM

# Deploy the contract
tut08 = ts4.BaseContract('tutorial08', {})

# Сheck balance of the deployed contract. There are 100 grams by default
tut08.ensure_balance(default_balance)

# Another way to check the balance of contract
assert eq(default_balance, tut08.balance())
