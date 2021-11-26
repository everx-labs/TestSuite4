import os
import sys
import importlib

G_VERSION		= '0.4.1'

QUEUE           = []
EVENTS          = []
ALL_MESSAGES    = []
NICKNAMES       = dict()

GRAM            = 1_000_000_000
EMPTY_CELL      = 'te6ccgEBAQEAAgAAAA=='

G_DEFAULT_BALANCE   = 100*GRAM

G_TESTS_PATH    = 'contracts/'

G_VERBOSE           = False
G_DUMP_MESSAGES     = False
G_STOP_AT_CRASH     = True
G_SHOW_EVENTS       = False
G_SHOW_GETTERS      = False
G_MSG_FILTER        = None
G_WARN_ON_UNEXPECTED_ANSWERS = False
G_STOP_ON_NO_ACCEPT = True
G_STOP_ON_NO_ACCOUNT = True
G_STOP_ON_NO_FUNDS 	= True
G_CHECK_ABI_TYPES	= True
G_AUTODISPATCH      = False

G_ABI_FIXER     = None


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


