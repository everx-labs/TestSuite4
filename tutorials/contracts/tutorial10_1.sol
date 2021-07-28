/*
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify 
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
*/

pragma ton-solidity >=0.30.0;

interface ISomeContract {
    function call_me(uint16 value) external;
}

contract Tutorial10Encoder {
    // Encode call to call_me() with a given parameter. Return resulting message body as a cell
    function encode(uint16 value) public pure returns (TvmCell) {
        return tvm.encodeBody(ISomeContract.call_me, value);
    }


    function call_it(address dest, TvmCell payload) public pure {
        tvm.accept();
        // Call destination contract with a previously encoded message
        dest.transfer({value: 1 ton, body: payload});
    }
}
