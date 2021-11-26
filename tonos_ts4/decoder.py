from .util      import *
from .address   import *
from .abi       import *

class Decoder:
    """The :class:`Decoder <Decoder>` object, which contains decoder settings.

    :ivar bool ints: Whether decode integers or not
    :ivar bool strings: Decode string or leave it as `Bytes` object
    :ivar bool tuples: When getter returns tuple whether to return it as tuple or if no return as a map/dict
    :ivar list skip_fields: The list of the field names to be skipped during decoding stage
    """
    def __init__(self,
        ints        = None,
        strings     = None,
        tuples      = None,
        skip_fields = [],
    ):
        """Constructs :class:`Decoder <Decoder>` object.

        :param bool ints: Whether decode integers or not
        :param bool strings: Decode string or leave it as `Bytes` object
        :param bool tuples: When getter returns tuple whether to return it as tuple or if no return as a map/dict
        :param list skip_fields: The list of the field names to be skipped during decoding stage
        """
        self.ints        = ints
        self.strings     = strings
        self.tuples      = tuples
        self.skip_fields = skip_fields
        
    # TODO: consider adding setters and getters
        
    @staticmethod
    def defaults():
        return Decoder(ints = True, strings = True, tuples = True)
        
    def fill_nones(self, other):
        return Decoder(
                ints        = either_or(self.ints,        other.ints),
                strings     = either_or(self.strings,     other.strings),
                tuples      = either_or(self.tuples,      other.tuples),
                skip_fields = either_or(self.skip_fields, other.skip_fields),
            )
        

def decode_json_value(value, abi_type, decoder):
    assert isinstance(abi_type, AbiType)
    type = abi_type.type

    if abi_type.is_int():
        return decode_int(value) if decoder.ints else value

    if abi_type.is_array():
        type2 = abi_type.remove_array()
        return [decode_json_value(v, type2, decoder) for v in value]

    if type == 'bool':
        return bool(value)

    if type == 'address':
        return Address(value)

    if type == 'cell':
        return Cell(value)

    if type == 'string':
        return value

    if type == 'bytes':
        return bytes2str(value) if decoder.strings else Bytes(value)

    if type == 'tuple':
        assert isinstance(value, dict)
        res = {}
        for c in abi_type.components:
            field = c.name
            if c.dont_decode or field in decoder.skip_fields:
                res[field] = value[field]
            else:
                res[field] = decode_json_value(value[field], c, decoder)
        return res

    m = re.match(r'^map\((.*),(.*)\)$', type)
    if m:
        key_type = m.group(1)
        val_type = create_AbiType(m.group(2), abi_type)
        res = dict()
        for k in value.keys():
            if key_type == 'address':
                key = Address(k)
            else:
                key = decode_int(k)
            res[key] = decode_json_value(value[k], val_type, decoder)
        return res

    m = re.match(r'^optional\((.*)\)$', type)
    if m:
        if value is None:
            return None
        val_type = create_AbiType(m.group(1), abi_type)
        res = decode_json_value(value, val_type, decoder)
        return res


    print(type, value)
    ts4.verbose_("Unsupported type '{}'".format(type))
    return value
