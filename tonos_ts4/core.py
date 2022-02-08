"""
    This file is part of Ever OS.

    Ever OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2022 (c) TON LABS
"""

import os
import sys
import json
import importlib

from . import globals
from . import ts4
from .util import *
from .address import Cell

###########################################################################
##  Public functions

def enable_fees(value):
    """Enables gas consumtion accounting in the balance.

    :param bool value: `True` to enable gas accounting
    """
    assert isinstance(value, bool)
    cfg = ts4.core.get_global_config()
    cfg.gas_fee = value
    ts4.core.set_global_config(cfg)

def set_balance(target, value):
    """Sets balance for a given account.

    :param Address target: Target address
    :param num value: Desired balance
    """
    ts4.ensure_address(target)
    ts4.core.set_balance(target.str(), int(value))

def set_trace_level(level):
    """Sets the trace level for `core`.

    :param num value: desired trace level. Set `0` to disable trace logging
    """
    cfg = ts4.core.get_global_config()
    cfg.trace_level = level
    ts4.core.set_global_config(cfg)

def set_trace_tvm(value):
    """Enables TVM tracing.

    :param bool value: `True` to enable TVM tracing
    """
    cfg = ts4.core.get_global_config()
    cfg.trace_tvm = value
    ts4.core.set_global_config(cfg)

def set_global_gas_limit(value):
    """Sets global gas limit.

    :param num value: Desired global gas limit
    """
    cfg = ts4.core.get_global_config()
    cfg.global_gas_limit = value
    ts4.core.set_global_config(cfg)

def get_cell_repr_hash(cell):
    """Calculates hash of a given `Cell`.

    :param Cell cell: Cell to be hashed
    :return: Hexadecimal representation of the hash of the given cell
    :rtype: str
    """
    assert isinstance(cell, Cell)
    return '0x' + ts4.core.get_cell_repr_hash(cell.raw_)


###########################################################################
##  Internal functions

class ExecutionResult:
    def __init__(self, result):
        assert isinstance(result, str)
        result = json.loads(result)
        # ts4.dump_struct(result)
        self.data       = result
        self.exit_code  = result['exit_code']
        self.actions    = result['out_actions']
        self.gas_used   = result['gas']
        self.error      = result['info']
        self.debot_answer_msg = result['debot_answer_msg']

def load_linker_lib():
    PACKAGE_DIR = os.path.basename(os.path.dirname(__file__))
    CORE = '.' + sys.platform + '.linker_lib'

    try:
        core = importlib.import_module(CORE, PACKAGE_DIR)
    except ImportError as err:
        print('Error: {}'.format(err))
        exit()
    except:
        print('Unsupported platform:', sys.platform)
        exit()
    return core

def dispatch_message_ext(msg_id):
    result = globals.core.dispatch_message(msg_id)
    return ExecutionResult(result)

def call_contract_ext(addr, method, params, is_getter = False, is_debot = False, private_key = None):
    assert isinstance(addr,   ts4.Address)
    assert isinstance(params, dict)
    result = globals.core.call_contract(
        addr.str(), method, is_getter, is_debot, ts4.json_dumps(params), private_key,
    )
    return ExecutionResult(result)

def call_ticktock_ext(addr, is_tock):
    result = globals.core.call_ticktock(addr.str(), is_tock)
    return ExecutionResult(result)

def deploy_contract_ext(contract, ctor_params, initial_data, pubkey, private_key, wc, override_address, balance):
    address = globals.core.deploy_contract(
        contract.tvc_path,
        contract.abi_path,
        ts4.json_dumps(ctor_params)  if ctor_params  is not None else None,
        ts4.json_dumps(initial_data) if initial_data is not None else None,
        pubkey,
        private_key,
        wc,
        override_address,
        balance,
    )
    return address

# __core__ = load_linker_lib()
