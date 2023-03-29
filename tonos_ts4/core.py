"""
    This file is part of Ever OS.

    Ever OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2023 (c) EverX
"""

import json

from . import globals
from .address import *
from .abi import *
from .util import *
from .dump import *
from .global_functions import *
from .exception import check_exitcode

###########################################################################
##  Public functions

def enable_fees(value):
    """Enables gas consumtion accounting in the balance.

    :param bool value: `True` to enable gas accounting
    """
    assert isinstance(value, bool)
    cfg = globals.core.get_global_config()
    cfg.gas_fee = value
    globals.core.set_global_config(cfg)

def set_balance(target, value):
    """Sets balance for a given account.

    :param Address target: Target address
    :param num value: Desired balance
    """
    ensure_address(target)
    globals.core.set_balance(target.str(), int(value))

def set_trace_level(level):
    """Sets the trace level for `core`.

    :param num value: desired trace level. Set `0` to disable trace logging
    """
    cfg = globals.core.get_global_config()
    cfg.trace_level = level
    globals.core.set_global_config(cfg)

def set_trace_tvm(value: bool):
    """Enables TVM tracing.

    :param bool value: `True` to enable TVM tracing
    """
    cfg = globals.core.get_global_config()
    cfg.trace_tvm = value
    globals.core.set_global_config(cfg)

def set_global_gas_limit(value):
    """Sets global gas limit.

    :param num value: Desired global gas limit
    """
    cfg = globals.core.get_global_config()
    cfg.global_gas_limit = value
    globals.core.set_global_config(cfg)

def get_cell_repr_hash(cell):
    """Calculates hash of a given `Cell`.

    :param Cell cell: Cell to be hashed
    :return: Hexadecimal representation of the hash of the given cell
    :rtype: str
    """
    assert isinstance(cell, Cell)
    return '0x' + globals.core.get_cell_repr_hash(cell.raw_)

###########################################################################
##  Internal functions

class ExecutionResult:
    def __init__(self, result):
        assert isinstance(result, str)
        result = json.loads(result)
        # dump_struct(result)
        self.data       = result
        self.exit_code  = result['exit_code']
        self.actions    = result['out_actions']
        self.gas_used   = result['gas']
        self.error      = result['info']
        self.debot_answer_msg = result['debot_answer_msg']

def dispatch_message_ext(msg_id):
    result = globals.core.dispatch_message(msg_id)
    return ExecutionResult(result)

# func contract getter
def run_get(addr, method, params):
    assert isinstance(addr, Address)
    assert isinstance(params, dict)
    result = globals.core.run_get(
        addr.str(), method, json_dumps(params),
    )
    result = json.loads(result)
    if len(result["out_actions"]) == 0:
        stack = result.get("stack")
        assert isinstance(stack, list)
        params = dict()
        for i in range(len(stack)):
            params["value%d" % i] = stack[i]

        result["out_actions"] = [json_dumps(dict(
            id = 1,
            parent_id = 0,
            msg_type = "answer",
            src = addr,
            dst = "",
            name = method,
            params = params,
            timestamp = globals.time_get(),
            log_str = ""
            # value = None,
        ))]
    result = json_dumps(result)
    return ExecutionResult(result)

def call_contract_ext(addr, method, params, is_getter = False, is_debot = False, private_key = None) -> ExecutionResult:
    assert isinstance(addr, Address)
    assert isinstance(params, dict)
    result = globals.core.call_contract(
        addr.str(), method, is_getter, is_debot, json_dumps(params), private_key,
    )
    return ExecutionResult(result)

def call_getter(addr, method, params, is_debot = False) -> str:
    assert isinstance(addr,   Address)
    assert isinstance(params, dict)
    return globals.core.call_getter(addr.str(), method, json_dumps(params), is_debot)

def call_ticktock_ext(addr, is_tock):
    result = globals.core.call_ticktock(addr.str(), is_tock)
    return ExecutionResult(result)

def deploy_contract_ext(contract, ctor_params, initial_data, pubkey, private_key, wc, override_address, balance):
    address = globals.core.deploy_contract(
        contract.tvc_path,
        contract.abi_path,
        json_dumps(ctor_params)  if ctor_params  is not None else None,
        json_dumps(initial_data) if initial_data is not None else None,
        pubkey,
        private_key,
        wc,
        override_address,
        balance,
    )
    return address

def parse_config_param(p: dict) -> Cell | None:
    assert isinstance(p, dict)
    cell = globals.core.parse_config_param(json_dumps(p))
    try:
        result = ExecutionResult(cell)
    except:
        return Cell(cell)
    check_exitcode([0], result.exit_code)
    return None

def gen_addr(name, initial_data = None, keypair = None, wc = 0):
    """Generates contract addresss.

    :param str name: Name used to load contract's bytecode and ABI
    :param dict initial_data: Initial data for the contract (static members)
    :param keypair: Keypair containing private and public keys
    :param num wc: workchain_id to deploy contract to
    :return: Expected contract address
    :rtype: Address
    """
    if keypair is not None:
        # TODO: copy-paste below!
        (private_key, pubkey) = keypair
        if pubkey is not None:
            assert pubkey[0:2] == '0x'
            pubkey = pubkey.replace('0x', '')
    else:
        (private_key, pubkey) = (None, None)

    abi = Abi(name)

    if initial_data is not None:
        initial_data = check_method_params(abi, '.data', initial_data)

    result = globals.core.gen_addr(
        make_path(name, '.tvc'),
        abi.path_,
        json_dumps(initial_data) if initial_data is not None else None,
        pubkey,
        private_key,
        wc
    )
    return Address(result)

def encode_message_body(address: Address, abi_name: str, method, params):
    """Encode given message body.

    :param str abi_name: The contract name the ABI of which should be used for encoding
    :param str method: A name of the encoded method
    :param dict params: A dictionary with parameters for the encoded method
    :return: Cell object containing encoded message
    :rtype: Cell
    """
    assert isinstance(abi_name, str)
    assert isinstance(address, Address)
    abi_file = abi_name
    encoded = globals.core.encode_message_body(
        address.str(),
        abi_file,
        method,
        json_dumps(params)
    )
    return Cell(encoded)

def build_int_msg(src, dst, abi_file, method, params, value):
    """Creates an internal message representing the given call.

    :param Address src: Source address
    :param Address dst: Destination address
    :param Address abi_file: The name of the destination contract whose ABI should be used for encoding message
    :param str method: A name of the encoded method
    :param dict params: A dictionary with parameters for the encoded method
    :param num value: Desired message value
    :return: Msg object containing encoded message
    :rtype: Msg
    """
    assert isinstance(src, Address)
    assert isinstance(dst, Address)

    msg_body = encode_message_body(src, abi_file, method, params)

    # src = zero_addr(-1)
    msg = globals.core.build_int_msg(src.str(), dst.str(), msg_body.raw_, value)
    # verbose_(msg)
    msg = Msg(json.loads(msg))
    verbose_(msg)
    globals.QUEUE.append(msg)
    return msg
