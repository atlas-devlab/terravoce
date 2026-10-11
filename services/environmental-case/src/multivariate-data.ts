import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { gunzipSync } from "node:zlib";
import { sha256Hex } from "@terravoce/protocol";
import { z } from "zod";
import { loadDataset, type Dataset, type Measurement } from "./dataset.js";

const sourceSchema = z.object({
  file: z.string(), rawSha256: z.string().regex(/^0x[0-9a-f]{64}$/),
  parameterCode: z.string(), timeSeriesId: z.string(), unit: z.string(),
  sourceUrl: z.url(), capturedAt: z.iso.datetime()
}).strict();
export const multivariateManifestSchema = z.object({
  version: z.literal("willamette-multivariate-v1"), stationId: z.literal("USGS-14211720"),
  start: z.iso.datetime(), end: z.iso.datetime(), oxygenSourceHash: z.string(), stationHash: z.string(),
  license: z.literal("US Government work; public domain"),
  sources: z.object({ temperature: sourceSchema, discharge: sourceSchema }).strict(),
  experiment: z.object({
    horizonSeconds: z.literal(3600), windowSize: z.literal(12),
    selectionStart: z.iso.datetime(), calibrationStart: z.iso.datetime(), holdoutStart: z.iso.datetime(),
    ridgeAlphas: z.array(z.number().positive()).min(1), intervalCoverage: z.number().gt(0).lt(1),
    selectionMetric: z.literal("MAE"), status: z.string()
  }).strict()
}).strict();
export type MultivariateManifest = z.infer<typeof multivariateManifestSchema>;
export type Covariate = "temperature" | "discharge";
const specifications = {
  temperature: { file: "temperature.json.gz", code: "00010", series: "78520072e15541dea31a430cc3a72b93", unit: "degC", scale: 1 },
  discharge: { file: "discharge.json.gz", code: "00060", series: "25161ce7dc08491389080de10c85fd9e", unit: "ft^3/s", scale: 0.028316846592 }
} as const;
const collectionSchema = z.object({
  type: z.literal("FeatureCollection"), numberReturned: z.number().int().optional(),
  links: z.array(z.object({ rel: z.string(), href: z.string() })),
  features: z.array(z.object({ id: z.string().min(1), properties: z.object({
    monitoring_location_id: z.string(), time_series_id: z.string(), parameter_code: z.string(),
    statistic_id: z.string(), time: z.iso.datetime({ offset: true }), value: z.string().nullable(),
    unit_of_measure: z.string(), approval_status: z.string(), qualifier: z.unknown(),
    last_modified: z.iso.datetime({ offset: true })
  }) }))
});
export function validateCovariate(raw: string, manifest: MultivariateManifest, kind: Covariate) {
  const source = manifest.sources[kind], spec = specifications[kind];
  if (source.file !== spec.file || source.parameterCode !== spec.code || source.timeSeriesId !== spec.series || source.unit !== spec.unit) {
    throw new Error("Covariate specification mismatch");
  }
  if (sha256Hex(raw) !== source.rawSha256) throw new Error("Covariate snapshot hash mismatch");
  const url = new URL(source.sourceUrl);
  if (url.origin !== "https://api.waterdata.usgs.gov" || url.username || url.password ||
      url.hash || url.searchParams.size !== 5 ||
      url.pathname !== "/ogcapi/v1/collections/continuous/items" || url.searchParams.get("f") !== "json" ||
      url.searchParams.get("monitoring_location_id") !== manifest.stationId ||
      url.searchParams.get("parameter_code") !== spec.code || url.searchParams.get("limit") !== "10000" ||
      url.searchParams.get("time") !== `${manifest.start}/${manifest.end}`) throw new Error("Covariate source query mismatch");
  const data = collectionSchema.parse(JSON.parse(raw));
  if (data.features.length >= 10000 || data.links.some((l) => l.rel === "next") ||
      (data.numberReturned !== undefined && data.numberReturned !== data.features.length)) throw new Error("Incomplete covariate snapshot");
  const measurements: Measurement[] = [], excluded: { id: string; reason: string }[] = [];
  const ids = new Set<string>(), times = new Set<number>();
  for (const f of data.features) {
    const p = f.properties, time = Date.parse(p.time);
    if (ids.has(f.id) || times.has(time)) throw new Error("Duplicate covariate record");
    ids.add(f.id); times.add(time);
    if (p.monitoring_location_id !== manifest.stationId || p.time_series_id !== spec.series ||
        p.parameter_code !== spec.code || p.statistic_id !== "00011" || p.unit_of_measure !== spec.unit) {
      throw new Error("Mixed covariate station, series, parameter, statistic or unit");
    }
    // Authentic irregular timestamps and signed tidal discharge are retained, never resampled.
    if (time < Date.parse(manifest.start) || time > Date.parse(manifest.end)) throw new Error("Covariate outside interval");
    const value = p.value === null || p.value.trim() === "" ? NaN : Number(p.value);
    const reason = p.approval_status !== "Approved" ? "not-approved" :
      p.qualifier !== null && p.qualifier !== "" ? "qualified" :
      !Number.isFinite(value) ? "missing-or-invalid-value" : undefined;
    if (reason) { excluded.push({ id: f.id, reason }); continue; }
    measurements.push({ id: f.id, time: new Date(time).toISOString(), value: value * spec.scale,
      lastModified: new Date(p.last_modified).toISOString() });
  }
  measurements.sort((a, b) => Date.parse(a.time) - Date.parse(b.time));
  return { measurements, quality: { total: data.features.length, accepted: measurements.length, excluded,
    sourceUnit: spec.unit, normalizedUnit: kind === "discharge" ? "m3/s" : "degC", scale: spec.scale } };
}
export interface MultivariateData {
  manifest: MultivariateManifest; oxygen: Dataset;
  temperature: ReturnType<typeof validateCovariate>; discharge: ReturnType<typeof validateCovariate>;
}
export async function loadMultivariateData(folder: string, oxygenFolder: string): Promise<MultivariateData> {
  const manifest = multivariateManifestSchema.parse(JSON.parse(await readFile(resolve(folder, "manifest.json"), "utf8")));
  const oxygen = await loadDataset(oxygenFolder);
  if (oxygen.manifest.sourceHash !== manifest.oxygenSourceHash || oxygen.manifest.stationHash !== manifest.stationHash ||
      oxygen.manifest.start !== manifest.start || oxygen.manifest.end !== manifest.end) throw new Error("Oxygen snapshot mismatch");
  const read = async (kind: Covariate) => {
    if (manifest.sources[kind].file !== specifications[kind].file) throw new Error("Covariate file mismatch");
    const compressed = await readFile(resolve(folder, manifest.sources[kind].file));
    return validateCovariate(gunzipSync(compressed, { maxOutputLength: 10_000_000 }).toString("utf8"), manifest, kind);
  };
  const [temperature, discharge] = await Promise.all([read("temperature"), read("discharge")]);
  return { manifest, oxygen, temperature, discharge };
}
