#!/bin/bash
# This file is part of Ever OS.
#
# Ever OS is free software: you can redistribute it and/or modify 
# it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)
#
# Copyright 2019-2021 (c) TON LABS

if [ "${LINKER_LIB_PATH}" = "" ]; then
	LINKER_LIB_PATH=./target
fi
echo ${LINKER_LIB_PATH}
cargo build --target-dir=${LINKER_LIB_PATH} && mv ${LINKER_LIB_PATH}/debug/linker_lib.dll ../tonos_ts4/linker_lib.pyd
