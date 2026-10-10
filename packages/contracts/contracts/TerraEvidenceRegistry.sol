// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {AccessControlDefaultAdminRules} from
    "@openzeppelin/contracts/access/extensions/AccessControlDefaultAdminRules.sol";

import {ITerraEvidenceRegistry} from "./interfaces/ITerraEvidenceRegistry.sol";

contract TerraEvidenceRegistry is AccessControlDefaultAdminRules, ITerraEvidenceRegistry {
    bytes32 public constant ORACLE_ROLE = keccak256("ORACLE_ROLE");

    enum EvidenceKind {
        ObservationBatch,
        Assessment
    }

    struct Evidence {
        bytes32 regionId;
        bytes32 metadataHash;
        uint64 observedAt;
        uint32 attestationCount;
        EvidenceKind kind;
        bool accepted;
        string uri;
    }

    uint8 public immutable oracleQuorum;
    mapping(bytes32 evidenceHash => Evidence) private _evidence;
    mapping(bytes32 evidenceHash => mapping(address oracle => bool)) public hasAttested;

    error InvalidEvidence();
    error EvidenceMismatch();
    error DuplicateAttestation();

    event EvidenceAttested(
        bytes32 indexed evidenceHash,
        bytes32 indexed regionId,
        address indexed oracle,
        uint32 attestationCount
    );
    event EvidenceAccepted(bytes32 indexed evidenceHash, bytes32 indexed regionId);

    constructor(uint8 oracleQuorum_, uint48 adminDelay, address initialAdmin)
        AccessControlDefaultAdminRules(adminDelay, initialAdmin)
    {
        if (oracleQuorum_ < 2) revert InvalidEvidence();
        oracleQuorum = oracleQuorum_;
        _grantRole(ORACLE_ROLE, initialAdmin);
    }

    function attestEvidence(
        bytes32 evidenceHash,
        bytes32 regionId,
        bytes32 metadataHash,
        uint64 observedAt,
        EvidenceKind kind,
        string calldata uri
    ) external onlyRole(ORACLE_ROLE) {
        if (
            evidenceHash == bytes32(0) || regionId == bytes32(0) || metadataHash == bytes32(0)
                || observedAt == 0 || bytes(uri).length == 0
        ) revert InvalidEvidence();
        if (hasAttested[evidenceHash][msg.sender]) revert DuplicateAttestation();

        Evidence storage item = _evidence[evidenceHash];
        if (item.observedAt == 0) {
            item.regionId = regionId;
            item.metadataHash = metadataHash;
            item.observedAt = observedAt;
            item.kind = kind;
            item.uri = uri;
        } else if (
            item.regionId != regionId || item.metadataHash != metadataHash
                || item.observedAt != observedAt || item.kind != kind
                || keccak256(bytes(item.uri)) != keccak256(bytes(uri))
        ) {
            revert EvidenceMismatch();
        }

        hasAttested[evidenceHash][msg.sender] = true;
        item.attestationCount += 1;
        emit EvidenceAttested(evidenceHash, regionId, msg.sender, item.attestationCount);

        if (!item.accepted && item.attestationCount >= oracleQuorum) {
            item.accepted = true;
            emit EvidenceAccepted(evidenceHash, regionId);
        }
    }

    function evidence(bytes32 evidenceHash) external view returns (Evidence memory) {
        return _evidence[evidenceHash];
    }

    function isAcceptedForRegion(bytes32 evidenceHash, bytes32 regionId)
        external
        view
        returns (bool)
    {
        Evidence storage item = _evidence[evidenceHash];
        return item.accepted && item.regionId == regionId;
    }
}

