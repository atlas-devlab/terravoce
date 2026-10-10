// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

interface ITerraEvidenceRegistry {
    function isAcceptedForRegion(bytes32 evidenceHash, bytes32 regionId)
        external
        view
        returns (bool);
}

