"""
    This file is part of Ever OS.

    Ever OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2023 (c) EverX
"""

import os

import globals

from address import *
from abi     import *
from core import *
from decoder import *
from dump    import *
from exception import *
from global_functions import *

def _build_params_dict(args, inputs):
    if len(args) != len(inputs):
        raise BaseException('Wrong parameters count: expected {}, got {}'.format(len(inputs), len(args)))
    d = dict()
    for i in range(len(args)):
        t = AbiType(inputs[i])
        d[t.name] = args[i]
    return d

def _build_getter_wrapper(contract, method, inputs, mode):
    def func0(*args):
        return contract.call_getter(method, _build_params_dict(args, inputs))
    def func1(*args):
        return contract.call_method(method, _build_params_dict(args, inputs))
    def func2(*args):
        return contract.call_method_signed(method, _build_params_dict(args, inputs))

    if mode == 0:       return func0
    if mode == 1:       return func1
    if mode == 2:       return func2

class Getters:
    def __init__(self, contract, mode):
        assert isinstance(contract, BaseContract)
        abi = contract.abi
        for rec in abi.json['functions']:
            method = rec['name']
            setattr(self, method, _build_getter_wrapper(contract, method, rec['inputs'], mode))

class BaseContract:
    """The :class:`BaseContract <BaseContract>` object, which is responsible
    for deploying contracts and interaction with deployed contracts.
    """
    def __init__(self,
        name: str,
        ctor_params         = None,
        initial_data        = None,
        wc                  = 0,
        address             = None,
        override_address    = None,
        pubkey              = None,
        private_key         = None,
        keypair             = None,
        balance             = None,
        nickname            = None,
    ):
        """Constructs :class:`BaseContract <BaseContract>` object.

        :param str name: Name used to load contract's bytecode and ABI
        :param dict ctor_params: Parameters for offchain constructor call
            If None, constructor is not called and can be called with
            separate `call_method()` call (onchain constructed)
        :param num wc: workchain_id to deploy contract to
        :param dict initial_data: Initial data for the contract (static members)
        :param Address address: If this parameter is specified no new contract is created
            but instead a wrapper for an existing contract is created
        :param Address override_address: When specified this address will be used for deploying
            the contract. Otherwise the address is generated according to real blockchain rules
        :param str pubkey: Public key used in contract construction
        :param str private_key: Private key used to sign construction message
        :param keypair: Keypair containing private and public keys
        :param num balance: Desired contract balance
        :param str nickname: Nickname of the contract used in verbose output
        """
        if name.startswith('debots:'):
            name = os.path.join(os.path.dirname(__file__), name.replace('debots:', 'debots/'))
        self.name_ = name
        p_n = '' if nickname == None else f'({nickname})'
        if override_address is not None:
            Address.ensure_address(override_address)
            override_address = override_address.str()
        if keypair is not None:
            (private_key, pubkey) = keypair
        self.private_key_ = private_key
        self.public_key_  = pubkey

        balance = either_or(balance, globals.G_DEFAULT_BALANCE)

        # Load ABI
        exception = None
        try:
            self.abi = Abi(name)
        except FileNotFoundError as err:
            exception = FileNotFoundError(str(err))
            raise exception

        if address is None:
            if globals.G_VERBOSE:
                print(blue(f'Deploying {name} {p_n}'))

            exception = None
            try:
                if ctor_params is not None:
                    ctor_params = check_method_params(self.abi, 'constructor', ctor_params)
                if initial_data is not None:
                    initial_data = check_method_params(self.abi, '.data', initial_data)
            except Exception as err:
                exception = translate_exception(err)
                raise exception


            if pubkey is not None:
                # assert pubkey[0:2] == '0x'
                pubkey = pubkey.replace('0x', '')
            try:
                address = deploy_contract_ext(self, ctor_params, initial_data, pubkey, None, wc, override_address, balance)
            except RuntimeError as err:
                tvm_err_msg = globals.core.get_last_error_msg()
                if tvm_err_msg is not None:
                    verbose_(tvm_err_msg)
                exception = BaseException(err)
                raise exception
            address = Address(address)
            just_deployed = True
        else:
            assert isinstance(address, Address)
            globals.core.load_account_state(address.str(), make_path(name, '.boc'), make_path(name.split('.', 1)[0], '.abi.json'))
            just_deployed = False
        self._init2(name, address, just_deployed = just_deployed)
        if nickname is not None:
            register_nickname(self.address, nickname)

        if globals.G_GENERATE_GETTERS:
            self._generate_wrappers()

    @property
    def abi_path(self):
        """Returns path to contract ABI file.

        :return: Path to ABI file
        :rtype: str
        """
        return self.abi.path_

    @property
    def tvc_path(self) -> str:
        """Returns path to contract TVC file.

        :return: Path to TVC file
        :rtype: str
        """

        return make_path(self.name_, '.tvc')

    @property
    def abi_json(self):
        return self.abi.json

    def _init2(self, name, address, nickname = None, just_deployed = False):
        Address.ensure_address(address)
        self.addr_ = address
        # if not just_deployed:
        #     if globals.G_VERBOSE:
        #         print(blue('Creating wrapper for ' + name))
        #     globals.core.set_contract_abi(self.address.str(), self.abi.path_)

        if globals.G_ABI_FIXER is not None:
            fix_abi(self.name_, self.abi_json, globals.G_ABI_FIXER)

    @property
    def balance(self):
        """Retreives balance of a given contract.

        :return: Account balance
        :rtype: num
        """
        return get_balance(self.address)

    @property
    def address(self) -> Address:
        """Returns address of a given contract.

        :return: Address of contract
        :rtype: Address
        """
        return self.addr_

    @property
    def addr(self) -> Address:
        """Returns address of a given contract. Shorter version of `address`.

        :return: Address of contract
        :rtype: Address
        """
        return self.addr_

    @property
    def hex_addr(self) -> str:
        """Returns hexadecimal representation of address of a given contract without workchain

        :return: Address of contract
        :rtype: str
        """
        return '0x' + self.addr.str().split(':')[1]

    def ensure_balance(self, v, dismiss = False):
        # TODO: is this method needed here?
        ensure_balance(v, self.balance, dismiss)

    def prepare_getter_params(self, method: str, params = dict(), expect_ec = 0):
        params = check_method_params(self.abi, method, params)

        if globals.G_VERBOSE and globals.G_SHOW_GETTERS:
            print(green('  getter') + grey(':            -> ') + bright_cyan(format_addr(self.addr)))
            print(cyan(grey('    method: ') + bright_cyan('{}'.format(method))))
            if params != dict():
                print(cyan(grey('    params: ') + bright_cyan(Params.stringify(params))))

        assert isinstance(method,    str)
        assert isinstance(params,    dict)
        assert isinstance(expect_ec, int)
        return params

    def run_get(self, method: str, params = dict(), expect_ec = 0, decoder = None) -> dict:
        """Calls a given getter for funcC contract and returns an answer in raw JSON format.

        :param str method: Name of a getter
        :param dict params: A dictionary with getter parameters
        :param num expect_ec: Expected exit code. Use non-zero value
            if you expect a getter to raise an exception
        :return: Message parameters
        :rtype: JSON
        """
        params = self.prepare_getter_params(method, params, expect_ec)

        result = run_get(self.addr, method, params)
        values = self.analyze_getter_answer(result, expect_ec, method)
        assert isinstance(values, dict)

        if expect_ec > 0:
            # TODO: ensure values is empty?
            return

        if decoder is None:
            decoder = Decoder.defaults()
        decoder.fill_nones(decoder)

        # print('values =', values)
        answer = decode_contract_answer(self.abi, values, method, None, decoder)
        return answer
        # return make_params(answer) if decode else answer

    def call_getter_raw(self, method, params = dict(), expect_ec = 0) -> dict:
        """Calls a given getter and returns an answer in raw JSON format.

        :param str method: Name of a getter
        :param dict params: A dictionary with getter parameters
        :param num expect_ec: Expected exit code. Use non-zero value
            if you expect a getter to raise an exception
        :return: Message parameters
        :rtype: JSON
        """
        params = self.prepare_getter_params(method, params, expect_ec)

        result = call_contract_ext(self.addr, method, params, is_getter = True)
        values = self.analyze_getter_answer(result, expect_ec, method)
        assert isinstance(values, dict)
        return values

    def analyze_getter_answer(self, result: ExecutionResult, expect_ec = 0, method = None):
        if result.data['accept_in_getter'] and globals.G_WARN_ON_ACCEPT_IN_GETTER:
            print(yellow('WARNING! Accept in getter!'))

        assert eq(None, result.error)
        # print(result.actions)

        check_exitcode([expect_ec], result.exit_code)

        if expect_ec != 0:
            return

        actions = [Msg(json.loads(a)) for a in result.actions]

        for msg in actions:
            if not msg.is_answer():
                raise BaseException("Unexpected message type '{}' in getter output".format(msg.type))

        if len(result.actions) == 0:
            raise BaseException("Getter '{}' returns no answer".format(method))

        assert eq(1, len(result.actions)), 'len(actions) == 1'
        msg = actions[0]

        if globals.G_VERBOSE and globals.G_SHOW_GETTERS:
            print(f"{grey('    result:')} {cyan(Params.stringify(msg.params))}\n")

        return msg.params

    def call_getter(self,
        method,
        params = dict(),
        key = None,
        expect_ec = 0,
        decode = False, # TODO: this parameter is deprecated since 0.3.1
        decoder = None,
        decode_ints = None,         # TODO: this parameter is deprecated since 0.3.1
        decode_tuples = None,       # TODO: this parameter is deprecated since 0.3.1
        dont_decode_fields = None,  # TODO: this parameter is deprecated since 0.3.1
    ):
        """Calls a given getter and decodes an answer.

        :param str method: Name of a getter
        :param dict params: A dictionary with getter parameters
        :param str key: (optional) If function returns tuple this parameter forces to return only one value under the desired key.
        :param num expect_ec: Expected exit code. Use non-zero value
            if you expect a getter to raise an exception
        :param Decoder decoder: Use this parameter to override decoding parameters
        :return: A returned value in decoded form (exact type depends on the type of getter)
        :rtype: type
        """
        exception = None
        try:
            values = self.call_getter_raw(method, params, expect_ec)
        except Exception as err:
            exception = translate_exception(err)
            raise exception

        if expect_ec > 0:
            # TODO: ensure values is empty?
            return

        if decoder is None:
            decoder = Decoder.defaults()
        decoder.fill_nones(decoder)

        if decode_ints is not None:
            decoder.ints = decode_ints
            # deprecated_msg = "Parameter is deprecated. Use `decoder = Decoder(ints = {})` instead.".format(decode_ints)
            # assert False, red(deprecated_msg)

        if decode_tuples is not None:
            deprecated_msg = "Parameter is deprecated. Use `decoder = Decoder(tuples = {})` instead.".format(decode_tuples)
            assert False, red(deprecated_msg)

        if dont_decode_fields is not None:
            deprecated_msg = "Parameter is deprecated. Use `decoder = Decoder(skip_fields = ...)` instead."
            assert False, red(deprecated_msg)


        # print('values =', values)
        answer = decode_contract_answer(self.abi, values, method, key, decoder)
        return make_params(answer) if decode else answer

    def decode_event(self, event_msg):
        """Experimental feature. Decodes event parameters

        :param Msg event_msg: An event message
        :return: Event parameters in decoded form
        :rtype: Params
        """
        assert isinstance(event_msg, Msg), '{}'.format(event_msg)

        values      =   event_msg.data['params']
        event_name  =   event_msg.event
        event_def   =   self.abi.find_event_def(event_name)

        assert event_def is not None, red('Cannot find event: {}'.format(event_name))

        # decoder = either_or(decoder, decoder).fill_nones(decoder)

        return decode_event_inputs(event_def, values)

    def _dump_event_type(self, msg):
        assert msg.is_event()
        dump_struct(self.abi.find_event_def(msg.event))

    def call_method(self, method, params = dict(), private_key = None, expect_ec = 0, is_debot = False):
        """Calls a given method.

        :param str method: Name of the method to be called
        :param dict params: A dictionary with parameters for calling the contract function
        :param str private_key: A private key to be used to sign the message
        :param num expect_ec: Expected exit code. Use non-zero value
            if you expect a method to raise an exception
        :return: Value in decoded form (if method returns something)
        :rtype: dict
        """
        # TODO: check param types. In particular, that `private_key` looks correct.
        #       Or introduce special type for keys...

        assert isinstance(params, dict)
        if globals.G_VERBOSE:
            print_ext_in_msg(self.addr, method, params)

        exception = None
        try:
            params = check_method_params(self.abi, method, params)
        except Exception as err:
            exception = translate_exception(err)
            raise exception

        try:
            result = call_contract_ext(self.addr, method, params, is_debot = is_debot, private_key = private_key)
        except RuntimeError as err:
            if globals.G_VERBOSE:
                print(err.__repr__())
                print("Exception when calling '{}' with params {}".format(method, json_dumps(params)))
            exception = BaseException(str(err))
            raise exception

        return self.analyze_call_result(result, expect_ec, method)

    def send_external_raw(self, message: Cell, expect_ec = 0):
        assert isinstance(message, Cell)

        try:
            result = globals.core.send_external_message(self.addr.str(), message.raw_)
        except RuntimeError as err:
            if globals.G_VERBOSE:
                print(err.__repr__())
                print("Exception when sending raw external message", message)
            raise BaseException(str(err))
        
        self.analyze_call_result(ExecutionResult(result), expect_ec)

    def analyze_call_result(self, result: ExecutionResult, expect_ec = 0, method = None):
        if isinstance(expect_ec, int):
            expect_ec = [expect_ec]

        globals.G_LAST_GAS_USED = result.gas_used

        globals.time_shift()

        if result.error == 'no_accept':
            severity = 'ERROR' if globals.G_STOP_ON_NO_ACCEPT else 'WARNING'
            err_msg = '{}! No ACCEPT in the contract method `{}`'.format(severity, method)
            if globals.G_STOP_ON_NO_ACCEPT:
                raise BaseException(red(err_msg))
            verbose_(err_msg)
        elif result.error == 'no_account':
            severity = 'ERROR' if globals.G_STOP_ON_NO_ACCOUNT else 'WARNING'
            err_msg = '{}! Account doesn\'t exist: `{}`'.format(severity, self.addr.str())
            if globals.G_STOP_ON_NO_ACCOUNT:
                raise BaseException(red(err_msg))
            verbose_(err_msg)
        elif result.error == 'no_funds':
            severity = 'ERROR' if globals.G_STOP_ON_NO_FUNDS else 'WARNING'
            err_msg = '{}! Not enough funds on: `{}`'.format(severity, self.addr.str())
            if globals.G_STOP_ON_NO_FUNDS:
                raise BaseException(red(err_msg))
            verbose_(err_msg)
        else:
            try:
                _gas, answer = process_actions(result, expect_ec)
            except Exception as err:
                exception = translate_exception(err)
                raise exception
            if answer is not None:
                assert answer.is_answer(method)
                key = None
                decoded_answer = decode_contract_answer(self.abi, answer.params, method, key, decoder)
                if globals.G_AUTODISPATCH:
                    try:
                        dispatch_messages()
                    except Exception as err:
                        exception = translate_exception(err)
                        raise exception
                return decoded_answer
        return None

    def call_method_signed(self, method, params = dict(), expect_ec = 0):
        """Calls a given method using contract's private key.

        :param str method: Name of the method to be called
        :param dict params: A dictionary with parameters for calling the contract function
        :param num expect_ec: Expected exit code. Use non-zero value
            if you expect a method to raise an exception
        :return: Value in decoded form (if method returns something)
        :rtype: dict
        """
        return self.call_method(method, params, private_key = self.private_key_, expect_ec = expect_ec)

    def ticktock(self, is_tock):
        """Simulates tick-tock call.

        :param bool is_tock: False for Tick and True for Tock
        :return: The amount of gas spent on the execution of the transaction
        :rtype: num
        """
        if globals.G_VERBOSE:
            print_tick_tock(self.address, is_tock)
        result = call_ticktock_ext(self.address, is_tock)
        gas, answer = process_actions(result)
        assert answer is None
        return gas

    def create_keypair(self):
        assert False, red("create_keypair() is deprecated. Use 'keypair' parameter of BaseContract's constructor instead")

    @property
    def keypair(self):
        """Returns keypair assigned to the contract.

        :return: Account keypair
        :rtype: (str, str)
        """
        return (self.private_key_, self.public_key_)

    def _generate_wrappers(self):
        self.g  = Getters(self, 0)  # getter
        self.m  = Getters(self, 1)  # method
        self.ms = Getters(self, 2)  # signed method
        # assert False


