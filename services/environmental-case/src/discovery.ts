import { lstat, open } from "node:fs/promises";
import { resolve } from "node:path";
import { TextDecoder } from "node:util";
import { canonicalJson, sha256Hex } from "@terravoce/protocol";
import { z } from "zod";

const hashSchema = z.string().regex(/^0x[0-9a-f]{64}$/);
const dateSchema = z.iso.datetime({ offset: true });
export const discoveryProtocolSchema = z.object({
  version: z.literal("autonomous-source-protocol-v1"),
  catalogOrigin: z.literal("https://api.waterdata.usgs.gov"),
  catalogPath: z.literal("/ogcapi/v1/collections/time-series-metadata/items"),
  territory: z.object({ regionId: z.string().min(2), bbox: z.tuple([z.number(), z.number(), z.number(), z.number()]), hydrologicUnitPrefix: z.string().regex(/^\d{6}$/) }),
  metric: z.object({ parameterCode: z.literal("00300"), unit: z.literal("mg/L"), statisticId: z.literal("00011") }),
  window: z.object({ start: dateSchema, end: dateSchema }),
  alreadyConnectedStationIds: z.array(z.string().regex(/^USGS-\d+$/)),
  limits: z.object({ pageSize: z.number().int().min(1).max(100), maxCatalogPages: z.number().int().min(1).max(4), maxCandidates: z.number().int().min(1).max(8), maxObservationRecords: z.number().int().min(2).max(500), maxResponseBytes: z.number().int().min(100).max(2000000), timeoutMs: z.number().int().min(1).max(30000) }),
  publication: z.object({ mode: z.literal("local-ephemeral-EVM"), quorum: z.literal(3), registeredOperators: z.literal(4), realFunding: z.literal(false), operationalEligible: z.literal(false) })
}).passthrough();
export type DiscoveryProtocol = z.infer<typeof discoveryProtocolSchema>;
const featureSchema = z.object({ type: z.literal("Feature"), id: z.string(), geometry: z.object({ type: z.literal("Point"), coordinates: z.array(z.number()).min(2) }).nullable(), properties: z.record(z.string(), z.unknown()) });
const collectionSchema = z.object({ type: z.literal("FeatureCollection"), features: z.array(featureSchema), numberReturned: z.number().int().nonnegative().optional(), links: z.array(z.object({ rel: z.string(), href: z.url() })) });
type Feature = z.infer<typeof featureSchema>;
export interface ArchivedResponse { file: string; url: string; rawSha256: string; capturedAt: string; bytes: number }
export interface DiscoveryArchive { version: "autonomous-source-archive-v1"; protocolHash: string; responses: ArchivedResponse[] }
export interface DiscoveredMeasurement { id: string; time: string; value: number; unit: "mg/L"; approval: "Approved"; lastModified: string }
export interface Candidate { stationId: string; seriesId: string }
export type Getter = (url: string) => Promise<string>;

