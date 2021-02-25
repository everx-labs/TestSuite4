# This file is part of TON OS.
#
# TON OS is free software: you can redistribute it and/or modify 
# it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)
#
# Copyright 2019-2021 (c) TON LABS

if [ "${LINKER_LIB_PATH}" = "" ]; then
    LINKER_LIB_PATH=./target
fi

DST_BASE_PATH=../tonos_ts4
SRC_FILENAME=liblinker_lib.so
OS_PATH=linux
DST_EXT=so

# Extract version from Cargo.toml
#VERSION=$(awk -F= 'BEGIN{found=0} {if($1=="[package]") found=1; if(found==1 && $1=="version") {gsub(/"/, "", $2);print $2; exit} }' Cargo.toml)

case "$(uname -s)" in
    Darwin*)
        SRC_FILENAME=liblinker_lib.dylib
        OS_PATH=darwin
    ;;
    CYGWIN*|MINGW32*|MSYS*|MINGW*)
        SRC_FILENAME=linker_lib.dll
        OS_PATH=win32
        DST_EXT=pyd
    ;;
esac

echo ${LINKER_LIB_PATH}

cargo build --release --target-dir=${LINKER_LIB_PATH} \
    && mkdir -p ${DST_BASE_PATH}/${OS_PATH} \
    && mv -v ${LINKER_LIB_PATH}/release/${SRC_FILENAME} ${DST_BASE_PATH}/${OS_PATH}/linker_lib.${DST_EXT}
