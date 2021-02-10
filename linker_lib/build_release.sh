# This file is part of TON OS.
#
# TON OS is free software: you can redistribute it and/or modify 
# it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)
#
# Copyright 2019-2021 (c) TON LABS

if [ "${LINKER_LIB_PATH}" = "" ]; then
    LINKER_LIB_PATH=./target
fi

SRC_FILENAME=liblinker_lib.so
DST_FILENAME=linker_lib.so

case "$(uname -s)" in
    Darwin*)
        SRC_FILENAME=liblinker_lib.dylib
    ;;
    CYGWIN*|MINGW32*|MSYS*|MINGW*)
        SRC_FILENAME=linker_lib.dll
        DST_FILENAME=linker_lib.pyd
    ;;
esac

echo ${LINKER_LIB_PATH}

cargo build --release --target-dir=${LINKER_LIB_PATH} \
    && mv -v ${LINKER_LIB_PATH}/release/${SRC_FILENAME} ../ts4_py_lib/${DST_FILENAME}
