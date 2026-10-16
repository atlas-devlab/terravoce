"""One committed August capture and offline validation with unchanged July kernels."""
import argparse
import gzip
import json
import math
import re
import subprocess
from pathlib import Path

import lake_transfer as lake

ROOT = Path(__file__).resolve().parents[1]
DATA = Path("docs/datasets/owasco-temporal-validation")
PROTOCOL = DATA / "protocol.json"
PROTOCOL_SHA256 = "b9746290e6ffd702440c257b62a72cd49d0161ffbf73fe887a668f508397439d"
WINDOW = {"id": "owasco-august-2020", "start": "2020-08-01T00:00:00Z", "end": "2020-08-29T00:00:00Z"}
MODEL, MODEL_HASH = lake.MODEL, lake.MODEL_HASH
DEVELOPMENT, DEVELOPMENT_HASH = lake.DEVELOPMENT, lake.DEVELOPMENT_HASH
PREVIOUS = "docs/evidence/owasco-lake-transfer/evaluation.json"
PREVIOUS_HASH = "7bd27ec609a7c4f471385498b61fff7b9d74546de13711559e84fcb16536ff85"
STATION, SOURCES = lake.STATION, lake.SOURCES
P, R, C, F, METHODS, TOL, LIMIT = lake.P, lake.R, lake.C, lake.F, lake.METHODS, lake.TOL, lake.LIMIT
FEATURES = ["oxygenNow", "oxygenDelta30m", "oxygenDelta2h", "oxygenDelta5h30m",
            "clockSinUTC", "clockCosUTC", "temperatureNow", "temperatureDelta2h"]
# The original fourteen-file commitment is preserved independently of the new commit.
HISTORICAL_HASHES = {
    "docs/datasets/owasco-lake-transfer/continuous-queryables.json.gz": "9e0b99dea92e13b5d2ef912378d3ae4bd8e5ff7e949760324ec4fa36304c996d",
    "docs/datasets/owasco-lake-transfer/protocol.json": "a97f7eae9c9ad4c0f7e2e46848e2cc5df15c1cf8b5b50473c2a0a7f3e866c02b",
    "docs/datasets/owasco-lake-transfer/time-series-metadata.json.gz": "2f1f154b74b5ab40ba23ec021b1d98fda0b25ab95306f5497cb57a6290f15a12",
    "docs/datasets/willamette-threshold-development/protocol.json": "d68381c42e992e4328b6bb454642a51878bedcf4b1d1748aafdc7576bb335d9e",
    MODEL: MODEL_HASH,
    DEVELOPMENT: DEVELOPMENT_HASH,
    "scripts/audit_stability_compare.py": "b08e369bfb7e75ecd931457387e0f2e8f41696b256e68c0cf191cdac3aa9d64a",
    "scripts/audit_willamette.py": "9a8de29078d7e4c75260b7f9fea1b7220193f64a97b0b00384ca680ea00f8d12",
    "scripts/evaluate_threshold_development.py": "e0065e82d5eb7e2acbe3680c903a2c37370188b8133d2020877a0907764c73f7",
    "scripts/experiment_multiseason.py": "00999b36a5c5fcb5c6a51ca9d00ee076f6bd9b1c2fb47245a402ccf9c5d4dfea",
    "scripts/lake_transfer.py": "e3579938b0d1c4991fcfc69506e871323f8e6d1c3a52089caa48bb0e4790079c",
    "scripts/test_lake_transfer.py": "ad44e2603230bc28fd06aeb3689eae974a7e8e8c835524ab1b5a4d0624e8018a",
    "scripts/test_threshold_development.py": "3c904d228a51b2ff90ca4705d4d969d62c6d50819228c0c076d41433e5d99099",
    "scripts/threshold_development.py": "153d614d06306add9fe55cc8b5d435edac15557b4ba493035ec083cebe7a5caf",
}
REQUIRED_FILES = set(HISTORICAL_HASHES) | {
    PROTOCOL.as_posix(), "scripts/owasco_temporal_validation.py", "scripts/test_owasco_temporal_validation.py"}
