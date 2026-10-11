import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { gunzipSync } from "node:zlib";
import { describe, expect, it } from "vitest";
import { sha256Hex } from "@terravoce/protocol";
import { loadMultivariateData, validateCovariate, type Covariate } from "./multivariate-data.js";
import { alignedPairs, runMultivariateExperiment, verifyMultivariateReport } from "./multivariate.js";
import { fitRidge, predictResidual } from "./ridge.js";

const folder = fileURLToPath(new URL("../../../docs/datasets/usgs-willamette-multivariate/", import.meta.url));
const oxygenFolder = fileURLToPath(new URL("../../../docs/datasets/usgs-willamette/", import.meta.url));
const data = await loadMultivariateData(folder, oxygenFolder);
const flowRaw = gunzipSync(await readFile(`${folder}/discharge.json.gz`)).toString("utf8");
function editFlow(change: (value: any) => void) {
  const value = JSON.parse(flowRaw); change(value);
  const raw = JSON.stringify(value), manifest = structuredClone(data.manifest);
  manifest.sources.discharge.rawSha256 = sha256Hex(raw);
  return () => validateCovariate(raw, manifest, "discharge");
}
describe("transparent multivariate experiment", () => {
  it("solves a known centered ridge system and keeps constant features finite", () => {
    const model = fitRidge([[-1, 8], [0, 8], [1, 8]], [-2, 0, 2], 3);
    // X'X=3 after standardization and alpha=3, so slope is half the unpenalized slope.
    expect(predictResidual(model, [1, 8])).toBeCloseTo(1, 12);
    expect(predictResidual(model, [-1, 8])).toBeCloseTo(-1, 12);
    expect(model.coefficients[1]).toBe(0);
    expect(() => fitRidge([[NaN]], [1], 1)).toThrow("Invalid");
  });
  it("preserves signed tidal discharge, unit conversion and authentic irregular records", () => {
    const raw = JSON.parse(flowRaw);
    expect(data.temperature.quality.accepted).toBe(673);
    expect(data.discharge.quality.accepted).toBe(4034);
    const negative = raw.features.find((f: any) => Number(f.properties.value) < 0);
    expect(data.discharge.measurements.find((m) => m.id === negative.id)!.value)
      .toBeCloseTo(Number(negative.properties.value) * 0.028316846592, 10);
    expect(data.discharge.measurements.some((m) => m.time === "2025-08-05T18:16:03.000Z")).toBe(true);
  });
  it.each([
    ["units", (j: any) => j.features[0].properties.unit_of_measure = "m3/s"],
    ["series", (j: any) => j.features[0].properties.time_series_id = "tide-filtered-future-input"],
    ["statistic", (j: any) => j.features[0].properties.statistic_id = "00003"],
    ["duplicate", (j: any) => { j.features.push(j.features[0]); j.numberReturned = j.features.length; }],
    ["pagination", (j: any) => j.links.push({ rel: "next", href: "https://api.waterdata.usgs.gov/more" })],
    ["time", (j: any) => j.features[0].properties.time = "2024-01-01T00:00:00Z"]
  ])("rejects invalid %s with a recomputed local hash", (_name, change) => expect(editFlow(change)).toThrow());
  it("rejects changed raw bytes, source queries and file paths", () => {
    expect(() => validateCovariate(flowRaw + " ", data.manifest, "discharge")).toThrow("hash mismatch");
    const manifest = structuredClone(data.manifest);
    manifest.sources.discharge.sourceUrl = "https://example.com/data";
    expect(() => validateCovariate(flowRaw, manifest, "discharge")).toThrow("query mismatch");
    manifest.sources.discharge.file = "../other.json.gz";
    expect(() => validateCovariate(flowRaw, manifest, "discharge")).toThrow("specification");
  });
  it("excludes qualified/provisional values and skips exact joins without interpolation", () => {
    const excluded = editFlow((j) => {
      j.features[0].properties.approval_status = "Provisional";
      j.features[1].properties.qualifier = "e";
      j.features[2].properties.value = "";
    })();
    expect(excluded.quality.excluded.map((x) => x.reason)).toEqual(["not-approved", "qualified", "missing-or-invalid-value"]);
    const original = alignedPairs(data);
    const changed = structuredClone(data);
    changed.temperature.measurements = changed.temperature.measurements.filter((m) => m.time !== "2025-08-12T00:00:00.000Z");
    const incomplete = alignedPairs(changed);
    expect(incomplete.pairs.length).toBe(original.pairs.length - 12);
    expect(incomplete.skipped).toBe(12);
  });
  it("keeps model fitting, selection and calibration independent of future holdout data", () => {
    const before = runMultivariateExperiment(data), changed = structuredClone(data);
    const cutoff = Date.parse("2025-08-12T01:00:00Z");
    changed.oxygen.measurements.filter((m) => Date.parse(m.time) >= cutoff).forEach((m) => m.value += 3);
    for (const kind of ["temperature", "discharge"] as Covariate[]) {
      changed[kind].measurements.filter((m) => Date.parse(m.time) >= cutoff).forEach((m) => m.value += 20);
    }
    const after = runMultivariateExperiment(changed);
    expect(after.selected).toBe(before.selected);
    expect(after.candidates.map(({ model, selection }) => ({ model, selection })))
      .toEqual(before.candidates.map(({ model, selection }) => ({ model, selection })));
    expect(after.interval.halfWidthMgL).toBe(before.interval.halfWidthMgL);
    expect(after.rows[0]!.selectedPredictionMgL).toBe(before.rows[0]!.selectedPredictionMgL);
    expect(after.rows[0]!.actual).toBe(before.rows[0]!.actual + 3);
    expect(after.selectedHoldout.maeMgL).not.toBe(before.selectedHoldout.maeMgL);
  }, 20000);
  it("retains persistence when no model improves a perfect baseline", () => {
    const constant = structuredClone(data);
    constant.oxygen.measurements.forEach((m) => m.value = 8);
    const report = runMultivariateExperiment(constant);
    expect(report.selected).toBe("persistence");
    expect(report.selectedHoldout.maeMgL).toBe(0);
    expect(report.holdoutImprovementOverPersistencePercent).toBeNull();
    expect(report.decision).toContain("keep current operational path");
  }, 20000);
  it("purges cross-boundary labels and reproduces the entire report including its commitment", () => {
    const report = runMultivariateExperiment(data);
    expect(report.splits.purgedBoundaryPairs).toBe(3);
    expect(report.splits.holdout.pairs).toBe(143);
    expect(report.operationalModelChanged).toBe(false);
    expect(report.causalScenarioValidated).toBe(false);
    expect(verifyMultivariateReport(data, report).verified).toBe(true);
    expect(() => verifyMultivariateReport(data, { ...report, reportHash: "0xaltered" })).toThrow("reproduce");
    expect(() => runMultivariateExperiment({ ...data, manifest: { ...data.manifest,
      experiment: { ...data.manifest.experiment, selectionStart: "2025-08-14T00:00:00Z" } } })).toThrow("splits");
  }, 20000);
});