function assertProtocol(p: DiscoveryProtocol) {
  const [west, south, east, north] = p.territory.bbox;
  if (west < -180 || east > 180 || south < -90 || north > 90 || west >= east || south >= north || Date.parse(p.window.start) >= Date.parse(p.window.end) || Date.parse(p.window.end) - Date.parse(p.window.start) > 86400000) throw new Error("Invalid territory or bounded window");
}
function inside(feature: Feature, p: DiscoveryProtocol) {
  if (!feature.geometry) return false;
  const [lon, lat] = feature.geometry.coordinates;
  const [west, south, east, north] = p.territory.bbox;
  return lon! >= west && lon! <= east && lat! >= south && lat! <= north;
}
function collection(raw: string, limit: number) {
  const data = collectionSchema.parse(JSON.parse(raw));
  if (data.features.length > limit || (data.numberReturned !== undefined && data.numberReturned !== data.features.length)) throw new Error("Inconsistent bounded collection");
  return data;
}
export function catalogUrl(p: DiscoveryProtocol): string {
  const u = new URL(p.catalogPath, p.catalogOrigin);
  for (const [k, v] of Object.entries({ f: "json", bbox: p.territory.bbox.join(","), parameter_code: p.metric.parameterCode, statistic_id: p.metric.statisticId, limit: String(p.limits.pageSize) })) u.searchParams.set(k, v);
  return u.href;
}
export function assertCatalogUrl(url: string, p: DiscoveryProtocol) {
  const u = new URL(url), expected = new URL(catalogUrl(p));
  if (u.origin !== p.catalogOrigin || u.pathname !== p.catalogPath || u.username || u.password || u.hash) throw new Error("Untrusted catalog pagination destination");
  for (const [k, v] of expected.searchParams) if (u.searchParams.get(k) !== v || u.searchParams.getAll(k).length !== 1) throw new Error("Pagination changed frozen query");
  for (const k of u.searchParams.keys()) if (!expected.searchParams.has(k) && k !== "offset") throw new Error("Unexpected pagination query");
  if (u.searchParams.has("offset") && (!/^\d+$/.test(u.searchParams.get("offset")!) || u.searchParams.getAll("offset").length !== 1)) throw new Error("Invalid pagination offset");
}
function stationUrl(c: Candidate, p: DiscoveryProtocol) { return `${p.catalogOrigin}/ogcapi/v1/collections/monitoring-locations/items/${c.stationId}?f=json`; }
function observationsUrl(c: Candidate, p: DiscoveryProtocol) {
  const u = new URL("/ogcapi/v1/collections/continuous/items", p.catalogOrigin);
  for (const [k,v] of Object.entries({ f: "json", monitoring_location_id: c.stationId, time_series_id: c.seriesId, parameter_code: p.metric.parameterCode, statistic_id: p.metric.statisticId, time: `${p.window.start}/${p.window.end}`, limit: String(p.limits.maxObservationRecords) })) u.searchParams.set(k,v);
  return u.href;
}
function candidates(features: Feature[], p: DiscoveryProtocol): Candidate[] {
  const seen = new Set<string>();
  const result: Candidate[] = [];
  for (const f of features) {
    const a = f.properties;
    if (typeof a.monitoring_location_id !== "string" || !/^USGS-\d+$/.test(a.monitoring_location_id) || !/^[a-f0-9]{32}$/.test(f.id)) continue;
    if (a.parameter_code !== p.metric.parameterCode || a.statistic_id !== p.metric.statisticId || typeof a.unit_of_measure !== "string" || a.unit_of_measure.toLowerCase() !== "mg/l" || !inside(f,p) || p.alreadyConnectedStationIds.includes(a.monitoring_location_id)) continue;
    if (typeof a.begin !== "string" || typeof a.end !== "string" || !Number.isFinite(Date.parse(a.begin)) || !Number.isFinite(Date.parse(a.end)) || Date.parse(a.begin) > Date.parse(p.window.start) || Date.parse(a.end) < Date.parse(p.window.end)) continue;
    const key = `${a.monitoring_location_id}:${f.id}`;
    if (seen.has(key)) throw new Error("Duplicate catalog candidate");
    seen.add(key); result.push({ stationId: a.monitoring_location_id, seriesId: f.id });
  }
  return result.sort((a,b) => a.stationId < b.stationId ? -1 : a.stationId > b.stationId ? 1 : a.seriesId < b.seriesId ? -1 : a.seriesId > b.seriesId ? 1 : 0);
}
function stationMatches(raw: string, c: Candidate, p: DiscoveryProtocol): { name: string; hydrologicUnit: string; coordinates: number[] } | undefined {
  const f = featureSchema.parse(JSON.parse(raw)), a = f.properties;
  if (f.id !== c.stationId || a.id !== c.stationId || a.agency_code !== "USGS" || !inside(f,p) || typeof a.hydrologic_unit_code !== "string" || !a.hydrologic_unit_code.startsWith(p.territory.hydrologicUnitPrefix)) return undefined;
  return { name: String(a.monitoring_location_name ?? a.station_name ?? c.stationId), hydrologicUnit: a.hydrologic_unit_code, coordinates: f.geometry!.coordinates };
}
function measurements(raw: string, c: Candidate, p: DiscoveryProtocol) {
  const data = collection(raw, p.limits.maxObservationRecords);
  if (data.links.some(l => l.rel === "next")) throw new Error("Observation response is incomplete; narrow window or explicit pagination required");
  const accepted: DiscoveredMeasurement[] = [], excluded: {id: string; reason: string}[] = [], ids = new Set<string>(), times = new Set<string>();
  for (const f of data.features) {
    const a = f.properties;
    if (a.monitoring_location_id !== c.stationId || a.time_series_id !== c.seriesId || a.parameter_code !== p.metric.parameterCode || a.statistic_id !== p.metric.statisticId || typeof a.unit_of_measure !== "string" || a.unit_of_measure.toLowerCase() !== "mg/l") throw new Error("Observation identity or unit mismatch");
    if (typeof a.time !== "string" || !dateSchema.safeParse(a.time).success || Date.parse(a.time) < Date.parse(p.window.start) || Date.parse(a.time) > Date.parse(p.window.end)) throw new Error("Observation time outside frozen window");
    const time = new Date(a.time).toISOString();
    if (ids.has(f.id) || times.has(time)) throw new Error("Duplicate observation id or time");
    ids.add(f.id); times.add(time);
    const value = typeof a.value === "string" && a.value.trim() !== "" ? Number(a.value) : NaN;
    const reason = a.approval_status !== "Approved" ? "publisher-not-approved" : a.qualifier !== null && a.qualifier !== "" ? "publisher-qualified" : !Number.isFinite(value) || value < 0 ? "missing-or-invalid-value" : typeof a.last_modified !== "string" || !dateSchema.safeParse(a.last_modified).success ? "missing-modification-time" : undefined;
    if (reason) excluded.push({id:f.id,reason});
    else accepted.push({ id: f.id, time, value, unit: "mg/L", approval: "Approved", lastModified: new Date(a.last_modified as string).toISOString() });
  }
  accepted.sort((a,b)=>a.time.localeCompare(b.time));
  return { accepted, excluded, total: data.features.length };
}

