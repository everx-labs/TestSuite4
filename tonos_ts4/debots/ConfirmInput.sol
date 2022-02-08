pragma ton-solidity >=0.35.0;

interface IConfirmInput {

	function get(uint32 answerId, string prompt) external returns (bool value);

}

library ConfirmInput {

	uint256 constant ID = 0x16653eaf34c921467120f2685d425ff963db5cbb5aa676a62a2e33bfc3f6828a;
	int8 constant DEBOT_WC = -31;

	function get(uint32 answerId, string prompt) public pure {
		address addr = address.makeAddrStd(DEBOT_WC, ID);
		IConfirmInput(addr).get(answerId, prompt);
	}

}

contract ConfirmInputABI is IConfirmInput {

	function get(uint32 answerId, string prompt) external override returns (bool value) {}

}