ATTEMPT_VERSION = "owasco-temporal-capture-attempt-v1"
MANIFEST_VERSION = "owasco-temporal-capture-v1"
EVALUATION_VERSION = "owasco-temporal-evaluation-v1"
sha, encoded, now, download = lake.sha, lake.encoded, lake.now, lake.download


def frozen_inputs(root):
    raw = (root / PROTOCOL).read_bytes()
    spec = json.loads(raw)
    if sha(raw) != PROTOCOL_SHA256:
        raise ValueError("Fixed August protocol bytes changed")
    if (spec["version"] != "owasco-frozen-temporal-v1" or spec["stationId"] != STATION or
            spec["window"] != WINDOW or spec["sources"] != SOURCES or spec["horizonSeconds"] != 3600 or
            spec["features"] != FEATURES or spec["methods"] != list(METHODS) or
            spec["primaryMetric"] != "MAE in mg/L on the identical accepted origin-target cohort" or
            any(spec["eligibility"][k] != v for k, v in {
                "minimumAcceptedPairs": 1000, "minimumExpectedGridCoverage": .9, "expectedOrigins": 1332}.items()) or
            any(spec["uncertainty"][k] != v for k, v in {"blockHours": [48, 24, 72], "iterations": 5000,
                "seed": 20261015, "confidenceFraction": .95, "minimumNonemptyBlocks": 4}.items()) or
            spec["decision"]["numericalToleranceMgL"] != TOL or spec["decision"]["primaryBaseline"] != P or
            spec["decision"]["operationalPromotion"] is not False or
            spec["decision"]["practicalEnvironmentalBenefitDefined"] is not False or
            any(spec["capture"][k] != v for k, v in {"maximumBodyBytes": LIMIT,
                "exclusiveAttemptBeforeHTTP": True, "automaticRetries": False, "redirects": False,
                "replaceFailedWindow": False, "officialHost": "api.waterdata.usgs.gov",
                "endpoint": "https://api.waterdata.usgs.gov/ogcapi/v1/collections/continuous/items",
                "explicitTimeSeriesFilter": True}.items())):
        raise ValueError("Fixed August transfer protocol changed")
    if spec["implementationFiles"] != sorted(REQUIRED_FILES):
        raise ValueError("Incomplete August implementation snapshot")
    for file, expected in HISTORICAL_HASHES.items():
        if sha((root / file).read_bytes()) != expected:
            raise ValueError(f"Historical frozen file changed: {file}")
    for key, file, expected in (("baseModel", MODEL, MODEL_HASH), ("development", DEVELOPMENT, DEVELOPMENT_HASH),
                                ("previousPrimaryEvaluation", PREVIOUS, PREVIOUS_HASH)):
        if (spec[key]["file"] != file or spec[key]["rawSha256"] != expected or
                sha((root / file).read_bytes()) != expected):
            raise ValueError(f"Frozen input changed: {key}")
    development = json.loads((root / DEVELOPMENT).read_bytes())
    if (spec["development"]["selectedThresholdMgL"] != .1 or
            development["selectedThresholdMgL"] != .1 or development["status"] != "promising-in-development-only"):
        raise ValueError("No eligible frozen development threshold")
    metadata_file = "docs/datasets/owasco-lake-transfer/time-series-metadata.json.gz"
    if spec["sourceChoice"]["metadataFile"] != metadata_file:
        raise ValueError("Fixed source metadata path changed")
    metadata_raw = lake.shared.compressed_body(root / metadata_file)
    if sha(metadata_raw) != spec["sourceChoice"]["metadataRawSha256"]:
        raise ValueError("Source metadata commitment changed")
    lake.validate_metadata(json.loads(metadata_raw))
    model = json.loads((root / MODEL).read_bytes())
    m, recipe = model["model"], model["recipe"]
    if (recipe["featureWidth"] != 8 or recipe["horizonSeconds"] != 3600 or recipe["features"] != FEATURES or
            recipe["alpha"] != 100 or m["alpha"] != 100 or
            any(len(m[k]) != 8 or any(type(v) not in (float, int) or not math.isfinite(v) for v in m[k])
                for k in ("mean", "scale", "coefficients")) or any(v <= 0 for v in m["scale"]) or
            type(m["residualIntercept"]) not in (float, int) or not math.isfinite(m["residualIntercept"])):
        raise ValueError("Invalid frozen numerical model")
    return spec, sha(raw), model


