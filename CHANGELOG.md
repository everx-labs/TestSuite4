
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
