## 09-11-2021: TestSuite4 0.4.1

### NEW

- ABI 2.1: support for Optional type and strings
- added `ts4.core.get_now`
- added support for string seed in `make_keypair()`
- added `save_keypair()` and `load_keypair()`
- added `gen_addr(name, initial_data, keypair, wc)`
- added more error description for exit codes (ec=51,52,60...)
- added `ts4.globals.G_SHOW_GETTERS` setting
- removed obsolete `ts4.globals.G_DECODE_TUPLES`

### CHANGES

- updated `tutorial07_time.py`

### FIXES

- fixed an issue with loading from '.boc'

## 27-07-2021: TestSuite4 0.4.0

### BREAKING CHANGES

- moved all globals to `ts4.globals` module
- changed return type of `load_tvc()` to `Cell`
- changed return type of `load_code_cell()` to `Cell`
- changed return type of `load_data_cell()` to `Cell`

### NEW

- added `encode_message_body` function for encoding message
- added error description for exit_code=76 (constructor was not called)
- added support for static members initialization (initial data)
- added `ts4.make_keypair(seed)` parameter to generate constant keys
- added global decoder parameters config (`ts4.decoder`)
- added `utils.either_or()` helper
- added `Decoder` class with decoding parameters
- added support for native strings in parameters (no need to call `str2bytes()`)
- added `ts4.globals.G_DEFAULT_BALANCE`
- implemented checking of ABI types and names when calling getters and methods

### CHANGES

- updated `tutorial01_getters.py`
- updated `tutorial02_methods.py`
- updated `tutorial09_send_money.py`
- updated `tutorial10_encode_call.py`

### FIXES

- fixed bug in BalanceWatcher
- fixed bug in reserved balance mode 0
- fixed crash when account does not exist
- fixed crash at duplicate deployment
- fixed printing of Bytes in eq()
- fixed Bytes comparision (uppercase vs lowercase)
- fixed annoying problem with unclear message when misspellen parameters: `RuntimeError: cannot encode abi body: WrongDataFormat { val: Null }`

### EXPERIMENTAL

- implemented experimental G_AUTODISPATCH mode

### OTHER

- major python code refactoring!

## 25-05-2021: TestSuite4 0.3.0

### BREAKING CHANGES

- The following member functions of `BaseContract` transformed
  into properties: `addr()`, `address()`, `balance()`, `keypair()`

### New Features

- Improved readability of verbose output
- Implemented printing of text error message in case of unexpected exit_code
- Added support for mappings in `call_getter`
- Reworked the way to work with private and public keys
- Added `keypair` parameter to BaseContract's constructor

### Tutorials

- Updated tutorials `01_getters`, `03_constructos` and `09_send_money`

### Bugs and Issues

- Added return to the `call_method_signed`
- Fixed an issue with crash at self-destruction
- Changed return type for `load_code_cell/load_data_cell` from string to `Cell`
- Made `BaseContract.create_keypair()` deprecated
- Changed behaviour of `decode_tuples` parameter
- Added `G_DECODE_TUPLES` global variable
- Added a type check in `Cell`'s constructor


## 15-04-2021: TestSuite4 0.2.1

### New Features

  - Added `ts4.core.fetch_contract_state()`
  - Implemented self-destruct feature (128+32)
  - Added class `Cell`

### Tutorials

  - Updated `tutorial09_send_money` with case which simulating to send message likes the Surf

### Bugs and Issues

  - Forced to close opened files after reading
  - Fixed `Bytes` to string comparision behavior
  - Added `ts4.set_config_param()` helper
  - Added `ts4.sign_cell()` helper
  - Improved support for bounced messages (no 'WARNING! Unknown message!' anymore)
  - Improved error handling

## 26-03-2021: TestSuite4 0.2.0

### General

- Added `ts4.init()` function for initializing TS4.
- Added `ts4.reset_all()`.
- Added `ts4.load_code_cell()` and `ts4.load_data_cell()`.
- Added `ts4.set_contract_abi()`.
- Added `ts4.zero_addr()`.
- Improved support for working with large ints.
- Added `callback` parameter to `dispatch_messages()`.
- added `Bytes` helper class
- added `dst` parameter to `Msg.is_event()`
- Added `G_STOP_ON_NO_ACCEPT` flag that controls runtime progress
  while processing method without `tvm.accept()`.
- No need to change working directory before running tests anymore

### Tutorials

- added `tutorial11_set_code` - using the contract code update functionality
- updated all tutorials

### Bugs and Issues

- Added support for `msg.createdAt`, `block.timestamp` and `tx.timestamp`.

### Methods and getters

- Implemented calling methods with return value.
- Forbidden sending messages and firing events from getters.
- Removed `private_key` parameter from `call_getter()`.
- Added `expect_ec` parameter to `call_getter()`.
- Added experimental `call_getter(...decode=True)` mode.


## 25-02-2021: TestSuite4 0.1.2

### General

- renamed `ts4_py_lib` to `tonos_ts4.ts4`
- added ability to install TS4 from package (`pip install tonos-ts4`)
- changed setup instructions for building TS4 from source.

### Tutorials

- added `tutorial10_encode_call` - encode a payload for use in a transfer function call
- updated tutorials

### Core Engine

- added support for `ACCEPT`
- added support for `tvm.log()` (see the tutorial01_getters.py)
- fixed an issue with getter returning array of structs
- major refactoring for Rust code

### Python library

- added `Address` and `Msg` helper classes
- added `BaseContract.keypair()`
- added `ts4.get_balance()`
- implemented printing getter names in verbose mode
- improved error reporting


## 10-02-2021: TestSuite4 0.1.1

### Tutorials

- added `tutorial06_signatures` - working with singed external calls,
  and handling exceptions raised by a contract.
- added `tutorial07_time` - fast-forwarding time however you need to.
- added `tutorial08_balance` - fetching contract balance.
- added `tutorial09_send_money` - send money and watch it travel within the virtual blockchain.
- improved previous tutorials

### Python and Engine

- added support for bounced messages
- added `ts4.version()`
- added `ts4.register_abi()`
- added `private_key` parameter to `core.deploy_contract()`
- added `expect_ec` parameter to `call_method()` and `dispatch_one_message()`
- enabled cutting of long strings when dumping messages to improve readabiliy of debug output
- fixed an issue with signed offchain constructor
- improved error handling and reporting
- added more checks and helpers to `ts4lib.py`
- renamed `ts4lib.py` to `ts4.py`
- large refactoring and code cleanup

### Other

- fixed the build process under macOS
- switched to the latest PyO3 library


## 20-01-2021: Initial Release of version 0.1.0

- Initial Release of version 0.1.0
