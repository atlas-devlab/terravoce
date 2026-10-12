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
  console.log(JSON.stringify({verified:true,evidenceHash:evidence.evidenceHash,selected:evidence.reproduction.selected,observations:evidence.reproduction.observations.length,physicalTruthVerified:false,operationalEligible:false}));
}else throw new Error("Use capture or verify");
