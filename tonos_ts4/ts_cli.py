"""
    This file is part of Ever OS.

    Ever OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2023 (c) EverX
"""

import base64
import json
import os
import os.path
import shutil
import subprocess
import time

from address   import *
from abi       import *
from core      import *
from decoder   import *
from dump      import *
from globals   import EMPTY_CELL, core
from util      import *
from global_functions  import *

class GlobalConfig:
    def __init__(self):
        self.trace_tvm = None

class ContractDescription:
    def __init__ (self, tvc_path, abi_path, boc_path, dbg_path, key_path):
        self.tvc_path = tvc_path
        self.abi_path = abi_path
        self.boc_path = boc_path
        self.dbg_path = dbg_path
        self.key_path = key_path

class Core:
    def __init__(self) -> None:
        self.temp_path = ""
        self.contracts = dict()
        self.messages = dict()
        self.last_error = None
        self.config_path = None
        self.config_key = "18ba321b20fd6df7e317623b7109bc0c30717d783a2ad54407dc116ff614cfcfd189e68c5465891838ef026302f97e28127a8bf72f6bf494991fe8c12e466180"
        self.global_config = GlobalConfig()

    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(Core, cls).__new__(cls)
        else:
            3/0
        return cls.instance

    def reset_all(self):
        # TODO: need to clean path after finish tests on clean previous on reset_all
        self.temp_path = "debug/" + str(int(time.time()))
        os.makedirs(self.make_temp_path("keys"), exist_ok=True)
        os.makedirs(self.make_temp_path("msgs"), exist_ok=True)
        os.makedirs(self.make_temp_path("bocs"), exist_ok=True)
        os.makedirs(self.make_temp_path("trns"), exist_ok=True)
        self.contracts = dict()
        self.messages = dict()
        self.last_error = None
        self.config_path = shutil.copy(make_path("bc_config", ".boc"), self.make_temp_path("bocs/bc_config.boc"))
        self.global_config = GlobalConfig()

    def set_now(self, _now):
        pass

    def get_global_config(self) -> GlobalConfig:
        return self.global_config

    def set_global_config(self, config: GlobalConfig):
        self.global_config = config

    def make_temp_path(self, name, extension = "") -> str:
        return make_path(self.temp_path + "/" + name, extension)
    
    def set_config(self, config):
        # we no need this method because we are using real config contract
        print(yellow('we no need new config'), config)

    def set_config_param(self, index, value):
        assert isinstance(self.config_path, str)
        assert os.path.exists(self.config_path)
        abi_path = make_path('config', ".abi.json")
        assert os.path.exists(abi_path)
        cli_params = ["debug", "call", "--abi", abi_path, "--update"]
        self.add_now_param(cli_params, 1)
        self.add_config_param(cli_params, "--config")
        self.add_temp_keys_param(cli_params, self.config_key)
        method = "set_config_param"
        cli_params += ["--boc", "--addr", self.config_path, "--method", method]
        self.add_method_params(cli_params, value)
        result = self.run_tonos_cli(cli_params)
        return self.parse_execution_result("bc_config", result, method)

    def add_config_param(self, cli_params, name = "--bc_config"):
        if self.config_path is not None and os.path.exists(self.config_path):
            cli_params += [name, self.config_path]

    def add_method_params(self, cli_params, params: str, name = None):
        if params is not None and params != "{}":
            assert isinstance(params, str)
            params_path = self.make_temp_path("params", ".json")
            with open(params_path, 'wt') as fp:
                fp.write(params)
            # if ctor_name is not None:
            #     cli_params += ["--method", ctor_name]
            if name is not None:
                cli_params += [name]
            cli_params += [params_path]

    def add_keys_param(self, cli_params, key_path = None):
        if key_path is not None:
            cli_params += ["--keys", key_path]

    def add_temp_keys_param(self, cli_params, private_key):
        if private_key is None:
            return
        assert eq(128, len(private_key))
        keys = json_dumps(dict(
            secret = private_key[:64],
            public = private_key[64:]
        ))
        assert isinstance(keys, str)
        key_path = self.store_keys("sign", keys)
        self.add_keys_param(cli_params, key_path)
        # cli_params += ["--keys", key_path]

    def add_now_param(self, cli_params, shift = 0):
        cli_params += ["--now", str(globals.now * 1000 + shift)]

    def add_output_param(self, cli_params, dbg_path):
        if self.global_config.trace_tvm is None:
            output_path = "nul"
        else:
            if self.global_config.trace_tvm:
                cli_params += ["--full_trace"]
            output_path = make_path("trace", ".log")
        if dbg_path is not None:
            cli_params += ["--dbg_info", dbg_path]

        cli_params += ["--output", output_path]

    def generate_address(self, name: str, wc = -1) -> str:
        abi_path = make_path(name, ".abi.json")
        tvc_path = make_path(name, ".tvc")
        cli_params = ["genaddr", "--abi", abi_path, "--wc", str(wc), tvc_path]
        return self.run_tonos_cli(cli_params)["raw_address"]

    def store_keys(self, name: str, keys: str) -> str:
        key_path = self.make_temp_path("keys/" + name, '.json')
        with open(key_path, "wt") as f:
            f.write(keys)
        return key_path

    def deploy_contract(self, tvc_name: str, abi_name, ctor_params: str, initial_data, pubkey, private_key, wc, override_address, balance) -> str:
        (_, name) = os.path.split(tvc_name)
        (name, _) = os.path.splitext(name)
        # TODO: problems with WC
        assert eq(-1, wc)
        # TODO: we never use private key
        assert private_key is None
        assert initial_data is None

        address = override_address if override_address is not None else self.generate_address(name, wc)
        assert self.contracts.get(address) is None

        abi_path = shutil.copy(make_path(name, '.abi.json'), self.make_temp_path("bocs/" + name, '.abi.json'))
        boc_path = self.make_temp_path("bocs/" + name, '.boc')
        dbg_path = shutil.copy(make_path(name, '.debug.json'), self.make_temp_path("bocs/" + name, '.debug.json'))
        tvc_path = shutil.copy(make_path(name, '.tvc'), self.make_temp_path("bocs/" + name, '.tvc'))

        if pubkey is not None:
            keys = json_dumps(dict(
                secret = private_key[:64] if private_key is not None else '0' * 64,
                public = pubkey,
            ))
            key_path = self.store_keys(address.replace(':', '-'), keys)
        else:
            key_path = None

        cli_params = ["test", "deploy", tvc_path, "--abi", abi_path, "--address", address]
        cli_params += ["--initial_balance", str(balance)]
        self.add_now_param(cli_params)
        self.add_keys_param(cli_params, key_path)
        self.add_output_param(cli_params, dbg_path)
        self.add_config_param(cli_params)
        self.add_method_params(cli_params, ctor_params, "--params")
        result = self.run_tonos_cli(cli_params)

        # analyze result
        self.parse_execution_result(address, result, None, abi_path)
        assert os.path.exists(boc_path)
        if pubkey is not None:
            boc_path = shutil.move(boc_path, boc_path.removesuffix(".boc") + "-" + pubkey[:8] + ".boc")
        # if name.startswith('Config'):
        #     self.config_path = boc_path
        # TODO: we don't story keys if no private
        # TODO: don't store tvc_path
        self.contracts[address] = ContractDescription(tvc_path, abi_path, boc_path, dbg_path, key_path)
        return address
    
    def load_account_state(self, address: str, boc_path: str, abi_path: str):
        assert os.path.exists(boc_path)
        _, name = os.path.split(boc_path)
        boc_path = shutil.copy(boc_path, self.make_temp_path("bocs/" + name))
        name = name.split('.', 1)[0]
        abi_path = make_path(name, '.abi.json')
        dbg_path = make_path(name, '.debug.json')
        if os.path.exists(dbg_path):
            dbg_path = shutil.copy(dbg_path, self.make_temp_path("bocs/" + name, '.debug.json'))
        else:
            dbg_path = None
        if os.path.exists(abi_path):
            abi_path = shutil.copy(abi_path, self.make_temp_path("bocs/" + name, '.abi.json'))
        else:
            abi_path = None
        self.contracts[address] = ContractDescription(None, abi_path, boc_path, dbg_path, None)
    
    def call_contract(self, address: str, method: str, is_getter, is_debot, params: str, private_key: str | None = None) -> str:
        if is_getter:
            assert private_key is None
            return self.call_getter(address, method, params, is_debot)
        descr = self.get_contract(address)
        cli_params = ["debug", "call", "--abi", descr.abi_path, "--update"]
        self.add_now_param(cli_params, 1)
        self.add_output_param(cli_params, descr.dbg_path)
        self.add_config_param(cli_params, "--config")
        self.add_temp_keys_param(cli_params, private_key)
        cli_params += ["--boc", "--addr", descr.boc_path, "--method", method]
        self.add_method_params(cli_params, params)
        result = self.run_tonos_cli(cli_params)
        return self.parse_execution_result(address, result, method)

    def call_getter(self, address: str, method: str, params: str, is_debot = False) -> str:
        descr = self.get_contract(address)
        cli_params = ["runx", "--boc", "--abi", descr.abi_path]
        # self.add_config_param(cli_params) # TODO: here problem - need config params
        cli_params += ["--addr", descr.boc_path, "--method", method, params]
        result = self.run_tonos_cli(cli_params)
        error = result.get("Error")
        if error is not None:
            return self.parse_error(error)
        msg = json_dumps(dict(
            id = "getter",
            name = method,
            params = result,
            src = address,
            dst = None,
            msg_type = "answer",
            timestamp = globals.now,
            log_str = None,
        ))
        result = json_dumps(dict(
            exit_code = 0,
            out_actions = [msg],
            gas = 0,
            info = None,
            debot_answer_msg = None,
            accept_in_getter = False,
        ))
        return result

    def call_ticktock(self, address: str, is_tock = False) -> str:
        descr = self.get_contract(address)
        cli_params = ["test", "ticktock", descr.boc_path]
        if is_tock:
            cli_params = ["--tock"]
        self.add_now_param(cli_params)
        self.add_config_param(cli_params)
        self.add_output_param(cli_params, descr.dbg_path)
        result = self.run_tonos_cli(cli_params)
        return self.parse_execution_result(address, result)

    def encode_message_body(self, address: str, abi_path: str, method: str, params: str) -> str:
        assert isinstance(address, str)
        descr = self.get_contract(address)
        cli_params = ["body", "--abi", descr.abi_path, method, params]
        result = self.run_tonos_cli(cli_params)
        body = result.get("Message")
        if body is not None:
            return body
        return self.parse_execution_result(address, result)
    
    def send_external_message(self, address: str, msg_base64: str):
        descr = self.get_contract(address)
        msg_path = self.make_temp_path("msgs/temp" +str(globals.now), '.boc')
        with open(msg_path, 'wb') as fp:
            fp.write(base64.b64decode(msg_base64))

        cli_params = ["debug", "message", msg_path, "--boc", "--addr", descr.boc_path, "--update"]
        self.add_config_param(cli_params, "--config")
        self.add_output_param(cli_params, descr.dbg_path)
        self.add_now_param(cli_params)

        result = self.run_tonos_cli(cli_params)
        return self.parse_execution_result(address, result)

    def dispatch_message(self, id: str) -> str:
        assert eq(64, len(id))
        (msg_path, address) = self.messages[id]
        return self.process_message(msg_path, address)
    
    def process_message(self, msg_path, address) -> str:
        descr = self.get_contract(address)
        cli_params = ["debug", "message", "--update"]
        self.add_config_param(cli_params, "--config")
        self.add_output_param(cli_params, descr.dbg_path)
        self.add_now_param(cli_params, 1)
        cli_params += ["--boc", "--addr", descr.boc_path, msg_path]
        result = self.run_tonos_cli(cli_params)
        return self.parse_execution_result(address, result)

    def parse_error(self, error) -> str:
        if isinstance(error, str):
            exit_code = -1
            self.last_error = error
        else:
            code = error.get("code")
            if code == 414:
                exit_code = error["data"]["exit_code"]
                # TODO: self.last_error = error["message"]
            else:
                exit_code = error["exit_code"]
            self.last_error = error.get("message")
            
        result = dict(
            exit_code = exit_code,
            out_actions = [],
            gas = [],
            debot_answer_msg = None,
            accept_in_getter = False,
            info = None,
        )
        return json_dumps(result)

    def parse_execution_result(self, address: str | None, result: dict, name: str | None = None, abi_path: str | None = None) -> str:
        error = result.get("Error")
        if error is not None:
            return self.parse_error(error)

        out_actions = []
        messages = result.get("messages")
        tr = result.get("transaction")
        if tr is not None:
            self.write_transaction(tr)
            if int(tr["total_fees"]) != 0:
                print(yellow("fees!!!"), tr["total_fees"], tr["id"])
                raise
        if messages is not None:
            for description in messages:
                msg = self.parse_message(address, description)
                out_actions.append(msg)
        description = result.get("description")
        if description is not None:
            exit_code = description["exit_code"]
            gas = description["gas_usage"]
            in_msg = description.get("in_msg")
            if in_msg is not None:
                result = self.decode_message(in_msg, abi_path)
                print(result)
            total_fees = description["total_fees"]
            if total_fees is not None and int(total_fees) != 0:
                print(yellow("fees!!!"), total_fees)
        else:
            exit_code = 0
            gas = 0
        result = dict(
            exit_code = exit_code,
            out_actions = out_actions,
            gas = gas,
            info = None,
            debot_answer_msg = None,
            accept_in_getter = False,
        )
        return json_dumps(result)

    def parse_message(self, address: str | None, description: dict) -> str:
        header = description["Header"]
        src = header["source"]
        assert eq(address, src)
        dst = header["destination"]
        abi_path = self.get_contract(dst).abi_path
        msg_base64 = description["Message_base64"]
        id = description["id"]
        msg_path = self.make_temp_path("msgs/" + id, '.boc')
        self.messages[id] = (msg_path, dst)
        with open(msg_path, 'wb') as fp:
            fp.write(base64.b64decode(msg_base64))
        result = self.decode_message(msg_path, abi_path)
        body = result.get("BodyCall", None)
        if body is not None and isinstance(body, dict):
            msg_type = "call"
            (name, params) = body.popitem()
        else:
            msg_type = "empty"
            name = None
            params = dict()

        return json_dumps(dict(
            id = id,
            value = int(header["value"]),
            bounced = header["bounced"],
            src = src,
            dst = dst,
            timestamp = header["created_at"],
            log_str = None,
            msg_type = msg_type,
            name = name,
            params = params
        ))

    def write_transaction(self, tr: dict):
        if self.global_config.trace_tvm:
            id = tr["id"][:8]
            trns_path = self.make_temp_path("trns/" + id, ".json")
            with open(trns_path, "w") as f:
                f.write(json_dumps(tr, 2))

    def get_msg_body(self, id: str) -> str:
        (msg_path, address) = self.messages[id]
        with open(msg_path, 'rb') as fp:
            return base64.b64encode(fp.read(1_000_000)).decode('utf-8')
        
    def get_last_error_msg(self) -> str | None:
        return self.last_error

    def sign_cell_hash(self, cell: str, private_key: str) -> str:
        return self.sign_cell(cell, private_key)

    def sign_cell(self, cell: str, private_key: str) -> str:
        assert isinstance(cell, str)
        assert isinstance(private_key, str)
        cli_params = ["test", "sign", "--cell", cell]
        self.add_temp_keys_param(cli_params, private_key)
        result = self.run_tonos_cli(cli_params)
        signature = result.get("Signature")
        if signature is not None:
            return base64_to_hex(signature)
        return self.parse_execution_result(None, result)

    def get_contract(self, address: str) -> ContractDescription:
        assert isinstance(address, str)
        result = self.contracts.get(address)
        if result is None:
            print(red("BAD address"), address)
            exit(1)
        return result

    def get_balance(self, address: str) -> int:
        boc_path = self.get_contract(address).boc_path
        cli_params = ["decode", "account", "boc", boc_path]
        result = self.run_tonos_cli(cli_params)
        balance = result.get("balance")
        if balance is not None:
            return int(balance)
        balance = self.parse_execution_result(address, result)
        return int(balance)

    def load_code_cell(self, path: str) -> str:
        assert os.path.exists(path)
        cli_params = ["decode", "stateinit", path]
        if path.endswith(".boc"):
            cli_params += ["--boc"]
        else:
            cli_params += ["--tvc"]
        result = self.run_tonos_cli(cli_params)
        code = result.get("code")
        if code is not None:
            return code
        return self.parse_execution_result(None, result)
    
    def run_get(self, address: str, method, params):
        boc_path = self.get_contract(address).boc_path
        cli_params = ["runget", "--boc", boc_path, method]
        if params != "{}":
            cli_params += [params]
        result = self.run_tonos_cli(cli_params)
        value = result.get("value0")
        if value is not None:
            # return [value]
            msg = json_dumps(dict(
                id = "getter",
                name = method,
                params = result,
                src = address,
                dst = None,
                msg_type = "answer",
                timestamp = globals.now,
                log_str = None,
            ))
            result = json_dumps(dict(
                exit_code = 0,
                out_actions = [msg],
                gas = 0,
                info = None,
                debot_answer_msg = None,
                accept_in_getter = False,
                stack = value
            ))
            return result
        return self.parse_execution_result(None, result)

    def decode_message(self, message: str, abi_path: str | None) -> dict:
        cli_params = ["decode", "msg", "--abi", abi_path, message]
        return self.run_tonos_cli(cli_params)
    
    def parse_config_param(self, p: str) -> str:
        cli_params = ["test", "config", "--encode"]
        self.add_method_params(cli_params, p)
        result = self.run_tonos_cli(cli_params)
        cell = result.get("Cell")
        if cell is not None:
            return cell
        return self.parse_execution_result("bc_config", result)
    
    def dump_config_param(self, index: int):
        1/0
        # self.print_config_param

    def print_config_param(self, index: int, cell: str):
        if cell == EMPTY_CELL:
            return 'no parameter set'
        param_path = make_path("params", ".bin")
        with open(param_path, "wb") as f:
            f.write(base64.b64decode(cell))
        cli_params = ["test", "config", "--decode", param_path, "--index", str(index)]
        result = self.run_tonos_cli(cli_params)
        p = result.get('p' + str(index))
        if p is not None:
            return p
        return self.parse_execution_result(None, result)

        # # TODO: in future get directly from config just by index
        # assert isinstance(cell, str)
        # print(yellow("print_config_param"), index, cell)
        # # TODO: get config param

    def run_tonos_cli(self, cli_params: list[str], help = False, is_json = True, print_cmdline = False,  print_output = False) -> dict:
        tonos_cli = 'c:\\work/ton-node/target/release/tonos-cli'
        try:
            cmdline = subprocess.list2cmdline(cli_params)
            if print_cmdline or self.global_config.trace_tvm is not None:
                print(time.ctime(), green("cmdline"), cmdline)
        except:
            print(red("BAD list"), cli_params)
            exit(1)

        if help:
            list = [tonos_cli, "--help"] + cli_params
            print(subprocess.getoutput(list))
            exit(1)
        if not is_json:
            list = [tonos_cli] + cli_params
            print(subprocess.getoutput(list))
            exit(1)

        list = [tonos_cli, "-j"] + cli_params
        result = subprocess.getoutput(list)
        if print_output  or self.global_config.trace_tvm is not None:
            print(time.ctime(), green("result"), result)
        if result == '':
            return dict()
        try:
            answer = json.loads(result)
        except:
            print(red("BAD JSON result"), result)
            exit(1)
        # if answer.get("Error") is not None:
        #     print(red("BAD answer"), result)
        #     exit(1)
        self.global_config.trace_tvm = None
        return answer

core = Core()
globals.set_core(core, '0.1.0a1')
