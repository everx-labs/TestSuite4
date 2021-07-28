# TODO: add header

import copy

from .util    import *
from .address import *

from . import ts4

class AbiType:
    def __init__(self, type):
        assert isinstance(type, dict)
        self.raw_ = type
        self.name = type['name']
        self.type = type['type']
        if self.type == 'tuple':
            self.components = [AbiType(t) for t in self.raw_['components']]
        self.dont_decode = 'dont_decode' in self.raw_

    def __repr__(self):
        return str(self.raw_)

    def is_array(self):
        return self.type[-2:] == '[]'

    def is_int(self):
        return _is_integer_type(self.type)

    def remove_array(self):
        assert self.is_array()
        type2 = copy.deepcopy(self.raw_)
        type2['type'] = self.type[:-2]
        return AbiType(type2)

class AbiTraversalHelper:
    def __init__(self, abi_name, abi_json):
        self.name_ = abi_name
        self.json_ = abi_json

    def travel_fields(self, cb):
        for f in self.json_['functions']:
            self.recFunc(self.name_ + '.functions', f, cb)
        for e in self.json_['events']:
            self.recEvent(self.name_ + '.events', e, cb)

    def recFunc(self, path, json, cb):
        path = path + '.' + json['name']
        # print(path)
        for j in json['outputs']:
            self.recVar(path + '.outputs', j, cb)

    def recEvent(self, path, json, cb):
        path = path + '.' + json['name']
        # print(path)
        for j in json['inputs']:
            self.recVar(path + '.inputs', j, cb) # TODO: do we need inputs here?

    def recVar(self, path, json, cb):
        path = path + '.' + json['name']
        type = json['type']
        while type.endswith('[]'):
            type = type[:len(type)-2]
        # print(path, type)
        if type == 'tuple':
            for j in json['components']:
                self.recVar(path, j, cb)
        cb(path, json)

def _is_integer_type(type):
    assert isinstance(type, str)
    return re.match(r'^(u)?int\d+$', type)

def find_abi_method(abi, method):
    for rec in abi['functions']:
        if rec['name'] == method:
            return rec
    return None

def find_getter_output_types(abi, method):
    rec = find_abi_method(abi, method)
    assert rec is not None
    return [AbiType(t) for t in rec['outputs']]

def find_getter_output_type(abi, method, key):
    types = find_getter_output_types(abi, method)
    for t in types:
        if t.name == key:
            return t
    assert False

def find_event_def(abi, event_name):
    assert isinstance(event_name, str)
    for event_def in abi['events']:
        if event_def['name'] == event_name:
            return event_def
    return None

def decode_event_inputs(event_def, values):
    res = {}
    for type in event_def['inputs']:
        type = AbiType(type)
        name  = type.name
        value = values[name]
        if not type.dont_decode:
            value = ts4.decode_json_value(value, type, ts4.decoder)
        res[name] = value

    return Params(res)


def check_method_params(abi, method, params):
    # ts4.verbose('check_method_params {}'.format(params))
    if method == '.data':
        inputs = abi['data']
    else:
        func = find_abi_method(abi, method)
        if func is None:
            raise Exception("Unknown method name '{}'".format(method))
        inputs = func['inputs']
    res = {}
    for param in inputs:
        pname = param['name']
        if pname not in params:
            # ts4.verbose('Raising exception')
            if globals.G_VERBOSE:
                print('params =', params)
            raise Exception("Parameter '{}' is missing when calling method '{}'".format(pname, method))
        # ts4.dump_struct(param)
        # ts4.dump_struct(params[pname])
        res[pname] = check_param_names_rec(params[pname], AbiType(param))
    return res

def _raise_type_mismatch(expected_type, value, abi_type):
    msg = 'Expected {}, got {}'.format(expected_type, value.__repr__())
    if ts4.globals.G_CHECK_ABI_TYPES:
        if ts4.globals.G_VERBOSE:
            ts4.verbose_('Expected type: {}'.format(abi_type))
        raise Exception(msg)
    else:
        ts4.verbose_(msg)

def check_param_names_rec(value, abi_type):
    assert isinstance(abi_type, AbiType)
    type = abi_type.type

    if abi_type.is_int():
        return value

    if abi_type.is_array():
        type2 = abi_type.remove_array()
        value2 = []
        for v in value:
            v2 = check_param_names_rec(v, type2)
            value2.append(v2)
        return value2

    # print(ts4.red(value.__str__()), ts4.yellow(value.__repr__()))

    if type == 'bool':
        if not isinstance(value, bool):
            _raise_type_mismatch('bool', value, abi_type)
        return value

    if type == 'address':
        if not isinstance(value, Address):
            _raise_type_mismatch('address', value, abi_type)
        return value

    if type == 'cell':
        if not isinstance(value, Cell):
            _raise_type_mismatch('cell', value, abi_type)
        return value

    if type == 'bytes':
        if isinstance(value, str):
            return Bytes(str2bytes(value))
        if isinstance(value, Bytes):
            return value
        _raise_type_mismatch('string', value, abi_type)

    if type == 'tuple':
        assert isinstance(value, dict)
        res = {}
        for c in abi_type.components:
            field = c.name
            if not field in value:
                raise Exception("Field '{}' is missing in structure '{}'".format(field, abi_type.name))
            res[field] = check_param_names_rec(value[field], c)
        return res

    m = re.match(r'^map\((.*),(.*)\)$', type)
    if m:
        key_type = m.group(1)
        val_type = dict(name = None, type = m.group(2))
        if 'components' in abi_type.raw_:
            val_type['components'] = abi_type.raw_['components']
        val_type = AbiType(val_type)
        res = dict()
        for k in value.keys():
            # if key_type == 'address':
            #     key = Address(k)
            # else:
            #     key = decode_int(k)
            res[k] = check_param_names_rec(value[k], val_type)
        return res

    print(type, value)
    ts4.verbose_("Unsupported type '{}'".format(type))
    return value

