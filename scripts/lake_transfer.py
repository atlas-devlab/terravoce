"""Single-attempt lake capture and offline frozen-model transfer; no fitting or tuning."""
import argparse
import gzip
import hashlib
import json
import math
import random
import re
import subprocess
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

import audit_willamette as shared
from audit_stability_compare import assert_same_receipt
from threshold_development import apply_filter

ROOT = Path(__file__).resolve().parents[1]
DATA = Path("docs/datasets/owasco-lake-transfer")
PROTOCOL = DATA / "protocol.json"
MODEL = "docs/evidence/willamette-multiseason/frozen-model.json"
DEVELOPMENT = "docs/evidence/willamette-threshold-development/evaluation.json"
MODEL_HASH = "72d7d14221c7b14c173dba59d69d2a1d36cbb27ee146378b9e046eea998762c9"
DEVELOPMENT_HASH = "d8b4d73751f457df5a34b82d2c2202c14585d02e17ae3e206f182ab8c185c5f2"
STATION = "USGS-425327076313601"
WINDOW = {"id": "owasco-july-2020", "start": "2020-07-01T00:00:00Z", "end": "2020-07-29T00:00:00Z"}
SOURCES = {
    "oxygen": {"parameterCode": "00300", "timeSeriesId": "b3904dc881b44599bc5f7eeb63da5a40", "unit": "mg/l", "scale": 1},
    "temperature": {"parameterCode": "00010", "timeSeriesId": "d584a0bd0b6f4e979451c8498c85a192", "unit": "degC", "scale": 1}}
P, R, C, F = ("persistence", "same-frozen-ridge-without-fallback",
               "same-frozen-ridge-with-fallback", "small-correction-filter")
METHODS, LIMIT, TOL = (P, R, C, F), 10_000_000, 1e-9
REQUIRED_FILES = {str(PROTOCOL).replace("\\", "/"), MODEL, DEVELOPMENT,
    "scripts/lake_transfer.py", "scripts/test_lake_transfer.py", "scripts/audit_willamette.py",
    "scripts/audit_stability_compare.py", "scripts/threshold_development.py", "scripts/test_threshold_development.py"}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


def now():
    return shared.iso(datetime.now(timezone.utc))


def frozen_inputs(root):
    raw = (root / PROTOCOL).read_bytes()
    spec = json.loads(raw)
    if (spec["stationId"] != STATION or spec["window"] != WINDOW or spec["sources"] != SOURCES or
            spec["horizonSeconds"] != 3600 or spec["development"]["selectedThresholdMgL"] != .1 or
            any(spec["eligibility"][k] != v for k, v in {"minimumAcceptedPairs": 1000, "minimumExpectedGridCoverage": .9, "expectedOrigins": 1332}.items()) or
            any(spec["uncertainty"][k] != v for k, v in {"blockHours": [48, 24, 72], "iterations": 5000, "seed": 20261015,
                "confidenceFraction": .95, "minimumNonemptyBlocks": 4}.items()) or
            spec["decision"]["numericalToleranceMgL"] != TOL or spec["decision"]["operationalPromotion"] is not False or
            spec["methods"] != list(METHODS)):
        raise ValueError("Fixed transfer protocol changed")
    for key, file, expected in (("baseModel", MODEL, MODEL_HASH), ("development", DEVELOPMENT, DEVELOPMENT_HASH)):
        if (spec[key]["file"] != file or spec[key]["rawSha256"].removeprefix("0x") != expected or
                sha((root / file).read_bytes()) != expected):
            raise ValueError("Frozen model or development result changed")
    development, model = json.loads((root / DEVELOPMENT).read_bytes()), json.loads((root / MODEL).read_bytes())
    if development["selectedThresholdMgL"] != .1 or development["status"] != "promising-in-development-only":
        raise ValueError("No eligible frozen development threshold")
    if spec["features"] != model["recipe"]["features"]:
        raise ValueError("Frozen feature order changed")
    metadata_raw = shared.compressed_body(root / spec["sourceChoice"]["metadataFile"])
    if sha(metadata_raw) != spec["sourceChoice"]["metadataRawSha256"]:
        raise ValueError("Source metadata commitment changed")
    validate_metadata(json.loads(metadata_raw))
    m = model["model"]
    if (model["recipe"]["featureWidth"] != 8 or model["recipe"]["horizonSeconds"] != 3600 or
            any(len(m[k]) != 8 or any(type(v) not in (float, int) or not math.isfinite(v) for v in m[k])
                for k in ("mean", "scale", "coefficients")) or any(v <= 0 for v in m["scale"]) or
            not math.isfinite(m["residualIntercept"])):
        raise ValueError("Invalid frozen numerical model")
    return spec, sha(raw), model