def _make_tuple_result(abi, method, values, decoder):
    assert isinstance(abi, Abi)
    assert isinstance(decoder, Decoder)
    types = abi.find_getter_output_types(method)
    res_dict = {}
    res_arr  = []
    for type in types:
        if type.name in decoder.skip_fields:
            value = values[type.name]
        else:
            value = decode_json_value(values[type.name], type, decoder)
        res_dict[type.name] = value
        res_arr.append(value)
    if decoder.tuples is True:
        return tuple(res_arr)
    else:
        return res_dict

def decode_contract_answer(
    abi: Abi,
    values: dict,
    method,
    key,
    decoder,
):
    keys = list(values.keys())

    if key is None and len(keys) == 1:
        key = keys[0]

    if key is None:
        return _make_tuple_result(abi, method, values, decoder)

    assert key is not None
    assert key in values, red("No '{}' in {}".format(key, values))

    value     = values[key]
    abi_type  = abi.find_getter_output_type(method, key)

    return decode_json_value(value, abi_type, decoder)

def process_actions(result: ExecutionResult, expect_ec = [0]):
    # print('process_actions: expect_ec = {}'.format(expect_ec))
    assert isinstance(expect_ec, list)
    assert isinstance(result, ExecutionResult)
    ec = result.exit_code

    if globals.G_VERBOSE:
        if ec != 0:
            print(grey('    exit_code: ') + yellow(ec) + '\n')

    if ec not in expect_ec:
        verbose_(globals.core.get_last_error_msg())

    check_exitcode(expect_ec, ec)

    if result.error is not None:
        raise BaseException("Transaction aborted: {}".format(result.error))

    answer = None

    for j in result.actions:
        # print(j)
        msg = Msg(json.loads(j))
        # if globals.G_VERBOSE:
            # print('process msg:', msg)
        # print('process msg:', msg, msg.is_event())
        if msg.is_event():
            if globals.G_VERBOSE or globals.G_SHOW_EVENTS:
                # TODO: move this printing code to a separate function and file
                xtra = ''
                params = msg.params
                if msg.is_event('DebugEvent'):
                    xtra = ' ={}'.format(decode_int(params['x']))
                elif msg.is_event('LogEvent'):
                    params['comment'] = bytearray.fromhex(params['comment']).decode()
                print(bright_blue('< event') + grey(': '), end='')
                print(cyan('          '), grey('<-'), bright_cyan(format_addr(msg.src)))
                print(cyan(grey('    name:   ') + cyan('{}'.format(bright_cyan(msg.event)))))
                print(grey('    params: ') + cyan(Params.stringify(params)), cyan(xtra), '\n')
            globals.EVENTS.append(msg)
        else:
            # not event
            if msg.is_unknown():
                #print(msg)
                if globals.G_VERBOSE:
                    body_str = ellipsis(globals.core.get_msg_body(msg.id), 64)
                    print(yellow('WARNING! Unknown message!' + 'body = {}'.format(body_str)))
            elif msg.is_bounced():
                pass
            elif msg.is_answer():
                # We expect only one answer
                assert answer is None
                answer = msg
                continue
            else:
                assert msg.is_call() or msg.is_empty(), red('Unexpected type: {}'.format(msg.type))
            globals.QUEUE.append(msg)
    return (result.gas_used, answer)

