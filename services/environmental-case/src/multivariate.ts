import { canonicalJson, sha256Hex } from "@terravoce/protocol";
import type { Measurement } from "./dataset.js";
import type { MultivariateData } from "./multivariate-data.js";
import { forecastWindow, windowAt } from "./replay.js";
import { fitRidge, predictResidual, type RidgeModel } from "./ridge.js";

export const featureNames = ["oxygenNow", "oxygenDelta30m", "oxygenDelta2h", "oxygenDelta5h30m",
  "clockSinUTC", "clockCosUTC", "temperatureNow", "temperatureDelta2h", "signedDischargeNow", "signedDischargeDelta2h"];
export interface ForecastPair {
  origin: string; target: string; actual: number; persistence: number; linear: number; features: number[];
  evidence: { oxygen: string[]; temperature: string[]; discharge: string[]; targetOxygen: string };
}
export function alignedPairs(data: MultivariateData) {
  const temp = new Map(data.temperature.measurements.map((m) => [m.time, m]));
  const flow = new Map(data.discharge.measurements.map((m) => [m.time, m]));
  const oxygen = new Map(data.oxygen.measurements.map((m) => [m.time, m]));
  const pairs: ForecastPair[] = [];
  let skipped = 0, eligibleOrigins = 0;
  for (const origin of data.oxygen.measurements) {
    if (Date.parse(origin.time) < Date.parse(data.manifest.start) + 11 * 1800000 ||
        Date.parse(origin.time) + 3600000 > Date.parse(data.manifest.end)) continue;
    eligibleOrigins++;
    const targetTime = new Date(Date.parse(origin.time) + 3600000).toISOString();
    const target = oxygen.get(targetTime);
    let history: Measurement[];
    try { history = windowAt(data.oxygen, origin.time); } catch { skipped++; continue; }
    const temperature = history.map((m) => temp.get(m.time)), discharge = history.map((m) => flow.get(m.time));
    if (!target || temperature.some((m) => !m) || discharge.some((m) => !m)) { skipped++; continue; }
    const t = temperature as Measurement[], q = discharge as Measurement[], now = history[11]!.value;
    const clock = (Date.parse(origin.time) % 86400000) / 86400000 * 2 * Math.PI;
    pairs.push({ origin: origin.time, target: targetTime, actual: target.value, persistence: now,
      linear: forecastWindow(data.oxygen, history).forecastValue,
      features: [now, now - history[10]!.value, now - history[7]!.value, now - history[0]!.value,
        Math.sin(clock), Math.cos(clock), t[11]!.value, t[11]!.value - t[7]!.value,
        q[11]!.value, q[11]!.value - q[7]!.value],
      evidence: { oxygen: history.map((m) => m.id), temperature: t.map((m) => m.id),
        discharge: q.map((m) => m.id), targetOxygen: target.id } });
  }
  return { pairs, eligibleOrigins, skipped };
}
type Candidate = { name: string; width: number; model?: RidgeModel };
function predict(candidate: Candidate, row: ForecastPair) {
  if (candidate.name === "persistence") return row.persistence;
  if (candidate.name === "existing-linear") return row.linear;
  return row.persistence + predictResidual(candidate.model!, row.features.slice(0, candidate.width));
}
function scores(rows: ForecastPair[], candidate: Candidate) {
  if (!rows.length) throw new Error("Empty evaluation split");
  const errors = rows.map((r) => predict(candidate, r) - r.actual);
  return { pairs: rows.length, maeMgL: errors.reduce((s, e) => s + Math.abs(e), 0) / rows.length,
    rmseMgL: Math.sqrt(errors.reduce((s, e) => s + e * e, 0) / rows.length),
    biasMgL: errors.reduce((s, e) => s + e, 0) / rows.length };
}
export function runMultivariateExperiment(data: MultivariateData) {
  const { pairs, eligibleOrigins, skipped } = alignedPairs(data);
  const config = data.manifest.experiment;
  const selection = Date.parse(config.selectionStart), calibration = Date.parse(config.calibrationStart), holdout = Date.parse(config.holdoutStart);
  if (!(Date.parse(data.manifest.start) < selection && selection < calibration && calibration < holdout && holdout < Date.parse(data.manifest.end))) {
    throw new Error("Invalid chronological splits");
  }
  // Origin and label must both belong to their phase; pairs crossing a boundary are purged.
  const training = pairs.filter((r) => Date.parse(r.target) <= selection);
  const validation = pairs.filter((r) => Date.parse(r.origin) >= selection && Date.parse(r.target) <= calibration);
  const calibrating = pairs.filter((r) => Date.parse(r.origin) >= calibration && Date.parse(r.target) <= holdout);
  const testing = pairs.filter((r) => Date.parse(r.origin) >= holdout);
  if ([training, validation, calibrating, testing].some((r) => r.length < 24)) throw new Error("Insufficient chronological data");
  const candidates: Candidate[] = [{ name: "persistence", width: 0 }, { name: "existing-linear", width: 0 }];
  for (const [name, width] of [["oxygen-clock", 6], ["oxygen-clock-temperature", 8], ["oxygen-clock-temperature-discharge", 10]] as const) {
    for (const alpha of config.ridgeAlphas) candidates.push({ name: `${name}:ridge-${alpha}`, width,
      model: fitRidge(training.map((r) => r.features.slice(0, width)), training.map((r) => r.actual - r.persistence), alpha) });
  }
  // Deterministic tie-break favors earlier/simpler candidates. Holdout never chooses a model.
  const validationScores = candidates.map((c) => scores(validation, c));
  let selectedIndex = 0;
  for (let i = 1; i < candidates.length; i++) if (validationScores[i]!.maeMgL < validationScores[selectedIndex]!.maeMgL) selectedIndex = i;
  const selected = candidates[selectedIndex]!;
  const calibrationErrors = calibrating.map((r) => Math.abs(predict(selected, r) - r.actual)).sort((a, b) => a - b);
  const halfWidth = calibrationErrors[Math.ceil(calibrationErrors.length * config.intervalCoverage) - 1]!;
  const rows = testing.map((r) => {
    const predicted = predict(selected, r), lower = predicted - halfWidth, upper = predicted + halfWidth;
    return { ...r, selectedPredictionMgL: predicted, lowerMgL: lower, upperMgL: upper, covered: r.actual >= lower && r.actual <= upper };
  });
  const selectedTest = scores(testing, selected), baselineTest = scores(testing, candidates[0]!);
  const negativePredictions = rows.filter((r) => r.selectedPredictionMgL < 0).length;
  const report = {
    version: "willamette-forecast-experiment-v1", modelVersion: "ridge-residual-v1", mode: "observation-only",
    dataVintage: "retrospective approved archive; not an as-of-origin availability backtest",
    manifestHash: sha256Hex(canonicalJson(data.manifest)),
    sourceHashes: { oxygen: data.manifest.oxygenSourceHash, temperature: data.manifest.sources.temperature.rawSha256,
      discharge: data.manifest.sources.discharge.rawSha256, station: data.manifest.stationHash },
    period: { start: data.manifest.start, end: data.manifest.end }, horizonSeconds: 3600,
    featureNames, featureHistory: "current/past measurements only; exact UTC joins, no interpolation; signed instantaneous discharge",
    quality: { oxygen: data.oxygen.quality, temperature: data.temperature.quality, discharge: data.discharge.quality,
      eligibleOrigins, acceptedPairs: pairs.length, skippedMissingHistoryOrExactTarget: skipped },
    splits: { training: { targetThrough: config.selectionStart, pairs: training.length },
      selection: { originFrom: config.selectionStart, targetThrough: config.calibrationStart, pairs: validation.length },
      calibration: { originFrom: config.calibrationStart, targetThrough: config.holdoutStart, pairs: calibrating.length },
      holdout: { originFrom: config.holdoutStart, targetThrough: data.manifest.end, pairs: testing.length },
      purgedBoundaryPairs: pairs.length - training.length - validation.length - calibrating.length - testing.length },
    selectionRule: "lowest selection MAE among both baselines and all declared ridge candidates; no refit or holdout tuning",
    candidates: candidates.map((c, i) => ({ name: c.name, features: featureNames.slice(0, c.width), model: c.model ?? null,
      selection: validationScores[i]!, holdout: scores(testing, c) })),
    selected: selected.name, selectedHoldout: selectedTest,
    holdoutImprovementOverPersistencePercent: baselineTest.maeMgL === 0 ? null : (1 - selectedTest.maeMgL / baselineTest.maeMgL) * 100,
    interval: { method: "calibration absolute-error empirical quantile; serial dependence prevents a nominal coverage guarantee",
      requestedFraction: config.intervalCoverage, halfWidthMgL: halfWidth,
      holdoutCoverage: rows.filter((r) => r.covered).length / rows.length },
    observedHoldoutBelowIllustrative5MgL: rows.filter((r) => r.actual < 5).length, negativePredictions,
    decision: selected.name !== "persistence" && selectedTest.maeMgL < baselineTest.maeMgL && negativePredictions === 0
      ? "exploratory improvement; retain in observation mode, broader independent validation required"
      : "no demonstrated improvement suitable for promotion; keep current operational path",
    operationalModelChanged: false, ecologicalImprovementVerified: false, causalScenarioValidated: false,
    limitations: ["One station and two summer weeks; no seasonal or geographic generalization",
      "Finalized measurements may not have been available at historical forecast origins",
      "Overlapping horizons and serial dependence reduce effective independent sample size",
      "No demonstrated detection skill for low-oxygen events absent from the holdout",
      "Association is not an intervention effect; no pollutants, meteorology or causal physical model included",
      "No bridge, governance, policy, funds or field-actuator changes"], rows
  };
  return { ...report, reportHash: sha256Hex(canonicalJson(report)) };
}
export function verifyMultivariateReport(data: MultivariateData, candidate: unknown) {
  const reproduced = runMultivariateExperiment(data);
  if (canonicalJson(candidate) !== canonicalJson(reproduced)) throw new Error("Forecast report does not reproduce");
  return { verified: true, reportHash: reproduced.reportHash, scope: "deterministic local reproduction; not independent scientific validation" };
}