def validate_metadata(collection):
    if collection["type"] != "FeatureCollection" or any(l["rel"] == "next" for l in collection["links"]):
        raise ValueError("Incomplete source catalogue")
    for s in SOURCES.values():
        features = [f for f in collection["features"] if f["id"] == s["timeSeriesId"]]
        if len(features) != 1:
            raise ValueError("Missing or duplicated source series metadata")
        p = features[0]["properties"]
        if (p["monitoring_location_id"], p["parameter_code"], p["statistic_id"], p["unit_of_measure"],
                p["sublocation_identifier"], p["web_description"], p["primary"], p["computation_identifier"]) != (
                STATION, s["parameterCode"], "00011", s["unit"], "EXO 1", "Depth at 3 feet", "Primary", "Instantaneous"):
            raise ValueError("Catalogue identities must describe the same fixed EXO 1 deployment")


def implementation(root, revision, spec):
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", revision):
        raise ValueError("Need a full frozen Git commit")
    files = spec["implementationFiles"]
    if (files != sorted(set(files)) or not REQUIRED_FILES <= set(files) or
            any(Path(f).is_absolute() or ".." in Path(f).parts or "\\" in f for f in files)):
        raise ValueError("Incomplete implementation snapshot")
    items = []
    for file in files:
        raw = (root / file).read_bytes()
        committed = subprocess.run(["git", "show", f"{revision}:{file}"], cwd=root,
            capture_output=True, check=True, timeout=20).stdout
        if raw != committed:
            raise ValueError(f"Current bytes differ from frozen Git commit: {file}")
        items.append({"file": file, "rawSha256": sha(raw)})
    return {"frozenAtCommit": revision, "implementationFiles": items,
            "implementationSnapshotHash": sha(encoded(items)), "verifiedAgainstCurrentFilesAndGit": True}


def source_url(spec, kind):
    s, w = spec["sources"][kind], spec["window"]
    return "https://api.waterdata.usgs.gov/ogcapi/v1/collections/continuous/items?" + urlencode({
        "f": "json", "monitoring_location_id": spec["stationId"], "parameter_code": s["parameterCode"],
        "time_series_id": s["timeSeriesId"], "time": f"{w['start']}/{w['end']}", "limit": "10000"})


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise ValueError("HTTP redirects are not permitted")


def download(url):
    """One HTTPS request; no retry, redirects, alternate host, period or depth."""
    request = Request(url, headers={"User-Agent": "Virdacora-lake-research/1.0", "Accept": "application/json"})
    try:
        response = build_opener(NoRedirect).open(request, timeout=60)
    except HTTPError as error:
        response = error
    with response:
        raw = response.read(LIMIT + 1)
        return response.status, raw


def capture(root, revision):
    spec, protocol_hash, _ = frozen_inputs(root)
    frozen = implementation(root, revision, spec)
    folder = root / DATA
    if any((folder / name).exists() for name in ("manifest.json", "oxygen.json.gz", "temperature.json.gz")):
        raise ValueError("Capture outputs already exist; replacement is forbidden")
    attempt = {"version": "lake-transfer-capture-attempt-v1", "protocolSHA256": protocol_hash,
        "startedAtUTC": now(), "window": spec["window"], **frozen}
    # Exclusive creation precedes any HTTP request, including failed ones.
    with (folder / "capture-attempt.json").open("xb") as handle:
        handle.write(encoded(attempt))
    manifest = {"version": "lake-transfer-capture-v1", "attemptSHA256": sha(encoded(attempt)),
        "protocolSHA256": protocol_hash, "sources": {}, "captureEligible": True}
    for kind in SOURCES:
        source = {"file": f"{kind}.json.gz", "sourceUrl": source_url(spec, kind), "startedAtUTC": now()}
        try:
            status, raw = download(source["sourceUrl"])
            source["httpStatus"] = status
            # Save bounded HTTP error bodies too. Oversized bodies are explicitly truncated and ineligible.
            source["bodyTruncated"] = len(raw) > LIMIT
            raw = raw[:LIMIT]
            compressed = gzip.compress(raw, mtime=0)
            with (folder / source["file"]).open("xb") as handle:
                handle.write(compressed)
            source.update(rawSHA256=sha(raw), compressedSHA256=sha(compressed), rawBytes=len(raw))
            if status != 200 or source["bodyTruncated"]:
                raise ValueError("Non-200 or oversized source response")
            s = SOURCES[kind]
            _, quality = shared.read_collection(raw, STATION, s["parameterCode"], s["timeSeriesId"], s["unit"],
                shared.instant(WINDOW["start"]), shared.instant(WINDOW["end"]))
            source["records"] = quality["total"]
            source["status"] = "captured"
        except Exception as error:
            source["status"], source["error"] = "unavailable", f"{type(error).__name__}: {error}"
            manifest["captureEligible"] = False
        source["finishedAtUTC"] = now()
        manifest["sources"][kind] = source
    with (folder / "manifest.json").open("xb") as handle:
        handle.write(encoded(manifest))
    return manifest


