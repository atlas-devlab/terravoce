// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {AccessControlDefaultAdminRules} from
    "@openzeppelin/contracts/access/extensions/AccessControlDefaultAdminRules.sol";

import {ITerraPolicyRegistry} from "./interfaces/ITerraPolicyRegistry.sol";

contract TerraPolicyRegistry is AccessControlDefaultAdminRules, ITerraPolicyRegistry {
    bytes32 public constant POLICY_CURATOR_ROLE = keccak256("POLICY_CURATOR_ROLE");

    struct PolicyRecord {
        bytes32 sourceHash;
        bytes32 regionId;
        uint64 activatedAt;
        uint64 deactivatedAt;
        uint64 challengeSeconds;
        string uri;
    }

    struct ActionRule {
        address executor;
        uint96 maxAmount;
        bool allowed;
    }

    mapping(bytes32 policyHash => PolicyRecord) private _policies;
    mapping(bytes32 policyHash => mapping(bytes32 actionHash => ActionRule)) private _actionRules;

    error InvalidPolicy();
    error PolicyAlreadyExists();
    error PolicyNotActive();

    event PolicyActivated(
        bytes32 indexed policyHash,
        bytes32 indexed sourceHash,
        bytes32 indexed regionId,
        uint64 challengeSeconds,
        string uri
    );
    event PolicyActionRegistered(
        bytes32 indexed policyHash,
        bytes32 indexed actionHash,
        address indexed executor,
        uint96 maxAmount
    );
    event PolicyDeactivated(bytes32 indexed policyHash);

    constructor(uint48 adminDelay, address initialAdmin)
        AccessControlDefaultAdminRules(adminDelay, initialAdmin)
    {
        _grantRole(POLICY_CURATOR_ROLE, initialAdmin);
    }

    function activatePolicy(
        bytes32 policyHash,
        bytes32 sourceHash,
        bytes32 regionId,
        uint64 challengeSeconds,
        bytes32[] calldata actionHashes,
        address[] calldata executors,
        uint96[] calldata maxAmounts,
        string calldata uri
    ) external onlyRole(POLICY_CURATOR_ROLE) {
        if (
            policyHash == bytes32(0) || sourceHash == bytes32(0) || regionId == bytes32(0)
                || challengeSeconds == 0 || actionHashes.length == 0
                || actionHashes.length != executors.length || actionHashes.length != maxAmounts.length
                || bytes(uri).length == 0
        ) {
            revert InvalidPolicy();
        }
        if (_policies[policyHash].activatedAt != 0) revert PolicyAlreadyExists();
        _policies[policyHash] = PolicyRecord({
            sourceHash: sourceHash,
            regionId: regionId,
            activatedAt: uint64(block.timestamp),
            deactivatedAt: 0,
            challengeSeconds: challengeSeconds,
            uri: uri
        });

        for (uint256 index = 0; index < actionHashes.length; index += 1) {
            bytes32 actionHash = actionHashes[index];
            address executor = executors[index];
            uint96 maxAmount = maxAmounts[index];
            if (
                actionHash == bytes32(0) || executor == address(0) || maxAmount == 0
                    || _actionRules[policyHash][actionHash].allowed
            ) revert InvalidPolicy();
            _actionRules[policyHash][actionHash] = ActionRule({
                executor: executor,
                maxAmount: maxAmount,
                allowed: true
            });
            emit PolicyActionRegistered(policyHash, actionHash, executor, maxAmount);
        }
        emit PolicyActivated(policyHash, sourceHash, regionId, challengeSeconds, uri);
    }

    function deactivatePolicy(bytes32 policyHash) external onlyRole(POLICY_CURATOR_ROLE) {
        PolicyRecord storage policy = _policies[policyHash];
        if (policy.activatedAt == 0 || policy.deactivatedAt != 0) revert PolicyNotActive();
        policy.deactivatedAt = uint64(block.timestamp);
        emit PolicyDeactivated(policyHash);
    }

    function getPolicy(bytes32 policyHash) external view returns (PolicyRecord memory) {
        return _policies[policyHash];
    }

    function actionRule(bytes32 policyHash, bytes32 actionHash)
        external
        view
        returns (ActionRule memory)
    {
        return _actionRules[policyHash][actionHash];
    }

    function isActive(bytes32 policyHash) external view returns (bool) {
        PolicyRecord storage policyRecord = _policies[policyHash];
        return policyRecord.activatedAt != 0 && policyRecord.deactivatedAt == 0;
    }

    function validateAction(
        bytes32 policyHash,
        bytes32 regionId,
        bytes32 actionHash,
        address executor,
        uint96 amount
    ) external view returns (bool allowed, uint64 challengeSeconds) {
        PolicyRecord storage policyRecord = _policies[policyHash];
        ActionRule storage rule = _actionRules[policyHash][actionHash];
        allowed = policyRecord.activatedAt != 0 && policyRecord.deactivatedAt == 0
            && policyRecord.regionId == regionId && rule.allowed && rule.executor == executor
            && amount <= rule.maxAmount;
        challengeSeconds = policyRecord.challengeSeconds;
    }
}
