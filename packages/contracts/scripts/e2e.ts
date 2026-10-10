import { generateKeyPairSync } from "node:crypto";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

import { canonicalJson, sha256Hex, signObservation } from "@terravoce/protocol";
import { buildApp, MemoryObservationStore } from "@terravoce/oracle";
import { network } from "hardhat";

const DAY = 86_400;
const FUNDING_UNIT = 1_000_000n;
const fixedNow = new Date("2026-07-15T12:00:00.000Z");
const policySource = await readFile(resolve("../../policies/po-water-v1.terra"), "utf8");

const app = buildApp({
  store: new MemoryObservationStore(),
  policySource,
  adminToken: "e2e-admin",
  oracleToken: "e2e-oracle",
  now: () => fixedNow
});
const { privateKey, publicKey } = generateKeyPairSync("ed25519");
const privateKeyDerBase64 = privateKey
  .export({ format: "der", type: "pkcs8" })
  .toString("base64");
const publicKeyDerBase64 = publicKey
  .export({ format: "der", type: "spki" })
  .toString("base64");

const registration = await app.inject({
  method: "POST",
  url: "/v1/sensors",
  headers: { "x-admin-token": "e2e-admin" },
  payload: {
    sensorId: "sensor-po-e2e-01",
    regionId: "IT-PO-DELTA",
    publicKeyDerBase64,
    label: "End-to-end Po oxygen sensor"
  }
});
if (registration.statusCode !== 201) throw new Error(registration.body);

for (let sequence = 0; sequence < 12; sequence += 1) {
  const observedAt = new Date(fixedNow.getTime() - (11 - sequence) * 60 * 60_000);
  const observation = signObservation(
    {
      sensorId: "sensor-po-e2e-01",
      regionId: "IT-PO-DELTA",
      metric: "water.oxygen.mg_l",
      value: 7 - sequence * 0.3,
      unit: "mg/L",
      observedAt: observedAt.toISOString(),
      sequence
    },
    privateKeyDerBase64
  );
  const ingestion = await app.inject({
    method: "POST",
    url: "/v1/observations",
    payload: observation
  });
  if (ingestion.statusCode !== 202) throw new Error(ingestion.body);
}

const assessmentResponse = await app.inject({
  method: "POST",
  url: "/v1/assessments/run",
  headers: { "x-oracle-token": "e2e-oracle" },
  payload: {
    regionId: "IT-PO-DELTA",
    metric: "water.oxygen.mg_l",
    forecastHorizonHours: 24,
    requestedAction: "WATER_AERATION",
    requestedAmount: 180,
    asset: "USDC"
  }
});
if (assessmentResponse.statusCode !== 201) throw new Error(assessmentResponse.body);
const oracleResult = assessmentResponse.json();
if (oracleResult.actionDraft === undefined) throw new Error("TerraLex denied the demo action");

const { ethers, networkHelpers } = await network.create();
const [admin, oracle2, automation, community, youth, executor] = await ethers.getSigners();
const stablecoin = await ethers.deployContract("MockStablecoin");
const evidence = await ethers.deployContract("TerraEvidenceRegistry", [2, 0, admin.address]);
const policies = await ethers.deployContract("TerraPolicyRegistry", [0, admin.address]);
const civic = await ethers.deployContract("TerraCivicRegistry", [0, admin.address]);
const treasury = await ethers.deployContract("TerraTreasury", [
  await stablecoin.getAddress(),
  7 * DAY,
  500n * FUNDING_UNIT,
  0,
  admin.address
]);
const governor = await ethers.deployContract("TerraActGovernor", [
  await evidence.getAddress(),
  await policies.getAddress(),
  await civic.getAddress(),
  await treasury.getAddress(),
  10_000,
  10_000,
  3 * DAY,
  DAY,
  5 * DAY,
  250n * FUNDING_UNIT,
  0,
  admin.address
]);
await treasury.setGovernor(await governor.getAddress());
await stablecoin.mint(await treasury.getAddress(), 10_000n * FUNDING_UNIT);
await evidence.grantRole(await evidence.ORACLE_ROLE(), oracle2.address);
await governor.grantRole(await governor.AUTOMATION_ROLE(), automation.address);

const regionId = ethers.id(oracleResult.actionDraft.regionId);
const actionHash = ethers.id(oracleResult.actionDraft.action);
const policyHash = oracleResult.actionDraft.policyHash;
await policies.activatePolicy(
  policyHash,
  ethers.sha256(ethers.toUtf8Bytes(policySource)),
  regionId,
  oracleResult.actionDraft.challengeSeconds,
  [actionHash],
  [executor.address],
  [250n * FUNDING_UNIT],
  "urn:terravoce:policy:po-water-v1"
);
await civic.registerMember(regionId, 0, community.address, ethers.id("e2e-community"));
await civic.registerMember(regionId, 1, youth.address, ethers.id("e2e-youth"));

const evidenceHash = oracleResult.assessment.evidenceHash;
const metadataHash = sha256Hex(canonicalJson(oracleResult.assessment));
const observedAt = Math.floor(Date.parse(oracleResult.assessment.generatedAt) / 1_000);
for (const oracle of [admin, oracle2]) {
  await evidence
    .connect(oracle)
    .attestEvidence(
      evidenceHash,
      regionId,
      metadataHash,
      observedAt,
      1,
      `urn:terravoce:assessment:${oracleResult.assessment.assessmentId}`
    );
}

await governor.connect(automation).propose({
  regionId,
  evidenceHash,
  policyHash,
  actionHash,
  recipient: executor.address,
  amount: BigInt(oracleResult.actionDraft.requestedAmount) * FUNDING_UNIT,
  riskTier: 0,
  requestAutonomy: true,
  metadataURI: `urn:terravoce:action:${oracleResult.assessment.assessmentId}`
});
await networkHelpers.time.increase(oracleResult.actionDraft.challengeSeconds + 1);
await governor.execute(1);

console.log(
  JSON.stringify(
    {
      policyHash,
      evidenceHash,
      proposalId: "1",
      proposalState: Number(await governor.proposalState(1)),
      executorFunding: (await stablecoin.balanceOf(executor.address)).toString(),
      contracts: {
        governor: await governor.getAddress(),
        treasury: await treasury.getAddress(),
        evidence: await evidence.getAddress(),
        policies: await policies.getAddress(),
        civic: await civic.getAddress()
      }
    },
    null,
    2
  )
);
await app.close();

