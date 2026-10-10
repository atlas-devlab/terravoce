// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {AccessControlDefaultAdminRules} from
    "@openzeppelin/contracts/access/extensions/AccessControlDefaultAdminRules.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

import {ITerraTreasury} from "./interfaces/ITerraTreasury.sol";

contract TerraTreasury is AccessControlDefaultAdminRules, ReentrancyGuard, ITerraTreasury {
    using SafeERC20 for IERC20;

    IERC20 public immutable fundingToken;
    uint64 public immutable epochDuration;
    uint256 public immutable autonomousEpochLimit;
    address public governor;

    mapping(uint256 proposalId => bool) public released;
    mapping(uint256 epoch => uint256) public autonomousSpent;

    error InvalidTreasuryConfiguration();
    error GovernorAlreadySet();
    error UnauthorizedGovernor();
    error ProposalAlreadyReleased();
    error AutonomousBudgetExceeded();

    event GovernorSet(address indexed governor);
    event FundsReleased(
        uint256 indexed proposalId,
        address indexed recipient,
        uint256 amount,
        bool autonomous
    );

    constructor(
        address fundingToken_,
        uint64 epochDuration_,
        uint256 autonomousEpochLimit_,
        uint48 adminDelay,
        address initialAdmin
    ) AccessControlDefaultAdminRules(adminDelay, initialAdmin) {
        if (
            fundingToken_ == address(0) || epochDuration_ == 0 || autonomousEpochLimit_ == 0
        ) revert InvalidTreasuryConfiguration();
        fundingToken = IERC20(fundingToken_);
        epochDuration = epochDuration_;
        autonomousEpochLimit = autonomousEpochLimit_;
    }

    function setGovernor(address governor_) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (governor != address(0)) revert GovernorAlreadySet();
        if (governor_ == address(0)) revert InvalidTreasuryConfiguration();
        governor = governor_;
        emit GovernorSet(governor_);
    }

    function currentEpoch() public view returns (uint256) {
        return block.timestamp / epochDuration;
    }

    function release(uint256 proposalId, address recipient, uint256 amount, bool autonomous)
        external
        nonReentrant
    {
        if (msg.sender != governor) revert UnauthorizedGovernor();
        if (released[proposalId]) revert ProposalAlreadyReleased();
        if (recipient == address(0) || amount == 0) revert InvalidTreasuryConfiguration();

        if (autonomous) {
            uint256 epoch = currentEpoch();
            uint256 updated = autonomousSpent[epoch] + amount;
            if (updated > autonomousEpochLimit) revert AutonomousBudgetExceeded();
            autonomousSpent[epoch] = updated;
        }

        released[proposalId] = true;
        fundingToken.safeTransfer(recipient, amount);
        emit FundsReleased(proposalId, recipient, amount, autonomous);
    }
}