def make_rows(oxygen, temperature, start, end, model):
    rows, missing, incomplete = [], 0, 0
    origin, last = start + timedelta(hours=5.5), end - timedelta(hours=1)
    ranges, candidate = model["training"]["featureRanges"], {"name": model["recipe"]["name"], "model": model["model"]}
    expected = int((last - origin).total_seconds() / 1800) + 1
    while origin <= last:
        target = origin + timedelta(hours=1)
        history = [origin - timedelta(minutes=30 * j) for j in range(11, -1, -1)]
        if origin not in oxygen:
            missing += 1
        elif target not in oxygen or any(t not in s for s in (oxygen, temperature) for t in history):
            incomplete += 1
        else:
            o, t = [oxygen[h]["value"] for h in history], [temperature[h]["value"] for h in history]
            clock = (origin.hour * 3600 + origin.minute * 60 + origin.second) / 86400 * 2 * math.pi
            x = [o[-1], o[-1] - o[-2], o[-1] - o[-5], o[-1] - o[0], math.sin(clock), math.cos(clock), t[-1], t[-1] - t[-5]]
            try:
                ridge = shared.prediction(candidate, {"persistence": o[-1], "features": x})
            except OverflowError:
                ridge = math.inf
            finite, flat = math.isfinite(ridge), all(v == o[-1] for v in o)
            predictions = {P: o[-1], R: ridge if finite else None,
                C: o[-1] if flat else ridge if finite else None,
                F: apply_filter(o[-1], ridge, .1) if finite else None}
            rows.append({"origin": shared.iso(origin), "target": shared.iso(target), "actual": oxygen[target]["value"],
                "features": x, "oxygenHistory": [{"timeUTC": shared.iso(h), "value": oxygen[h]["value"]} for h in history],
                "evidence": {"oxygen": [oxygen[h]["id"] for h in history], "temperature": [temperature[h]["id"] for h in history],
                    "targetOxygen": oxygen[target]["id"]}, "historyFlat": flat, "predictionsMgL": predictions,
                "outsideTrainingFeatures": [f["feature"] for j, f in enumerate(ranges)
                    if x[j] < f["min"] - TOL or x[j] > f["max"] + TOL]})
        origin += timedelta(minutes=30)
    return rows, {"expectedOrigins": expected, "acceptedExactGridPairs": len(rows),
        "missingApprovedOxygenOrigins": missing, "presentOriginsWithIncompleteHistoryOrTarget": incomplete,
        "acceptedGridFraction": len(rows) / expected}


def quantile(values, fraction):
    values = sorted(values)
    p = (len(values) - 1) * fraction
    lo, hi = math.floor(p), math.ceil(p)
    return values[lo] + (values[hi] - values[lo]) * (p - lo)


def summarize(rows):
    scores, diagnostics, comparisons = {}, {}, {}
    for m in METHODS:
        values = [r["predictionsMgL"][m] for r in rows]
        invalid = sum(v is None or not math.isfinite(v) for v in values)
        diagnostics[m] = {"nonfinitePredictions": invalid, "negativePredictions": sum(v is not None and v < 0 for v in values)}
        errors = [] if invalid else [v - r["actual"] for r, v in zip(rows, values)]
        try:
            scores[m] = None if not errors else {"pairs": len(rows), "maeMgL": math.fsum(map(abs, errors)) / len(errors),
                "rmseMgL": math.sqrt(math.fsum(e * e for e in errors) / len(errors)), "biasMgL": math.fsum(errors) / len(errors),
                "p95AbsoluteErrorMgL": quantile(list(map(abs, errors)), .95), "maxAbsoluteErrorMgL": max(map(abs, errors))}
            if scores[m] and not all(math.isfinite(v) for v in scores[m].values()):
                scores[m] = None
        except OverflowError:
            scores[m] = None
        gains = [] if invalid else [abs(r["predictionsMgL"][P] - r["actual"]) - abs(v - r["actual"]) for r, v in zip(rows, values)]
        comparisons[m] = {"wins": sum(g > TOL for g in gains), "ties": sum(abs(g) <= TOL for g in gains),
            "losses": sum(g < -TOL for g in gains)}
    return {"scores": scores, "predictionDiagnostics": diagnostics, "pairedCasesAgainstPersistence": comparisons}


