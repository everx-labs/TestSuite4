pragma ton-solidity >=0.35.0;
pragma AbiHeader expire;
pragma AbiHeader time;
pragma AbiHeader pubkey;

abstract contract Debot {

    uint8 constant DEBOT_ABI = 1;

    uint8 m_options;
    optional(string) m_debotAbi;
    /// @notice Deprecated. For compatibility with old DEngine.
    optional(string) m_targetAbi;
    /// @notice Deprecated. For compatibility with old DEngine.
    optional(address) m_target;

    /*
     * Public debot interface
     */

    /// @notice DeBot entry point.
    function start() public virtual;

    /// @notice DeBot version and title.
    function getVersion() public virtual returns (string name, uint24 semver);

    /// @notice Returns DeBot ABI.
    function getDebotOptions() public view returns (uint8 options, string debotAbi, string targetAbi, address targetAddr) {
        debotAbi = m_debotAbi.hasValue() ? m_debotAbi.get() : "";
        targetAbi = m_targetAbi.hasValue() ? m_targetAbi.get() : "";
        targetAddr = m_target.hasValue() ? m_target.get() : address(0);
        options = m_options;
    }

    /// @notice Allow to set debot ABI. Do it before using debot.
    function setABI(string dabi) public {
        require(tvm.pubkey() == msg.pubkey(), 100);
        tvm.accept();
        m_options |= DEBOT_ABI;
        m_debotAbi = dabi;
    }
}