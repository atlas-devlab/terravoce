"""Post-hoc error decomposition of the completed stability experiment; offline, no fit."""
import argparse
import gzip
import hashlib
import json
import math
from datetime import datetime, timedelta
from pathlib import Path

import evaluate_stability as completed
from audit_stability_compare import assert_same_receipt
from forecast_diagnostics import contribution_breakdown

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path("docs/evidence/willamette-stability/evaluation.json.gz")
MODEL = Path("docs/evidence/willamette-multiseason/frozen-model.json")
OUTPUT = Path("docs/evidence/willamette-error-mechanisms/diagnostic.json")
P, R, C = completed.METHODS
TOL = 1e-9  # Numerical comparisons only; not an environmental or sensor threshold.
PINS = {
    SOURCE.as_posix(): "5295b0a92a3f6d7c6dbec2efce5cbe1f407cbc5307fa992c4b48d479f020545f",
    MODEL.as_posix(): "72d7d14221c7b14c173dba59d69d2a1d36cbb27ee146378b9e046eea998762c9",
}
OUTCOMES = ("unchanged", "rise", "fall")
MAGNITUDES = ("zero", "(0,0.1]", "(0.1,0.3]", ">0.3")
BEHAVIORS = ("no-correction-unchanged", "no-correction-changed", "corrected-unchanged",
             "wrong-direction", "right-direction-undershoot", "overshoot-helps",
             "overshoot-tie", "overshoot-harms")


def close(a, b):
    if not math.isfinite(a) or not math.isfinite(b) or abs(a - b) > TOL:
        raise ValueError(f"Decomposition does not reconcile: {a} versus {b}")


def errors(row, method):
    return row["predictionsMgL"][method] - row["actual"]


def gain(row, method, squared=False):
    p, m = errors(row, P), errors(row, method)
    return p * p - m * m if squared else abs(p) - abs(m)


def outcome(row):
    delta = row["actual"] - row["predictionsMgL"][P]
    return "unchanged" if abs(delta) <= TOL else ("rise" if delta > 0 else "fall")


def magnitude(row):
    delta = abs(row["actual"] - row["predictionsMgL"][P])
    return MAGNITUDES[0 if delta <= TOL else 1 if delta <= .1 + TOL else 2 if delta <= .3 + TOL else 3]


def behavior(row, method):
    future = row["actual"] - row["predictionsMgL"][P]
    correction = row["predictionsMgL"][method] - row["predictionsMgL"][P]
    if abs(correction) <= TOL:
        return "no-correction-unchanged" if abs(future) <= TOL else "no-correction-changed"
    if abs(future) <= TOL:
        return "corrected-unchanged"
    if correction * future < 0:
        return "wrong-direction"
    if abs(correction) <= abs(future) + TOL:
        return "right-direction-undershoot"
    advantage = gain(row, method)
    return "overshoot-tie" if abs(advantage) <= TOL else "overshoot-helps" if advantage > 0 else "overshoot-harms"


def scores(rows, method):
    if not rows:
        return None
    values = [errors(row, method) for row in rows]
    return {"maeMgL": math.fsum(abs(v) for v in values) / len(values),
            "mseMgL2": math.fsum(v * v for v in values) / len(values),
            "rmseMgL": math.sqrt(math.fsum(v * v for v in values) / len(values)),
            "biasMgL": math.fsum(values) / len(values)}


def partition(windows, names, classifier, method=C):
    """Conditioned pooled scores and exact additive contributions use different denominators."""
    groups = []
    for name in names:
        selected = [[row for row in window["rows"] if classifier(row) == name] for window in windows]
        pooled = [row for rows in selected for row in rows]
        by_season = [{"season": window["window"]["season"], "pairs": len(rows),
                      "seasonDenominator": len(window["rows"]),
                      "maeGainContributionMgL": math.fsum(gain(r, method) for r in rows) / len(window["rows"])}
                     for window, rows in zip(windows, selected)]
        groups.append({"group": name, "pairs": len(pooled),
            "pooledScores": {m: scores(pooled, m) for m in (P, method)},
            "macroMAEGainContributionMgL": math.fsum(s["maeGainContributionMgL"] for s in by_season) / len(windows),
            "macroMSEGainContributionMgL2": math.fsum(
                math.fsum(gain(r, method, squared=True) for r in rows) / len(w["rows"])
                for w, rows in zip(windows, selected)) / len(windows),
            "bySeason": by_season})
    if sum(g["pairs"] for g in groups) != sum(len(w["rows"]) for w in windows):
        raise ValueError("Partition dropped or duplicated observations")
    for squared, field in ((False, "macroMAEGainContributionMgL"), (True, "macroMSEGainContributionMgL2")):
        expected = math.fsum(math.fsum(gain(r, method, squared) for r in w["rows"]) / len(w["rows"])
                             for w in windows) / len(windows)
        close(math.fsum(g[field] for g in groups), expected)
    return groups


