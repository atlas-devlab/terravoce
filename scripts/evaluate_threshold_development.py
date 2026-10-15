"""Offline threshold development on already-inspected Willamette archives; no fitting."""
import argparse
import hashlib
import json
import math
import re
from datetime import timedelta
from pathlib import Path

import evaluate_stability as stability
import threshold_development as plan
from audit_stability_compare import assert_same_receipt

ROOT = Path(__file__).resolve().parents[1]
P, R, C = stability.METHODS
FILTER = "small-correction-filter"
PREFLIGHT = Path("docs/evidence/willamette-threshold-development/preflight.json")
IMPLEMENTATION_FILES = sorted([
    "scripts/evaluate_threshold_development.py", "scripts/test_evaluate_threshold_development.py",
    "scripts/threshold_development.py", "scripts/test_threshold_development.py",
    "scripts/audit_stability_compare.py", str(plan.PLAN).replace("\\", "/"),
    str(PREFLIGHT).replace("\\", "/"),
])


def commitment(root, revision):
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", revision):
        raise ValueError("Need a full frozen Git commit before candidate scoring")
    files = []
    for filename in IMPLEMENTATION_FILES:
        current = (root / filename).read_bytes()
        if current != stability.git_bytes(root, revision, filename):
            raise ValueError(f"Development implementation changed from frozen Git commit: {filename}")
        files.append({"file": filename, "rawSha256": hashlib.sha256(current).hexdigest()})
    return {"frozenAtCommit": revision, "files": files,
            "currentFilesMatchGitCommit": True}


def summarize(rows, threshold=None):
    """Keep every input origin; never drop rows according to a method's error."""
    if not rows:
        raise ValueError("Cannot score an empty development part")
    methods = list(stability.METHODS) + ([FILTER] if threshold is not None else [])
    predictions = {m: [] for m in methods}
    for row in rows:
        if not plan.finite(row["actual"]) or row["actual"] < 0:
            raise ValueError("Need finite nonnegative observed oxygen")
        current = row["predictionsMgL"][P]
        if not plan.finite(current) or current < 0:
            raise ValueError("Need finite nonnegative persistence")
        for method in stability.METHODS:
            value = row["predictionsMgL"][method]
            if not plan.finite(value):
                raise ValueError("Nonfinite comparator prediction; shared cohort cannot be scored")
            predictions[method].append(value)
        if threshold is not None:
            predictions[FILTER].append(plan.apply_filter(current, row["predictionsMgL"][R], threshold))
    result = {}
    for method, values in predictions.items():
        try:
            metrics = stability.base.score(rows, values)
            metrics["maximumAbsoluteErrorMgL"] = max(abs(v - row["actual"]) for v, row in zip(values, rows))
        except OverflowError as error:
            raise ValueError("Development score overflow") from error
        if any(not math.isfinite(value) for value in metrics.values()):
            raise ValueError("Nonfinite development score")
        result[method] = {"scores": metrics, "nonfinitePredictions": 0,
            "negativePredictions": sum(value < 0 for value in values),
            # Exact comparison deliberately matches the committed selection policy.
            "nonzeroCorrections": sum(value != row["predictionsMgL"][P] for value, row in zip(values, rows))}
    return {"pairs": len(rows), "methods": result}


def macro(parts, method):
    if set(parts) != set(plan.SEASONS):
        raise ValueError("Need exactly the four fixed seasonal windows")
    return math.fsum(parts[s]["methods"][method]["scores"]["maeMgL"] for s in plan.SEASONS) / 4


def passes_screen(parts):
    gain = macro(parts, P) - macro(parts, FILTER)
    window_losses = {s: parts[s]["methods"][FILTER]["scores"]["maeMgL"] -
                     parts[s]["methods"][P]["scores"]["maeMgL"] for s in plan.SEASONS}
    invalid = sum(parts[s]["methods"][FILTER][field] for s in plan.SEASONS
                  for field in ("nonfinitePredictions", "negativePredictions"))
    return {"passed": gain > plan.TOL and all(v <= plan.TOL for v in window_losses.values()) and invalid == 0,
            "macroGainOverPersistenceMgL": gain, "windowLossAgainstPersistenceMgL": window_losses,
            "invalidOrNegativePredictions": invalid}


def grid_quality(window, groups):
    """Expected origin counts refer to the fixed grid, not to method-dependent filtering."""
    start, end = plan.instant(window["start"]), plan.instant(window["end"])
    boundary = start + timedelta(days=14)
    expected = {name: 0 for name in groups}
    origin = start + timedelta(hours=5.5)
    while origin + timedelta(hours=1) <= end:
        name = ("selection" if origin + timedelta(hours=1) < boundary else
                "laterCheck" if origin - timedelta(hours=5.5) >= boundary else "excludedBetween")
        expected[name] += 1
        origin += timedelta(minutes=30)
    if any(len(groups[name]) > expected[name] for name in groups):
        raise ValueError("Accepted origins exceed the fixed expected grid")
    return {name: {"expectedOrigins": expected[name], "acceptedPairs": len(groups[name]),
                   "missingOrIncompleteOrigins": expected[name] - len(groups[name])} for name in groups}


