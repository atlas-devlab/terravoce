// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

interface ITerraTreasury {
    function release(uint256 proposalId, address recipient, uint256 amount, bool autonomous)
        external;
}