def attenuation_slope(rows, method):
    """Right derivative at lambda=0 of mean |actual-current-lambda*correction|."""
    terms = []
    for row in rows:
        residual = row["actual"] - row["predictionsMgL"][P]
        d = row["predictionsMgL"][method] - row["predictionsMgL"][P]
        # Exact equality defines the cusp. Numerical tolerance does not change this proof.
        terms.append(abs(d) if residual == 0 else -math.copysign(1., residual) * d)
    return math.fsum(terms) / len(terms)


def validate_rows(windows):
    if [w["window"]["season"] for w in windows] != ["winter", "spring", "summer", "autumn"]:
        raise ValueError("Expected the four completed seasonal windows")
    origins = set()
    for window in windows:
        if not window["rows"]:
            raise ValueError("Empty completed season")
        for row in window["rows"]:
            key = row["origin"]
            start = datetime.fromisoformat(key.replace("Z", "+00:00"))
            end = datetime.fromisoformat(row["target"].replace("Z", "+00:00"))
            values = [row["actual"], *row["predictionsMgL"].values(), *row["features"]]
            if key in origins or end - start != timedelta(hours=1) or any(
                    type(v) not in (int, float) or not math.isfinite(v) for v in values):
                raise ValueError("Duplicate, nonfinite or non-hourly diagnostic row")
            origins.add(key)
            history = row["oxygenHistory"]
            times = [datetime.fromisoformat(h["timeUTC"].replace("Z", "+00:00")) for h in history]
            if (len(history) != 12 or times != [start - timedelta(minutes=30 * j) for j in range(11, -1, -1)]
                    or any(type(h["value"]) not in (int, float) or not math.isfinite(h["value"]) for h in history)
                    or history[-1]["value"] != row["predictionsMgL"][P]
                    or set(row["predictionsMgL"]) != set(completed.METHODS)):
                raise ValueError("Invalid twelve-sample history or methods")
            flat = all(h["value"] == history[0]["value"] for h in history)
            if type(row["historyFlat"]) is not bool or row["historyFlat"] != flat:
                raise ValueError("Saved flat-history label disagrees with past measurements")
            close(row["predictionsMgL"][C], row["predictionsMgL"][P if flat else R])


def example(row, season, frozen):
    adapted = {"features": row["features"], "persistence": row["predictionsMgL"][P],
               "newPrediction": row["predictionsMgL"][R]}
    return {"season": season, "origin": row["origin"], "target": row["target"],
            "actualMgL": row["actual"], "predictionsMgL": row["predictionsMgL"],
            "absoluteErrorsMgL": {m: abs(errors(row, m)) for m in completed.METHODS},
            "fallbackGainMgL": gain(row, C), "oxygenHistory": row["oxygenHistory"],
            "outsideTrainingFeatures": row["outsideTrainingFeatures"],
            "numericalContributionsNotPhysicalCauses": contribution_breakdown(
                adapted, frozen["model"], frozen["recipe"]["features"])}


