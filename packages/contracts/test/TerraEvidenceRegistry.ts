import { expect } from "chai";
import { network } from "hardhat";

describe("TerraEvidenceRegistry candidate quorum", function () {
  async function fixture() {
    const { ethers } = await network.create();
    const [admin, honest0, honest1, honest2, malicious, outsider] = await ethers.getSigners();
    const registry = await ethers.deployContract("TerraEvidenceRegistry", [3, 0, admin.address]);
    const role = await registry.ORACLE_ROLE();
    const operators = [honest0, honest1, honest2, malicious];
    for (const operator of operators) await registry.grantRole(role, operator.address);
    await registry.revokeRole(role, admin.address);
    const args = [ethers.id("environmental-batch"), ethers.id("willamette"),
      ethers.id("verified-metadata"), 1_751_414_400, 0, "urn:terravoce:environmental-batch"] as const;
    return { ethers, admin, operators, malicious, outsider, registry, role, args };
  }

  it("lets three honest votes finalize after malicious first metadata", async function () {
    const f = await fixture();
    await f.registry.connect(f.malicious).attestEvidence(f.args[0], f.args[1],
      f.ethers.id("false-first-metadata"), f.args[3], f.args[4], f.args[5]);
    for (const operator of f.operators.slice(0, 3)) {
      await f.registry.connect(operator).attestEvidence(...f.args);
    }
    const final = await f.registry.evidence(f.args[0]);
    expect(final.accepted).to.equal(true);
    expect(final.metadataHash).to.equal(f.args[2]);
    expect(final.attestationCount).to.equal(3);
    expect(await f.registry.isAcceptedForRegion(f.args[0], f.args[1])).to.equal(true);
  });

  const alteredFields = ["region", "metadata", "time", "kind", "uri"] as const;
  for (const field of alteredFields) {
    it(`isolates malicious first ${field} and finalizes every honest field together`, async function () {
      const f = await fixture();
      const bad = [...f.args];
      if (field === "region") bad[1] = f.ethers.id("false-region");
      if (field === "metadata") bad[2] = f.ethers.id("false-metadata");
      if (field === "time") bad[3] = f.args[3] + 1;
      if (field === "kind") bad[4] = 1;
      if (field === "uri") bad[5] = f.args[5] + ":\u00e8:alternative";
      const wrongId = await f.registry.evidenceCandidateId(...bad);
      const correctId = await f.registry.evidenceCandidateId(...f.args);
      expect(wrongId).not.to.equal(correctId);
      await f.registry.connect(f.malicious).attestEvidence(...bad);
      for (let i = 0; i < 3; i++) {
        await f.registry.connect(f.operators[i]).attestEvidence(...f.args);
        expect(await f.registry.isAcceptedForRegion(f.args[0], f.args[1])).to.equal(i === 2);
      }
      const final = await f.registry.evidence(f.args[0]);
      expect([final.regionId, final.metadataHash, final.observedAt, Number(final.kind), final.uri])
        .to.deep.equal([f.args[1], f.args[2], BigInt(f.args[3]), f.args[4], f.args[5]]);
      expect(final.attestationCount).to.equal(3);
      expect(await f.registry.acceptedCandidateId(f.args[0])).to.equal(correctId);
      const rejected = await f.registry.candidate(f.args[0], wrongId);
      expect(rejected.attestationCount).to.equal(1);
      expect(rejected.accepted).to.equal(false);
    });
  }

  it("finalizes honest metadata in all 24 arrival orders of one malicious and three honest identities", async function () {
    function permutations(values: number[]): number[][] {
      return values.length === 0 ? [[]] : values.flatMap((v, i) =>
        permutations(values.filter((_, j) => i !== j)).map(rest => [v, ...rest]));
    }
    const orders = permutations([0, 1, 2, 3]);
    expect(orders.length).to.equal(24);
    for (const order of orders) {
      const f = await fixture();
      const bad = [...f.args];
      bad[2] = f.ethers.id("malicious-arrival-order");
      for (const identity of order) {
        if (identity === 3 && (await f.registry.evidence(f.args[0])).accepted) {
          await expect(f.registry.connect(f.malicious).attestEvidence(...bad))
            .to.be.revertedWithCustomError(f.registry, "EvidenceMismatch");
        } else {
          await f.registry.connect(f.operators[identity]).attestEvidence(...(identity === 3 ? bad : f.args));
        }
      }
      const final = await f.registry.evidence(f.args[0]);
      expect(final.accepted, `order ${order}`).to.equal(true);
      expect(final.metadataHash).to.equal(f.args[2]);
      expect(final.attestationCount).to.equal(3);
    }
  });

  it("does not combine two votes for each of two different envelopes", async function () {
    const f = await fixture();
    const bad = [...f.args]; bad[2] = f.ethers.id("split-envelope");
    for (let i = 0; i < 4; i++) {
      await f.registry.connect(f.operators[i]).attestEvidence(...(i < 2 ? f.args : bad));
    }
    for (const args of [f.args, bad]) {
      const candidate = await f.registry.candidate(f.args[0], await f.registry.evidenceCandidateId(...args));
      expect(candidate.attestationCount).to.equal(2);
      expect(candidate.accepted).to.equal(false);
    }
    expect(await f.registry.acceptedCandidateId(f.args[0])).to.equal(f.ethers.ZeroHash);
    expect(await f.registry.isAcceptedForRegion(f.args[0], f.args[1])).to.equal(false);
  });

  it("does not promise progress with one malicious identity and one absent honest identity", async function () {
    const f = await fixture();
    const bad = [...f.args]; bad[2] = f.ethers.id("withholding-or-false-envelope");
    await f.registry.connect(f.malicious).attestEvidence(...bad);
    for (const operator of f.operators.slice(0, 2)) await f.registry.connect(operator).attestEvidence(...f.args);
    const good = await f.registry.candidate(f.args[0], await f.registry.evidenceCandidateId(...f.args));
    expect(good.attestationCount).to.equal(2);
    expect(good.accepted).to.equal(false);
    expect(await f.registry.isAcceptedForRegion(f.args[0], f.args[1])).to.equal(false);
  });

  it("keeps one vote per identity and content root across candidates and role re-enrollment", async function () {
    const f = await fixture();
    const bad = [...f.args]; bad[2] = f.ethers.id("equivocation");
    await f.registry.connect(f.malicious).attestEvidence(...bad);
    await expect(f.registry.connect(f.malicious).attestEvidence(...f.args))
      .to.be.revertedWithCustomError(f.registry, "DuplicateAttestation");
    await f.registry.revokeRole(f.role, f.malicious.address);
    await f.registry.grantRole(f.role, f.malicious.address);
    await expect(f.registry.connect(f.malicious).attestEvidence(...f.args))
      .to.be.revertedWithCustomError(f.registry, "DuplicateAttestation");
    const other = [...f.args]; other[0] = f.ethers.id("another-content-root");
    await f.registry.connect(f.malicious).attestEvidence(...other);
    expect(await f.registry.hasAttested(other[0], f.malicious.address)).to.equal(true);
  });

  it("preserves authorization and rejects invalid input without consuming a vote", async function () {
    const f = await fixture();
    await expect(f.registry.connect(f.outsider).attestEvidence(...f.args))
      .to.be.revertedWithCustomError(f.registry, "AccessControlUnauthorizedAccount");
    for (const index of [0, 1, 2, 3, 5]) {
      const invalid = [...f.args];
      invalid[index] = index === 3 ? 0 : index === 5 ? "" : f.ethers.ZeroHash;
      await expect(f.registry.connect(f.operators[0]).attestEvidence(...invalid))
        .to.be.revertedWithCustomError(f.registry, "InvalidEvidence");
    }
    expect(await f.registry.hasAttested(f.args[0], f.operators[0].address)).to.equal(false);
    await f.registry.connect(f.operators[0]).attestEvidence(...f.args);
    expect((await f.registry.evidence(f.args[0])).attestationCount).to.equal(1);
  });

  it("freezes the accepted envelope and permits later matching attestations", async function () {
    const f = await fixture();
    for (const operator of f.operators.slice(0, 3)) await f.registry.connect(operator).attestEvidence(...f.args);
    const correctId = await f.registry.acceptedCandidateId(f.args[0]);
    const bad = [...f.args]; bad[1] = f.ethers.id("later-false-region");
    await expect(f.registry.connect(f.malicious).attestEvidence(...bad))
      .to.be.revertedWithCustomError(f.registry, "EvidenceMismatch");
    expect(await f.registry.isAcceptedForRegion(f.args[0], bad[1])).to.equal(false);
    expect(await f.registry.hasAttested(f.args[0], f.malicious.address)).to.equal(false);
    await expect(f.registry.connect(f.malicious).attestEvidence(...f.args))
      .to.emit(f.registry, "EvidenceCandidateAttested").withArgs(f.args[0], correctId, f.malicious.address, 4);
    expect((await f.registry.evidence(f.args[0])).attestationCount).to.equal(4);
    expect(await f.registry.acceptedCandidateId(f.args[0])).to.equal(correctId);
  });

  it("binds the complete envelope to encoding version, chain, registry and content root", async function () {
    const f = await fixture();
    const chainId = (await f.ethers.provider.getNetwork()).chainId;
    const encoded = f.ethers.AbiCoder.defaultAbiCoder().encode(
      ["bytes32", "uint256", "address", "bytes32", "bytes32", "bytes32", "uint64", "uint8", "string"],
      [f.ethers.id("TerraVoce.EvidenceCandidate.v1"), chainId, await f.registry.getAddress(), ...f.args]);
    const id = await f.registry.evidenceCandidateId(...f.args);
    expect(id).to.equal(f.ethers.keccak256(encoded));
    const other = await f.ethers.deployContract("TerraEvidenceRegistry", [3, 0, f.admin.address]);
    expect(await other.evidenceCandidateId(...f.args)).not.to.equal(id);
    const anotherRoot = [...f.args]; anotherRoot[0] = f.ethers.id("other-root");
    expect(await f.registry.evidenceCandidateId(...anotherRoot)).not.to.equal(id);
  });

  it("keeps the first pending getter provisional and reports each candidate count separately", async function () {
    const f = await fixture();
    const bad = [...f.args]; bad[2] = f.ethers.id("provisional-first-metadata");
    await f.registry.connect(f.malicious).attestEvidence(...bad);
    for (const operator of f.operators.slice(0, 2)) await f.registry.connect(operator).attestEvidence(...f.args);
    const pending = await f.registry.evidence(f.args[0]);
    expect(pending.metadataHash).to.equal(bad[2]);
    expect(pending.attestationCount).to.equal(1);
    expect(pending.accepted).to.equal(false);
    expect((await f.registry.candidate(f.args[0], await f.registry.evidenceCandidateId(...f.args))).attestationCount)
      .to.equal(2);
    await f.registry.connect(f.operators[2]).attestEvidence(...f.args);
    expect((await f.registry.evidence(f.args[0])).metadataHash).to.equal(f.args[2]);
  });

  it("does not charge honest finalization for clearing a malicious first URI", async function () {
    async function finalizationGas(uriBytes: number) {
      const f = await fixture();
      const bad = [...f.args]; bad[5] = "x".repeat(uriBytes);
      await f.registry.connect(f.malicious).attestEvidence(...bad);
      for (const operator of f.operators.slice(0, 2)) await f.registry.connect(operator).attestEvidence(...f.args);
      const receipt = await (await f.registry.connect(f.operators[2]).attestEvidence(...f.args)).wait();
      expect((await f.registry.evidence(f.args[0])).accepted).to.equal(true);
      return receipt!.gasUsed;
    }
    const shortUriGas = await finalizationGas(32);
    const longUriGas = await finalizationGas(10_000);
    console.log(`    honest finalization gas: 32-byte attacker URI=${shortUriGas}; 10000-byte attacker URI=${longUriGas}`);
    expect(longUriGas <= shortUriGas + 20_000n).to.equal(true);
  });
});
