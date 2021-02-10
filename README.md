# TestSuite4

TestSuite4 is a framework designed to simplify development and testing of TON Contracts. It contains lightweight 
blockchain emulator making it easy to develop contracts in a TDD-friendly style.

## Features:

- **Speed** - perform dozens of tests in just seconds.
- **Complex test scenarios** - using Python as a scripting language allows you to create testing scenarios of varying complexity.
- **Deep Integration** - access all internal messages, measure gas and control time.
- **Easy installation** - only Python and Rust are needed to compile and run *TestSuite4* on your local Windows, Linux or macOS.

See `tutorials` for self-documented examples of framework usage.

## List of tutorials

- [tutorial01_getters.py](tutorials/tutorial01_getters.py) - Working with getters of various types.
- [tutorial02_methods.py](tutorials/tutorial02_methods.py) - Working with external methods.
- [tutorial03_constructors.py](tutorials/tutorial03_constructors.py) - Working with constructors.
- [tutorial04_messages.py](tutorials/tutorial04_messages.py) - Dispatching messages between contracts and catching events.
- [tutorial05_deploy.py](tutorials/tutorial05_deploy.py) - Deploying a contract from a contract and working with it through wrappers.
- [tutorial06_sign.py](tutorials/tutorial06_sign.py) - Working with singed external calls and handling exceptions raised by a contract.
- [tutorial07_time](tutorials/tutorial07_time.py) - Fast-forwarding time however you need to.
- [tutorial08_balance.py](tutorials/tutorial08_balance.py) - Fetching contract balance.
- [tutorial09_send_money.py](tutorials/tutorial09_send_money.py) - Send money and watch it travel within the virtual blockchain.

## Prerequesites

- Python 3.6-3.7
- Latest version of Rust
- Cargo tool

## Setup for Linux

```bash
cd linker_lib && cargo update && ./build_release.sh
```

## Setup for Windows
```bash
cd linker_lib && cargo update && buildWin.sh
```

## Run tutorials for Linux

```bash
cd tutorials
python3 tutorial01_getters.py
```

## Run tutorials for Windows

```bash
cd tutorials
python tutorial01_getters.py
```