def diagnose(root=ROOT):
    inputs = []
    for filename, expected in PINS.items():
        raw = (root / filename).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError(f"Completed input changed: {filename}")
        inputs.append({"file": filename, "rawSha256": expected})
    raw = gzip.decompress((root / SOURCE).read_bytes())
    if hashlib.sha256(raw).hexdigest() != "d0e216eea8127c9b78bb1010068452fa7ca606d7344234f38ea42f4dd3302673":
        raise ValueError("Uncompressed evaluation changed")
    report = json.loads(raw)
    # Rebuild forecasts, source hashes, quality filters and the pre-capture Git commitment.
    # This is replay of the completed model, never a solver or new candidate prediction.
    completed.shared.compare_saved(completed.evaluate(root), report, "completed stability evaluation")
    windows = report["windows"]
    validate_rows(windows)
    frozen = json.loads((root / MODEL).read_bytes())
    rows = [r for w in windows for r in w["rows"]]
    seasonal = [{"window": w["window"], "pairs": len(w["rows"]),
                 "scores": {m: scores(w["rows"], m) for m in completed.METHODS}} for w in windows]
    macro = {m: {metric: math.fsum(s["scores"][m][metric] for s in seasonal) / 4
                 for metric in ("maeMgL", "mseMgL2", "rmseMgL")}
             for m in completed.METHODS}
    for m in completed.METHODS:
        close(macro[m]["maeMgL"], report["macro"]["seasonalMeanMAEMgL"][m])
    outcome_groups = partition(windows, OUTCOMES, outcome)
    magnitude_groups = partition(windows, MAGNITUDES, magnitude)
    behaviors = {m: partition(windows, BEHAVIORS, lambda row, method=m: behavior(row, method), m)
                 for m in (R, C)}
    past = {
        "flatHistory": partition(windows, ("flat", "changing"), lambda r: "flat" if r["historyFlat"] else "changing"),
        "ridgeCorrectionAmplitude": partition(windows, ("at-most-0.05", "above-0.05"),
            lambda r: "at-most-0.05" if abs(r["predictionsMgL"][R] - r["predictionsMgL"][P]) <= .05 + TOL else "above-0.05"),
    }
    counts = {}
    for method in (R, C):
        gains = [gain(r, method) for r in rows]
        counts[method] = {"wins": sum(g > TOL for g in gains), "ties": sum(abs(g) <= TOL for g in gains),
                          "losses": sum(g < -TOL for g in gains), "pairs": len(rows)}
    slopes = {m: {"bySeason": [{"season": w["window"]["season"], "rightDerivativeAtZeroMgL": attenuation_slope(w["rows"], m)}
                              for w in windows],
                  "macroRightDerivativeAtZeroMgL": math.fsum(attenuation_slope(w["rows"], m) for w in windows) / 4}
              for m in (R, C)}
    ordered = sorted(((r, w["window"]["season"]) for w in windows for r in w["rows"]),
                     key=lambda pair: (gain(pair[0], C), pair[0]["origin"]))
    return {"version": "willamette-posthoc-error-mechanisms-v1", "stationId": report["stationId"],
        "horizonSeconds": 3600, "inputs": inputs, "completedProtocolHash": report["protocolHash"],
        "pairs": len(rows), "methods": list(completed.METHODS), "seasonal": seasonal, "macro": macro,
        "comparisonsToPersistence": counts, "byFutureOutcome": outcome_groups,
        "byFutureChangeMagnitude": magnitude_groups, "behavior": behaviors, "knownAtOriginGroups": past,
        "constantAttenuation": slopes,
        "examples": {"maximumHarm": example(*ordered[0], frozen), "maximumBenefit": example(*ordered[-1], frozen)},
        "definitions": {
            "gain": "abs(persistence-actual) - abs(method-actual); positive helps",
            "macroMAE": "Equal mean of four within-window MAEs, not a pooled mean",
            "contribution": "Sum of subgroup error gains / all accepted pairs of that season, then equal mean of four seasons; additive",
            "pooledScores": "Conditional mean over subgroup pairs pooled across seasons; different denominator from macro contribution",
            "macroRMSE": "Equal mean of four seasonal RMSEs; does not decompose additively",
            "mseContribution": "Uses squared errors; additive MSE, not RMSE",
            "numericTolerance": TOL,
            "futureLabels": "Outcomes and change magnitudes need the target; explanatory only, never available forecast gates",
            "amplitudeCut": "0.05 mg/L is an inspected post-hoc descriptive cut; not selected, optimized or validated for prediction",
            "attenuationProof": "F(lambda)=mean_seasons mean_rows |actual-current-lambda*d| is convex. A positive right derivative at zero implies F(lambda)>F(0) for any constant lambda>0 on this finite dataset only",
        },
        "scope": {"postHoc": True, "newFinalValidation": False, "newDataDownloaded": False,
                  "modelRefitted": False, "newForecastRuleEvaluated": False, "operationalModelChanged": False,
                  "nextTestAgreedOrFrozen": False},
        "limitations": ["Four already-inspected 28-day 2025 windows at one tidal station; seasonal labels are not full-season validation",
            "Archived finalized observations do not establish as-of-origin availability, instrument accuracy or live forecasting skill",
            "Equality and 0.1 mg/L increments concern published values, not physical constancy or measurement uncertainty",
            "Examples are deterministic extremes, not typical performance; coefficient contributions are arithmetic, not causal effects",
            "No attribution to weather, tides, pollution or human activity is established by this decomposition",
            "No observed target below illustrative 5 mg/L; no hypoxia alert, intervention or ecological benefit validated",
            "No calibrated prediction intervals or independent subgroup uncertainty estimates; grouped results are descriptive"],
        "mission": report["mission"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "verify"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.command == "run":
        if args.output is None or args.report is not None:
            parser.error("run requires --output only")
        if args.output.exists():
            raise ValueError("Never overwrite a saved diagnostic; use verify")
        report = diagnose(args.root)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8", newline="\n") as target:
            json.dump(report, target, ensure_ascii=False, indent=2, allow_nan=False)
            target.write("\n")
    else:
        if args.output is not None:
            parser.error("verify does not accept --output")
        path = args.report or args.root / OUTPUT
        assert_same_receipt(diagnose(args.root), json.loads(path.read_bytes()), "error mechanisms")
        report = json.loads(path.read_bytes())
    print(json.dumps({"verified": True, "pairs": report["pairs"], "scope": report["scope"]}))


if __name__ == "__main__":
    main()
