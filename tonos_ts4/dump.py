from .util import *
from .address import *
from .abi import *
from .global_functions import *


def dump_struct(struct, compact = False):
    if compact:
        print(json.dumps(struct))
    else:
        print(dump_struct_str(struct))

class JsonEncoder(json.JSONEncoder):
    def default(self, o):
        # verbose_(o)
        if isinstance(o, Address):
            return o.str()
        elif isinstance(o, Bytes):
            return o.raw_
        else:
            assert False

def dump_struct_str(struct):
    return json.dumps(struct, indent = 2, cls = JsonEncoder)

def _fix_large_ints(v):
    def transform_value(v):
        if isinstance(v, Address):
            return v.str()
        if isinstance(v, Bytes):
            return v.raw_
        if isinstance(v, Cell):
            return v.raw_
        if isinstance(v, int):
            if v > 0xffffFFFFffffFFFF:
                v = hex(v)
            return v
        return v
    return transform_structure(v, transform_value)

def json_dumps(j):
    j = _fix_large_ints(j)
    return json.dumps(j) #, cls = JsonEncoder)


#########################################################################################################


def dump_all_messages():
    prev_time = 0
    for msg in ALL_MESSAGES:
        cur_time = msg['timestamp']
        if cur_time == prev_time:
            print('---------------')
        else:
            print('--------------- {} ------------ ------------ ------------'
                .format(colorize(BColors.BOLD, str(cur_time))))
            prev_time = cur_time
        dump_message(msg)


def dump_message(msg: Msg):
    assert isinstance(msg, Msg)
    value = msg.value / GRAM if msg.value is not None else 'n/a'
    #print(msg)

    msg_type = ''
    ttt = ''
    if msg.is_type('call',  'empty', 'bounced'):
        # ttt = "{}".format(msg)
        if msg.is_call():
            ttt = bright_cyan(msg.method) + grey('\n    params: ') + cyan(Params.stringify(msg.params) + '\n')
            ttt = grey('    method:') + ttt
        elif msg.is_bounced():
            msg_type = yellow(' <bounced>')
        elif msg.is_type('empty') and value > 0:
            msg_type = cyan(' <transfer>')
        else:
            msg_type = cyan(' <empty>')
        #print(grey('    method:'), ttt)
    elif msg.is_unknown():
        #print(msg)
        ttt = "> " + yellow('<unknown>') #TODO to highlight the print
        #print("> " + ttt)
    else:
        assert msg.is_answer()
        ttt = "> " + green('{}'.format(msg.data))
        #print("> " + green(ttt))

    print(blue('> int_msg' + msg_type) + grey(': '), end='')
    print(bright_cyan(format_addr(msg.src)), grey('->'), bright_cyan(format_addr(msg.dst)), end='')
    print(grey(', value:'), cyan(msg.value))
    if ttt != '':
        print(ttt)


#########################################################################################################

def dump_js_data():
    all_runs = get_all_runs()
    msgs = get_all_messages()
    with open('msg_data.js', 'w') as f:
        print('var allMessages = ' + dump_struct_str(msgs) + ';', file = f)
        print('var nicknames = ' + dump_struct_str(globals.NICKNAMES) + ';', file = f)
        print('var allRuns = ' + dump_struct_str(all_runs) + ';', file = f)

