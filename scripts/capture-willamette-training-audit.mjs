// Optional source capture for training readiness. No model fitting or predictions.
import { readFile, writeFile, mkdir, access } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";
import { gzipSync } from "node:zlib";

const root = fileURLToPath(new URL("../", import.meta.url));
const folder = resolve(root, "docs/datasets/usgs-willamette-training-audit");
const rawProtocol = await readFile(resolve(folder, "protocol.json"));
const protocol = JSON.parse(rawProtocol);
const hash = (body) => "0x" + createHash("sha256").update(body).digest("hex");
if (protocol.version !== "willamette-training-readiness-v1" || protocol.stationId !== "USGS-14211720") throw new Error("Unexpected protocol");
if (Object.keys(protocol.sources).sort().join(",") !== "discharge,oxygen,temperature") throw new Error("Unexpected sources");
for (const window of protocol.windows) {
  if (!/^[a-z]+-[0-9]{4}$/.test(window.id) || !Number.isFinite(Date.parse(window.start)) || !Number.isFinite(Date.parse(window.end)) || Date.parse(window.start) >= Date.parse(window.end)) throw new Error("Invalid window");
  try { await access(resolve(folder, window.id)); throw new Error(`Capture already exists: ${window.id}`); }
  catch (error) { if (error.code !== "ENOENT") throw error; }
}
// Fetch one window at a time, at most three concurrent public requests.
for (const window of protocol.windows) {
  let responses;
  try {
    const settled = await Promise.allSettled(Object.entries(protocol.sources).map(async ([kind, spec]) => {
      const url = new URL("https://api.waterdata.usgs.gov/ogcapi/v1/collections/continuous/items");
      for (const [key, value] of Object.entries({ f: "json", monitoring_location_id: protocol.stationId, parameter_code: spec.parameterCode, time: `${window.start}/${window.end}`, limit: "10000" })) url.searchParams.set(key, value);
      const response = await fetch(url, { redirect: "error", signal: AbortSignal.timeout(30000) });
      if (!response.ok) throw new Error(`USGS HTTP ${response.status}`);
      const body = Buffer.from(await response.arrayBuffer());
      if (body.length > 10_000_000) throw new Error("Response exceeds size limit");
      const obj = JSON.parse(body);
      if (obj.type !== "FeatureCollection" || !Array.isArray(obj.features) || obj.features.length >= 10000 || obj.links.some((l) => l.rel === "next") || (obj.numberReturned !== undefined && obj.numberReturned !== obj.features.length)) throw new Error("Incomplete collection");
      return { body, kind, source: { file: `${kind}.json.gz`, sourceUrl: url.href, rawSha256: hash(body), capturedAt: new Date().toISOString(), records: obj.features.length } };
    }));
    const failed = settled.find((result) => result.status === "rejected");
    if (failed) throw failed.reason;
    responses = settled.map((result) => result.value);
  } catch (error) {
    // Keep an explicit failure for this declared window; no silent replacement.
    const path = resolve(folder, window.id);
    await mkdir(path, { recursive: false });
    await writeFile(resolve(path, "manifest.json"), JSON.stringify({ version: "training-capture-v1", protocolHash: hash(rawProtocol), window, status: "unavailable", error: String(error.message) }, null, 2) + "\n", { flag: "wx" });
    console.log(JSON.stringify({ window: window.id, status: "unavailable", error: String(error.message) }));
    continue;
  }
  const path = resolve(folder, window.id);
  await mkdir(path, { recursive: false });
  for (const { body, source } of responses) await writeFile(resolve(path, source.file), gzipSync(body, { level: 9 }), { flag: "wx" });
  await writeFile(resolve(path, "manifest.json"), JSON.stringify({ version: "training-capture-v1", protocolHash: hash(rawProtocol), window, status: "captured", license: "US Government work; public domain", sources: Object.fromEntries(responses.map(({ kind, source }) => [kind, source])) }, null, 2) + "\n", { flag: "wx" });
  console.log(JSON.stringify({ window: window.id, status: "captured", counts: Object.fromEntries(responses.map(({ kind, source }) => [kind, source.records])) }));
}
