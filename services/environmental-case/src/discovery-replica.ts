import { verifyDiscovery } from "./discovery.js";
const [folder, expectedHash]=process.argv.slice(2);
if(!folder||!expectedHash)throw new Error("Provide archive directory and independently pinned evidence hash");
try{
  const evidence=await verifyDiscovery(folder,expectedHash);
  console.log(JSON.stringify({verified:true,evidenceHash:evidence.evidenceHash,records:evidence.reproduction.observations.length,scope:"snapshot reproducibility; physical truth unverified"}));
}catch(error){console.log(JSON.stringify({verified:false,error:(error as Error).message}));process.exitCode=2;}
