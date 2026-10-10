// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {AccessControlDefaultAdminRules} from
    "@openzeppelin/contracts/access/extensions/AccessControlDefaultAdminRules.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

import {ITerraCivicRegistry} from "./interfaces/ITerraCivicRegistry.sol";
import {ITerraEvidenceRegistry} from "./interfaces/ITerraEvidenceRegistry.sol";
import {ITerraPolicyRegistry} from "./interfaces/ITerraPolicyRegistry.sol";
import {ITerraTreasury} from "./interfaces/ITerraTreasury.sol";

contract TerraActGovernor is AccessControlDefaultAdminRules, ReentrancyGuard {
    uint16 private constant BPS = 10_000;

    bytes32 public constant AUTOMATION_ROLE = keccak256("AUTOMATION_ROLE");
    bytes32 public constant GUARDIAN_ROLE = keccak256("GUARDIAN_ROLE");

    enum RiskTier {
        Reversible,
        Irreversible
    }

    enum ProposalState {
        Challenge,
        Voting,
        Paused,
        Ready,
        Rejected,
        Executed
    }

    struct ActionRequest {
        bytes32 regionId;
        bytes32 evidenceHash;
        bytes32 policyHash;
        bytes32 actionHash;
        address recipient;
        uint96 amount;
        RiskTier riskTier;
        bool requestAutonomy;
        string metadataURI;
    }

    struct Proposal {
        address proposer;
        address recipient;
        bytes32 regionId;
        bytes32 evidenceHash;
        bytes32 policyHash;
        bytes32 actionHash;
        uint96 amount;
        uint64 createdAt;
        uint64 challengeEndsAt;
        uint64 votingEndsAt;
        uint64 pauseUntil;
        uint32 communityEligible;
        uint32 youthEligible;
        uint32 communityFor;
        uint32 communityAgainst;
        uint32 youthFor;
        uint32 youthAgainst;
        RiskTier riskTier;
        bool autonomous;
        bool challenged;
        bool pausedOnce;
        bool executed;
        string metadataURI;
    }

    ITerraEvidenceRegistry public immutable evidenceRegistry;
    ITerraPolicyRegistry public immutable policyRegistry;
    ITerraCivicRegistry public immutable civicRegistry;
    ITerraTreasury public immutable treasury;
    uint16 public immutable communityApprovalBps;
    uint16 public immutable youthApprovalBps;
    uint64 public immutable votingPeriod;
    uint64 public immutable challengePeriod;
    uint64 public immutable guardianPauseDuration;
    uint96 public immutable maxAutonomousActionAmount;

    uint256 public proposalCount;
    mapping(uint256 proposalId => Proposal) private _proposals;
    mapping(
        uint256 proposalId
            => mapping(ITerraCivicRegistry.Chamber chamber => mapping(address voter => bool))
    ) public hasVoted;

    error InvalidConfiguration();
    error InvalidProposal();
    error EvidenceNotAccepted();
    error PolicyNotActive();
    error NotEligible();
    error NotAutonomousProposal();
    error ChallengeWindowClosed();
    error VoteUnavailable();
    error DuplicateVote();
    error PauseUnavailable();
    error ProposalNotReady();

    event ProposalCreated(
        uint256 indexed proposalId,
        bytes32 indexed regionId,
        address indexed proposer,
        bool autonomous,
        RiskTier riskTier,
        bytes32 evidenceHash,
        bytes32 policyHash
    );
    event ProposalChallenged(uint256 indexed proposalId, address indexed challenger);
    event VoteCast(
        uint256 indexed proposalId,
        ITerraCivicRegistry.Chamber indexed chamber,
        address indexed voter,
        bool support
    );
    event ProposalPaused(
        uint256 indexed proposalId,
        address indexed guardian,
        bytes32 indexed reasonHash,
        uint64 pauseUntil
    );
    event ProposalExecuted(uint256 indexed proposalId, address indexed recipient, uint256 amount);

    constructor(
        address evidenceRegistry_,
        address policyRegistry_,
        address civicRegistry_,
        address treasury_,
        uint16 communityApprovalBps_,
        uint16 youthApprovalBps_,
        uint64 votingPeriod_,
        uint64 challengePeriod_,
        uint64 guardianPauseDuration_,
        uint96 maxAutonomousActionAmount_,
        uint48 adminDelay,
        address initialAdmin
    ) AccessControlDefaultAdminRules(adminDelay, initialAdmin) {
        if (
            evidenceRegistry_ == address(0) || policyRegistry_ == address(0)
                || civicRegistry_ == address(0) || treasury_ == address(0)
                || communityApprovalBps_ == 0 || communityApprovalBps_ > BPS
                || youthApprovalBps_ == 0 || youthApprovalBps_ > BPS || votingPeriod_ == 0
                || challengePeriod_ == 0 || guardianPauseDuration_ == 0
                || maxAutonomousActionAmount_ == 0
        ) revert InvalidConfiguration();

        evidenceRegistry = ITerraEvidenceRegistry(evidenceRegistry_);
        policyRegistry = ITerraPolicyRegistry(policyRegistry_);
        civicRegistry = ITerraCivicRegistry(civicRegistry_);
        treasury = ITerraTreasury(treasury_);
        communityApprovalBps = communityApprovalBps_;
        youthApprovalBps = youthApprovalBps_;
        votingPeriod = votingPeriod_;
        challengePeriod = challengePeriod_;
        guardianPauseDuration = guardianPauseDuration_;
        maxAutonomousActionAmount = maxAutonomousActionAmount_;
        _grantRole(AUTOMATION_ROLE, initialAdmin);
        _grantRole(GUARDIAN_ROLE, initialAdmin);
    }

    function propose(ActionRequest calldata request) external returns (uint256 proposalId) {
        if (
            request.regionId == bytes32(0) || request.evidenceHash == bytes32(0)
                || request.actionHash == bytes32(0) || request.recipient == address(0)
                || request.amount == 0 || bytes(request.metadataURI).length == 0
        ) revert InvalidProposal();
        if (!evidenceRegistry.isAcceptedForRegion(request.evidenceHash, request.regionId)) {
            revert EvidenceNotAccepted();
        }

        uint32 communityEligible = civicRegistry.activeMemberCount(
            request.regionId, ITerraCivicRegistry.Chamber.Community
        );
        uint32 youthEligible =
            civicRegistry.activeMemberCount(request.regionId, ITerraCivicRegistry.Chamber.Youth);
        if (communityEligible == 0 || youthEligible == 0) revert InvalidProposal();

        bool autonomous = request.requestAutonomy;
        uint64 createdAt = uint64(block.timestamp);
        uint64 challengeEndsAt;
        uint64 votingEndsAt;

        if (autonomous) {
            if (!hasRole(AUTOMATION_ROLE, msg.sender)) revert NotEligible();
            if (
                request.riskTier != RiskTier.Reversible
                    || request.amount > maxAutonomousActionAmount
            ) revert InvalidProposal();
            (bool actionAllowed, uint64 policyChallengeSeconds) = policyRegistry.validateAction(
                request.policyHash,
                request.regionId,
                request.actionHash,
                request.recipient,
                request.amount
            );
            if (!actionAllowed) revert PolicyNotActive();
            uint64 effectiveChallenge =
                policyChallengeSeconds > challengePeriod ? policyChallengeSeconds : challengePeriod;
            challengeEndsAt = createdAt + effectiveChallenge;
        } else {
            if (
                !civicRegistry.isMemberAt(
                    request.regionId,
                    ITerraCivicRegistry.Chamber.Community,
                    msg.sender,
                    createdAt
                )
            ) revert NotEligible();
            votingEndsAt = createdAt + votingPeriod;
        }

        proposalId = ++proposalCount;
        Proposal storage proposal = _proposals[proposalId];
        proposal.proposer = msg.sender;
        proposal.recipient = request.recipient;
        proposal.regionId = request.regionId;
        proposal.evidenceHash = request.evidenceHash;
        proposal.policyHash = request.policyHash;
        proposal.actionHash = request.actionHash;
        proposal.amount = request.amount;
        proposal.createdAt = createdAt;
        proposal.challengeEndsAt = challengeEndsAt;
        proposal.votingEndsAt = votingEndsAt;
        proposal.communityEligible = communityEligible;
        proposal.youthEligible = youthEligible;
        proposal.riskTier = request.riskTier;
        proposal.autonomous = autonomous;
        proposal.metadataURI = request.metadataURI;

        emit ProposalCreated(
            proposalId,
            request.regionId,
            msg.sender,
            autonomous,
            request.riskTier,
            request.evidenceHash,
            request.policyHash
        );
    }

    function challenge(uint256 proposalId) external {
        Proposal storage proposal = _proposal(proposalId);
        if (!proposal.autonomous || proposal.challenged) revert NotAutonomousProposal();
        if (block.timestamp >= proposal.challengeEndsAt) revert ChallengeWindowClosed();
        if (
            !civicRegistry.isMemberAt(
                proposal.regionId,
                ITerraCivicRegistry.Chamber.Community,
                msg.sender,
                proposal.createdAt
            )
        ) revert NotEligible();

        proposal.challenged = true;
        proposal.votingEndsAt = uint64(block.timestamp) + votingPeriod;
        emit ProposalChallenged(proposalId, msg.sender);
    }

    function castVote(
        uint256 proposalId,
        ITerraCivicRegistry.Chamber chamber,
        bool support
    ) external {
        Proposal storage proposal = _proposal(proposalId);
        if (proposal.autonomous && !proposal.challenged) revert VoteUnavailable();
        if (proposal.votingEndsAt == 0 || block.timestamp >= proposal.votingEndsAt) {
            revert VoteUnavailable();
        }
        if (hasVoted[proposalId][chamber][msg.sender]) revert DuplicateVote();
        if (!civicRegistry.isMemberAt(proposal.regionId, chamber, msg.sender, proposal.createdAt)) {
            revert NotEligible();
        }

        hasVoted[proposalId][chamber][msg.sender] = true;
        if (chamber == ITerraCivicRegistry.Chamber.Community) {
            if (support) proposal.communityFor += 1;
            else proposal.communityAgainst += 1;
        } else {
            if (support) proposal.youthFor += 1;
            else proposal.youthAgainst += 1;
        }
        emit VoteCast(proposalId, chamber, msg.sender, support);
    }

    function pauseProposal(uint256 proposalId, bytes32 reasonHash)
        external
        onlyRole(GUARDIAN_ROLE)
    {
        Proposal storage proposal = _proposal(proposalId);
        if (proposal.executed || proposal.pausedOnce || reasonHash == bytes32(0)) {
            revert PauseUnavailable();
        }
        proposal.pausedOnce = true;
        proposal.pauseUntil = uint64(block.timestamp) + guardianPauseDuration;

        if (proposal.autonomous && !proposal.challenged) {
            proposal.challenged = true;
            proposal.votingEndsAt = uint64(block.timestamp) + votingPeriod;
        }
        emit ProposalPaused(proposalId, msg.sender, reasonHash, proposal.pauseUntil);
    }

    function execute(uint256 proposalId) external nonReentrant {
        Proposal storage proposal = _proposal(proposalId);
        if (proposalState(proposalId) != ProposalState.Ready) revert ProposalNotReady();

        bool remainsAutonomous = proposal.autonomous && !proposal.challenged;
        if (remainsAutonomous) {
            (bool actionAllowed,) = policyRegistry.validateAction(
                proposal.policyHash,
                proposal.regionId,
                proposal.actionHash,
                proposal.recipient,
                proposal.amount
            );
            if (!actionAllowed) revert PolicyNotActive();
        }
        proposal.executed = true;
        treasury.release(proposalId, proposal.recipient, proposal.amount, remainsAutonomous);
        emit ProposalExecuted(proposalId, proposal.recipient, proposal.amount);
    }

    function getProposal(uint256 proposalId) external view returns (Proposal memory) {
        Proposal storage stored = _proposal(proposalId);
        return stored;
    }

    function proposalState(uint256 proposalId) public view returns (ProposalState) {
        Proposal storage stored = _proposal(proposalId);
        if (stored.executed) return ProposalState.Executed;

        if (stored.autonomous && !stored.challenged) {
            if (block.timestamp < stored.challengeEndsAt) return ProposalState.Challenge;
            if (block.timestamp < stored.pauseUntil) return ProposalState.Paused;
            return ProposalState.Ready;
        }

        if (block.timestamp < stored.votingEndsAt) return ProposalState.Voting;
        if (!_approved(stored)) return ProposalState.Rejected;
        if (block.timestamp < stored.pauseUntil) return ProposalState.Paused;
        return ProposalState.Ready;
    }

    function _approved(Proposal storage proposal) private view returns (bool) {
        return uint256(proposal.communityFor) * BPS
                >= uint256(proposal.communityEligible) * communityApprovalBps
            && uint256(proposal.youthFor) * BPS
                >= uint256(proposal.youthEligible) * youthApprovalBps;
    }

    function _proposal(uint256 proposalId) private view returns (Proposal storage stored) {
        if (proposalId == 0 || proposalId > proposalCount) revert InvalidProposal();
        return _proposals[proposalId];
    }
}
