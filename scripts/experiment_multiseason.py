"""Fixed four-season one-hour research experiment. Fit, freeze, then evaluate without refitting."""
import argparse
import gzip
import json
import math
import random
import subprocess
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import audit_willamette as shared

ROOT = Path(__file__).resolve().parents[1]
DATA = Path("docs/datasets/usgs-willamette-multiseason")
EVIDENCE = Path("docs/evidence/willamette-multiseason")
KINDS = ("oxygen", "temperature", "discharge")
OLD_HASH = "0x786ea6c17bec5e55238875cf02b55a9b6bd65985b78ac1a56851b1b150a5bd29"


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def protocol(root):
    raw = (root / DATA / "protocol.json").read_bytes()
    p = json.loads(raw)
    if (p["version"] != "willamette-multiseason-one-hour-v1" or p["stationId"] != "USGS-14211720" or
            p["model"]["alpha"] != 100 or p["model"]["featureWidth"] != 8 or set(p["sources"]) != set(KINDS)):
        raise ValueError("Unexpected fixed experiment protocol")
    return p, shared.digest(raw)


def read_window(folder, window, p, protocol_hash, version, model_hash=None):
    path = folder / window["id"]
    if not (path / "manifest.json").exists():
        return [], {"window": window, "status": "unavailable", "reason": "missing fixed capture"}
    manifest = json.loads((path / "manifest.json").read_bytes())
    if (manifest["version"] != version or manifest["protocolHash"] != protocol_hash or manifest["window"] != window or
            (model_hash is not None and manifest["frozenModelHash"] != model_hash)):
        raise ValueError("Capture protocol/model commitment mismatch")
    if manifest["status"] == "unavailable":
        return [], {"window": window, "status": "unavailable", "reason": manifest["error"]}
    if manifest["status"] != "captured" or set(manifest["sources"]) != set(KINDS):
        raise ValueError("Unexpected capture manifest")
    sources, quality, hashes = {}, {}, {}
    start, end = shared.instant(window["start"]), shared.instant(window["end"])
    for kind in KINDS:
        spec, source = p["sources"][kind], manifest["sources"][kind]
        if source["file"] != f"{kind}.json.gz":
            raise ValueError("Unexpected source filename")
        url = urlparse(source["sourceUrl"])
        if (url.scheme != "https" or url.netloc != "api.waterdata.usgs.gov" or
                url.path != "/ogcapi/v1/collections/continuous/items" or url.fragment or parse_qs(url.query) != {
                    "f": ["json"], "monitoring_location_id": [p["stationId"]], "parameter_code": [spec["parameterCode"]],
                    "time": [f"{window['start']}/{window['end']}"], "limit": ["10000"]}):
            raise ValueError("Source query mismatch")
        raw = shared.compressed_body(path / source["file"])
        if shared.digest(raw) != source["rawSha256"]:
            raise ValueError("Source hash mismatch")
        records, quality[kind] = shared.read_collection(raw, p["stationId"], spec["parameterCode"],
            spec["timeSeriesId"], spec["unit"], start, end, spec["scale"])
        if quality[kind]["total"] != source["records"]:
            raise ValueError("Capture count mismatch")
        sources[kind], hashes[kind] = records, source["rawSha256"]
    rows, alignment = shared.make_pairs(sources["oxygen"], sources["temperature"], sources["discharge"], start, end)
    first, last = start + timedelta(hours=5.5), end - timedelta(hours=1)
    grid = {first + timedelta(minutes=30 * i) for i in range(int((last - first).total_seconds() / 1800) + 1)}
    # Score only the predeclared exact grid, even if an archive also contains irregular timestamps.
    rows = [r for r in rows if shared.instant(r["origin"]) in grid]
    valid = {shared.instant(r["origin"]) for r in rows}
    present = set(sources["oxygen"]) & grid
    full_grid = {"expectedOrigins": len(grid), "acceptedExactGridPairs": len(valid),
        "missingApprovedOxygenOrigins": len(grid - present), "presentOriginsWithIncompleteHistoryOrTarget": len(present - valid),
        "acceptedGridFraction": len(valid) / len(grid)}
    return rows, {"window": window, "status": "audited", "sourceHashes": hashes, "quality": quality,
        "alignment": alignment, "fullExpectedGrid": full_grid}


