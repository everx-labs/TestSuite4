/*
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify 
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
*/

pragma solidity >=0.6.0;

contract Tutorial01Getters {

    uint public m_number;
    address public m_address;
    bool public m_bool;
    bytes public m_bytes;
    string public m_string;
    uint8[] public m_array;

    struct SomeStruct {
        uint s_number;
        address s_address;
        uint8[] s_array;
    }

    SomeStruct m_struct;

    constructor() public {
        tvm.accept();

        m_number = 3735928559;
        m_address = address(0xc4a31362f0dd98a8cc9282c2f19358c888dfce460d93adb395fa138d61ae5069);
        m_bool = true;
        m_bytes = "coffee";
        m_string = "green tea";
        m_array = [1, 2, 3, 4, 5];

        m_struct = SomeStruct(
            m_number,
            m_address,
            m_array
        );
    }

    function get_struct() public view returns (SomeStruct someStruct) {
        return m_struct;
    }
}
