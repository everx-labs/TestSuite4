/*
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify 
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
*/

pragma solidity >=0.6.0;

interface INeighbor {
    function pong(uint32 replay) external;
}

contract Tutorial04_2 {
    event ReceivedRequest(uint32 request);

    function ping(uint32 request) public {
        tvm.accept();
        INeighbor(msg.sender).pong(request);
        emit ReceivedRequest(request);
    }
}
