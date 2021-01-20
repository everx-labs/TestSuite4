/*
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify 
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
*/

pragma solidity >=0.6.0;

import "tutorial05_2.sol";

contract Tutorial05_1 {

    TvmCell m_code;
    TvmCell m_data;
    address public m_address;

    constructor (TvmCell code, TvmCell data) public {
        // Save the code of second contract
        m_code = code;
        m_data = data;
    }

    function deploy(uint key) public {
        // Create StateInit for the contract to be deployed
        TvmCell stateInit = tvm.buildStateInit(m_code, m_data);

        // Create a deployment message with a given parameters
        Tutorial05_2 result = new Tutorial05_2{stateInit: stateInit, value:1_000_000_000, flag: 1}(key);

        // Saves the address of a new contract to local storage
        m_address = address(result);
    }

}
