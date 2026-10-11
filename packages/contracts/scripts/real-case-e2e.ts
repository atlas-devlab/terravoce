import assert from "node:assert/strict";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { canonicalJson, sha256Hex } from "@terravoce/protocol";
import { buildApp, MemoryObservationStore } from "@terravoce/oracle";
import { deliverResult, importerObservations, loadDataset, prepareCase, replay,
  sameAssessment, verifyResult, windowAt } from "@terravoce/environmental-case";
import { network } from "hardhat";

const dataset = await loadDataset(resolve("../../docs/datasets/usgs-willamette"));
const policySource = await readFile(resolve("../../policies/usgs-data-review-v1.terra"), "utf8");
const spec = prepareCase(dataset, policySource);
const imported = importerObservations(windowAt(dataset, spec.origin));
const app = buildApp({ store: new MemoryObservationStore(), policySource,
  adminToken: "local-case-admin", oracleToken: "local-case-oracle", now: () => new Date(spec.origin) });
const sensor = await app.inject({ method: "POST", url: "/v1/sensors",
  headers: { "x-admin-token": "local-case-admin" }, payload: {
    sensorId: "usgs-http-importer-14211720", regionId: spec.regionId,
    publicKeyDerBase64: imported.publicKeyDerBase64,
    label: "Local HTTP importer signature; NOT a USGS sensor signature"
  } });
assert.equal(sensor.statusCode, 201);
for (const entry of imported.observations) {
  const accepted = await app.inject({ method: "POST", url: "/v1/observations", payload: entry.observation });
  assert.equal(accepted.statusCode, 202, accepted.body);
}
const response = await app.inject({ method: "POST", url: "/v1/assessments/run",
  headers: { "x-oracle-token": "local-case-oracle" }, payload: {
    regionId: spec.regionId, metric: "water.oxygen.mg_l", forecastHorizonHours: 1,
    requestedAction: spec.action, requestedAmount: spec.requestedAmount, asset: spec.asset
  } });
assert.equal(response.statusCode, 201, response.body);
const oracle = response.json();
assert.equal(oracle.decision.allowed, true);
sameAssessment(oracle.assessment, spec.assessment);
assert.equal(oracle.actionDraft.policyHash, spec.policyHash);

const { ethers, networkHelpers } = await network.create();
const [admin, oracle2, replica3, replica4, community, youth, executor, scientist, outsider] = await ethers.getSigners();
const token = await ethers.deployContract("MockStablecoin");
const evidence = await ethers.deployContract("TerraEvidenceRegistry", [2, 0, admin.address]);
const policies = await ethers.deployContract("TerraPolicyRegistry", [0, admin.address]);
const civic = await ethers.deployContract("TerraCivicRegistry", [0, admin.address]);
const unit = 1_000_000n, amount = 10n * unit, day = 86400;
const treasury = await ethers.deployContract("TerraTreasury", [await token.getAddress(), 7 * day, 10n * unit, 0, admin.address]);
const governor = await ethers.deployContract("TerraActGovernor", [await evidence.getAddress(), await policies.getAddress(),
  await civic.getAddress(), await treasury.getAddress(), 10000, 10000, 3 * day, day, 5 * day, amount, 0, admin.address]);
await treasury.setGovernor(await governor.getAddress());
await token.mint(await treasury.getAddress(), amount);
const regionId = ethers.id(spec.regionId);
const escrow = await ethers.deployContract("TerraResultEscrow", [await governor.getAddress(), {
  caseHash: spec.caseHash, regionId, evidenceHash: spec.assessment.evidenceHash, policyHash: spec.policyHash,
  amount, executor: executor.address, scientificReviewer: scientist.address, communityReviewer: community.address
}]);
await policies.activatePolicy(spec.policyHash, spec.policySourceHash, regionId, spec.challengeSeconds,
  [ethers.id(spec.action)], [await escrow.getAddress()], [amount], `urn:terravoce:policy:${spec.policyHash}`);
await civic.registerMember(regionId, 0, community.address, ethers.id("local-case-community"));
await civic.registerMember(regionId, 1, youth.address, ethers.id("local-case-youth"));
await evidence.grantRole(await evidence.ORACLE_ROLE(), oracle2.address);
const evidenceURI = `urn:terravoce:case:${spec.caseHash}`;
for (const signer of [admin, oracle2]) {
  await evidence.connect(signer).attestEvidence(spec.assessment.evidenceHash, regionId,
    sha256Hex(canonicalJson(spec)), Math.floor(Date.parse(spec.origin) / 1000), 1, evidenceURI);
}
const operators = [admin, oracle2, replica3, replica4];
const bridge = await ethers.deployContract("TerraAutonomyBridge", [await governor.getAddress(), operators.map((s) => s.address)]);
await governor.grantRole(await governor.AUTOMATION_ROLE(), await bridge.getAddress());
const request = { regionId, evidenceHash: spec.assessment.evidenceHash, policyHash: spec.policyHash,
  actionHash: ethers.id(spec.action), recipient: await escrow.getAddress(), amount, riskTier: 0,
  requestAutonomy: true, metadataURI: evidenceURI };