def bootstrap(rows, start, hours, uncertainty):
    result = {"blockHours": hours, "iterations": uncertainty["iterations"], "seed": uncertainty["seed"] + hours,
        "confidenceFraction": uncertainty["confidenceFraction"], "pairedSameBlockDrawsForAllMethods": True}
    groups = defaultdict(list)
    for row in rows:
        groups[int((shared.instant(row["origin"]) - start).total_seconds() // (hours * 3600))].append(row)
    blocks = list(groups.values())
    result["nonemptyBlocks"] = len(blocks)
    if len(blocks) < uncertainty["minimumNonemptyBlocks"]:
        return result | {"status": "insufficient-blocks", "gainAgainstPersistence": None}
    sums = [[math.fsum(abs(r["predictionsMgL"][P] - r["actual"]) - abs(r["predictionsMgL"][m] - r["actual"])
                      for r in b) for m in METHODS] for b in blocks]
    rng, gains = random.Random(result["seed"]), {m: [] for m in METHODS}
    for _ in range(uncertainty["iterations"]):
        selected = [rng.randrange(len(blocks)) for _ in blocks]
        n = sum(len(blocks[i]) for i in selected)
        for j, method in enumerate(METHODS):
            gains[method].append(math.fsum(sums[i][j] for i in selected) / n)
    tail = (1 - uncertainty["confidenceFraction"]) / 2
    return result | {"status": "estimated", "gainAgainstPersistence": {m: {
        "lowerGainMgL": quantile(gains[m], tail), "upperGainMgL": quantile(gains[m], 1 - tail)} for m in METHODS}}


def invalid_prediction(summary):
    # Negative finite comparator predictions remain visible but cannot disqualify a valid filter.
    return (any(d["nonfinitePredictions"] for d in summary["predictionDiagnostics"].values()) or
            summary["predictionDiagnostics"][F]["negativePredictions"] > 0 or
            any(v is None for v in summary["scores"].values()))


def evaluate(root):
    spec, protocol_hash, model = frozen_inputs(root)
    folder = root / DATA
    attempt_raw, manifest_raw = (folder / "capture-attempt.json").read_bytes(), (folder / "manifest.json").read_bytes()
    attempt, manifest = json.loads(attempt_raw), json.loads(manifest_raw)
    frozen = implementation(root, attempt["frozenAtCommit"], spec)
    if (attempt["version"] != "lake-transfer-capture-attempt-v1" or attempt["protocolSHA256"] != protocol_hash or
            attempt["window"] != spec["window"] or any(attempt[k] != v for k, v in frozen.items()) or
            manifest["version"] != "lake-transfer-capture-v1" or manifest["protocolSHA256"] != protocol_hash or
            manifest["attemptSHA256"] != sha(attempt_raw) or set(manifest["sources"]) != set(SOURCES)):
        raise ValueError("Capture attempt/manifest commitment mismatch")
    started = shared.instant(attempt["startedAtUTC"])
    sources, quality = {}, {}
    for kind, source in manifest["sources"].items():
        if (source["sourceUrl"] != source_url(spec, kind) or source["file"] != f"{kind}.json.gz" or
                not started <= shared.instant(source["startedAtUTC"]) <= shared.instant(source["finishedAtUTC"])):
            raise ValueError("Capture URL, identity, file or timestamps changed")
        if "rawSHA256" in source:
            compressed = (folder / source["file"]).read_bytes()
            raw = shared.compressed_body(folder / source["file"])
            if sha(compressed) != source["compressedSHA256"] or sha(raw) != source["rawSHA256"] or len(raw) != source["rawBytes"]:
                raise ValueError("Archived source body changed")
        elif (folder / source["file"]).exists():
            raise ValueError("Uncommitted source body")
        if source["status"] != "captured":
            if source["status"] != "unavailable":
                raise ValueError("Unknown archived source status")
            continue
        if source["httpStatus"] != 200 or source["bodyTruncated"] or "rawSHA256" not in source:
            raise ValueError("Invalid successful HTTP capture")
        s = SOURCES[kind]
        sources[kind], quality[kind] = shared.read_collection(raw, STATION, s["parameterCode"], s["timeSeriesId"], s["unit"],
            shared.instant(WINDOW["start"]), shared.instant(WINDOW["end"]))
        if quality[kind]["total"] != source["records"]:
            raise ValueError("Source record count changed")
    receipt = {"version": "lake-transfer-evaluation-v1", "protocolSHA256": protocol_hash,
        "implementationCommitment": frozen, "manifestSHA256": sha(manifest_raw), "stationId": STATION,
        "window": WINDOW, "horizonSeconds": 3600, "thresholdMgL": .1, "primaryMetric": "MAE in mg/L",
        "newFit": False, "thresholdTunedOnLake": False, "operationalPromotion": False,
        "scope": "Exploratory retrospective transfer to one fixed lake depth and summer window; finalized archives, not a live forecast",
        "sourceQuality": quality, "sourceHashes": {k: s.get("rawSHA256") for k, s in manifest["sources"].items()}}
    if manifest["captureEligible"] is not (len(sources) == len(SOURCES)):
        raise ValueError("Capture eligibility and source states disagree")
    if not manifest["captureEligible"]:
        return receipt | {"decision": "insufficient-data", "rows": [], "reason": "Original capture failed; no replacement permitted"}
    rows, grid = make_rows(sources["oxygen"], sources["temperature"], shared.instant(WINDOW["start"]), shared.instant(WINDOW["end"]), model)
    summary = summarize(rows)
    invalid = invalid_prediction(summary)
    eligible = len(rows) >= 1000 and grid["acceptedGridFraction"] >= .9 and grid["expectedOrigins"] == 1332
    bands = [] if invalid else [bootstrap(rows, shared.instant(WINDOW["start"]), h, spec["uncertainty"]) for h in spec["uncertainty"]["blockHours"]]
    gain = None if invalid else summary["scores"][P]["maeMgL"] - summary["scores"][F]["maeMgL"]
    decision = ("insufficient-data" if not eligible else "invalid-prediction" if invalid else
        "no-overall-improvement" if gain <= TOL else "inconclusive-gain" if any(b["status"] != "estimated" or
            b["gainAgainstPersistence"][F]["lowerGainMgL"] <= TOL for b in bands) else "credible-exploratory-single-window-improvement")
    return receipt | summary | {"fullExpectedGrid": grid, "dataScreenPassed": eligible, "gainOverPersistenceMgL": gain,
        "bootstrap": bands, "decision": decision, "featureExtrapolation": {"pairs": sum(bool(r["outsideTrainingFeatures"]) for r in rows),
            "fraction": sum(bool(r["outsideTrainingFeatures"]) for r in rows) / len(rows) if rows else None,
            "byFeature": {f["feature"]: sum(f["feature"] in r["outsideTrainingFeatures"] for r in rows)
                          for f in model["training"]["featureRanges"]},
            "meaning": "Univariate training ranges only; not a validated confidence or applicability domain"},
        "daily": [{"originDayUTC": day, **summarize([r for r in rows if r["origin"].startswith(day)])}
                  for day in sorted({r["origin"][:10] for r in rows})],
        "approvedTargetsBelowIllustrative5MgL": {"pairs": sum(r["actual"] < 5 for r in rows),
            "meaning": "Descriptive only; 5 mg/L is not an established local ecological threshold"}, "rows": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preflight", "capture", "evaluate", "verify"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--frozen-at-commit")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.command in ("evaluate", "verify") and args.report is None:
        parser.error("evaluate and verify require --report for saved, reviewable evidence")
    if args.command in ("preflight", "capture") and not args.frozen_at_commit:
        parser.error("Need --frozen-at-commit before capture")
    if args.command == "preflight":
        spec, digest, _ = frozen_inputs(args.root)
        result = {"protocolSHA256": digest, "captureStarted": (args.root / DATA / "capture-attempt.json").exists(),
            **implementation(args.root, args.frozen_at_commit, spec)}
    elif args.command == "capture":
        result = capture(args.root, args.frozen_at_commit)
    else:
        result = evaluate(args.root)
        if args.report:
            if args.command == "verify":
                assert_same_receipt(result, json.loads(args.report.read_bytes()), "lake-transfer")
            else:
                args.report.parent.mkdir(parents=True, exist_ok=True)
                with args.report.open("xb") as handle:
                    handle.write(encoded(result))
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
