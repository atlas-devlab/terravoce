// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

interface ITerraPolicyRegistry {
    function isActive(bytes32 policyHash) external view returns (bool);

    function validateAction(
        bytes32 policyHash,
        bytes32 regionId,
        bytes32 actionHash,
        address executor,
        uint96 amount
    ) external view returns (bool allowed, uint64 challengeSeconds);
}
