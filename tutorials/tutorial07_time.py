"""
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
"""

'''

    This tutorial demonstrates how you can change the current time that the TVM uses

'''


import time
import tonos_ts4.ts4 as ts4

eq = ts4.eq

# Set a directory where the artifacts of the used contracts are located
ts4.set_tests_path('contracts/')

# Toggle to print additional execution info
ts4.set_verbose(True)

now = int(time.time())
# TS4 uses either real-clock or virtual time. Once you can core.set_now() you switch
#   to virtual time mode, where you can move time to future on your own
ts4.core.set_now(now)

# Deploy a contract
tut07 = ts4.BaseContract('tutorial07', {})

# Call the getter and ensure that the required time has not yet arrived
assert eq(False, tut07.call_getter('isUnlocked'))

DAY = 86400
# Fast forward 7 days
ts4.core.set_now(now + 7 * DAY)

# ... and ensure that the required time has come
assert eq(True, tut07.call_getter('isUnlocked'))

# P.S. Traveling into the future is easy. Isn't it?
