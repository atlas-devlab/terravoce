// Optional network capture. Normal tests/audits consume only the immutable snapshots.
import { readFile, writeFile, mkdir, access } from "node:fs/promises";
import { constants } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";
import { gzipSync } from "node:zlib";

const root = fileURLToPath(new URL("../", import.meta.url));
const folder = resolve(root, "docs/datasets/usgs-willamette-validation");
const protocolRaw = await readFile(resolve(folder, "protocol.json"));
const protocol = JSON.parse(protocolRaw.toString("utf8"));
const hash = (bytes) => "0x" + createHash("sha256").update(bytes).digest("hex");
if (protocol.version !== "frozen-willamette-validation-v1" || protocol.stationId !== "USGS-14211720") {
  throw new Error("Unexpected validation protocol");
}
// Refuse to refresh existing windows: that would mix different data vintages.
for (const window of protocol.windows) {
  if (!/^[a-z]+-[0-9]{4}$/.test(window.id)) throw new Error("Unsafe window identifier");
  try { await access(resolve(folder, window.id), constants.F_OK); throw new Error(`Capture already exists: ${window.id}`); }
  catch (error) { if (error.code !== "ENOENT") throw error; }
}
const captures = await Promise.all(protocol.windows.map(async (window) => {
  const responses = await Promise.all(Object.entries(protocol.sources).map(async ([kind, spec]) => {
    const url = new URL("https://api.waterdata.usgs.gov/ogcapi/v1/collections/continuous/items");
    for (const [key, value] of Object.entries({ f: "json", monitoring_location_id: protocol.stationId,
      parameter_code: spec.parameterCode, time: `${window.start}/${window.end}`, limit: "10000" })) url.searchParams.set(key, value);
    const response = await fetch(url, { redirect: "error", signal: AbortSignal.timeout(30000) });
    if (!response.ok) throw new Error(`USGS ${response.status}: ${window.id}/${kind}`);
    const body = Buffer.from(await response.arrayBuffer());
    if (body.length > 10_000_000) throw new Error("Capture exceeds size limit");
    const json = JSON.parse(body.toString("utf8"));
    if (json.type !== "FeatureCollection" || json.features.length >= 10000 || json.links.some((l) => l.rel === "next")) {
      throw new Error("Incomplete capture");
    }
    return { kind, body, source: { file: `${kind}.json.gz`, sourceUrl: url.href,
      rawSha256: hash(body), capturedAt: new Date().toISOString(), records: json.features.length } };
  }));
  return { window, responses };
}));
// All requested responses must succeed before any window is persisted.
for (const { window, responses } of captures) {
  const destination = resolve(folder, window.id);
  await mkdir(destination, { recursive: true });
  for (const { body, source } of responses) await writeFile(resolve(destination, source.file), gzipSync(body, { level: 9 }), { flag: "wx" });
  const manifest = { version: "validation-capture-v1", protocolHash: hash(protocolRaw), window,
    license: "US Government work; public domain", sources: Object.fromEntries(responses.map(({ kind, source }) => [kind, source])) };
  await writeFile(resolve(destination, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n", { flag: "wx" });
  console.log(JSON.stringify({ window: window.id, protocolHash: manifest.protocolHash,
    sources: Object.fromEntries(responses.map(({ kind, source }) => [kind, { count: source.records, hash: source.rawSha256 }])) }));
}
