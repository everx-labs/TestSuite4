"""
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
"""

'''

    This tutorial demonstrates the different variants for working with the constructor.

'''


import tonos_ts4.ts4 as ts4

eq = ts4.eq


def test1():
    # Deploy a contract. Constructor is called automatically.
    tut = ts4.BaseContract('tutorial03_1', {})

    # Call a getter and ensure that we received correct integer value
    expected_value = 3735928559
    assert eq(expected_value, tut.call_getter('m_number'))


def test2():
    t_number = 12648430

    # Deploy a contract without construction
    tut = ts4.BaseContract('tutorial03_2', ctor_params = None)

    # And construct it manually with an external message
    tut.call_method('constructor', {'t_number': t_number})

    # Call a getter and ensure that we received correct integer value
    assert eq(t_number, tut.call_getter('m_number'))


def test3():
    t_number = 3054

    # Deploy a contract with calling constructor (offchain)
    tut = ts4.BaseContract('tutorial03_2', ctor_params = {'t_number': t_number})

    # Call a getter and ensure that we received correct integer value
    assert eq(t_number, tut.call_getter('m_number'))


def test4():
    (private_key, public_key) = ts4.make_keypair()
    t_number = 14613198

    # Deploy a contract with given (by pubkey) owner.
    # Private key is needed here only when constructor checks 
    # that message is signed.
    tut = ts4.BaseContract('tutorial03_3', 
        ctor_params = dict(t_number = t_number), 
        pubkey      = public_key, 
        private_key = private_key
    )

    assert eq(t_number, tut.call_getter('m_number'))


# Initialize TS4 by specifying where the artifacts of the used contracts are located
# verbose: toggle to print additional execution info
ts4.init('contracts/', verbose = True)

test1()
test2()
test3()
test4()