def training_data(root, p):
    folder = root / p["trainingFolder"]
    raw = (folder / "protocol.json").read_bytes()
    training = json.loads(raw)
    if training["sources"] != p["sources"] or training["stationId"] != p["stationId"]:
        raise ValueError("Training and test source specifications differ")
    if [w["id"] for w in training["windows"]] != p["trainingWindows"]:
        raise ValueError("Training windows changed")
    rows, windows = [], []
    for w in training["windows"]:
        pairs, info = read_window(folder, w, training, shared.digest(raw), "training-capture-v1")
        if info["status"] != "audited" or not pairs:
            raise ValueError("Fixed training window unavailable")
        rows.extend(pairs)
        windows.append(info)
    if any(shared.instant(r["target"]).year != 2024 for r in rows):
        raise ValueError("Later labels cannot enter training")
    ranges = [{"feature": name, "min": min(r["features"][j] for r in rows), "max": max(r["features"][j] for r in rows)}
              for j, name in enumerate(p["model"]["features"])]
    return rows, {"protocolHash": shared.digest(raw), "pairs": len(rows), "windows": windows, "featureRanges": ranges}


def typescript_fit(root, rows):
    work = root / "work"
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="fixed-fit-", dir=work) as temporary:
        path = Path(temporary) / "input.json"
        path.write_bytes(encoded({"version": "willamette-multiseason-fit-input-v1", "alpha": 100,
            "rows": [{k: r[k] for k in ("origin", "target", "actual", "persistence")} | {"features": r["features"][:8]} for r in rows]}))
        result = subprocess.run(["node", str(root / "node_modules/tsx/dist/cli.mjs"),
            str(root / "services/environmental-case/src/multiseason-fit-cli.ts"), str(path)],
            cwd=root, capture_output=True, text=True, check=True, timeout=60)
        return json.loads(result.stdout)


def validate_model(model):
    if set(model) != {"alpha", "mean", "scale", "coefficients", "residualIntercept"} or model["alpha"] != 100:
        raise ValueError("Changed fixed model recipe")
    for key in ("mean", "scale", "coefficients"):
        if len(model[key]) != 8 or any(type(v) not in (int, float) or not math.isfinite(v) for v in model[key]):
            raise ValueError("Malformed model vector")
    if any(s <= 0 for s in model["scale"]) or not math.isfinite(model["residualIntercept"]):
        raise ValueError("Invalid model scale/intercept")


def old_candidate(root):
    raw = (root / "docs/evidence/willamette-forecast/forecast.json").read_bytes()
    if shared.digest(raw) != OLD_HASH:
        raise ValueError("Original summer model commitment changed")
    report = json.loads(raw)
    selected = next(c for c in report["candidates"] if c["name"] == report["selected"])
    validate_model(selected["model"])
    return selected


def fit(root):
    p, ph = protocol(root)
    rows, training = training_data(root, p)
    old_candidate(root)
    model = typescript_fit(root, rows)
    validate_model(model)
    independent = shared.decimal_ridge(rows, 8, 100)
    difference = shared.compare_saved(model, independent, "independent fit")
    return {"version": "willamette-multiseason-frozen-model-v1", "createdAtUTC": shared.iso(datetime.now(timezone.utc)),
        "protocolHash": ph, "stationId": p["stationId"], "recipe": p["model"], "training": training, "model": model,
        "originalSummerReportHash": OLD_HASH,
        "solverCheck": {"primary": "existing TypeScript centered ridge, partial-pivot elimination",
            "independent": "Python Decimal 50-digit Cholesky on the same prepared source rows",
            "maximumParameterDifference": difference, "tolerance": shared.TOLERANCE,
            "meaning": "Independent arithmetic implementation, not external scientific or field validation"},
        "operationalModelChanged": False, "testValuesUsed": False}


def frozen(root):
    p, ph = protocol(root)
    raw = (root / EVIDENCE / "frozen-model.json").read_bytes()
    saved = json.loads(raw)
    if (saved["version"] != "willamette-multiseason-frozen-model-v1" or saved["protocolHash"] != ph or
            saved["stationId"] != p["stationId"] or saved["recipe"] != p["model"] or
            saved["testValuesUsed"] is not False or saved["originalSummerReportHash"] != OLD_HASH):
        raise ValueError("Frozen model/protocol mismatch")
    validate_model(saved["model"])
    _, training = training_data(root, p)  # QA only. This does not call either solver.
    shared.compare_saved(training, saved["training"], "frozen training provenance")
    return p, saved, shared.digest(raw)


def verify_fit(root):
    _, saved, _ = frozen(root)
    rebuilt = fit(root)  # Explicit audit command; evaluation never invokes it.
    rebuilt["createdAtUTC"] = saved["createdAtUTC"]
    return shared.compare_saved(rebuilt, saved, "frozen fit")


def quantile(values, fraction):
    ordered = sorted(values)
    if not ordered:
        raise ValueError("Empty quantile")
    pos = (len(ordered) - 1) * fraction
    lo, hi = math.floor(pos), math.ceil(pos)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def score(rows, values):
    return shared.metrics(rows, values) | {"p95AbsoluteErrorMgL": quantile([abs(v - r["actual"]) for r, v in zip(rows, values)], .95)}


