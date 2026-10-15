"""Past-only filter, fixed development plan and timestamp preflight; no candidate scoring."""
import argparse
import gzip
import hashlib
import json
import math
from datetime import datetime, timedelta
from pathlib import Path

from audit_stability_compare import assert_same_receipt

ROOT = Path(__file__).resolve().parents[1]
PLAN = Path("docs/datasets/willamette-threshold-development/protocol.json")
PLAN_SHA256 = "d68381c42e992e4328b6bb454642a51878bedcf4b1d1748aafdc7576bb335d9e"
THRESHOLDS = (0, .025, .05, .1, .2)
SEASONS = ("winter", "spring", "summer", "autumn")
TOL = 1e-9
PINS = {
    "docs/evidence/willamette-stability/evaluation.json.gz": "5295b0a92a3f6d7c6dbec2efce5cbe1f407cbc5307fa992c4b48d479f020545f",
    "docs/evidence/willamette-multiseason/frozen-model.json": "72d7d14221c7b14c173dba59d69d2a1d36cbb27ee146378b9e046eea998762c9",
}


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def apply_filter(current_oxygen, ridge_prediction, threshold):
    """No target or future-history argument; discard the whole small correction."""
    if (not all(finite(v) for v in (current_oxygen, ridge_prediction, threshold))
            or current_oxygen < 0 or threshold < 0):
        raise ValueError("Need finite predictions, nonnegative current oxygen and threshold")
    correction = ridge_prediction - current_oxygen
    if not math.isfinite(correction):
        raise ValueError("Correction overflow")
    # Deliberately no epsilon or rounding at the rule's boundary.
    return current_oxygen if abs(correction) <= threshold else ridge_prediction


