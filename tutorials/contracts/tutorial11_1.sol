pragma ton-solidity >=0.30.0;

contract Tutorial11_1 {
    uint8 m_data;

    constructor() public {
        tvm.accept();
        m_data = 20;
    }

    function upgrade(TvmCell code) external {
        tvm.accept();
        tvm.setcode(code);
        tvm.setCurrentCode(code);
        onCodeUpgrade(100);
    }

    function onCodeUpgrade(uint8 param) private {}

    function test() external view returns (uint8) {
        return 1 + m_data;
    }
}
