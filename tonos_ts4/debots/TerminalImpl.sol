pragma ton-solidity >=0.35.0;
pragma AbiHeader expire;
pragma AbiHeader time;
pragma AbiHeader pubkey;
import "Terminal.sol";

contract TerminalImpl is ITerminal {

	constructor () public {
	}

	event Print(uint32 answerId, string message);
	event Input(uint32 answerId, string prompt, bool multiline);

	function input(uint32 answerId, string prompt, bool multiline) external override returns (string value) {
		emit Input(answerId, prompt, multiline);
	}

	function print(uint32 answerId, string message) external override {
		emit Print(answerId, message);
	}

	function printf(uint32 answerId, string fmt, TvmCell fargs) external override {}

	function call_input(address addr, uint32 answerId, string txt) public pure {
		tvm.accept();
		TvmBuilder b;
		b.store(answerId, txt);
		addr.transfer({value: 1 ever, body: b.toCell()});
	}
}

