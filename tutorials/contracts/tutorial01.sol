/*
    This file is part of Ever OS.

    Ever OS is free software: you can redistribute it and/or modify
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
*/

pragma ton-solidity >=0.30.0;

contract Tutorial01Getters {

    uint    public m_number;
    address public m_address;
    bool    public m_bool;
    bytes   public m_bytes;
    string  public m_string;
    uint8[] public m_array;

    struct SomeStruct {
        uint    s_number;
        address s_address;
        uint8[] s_array;
    }

    SomeStruct public m_struct;

    mapping (uint => address) public m_uint_addr;

    constructor() public {
        tvm.accept();

        // Added to facilitate the debugging process
        tvm.log('Constructor');

        m_number  = 3735928559;
        m_address = address(0xc4a31362f0dd98a8cc9282c2f19358c888dfce460d93adb395fa138d61ae5069);
        m_bool    = true;
        m_bytes   = "coffee";
        m_string  = "green tea";
        m_array   = [1, 2, 3, 4, 5];

        m_struct = SomeStruct(
            m_number,
            m_address,
            m_array
        );

        m_uint_addr[1] = address(this);
        m_uint_addr[2] = address.makeAddrStd(-1, 0x3333333333333333333333333333333333333333333333333333333333333333);
        m_uint_addr[m_number] = m_address;
    }

    function get_tuple() public pure returns (uint one, uint two, uint three) {
        one = 111; two = 222; three = 333;
    }

}