/** No station identifiers are supplied to this algorithm except the already-connected exclusions. */
export async function discoverAndCollect(input: unknown, get: Getter) {
  const p = discoveryProtocolSchema.parse(input); assertProtocol(p);
  const catalog: Feature[] = [], pages: string[] = [], attempts: {candidate: Candidate; reason: string}[] = [];
  let next: string | undefined = catalogUrl(p);
  while (next) {
    if (pages.length >= p.limits.maxCatalogPages || pages.includes(next)) throw new Error("Catalog incomplete or pagination cycle within request budget");
    assertCatalogUrl(next,p); pages.push(next);
    const data = collection(await get(next),p.limits.pageSize); catalog.push(...data.features);
    const links = data.links.filter(l=>l.rel==="next");
    if (links.length > 1) throw new Error("Ambiguous pagination");
    next = links[0]?.href;
  }
  const eligible = candidates(catalog,p);
  for (const c of eligible.slice(0,p.limits.maxCandidates)) {
    const station = stationMatches(await get(stationUrl(c,p)),c,p);
    if (!station) { attempts.push({candidate:c,reason:"station-outside-territory-or-identity-mismatch"}); continue; }
    const data = measurements(await get(observationsUrl(c,p)),c,p);
    if (data.accepted.length < 2) { attempts.push({candidate:c,reason:"insufficient-approved-unqualified-observations"}); continue; }
    return { selected:c, station, observations:data.accepted, quality:{total:data.total,accepted:data.accepted.length,excluded:data.excluded}, discovery:{catalogPages:pages.length,catalogRecords:catalog.length,eligibleCandidates:eligible.length,attempts}, publisher:"USGS", sourceSignature:"none; HTTPS publisher retrieval only", independentPublishers:1, physicalTruthVerified:false, ecologicalImprovementVerified:false, operationalEligible:false, fundingRelease:false };
  }
  throw new Error("No eligible new source within bounded candidate budget");
}

export function evidenceCommitment<T>(protocolRaw: string, archive: DiscoveryArchive, reproduction: T) {
  if (archive.protocolHash !== sha256Hex(protocolRaw)) throw new Error("Frozen protocol hash mismatch");
  const core = { version:"autonomous-source-evidence-v1", protocolHash:archive.protocolHash, archiveHash:sha256Hex(canonicalJson(archive)), reproduction };
  return { ...core, evidenceHash:sha256Hex(`terravoce-autonomous-evidence-v1:${canonicalJson(core)}`) };
}

