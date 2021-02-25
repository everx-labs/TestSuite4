/*
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify 
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
*/

pragma ton-solidity >=0.30.0;

contract Tutorial10 {
    uint16 public m_value;

    function call_me(uint16 value) public {
        // Ensure it is internal message
        require(msg.sender != address(0), 101);
        m_value = value;
    }
}
