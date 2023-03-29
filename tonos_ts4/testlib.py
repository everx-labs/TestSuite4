"""
    This file is part of Ever OS.

    Ever OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2022 (c) TON LABS
"""

import tonos_ts4.ts4 as ts4
from tonos_ts4.ts4 import verbose_, eq, leq, GRAM, BaseContract
# eq = ts4.eq
# GRAM = ts4.GRAM
# BaseContract = ts4.BaseContract

def events_queue_size():
    return len(ts4.globals.EVENTS)

def reset_all():
    ts4.ensure_queue_empty()
    assert eq(0, events_queue_size())
    ts4.reset_all()

def start_test(tag : str):
    tag = ' {} '.format(tag)
    N = 80
    while len(tag) < N:
        if len(tag) < N: tag = '*' + tag
        if len(tag) < N: tag = tag + '*'
    print(ts4.colorize(ts4.BColors.HEADER, tag))
    reset_all()
