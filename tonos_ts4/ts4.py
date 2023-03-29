"""
    This file is part of Ever OS.

    Ever OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2023 (c) EverX
"""

import sys
import base64
import secrets
import json
import numbers
import re
import copy
import os.path
import importlib
from glob import glob

from .util      import *
from .core      import *
from .address   import *
from .abi       import *
from .decoder   import *
from .dump      import *
from .global_functions  import *

from .globals       import core

def load_linker_lib():
    PACKAGE_DIR = os.path.basename(os.path.dirname(__file__))
    CORE = '.' + sys.platform + '.linker_lib'

    try:
        core = importlib.import_module(CORE, PACKAGE_DIR)
    except ImportError as err:
        print('Import module error: {}'.format(err))
        exit()
    except:
        print('Unsupported platform:', sys.platform)
        exit()
    return core

core = load_linker_lib()
globals.set_core(core, '0.5.0a3')