def calendar_blocks(window, rows, hours):
    start = shared.instant(window["start"])
    grouped = defaultdict(list)
    for r in rows:
        index = math.floor((shared.instant(r["origin"]) - start).total_seconds() / (3600 * hours))
        grouped[index].append(r)
    return [(sum(abs(r["persistence"] - r["actual"]) for r in group),
             sum(abs(r["newPrediction"] - r["actual"]) for r in group), len(group)) for _, group in sorted(grouped.items())]


def bootstrap(windows, hours, spec):
    groups = [calendar_blocks(w["window"], w.get("rows", []), hours) for w in windows]
    counts = [len(g) for g in groups]
    base = {"blockHours": hours, "iterations": spec["iterations"], "seed": spec["baseSeed"] + hours,
        "nonemptyBlocksPerSeason": counts, "confidenceFraction": spec["confidenceFraction"]}
    if len(groups) != 4 or min(counts, default=0) < spec["minimumNonemptyBlocksPerSeason"]:
        return base | {"status": "insufficient-blocks", "lowerGainMgL": None, "upperGainMgL": None}
    rng = random.Random(base["seed"])
    gains = []
    for _ in range(spec["iterations"]):
        season_gains = []
        for blocks in groups:
            sampled = [blocks[rng.randrange(len(blocks))] for _ in blocks]
            season_gains.append(sum(b - m for b, m, n in sampled) / sum(n for b, m, n in sampled))
        gains.append(sum(season_gains) / 4)
    tail = (1 - spec["confidenceFraction"]) / 2
    return base | {"status": "estimated", "lowerGainMgL": quantile(gains, tail), "upperGainMgL": quantile(gains, 1 - tail)}


def classify(windows, macro, bands, decision):
    tol = decision["numericalToleranceMgL"]
    if len(windows) != 4 or not all(w["dataScreenPassed"] for w in windows) or any(b["status"] != "estimated" for b in bands):
        return "insufficient-data"
    if any(w["negativePredictions"] for w in windows):
        return "invalid-negative-prediction"
    if macro["gainMgL"] <= tol:
        return "no-overall-improvement"
    if any(w["scores"]["new"]["maeMgL"] > w["scores"]["persistence"]["maeMgL"] + tol for w in windows):
        return "observed-seasonal-tradeoff"
    if any(b["lowerGainMgL"] <= tol for b in bands):
        return "inconclusive-gain"
    return "credible-exploratory-improvement"


