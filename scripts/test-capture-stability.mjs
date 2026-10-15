import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve, dirname } from "node:path";
import { gunzipSync } from "node:zlib";
import { execFileSync } from "node:child_process";
import { captureSource, hash, snapshotHash, sourceUrl, writeWindow, reserveAttempt, IMPLEMENTATION_FILES, ROOT } from "./capture-willamette-stability.mjs";

const window = { id: "synthetic", start: "2025-02-01T00:00:00Z", end: "2025-03-01T00:00:00Z" };
const url = sourceUrl(window, "USGS-14211720", "00300");
const valid = JSON.stringify({ type: "FeatureCollection", features: [], links: [], numberReturned: 0 });

test("fixed official URL and sorted unique implementation inventory", () => {
  const parsed = new URL(url);
  assert.equal(parsed.origin, "https://api.waterdata.usgs.gov");
  assert.equal(parsed.searchParams.get("time"), `${window.start}/${window.end}`);
  assert.equal(parsed.searchParams.get("monitoring_location_id"), "USGS-14211720");
  assert.equal(parsed.searchParams.get("limit"), "10000");
  assert.deepEqual(IMPLEMENTATION_FILES, [...new Set(IMPLEMENTATION_FILES)].sort());
  const inventory = [{ file: "synthetic", rawSha256: hash(Buffer.from("fixture")) }];
  assert.equal(snapshotHash(inventory), hash(Buffer.from(JSON.stringify(inventory))));
});

test("capture and offline evaluator freeze exactly the same inventory and encoding", () => {
  const code = "import sys,json;sys.path.insert(0,'scripts');import evaluate_stability as e;print(json.dumps({'files':e.IMPLEMENTATION_FILES,'hash':e.implementation_hash([{'file':f,'rawSha256':'0xsynthetic'} for f in e.IMPLEMENTATION_FILES])}))";
  const p = JSON.parse(execFileSync(process.platform === "win32" ? "python" : "python3", ["-c", code], { cwd: ROOT, encoding: "utf8" }));
  assert.deepEqual(p.files, IMPLEMENTATION_FILES);
  assert.equal(p.hash, snapshotHash(IMPLEMENTATION_FILES.map((file) => ({ file, rawSha256: "0xsynthetic" }))));
});

test("preserves exact complete response bytes and does not retry", async () => {
  let calls = 0;
  const captured = await captureSource("oxygen", url, async (actual, options) => {
    calls++;
    assert.equal(actual, url);
    assert.equal(options.redirect, "error");
    return new Response(valid, { headers: { "content-type": "application/json" } });
  });
  assert.equal(calls, 1);
  assert.equal(captured.status, "captured");
  assert.equal(captured.source.rawSha256, hash(Buffer.from(valid)));
  assert.equal(captured.body.toString(), valid);
});

test("HTTP failures, pagination and count mismatch remain unavailable with archived bodies", async () => {
  const cases = [new Response("rate limited", { status: 429 }),
    new Response(JSON.stringify({ type: "FeatureCollection", features: [], links: [{ rel: "next" }] })),
    new Response(JSON.stringify({ type: "FeatureCollection", features: [], links: [], numberReturned: 1 }))];
  for (const response of cases) {
    const r = await captureSource("oxygen", url, async () => response);
    assert.equal(r.status, "unavailable");
    assert.ok(r.body.length);
    assert.equal(r.source.rawSha256, hash(r.body));
  }
});

test("network failures keep explicit absence and failed windows retain companion responses", async () => {
  const missing = await captureSource("oxygen", url, async () => { throw new Error("synthetic offline"); });
  assert.equal(missing.body, undefined);
  assert.equal(missing.status, "unavailable");
  const companion = await captureSource("temperature", url, async () => new Response(valid));
  const directory = await mkdtemp(join(tmpdir(), "virdacora-capture-test-"));
  assert.equal(dirname(resolve(directory)), resolve(tmpdir()));
  assert.ok(resolve(directory).startsWith(join(resolve(tmpdir()), "virdacora-capture-test-")));
  try {
    const destination = join(directory, "capture");
    const manifest = await writeWindow(destination, window, { frozenAtCommit: "synthetic" }, [missing, companion]);
    assert.equal(manifest.status, "unavailable");
    assert.match(manifest.error, /oxygen/);
    assert.equal(gunzipSync(await readFile(join(destination, "temperature.json.gz"))).toString(), valid);
    await assert.rejects(writeWindow(destination, window, {}, [companion]), /exist/i);
    const marker = join(directory, "attempt.json");
    const reservations = await Promise.allSettled([reserveAttempt(marker, { testWindows: [window] }, {}),
      reserveAttempt(marker, { testWindows: [window] }, {})]);
    assert.equal(reservations.filter((r) => r.status === "fulfilled").length, 1);
    assert.equal(reservations.filter((r) => r.status === "rejected").length, 1);
    await assert.rejects(reserveAttempt(marker, { testWindows: [window] }, {}), /exist/i);
  } finally {
    // Exactly the temporary directory returned by mkdtemp, no computed parent.
    await rm(directory, { recursive: true });
  }
});
