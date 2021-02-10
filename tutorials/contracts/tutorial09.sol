/*
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify 
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
*/

pragma solidity >=0.6.0;

contract ContractTransfer {
    function send_grams(address addr, uint64 amount, bool bounce) pure public {
        addr.transfer(amount, bounce);
    }

    onBounce(TvmSlice body) pure external {
        require(body.bits() == 0);
    }
}
