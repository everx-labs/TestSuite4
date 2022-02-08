pragma ton-solidity >=0.35.0;

interface IAddressInput {
	function get(uint32 answerId, string prompt) external returns (address value);
}

library AddressInput {
    int8 constant DEBOT_WC = -31;
    uint256 constant ID = 0xd7ed1bd8e6230871116f4522e58df0a93c5520c56f4ade23ef3d8919a984653b;

    function get(uint32 answerId, string prompt) public pure {
        address addr = address.makeAddrStd(DEBOT_WC, ID);
        IAddressInput(addr).get(answerId, prompt);
    }
}

contract AddressInputABI is IAddressInput {
    function get(uint32 answerId, string prompt) external override returns (address value) {}
}
