"""
    This file is part of Ever OS.

    Ever OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2022 (c) TON LABS
"""

'''
    This tutorial demonstrates working with a simple helloworld debot.
'''

from tonos_ts4.debotlib import *

# Initialize TS4 system
ts4.init('contracts', verbose = False)

# Create debots context
ctx = DebotContext()
ctx.auto_dispatch = True

# Load and start debot
debot = ctx.load_debot('helloDebot', 'debot')

# Expect given print
ctx.expect_print('Hello, World!')

# Expect given input and send answer
ctx.expect_input('How is it going?', 'WOW!!!')

# Expect debot's print
ctx.expect_print('You entered "WOW!!!"')

