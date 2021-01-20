# TestSuite4

TestSuite4 is a framework designed to simplify development and testing of TON Contracts. It includes light-weight
emulator of blockchain making it easy to develop contracts. See `tutorials` for self-documented examples of framework usage.

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