pragma ton-solidity >=0.35.0;
pragma AbiHeader expire;
pragma AbiHeader time;
pragma AbiHeader pubkey;
import "AddressInput.sol";

contract AddressInputImpl is IAddressInput {

	constructor () public {
	}

	event Get(uint32 answerId, string prompt);

	function get(uint32 answerId, string prompt) external override returns (address value) {
		emit Get(answerId, prompt);
	}
	
	function reply_get(address debot_addr, uint32 answerId, address answer_addr) public pure {
		tvm.accept();
		TvmBuilder b;
		b.store(answerId, answer_addr);
		debot_addr.transfer({value: 1 ever, body: b.toCell()});
	}
	
	
}