def develop(archived):
    """Selection uses first parts only; later parts cannot select or rescue a threshold."""
    if [w["window"]["season"] for w in archived["windows"]] != list(plan.SEASONS):
        raise ValueError("Expected the four fixed windows in order")
    split, metadata = {}, []
    for window in archived["windows"]:
        if window.get("dataScreenPassed") is not True or not isinstance(window.get("quality"), dict):
            raise ValueError("Missing or failed archived quality screen")
        groups, receipt = plan.split_window(window["window"], window["rows"])
        split[window["window"]["season"]] = groups
        metadata.append({"window": window["window"], "split": receipt,
            "gridByPart": grid_quality(window["window"], groups),
            "wholeWindowSourceQuality": window["quality"],
            "wholeWindowSourceQualityMeaning": "Archived source QA over the full 28-day query; not split-specific raw record counts"})
    baseline = {s: summarize(split[s]["selection"]) for s in plan.SEASONS}
    candidates, summaries = [], []
    for threshold in plan.THRESHOLDS:
        parts = {s: summarize(split[s]["selection"], threshold) for s in plan.SEASONS}
        candidate = {"thresholdMgL": threshold, "parts": parts, "macroMAEMgL": macro(parts, FILTER)}
        summary = {"thresholdMgL": threshold,
            "seasonalMAE": {s: parts[s]["methods"][FILTER]["scores"]["maeMgL"] for s in plan.SEASONS},
            "nonzeroCorrections": sum(parts[s]["methods"][FILTER]["nonzeroCorrections"] for s in plan.SEASONS),
            "invalidOrNegativePredictions": sum(parts[s]["methods"][FILTER][field] for s in plan.SEASONS
                for field in ("nonfinitePredictions", "negativePredictions"))}
        candidates.append(candidate | {"selectionSummary": summary, "screen": passes_screen(parts)})
        summaries.append(summary)
    selection = plan.choose_from_summaries({s: baseline[s]["methods"][P]["scores"]["maeMgL"] for s in plan.SEASONS}, summaries)
    threshold = selection["thresholdMgL"]
    later = None
    if threshold is not None:
        parts = {s: summarize(split[s]["laterCheck"], threshold) for s in plan.SEASONS}
        later = {"thresholdMgL": threshold, "parts": parts,
                 "macroMAEMgL": {m: macro(parts, m) for m in (*stability.METHODS, FILTER)},
                 "screen": passes_screen(parts), "otherThresholdsScored": False}
    status = ("no-promising-threshold" if threshold is None else
              "promising-in-development-only" if later["screen"]["passed"] else "selected-threshold-failed-later-development-check")
    return {"status": status, "selectedThresholdMgL": threshold, "windows": metadata,
            "selection": {"comparators": baseline, "candidates": candidates, "choice": selection}, "laterCheck": later}


def evaluate(root, frozen_at_commit):
    root = Path(root).resolve()
    frozen = commitment(root, frozen_at_commit)  # Must precede reading candidate outcomes.
    preflight = plan.preflight(root)
    assert_same_receipt(preflight, json.loads((root / PREFLIGHT).read_bytes()), "committed threshold preflight")
    source = root / next(iter(plan.PINS))
    archived = stability.read_report(source)
    assert_same_receipt(stability.evaluate(root), archived, "completed stability replay")
    return {"version": "willamette-threshold-development-evaluation-v1",
        "planRawSHA256": preflight["planRawSHA256"], "implementationCommitment": frozen,
        "pinnedInputs": [{"file": path, "rawSha256": digest} for path, digest in plan.PINS.items()],
        "completedStabilityReplayVerified": True, "stationId": "USGS-14211720", "horizonSeconds": 3600,
        "developmentOnly": True, "allWindowsPreviouslyInspected": True,
        "newModelFit": False, "newDataAcquisition": False, "newUnseenTestLaunched": False,
        "operationalModelChanged": False, "laterCheckCanSelectThreshold": False,
        "primaryMetric": "Equal-window mean of four MAEs in mg/L", **develop(archived),
        "limitations": ["Both temporal parts were previously inspected; the later check is development, not independent validation",
            "No statistical confidence or practical environmental benefit is established by the arithmetic acceptance screen",
            "Finalized archives do not prove historical as-of-origin availability or prospective forecast skill"],
        "mission": "Verifiable environmental evidence supporting community and youth decision rights; no Oracle, governance, quorum, treasury, token or spending change"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("evaluate", "verify"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--frozen-at-commit")
    args = parser.parse_args()
    if args.command == "evaluate":
        if args.output is None or args.report is not None or not args.frozen_at_commit:
            parser.error("evaluate needs --output and --frozen-at-commit, without --report")
        if args.output.exists():
            raise ValueError("Report already exists; never overwrite, use verify")
        result = evaluate(args.root, args.frozen_at_commit)
        with args.output.open("xb") as target:
            target.write((json.dumps(result, indent=2, allow_nan=False) + "\n").encode("utf-8"))
        print(json.dumps({"status": result["status"], "selectedThresholdMgL": result["selectedThresholdMgL"]}))
    else:
        if args.report is None or args.output is not None or args.frozen_at_commit is not None:
            parser.error("verify needs --report, without --output or --frozen-at-commit")
        saved = stability.read_report(args.report)
        result = evaluate(args.root, saved["implementationCommitment"]["frozenAtCommit"])
        assert_same_receipt(result, saved, "threshold development replay")
        print(json.dumps({"verified": True, "status": saved["status"]}))


if __name__ == "__main__":
    main()
