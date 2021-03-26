

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
