import { generateKeyPairSync } from "node:crypto";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { resolve } from "node:path";
import { canonicalJson, sha256Hex, signObservation } from "@terravoce/protocol";
import { buildApp, MemoryObservationStore } from "@terravoce/oracle";
import { expect } from "chai";
import { network } from "hardhat";

const DAY = 86_400;
const UNIT = 1_000_000n;
const root = resolve("../..");
const folder = resolve(root, "services/autonomy/.runtime/scenarios", `run-${Date.now()}`);
await mkdir(folder, { recursive: true });
const policySource = await readFile(resolve(root, "policies/po-water-v1.terra"), "utf8");
const now = new Date();
const { privateKey, publicKey } = generateKeyPairSync("ed25519");
const sensor = { sensorId: "sensor-autonomy-01", regionId: "IT-PO-DELTA",
  publicKeyDerBase64: publicKey.export({ format: "der", type: "spki" }).toString("base64"),
  label: "Synthetic autonomy failure-test sensor" };
const observations = Array.from({length: 12}, (_, sequence) => signObservation({
  sensorId: sensor.sensorId, regionId: sensor.regionId, metric: "water.oxygen.mg_l", unit: "mg/L",
  value: 7 - sequence * 0.3, sequence,
  observedAt: new Date(now.getTime() - (11-sequence)*3_600_000).toISOString(),
}, privateKey.export({ format: "der", type: "pkcs8" }).toString("base64")));
const fixture = { now: now.toISOString(), policySource, sensors: [sensor], observations };
const app = buildApp({ store: new MemoryObservationStore(), policySource,
  adminToken: "local-fixture-admin", oracleToken: "local-fixture-oracle", now: () => now });
await app.inject({method:"POST", url:"/v1/sensors", headers:{"x-admin-token":"local-fixture-admin"}, payload:sensor});
for (const observation of observations) {
  const response = await app.inject({method:"POST", url:"/v1/observations", payload:observation});
  expect(response.statusCode).to.equal(202);
}
const input = {regionId:sensor.regionId, metric:"water.oxygen.mg_l", forecastHorizonHours:24,
  requestedAction:"EXTRA_SAMPLING", requestedAmount:40, asset:"USDC"};
const response = await app.inject({method:"POST", url:"/v1/assessments/run", headers:{"x-oracle-token":"local-fixture-oracle"}, payload:input});
expect(response.statusCode).to.equal(201);
const result = response.json();
expect(result.decision.allowed).to.equal(true);
await app.close();
const { ethers, networkHelpers } = await network.create();
const [admin, oracle2, community, youth, executor, relayer] = await ethers.getSigners();
const operators = Array.from({length:4}, () => ethers.Wallet.createRandom());
for (const [i, wallet] of operators.entries()) {
  await mkdir(resolve(folder, `keys${i}`));
  await writeFile(resolve(folder, `keys${i}/ethereum_private_key.txt`), wallet.privateKey.slice(2));
}
const stablecoin = await ethers.deployContract("MockStablecoin");
const evidence = await ethers.deployContract("TerraEvidenceRegistry", [2,0,admin.address]);
const policies = await ethers.deployContract("TerraPolicyRegistry", [0,admin.address]);
const civic = await ethers.deployContract("TerraCivicRegistry", [0,admin.address]);
const treasury = await ethers.deployContract("TerraTreasury", [await stablecoin.getAddress(),7*DAY,500n*UNIT,0,admin.address]);
const governor = await ethers.deployContract("TerraActGovernor", [await evidence.getAddress(),await policies.getAddress(),await civic.getAddress(),await treasury.getAddress(),10000,10000,3*DAY,DAY,5*DAY,250n*UNIT,0,admin.address]);
const bridge = await ethers.deployContract("TerraAutonomyBridge", [await governor.getAddress(),operators.map(w=>w.address)]);
await governor.grantRole(await governor.AUTOMATION_ROLE(),await bridge.getAddress());
await governor.revokeRole(await governor.AUTOMATION_ROLE(),admin.address);
await treasury.setGovernor(await governor.getAddress());
await stablecoin.mint(await treasury.getAddress(),1000n*UNIT);
await evidence.grantRole(await evidence.ORACLE_ROLE(),oracle2.address);
const draft = result.actionDraft;
const regionId = ethers.id(draft.regionId);
await policies.activatePolicy(draft.policyHash,ethers.sha256(ethers.toUtf8Bytes(policySource)),regionId,draft.challengeSeconds,[ethers.id(draft.action)],[executor.address],[50n*UNIT],"urn:terravoce:policy:po-water-v1");
await civic.registerMember(regionId,0,community.address,ethers.id("autonomy-community"));
await civic.registerMember(regionId,1,youth.address,ethers.id("autonomy-youth"));
for (const signer of [admin,oracle2]) {
  await evidence.connect(signer).attestEvidence(draft.evidenceHash,regionId,sha256Hex(canonicalJson(result.assessment)),Math.floor(now.getTime()/1000),1,"urn:terravoce:synthetic-evidence");
}
const request = {regionId,evidenceHash:draft.evidenceHash,policyHash:draft.policyHash,
  actionHash:ethers.id(draft.action),recipient:executor.address,amount:(40n*UNIT).toString(),riskTier:0,
  requestAutonomy:true,metadataURI:"urn:terravoce:synthetic:extra-sampling"};
