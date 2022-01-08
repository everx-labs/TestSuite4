/*
    This file is part of Ever OS.

    Ever OS is free software: you can redistribute it and/or modify 
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
*/

pragma ton-solidity >=0.30.0;

contract Tutorial02 {
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

    function set_number(uint value) public {
        tvm.accept();
        m_number = value;
    }

    function set_address(address value) public {
        tvm.accept();
        m_address = value;
    }

    function set_bool(bool value) public {
        tvm.accept();
        m_bool = value;
    }

    function set_bytes(bytes value) public {
        tvm.accept();
        m_bytes = value;
    }

    function set_string(string value) public {
        tvm.accept();
        m_string = value;
    }

    function set_array(uint8[] value) public {
        tvm.accept();
        m_array = value;
    }

    function set_struct(SomeStruct someStruct) public {
        tvm.accept();
        m_struct = someStruct;
    }

    function get_struct() public view returns (SomeStruct someStruct) {
        return m_struct;
    }
}
