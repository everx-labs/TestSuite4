/*
    This file is part of TON OS.

    TON OS is free software: you can redistribute it and/or modify 
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
*/

pragma ton-solidity >=0.30.0;

interface IContract {
    function transfer(bytes comment) external functionID(0) view;
}

contract ContractTransfer {
    event Transfered(uint128 amount, bytes comment);

    function send_grams(address addr, uint64 amount, bool bounce) pure public {
        tvm.accept();
        addr.transfer(amount, bounce);
    }

    function send_grams_with_payload(address addr, uint64 amount, bytes comment) public pure {
        tvm.accept();
        TvmCell payload = tvm.encodeBody(IContract.transfer, comment);
        addr.transfer({ value: amount, body: payload });
    }

    function send_grams_with_flags(address addr, uint128 amount, uint16 flags) public pure {
        tvm.accept();
        addr.transfer({ value: amount, flag: flags });
    }

    onBounce(TvmSlice body) pure external {
        require(body.bits() == 0);
    }

    receive() external pure {
        TvmSlice data = msg.data;

        if (!data.empty()) {
            emit Transfered(msg.value, data.decode(bytes));
        }
    }
}
