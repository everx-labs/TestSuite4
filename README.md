# TestSuite4 0.1.2

TestSuite4 is a framework designed to simplify development and testing of TON Contracts. It contains lightweight
blockchain emulator making it easy to develop contracts in a TDD-friendly style.

## Features:

- **Speed** - perform dozens of tests in just seconds.
- **Complex test scenarios** - using Python as a scripting language allows you to create testing scenarios of varying complexity.
- **Deep Integration** - access all internal messages, measure gas and control time.
- **Easy installation** - use `pip install tonos-ts4` to install *TestSuite4* on your local Windows, Linux or macOS. You can also easily compile it from source if needed.

See `tutorials` for self-documented examples of framework usage.

## List of tutorials

- [tutorial01_getters.py](https://github.com/tonlabs/TestSuite4/blob/master/tutorials/tutorial01_getters.py) - Working with getters of various types.
- [tutorial02_methods.py](https://github.com/tonlabs/TestSuite4/blob/master/tutorials/tutorial02_methods.py) - Working with external methods.
- [tutorial03_constructors.py](https://github.com/tonlabs/TestSuite4/blob/master/tutorials/tutorial03_constructors.py) - Working with constructors.
- [tutorial04_messages.py](https://github.com/tonlabs/TestSuite4/blob/master/tutorials/tutorial04_messages.py) - Dispatching messages between contracts and catching events.
- [tutorial05_deploy.py](https://github.com/tonlabs/TestSuite4/blob/master/tutorials/tutorial05_deploy.py) - Deploying a contract from a contract and working with it through wrappers.
- [tutorial06_signatures.py](https://github.com/tonlabs/TestSuite4/blob/master/tutorials/tutorial06_signatures.py) - Working with singed external calls and handling exceptions raised by a contract.
- [tutorial07_time.py](https://github.com/tonlabs/TestSuite4/blob/master/tutorials/tutorial07_time.py) - Fast-forwarding time however you need to.
- [tutorial08_balance.py](https://github.com/tonlabs/TestSuite4/blob/master/tutorials/tutorial08_balance.py) - Fetching contract balance.
- [tutorial09_send_money.py](https://github.com/tonlabs/TestSuite4/blob/master/tutorials/tutorial09_send_money.py) - Send money and watch it travel within the virtual blockchain.
- [tutorial10_encode_call.py](https://github.com/tonlabs/TestSuite4/blob/master/tutorials/tutorial10_encode_call.py) - Encode the payload for use in the `transfer()` call.

## Quick Start

:warning: *You might need to replace `python` and `pip` with `python3` and `pip3` if you are running Linux or macOS.*

If you have `Python 3.6-3.9`, `pip` and `git` installed on your system, you can proceed with the following steps.

1. Install `tonos-ts4` package:
```bash
pip install tonos-ts4
```

2. Download tutorials from GitHub:
```bash
git clone git@github.com:tonlabs/TestSuite4.git
```

3. ... and run the tutorials:
```bash
cd TestSuite4/tutorials
python tutorial01_getters.py
```

## Building TestSuite4 from source

### Prerequesites

- Python 3.6-3.9
- Latest version of Rust
- Cargo tool

### Build for Linux and macOS

```bash
cd linker_lib && cargo update && ./build_release.sh && cd -
```

### Build for Windows

```bash
cd linker_lib && cargo update && build_release.sh && cd -
```

### Install package in developer mode

```bash
python setup.py develop
```

### Disable developer mode

```bash
python3 setup.py develop --uninstall
```

### Run tutorials

```bash
cd tutorials
python tutorial01_getters.py
```
