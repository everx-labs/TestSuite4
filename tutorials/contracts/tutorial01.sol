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
    mapping(uint8 => bool) public m_mapping;

    struct SomeStruct {
        uint s_number;
        address s_address;
        bool s_bool;
        bytes s_bytes;
        string s_string;
        uint8[] s_array;
        mapping(uint8 => bool) s_mapping;
    }

    SomeStruct m_struct;
    // cell

    constructor() public {
        tvm.accept();

        m_number = 3735928559;
        m_address = address(0xc4a31362f0dd98a8cc9282c2f19358c888dfce460d93adb395fa138d61ae5069);
        m_bool = true;
        m_bytes = "coffee";
        m_string = "green tea";
        m_array = [1, 2, 3, 4, 5];
        m_mapping[0] = false;
        m_mapping[1] = true;

        m_struct = SomeStruct(
            m_number,
            m_address,
            m_bool,
            m_bytes,
            m_string,
            m_array
        );
        m_struct.s_mapping = m_mapping;
    }

    function get_struct() public view returns (SomeStruct someStruct) {
        return m_struct;
    }
}
