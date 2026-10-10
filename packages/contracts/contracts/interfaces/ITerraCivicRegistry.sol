// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

interface ITerraCivicRegistry {
    enum Chamber {
        Community,
        Youth
    }

    function isMemberAt(bytes32 regionId, Chamber chamber, address account, uint64 timestamp)
        external
        view
        returns (bool);

    function activeMemberCount(bytes32 regionId, Chamber chamber)
        external
        view
        returns (uint32);
}

