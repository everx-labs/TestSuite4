/*
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify 
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
*/

pragma solidity >=0.6.0;

interface INeighbor {
    function ping(uint32 request) external;
}

contract Tutorial04_1 {
    event ReceivedReply(uint32 reply);

    function ping_neighbor(address neighbor, uint32 value) public {
        tvm.accept();
        INeighbor(neighbor).ping(value);
    }

    function pong(uint32 reply) public {
        tvm.accept();
        emit ReceivedReply(reply);
    }
}