const validUntil = (await networkHelpers.time.latest()) + 3600;
const digest = await bridge.actionDigest(spec.caseHash, validUntil, request);
// Fixture certificate exercises the existing bridge. This script does not launch ABCI replicas.
const participating = operators.slice(0, 3).sort((a, b) => a.address.toLowerCase().localeCompare(b.address.toLowerCase()));
const signatures = await Promise.all(participating.map((s) => s.signMessage(ethers.getBytes(digest))));
const submission = await (await bridge.submit(spec.caseHash, validUntil, request, signatures)).wait();
await escrow.bindProposal(1);
let prematureGovernanceRejected = false;
try { await governor.execute(1); } catch { prematureGovernanceRejected = true; }
assert.equal(prematureGovernanceRejected, true);
await governor.connect(community).challenge(1);
await governor.connect(community).castVote(1, 0, true);
// A community vote alone cannot authorize execution: youth approval remains required.
await governor.connect(youth).castVote(1, 1, true);
await networkHelpers.time.increase(3 * day + 1);
const civicExecution = await (await governor.execute(1)).wait();
assert.equal(await token.balanceOf(executor.address), 0n);
assert.equal(await token.balanceOf(await escrow.getAddress()), amount);
let prematurePaymentRejected = false;
try { await escrow.release(); } catch { prematurePaymentRejected = true; }
assert.equal(prematurePaymentRejected, true);
const result = deliverResult(dataset, spec);
await escrow.connect(executor).submitResult(result.resultHash, `urn:terravoce:result:${result.resultHash}`);
let outsiderReviewRejected = false;
try { await escrow.connect(outsider).approveResult(result.resultHash); } catch { outsiderReviewRejected = true; }
assert.equal(outsiderReviewRejected, true);
// These are simulated role identities controlled by one local test process, not independent people.
const scientificReproduction = verifyResult(dataset, policySource, spec, result);
await escrow.connect(scientist).approveResult(scientificReproduction.resultHash);
let oneReviewPaymentRejected = false;
try { await escrow.release(); } catch { oneReviewPaymentRejected = true; }
assert.equal(oneReviewPaymentRejected, true);
const communityReproduction = verifyResult(dataset, policySource, spec, result);
await escrow.connect(community).approveResult(communityReproduction.resultHash);
const payment = await (await escrow.release()).wait();
assert.equal(await token.balanceOf(executor.address), amount);
assert.equal(await token.balanceOf(await escrow.getAddress()), 0n);
const { rows: _rows, ...scientificReplay } = replay(dataset);
const report = {
  version: "real-data-local-chain-v1", caseHash: spec.caseHash, resultHash: result.resultHash,
  observationSource: "real USGS approved archival measurements",
  importerSignature: "ephemeral local importer; not USGS signature",
  governance: "simulated affected-community and youth identities; both voted",
  consensus: "3-of-4 local signer fixture through TerraAutonomyBridge; ABCI cluster not launched in this run",
  verification: scientificReproduction,
  independentFieldReview: "pending; no real operator/reviewer enrolled",
  physicalSampling: "not performed", ecologicalImprovementVerified: false,
  funding: { mode: "local valueless test tokens", amount: "10 TEST", paidAfterBothReviews: true },
  negativeChecks: { prematureGovernanceRejected, prematurePaymentRejected, outsiderReviewRejected, oneReviewPaymentRejected },
  transactions: { bridgeProposal: submission!.hash, civicExecution: civicExecution!.hash, payment: payment!.hash },
  contracts: { bridge: await bridge.getAddress(), governor: await governor.getAddress(), escrow: await escrow.getAddress() },
  result, scientificReplay
};
const folder = resolve(process.env.TERRAVOCE_CASE_OUTPUT ?? "../../outputs/real-case");
await mkdir(folder, { recursive: true });
await writeFile(resolve(folder, "chain-run.json"), JSON.stringify(report, null, 2) + "\n");
console.log(JSON.stringify(report, null, 2));
await app.close();