def implementation(root, revision, spec):
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", revision):
        raise ValueError("Need a full frozen Git commit")
    files = spec["implementationFiles"]
    if files != sorted(REQUIRED_FILES):
        raise ValueError("Incomplete August implementation snapshot")
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


def preflight(root, revision):
    spec, digest, _ = frozen_inputs(root)
    return {"protocolSHA256": digest, "window": spec["window"],
            "captureStarted": (root / DATA / "capture-attempt.json").exists(),
            **implementation(root, revision, spec)}


def capture(root, revision):
    spec, protocol_hash, _ = frozen_inputs(root)
    frozen = implementation(root, revision, spec)
    folder = root / DATA
    if any((folder / name).exists() for name in
           ("capture-attempt.json", "manifest.json", "oxygen.json.gz", "temperature.json.gz")):
        raise ValueError("Capture outputs already exist; replacement is forbidden")
    attempt = {"version": ATTEMPT_VERSION, "protocolSHA256": protocol_hash,
               "startedAtUTC": now(), "window": spec["window"], **frozen}
    with (folder / "capture-attempt.json").open("xb") as handle:
        handle.write(encoded(attempt))
    manifest = {"version": MANIFEST_VERSION, "attemptSHA256": sha(encoded(attempt)),
                "protocolSHA256": protocol_hash, "sources": {}, "captureEligible": True}
    start, end = (lake.shared.instant(spec["window"][key]) for key in ("start", "end"))
    for kind, source_spec in SOURCES.items():
        source = {"file": f"{kind}.json.gz", "sourceUrl": lake.source_url(spec, kind), "startedAtUTC": now()}
        try:
            status, raw = download(source["sourceUrl"])
            source["httpStatus"], source["bodyTruncated"] = status, len(raw) > LIMIT
            raw = raw[:LIMIT]
            compressed = gzip.compress(raw, mtime=0)
            with (folder / source["file"]).open("xb") as handle:
                handle.write(compressed)
            source.update(rawSHA256=sha(raw), compressedSHA256=sha(compressed), rawBytes=len(raw))
            if status != 200 or source["bodyTruncated"]:
                raise ValueError("Non-200 or oversized source response")
            _, quality = lake.shared.read_collection(raw, STATION, source_spec["parameterCode"],
                source_spec["timeSeriesId"], source_spec["unit"], start, end)
            source["records"], source["status"] = quality["total"], "captured"
        except Exception as error:
            source["status"], source["error"] = "unavailable", f"{type(error).__name__}: {error}"
            manifest["captureEligible"] = False
        source["finishedAtUTC"] = now()
        manifest["sources"][kind] = source
    manifest["finishedAtUTC"] = now()
    with (folder / "manifest.json").open("xb") as handle:
        handle.write(encoded(manifest))
    return manifest


