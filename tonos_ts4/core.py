import os
import sys
import importlib

from . import globals
from . import ts4
from .util import *

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

def enable_fees(value):
    assert isinstance(value, bool)
    cfg = ts4.core.get_global_config()
    cfg.gas_fee = value
    ts4.core.set_global_config(cfg)

def set_balance(target, value):
    ts4.ensure_address(target)
    ts4.core.set_balance(target.str(), int(value))

def set_trace_level(level):
    cfg = ts4.core.get_global_config()
    cfg.trace_level = level
    ts4.core.set_global_config(cfg)

def set_trace_tvm(value):
    cfg = ts4.core.get_global_config()
    cfg.trace_tvm = value
    ts4.core.set_global_config(cfg)


# __core__ = load_linker_lib()
