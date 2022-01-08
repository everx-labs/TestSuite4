/*
    This file is part of Ever OS.

    Ever OS is free software: you can redistribute it and/or modify 
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
*/

pragma ton-solidity >=0.30.0;
pragma AbiHeader pubkey;

contract SignMeth {
    uint256 public m_number;

    function setNumber(uint256 value) public {
        require(msg.pubkey() == tvm.pubkey(), 101);
        tvm.accept();
        m_number = value;
    }
}
