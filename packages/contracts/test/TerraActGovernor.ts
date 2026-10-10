import { expect } from "chai";
import { network } from "hardhat";

const DAY = 86_400;
const USDC = 1_000_000n;

describe("TerraAct protocol", function () {
  async function deployFixture() {
    const { ethers, networkHelpers } = await network.create();
    const [
      admin,
      oracle1,
      oracle2,
      automation,
      guardian,
      community1,
      community2,
      community3,
      community4,
      youth1,
      youth2,
      recipient,
      outsider
    ] = await ethers.getSigners();

    const stablecoin = await ethers.deployContract("MockStablecoin");
    const evidence = await ethers.deployContract("TerraEvidenceRegistry", [2, 0, admin.address]);
    const policies = await ethers.deployContract("TerraPolicyRegistry", [0, admin.address]);
    const civic = await ethers.deployContract("TerraCivicRegistry", [0, admin.address]);
    const treasury = await ethers.deployContract("TerraTreasury", [
      await stablecoin.getAddress(),
      7 * DAY,
      500n * USDC,
      0,
      admin.address
    ]);
    const governor = await ethers.deployContract("TerraActGovernor", [
      await evidence.getAddress(),
      await policies.getAddress(),
      await civic.getAddress(),
      await treasury.getAddress(),
      6_000,
      5_000,
      3 * DAY,
      DAY,
      5 * DAY,
      250n * USDC,
      0,
      admin.address
    ]);
    const env = await ethers.deployContract("ENVToken", [
      outsider.address,
      1_000_000n * 10n ** 18n,
      1_000_000n * 10n ** 18n
    ]);

    await treasury.setGovernor(await governor.getAddress());
    await stablecoin.mint(await treasury.getAddress(), 10_000n * USDC);

    await evidence.grantRole(await evidence.ORACLE_ROLE(), oracle1.address);
    await evidence.grantRole(await evidence.ORACLE_ROLE(), oracle2.address);
    await governor.grantRole(await governor.AUTOMATION_ROLE(), automation.address);
    await governor.grantRole(await governor.GUARDIAN_ROLE(), guardian.address);

    const regionId = ethers.id("IT-PO-DELTA");
    const aerationActionHash = ethers.id("WATER_AERATION");
    const samplingActionHash = ethers.id("EXTRA_SAMPLING");
    const policyHash =
      "0x16fcda4dd4e94a5493f0ebbc756d40ed37095a44ea69d0a691c230610196a114";
    const policySourceHash = ethers.sha256(ethers.toUtf8Bytes("po-water-v1.terra"));
    await policies.activatePolicy(
      policyHash,
      policySourceHash,
      regionId,
      DAY,
      [aerationActionHash, samplingActionHash],
      [recipient.address, recipient.address],
      [250n * USDC, 50n * USDC],
      "ipfs://policy/po-water-v1"
    );

    for (const [index, member] of [community1, community2, community3].entries()) {
      await civic.registerMember(
        regionId,
        0,
        member.address,
        ethers.id(`community-nullifier-${index}`)
      );
    }
    for (const [index, member] of [youth1, youth2].entries()) {
      await civic.registerMember(
        regionId,
        1,
        member.address,
        ethers.id(`youth-nullifier-${index}`)
      );
    }

    const evidenceHash = ethers.sha256(ethers.toUtf8Bytes("assessment-bundle-v1"));
    const metadataHash = ethers.sha256(ethers.toUtf8Bytes("assessment-metadata-v1"));
    const observedAt = await networkHelpers.time.latest();
    await evidence
      .connect(oracle1)
      .attestEvidence(
        evidenceHash,
        regionId,
        metadataHash,
        observedAt,
        1,
        "ipfs://evidence/assessment-v1"
      );
    await evidence
      .connect(oracle2)
      .attestEvidence(
        evidenceHash,
        regionId,
        metadataHash,
        observedAt,
        1,
        "ipfs://evidence/assessment-v1"
      );

    const autonomousRequest = (amount = 200n * USDC) => ({
      regionId,
      evidenceHash,
      policyHash,
      actionHash: aerationActionHash,
      recipient: recipient.address,
      amount,
      riskTier: 0,
      requestAutonomy: true,
      metadataURI: "ipfs://actions/water-aeration-v1"
    });

    const governedRequest = () => ({
      regionId,
      evidenceHash,
      policyHash: ethers.ZeroHash,
      actionHash: ethers.id("RESTORE_WETLAND"),
      recipient: recipient.address,
      amount: 1_000n * USDC,
      riskTier: 1,
      requestAutonomy: false,
      metadataURI: "ipfs://actions/restore-wetland-v1"
    });

    return {
      ethers,
      networkHelpers,
      accounts: {
        admin,
        oracle1,
        oracle2,
        automation,
        guardian,
        community1,
        community2,
        community3,
        community4,
        youth1,
        youth2,
        recipient,
        outsider
      },
      stablecoin,
      evidence,
      policies,
      civic,
      treasury,
      governor,
      env,
      regionId,
      policyHash,
      aerationActionHash,
      evidenceHash,
      metadataHash,
      observedAt,
      autonomousRequest,
      governedRequest
    };
  }

  it("accepts evidence only after independent oracle quorum", async function () {
    const { evidence, evidenceHash, regionId, accounts } = await deployFixture();
    const stored = await evidence.evidence(evidenceHash);
    expect(stored.attestationCount).to.equal(2);
    expect(stored.accepted).to.equal(true);
    expect(await evidence.isAcceptedForRegion(evidenceHash, regionId)).to.equal(true);

    await expect(
      evidence
        .connect(accounts.oracle2)
        .attestEvidence(
          evidenceHash,
          regionId,
          stored.metadataHash,
          stored.observedAt,
          1,
          stored.uri
        )
    ).to.be.revertedWithCustomError(evidence, "DuplicateAttestation");
  });

  it("executes an unchallenged reversible action after the public window", async function () {
    const { governor, treasury, stablecoin, accounts, autonomousRequest, networkHelpers } =
      await deployFixture();
    await governor.connect(accounts.automation).propose(autonomousRequest());
    expect(await governor.proposalState(1)).to.equal(0);

    await networkHelpers.time.increase(DAY + 1);
    await governor.connect(accounts.outsider).execute(1);

    expect(await stablecoin.balanceOf(accounts.recipient.address)).to.equal(200n * USDC);
    expect(await treasury.released(1)).to.equal(true);
    expect(await governor.proposalState(1)).to.equal(5);
  });

  it("binds an autonomous policy to its action, executor, and amount", async function () {
    const { governor, accounts, autonomousRequest, ethers } = await deployFixture();
    await expect(
      governor.connect(accounts.automation).propose({
        ...autonomousRequest(),
        actionHash: ethers.id("DREDGE_RIVER")
      })
    ).to.be.revertedWithCustomError(governor, "PolicyNotActive");
    await expect(
      governor.connect(accounts.automation).propose({
        ...autonomousRequest(),
        recipient: accounts.automation.address
      })
    ).to.be.revertedWithCustomError(governor, "PolicyNotActive");
  });

  it("honors emergency policy deactivation until the final execution", async function () {
    const { governor, policies, accounts, autonomousRequest, networkHelpers, policyHash } =
      await deployFixture();
    await governor.connect(accounts.automation).propose(autonomousRequest());
    await policies.deactivatePolicy(policyHash);
    await networkHelpers.time.increase(DAY + 1);
    await expect(governor.execute(1)).to.be.revertedWithCustomError(
      governor,
      "PolicyNotActive"
    );
  });

  it("turns a community challenge into a two-chamber vote", async function () {
    const { governor, stablecoin, accounts, autonomousRequest, networkHelpers } =
      await deployFixture();
    await governor.connect(accounts.automation).propose(autonomousRequest());
    await governor.connect(accounts.community1).challenge(1);
    expect(await governor.proposalState(1)).to.equal(1);

    await governor.connect(accounts.community1).castVote(1, 0, true);
    await governor.connect(accounts.community2).castVote(1, 0, true);
    await governor.connect(accounts.youth1).castVote(1, 1, true);
    await networkHelpers.time.increase(3 * DAY + 1);

    expect(await governor.proposalState(1)).to.equal(3);
    await governor.execute(1);
    expect(await stablecoin.balanceOf(accounts.recipient.address)).to.equal(200n * USDC);
  });

  it("does not let credentials issued after creation vote on an old proposal", async function () {
    const { ethers, governor, civic, accounts, autonomousRequest, networkHelpers, regionId } =
      await deployFixture();
    await governor.connect(accounts.automation).propose(autonomousRequest());
    await governor.connect(accounts.community1).challenge(1);
    await networkHelpers.time.increase(1);
    await civic.registerMember(
      regionId,
      0,
      accounts.community4.address,
      ethers.id("late-member")
    );

    await expect(
      governor.connect(accounts.community4).castVote(1, 0, true)
    ).to.be.revertedWithCustomError(governor, "NotEligible");
  });

  it("makes a guardian pause temporary and escalates autonomous action", async function () {
    const { ethers, governor, accounts, autonomousRequest, networkHelpers } =
      await deployFixture();
    await governor.connect(accounts.automation).propose(autonomousRequest());
    await governor.connect(accounts.guardian).pauseProposal(1, ethers.id("guardian-reason"));

    const stored = await governor.getProposal(1);
    expect(stored.challenged).to.equal(true);
    await governor.connect(accounts.community1).castVote(1, 0, true);
    await governor.connect(accounts.community2).castVote(1, 0, true);
    await governor.connect(accounts.youth1).castVote(1, 1, true);

    await networkHelpers.time.increase(3 * DAY + 1);
    expect(await governor.proposalState(1)).to.equal(2);
    await expect(governor.execute(1)).to.be.revertedWithCustomError(
      governor,
      "ProposalNotReady"
    );
    await expect(
      governor.connect(accounts.guardian).pauseProposal(1, ethers.id("second-reason"))
    ).to.be.revertedWithCustomError(governor, "PauseUnavailable");

    await networkHelpers.time.increase(2 * DAY + 1);
    expect(await governor.proposalState(1)).to.equal(3);
    await governor.execute(1);
  });

  it("requires affected-community authorship and both chambers for irreversible action", async function () {
    const { governor, env, accounts, governedRequest, networkHelpers } = await deployFixture();
    expect(await env.balanceOf(accounts.outsider.address)).to.be.greaterThan(0);
    await expect(
      governor.connect(accounts.outsider).propose(governedRequest())
    ).to.be.revertedWithCustomError(governor, "NotEligible");

    await governor.connect(accounts.community1).propose(governedRequest());
    await expect(
      governor.connect(accounts.outsider).castVote(1, 0, true)
    ).to.be.revertedWithCustomError(governor, "NotEligible");
    await governor.connect(accounts.community1).castVote(1, 0, true);
    await governor.connect(accounts.community2).castVote(1, 0, true);
    await governor.connect(accounts.youth1).castVote(1, 1, true);
    await networkHelpers.time.increase(3 * DAY + 1);
    expect(await governor.proposalState(1)).to.equal(3);
  });

  it("enforces the immutable autonomous epoch budget", async function () {
    const { governor, treasury, accounts, autonomousRequest, networkHelpers } =
      await deployFixture();
    await governor.connect(accounts.automation).propose(autonomousRequest());
    await governor.connect(accounts.automation).propose(autonomousRequest());
    await governor.connect(accounts.automation).propose(autonomousRequest());
    await networkHelpers.time.increase(DAY + 1);

    await governor.execute(1);
    await governor.execute(2);
    await expect(governor.execute(3)).to.be.revertedWithCustomError(
      treasury,
      "AutonomousBudgetExceeded"
    );
    expect((await governor.getProposal(3)).executed).to.equal(false);
  });

  it("does not expose treasury releases to administrators or token holders", async function () {
    const { treasury, accounts } = await deployFixture();
    await expect(
      treasury
        .connect(accounts.admin)
        .release(999, accounts.admin.address, 1n * USDC, false)
    ).to.be.revertedWithCustomError(treasury, "UnauthorizedGovernor");
  });
});
