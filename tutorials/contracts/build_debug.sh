#!/bin/sh
echo "Compiling $1..."
${SOLC_PATH}/solc $1.sol
${TVM_PATH} compile $1.code --lib ../../../pub/lib/stdlib_sol.tvm -o $1.tvc --debug-info