export async function verifyDiscovery(folder: string, expectedEvidenceHash: string) {
  hashSchema.parse(expectedEvidenceHash);
  const protocolRaw = (await readBoundedArchiveFile(resolve(folder,"protocol.json"),65536)).toString("utf8"), p = discoveryProtocolSchema.parse(JSON.parse(protocolRaw));
  const archive = z.object({ version:z.literal("autonomous-source-archive-v1"), protocolHash:hashSchema, responses:z.array(z.object({file:z.string().regex(/^[a-z][a-z0-9-]*\.json$/),url:z.url(),rawSha256:hashSchema,capturedAt:dateSchema,bytes:z.number().int().positive().max(p.limits.maxResponseBytes)}).strict()).max(p.limits.maxCatalogPages+p.limits.maxCandidates*2) }).strict().parse(JSON.parse((await readBoundedArchiveFile(resolve(folder,"manifest.json"),65536)).toString("utf8")));
  const files = new Set<string>(), urls = new Set<string>();
  for (const a of archive.responses) { if (files.has(a.file)||urls.has(a.url)) throw new Error("Duplicate archived request"); files.add(a.file);urls.add(a.url); }
  let cursor=0;
  const reproduction=await discoverAndCollect(p,async(url)=>{
    const a=archive.responses[cursor++];
    if (!a || a.url!==url) throw new Error("Archive does not reproduce exact discovery request order");
    const raw=await readBoundedArchiveFile(resolve(folder,a.file),p.limits.maxResponseBytes);
    if (raw.length!==a.bytes || sha256Hex(raw)!==a.rawSha256) throw new Error("Archived response hash mismatch");
    return raw.toString("utf8");
  });
  if (cursor!==archive.responses.length) throw new Error("Archive includes unused responses");
  const evidence=evidenceCommitment(protocolRaw,archive,reproduction);
  if (evidence.evidenceHash!==expectedEvidenceHash) throw new Error("External evidence commitment mismatch");
  return evidence;
}

/** Bounded HTTPS acquisition; discovered metadata never supplies executable code or arbitrary URLs. */
export async function fetchPublicResponse(url: string, p: DiscoveryProtocol): Promise<string> {
  const u=new URL(url);
  if(u.origin!==p.catalogOrigin || u.username || u.password || u.hash || !/^\/ogcapi\/v1\/collections\/(time-series-metadata\/items|continuous\/items|monitoring-locations\/items\/USGS-\d+)$/.test(u.pathname)) throw new Error("Untrusted acquisition destination");
  const signal=AbortSignal.timeout(p.limits.timeoutMs);
  const response=await fetch(u,{redirect:"error",signal,headers:{"User-Agent":"TerraVoce-research-discovery/1.0"}});
  if(!response.ok || !response.body) throw new Error(`Public source unavailable: HTTP ${response.status}`);
  if(!response.headers.get("content-type")?.toLowerCase().includes("json"))throw new Error("Publisher response is not JSON");
  const chunks:Uint8Array[]=[];let bytes=0;
  for await(const chunk of response.body){bytes+=chunk.length;if(bytes>p.limits.maxResponseBytes){await response.body.cancel().catch(()=>{});throw new Error("Response exceeds byte budget");}chunks.push(chunk);}
  const raw=Buffer.concat(chunks);
  new TextDecoder("utf-8",{fatal:true}).decode(raw); // Reject replacement decoding: preserve exact UTF-8 response bytes.
  return raw.toString("utf8");
}

/** Shared peer archives have the same byte boundary as live acquisition. */
export async function readBoundedArchiveFile(path: string, maxBytes: number): Promise<Buffer> {
  if(!Number.isSafeInteger(maxBytes)||maxBytes<1)throw new Error("Invalid archive byte budget");
  const entry=await lstat(path);
  if(!entry.isFile()||entry.isSymbolicLink())throw new Error("Archive entry is not a regular file");
  if(entry.size>maxBytes)throw new Error("Archive entry exceeds byte budget");
  const handle=await open(path,"r"),chunks:Buffer[]=[];
  try{
    const opened=await handle.stat();
    if(!opened.isFile()||opened.size>maxBytes)throw new Error("Opened archive entry exceeds byte budget");
    let total=0;
    for(;;){
      const chunk=Buffer.alloc(Math.min(65536,maxBytes+1-total));
      const {bytesRead}=await handle.read(chunk,0,chunk.length,null);
      if(bytesRead===0)break;
      total+=bytesRead;if(total>maxBytes)throw new Error("Growing archive entry exceeds byte budget");
      chunks.push(chunk.subarray(0,bytesRead));
    }
    return Buffer.concat(chunks);
  }finally{await handle.close();}
}