def dispatch_messages(callback = None, limit = None, expect_ec = [0]):
    """Dispatches all messages in the queue one by one until the queue becomes empty.

    :param callback: Callback to be called for each processed message.
        If callback returns False then the given message is skipped.
    :param num limit: Limit the number of processed messages by a given value.
    :param num expect_ec: List of expected exit codes
    :return: False if queue was empty, True otherwise
    :rtype: bool

    """
    count = 0
    while len(globals.QUEUE) > 0:
        count = count + 1
        msg = peek_msg()
        if callback is not None and callback(msg, False) == False:
            pop_msg()
            continue
        dispatch_one_message(expect_ec)
        if callback is not None:
            callback(msg, True)
        if limit is not None:
            if count >= limit:
                break
    return count > 0

def dispatch_one_message(expect_ec = 0, src = None, dst = None):
    """Takes first unprocessed message from the queue and dispatches it.
    Use `expect_ec` parameter if you expect non-zero exit code.

    :param num expect_ec: Expected exit code
    :return: The amount of gas spent on the execution of the transaction
    :rtype: num
    """
    if isinstance(expect_ec, int):
        expect_ec = [expect_ec]
    assert isinstance(expect_ec, list)
    msg = pop_msg()
    globals.ALL_MESSAGES.append(msg)
    dump1 = globals.G_VERBOSE or globals.G_DUMP_MESSAGES
    dump2 = globals.G_MSG_FILTER is not None and globals.G_MSG_FILTER(msg.data)
    if dump1 or dump2:
        print_int_msg(msg)
    if msg.dst.is_none():
        # TODO: a getter's reply. Add a test for that
        return
    if src is not None:
        assert eq(src.addr, msg.src)

    if dst is not None:
        assert eq(dst.addr, msg.dst)

    # dump_struct(msg.data)

    # CONFIRM_INPUT_ADDR = Address('-31:16653eaf34c921467120f2685d425ff963db5cbb5aa676a62a2e33bfc3f6828a')
    # if msg.dst == CONFIRM_INPUT_ADDR:
    #     verbose_('!!!!!!!!!!!!')

    result = dispatch_message_ext(msg.id)

    globals.G_LAST_GAS_USED = result.gas_used

    # print('actions =', result.actions)
    exception = None
    try:
        gas, answer = process_actions(result, expect_ec)
    except Exception as err:
        exception = translate_exception(err)
        raise exception
    if result.debot_answer_msg is not None:
        answer_msg = Msg(json.loads(result.debot_answer_msg))
        # verbose_(answer_msg)
        globals.QUEUE.append(answer_msg)
    if answer is not None:
        # verbose_('debot_answer = {}'.format(answer))
        translated_msg = globals.core.debot_translate_getter_answer(answer.id)
        # verbose_('translated_msg = {}'.format(translated_msg))
        translated_msg = Msg(json.loads(translated_msg))
        # verbose_(translated_msg)
        globals.QUEUE.append(translated_msg)

    return gas