const jobId = ethers.id(`synthetic-${folder}`);
const validUntil = (await networkHelpers.time.latest())+3600;
const digest = await bridge.actionDigest(jobId,validUntil,request);
const job = {version:1,jobId,validUntil,digest,chainId:Number((await ethers.provider.getNetwork()).chainId),
  bridge:await bridge.getAddress(),governor:await governor.getAddress(),operators:operators.map(w=>w.address),
  input,expectedAssessment:result.assessment,expectedDraft:draft,assetDecimals:6,request};
await writeFile(resolve(folder,"fixture.json"),JSON.stringify(fixture,null,2));
await writeFile(resolve(folder,"job.json"),JSON.stringify(job,null,2));
console.log("Testing 4 real AEA/Tendermint/Oracle replicas; local synthetic observations and mock funding.");
const python = process.env.AUTONOMY_PYTHON ?? "python";
let child;
try {
  child = await promisify(execFile)(python,[resolve(root,"services/autonomy/run_cluster.py"),folder],{timeout:600_000,maxBuffer:4*1024*1024});
} catch (error: any) {
  throw new Error(`Autonomy cluster failed; inspect ${folder}.\n${error.stderr?.slice(-2500) ?? error.message}`);
}
console.log(child.stdout);
const cluster = JSON.parse(await readFile(resolve(folder,"cluster-results.json"),"utf8"));
const certificate = cluster[1].certificate;
expect(certificate.digest).to.equal(digest);
expect(certificate.signatures).to.have.length(3);
const signatures = certificate.signatures.sort((a:any,b:any)=>a.signer.toLowerCase().localeCompare(b.signer.toLowerCase())).map((s:any)=>s.signature);
for (const entry of certificate.signatures) expect(ethers.verifyMessage(ethers.getBytes(digest),entry.signature)).to.equal(entry.signer);
await expect(bridge.submit(jobId,validUntil,request,signatures.slice(0,2))).to.be.revertedWithCustomError(bridge,"InvalidQuorum");
await expect(bridge.submit(jobId,validUntil,{...request,amount:(41n*UNIT).toString()},signatures)).to.be.revertedWithCustomError(bridge,"InvalidQuorum");
await expect(bridge.submit(jobId,validUntil,request,[signatures[0],signatures[0],signatures[1]])).to.be.revertedWithCustomError(bridge,"InvalidQuorum");
await bridge.connect(relayer).submit(jobId,validUntil,request,signatures);
await expect(bridge.submit(jobId,validUntil,request,signatures)).to.be.revertedWithCustomError(bridge,"AlreadySubmitted");
await expect(governor.execute(1)).to.be.revertedWithCustomError(governor,"ProposalNotReady");
// Real civic intervention: one challenge makes both chambers' approval necessary.
await governor.connect(community).challenge(1);
await governor.connect(community).castVote(1,0,true);
await networkHelpers.time.increase(3*DAY+1);
expect(Number(await governor.proposalState(1))).to.equal(4); // Rejected: no youth approval.
await expect(governor.execute(1)).to.be.revertedWithCustomError(governor,"ProposalNotReady");
expect(await stablecoin.balanceOf(executor.address)).to.equal(0n);
const report = {passed:true,synthetic:true,runFolder:folder,jobId,digest,
  singleNodeOutage:{certificateSigners:3,heights:cluster[1].heightsAfter},
  twoNodeOutage:{certificate:false,heights:cluster[0].heightsAfter},
  checks:["two signatures rejected","tampered amount rejected","duplicate signer rejected","replay rejected",
    "challenge window enforced","community challenge enforced","youth approval required","no funds released"],
  proposalId:"1",proposalState:"Rejected",executorFunding:"0"};
await writeFile(resolve(folder,"e2e-report.json"),JSON.stringify(report,null,2));
console.log(JSON.stringify(report,null,2));
