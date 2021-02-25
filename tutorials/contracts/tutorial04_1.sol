/*
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify 
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
*/

pragma ton-solidity >=0.30.0;

interface INeighbor {
    function ping(uint32 request) external;
}

contract Tutorial04_1 {
    event ReceivedReply(uint32 reply);

    function ping_neighbor(address neighbor, uint32 value) public pure {
        tvm.accept();
        INeighbor(neighbor).ping(value);
    }

    function pong(uint32 reply) public pure {
        tvm.accept();
        emit ReceivedReply(reply);
    }
}