def instant(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() != timedelta(0):
        raise ValueError("Need UTC timestamps")
    return parsed


def split_window(window, rows):
    """Use timestamps only. Inspect no outcomes and compute no forecast errors."""
    start, end = instant(window["start"]), instant(window["end"])
    if end - start != timedelta(days=28):
        raise ValueError("Expected an archived 28-day query window")
    boundary = start + timedelta(days=14)
    groups = {"selection": [], "laterCheck": [], "excludedBetween": []}
    origins = set()
    for row in rows:
        origin, target = instant(row["origin"]), instant(row["target"])
        history = [instant(h["timeUTC"]) for h in row["oxygenHistory"]]
        if (origin in origins or len(history) != 12 or target - origin != timedelta(hours=1)
                or history != [origin - timedelta(minutes=30 * j) for j in range(11, -1, -1)]
                or history[0] < start or target > end or origin.minute not in (0, 30)
                or origin.second or origin.microsecond):
            raise ValueError("Invalid or duplicate origin, exact history, horizon or query bounds")
        origins.add(origin)
        group = "selection" if target < boundary else "laterCheck" if history[0] >= boundary else "excludedBetween"
        groups[group].append(row)
    if not groups["selection"] or not groups["laterCheck"]:
        raise ValueError("Both development parts need accepted pairs; no adequacy claim implied")
    latest_target = max(instant(r["target"]) for r in groups["selection"])
    earliest_history = min(instant(r["oxygenHistory"][0]["timeUTC"]) for r in groups["laterCheck"])
    # Exact half-hour grid: elapsed seconds are discrete, not a floating-point metric.
    origin_gap = int((min(instant(r["origin"]) for r in groups["laterCheck"]) -
                  max(instant(r["origin"]) for r in groups["selection"])).total_seconds())
    if not latest_target < earliest_history or origin_gap < 25200:
        raise ValueError("Development evidence overlaps across the boundary")
    return groups, {"boundaryUTC": boundary.isoformat().replace("+00:00", "Z"),
        "pairs": {name: len(values) for name, values in groups.items()},
        "latestSelectionTargetUTC": latest_target.isoformat().replace("+00:00", "Z"),
        "earliestLaterHistoryUTC": earliest_history.isoformat().replace("+00:00", "Z"),
        "retainedOriginGapSeconds": origin_gap, "noMechanicalOverlap": True}


def choose_from_summaries(baseline_mae, candidates):
    """Future runner's deterministic selection policy; tests use invented summaries only."""
    def validate_scores(values):
        if set(values) != set(SEASONS) or any(not finite(v) or v < 0 for v in values.values()):
            raise ValueError("Need four finite nonnegative window MAEs")
    validate_scores(baseline_mae)
    if (len(candidates) != len(THRESHOLDS) or any(not finite(c["thresholdMgL"]) for c in candidates) or
            {c["thresholdMgL"] for c in candidates} != set(THRESHOLDS)):
        raise ValueError("Need every fixed candidate exactly once")
    baseline = math.fsum(baseline_mae[s] for s in SEASONS) / 4
    eligible = []
    for candidate in candidates:
        validate_scores(candidate["seasonalMAE"])
        for field in ("nonzeroCorrections", "invalidOrNegativePredictions"):
            if type(candidate[field]) is not int or candidate[field] < 0:
                raise ValueError("Need nonnegative exact diagnostic counts")
        macro = math.fsum(candidate["seasonalMAE"][s] for s in SEASONS) / 4
        if (candidate["invalidOrNegativePredictions"] == 0 and baseline - macro > TOL and
                all(candidate["seasonalMAE"][s] <= baseline_mae[s] + TOL for s in SEASONS)):
            eligible.append(candidate | {"macroMAEMgL": macro})
    if not eligible:
        return {"decision": "retain-persistence", "thresholdMgL": None,
                "eligibleCandidates": 0, "selectionMacroMAEMgL": baseline}
    best = min(c["macroMAEMgL"] for c in eligible)
    tied = [c for c in eligible if c["macroMAEMgL"] <= best + TOL]
    chosen = min(tied, key=lambda c: (c["nonzeroCorrections"], -c["thresholdMgL"]))
    return {"decision": "candidate-for-later-development-check", "thresholdMgL": chosen["thresholdMgL"],
            "eligibleCandidates": len(eligible), "selectionMacroMAEMgL": chosen["macroMAEMgL"]}


def preflight(root=ROOT):
    raw = (root / PLAN).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PLAN_SHA256:
        raise ValueError("Development plan commitment changed")
    spec = json.loads(raw)
    if (spec["version"] != "willamette-threshold-development-v1" or
            spec["phase"] != "plan-and-synthetic-checks-before-candidate-scoring" or
            spec["stationId"] != "USGS-14211720" or spec["horizonSeconds"] != 3600 or
            spec["developmentOnly"] is not True or spec["allWindowsPreviouslyInspected"] is not True or
            spec["rule"]["candidateThresholdsMgL"] != list(THRESHOLDS) or
            spec["selection"]["numericalToleranceMgL"] != TOL or
            spec["split"]["minimumOriginSeparationSeconds"] != 25200 or
            spec["split"]["boundaryDaysAfterQueryStart"] != 14 or
            spec["nextUnseenTest"]["status"] != "not-defined-or-launched" or
            {i["file"]: i["rawSha256"] for i in spec["inputs"]} != PINS):
        raise ValueError("Development plan and implementation disagree")
    for filename, expected in PINS.items():
        if hashlib.sha256((root / filename).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Pinned development input changed: {filename}")
    report = json.loads(gzip.decompress((root / next(iter(PINS))).read_bytes()))
    if [w["window"]["season"] for w in report["windows"]] != list(SEASONS):
        raise ValueError("Expected the four archived windows")
    splits = []
    for window in report["windows"]:
        groups, receipt = split_window(window["window"], window["rows"])
        if sum(map(len, groups.values())) != len(window["rows"]):
            raise ValueError("Split lost development rows")
        splits.append({"window": window["window"]} | receipt)
    return {"planRawSHA256": hashlib.sha256(raw).hexdigest(), "inputsVerified": True,
            "thresholdsMgL": list(THRESHOLDS), "splits": splits,
            "candidateScoringExecuted": False, "thresholdSelected": False,
            "newTestLaunched": False, "newFit": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=("preflight",), default="preflight")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--verify-report", type=Path)
    args = parser.parse_args()
    receipt = preflight(args.root)
    if args.verify_report:
        assert_same_receipt(receipt, json.loads(args.verify_report.read_bytes()), "threshold preflight")
    print(json.dumps(receipt, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
