pragma ton-solidity >=0.35.0;
pragma AbiHeader expire;
pragma AbiHeader time;
pragma AbiHeader pubkey;
import "ConfirmInput.sol";

contract ConfirmInputImpl is IConfirmInput {

	constructor () public {
	}

	address m_address;
	string public m_prompt;
	uint32 public m_answerId;

	function get(uint32 answerId, string prompt) external override returns (bool value) {
		m_address = msg.sender;
		m_prompt = prompt;
		m_answerId = answerId;
	}

	function reply(bool answer) public view {
		tvm.accept();
		TvmBuilder b;
		b.store(m_answerId, answer);
		m_address.transfer({value: 1 ever, body: b.toCell()});
	}

}

