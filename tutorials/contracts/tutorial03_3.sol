/*
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify 
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
*/

pragma solidity >=0.6.0;

contract Tutorial03_3 {
    uint public m_number;

    constructor(uint t_number) public {
        require(msg.pubkey() == tvm.pubkey());
        tvm.accept();

        m_number = t_number;
    }
}
