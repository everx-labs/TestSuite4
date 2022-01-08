/*
    This file is part of Ever OS.

    Ever OS is free software: you can redistribute it and/or modify 
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
*/

pragma ton-solidity >=0.30.0;

contract Tutorial11_2 {
    uint8 m_data;

    function upgrade(TvmCell code) external {
        tvm.accept();
        tvm.setcode(code);
        tvm.setCurrentCode(code);
        onCodeUpgrade(0);
    }

    function onCodeUpgrade(uint8 param) private {
        m_data = 60 + param;
    }

    function test() external view returns (uint8) {
        return 2 + m_data;
    }

    function new_func() external view returns (uint8) {
        return 5 + m_data;
    }
}
