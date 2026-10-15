// Capture the four predeclared retrospective windows once, after code is committed.
import { readFile, writeFile, mkdir, access } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";
import { createHash } from "node:crypto";
import { gzipSync } from "node:zlib";
import { execFileSync } from "node:child_process";

export const ROOT = fileURLToPath(new URL("../", import.meta.url));
export const PROTOCOL = "docs/datasets/usgs-willamette-stability/protocol.json";
export const IMPLEMENTATION_FILES = [...new Set([
  "scripts/capture-willamette-stability.mjs", "scripts/test-capture-stability.mjs",
  "scripts/evaluate_stability.py", "scripts/test_evaluate_stability.py",
  "scripts/stability_protocol.py", "scripts/test_stability_protocol.py",
  "scripts/experiment_multiseason.py", "scripts/audit_willamette.py", PROTOCOL,
  "docs/datasets/usgs-willamette-multiseason/protocol.json",
  "docs/evidence/willamette-multiseason/frozen-model.json",
  "docs/datasets/usgs-willamette-training-audit/protocol.json",
  "docs/datasets/usgs-willamette-validation/protocol.json",
  "docs/datasets/usgs-willamette-multivariate/manifest.json",
])].sort();
export const hash = (body) => "0x" + createHash("sha256").update(body).digest("hex");
export const snapshotHash = (files) => hash(Buffer.from(JSON.stringify(files), "utf8"));

export function sourceUrl(window, stationId, parameterCode) {
  const url = new URL("https://api.waterdata.usgs.gov/ogcapi/v1/collections/continuous/items");
  for (const [key, value] of Object.entries({ f: "json", monitoring_location_id: stationId,
    parameter_code: parameterCode, time: `${window.start}/${window.end}`, limit: "10000" })) {
    url.searchParams.set(key, value);
  }
  return url.href;
}

export async function inspectFreeze(root = ROOT, python = "python") {
  // Reuse the strict calendar, model and no-existing-capture guard; no network.
  const preflight = JSON.parse(execFileSync(python, ["scripts/stability_protocol.py"], { cwd: root, encoding: "utf8" }));
  const rawProtocol = await readFile(resolve(root, PROTOCOL));
  const spec = JSON.parse(rawProtocol);
  const frozenAtCommit = execFileSync("git", ["rev-parse", "HEAD"], { cwd: root, encoding: "utf8" }).trim();
  const implementationFiles = [];
  for (const file of IMPLEMENTATION_FILES) {
    const raw = await readFile(resolve(root, file));
    const committed = execFileSync("git", ["show", `${frozenAtCommit}:${file}`], { cwd: root, maxBuffer: 4_000_000 });
    if (!committed.equals(raw)) throw new Error(`Commit implementation before capture: ${file}`);
    implementationFiles.push({ file, rawSha256: hash(raw) });
  }
  if (preflight.protocolHash !== hash(rawProtocol)) throw new Error("Protocol changed during preflight");
  const base = JSON.parse(await readFile(resolve(root, spec.baseModel.protocolFile)));
  return { spec, base, commitment: { protocolHash: hash(rawProtocol), frozenModelHash: spec.baseModel.rawSha256,
    frozenAtCommit, implementationFiles, implementationSnapshotHash: snapshotHash(implementationFiles) } };
}

export async function captureSource(kind, url, fetcher = fetch) {
  const source = { file: `${kind}.json.gz`, sourceUrl: url, requestedAtUTC: new Date().toISOString() };
  let body;
  try {
    const response = await fetcher(url, { redirect: "error", signal: AbortSignal.timeout(45000) });
    source.httpStatus = response.status;
    const chunks = [];
    let size = 0;
    for await (const chunk of response.body ?? []) {
      size += chunk.length;
      if (size > 10_000_000) throw new Error("Response exceeds 10 MB; not a complete source");
      chunks.push(Buffer.from(chunk));
    }
    body = Buffer.concat(chunks);
    source.rawSha256 = hash(body);
    source.capturedAt = new Date().toISOString();
    source.responseContentType = response.headers.get("content-type");
    if (!response.ok) throw new Error(`USGS HTTP ${response.status}`);
    const obj = JSON.parse(body);
    if (obj.type !== "FeatureCollection" || !Array.isArray(obj.features) || obj.features.length >= 10000 ||
      !Array.isArray(obj.links) || obj.links.some((link) => link.rel === "next") ||
      (obj.numberReturned !== undefined && obj.numberReturned !== obj.features.length)) {
      throw new Error("Incomplete or unsupported collection");
    }
    source.records = obj.features.length;
    return { kind, source, body, status: "captured" };
  } catch (error) {
    // Preserve complete bodies even on HTTP or schema failures, and keep successful
    // companion sources. A failed fixed window is not replaced or silently retried.
    return { kind, source, body, status: "unavailable", error: String(error.message) };
  }
}

export async function writeWindow(path, window, commitment, responses) {
  await mkdir(path, { recursive: false });
  const failures = responses.filter((r) => r.status !== "captured");
  for (const { source, body } of responses) {
    if (body !== undefined) await writeFile(resolve(path, source.file), gzipSync(body, { level: 9 }), { flag: "wx" });
  }
  const manifest = { version: "stability-test-capture-v1", ...commitment, window,
    status: failures.length ? "unavailable" : "captured", license: "US Government work; public domain",
    sources: Object.fromEntries(responses.map(({ kind, source, status, error }) =>
      [kind, { ...source, captureStatus: status, ...(error ? { error } : {}) }])),
    ...(failures.length ? { error: failures.map((r) => `${r.kind}: ${r.error}`).join("; ") } : {}) };
  await writeFile(resolve(path, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n", { flag: "wx" });
  return manifest;
}

export async function reserveAttempt(path, spec, commitment) {
  const attempt = { version: "stability-capture-attempt-v1", ...commitment,
    startedAtUTC: new Date().toISOString(), windows: spec.testWindows,
    rule: "One exclusive attempt; retained after interruption; never silently reset or retried" };
  // An exclusive persistent marker is created before HTTP, so concurrent starts
  // or a restart after a crash cannot silently acquire the same fixed targets.
  await writeFile(path, JSON.stringify(attempt, null, 2) + "\n", { flag: "wx" });
  return attempt;
}

export async function main(args = process.argv.slice(2)) {
  if (args.length > 1 || (args.length === 1 && args[0] !== "--python3")) {
    throw new Error("Usage: node scripts/capture-willamette-stability.mjs [--python3]");
  }
  const { spec, base, commitment } = await inspectFreeze(ROOT, args[0] === "--python3" ? "python3" : "python");
  // Check all windows before any HTTP request or filesystem mutation.
  for (const window of spec.testWindows) {
    try { await access(resolve(ROOT, PROTOCOL, "..", window.id)); throw new Error(`Capture already exists: ${window.id}`); }
    catch (error) { if (error.code !== "ENOENT") throw error; }
  }
  await reserveAttempt(resolve(ROOT, PROTOCOL, "..", "capture-attempt.json"), spec, commitment);
  for (const window of spec.testWindows) {
    const responses = await Promise.all(Object.entries(base.sources).map(([kind, source]) =>
      captureSource(kind, sourceUrl(window, spec.stationId, source.parameterCode))));
    const manifest = await writeWindow(resolve(ROOT, PROTOCOL, "..", window.id), window, commitment, responses);
    console.log(JSON.stringify({ window: window.id, status: manifest.status,
      counts: Object.fromEntries(responses.map(({ kind, source }) => [kind, source.records ?? null])),
      ...(manifest.error ? { error: manifest.error } : {}) }));
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  await main();
}
