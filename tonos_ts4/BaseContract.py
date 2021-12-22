import os

from . import globals
from . import ts4

from .address import *
from .abi     import *
from .global_functions import *

def build_getter_wrapper(contract, method, inputs):
    def func(*args):
        if len(args) != len(inputs):
            raise ts4.BaseException('Wrong parameters count: expected {}, got {}'.format(len(inputs), len(args)))
        d = dict()
        for i in range(len(args)):
            t = AbiType(inputs[i])
            d[t.name] = args[i]
        return contract.call_getter(method, d)
    return func

class Getters:
    def __init__(self, contract):
        assert isinstance(contract, BaseContract)
        abi = contract.abi
        for rec in abi.json['functions']:
            method = rec['name']
            output_types = abi.find_getter_output_types(method)
            if output_types == []:
                continue
            setattr(self, method, build_getter_wrapper(contract, method, rec['inputs']))


class BaseContract:
    """The :class:`BaseContract <BaseContract>` object, which is responsible
    for deploying contracts and interaction with deployed contracts.
    """
    def __init__(self,
        name,
        ctor_params,
        wc = 0,
        initial_data        = None,
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
        self.name_ = name
        full_name = os.path.join(globals.G_TESTS_PATH, name)
        just_deployed = False
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
        self.abi = Abi(name)

        if address is None:
            if globals.G_VERBOSE:
                print(blue(f'Deploying {full_name} {p_n}'))

            error_msg = None

            try:
                if ctor_params is not None:
                    ctor_params = ts4.check_method_params(self.abi, 'constructor', ctor_params)

                if initial_data is not None:
                    initial_data = ts4.check_method_params(self.abi, '.data', initial_data)
            except Exception as err:
                error_msg = str(err)
            if error_msg is not None:
                raise ts4.BaseException(error_msg)

            if pubkey is not None:
                assert pubkey[0:2] == '0x'
                pubkey = pubkey.replace('0x', '')
            try:
                address = globals.core.deploy_contract(
                    full_name + '.tvc',
                    full_name + '.abi.json',
                    ts4.json_dumps(ctor_params) if ctor_params is not None else None,
                    ts4.json_dumps(initial_data) if initial_data is not None else None,
                    pubkey,
                    private_key,
                    wc,
                    override_address,
                    balance,
                )
            except Exception as err:
                tvm_err_msg = globals.core.get_last_error_msg()
                if tvm_err_msg is not None:
                    ts4.verbose_(tvm_err_msg)
                error_msg = str(err)
            if error_msg is not None:
                raise ts4.BaseException(error_msg)
            address = Address(address)
            just_deployed = True
        self._init2(name, address, just_deployed = just_deployed)
        if nickname is not None:
            ts4.register_nickname(self.address, nickname)

    @property
    def abi_json(self):
        return self.abi.json

    def _init2(self, name, address, nickname = None, just_deployed = False):
        Address.ensure_address(address)
        self.addr_ = address
        if not just_deployed:
            if globals.G_VERBOSE:
                print(blue('Creating wrapper for ' + name))
            globals.core.set_contract_abi(self.address.str(), self.abi.path_)

        if globals.G_ABI_FIXER is not None:
            ts4.fix_abi(self.name_, self.abi_json, globals.G_ABI_FIXER)

    @property
    def balance(self):
        """Retreives balance of a given contract.

        :return: Account balance
        :rtype: num
        """
        return ts4.get_balance(self.address)

    @property
    def address(self):
        """Returns address of a given contract.

        :return: Address of contract
        :rtype: Address
        """
        return self.addr_

    @property
    def addr(self):
        """Returns address of a given contract. Shorter version of `address`.

        :return: Address of contract
        :rtype: Address
        """
        return self.addr_

    def ensure_balance(self, v, dismiss = False):
        # TODO: is this method needed here?
        ts4.ensure_balance(v, self.balance, dismiss)

    def call_getter_raw(self, method, params = dict(), expect_ec = 0):
        """Calls a given getter and returns an answer in raw JSON format.

        :param str method: Name of a getter
        :param dict params: A dictionary with getter parameters
        :param num expect_ec: Expected exit code. Use non-zero value
            if you expect a getter to raise an exception
        :return: Message parameters
        :rtype: JSON
        """

        params = ts4.check_method_params(self.abi, method, params)

        if globals.G_VERBOSE and globals.G_SHOW_GETTERS:
            print(green('  getter') + grey(':             ') + bright_cyan(format_addr(self.addr)), end='')
            print(cyan(grey('\n    method: ') + bright_cyan('{}'.format(method))))

        assert isinstance(method,    str)
        assert isinstance(params,    dict)
        assert isinstance(expect_ec, int)

        result = globals.core.call_contract(
            self.addr.str(),
            method,
            True,   # is_getter
            False,  # is_debot
            ts4.json_dumps(params),
            None,   # private_key
        )

        result = ExecutionResult(result)
        assert eq(None, result.error)
        # print(actions)

        ts4.check_exitcode([expect_ec], result.exit_code)

        if expect_ec != 0:
            return

        actions = [Msg(json.loads(a)) for a in result.actions]

        for msg in actions:
            if not msg.is_answer():
                raise ts4.BaseException("Unexpected message type '{}' in getter output".format(msg.type))

        assert eq(1, len(result.actions)), 'len(actions) == 1'
        msg = Msg(json.loads(result.actions[0]))
        assert msg.is_answer(method)

        if globals.G_VERBOSE and globals.G_SHOW_GETTERS:
            print(f"{grey('    result: ')} {cyan(Params.stringify(msg.params))}\n")

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
        error_msg = None
        try:
            values = self.call_getter_raw(method, params, expect_ec)
        except Exception as err:
            error_msg = str(err)
        if error_msg is not None:
            raise ts4.BaseException(error_msg)

        if expect_ec > 0:
            # TODO: ensure values is empty?
            return

        if decode_ints is not None:
            deprecated_msg = "Parameter is deprecated. Use `decoder = ts4.Decoder(ints = {})` instead.".format(decode_ints)
            assert False, red(deprecated_msg)

        if decode_tuples is not None:
            deprecated_msg = "Parameter is deprecated. Use `decoder = ts4.Decoder(tuples = {})` instead.".format(decode_tuples)
            assert False, red(deprecated_msg)

        if dont_decode_fields is not None:
            deprecated_msg = "Parameter is deprecated. Use `decoder = ts4.Decoder(skip_fields = ...)` instead."
            assert False, red(deprecated_msg)

        decoder = either_or(decoder, ts4.decoder).fill_nones(ts4.decoder)

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

        # decoder = either_or(decoder, ts4.decoder).fill_nones(ts4.decoder)

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
        if isinstance(expect_ec, int):
            expect_ec = [expect_ec]
        if globals.G_VERBOSE:
            print(blue('> ext_in_msg') + grey(': '), end='')
            print(cyan('    '), grey('->'), bright_cyan(format_addr(self.addr)))
            print(cyan(grey('    method: ') + bright_cyan('{}'.format(method))
            + grey('\n    params: ') + cyan('{}'.format(Params.stringify(prettify_dict(params))))) + '\n')

        error_msg = None
        try:
            params = ts4.check_method_params(self.abi, method, params)
        except Exception as err:
            error_msg = str(err)
        if error_msg is not None:
            raise ts4.BaseException(error_msg)

        try:
            result = globals.core.call_contract(
                self.addr.str(),
                method,
                False, # is_getter
                is_debot,
                ts4.json_dumps(params),
                private_key,
            )
            result = ExecutionResult(result)
        except:
            if globals.G_VERBOSE:
                print("Exception when calling '{}' with params {}".format(method, ts4.json_dumps(params)))
            raise

        globals.G_LAST_GAS_USED = result.gas_used

        if result.error == 'no_accept':
            severity = 'ERROR' if globals.G_STOP_ON_NO_ACCEPT else 'WARNING'
            err_msg = '{}! No ACCEPT in the contract method `{}`'.format(severity, method)
            if globals.G_STOP_ON_NO_ACCEPT:
                raise ts4.BaseException(red(err_msg))
            verbose_(err_msg)
        elif result.error == 'no_account':
            severity = 'ERROR' if globals.G_STOP_ON_NO_ACCOUNT else 'WARNING'
            err_msg = '{}! Account doesn\'t exist: `{}`'.format(severity, self.addr.str())
            if globals.G_STOP_ON_NO_ACCOUNT:
                raise ts4.BaseException(red(err_msg))
            verbose_(err_msg)
        elif result.error == 'no_funds':
            severity = 'ERROR' if globals.G_STOP_ON_NO_FUNDS else 'WARNING'
            err_msg = '{}! Not enough funds on: `{}`'.format(severity, self.addr.str())
            if globals.G_STOP_ON_NO_FUNDS:
                raise ts4.BaseException(red(err_msg))
            verbose_(err_msg)
        else:
            error_msg = None
            try:
                _gas, answer = ts4.process_actions(result, expect_ec)
            except Exception as err:
                error_msg = str(err)
            if error_msg is not None:
                raise ts4.BaseException(error_msg)
            if answer is not None:
                assert answer.is_answer(method)
                key = None
                decoded_answer = decode_contract_answer(self.abi, answer.params, method, key, ts4.decoder)
            if globals.G_AUTODISPATCH:
                ts4.dispatch_messages()
            if answer is not None:
                return decoded_answer


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
            print('ticktock {}'.format(format_addr(self.address)))
        result = globals.core.call_ticktock(self.address.str(), is_tock)
        result = ExecutionResult(result)
        gas, answer = ts4.process_actions(result)
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

    # TODO: add docs
    def generate_getters(self):
        self.g = Getters(self)
        # assert False


def _make_tuple_result(abi, method, values, decoder):
    types = abi.find_getter_output_types(method)
    res_dict = {}
    res_arr  = []
    for type in types:
        value = ts4.decode_json_value(values[type.name], type, decoder)
        res_dict[type.name] = value
        res_arr.append(value)
    if decoder.tuples is True:
        return tuple(res_arr)
    else:
        return res_dict

def decode_contract_answer(
    abi,
    values,
    method,
    key,
    params,
):
    keys = list(values.keys())

    if key is None and len(keys) == 1:
        key = keys[0]

    if key is None:
        return _make_tuple_result(abi, method, values, params)

    assert key is not None
    assert key in values, red("No '{}' in {}".format(key, values))

    value     = values[key]
    abi_type  = abi.find_getter_output_type(method, key)

    return ts4.decode_json_value(value, abi_type, params)

