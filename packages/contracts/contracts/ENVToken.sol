// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {ERC20Capped} from "@openzeppelin/contracts/token/ERC20/extensions/ERC20Capped.sol";
import {ERC20Permit} from "@openzeppelin/contracts/token/ERC20/extensions/ERC20Permit.sol";

contract ENVToken is ERC20, ERC20Capped, ERC20Permit {
    constructor(address allocationRecipient, uint256 initialSupply, uint256 supplyCap)
        ERC20("TerraVoce Environmental Utility", "ENV")
        ERC20Capped(supplyCap)
        ERC20Permit("TerraVoce Environmental Utility")
    {
        _mint(allocationRecipient, initialSupply);
    }

    function _update(address from, address to, uint256 value)
        internal
        override(ERC20, ERC20Capped)
    {
        super._update(from, to, value);
    }
}

