import assert from "node:assert/strict";
import { cp, mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { execFile, execFileSync } from "node:child_process";
import { promisify } from "node:util";
import { resolve } from "node:path";
import { canonicalJson, sha256Hex } from "@terravoce/protocol";
import { discoverAndCollect, discoveryProtocolSchema, evidenceCommitment, verifyDiscovery, type DiscoveryArchive } from "@terravoce/environmental-case";
import { network } from "hardhat";

const run=promisify(execFile), root=resolve("../.."), source=resolve(root,"docs/datasets/autonomous-source");
const output=resolve(process.env.TERRAVOCE_SOURCE_OUTPUT??resolve(root,"outputs/autonomous-source"));
const sealPath="docs/evidence/autonomous-source/seal.json";
const committedSeal=JSON.parse(execFileSync("git",["show",`HEAD:${sealPath}`],{cwd:root,encoding:"utf8"}));
const localSeal=JSON.parse(await readFile(resolve(root,sealPath),"utf8"));
assert.equal(canonicalJson(localSeal),canonicalJson(committedSeal),"Local seal differs from committed external checkpoint");
const seal=committedSeal;
const honest=await verifyDiscovery(source,seal.evidenceHash);
const scratchRoot=resolve(process.env.TERRAVOCE_SOURCE_SCRATCH??resolve(root,"work/source-chain-runs"));await mkdir(scratchRoot,{recursive:true});
const scratch=await mkdtemp(resolve(scratchRoot,"run-"));
const altered=resolve(scratch,"altered"), coherent=resolve(scratch,"coherent-false-publisher");
await cp(source,altered,{recursive:true});await cp(source,coherent,{recursive:true});
const protocolRaw=await readFile(resolve(source,"protocol.json"),"utf8"), protocol=discoveryProtocolSchema.parse(JSON.parse(protocolRaw));
const archive:DiscoveryArchive=JSON.parse(await readFile(resolve(source,"manifest.json"),"utf8"));
const observation=archive.responses.find(a=>new URL(a.url).pathname.endsWith("/continuous/items"))!;
const originalRaw=JSON.parse(await readFile(resolve(source,observation.file),"utf8"));
const originalValue=Number(originalRaw.features[0].properties.value);
originalRaw.features[0].properties.value="9.9";
await writeFile(resolve(altered,observation.file),JSON.stringify(originalRaw));
// A stronger adversary controls the initial publisher output AND its new commitment.
const coherentArchive=structuredClone(archive), coherentEntry=coherentArchive.responses.find(a=>a.file===observation.file)!;
for(const f of originalRaw.features)f.properties.value="9.9";
const coherentRaw=JSON.stringify(originalRaw);
coherentEntry.rawSha256=sha256Hex(coherentRaw);coherentEntry.bytes=Buffer.byteLength(coherentRaw);
await writeFile(resolve(coherent,observation.file),coherentRaw);
await writeFile(resolve(coherent,"manifest.json"),JSON.stringify(coherentArchive,null,2)+"\n");
const rawMap=new Map(await Promise.all(coherentArchive.responses.map(async a=>[a.url,await readFile(resolve(coherent,a.file),"utf8")] as const)));
const falseReproduction=await discoverAndCollect(protocol,async u=>{const raw=rawMap.get(u);if(!raw)throw new Error("Unarchived false-source request");return raw;});
const falseEvidence=evidenceCommitment(protocolRaw,coherentArchive,falseReproduction);
assert.notEqual(falseEvidence.evidenceHash,honest.evidenceHash);

const worker=resolve(root,"services/environmental-case/dist/discovery-replica.js");
async function replica(id:number,folder:string,expected:string){
  try{const {stdout}=await run(process.execPath,[worker,folder,expected],{timeout:30000,maxBuffer:100000});return {id,...JSON.parse(stdout.trim())};}
  catch(error){const e=error as Error&{stdout?:string};return {id,...(e.stdout?JSON.parse(e.stdout.trim()):{verified:false,error:e.message})};}
}
// These are real separate local verification processes, not independently administered nodes.
const honestReplicas=await Promise.all([0,1,2].map(i=>replica(i,source,seal.evidenceHash)));
assert.equal(honestReplicas.every(r=>r.verified&&r.evidenceHash===honest.evidenceHash),true);
const alteredReplica=await replica(3,altered,seal.evidenceHash);assert.equal(alteredReplica.verified,false);
const coherentAgainstOriginal=await replica(3,coherent,seal.evidenceHash);assert.equal(coherentAgainstOriginal.verified,false);
const falseInitialSnapshot=await replica(3,coherent,falseEvidence.evidenceHash);assert.equal(falseInitialSnapshot.verified,true);

const {ethers}=await network.create();
const [admin,operator0,operator1,operator2,operator3,outsider,sybil0,sybil1,sybil2]=await ethers.getSigners();
const operators=[operator0,operator1,operator2,operator3];
const registry=await ethers.deployContract("TerraEvidenceRegistry",[3,0,admin.address]);
await registry.waitForDeployment();
const role=await registry.ORACLE_ROLE();for(const s of operators)await (await registry.grantRole(role,s.address)).wait();
await (await registry.revokeRole(role,admin.address)).wait();
const verificationArtifacts=await Promise.all([
  "services/environmental-case/src/discovery.ts",
  "services/environmental-case/src/discovery-replica.ts",
  "packages/contracts/contracts/TerraEvidenceRegistry.sol",
  "packages/contracts/scripts/source-evidence-e2e.ts",
  "services/environmental-case/dist/discovery.js",
  "services/environmental-case/dist/discovery-replica.js",
  "packages/protocol/dist/index.js",
  "packages/protocol/dist/crypto.js",
  "packages/protocol/dist/schemas.js",
  "pnpm-lock.yaml",
  "tsconfig.base.json",
  "services/environmental-case/tsconfig.json",
  "packages/protocol/tsconfig.json"
].map(async file=>({file,rawSha256:sha256Hex(await readFile(resolve(root,file)))})));
const metadata={version:"autonomous-source-chain-metadata-v2",registryRule:"TerraVoce.EvidenceCandidate.v1",evidence:honest,verificationArtifacts,scope:"Reproducibility acceptance only; no physical-truth attestation"};
const region=ethers.id(protocol.territory.regionId), metadataHash=sha256Hex(canonicalJson(metadata));
const observedAt=Math.floor(Date.parse(honest.reproduction.observations.at(-1)!.time)/1000), uri=`urn:terravoce:source:${honest.evidenceHash}`;
const args=[honest.evidenceHash,region,metadataHash,observedAt,0,uri] as const;
async function mustRevert(action:()=>Promise<unknown>,name:string){let rejected=false;try{await action();}catch(error){assert.match(String(error),new RegExp(name));rejected=true;}assert.equal(rejected,true,`Expected ${name}`);}
await mustRevert(()=>registry.connect(outsider).attestEvidence(...args),"AccessControlUnauthorizedAccount");
const acceptedTransactions:{hash:string;blockNumber:number;blockHash:string;operator:string}[]=[];
for(let i=0;i<3;i++){
  const receipt=await (await registry.connect(operators[i]!).attestEvidence(...args)).wait();
  acceptedTransactions.push({hash:receipt!.hash,blockNumber:receipt!.blockNumber,blockHash:receipt!.blockHash,operator:operators[i]!.address});
  assert.equal(await registry.isAcceptedForRegion(honest.evidenceHash,region),i===2);
  if(i===0){
    await mustRevert(()=>registry.connect(operator0).attestEvidence(...args),"DuplicateAttestation");
  }
}
const honestState=await registry.evidence(honest.evidenceHash);
assert.equal(honestState.attestationCount,3n);assert.equal(await registry.hasAttested(honest.evidenceHash,operator3.address),false);
await mustRevert(()=>registry.connect(operator3).attestEvidence(honest.evidenceHash,region,ethers.id("altered-metadata"),observedAt,0,uri),"EvidenceMismatch");
const acceptedCandidateId=await registry.acceptedCandidateId(honest.evidenceHash);
assert.equal(acceptedCandidateId,await registry.evidenceCandidateId(...args));
const falseArgs=[falseEvidence.evidenceHash,region,sha256Hex(canonicalJson(falseEvidence)),observedAt,0,`urn:terravoce:source:${falseEvidence.evidenceHash}`] as const;
await (await registry.connect(operator0).attestEvidence(...falseArgs)).wait();
await (await registry.connect(operator1).attestEvidence(...falseArgs)).wait();
const twoCompromised=await registry.isAcceptedForRegion(falseEvidence.evidenceHash,region);assert.equal(twoCompromised,false);
const collusionReceipt=await(await registry.connect(operator2).attestEvidence(...falseArgs)).wait();
const threeCompromised=await registry.isAcceptedForRegion(falseEvidence.evidenceHash,region);assert.equal(threeCompromised,true);
const twoOnline=[honestReplicas[0],honestReplicas[1]];
assert.equal(twoOnline.length<Number(await registry.oracleQuorum()),true);
// A fresh registry round exercises the same honest batch with only two available attestors.
const stalledRegistry=await ethers.deployContract("TerraEvidenceRegistry",[3,0,admin.address]);await stalledRegistry.waitForDeployment();
for(const s of operators)await(await stalledRegistry.grantRole(role,s.address)).wait();
await(await stalledRegistry.revokeRole(role,admin.address)).wait();
for(const s of operators.slice(0,2))await(await stalledRegistry.connect(s).attestEvidence(...args)).wait();
const stalled=await stalledRegistry.evidence(honest.evidenceHash);assert.equal(stalled.attestationCount,2n);assert.equal(stalled.accepted,false);
// Capturing the enrollment administrator is a different threat from capturing an ordinary node.
const capturedAdminRegistry=await ethers.deployContract("TerraEvidenceRegistry",[3,0,admin.address]);await capturedAdminRegistry.waitForDeployment();
for(const s of operators)await(await capturedAdminRegistry.grantRole(role,s.address)).wait();
await(await capturedAdminRegistry.revokeRole(role,admin.address)).wait();
const sybils=[sybil0,sybil1,sybil2];
for(const s of sybils){await(await capturedAdminRegistry.grantRole(role,s.address)).wait();await(await capturedAdminRegistry.connect(s).attestEvidence(...falseArgs)).wait();}
const enrollmentCapture=await capturedAdminRegistry.isAcceptedForRegion(falseEvidence.evidenceHash,region);assert.equal(enrollmentCapture,true);
// A single authorized attacker arrives first and substitutes the complete envelope.
// Its candidate must remain separate while three honest verifier results reach quorum.
const poisonedRegistry=await ethers.deployContract("TerraEvidenceRegistry",[3,0,admin.address]);await poisonedRegistry.waitForDeployment();
for(const s of operators)await(await poisonedRegistry.grantRole(role,s.address)).wait();
await(await poisonedRegistry.revokeRole(role,admin.address)).wait();
const poisonedArgs=[honest.evidenceHash,ethers.id("attacker-selected-region"),ethers.id("first-attestor-false-metadata"),observedAt+1,1,"urn:attacker:favorable-narrative"] as const;
const maliciousCandidateId=await poisonedRegistry.evidenceCandidateId(...poisonedArgs);
const honestCandidateId=await poisonedRegistry.evidenceCandidateId(...args);
const maliciousReceipt=await(await poisonedRegistry.connect(operator3).attestEvidence(...poisonedArgs)).wait();
assert.equal(await poisonedRegistry.isAcceptedForRegion(honest.evidenceHash,region),false);
const recoveryTransactions:{hash:string;blockNumber:number;blockHash:string;operator:string}[]=[];
for(let i=0;i<3;i++){
  const receipt=await(await poisonedRegistry.connect(operators[i]!).attestEvidence(...args)).wait();
  recoveryTransactions.push({hash:receipt!.hash,blockNumber:receipt!.blockNumber,blockHash:receipt!.blockHash,operator:operators[i]!.address});
  assert.equal(await poisonedRegistry.isAcceptedForRegion(honest.evidenceHash,region),i===2);
}
const recovered=await poisonedRegistry.evidence(honest.evidenceHash);
const maliciousCandidate=await poisonedRegistry.candidate(honest.evidenceHash,maliciousCandidateId);
assert.equal(maliciousCandidate.attestationCount,1n);assert.equal(maliciousCandidate.accepted,false);
assert.equal(recovered.accepted,true);assert.equal(recovered.attestationCount,3n);
assert.deepEqual([recovered.regionId,recovered.metadataHash,Number(recovered.observedAt),Number(recovered.kind),recovered.uri],[region,metadataHash,observedAt,0,uri]);
assert.equal(await poisonedRegistry.acceptedCandidateId(honest.evidenceHash),honestCandidateId);
assert.equal(await poisonedRegistry.isAcceptedForRegion(honest.evidenceHash,poisonedArgs[1]),false);
await mustRevert(()=>poisonedRegistry.connect(operator3).attestEvidence(...args),"DuplicateAttestation");
for(const s of operators.slice(0,3))await(await registry.revokeRole(role,s.address)).wait();
const acceptedAfterRevocation=await registry.isAcceptedForRegion(falseEvidence.evidenceHash,region);assert.equal(acceptedAfterRevocation,true);
await mustRevert(()=>registry.connect(operator0).attestEvidence(ethers.id("new-evidence-after-revocation"),region,metadataHash,observedAt,0,uri),"AccessControlUnauthorizedAccount");
const finalBlock=await ethers.provider.getBlock("latest"),chainId=(await ethers.provider.getNetwork()).chainId.toString();
const report={
  version:"autonomous-source-local-chain-test-v2",executedAt:new Date().toISOString(),source:{stationId:honest.reproduction.selected.stationId,stationName:honest.reproduction.station.name,seriesId:honest.reproduction.selected.seriesId,records:honest.reproduction.observations.length,publisher:"USGS",newStationWithinExistingPublisher:true},
  evidenceHash:honest.evidenceHash,metadataHash,metadata,regionId:protocol.territory.regionId,
  chain:{mode:"local ephemeral Hardhat EVM; state ends with this command",chainId,registry:await registry.getAddress(),quorum:3,registeredTestOperators:operators.map(s=>s.address),accepted:honestState.accepted,attestationCount:Number(honestState.attestationCount),acceptedCandidateId,observedAt,uri,attestations:acceptedTransactions,finalBlock:{number:finalBlock!.number,hash:finalBlock!.hash}},
  verificationProcesses:{mode:"three separate local Node processes plus adversarial replay; one host/operator controls all",honestReplicas,alteredReplica,coherentAgainstOriginal,falseInitialSnapshot},
  scenarios:{
    threeOnlineOneNotStarted:{accepted:true,offlineIdentity:operator3.address,actualNetworkedABCICluster:false},
    oneAlteredArchive:{detected:true,error:alteredReplica.error},
    rawAndManifestRewritten:{detectedAgainstOriginalCommitment:true,error:coherentAgainstOriginal.error},
    unauthorizedIdentity:{rejected:true},duplicateIdentity:{rejected:true},
    metadataSubstitutionAfterFinalization:{rejected:true},
    twoCompromisedAttestors:{accepted:twoCompromised},
    twoUnavailable:{required:3,available:twoOnline.length,registry:await stalledRegistry.getAddress(),onChainAccepted:stalled.accepted,onChainAttestationCount:Number(stalled.attestationCount),progressPossible:false},
    threeCompromisedAttestors:{accepted:threeCompromised,transaction:collusionReceipt!.hash,outcome:"demonstrated failure of truthful evidence under authorized majority capture"},
    coherentlyFalseInitialPublisher:{reproducibilityAccepted:true,physicalTruthVerified:false,firstRealValue:originalValue,simulatedFalseValue:9.9,outcome:"demonstrated upstream trust gap; not an accusation against USGS"},
    capturedEnrollmentAdministrator:{registry:await capturedAdminRegistry.getAddress(),addedIdentities:sybils.map(s=>s.address),falseEvidenceAccepted:enrollmentCapture,outcome:"role-enrollment administrator can manufacture an authorized quorum; independently governed admission remains necessary"},
    firstAttestorMetadataPoisoning:{
      registry:await poisonedRegistry.getAddress(),maliciousIdentity:operator3.address,
      maliciousCandidateId,honestCandidateId,maliciousAttestationCount:Number(maliciousCandidate.attestationCount),
      maliciousCandidateAccepted:maliciousCandidate.accepted,maliciousRegionAccepted:false,
      maliciousTransaction:{hash:maliciousReceipt!.hash,blockNumber:maliciousReceipt!.blockNumber,blockHash:maliciousReceipt!.blockHash},
      honestTransactions:recoveryTransactions,attestationCount:Number(recovered.attestationCount),accepted:recovered.accepted,
      honestCorrectMetadataRejected:false,allFinalizedFieldsMatchHonestEnvelope:true,
      maliciousSecondVoteRejected:true,
      outcome:"first-attestor censorship no longer reproduces: one false candidate remains at one vote; three honest votes finalize their complete envelope"
    },
    revocationAfterFalseAcceptance:{acceptedRemains:acceptedAfterRevocation,newAttestationRejected:true,outcome:"role revocation prevents future attestations but does not erase prior accepted evidence; correction/challenge lifecycle remains future work"}
  },
  residualRisks:["Initial publisher falsification or selective omission cannot be ruled out by hashes/quorum","All local identities and storage remain under one host administrator","Registry administrator can change ORACLE_ROLE membership; production needs governed enrollment and key isolation","Evidence acceptance is not environmental truth, forecast validation, policy/action authorization or funding approval","One preconfigured catalog is not global source discovery or multiple independent publishers","Archive and chain are local; no independent mirror or public-chain publication was established"],
  ecologicalImprovementVerified:false,operationalEligible:false,fundingRelease:false,fundsTransferred:"none",LLMUsed:false,
  totalAcquisitionBytes:archive.responses.reduce((sum,r)=>sum+r.bytes,0),acquisitionRequests:archive.responses.length
};
await mkdir(output,{recursive:true});await writeFile(resolve(output,"chain-run.json"),JSON.stringify(report,null,2)+"\n");
console.log(JSON.stringify({source:report.source,evidenceHash:report.evidenceHash,metadataHash:report.metadataHash,chain:{chainId:report.chain.chainId,registry:report.chain.registry,accepted:report.chain.accepted,attestationCount:report.chain.attestationCount},scenarios:report.scenarios,fundingRelease:false,totalAcquisitionBytes:report.totalAcquisitionBytes,acquisitionRequests:report.acquisitionRequests},null,2));
