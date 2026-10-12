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
    mapping(bytes32 evidenceHash => mapping(bytes32 candidateId => Evidence)) private _candidates;
    mapping(bytes32 evidenceHash => bytes32 candidateId) private _firstCandidateId;
    mapping(bytes32 evidenceHash => bytes32 candidateId) public acceptedCandidateId;
    mapping(bytes32 evidenceHash => mapping(address oracle => bool)) public hasAttested;

    bytes32 private constant CANDIDATE_DOMAIN = keccak256("TerraVoce.EvidenceCandidate.v1");

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
    event EvidenceCandidateAttested(
        bytes32 indexed evidenceHash,
        bytes32 indexed candidateId,
        address indexed oracle,
        uint32 attestationCount
    );

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

        bytes32 candidateId = evidenceCandidateId(
            evidenceHash, regionId, metadataHash, observedAt, kind, uri
        );
        // Before quorum, another complete envelope is a separate candidate, not a mismatch.
        // Once accepted, the winner is immutable even if more identities are enrolled later.
        if (_evidence[evidenceHash].accepted && acceptedCandidateId[evidenceHash] != candidateId) {
            revert EvidenceMismatch();
        }

        Evidence storage item = _candidates[evidenceHash][candidateId];
        if (item.observedAt == 0) {
            item.regionId = regionId;
            item.metadataHash = metadataHash;
            item.observedAt = observedAt;
            item.kind = kind;
            item.uri = uri;
        }

        hasAttested[evidenceHash][msg.sender] = true;
        item.attestationCount += 1;
        emit EvidenceAttested(evidenceHash, regionId, msg.sender, item.attestationCount);
        emit EvidenceCandidateAttested(evidenceHash, candidateId, msg.sender, item.attestationCount);

        if (!item.accepted && item.attestationCount >= oracleQuorum) {
            item.accepted = true;
            acceptedCandidateId[evidenceHash] = candidateId;
            emit EvidenceAccepted(evidenceHash, regionId);
        }

        // Pending data is read from its candidate instead of copied into final storage.
        // A malicious first URI must not make honest finalization pay to clear that string.
        if (_firstCandidateId[evidenceHash] == bytes32(0)) _firstCandidateId[evidenceHash] = candidateId;
        if (item.accepted) {
            _evidence[evidenceHash] = item;
        }
    }

    function evidenceCandidateId(
        bytes32 evidenceHash,
        bytes32 regionId,
        bytes32 metadataHash,
        uint64 observedAt,
        EvidenceKind kind,
        string memory uri
    ) public view returns (bytes32) {
        return keccak256(
            abi.encode(
                CANDIDATE_DOMAIN, block.chainid, address(this), evidenceHash,
                regionId, metadataHash, observedAt, kind, uri
            )
        );
    }

    function candidate(bytes32 evidenceHash, bytes32 candidateId)
        external
        view
        returns (Evidence memory)
    {
        return _candidates[evidenceHash][candidateId];
    }

    function evidence(bytes32 evidenceHash) external view returns (Evidence memory) {
        if (_evidence[evidenceHash].accepted) return _evidence[evidenceHash];
        return _candidates[evidenceHash][_firstCandidateId[evidenceHash]];
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

