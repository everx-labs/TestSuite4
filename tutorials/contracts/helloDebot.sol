pragma ton-solidity >=0.50.0;
pragma AbiHeader expire;
pragma AbiHeader time;
pragma AbiHeader pubkey;

// import required DeBot interfaces and basic DeBot contract.
import "https://raw.githubusercontent.com/tonlabs/debots/main/Debot.sol";
import "https://raw.githubusercontent.com/tonlabs/DeBot-IS-consortium/main/Terminal/Terminal.sol";

contract HelloDebot is Debot {

    /// @notice Entry point function for DeBot.
    function start() public override {
        // print string to user.
        Terminal.print(0, "Hello, World!");
        // input string from user and define callback that receives entered string.
        Terminal.input(tvm.functionId(setUserInput), "How is it going?", false);
    }

    function setUserInput(string value) public {
        // TODO: continue DeBot logic here...
        Terminal.print(0, format("You entered \"{}\"", value));
    }

    function getDebotInfo() public functionID(0xDEB) override view returns(
        string name, string version, string publisher, string key, string author,
        address support, string hello, string language, string dabi, bytes icon
    ) {
        name = "HelloWorld Debot";
        version = "0.2.0";
        publisher = "TON Labs";
        key = "";
        author = "TON Labs";
        support = address.makeAddrStd(0, 0x0);
        hello = "Hello, I'm HelloWorld DeBot.";
        language = "en";
        dabi = m_debotAbi.get();
        icon = "";
    }

    function getRequiredInterfaces() public view override returns (uint256[] interfaces) {
        return [ Terminal.ID ];
    }
}