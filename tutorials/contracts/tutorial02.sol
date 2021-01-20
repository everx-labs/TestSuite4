/*
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify 
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
*/

pragma solidity >=0.6.0;

contract Tutorial02 {
    uint public m_number;
    address public m_address;
    bool public m_bool;
    string public m_string;
    uint8[] public m_array;

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

    function set_string(string value) public {
        tvm.accept();
        m_string = value;
    }

    function set_array(uint8[] value) public {
        tvm.accept();
        m_array = value;
    }
}
