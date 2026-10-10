// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {AccessControlDefaultAdminRules} from
    "@openzeppelin/contracts/access/extensions/AccessControlDefaultAdminRules.sol";

import {ITerraCivicRegistry} from "./interfaces/ITerraCivicRegistry.sol";

contract TerraCivicRegistry is AccessControlDefaultAdminRules, ITerraCivicRegistry {
    bytes32 public constant REGISTRAR_ROLE = keccak256("REGISTRAR_ROLE");

    struct Membership {
        uint64 issuedAt;
        uint64 revokedAt;
        bytes32 personNullifier;
    }

    mapping(bytes32 regionId => mapping(Chamber chamber => mapping(address account => Membership)))
        private _memberships;
    mapping(bytes32 regionId => mapping(Chamber chamber => mapping(bytes32 nullifier => bool)))
        private _usedNullifiers;
    mapping(bytes32 regionId => mapping(Chamber chamber => uint32)) private _activeCounts;

    error InvalidMembership();
    error MembershipAlreadyExists();
    error NullifierAlreadyUsed();
    error MembershipNotActive();

    event MemberRegistered(
        bytes32 indexed regionId,
        Chamber indexed chamber,
        address indexed account,
        bytes32 personNullifier
    );
    event MemberRevoked(bytes32 indexed regionId, Chamber indexed chamber, address indexed account);

    constructor(uint48 adminDelay, address initialAdmin)
        AccessControlDefaultAdminRules(adminDelay, initialAdmin)
    {
        _grantRole(REGISTRAR_ROLE, initialAdmin);
    }

    function registerMember(
        bytes32 regionId,
        Chamber chamber,
        address account,
        bytes32 personNullifier
    ) external onlyRole(REGISTRAR_ROLE) {
        if (regionId == bytes32(0) || account == address(0) || personNullifier == bytes32(0)) {
            revert InvalidMembership();
        }
        if (_memberships[regionId][chamber][account].issuedAt != 0) {
            revert MembershipAlreadyExists();
        }
        if (_usedNullifiers[regionId][chamber][personNullifier]) revert NullifierAlreadyUsed();

        _usedNullifiers[regionId][chamber][personNullifier] = true;
        _memberships[regionId][chamber][account] = Membership({
            issuedAt: uint64(block.timestamp),
            revokedAt: 0,
            personNullifier: personNullifier
        });
        _activeCounts[regionId][chamber] += 1;
        emit MemberRegistered(regionId, chamber, account, personNullifier);
    }

    function revokeMember(bytes32 regionId, Chamber chamber, address account)
        external
        onlyRole(REGISTRAR_ROLE)
    {
        Membership storage member = _memberships[regionId][chamber][account];
        if (member.issuedAt == 0 || member.revokedAt != 0) revert MembershipNotActive();
        member.revokedAt = uint64(block.timestamp);
        _activeCounts[regionId][chamber] -= 1;
        emit MemberRevoked(regionId, chamber, account);
    }

    function membership(bytes32 regionId, Chamber chamber, address account)
        external
        view
        returns (Membership memory)
    {
        return _memberships[regionId][chamber][account];
    }

    function isMemberAt(bytes32 regionId, Chamber chamber, address account, uint64 timestamp)
        external
        view
        returns (bool)
    {
        Membership storage member = _memberships[regionId][chamber][account];
        return member.issuedAt != 0 && member.issuedAt <= timestamp
            && (member.revokedAt == 0 || member.revokedAt > timestamp);
    }

    function activeMemberCount(bytes32 regionId, Chamber chamber)
        external
        view
        returns (uint32)
    {
        return _activeCounts[regionId][chamber];
    }
}