def archived_sources(root, spec, protocol_hash):
    folder = root / DATA
    attempt_raw = (folder / "capture-attempt.json").read_bytes()
    manifest_raw = (folder / "manifest.json").read_bytes()
    attempt, manifest = json.loads(attempt_raw), json.loads(manifest_raw)
    frozen = implementation(root, attempt["frozenAtCommit"], spec)
    if (attempt["version"] != ATTEMPT_VERSION or attempt["protocolSHA256"] != protocol_hash or
            attempt["window"] != spec["window"] or any(attempt[k] != v for k, v in frozen.items()) or
            manifest["version"] != MANIFEST_VERSION or manifest["protocolSHA256"] != protocol_hash or
            manifest["attemptSHA256"] != sha(attempt_raw) or set(manifest["sources"]) != set(SOURCES) or
            type(manifest["captureEligible"]) is not bool):
        raise ValueError("Capture attempt/manifest commitment mismatch")
    previous_end = lake.shared.instant(attempt["startedAtUTC"])
    manifest_end = lake.shared.instant(manifest["finishedAtUTC"])
    start, end = (lake.shared.instant(spec["window"][key]) for key in ("start", "end"))
    sources, quality = {}, {}
    for kind, source_spec in SOURCES.items():
        source = manifest["sources"][kind]
        source_start, source_end = (lake.shared.instant(source[key]) for key in ("startedAtUTC", "finishedAtUTC"))
        if (source["sourceUrl"] != lake.source_url(spec, kind) or source["file"] != f"{kind}.json.gz" or
                not previous_end <= source_start <= source_end <= manifest_end):
            raise ValueError("Capture URL, identity, file or timestamps changed")
        previous_end = source_end
        body_fields = {"rawSHA256", "compressedSHA256", "rawBytes"}
        present = body_fields.intersection(source)
        if present and present != body_fields:
            raise ValueError("Incomplete archived body commitment")
        if present:
            compressed = (folder / source["file"]).read_bytes()
            raw = lake.shared.compressed_body(folder / source["file"])
            if (type(source["rawBytes"]) is not int or not 0 <= source["rawBytes"] <= LIMIT or
                    sha(compressed) != source["compressedSHA256"] or sha(raw) != source["rawSHA256"] or
                    len(raw) != source["rawBytes"]):
                raise ValueError("Archived source body changed")
        elif (folder / source["file"]).exists():
            raise ValueError("Uncommitted source body")
        if source["status"] == "unavailable":
            if not isinstance(source.get("error"), str) or not source["error"]:
                raise ValueError("Missing archived source failure")
            continue
        if source["status"] != "captured":
            raise ValueError("Unknown archived source status")
        if (not present or source.get("httpStatus") != 200 or source.get("bodyTruncated") is not False):
            raise ValueError("Invalid successful HTTP capture")
        sources[kind], quality[kind] = lake.shared.read_collection(raw, STATION, source_spec["parameterCode"],
            source_spec["timeSeriesId"], source_spec["unit"], start, end)
        if type(source["records"]) is not int or quality[kind]["total"] != source["records"]:
            raise ValueError("Source record count changed")
    if manifest["captureEligible"] is not (len(sources) == len(SOURCES)):
        raise ValueError("Capture eligibility and source states disagree")
    return attempt, manifest, sha(manifest_raw), frozen, sources, quality


def check_recomposition(rows, summary, daily):
    if lake.invalid_prediction(summary):
        return {"status": "not-applicable-invalid-prediction"}
    n = len(rows)
    for method in METHODS:
        score = summary["scores"][method]
        if score["pairs"] != n or sum(day["scores"][method]["pairs"] for day in daily) != n:
            raise ValueError("Recomposition cohort differs")
        recomposed = math.fsum(day["scores"][method]["maeMgL"] * day["scores"][method]["pairs"]
                              for day in daily) / n
        paired = math.fsum(abs(row["predictionsMgL"][P] - row["actual"]) -
                           abs(row["predictionsMgL"][method] - row["actual"]) for row in rows) / n
        if (abs(recomposed - score["maeMgL"]) > TOL or
                abs(paired - (summary["scores"][P]["maeMgL"] - score["maeMgL"])) > TOL):
            raise ValueError("MAE or paired-gain recomposition failed")
    return {"status": "passed", "cohortPairs": n, "dailyMAEAndPairedGain": True}


