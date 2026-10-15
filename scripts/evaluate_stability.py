"""Offline replay of the frozen one-hour stability rule; no fitting or network access."""
import argparse
import gzip
import json
import math
import random
import re
import subprocess
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import audit_willamette as shared
import experiment_multiseason as base
import stability_protocol as protocol

ROOT = Path(__file__).resolve().parents[1]
DATA = protocol.PROTOCOL.parent
CAPTURE_VERSION = "stability-test-capture-v1"
METHODS = ("persistence", "same-frozen-ridge-without-fallback", "same-frozen-ridge-with-fallback")
PERSISTENCE, RIDGE, FALLBACK = METHODS
BASELINES = METHODS[:2]
IMPLEMENTATION_FILES = sorted(set([
    "scripts/capture-willamette-stability.mjs", "scripts/test-capture-stability.mjs",
    "scripts/evaluate_stability.py", "scripts/test_evaluate_stability.py",
    "scripts/stability_protocol.py", "scripts/test_stability_protocol.py",
    "scripts/experiment_multiseason.py", "scripts/audit_willamette.py",
    str(protocol.PROTOCOL).replace("\\", "/"),
    "docs/evidence/willamette-multiseason/frozen-model.json",
    *protocol.PREVIOUS_FILES]))


def implementation_hash(files):
    """Exactly the capture runner's JSON.stringify(array), UTF-8, without a newline."""
    return shared.digest(json.dumps(files, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def git_bytes(root, revision, filename):
    return subprocess.run(["git", "show", f"{revision}:{filename}"], cwd=root,
                          capture_output=True, check=True, timeout=20).stdout


def verify_implementation(root, manifest):
    revision, files = manifest.get("frozenAtCommit", ""), manifest.get("implementationFiles", [])
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", revision):
        raise ValueError("Capture needs a full frozen Git commit")
    if (not isinstance(files, list) or any(not isinstance(item, dict) or set(item) != {"file", "rawSha256"} for item in files)
            or [item["file"] for item in files] != IMPLEMENTATION_FILES
            or implementation_hash(files) != manifest.get("implementationSnapshotHash")):
        raise ValueError("Capture implementation snapshot mismatch")
    for item in files:
        current = (root / item["file"]).read_bytes()
        if shared.digest(current) != item["rawSha256"] or shared.digest(git_bytes(root, revision, item["file"])) != item["rawSha256"]:
            raise ValueError(f"Implementation bytes differ from frozen Git commit: {item['file']}")
    return {"frozenAtCommit": revision, "implementationFiles": files,
            "implementationSnapshotHash": manifest["implementationSnapshotHash"],
            "verifiedAgainstCurrentFilesAndGit": True}


def frozen_inputs(root):
    raw = (root / protocol.PROTOCOL).read_bytes()
    spec = json.loads(raw)
    protocol.validate_definition(spec, protocol.previous_windows(root))
    for filename, expected in ((spec["baseModel"]["file"], spec["baseModel"]["rawSha256"]),
                               (spec["baseModel"]["protocolFile"], spec["baseModel"]["protocolRawSha256"])):
        if shared.digest((root / filename).read_bytes()) != expected:
            raise ValueError("Frozen model or base protocol bytes changed")
    source_spec, model, model_hash = base.frozen(root)  # Provenance QA only; never invokes a solver.
    if model_hash != spec["baseModel"]["rawSha256"]:
        raise ValueError("Unexpected frozen model")
    return spec, shared.digest(raw), source_spec, model, model_hash


def oxygen_history(root, window, sources, manifest):
    """Read only the accepted archived oxygen records, with the same QA as pair construction."""
    spec = sources["sources"]["oxygen"]
    raw = shared.compressed_body(root / DATA / window["id"] / manifest["sources"]["oxygen"]["file"])
    if shared.digest(raw) != manifest["sources"]["oxygen"]["rawSha256"]:
        raise ValueError("Oxygen body changed between pair construction and rule replay")
    records, _ = shared.read_collection(raw, sources["stationId"], spec["parameterCode"],
        spec["timeSeriesId"], spec["unit"], shared.instant(window["start"]), shared.instant(window["end"]), spec["scale"])
    return records


def verify_archived_bodies(root, window, sources, manifest):
    """An unavailable window can still contain complete companion or HTTP-error bodies."""
    if set(manifest.get("sources", {})) != set(base.KINDS):
        raise ValueError("Capture must describe all three attempted sources")
    hashes = {}
    for kind, source in manifest["sources"].items():
        spec = sources["sources"][kind]
        url = urlparse(source["sourceUrl"])
        if (source["file"] != f"{kind}.json.gz" or url.scheme != "https" or url.netloc != "api.waterdata.usgs.gov"
                or url.path != "/ogcapi/v1/collections/continuous/items" or url.fragment
                or parse_qs(url.query) != {"f": ["json"], "monitoring_location_id": [sources["stationId"]],
                    "parameter_code": [spec["parameterCode"]], "time": [f"{window['start']}/{window['end']}"], "limit": ["10000"]}
                or source.get("captureStatus") not in ("captured", "unavailable")
                or manifest["status"] == "captured" and source["captureStatus"] != "captured"):
            raise ValueError("Capture source request/status mismatch")
        path = root / DATA / window["id"] / source["file"]
        if "rawSha256" in source:
            raw = shared.compressed_body(path)
            if shared.digest(raw) != source["rawSha256"]:
                raise ValueError("Archived source body hash mismatch")
            hashes[kind] = source["rawSha256"]
        elif path.exists() or source["captureStatus"] == "captured":
            raise ValueError("Uncommitted source body")
    return hashes


def scores(rows):
    result = {}
    for method in METHODS:
        values = [r["predictionsMgL"][method] for r in rows]
        if not rows or any(v is None for v in values):
            result[method] = None
            continue
        try:
            value = base.score(rows, values)
            result[method] = value if all(math.isfinite(v) for v in value.values()) else None
        except OverflowError:
            result[method] = None
    return result


def evaluate_rows(rows, oxygen, info, spec, model):
    """All model and fallback inputs are derived before, and independently of, scoring targets."""
    candidate = {"name": model["recipe"]["name"], "model": model["model"]}
    predictions = []
    ranges = model["training"]["featureRanges"]
    for row in rows:
        origin = shared.instant(row["origin"])
        history = [{"timeUTC": shared.iso(origin - timedelta(minutes=30 * i)),
                    "value": oxygen[origin - timedelta(minutes=30 * i)]["value"]} for i in range(11, -1, -1)]
        # Pass no actual, target or future record to the numerical predictor.
        inputs = {"persistence": row["persistence"], "features": row["features"][:8]}
        try:
            ridge = shared.prediction(candidate, inputs)
        except OverflowError:
            ridge = float("inf")
        finite = math.isfinite(ridge)
        rule = protocol.apply_rule(history, row["origin"], ridge) if finite else None
        flat = all(r["value"] == history[-1]["value"] for r in history)
        values = {PERSISTENCE: row["persistence"], RIDGE: ridge if finite else None,
                  FALLBACK: rule["predictionMgL"] if rule else None}
        outside = [f["feature"] for j, f in enumerate(ranges)
                   if row["features"][j] < f["min"] - shared.TOLERANCE or row["features"][j] > f["max"] + shared.TOLERANCE]
        predictions.append({k: row[k] for k in ("origin", "target", "actual", "evidence")} | {
            "features": inputs["features"], "oxygenHistory": history, "historyFlat": flat,
            "residualMultiplier": 0 if flat else 1, "predictionsMgL": values, "outsideTrainingFeatures": outside})
    diagnostics = {
        "nonfinitePredictions": {m: sum(r["predictionsMgL"][m] is None for r in predictions) for m in METHODS},
        "negativePredictions": {m: sum(r["predictionsMgL"][m] is not None and r["predictionsMgL"][m] < 0 for r in predictions) for m in METHODS}}
    all_scores = scores(predictions)
    diagnostics["nonfiniteScoreMethods"] = [m for m in METHODS if predictions and all_scores[m] is None
                                             and diagnostics["nonfinitePredictions"][m] == 0]
    days = []
    for day in sorted({r["origin"][:10] for r in predictions}):
        group = [r for r in predictions if r["origin"].startswith(day)]
        days.append({"originDayUTC": day, "pairs": len(group), "scores": scores(group)})
    subgroups = {}
    for name, flat in (("past-flat", True), ("past-changing", False)):
        group = [r for r in predictions if r["historyFlat"] is flat]
        subgroups[name] = {"pairs": len(group), "scores": scores(group)}
    accepted = len(predictions)
    coverage = info["fullExpectedGrid"]["acceptedGridFraction"]
    passed = (accepted >= spec["eligibility"]["minimumAcceptedPairsPerWindow"] and
              coverage >= spec["eligibility"]["minimumExpectedGridCoveragePerWindow"])
    return info | {"dataScreenPassed": passed, "scores": all_scores, "daily": days,
        "subgroups": subgroups, "predictionDiagnostics": diagnostics,
        "approvedTargetsBelowIllustrative5MgL": {"pairs": sum(r["actual"] < 5 for r in predictions),
            "origins": [r["origin"] for r in predictions if r["actual"] < 5], "meaning": "Descriptive only; not a local ecological threshold"},
        "observedOneHourDeclines": {"pairs": sum(r["actual"] < r["predictionsMgL"][PERSISTENCE] for r in predictions),
            "origins": [r["origin"] for r in predictions if r["actual"] < r["predictionsMgL"][PERSISTENCE]],
            "meaning": "Targets label this diagnostic after prediction; every row retains all twelve past oxygen samples and its target"},
        "featureExtrapolation": {"pairs": sum(bool(r["outsideTrainingFeatures"]) for r in predictions),
            "fraction": sum(bool(r["outsideTrainingFeatures"]) for r in predictions) / accepted if accepted else None,
            "byFeature": {f["feature"]: sum(f["feature"] in r["outsideTrainingFeatures"] for r in predictions) for f in ranges},
            "meaning": "Univariate training-range check, not a validated applicability domain or uncertainty probability"}, "rows": predictions}


def calendar_blocks(window, rows, hours):
    start = shared.instant(window["start"])
    groups = defaultdict(list)
    for row in rows:
        index = math.floor((shared.instant(row["origin"]) - start).total_seconds() / (hours * 3600))
        groups[index].append(row)
    return [{"pairs": len(group), "absoluteErrorSums": {
        m: sum(abs(r["predictionsMgL"][m] - r["actual"]) for r in group) for m in METHODS}}
        for _, group in sorted(groups.items())]


def bootstrap(windows, hours, uncertainty):
    invalid = (any(any(r["predictionsMgL"][m] is None for m in METHODS) for w in windows for r in w.get("rows", []))
               or any(w.get("predictionDiagnostics", {}).get("nonfiniteScoreMethods") for w in windows))
    groups = [] if invalid else [calendar_blocks(w["window"], w.get("rows", []), hours) for w in windows]
    counts = [len(g) for g in groups]
    invalid = invalid or any(not math.isfinite(value) for blocks in groups for block in blocks
                             for value in block["absoluteErrorSums"].values())
    result = {"blockHours": hours, "iterations": uncertainty["iterations"], "seed": uncertainty["baseSeed"] + hours,
        "nonemptyBlocksPerSeason": counts, "confidenceFraction": uncertainty["confidenceFraction"],
        "pairedSameBlockDrawsForAllMethods": True,
        "gainAgainstBaselines": {b: {"lowerGainMgL": None, "upperGainMgL": None} for b in BASELINES}}
    if invalid or len(groups) != 4 or min(counts, default=0) < uncertainty["minimumNonemptyBlocksPerSeason"]:
        return result | {"status": "invalid-prediction" if invalid else "insufficient-blocks"}
    rng, gains = random.Random(result["seed"]), {b: [] for b in BASELINES}
    for _ in range(uncertainty["iterations"]):
        seasonal = {b: [] for b in BASELINES}
        for blocks in groups:
            sampled = [blocks[rng.randrange(len(blocks))] for _ in blocks]
            n = sum(block["pairs"] for block in sampled)
            for baseline in BASELINES:
                seasonal[baseline].append(sum(block["absoluteErrorSums"][baseline] - block["absoluteErrorSums"][FALLBACK]
                                              for block in sampled) / n)
        for baseline in BASELINES:
            gains[baseline].append(sum(seasonal[baseline]) / 4)
    tail = (1 - uncertainty["confidenceFraction"]) / 2
    return result | {"status": "estimated", "gainAgainstBaselines": {b: {
        "lowerGainMgL": base.quantile(gains[b], tail), "upperGainMgL": base.quantile(gains[b], 1 - tail)} for b in BASELINES}}


def macro_scores(windows):
    means = None
    if len(windows) == 4 and all(all(w.get("scores", {}).get(m) is not None for m in METHODS) for w in windows):
        means = {m: sum(w["scores"][m]["maeMgL"] for w in windows) / 4 for m in METHODS}
    return {"seasonalMeanMAEMgL": means, "gainAgainstBaselines": {b: {
        "gainMgL": means[b] - means[FALLBACK] if means else None,
        "relativeGainPercent": 100 * (means[b] - means[FALLBACK]) / means[b] if means and means[b] else None} for b in BASELINES}}


def classify(windows, macro, bands, decision):
    tol = decision["numericalToleranceMgL"]
    if len(windows) != 4 or not all(w["dataScreenPassed"] for w in windows):
        return "insufficient-data"
    if any(any(w["predictionDiagnostics"]["nonfinitePredictions"].values()) or
           w["predictionDiagnostics"]["negativePredictions"][FALLBACK] or
           w["predictionDiagnostics"]["nonfiniteScoreMethods"] for w in windows):
        return "invalid-prediction"
    if any(b["status"] != "estimated" for b in bands):
        return "insufficient-data"
    if not any(w["subgroups"]["past-flat"]["pairs"] for w in windows):
        return "stability-rule-not-exercised"
    if any(macro["gainAgainstBaselines"][b]["gainMgL"] <= tol for b in BASELINES):
        return "no-overall-improvement"
    if any(w["scores"][FALLBACK]["maeMgL"] > w["scores"][b]["maeMgL"] + tol for w in windows for b in BASELINES):
        return "observed-seasonal-tradeoff"
    if any(band["gainAgainstBaselines"][b]["lowerGainMgL"] <= tol for band in bands for b in BASELINES):
        return "inconclusive-gain"
    return "credible-exploratory-improvement"


def evaluate(root=ROOT):
    root = Path(root).resolve()
    spec, protocol_hash, sources, model, model_hash = frozen_inputs(root)
    windows, commitments, verified = [], [], {}
    attempt_path = root / DATA / "capture-attempt.json"
    attempt = json.loads(attempt_path.read_bytes()) if attempt_path.exists() else None
    if attempt is not None:
        if (attempt.get("version") != "stability-capture-attempt-v1" or attempt.get("windows") != spec["testWindows"]
                or attempt.get("protocolHash") != protocol_hash or attempt.get("frozenModelHash") != model_hash):
            raise ValueError("Exclusive capture-attempt commitment mismatch")
        shared.instant(attempt["startedAtUTC"])
        verified[(attempt.get("frozenAtCommit"), attempt.get("implementationSnapshotHash"))] = verify_implementation(root, attempt)
    for window in spec["testWindows"]:
        path = root / DATA / window["id"] / "manifest.json"
        manifest = json.loads(path.read_bytes()) if path.exists() else None
        commitment = None
        if manifest is not None:
            if attempt is None or any(manifest.get(key) != attempt.get(key) for key in
                    ("protocolHash", "frozenModelHash", "frozenAtCommit", "implementationFiles", "implementationSnapshotHash")):
                raise ValueError("Window does not bind to the exclusive capture attempt")
            key = (manifest.get("frozenAtCommit"), manifest.get("implementationSnapshotHash"))
            if key not in verified:
                verified[key] = verify_implementation(root, manifest)
            else:
                # A cached commit must not allow a different file list through.
                if manifest.get("implementationFiles") != verified[key]["implementationFiles"]:
                    raise ValueError("Changed implementation file list in another capture")
            commitment = verified[key] | {"manifestRawSha256": shared.digest(path.read_bytes())}
            commitment["archivedBodyHashes"] = verify_archived_bodies(root, window, sources, manifest)
            commitments.append(commitment)
        rows, info = base.read_window(root / DATA, window, sources, protocol_hash, CAPTURE_VERSION, model_hash)
        if commitment:
            info["captureCommitment"] = commitment
        if "fullExpectedGrid" not in info:
            info["fullExpectedGrid"] = {"expectedOrigins": spec["eligibility"]["expectedOriginsPerWindow"],
                "acceptedExactGridPairs": 0, "acceptedGridFraction": 0,
                "missingApprovedOxygenOrigins": None, "presentOriginsWithIncompleteHistoryOrTarget": None,
                "meaning": "Capture unavailable; missing-origin decomposition cannot be observed"}
        oxygen = oxygen_history(root, window, sources, manifest) if rows else {}
        windows.append(evaluate_rows(rows, oxygen, info, spec, model))
    if len({c["frozenAtCommit"] for c in commitments}) > 1:
        raise ValueError("All fixed windows must bind to one pre-capture implementation commit")
    macro = macro_scores(windows)
    uncertainty = spec["uncertainty"]
    bands = [bootstrap(windows, hours, uncertainty) for hours in
             [uncertainty["primaryBlockHours"], *uncertainty["sensitivityBlockHours"]]]
    return {"version": "willamette-stability-evaluation-v1", "protocolHash": protocol_hash,
        "frozenModelHash": model_hash, "baseProtocolHash": spec["baseModel"]["protocolRawSha256"],
        "stationId": spec["stationId"], "horizonSeconds": 3600, "methods": list(METHODS),
        "captureAttemptRawSha256": shared.digest(attempt_path.read_bytes()) if attempt else None,
        "windows": windows, "macro": macro, "bootstrap": bands,
        "decision": classify(windows, macro, bands, spec["decision"]),
        "modelRefittedDuringEvaluation": False, "operationalModelChanged": False,
        "predictionIntervalsCalibrated": False, "practicalEnvironmentalBenefitDefined": False,
        "tenPercentIsAcceptanceGate": False,
        "limitations": [spec["scope"], uncertainty["limitations"], spec["decision"]["seasonalMeaning"],
            spec["decision"]["stableSubgroupMeaning"],
            "Finalized retrospective USGS records do not establish historical as-of-origin availability or prospective forecast skill",
            "Local file and Git hashes establish reproducibility and integrity relative to the saved archive, not independently authenticated physical truth or a trusted external timestamp",
            "One station and four selected 28-day windows do not validate pollutant attribution, interventions, ecological utility or community outcomes"],
        "mission": spec["mission"]}


def read_report(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as source:
        raw = source.read(100_000_001)
    if len(raw) > 100_000_000:
        raise ValueError("Report exceeds size limit")
    return json.loads(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["evaluate", "verify"])
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.command == "evaluate":
        if args.output is None or args.report is not None:
            parser.error("evaluate requires --output and does not accept --report")
        if args.output.exists():
            raise ValueError("Report already exists; never overwrite, use verify")
        report = evaluate(args.root)
        raw = base.encoded(report)
        with args.output.open("xb") as output:
            output.write(gzip.compress(raw, compresslevel=9, mtime=0) if args.output.suffix == ".gz" else raw)
        print(json.dumps({"decision": report["decision"], "macro": report["macro"], "bootstrap": report["bootstrap"]}, indent=2))
    else:
        if args.report is None or args.output is not None:
            parser.error("verify requires --report and does not accept --output")
        saved = read_report(args.report)
        difference = shared.compare_saved(evaluate(args.root), saved, "stability evaluation")
        print(json.dumps({"evaluationVerified": True, "maximumDifference": difference, "decision": saved["decision"]}))


if __name__ == "__main__":
    main()
