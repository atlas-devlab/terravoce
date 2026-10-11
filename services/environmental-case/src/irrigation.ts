import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { canonicalJson, sha256Hex } from "@terravoce/protocol";
import { z } from "zod";

const hash = z.string().regex(/^0x[0-9a-f]{64}$/);
const predictionSchema = z.object({ version: z.literal("awash-sealed-persistence-v1"),
  protocolHash: hash, method: z.literal("persistence"), unit: z.literal("mm/day"),
  targetPeriod: z.literal("2024-03-D1"), predictedDailyMeanMm: z.number().finite().nonnegative(),
  trainedModel: z.literal(false), operationalEligible: z.literal(false) });
const clipSchema = z.object({
  rasterCode: z.literal("WAPOR-3.L2-AETI-D.2024-03-D1"), unit: z.literal("mm/day"),
  crs: z.literal("EPSG:4326"), scale: z.literal(0.1), offset: z.literal(0), noDataValue: z.literal(-9999),
  affineTransform: z.tuple([z.number(), z.number().positive(), z.literal(0), z.number(), z.literal(0), z.number().negative()]),
  window: z.object({ col: z.number().int().nonnegative(), row: z.number().int().nonnegative(),
    width: z.number().int().positive().max(64), height: z.number().int().positive().max(64) }),
  values: z.array(z.array(z.number().int().finite()))
});

function replayTargetMean(input: unknown, bbox: number[]) {
  const clip = clipSchema.parse(input);
  const [xmin, ymin, xmax, ymax] = bbox as [number, number, number, number];
  const [c, a, , f, , e] = clip.affineTransform;
  const { col, row, width, height } = clip.window;
  if (col !== Math.floor((xmin-c)/a) || row !== Math.floor((ymax-f)/e) ||
      width !== Math.ceil((xmax-c)/a)-col || height !== Math.ceil((ymin-f)/e)-row ||
      clip.values.length !== height || clip.values.some(r => r.length !== width)) {
    throw new Error("Target native pixel window mismatch");
  }
  const radians = (value: number) => value * Math.PI / 180;
  let sum = 0, area = 0;
  for (let j = 0; j < height; j++) {
    const north = f + (row+j)*e, south = north + e;
    const latitudeWeight = Math.sin(radians(Math.min(ymax, north))) - Math.sin(radians(Math.max(ymin, south)));
    for (let i = 0; i < width; i++) {
      const west = c + (col+i)*a, east = west + a;
      const weight = latitudeWeight * radians(Math.min(xmax, east)-Math.max(xmin, west));
      if (weight <= 0) continue;
      const pixel = clip.values[j]![i]!;
      if (pixel < 0) throw new Error("Missing or invalid target pixels; review stays pending");
      sum += pixel * clip.scale * weight;
      area += weight;
    }
  }
  if (!(area > 0)) throw new Error("Empty target area");
  return sum / area;
}
const resultSchema = z.object({
  version: z.literal("awash-learning-result-v1"), predictionHash: hash, targetManifestHash: hash,
  targetPeriod: z.literal("2024-03-D1"), predictedDailyMeanMm: z.number().finite().nonnegative(),
  actualEstimatedDailyMeanMm: z.number().finite().nonnegative(), signedErrorMmPerDay: z.number().finite(),
  absoluteErrorMmPerDay: z.number().finite().nonnegative(), unit: z.literal("mm/day"),
  scoredRounds: z.literal(1), skillEstablished: z.literal(false), irrigationWithdrawalM3: z.null(),
  irrigationAttributionEstablished: z.literal(false), ecologicalImprovementVerified: z.literal(false),
  fundingRelease: z.literal(false), operationalEligible: z.literal(false)
}).strict();

/** A research review envelope, distinct from a signed sensor observation or Oracle risk assessment. */
export function prepareIrrigationReview(input: unknown) {
  const result = resultSchema.parse(input);
  const difference = result.predictedDailyMeanMm - result.actualEstimatedDailyMeanMm;
  if (Math.abs(difference - result.signedErrorMmPerDay) > 1e-10 ||
      Math.abs(Math.abs(difference) - result.absoluteErrorMmPerDay) > 1e-10) {
    throw new Error("Irrigation research score does not reproduce");
  }
  const core = {
    version: "terravoce-irrigation-research-review-v1", regionId: "awash-wonji-demo",
    mode: "historical-research", evidenceNature: "remote-sensing-estimate",
    objective: "Review source provenance and a sealed persistence prediction; no field outcome claim",
    suggestedAction: "DATA_REVIEW", requiredReview: ["scientific", "affected-community"],
    operationalEligible: false, fundingRelease: false,
    irrigationWithdrawalM3: null, ecologicalImprovementVerified: false, result
  };
  return { ...core, evidenceHash: sha256Hex(`terravoce-irrigation-research-review-v1:${canonicalJson(core)}`) };
}

export async function loadIrrigationReview(folder: string) {
  const [raw, prediction, targetManifest, protocol] = await Promise.all([
    readFile(resolve(folder, "docs/evidence/awash-irrigation/result.json"), "utf8"),
    readFile(resolve(folder, "docs/evidence/awash-irrigation/prediction.json")),
    readFile(resolve(folder, "docs/datasets/awash-irrigation/target/manifest.json")),
    readFile(resolve(folder, "docs/datasets/awash-irrigation/protocol.json"))
  ]);
  const input = resultSchema.parse(JSON.parse(raw));
  const sealed = predictionSchema.parse(JSON.parse(prediction.toString()));
  const manifest = JSON.parse(targetManifest.toString());
  if (sha256Hex(prediction) !== input.predictionHash || sha256Hex(targetManifest) !== input.targetManifestHash ||
      manifest.predictionHashBeforeAcquisition !== input.predictionHash ||
      manifest.protocolHash !== sha256Hex(protocol) || sealed.protocolHash !== manifest.protocolHash ||
      sealed.method !== "persistence" || sealed.targetPeriod !== input.targetPeriod ||
      Math.abs(sealed.predictedDailyMeanMm - input.predictedDailyMeanMm) > 1e-10) {
    throw new Error("Prediction or target source commitment mismatch");
  }
  const entry = z.object({ extractionPath: z.literal("aeti-2024-03-D1.pixels.json"), extractionHash: hash })
    .parse(manifest.records.find((row: { metric: string }) => row.metric === "aeti"));
  const pixels = await readFile(resolve(folder, "docs/datasets/awash-irrigation/target", entry.extractionPath));
  if (sha256Hex(pixels) !== entry.extractionHash) throw new Error("Target native pixel hash mismatch");
  const nativeMean = replayTargetMean(JSON.parse(pixels.toString()), JSON.parse(protocol.toString()).bboxWgs84);
  if (Math.abs(nativeMean - input.actualEstimatedDailyMeanMm) > 1e-10) {
    throw new Error("FAO estimate does not reproduce from native pixels");
  }
  return prepareIrrigationReview(input);
}
