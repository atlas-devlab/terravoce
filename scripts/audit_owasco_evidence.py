"""Post-hoc independent calculation from the same Owasco observations, not new validation.

Python stdlib only; no project imports, fitting, parameter search or network access.
This audit is independent code verification, not independent environmental observation
or a preregistered experiment. The frozen capture/evaluation implementation is untouched.
"""
import argparse
import gzip
import hashlib
import json
import math
import random
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = Path("docs/datasets/owasco-lake-transfer")
REPORT = Path("docs/evidence/owasco-lake-transfer/evaluation.json")
REPORT_SHA = "7bd27ec609a7c4f471385498b61fff7b9d74546de13711559e84fcb16536ff85"
FROZEN_COMMIT = "c06f1a79f073f71764aef501e9ae0f298a775377"
TOL = 1e-9


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(condition, label):
    if not condition:
        raise ValueError(f"Independent audit failed: {label}")


def instant(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(result.utcoffset() is not None, "explicit timezone")
    return result.astimezone(timezone.utc)


def stamp(value):
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def quantile(values, fraction):
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower, upper = math.floor(position), math.ceil(position)
    return ordered[lower] * (1 - (position - lower)) + ordered[upper] * (position - lower)


def audit(root=ROOT):
    root, largest = Path(root).resolve(), 0.0

    def close(actual, expected, label):
        nonlocal largest
        require(math.isfinite(actual) and math.isfinite(expected), label + " finite")
        difference = abs(actual - expected)
        require(difference <= TOL, label)
        largest = max(largest, difference)

    data = root / DATA
    report_raw = (root / REPORT).read_bytes()
    require(sha(report_raw) == REPORT_SHA, "pinned completed report")
    report = json.loads(report_raw)
    manifest_raw, attempt_raw = (data / "manifest.json").read_bytes(), (data / "capture-attempt.json").read_bytes()
    manifest, attempt = json.loads(manifest_raw), json.loads(attempt_raw)
    protocol_raw = (data / "protocol.json").read_bytes()
    protocol = json.loads(protocol_raw)
    require(sha(manifest_raw) == report["manifestSHA256"] and sha(attempt_raw) == manifest["attemptSHA256"], "capture chain")
    require(sha(protocol_raw) == report["protocolSHA256"] == manifest["protocolSHA256"] == attempt["protocolSHA256"], "protocol chain")
    require(attempt["frozenAtCommit"] == FROZEN_COMMIT, "pre-capture commit")
    require([f["file"] for f in attempt["implementationFiles"]] == protocol["implementationFiles"], "complete frozen inventory")
    for item in attempt["implementationFiles"]:
        raw = (root / item["file"]).read_bytes()
        committed = subprocess.run(["git", "show", FROZEN_COMMIT + ":" + item["file"]], cwd=root,
                                   capture_output=True, check=True, timeout=20).stdout
        require(raw == committed and sha(raw) == item["rawSha256"], "current and Git bytes: " + item["file"])
    for key in ("frozenAtCommit", "implementationFiles", "implementationSnapshotHash"):
        require(report["implementationCommitment"][key] == attempt[key], "report implementation chain")
    model_raw, dev_raw = [(root / protocol[key]["file"]).read_bytes() for key in ("baseModel", "development")]
    require(sha(model_raw) == protocol["baseModel"]["rawSha256"], "frozen model")
    require(sha(dev_raw) == protocol["development"]["rawSha256"], "Willamette-only threshold selection")
    model, development = json.loads(model_raw), json.loads(dev_raw)
    require(development["selectedThresholdMgL"] == protocol["development"]["selectedThresholdMgL"] == report["thresholdMgL"] == .1,
            "fixed threshold")
    require(development["status"] == "promising-in-development-only", "development status")
    metadata_raw = gzip.decompress((root / protocol["sourceChoice"]["metadataFile"]).read_bytes())
    require(sha(metadata_raw) == protocol["sourceChoice"]["metadataRawSha256"], "catalogue hash")
    metadata = json.loads(metadata_raw)
    start, end = instant(protocol["window"]["start"]), instant(protocol["window"]["end"])
    sources, rawcounts, cadence = {}, {}, {}
    for kind, spec in protocol["sources"].items():
        meta = [f["properties"] for f in metadata["features"] if f["id"] == spec["timeSeriesId"]]
        require(len(meta) == 1, "one catalogue series")
        m = meta[0]
        require((m["monitoring_location_id"], m["parameter_code"], m["statistic_id"], m["unit_of_measure"], m["sublocation_identifier"],
                 m["web_description"]) == (protocol["stationId"], spec["parameterCode"], "00011", spec["unit"], "EXO 1", "Depth at 3 feet"), "same deployment")
        source = manifest["sources"][kind]
        compressed = (data / source["file"]).read_bytes()
        require(sha(compressed) == source["compressedSHA256"], "compressed source")
        raw = gzip.decompress(compressed)
        require(sha(raw) == source["rawSHA256"] == report["sourceHashes"][kind] and len(raw) == source["rawBytes"], "raw source")
        require(source["httpStatus"] == 200 and source["status"] == "captured" and not source["bodyTruncated"], "successful HTTP capture")
        url = urlparse(source["sourceUrl"])
        require((url.scheme, url.netloc, url.path) == ("https", "api.waterdata.usgs.gov", "/ogcapi/v1/collections/continuous/items") and not url.fragment, "official endpoint")
        require(parse_qs(url.query) == {"f": ["json"], "monitoring_location_id": [protocol["stationId"]], "parameter_code": [spec["parameterCode"]],
            "time_series_id": [spec["timeSeriesId"]], "time": [protocol["window"]["start"] + "/" + protocol["window"]["end"]], "limit": ["10000"]}, "source query")
        collection = json.loads(raw)
        require(collection["type"] == "FeatureCollection" and not any(x["rel"] == "next" for x in collection["links"]), "complete collection")
        require(collection.get("numberReturned", len(collection["features"])) == len(collection["features"]) < 10000, "collection count")
        records, identities = {}, set()
        for feature in collection["features"]:
            prop = feature["properties"]
            time, value = instant(prop["time"]), float(prop["value"])
            require((prop["monitoring_location_id"], prop["parameter_code"], prop["time_series_id"], prop["statistic_id"], prop["unit_of_measure"]) ==
                (protocol["stationId"], spec["parameterCode"], spec["timeSeriesId"], "00011", spec["unit"]), "measurement identity")
            require(start <= time <= end and time not in records and feature["id"] not in identities, "bounds and uniqueness")
            require(prop["approval_status"] == "Approved" and prop["qualifier"] in (None, "") and math.isfinite(value) and
                    (kind != "oxygen" or value >= 0), "approved unqualified finite measurement")
            identities.add(feature["id"])
            records[time] = {"value": value, "id": feature["id"]}
        require(len(records) == source["records"] == report["sourceQuality"][kind]["accepted"], "accepted source count")
        sources[kind], rawcounts[kind] = records, len(records)
        times = sorted(records)
        cadence[kind] = {"minuteRemaindersModulo15": dict(Counter(t.minute % 15 for t in times)),
            "non900sIntervals": sum((b - a).total_seconds() != 900 for a, b in zip(times, times[1:]))}
    persistence, ridge_name, fallback, filtered = protocol["methods"]
    rows, missing, incomplete, expected = [], 0, 0, 0
    params, origin = model["model"], start + timedelta(minutes=330)
    while origin <= end - timedelta(hours=1):
        expected += 1
        target, history = origin + timedelta(hours=1), [origin - timedelta(minutes=30 * i) for i in range(11, -1, -1)]
        if origin not in sources["oxygen"]:
            missing += 1
        elif target not in sources["oxygen"] or any(t not in sources[k] for t in history for k in sources):
            incomplete += 1
        else:
            oxygen, temperature = [[sources[k][t]["value"] for t in history] for k in ("oxygen", "temperature")]
            angle = 2 * math.pi * (origin.hour * 3600 + origin.minute * 60 + origin.second) / 86400
            features = [oxygen[-1], oxygen[-1] - oxygen[-2], oxygen[-1] - oxygen[-5], oxygen[-1] - oxygen[0], math.sin(angle), math.cos(angle), temperature[-1], temperature[-1] - temperature[-5]]
            terms = [(v - m) / s * w for v, m, s, w in zip(features, params["mean"], params["scale"], params["coefficients"])]
            ridge, flat = oxygen[-1] + math.fsum([params["residualIntercept"]] + terms), len(set(oxygen)) == 1
            predictions = {persistence: oxygen[-1], ridge_name: ridge, fallback: oxygen[-1] if flat else ridge,
                           filtered: oxygen[-1] if abs(ridge - oxygen[-1]) <= .1 else ridge}
            evidence = {k: [sources[k][t]["id"] for t in history] for k in sources}
            evidence["targetOxygen"] = sources["oxygen"][target]["id"]
            row = {"origin": stamp(origin), "target": stamp(target), "actual": sources["oxygen"][target]["value"], "evidence": evidence, "historyFlat": flat}
            saved = report["rows"][len(rows)]
            require(all(saved[k] == v for k, v in row.items()), "exact row lineage and target")
            require(saved["oxygenHistory"] == [{"timeUTC": stamp(t), "value": sources["oxygen"][t]["value"]} for t in history], "twelve history records")
            outside = [r["feature"] for x, r in zip(features, model["training"]["featureRanges"]) if x < r["min"] - TOL or x > r["max"] + TOL]
            require(saved["outsideTrainingFeatures"] == outside, "univariate extrapolation flags")
            for a, b in zip(features, saved["features"]):
                close(a, b, "feature")
            for method, value in predictions.items():
                close(value, saved["predictionsMgL"][method], "forecast")
            rows.append(row | {"predictionsMgL": predictions})
        origin += timedelta(minutes=30)
    require(len(rows) == len(report["rows"]) == 1275 and expected == 1332, "exact shared cohort")
    grid = {"expectedOrigins": expected, "acceptedExactGridPairs": len(rows), "missingApprovedOxygenOrigins": missing,
        "presentOriginsWithIncompleteHistoryOrTarget": incomplete, "acceptedGridFraction": len(rows) / expected}
    require(report["fullExpectedGrid"] == grid, "complete grid denominator")
    maes, cases = {}, {}
    for method in protocol["methods"]:
        errors = [r["predictionsMgL"][method] - r["actual"] for r in rows]
        metrics = {"pairs": len(rows), "maeMgL": math.fsum(map(abs, errors)) / len(rows), "rmseMgL": math.sqrt(math.fsum(e * e for e in errors) / len(rows)),
            "biasMgL": math.fsum(errors) / len(rows), "p95AbsoluteErrorMgL": quantile(list(map(abs, errors)), .95), "maxAbsoluteErrorMgL": max(map(abs, errors))}
        for key, value in metrics.items():
            close(value, report["scores"][method][key], "metric " + key)
        gains = [abs(r["predictionsMgL"][persistence] - r["actual"]) - abs(r["predictionsMgL"][method] - r["actual"]) for r in rows]
        cases[method] = {"wins": sum(g > TOL for g in gains), "ties": sum(abs(g) <= TOL for g in gains), "losses": sum(g < -TOL for g in gains)}
        require(cases[method] == report["pairedCasesAgainstPersistence"][method], "wins ties losses")
        maes[method] = metrics["maeMgL"]
    groups = defaultdict(list)
    for row in rows:
        groups[int((instant(row["origin"]) - start).total_seconds() // 172800)].append(row)
    blocks = [(len(b), math.fsum(abs(z["predictionsMgL"][persistence] - z["actual"]) - abs(z["predictionsMgL"][filtered] - z["actual"]) for z in b)) for b in groups.values()]
    rng, samples = random.Random(20261063), []
    for _ in range(5000):
        chosen = [blocks[rng.randrange(len(blocks))] for _ in blocks]
        samples.append(math.fsum(g for n, g in chosen) / sum(n for n, g in chosen))
    band = {"lowerGainMgL": quantile(samples, .025), "upperGainMgL": quantile(samples, .975)}
    original = next(b for b in report["bootstrap"] if b["blockHours"] == 48)
    require(original["iterations"] == 5000 and original["seed"] == 20261063 and original["nonemptyBlocks"] == len(blocks), "bootstrap specification")
    for key, value in band.items():
        close(value, original["gainAgainstPersistence"][filtered][key], "paired bootstrap")
    return {"version": "independent-owasco-posthoc-audit-v1", "passed": True, "reportSHA256": REPORT_SHA,
        "auditScriptSHA256": sha(Path(__file__).read_bytes()), "independence": "Independent stdlib calculation; same source observations. Post-hoc code audit, not preregistration or independent physical measurement",
        "newFit": False, "newDataAcquisition": False, "frozenAtCommit": FROZEN_COMMIT, "frozenFilesChecked": len(attempt["implementationFiles"]),
        "sourceCounts": rawcounts, "grid": grid, "numericTolerance": TOL, "largestReconstructionDifference": largest, "maeMgL": maes,
        "filterCasesAgainstPersistence": cases[filtered], "filterMinusPersistenceMAEMgL": maes[filtered] - maes[persistence],
        "bootstrap48h": {"nonemptyBlocks": len(blocks), "iterations": 5000, "seed": 20261063, **band},
        "rawCadenceDiagnostics": cadence, "cadenceMeaning": "Exact-grid absence is not necessarily a physical observation gap; no timestamp shifting or interpolation performed"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--report", type=Path, help="Optional new receipt path; existing files are never overwritten")
    args = parser.parse_args()
    result = audit(args.root)
    text = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    print(text, end="")


if __name__ == "__main__":
    main()