def evaluate(root):
    p, model, model_hash = frozen(root)
    old = old_candidate(root)
    new = {"name": p["model"]["name"], "model": model["model"]}
    windows = []
    for window in p["testWindows"]:
        rows, info = read_window(root / DATA, window, p, model["protocolHash"], "multiseason-test-capture-v1", model_hash)
        if not rows:
            windows.append(info | {"dataScreenPassed": False, "rows": [], "negativePredictions": 0})
            continue
        new_values = [shared.prediction(new, r) for r in rows]
        old_values = [shared.prediction(old, r) for r in rows]
        if any(not math.isfinite(v) for v in new_values + old_values):
            raise ValueError("Nonfinite prediction")
        outside = [[f["feature"] for j, f in enumerate(model["training"]["featureRanges"])
                    if r["features"][j] < f["min"] - shared.TOLERANCE or r["features"][j] > f["max"] + shared.TOLERANCE] for r in rows]
        predictions = [r | {"features": r["features"][:8], "newPrediction": v, "oldSummerPrediction": ov,
            "outsideTrainingFeatures": out} for r, v, ov, out in zip(rows, new_values, old_values, outside)]
        scores = {"new": score(rows, new_values), "persistence": score(rows, [r["persistence"] for r in rows]),
            "existingLinear": score(rows, [r["linear"] for r in rows]), "oldSummer": score(rows, old_values)}
        daily = []
        for day in sorted({r["origin"][:10] for r in predictions}):
            group = [r for r in predictions if r["origin"][:10] == day]
            daily.append({"originDayUTC": day, "new": score(group, [r["newPrediction"] for r in group]),
                "persistence": score(group, [r["persistence"] for r in group])})
        passed = (len(rows) >= p["evaluation"]["minimumAcceptedPairsPerTestWindow"] and
                  info["fullExpectedGrid"]["acceptedGridFraction"] >= p["evaluation"]["minimumFixedGridCoveragePerTestWindow"])
        windows.append(info | {"dataScreenPassed": passed, "scores": scores, "daily": daily,
            "negativePredictions": sum(v < 0 for v in new_values), "approvedTargetsBelowIllustrative5MgL": sum(r["actual"] < 5 for r in rows),
            "featureExtrapolation": {"pairs": sum(bool(x) for x in outside), "fraction": sum(bool(x) for x in outside) / len(rows),
                "byFeature": {name: sum(name in out for out in outside) for name in p["model"]["features"]},
                "meaning": "Univariate training-range check; not a probability or a validated applicability domain"}, "rows": predictions})
    complete = len(windows) == 4 and all("scores" in w for w in windows)
    if complete:
        means = {name: sum(w["scores"][name]["maeMgL"] for w in windows) / 4 for name in ("new", "persistence", "existingLinear", "oldSummer")}
        gain = means["persistence"] - means["new"]
        macro = {"seasonalMeanMAEMgL": means, "gainMgL": gain,
            "relativeGainPercent": 100 * gain / means["persistence"] if means["persistence"] else None}
    else:
        macro = {"seasonalMeanMAEMgL": None, "gainMgL": None, "relativeGainPercent": None}
    u = p["uncertainty"]
    bands = [bootstrap(windows, h, u) for h in [u["primaryBlockHours"], *u["sensitivityBlockHours"]]]
    outcome = classify(windows, macro, bands, p["decision"])
    return {"version": "willamette-multiseason-evaluation-v1", "protocolHash": model["protocolHash"], "frozenModelHash": model_hash,
        "originalSummerReportHash": OLD_HASH, "stationId": p["stationId"], "windows": windows, "macro": macro, "bootstrap": bands,
        "decision": outcome, "aspirationalTenPercentReached": macro["relativeGainPercent"] is not None and macro["relativeGainPercent"] >= 10,
        "tenPercentIsAcceptanceGate": False, "modelRefittedDuringEvaluation": False, "operationalModelChanged": False,
        "predictionIntervalsCalibrated": False, "practicalEnvironmentalBenefitDefined": False,
        "limitations": [p["scope"], p["uncertainty"]["limitations"], p["decision"]["seasonalMeaning"],
            "Four fortnight windows are not a complete year; finalized archive does not prove historical live availability",
            "Selected features and recipe were inherited from earlier experiments; new windows were kept separate from this fit",
            "No pollutant, causal intervention, community outcome or verified funding benefit is established"]}


def summary(report, raw_hash):
    return {k: v for k, v in report.items() if k != "windows"} | {
        "fullReportRawHash": raw_hash, "windows": [{k: v for k, v in w.items() if k != "rows"} for w in report["windows"]]}


def save_evaluation(root, result):
    folder = root / EVIDENCE
    raw = encoded(result)
    brief = summary(result, shared.digest(raw))
    for path, body in [(folder / "evaluation.json.gz", gzip.compress(raw, compresslevel=9, mtime=0)),
                       (folder / "summary.json", encoded(brief))]:
        with path.open("xb") as destination:
            destination.write(body)
    return brief


def verify_evaluation(root):
    folder = root / EVIDENCE
    raw = shared.compressed_body(folder / "evaluation.json.gz")
    saved = json.loads(raw)
    difference = shared.compare_saved(evaluate(root), saved, "full evaluation")
    difference = max(difference, shared.compare_saved(summary(saved, shared.digest(raw)), json.loads((folder / "summary.json").read_bytes()), "summary"))
    return difference


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["fit", "verify-fit", "evaluate", "verify"])
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.command == "fit":
        folder = root / EVIDENCE
        folder.mkdir(parents=True, exist_ok=True)
        if (folder / "frozen-model.json").exists():
            raise ValueError("Frozen model already exists; use verify-fit, never overwrite")
        result = fit(root)
        with (folder / "frozen-model.json").open("xb") as destination:
            destination.write(encoded(result))
        print(json.dumps({"trainingPairs": result["training"]["pairs"], "solverCheck": result["solverCheck"], "testValuesUsed": False}, indent=2))
    elif args.command == "verify-fit":
        print(json.dumps({"frozenFitVerified": True, "maximumDifference": verify_fit(root)}))
    elif args.command == "evaluate":
        if any((root / EVIDENCE / name).exists() for name in ("evaluation.json.gz", "summary.json")):
            raise ValueError("Evaluation already exists; use verify, never overwrite")
        result = save_evaluation(root, evaluate(root))
        print(json.dumps({"decision": result["decision"], "macro": result["macro"], "bootstrap": result["bootstrap"]}, indent=2))
    else:
        print(json.dumps({"evaluationVerified": True, "maximumDifference": verify_evaluation(root)}))


if __name__ == "__main__":
    main()