def evaluate(root):
    spec, protocol_hash, model = frozen_inputs(root)
    _, manifest, manifest_hash, frozen, sources, quality = archived_sources(root, spec, protocol_hash)
    receipt = {"version": EVALUATION_VERSION, "protocolSHA256": protocol_hash,
        "implementationCommitment": frozen, "manifestSHA256": manifest_hash, "stationId": STATION,
        "window": spec["window"], "horizonSeconds": 3600, "thresholdMgL": .1, "primaryMetric": "MAE in mg/L",
        "newFit": False, "thresholdTunedOnLake": False, "operationalPromotion": False,
        "scope": "Exploratory retrospective temporal holdout at one lake depth; finalized archives, not a live forecast",
        "sourceQuality": quality, "sourceHashes": {k: s.get("rawSHA256") for k, s in manifest["sources"].items()}}
    if not manifest["captureEligible"]:
        return receipt | {"decision": "insufficient-data", "rows": [],
                          "reason": "Original capture failed; no replacement permitted"}
    start, end = (lake.shared.instant(spec["window"][key]) for key in ("start", "end"))
    rows, grid = lake.make_rows(sources["oxygen"], sources["temperature"], start, end, model)
    summary = lake.summarize(rows)
    invalid = lake.invalid_prediction(summary)
    eligible = (len(rows) >= spec["eligibility"]["minimumAcceptedPairs"] and
                grid["acceptedGridFraction"] >= spec["eligibility"]["minimumExpectedGridCoverage"] and
                grid["expectedOrigins"] == spec["eligibility"]["expectedOrigins"])
    bands = [] if invalid else [lake.bootstrap(rows, start, h, spec["uncertainty"])
                               for h in spec["uncertainty"]["blockHours"]]
    gain = None if invalid else summary["scores"][P]["maeMgL"] - summary["scores"][F]["maeMgL"]
    decision = ("insufficient-data" if not eligible else "invalid-prediction" if invalid else
        "no-overall-improvement" if gain <= TOL else "inconclusive-gain" if any(b["status"] != "estimated" or
        b["gainAgainstPersistence"][F]["lowerGainMgL"] <= TOL for b in bands) else
        "credible-exploratory-single-window-improvement")
    daily = [{"originDayUTC": day, **lake.summarize([r for r in rows if r["origin"].startswith(day)])}
             for day in sorted({r["origin"][:10] for r in rows})]
    recomposition = check_recomposition(rows, summary, daily)
    return receipt | summary | {"fullExpectedGrid": grid, "dataScreenPassed": eligible,
        "gainOverPersistenceMgL": gain, "bootstrap": bands, "decision": decision, "daily": daily,
        "recompositionChecks": recomposition,
        "featureExtrapolation": {"pairs": sum(bool(r["outsideTrainingFeatures"]) for r in rows),
            "fraction": sum(bool(r["outsideTrainingFeatures"]) for r in rows) / len(rows) if rows else None,
            "byFeature": {f["feature"]: sum(f["feature"] in r["outsideTrainingFeatures"] for r in rows)
                          for f in model["training"]["featureRanges"]},
            "meaning": "Univariate training ranges only; not a validated confidence or applicability domain"},
        "approvedTargetsBelowIllustrative5MgL": {"pairs": sum(r["actual"] < 5 for r in rows),
            "meaning": "Descriptive only; 5 mg/L is not an established local ecological threshold"}, "rows": rows}


def verify(root, report):
    result = evaluate(root)
    lake.assert_same_receipt(result, json.loads(report.read_bytes()), "owasco-temporal-validation")
    return result


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
        result = preflight(args.root, args.frozen_at_commit)
    elif args.command == "capture":
        result = capture(args.root, args.frozen_at_commit)
    elif args.command == "verify":
        result = verify(args.root, args.report)
    else:
        result = evaluate(args.root)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("xb") as handle:
            handle.write(encoded(result))
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
