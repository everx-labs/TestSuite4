pragma ton-solidity >=0.35.0;
pragma AbiHeader expire;
pragma AbiHeader time;
pragma AbiHeader pubkey;
import "Menu.sol";

contract MenuImpl is IMenu {

	constructor () public {
	}

	address m_address;
	string public m_title;
	string public m_description;
	MenuItem[] public m_items;

	function select(string title, string description, MenuItem[] items) external override returns (uint32 /*index*/)
	{
		m_address = msg.sender;
		m_title = title;
		m_description = description;
		m_items = items;
	}

	function reply_select(uint32 index) public view {
		tvm.accept();
		uint32 handlerId = m_items[index].handlerId;
		TvmBuilder b;
		b.store(handlerId, index);
		m_address.transfer({value: 1 ever, body: b.toCell()});
	}

}

