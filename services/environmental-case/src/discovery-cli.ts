import { access, mkdir, readFile, writeFile } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import { canonicalJson, sha256Hex } from "@terravoce/protocol";
import { discoverAndCollect, discoveryProtocolSchema, evidenceCommitment, fetchPublicResponse, verifyDiscovery, type DiscoveryArchive } from "./discovery.js";

const root=resolve("../.."), folder=resolve(root,"docs/datasets/autonomous-source"), output=resolve(root,"docs/evidence/autonomous-source");
const command=process.argv[2]??"verify";
if(command==="capture"){
  const protocolPath="docs/datasets/autonomous-source/protocol.json";
  const protocolRaw=await readFile(resolve(root,protocolPath),"utf8"), p=discoveryProtocolSchema.parse(JSON.parse(protocolRaw));
  if(!execFileSync("git",["show",`HEAD:${protocolPath}`],{cwd:root}).equals(Buffer.from(protocolRaw))) throw new Error("Commit the exact protocol before discovery");
  try{await access(resolve(folder,"manifest.json"));throw new Error("Capture already exists; use offline verify");}catch(e){if((e as NodeJS.ErrnoException).code!=="ENOENT")throw e;}
  const archive:DiscoveryArchive={version:"autonomous-source-archive-v1",protocolHash:sha256Hex(protocolRaw),responses:[]};
  const reproduction=await discoverAndCollect(p,async(url)=>{
    const raw=await fetchPublicResponse(url,p), file=`response-${String(archive.responses.length).padStart(2,"0")}.json`;
    await writeFile(resolve(folder,file),raw,{flag:"wx"});
    archive.responses.push({file,url,rawSha256:sha256Hex(raw),capturedAt:new Date().toISOString(),bytes:Buffer.byteLength(raw)});
    console.log(JSON.stringify({step:"acquired-public-response",file,bytes:Buffer.byteLength(raw),rawSha256:sha256Hex(raw)}));
    return raw;
  });
  const evidence=evidenceCommitment(protocolRaw,archive,reproduction);
  await writeFile(resolve(folder,"manifest.json"),JSON.stringify(archive,null,2)+"\n",{flag:"wx"});
  await mkdir(output,{recursive:true});
  const seal={version:"autonomous-source-seal-v1",protocolCommit:execFileSync("git",["rev-parse","HEAD"],{cwd:root,encoding:"utf8"}).trim(),evidenceHash:evidence.evidenceHash,scope:"Research-only discovery of a new station within one preconfigured publisher; no sensor signature or independent physical validation"};
  await writeFile(resolve(output,"seal.json"),JSON.stringify(seal,null,2)+"\n",{flag:"wx"});
  await writeFile(resolve(output,"reproduction.json"),JSON.stringify(evidence,null,2)+"\n",{flag:"wx"});
  console.log(JSON.stringify({step:"discovery-complete",selected:reproduction.selected,station:reproduction.station,quality:reproduction.quality,discovery:reproduction.discovery,evidenceHash:evidence.evidenceHash,requestCount:archive.responses.length},null,2));
}else if(command==="verify"){
  // Git is the external checkpoint for offline replay. Chain consumers receive this hash separately.
  const sealPath="docs/evidence/autonomous-source/seal.json";
  const committed=execFileSync("git",["show",`HEAD:${sealPath}`],{cwd:root,encoding:"utf8"});
  const disk=await readFile(resolve(root,sealPath),"utf8");
  if(canonicalJson(JSON.parse(committed))!==canonicalJson(JSON.parse(disk)))throw new Error("Local seal differs from committed external checkpoint");
  const seal=JSON.parse(committed), evidence=await verifyDiscovery(folder,seal.evidenceHash);
  const saved=JSON.parse(await readFile(resolve(output,"reproduction.json"),"utf8"));
  if(canonicalJson(saved)!==canonicalJson(evidence))throw new Error("Saved reproduction mismatch");
  const chainPath="docs/evidence/autonomous-source/chain-run.json";
  const committedChain=execFileSync("git",["show",`HEAD:${chainPath}`],{cwd:root,encoding:"utf8"});
  const chain=JSON.parse(await readFile(resolve(root,chainPath),"utf8"));
  if(canonicalJson(chain)!==canonicalJson(JSON.parse(committedChain)))throw new Error("Local chain report differs from committed checkpoint");
  if(chain.version!=="autonomous-source-local-chain-test-v1" || chain.evidenceHash!==evidence.evidenceHash ||
    canonicalJson(chain.metadata.evidence)!==canonicalJson(evidence) || sha256Hex(canonicalJson(chain.metadata))!==chain.metadataHash ||
    chain.chain.chainId!=="31337" || chain.chain.quorum!==3 || chain.chain.accepted!==true || chain.chain.attestationCount!==3 ||
    chain.chain.attestations.length!==3 || new Set(chain.chain.attestations.map((a:{operator:string})=>a.operator)).size!==3 ||
    chain.operationalEligible!==false || chain.fundingRelease!==false || chain.ecologicalImprovementVerified!==false)throw new Error("Pinned local chain report commitment mismatch");
  const expectedFiles=[
    "services/environmental-case/src/discovery.ts",
    "services/environmental-case/src/discovery-replica.ts",
    "packages/contracts/contracts/TerraEvidenceRegistry.sol",
    "services/environmental-case/dist/discovery.js",
    "services/environmental-case/dist/discovery-replica.js",
    "packages/protocol/dist/index.js",
    "packages/protocol/dist/crypto.js",
    "packages/protocol/dist/schemas.js",
    "pnpm-lock.yaml",
    "tsconfig.base.json",
    "services/environmental-case/tsconfig.json",
    "packages/protocol/tsconfig.json"
  ];
  if(canonicalJson(chain.metadata.verificationArtifacts.map((a:{file:string})=>a.file))!==canonicalJson(expectedFiles))throw new Error("Unexpected verification artifact set");
  for(const a of chain.metadata.verificationArtifacts)if(sha256Hex(await readFile(resolve(root,a.file)))!==a.rawSha256)throw new Error("Verification artifact differs from pinned chain metadata");
  console.log(JSON.stringify({verified:true,evidenceHash:evidence.evidenceHash,selected:evidence.reproduction.selected,observations:evidence.reproduction.observations.length,chainReportInternallyConsistent:true,publicChainReceiptVerified:false,physicalTruthVerified:false,operationalEligible:false}));
}else throw new Error("Use capture or verify");
