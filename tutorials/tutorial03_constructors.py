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
    tut = ts4.BaseContract('tutorial03_1', {})

    # Call a getter and ensure that we received correct integer value
    expected_value = 3735928559
    assert eq(expected_value, tut.call_getter('m_number'))


def test2():
    t_number = 12648430

    # Deploy a contract without constructing
    tut = ts4.BaseContract('tutorial03_2', ctor_params = None)
    #   and call constructor
    tut.call_method('constructor', {'t_number': t_number})

    # Call a getter and ensure that we received correct integer value
    assert eq(t_number, tut.call_getter('m_number'))


def test3():
    t_number = 3054

    # Deploy a contract with calling constructor
    tut = ts4.BaseContract('tutorial03_2', ctor_params = {'t_number': t_number})

    # Call a getter and ensure that we received correct integer value
    assert eq(t_number, tut.call_getter('m_number'))


def test4():
    (secret_key, public_key) = ts4.make_keypair()
    t_number = 14613198

    # Deploy a contract with given (by pubkey) owner
    tut = ts4.BaseContract('tutorial03_3', ctor_params = None, pubkey = public_key)
    tut.call_method('constructor', {'t_number': t_number}, secret_key)

    assert eq(t_number, tut.call_getter('m_number'))


# Set a directory where the artifacts of the used contracts are located
ts4.set_tests_path('contracts/')

# Toggle to print additional execution info
ts4.set_verbose(True)

test1()
test2()
test3()
test4()
