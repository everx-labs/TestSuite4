/*
    This file is part of Ever OS.

    Ever OS is free software: you can redistribute it and/or modify 
    it under the terms of the Apache License 2.0 (http://www.apache.org/licenses/)

    Copyright 2019-2021 (c) TON LABS
*/

pragma ton-solidity >=0.30.0;

contract Tutorial05_2 {

    uint public m_key;

    constructor (uint key) public {
        tvm.accept();
        m_key = key;
    }

}
