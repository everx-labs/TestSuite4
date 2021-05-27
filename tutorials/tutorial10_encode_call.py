"""
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
"""

'''

    This tutorial demonstrates how to encode a payload for use in a transfer function call

'''


from tonos_ts4 import ts4

eq = ts4.eq

# Initialize TS4 by specifying where the artifacts of the used contracts are located
# verbose: toggle to print additional execution info
ts4.init('contracts/', verbose = True)

# Deploy a contract (encoder/sender)
sender = ts4.BaseContract('tutorial10_1', {})

# Register nickname to be used in the output
ts4.register_nickname(sender.address, 'Sender')

# Deploy a contract (receiver)
receiver = ts4.BaseContract('tutorial10_2', {})
ts4.register_nickname(receiver.address, 'Receiver')

# Ensure that current value in the receiver contract is default
assert eq(0, receiver.call_getter('m_value'))

value = 0xbeaf
# Encode calling of the receiver contract
payload = sender.call_getter('encode', {'value': value})

# Call receiver contract's method via sender contract
sender.call_method('call_it', {'dest': receiver.address, 'payload': payload})

# Dispatch created internal message from sender to receiver
ts4.dispatch_one_message()

# Ensure that current value was set
assert eq(value, receiver.call_getter('m_value'))
