"""
    This file is part of Ever OS.

    Ever OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2023 (c) EverX
"""

QUEUE           = []
EVENTS          = []
ALL_MESSAGES    = []
NICKNAMES       = dict()

GRAM            = 1_000_000_000  # deprecated
EVER            = 1_000_000_000
EMPTY_CELL      = 'te6ccgEBAQEAAgAAAA=='

G_DEFAULT_BALANCE   = 100*EVER

G_TESTS_PATH    = 'contracts/'

G_VERBOSE               = False
G_AUTODISPATCH          = False
G_DUMP_MESSAGES         = False

G_SHOW_EVENTS           = False
G_SHOW_GETTERS          = False
G_SHOW_FULL_STACKTRACE  = False

G_STOP_AT_CRASH         = True
G_STOP_ON_NO_ACCEPT     = True
G_STOP_ON_NO_ACCOUNT    = True
G_STOP_ON_NO_FUNDS      = True

G_WARN_ON_UNEXPECTED_ANSWERS    = False
G_WARN_ON_ACCEPT_IN_GETTER      = True

G_CHECK_ABI_TYPES	    = True
G_GENERATE_GETTERS      = True

G_LAST_GAS_USED         = 0

G_MSG_FILTER            = None
G_ABI_FIXER             = None
G_OVERRIDE_EXPECT_EC    = None
G_SET_CONFIG_PARAMS     = False

core = None
version = None

def set_core(_core, _version):
    global core
    core = _core
    global version
    version = _version

def time_set(t):
    global now
    assert now <= t
    now = t
    assert core is not None
    core.set_now(now)

def time_get():
    global now
    return now

def time_shift(delta = 1):
    global now
    now += delta
    assert core is not None
    core.set_now(now)

def reset():
    global now
    now = 0
    assert core is not None
    core.reset_all()

def status(message):
    global now
    print('{0:>7}   {1}'.format(now, message))
