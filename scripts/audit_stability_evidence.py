"""Rebuild accepted origins, all forecasts and scores directly from archived USGS JSON.

No imports from the experiment implementation; no network or model fitting.
"""
import gzip
import hashlib
import json
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path

root = Path(sys.argv[1]).resolve()
dataset = root / "docs/datasets/usgs-willamette-stability"
report_path = root / "docs/evidence/willamette-stability/evaluation.json.gz"
report_bytes = gzip.decompress(report_path.read_bytes())
report = json.loads(report_bytes)
spec = json.loads((dataset / "protocol.json").read_bytes())
source_spec = json.loads((root / spec["baseModel"]["protocolFile"]).read_bytes())
model = json.loads((root / spec["baseModel"]["file"]).read_bytes())["model"]
methods = report["methods"]
parse = lambda value: datetime.fromisoformat(value.replace("Z", "+00:00"))
digest = lambda body: "0x" + hashlib.sha256(body).hexdigest()
maximum_difference = 0.


def equal(a, b):
    global maximum_difference
    assert math.isfinite(a) and math.isfinite(b)
    maximum_difference = max(maximum_difference, abs(a - b))
    assert abs(a - b) <= 1e-9, (a, b)


summaries = []
for window in report["windows"]:
    calendar = window["window"]
    folder = dataset / calendar["id"]
    manifest = json.loads((folder / "manifest.json").read_bytes())
    assert manifest["status"] == "captured"
    assert manifest["frozenAtCommit"] == "e8b4e133aa81ecda548480991584239a8ed142ea"
    start, end = parse(calendar["start"]), parse(calendar["end"])
    sources, revisions = {}, []
    for kind, definition in source_spec["sources"].items():
        source = manifest["sources"][kind]
        body = gzip.decompress((folder / source["file"]).read_bytes())
        assert digest(body) == source["rawSha256"]
        collection = json.loads(body)
        assert collection["type"] == "FeatureCollection"
        assert not any(link["rel"] == "next" for link in collection["links"])
        records, identities = {}, set()
        for feature in collection["features"]:
            p = feature["properties"]
            time = parse(p["time"])
            assert feature["id"] not in identities and time not in records
            identities.add(feature["id"])
            assert start <= time <= end
            assert (p["monitoring_location_id"], p["parameter_code"], p["time_series_id"],
                    p["statistic_id"], p["unit_of_measure"]) == (
                spec["stationId"], definition["parameterCode"], definition["timeSeriesId"], "00011", definition["unit"])
            value = float(p["value"])
            assert p["approval_status"] == "Approved" and p["qualifier"] in (None, "") and math.isfinite(value)
            if kind == "oxygen":
                assert value >= 0
            records[time] = (value * definition["scale"], feature["id"])
            revisions.append(p["last_modified"])
        assert len(records) == source["records"]
        sources[kind] = records
    grid = [start + timedelta(minutes=330 + 30 * i) for i in range(1332)]
    assert grid[-1] + timedelta(hours=1) == end
    accepted = {origin for origin in grid if origin + timedelta(hours=1) in sources["oxygen"] and
                all(origin - timedelta(minutes=30 * i) in series for series in sources.values() for i in range(12))}
    rows = window["rows"]
    assert {parse(row["origin"]) for row in rows} == accepted and len(rows) == len(accepted)
    assert len(rows) == window["fullExpectedGrid"]["acceptedExactGridPairs"]
    errors = {method: [] for method in methods}
    flat, flat_changed, negatives = 0, 0, 0
    for row in rows:
        origin, target = parse(row["origin"]), parse(row["target"])
        assert target == origin + timedelta(hours=1)
        times = [origin - timedelta(minutes=30 * i) for i in range(11, -1, -1)]
        oxygen = [sources["oxygen"][time][0] for time in times]
        temperatures = [sources["temperature"][time][0] for time in times]
        for kind in sources:
            assert row["evidence"][kind] == [sources[kind][time][1] for time in times]
        assert row["evidence"]["targetOxygen"] == sources["oxygen"][target][1]
        equal(row["actual"], sources["oxygen"][target][0])
        assert [parse(item["timeUTC"]) for item in row["oxygenHistory"]] == times
        assert [item["value"] for item in row["oxygenHistory"]] == oxygen
        clock = (origin.hour * 60 + origin.minute) / 1440 * 2 * math.pi
        features = [oxygen[-1], oxygen[-1] - oxygen[-2], oxygen[-1] - oxygen[-5], oxygen[-1] - oxygen[0],
                    math.sin(clock), math.cos(clock), temperatures[-1], temperatures[-1] - temperatures[-5]]
        for a, b in zip(features, row["features"]):
            equal(a, b)
        ridge = oxygen[-1] + model["residualIntercept"] + math.fsum(
            (x - mean) / scale * weight for x, mean, scale, weight in
            zip(features, model["mean"], model["scale"], model["coefficients"]))
        is_flat = len(set(oxygen)) == 1
        values = [oxygen[-1], ridge, oxygen[-1] if is_flat else ridge]
        assert row["historyFlat"] == is_flat
        flat += is_flat
        flat_changed += is_flat and row["actual"] != oxygen[-1]
        negatives += sources["discharge"][origin][0] < 0
        for method, prediction in zip(methods, values):
            equal(prediction, row["predictionsMgL"][method])
            errors[method].append(prediction - row["actual"])
    recomputed = {}
    for method, values in errors.items():
        ordered = sorted(map(abs, values))
        pos = (len(ordered) - 1) * .95
        low, high = math.floor(pos), math.ceil(pos)
        measures = {"maeMgL": math.fsum(ordered) / len(ordered),
                    "rmseMgL": math.sqrt(math.fsum(v * v for v in values) / len(values)),
                    "biasMgL": math.fsum(values) / len(values),
                    "p95AbsoluteErrorMgL": ordered[low] + (ordered[high] - ordered[low]) * (pos - low)}
        for metric, value in measures.items():
            equal(value, window["scores"][method][metric])
        recomputed[method] = measures
    summaries.append({"season": calendar["season"], "pairs": len(rows), "expectedOrigins": len(grid),
        "coverage": len(rows) / len(grid), "flatHistories": flat, "flatHistoriesWithChangedTarget": flat_changed,
        "negativeDischargeOrigins": negatives, "scores": recomputed,
        "lowestRecordedTargetMgL": min(row["actual"] for row in rows),
        "largestPersistenceErrorMgL": max(map(abs, errors[methods[0]])),
        "largestFallbackErrorMgL": max(map(abs, errors[methods[2]])),
        "sourceRevisionRange": {"min": min(revisions), "max": max(revisions)}})
for method in methods:
    equal(math.fsum(s["scores"][method]["maeMgL"] for s in summaries) / 4,
          report["macro"]["seasonalMeanMAEMgL"][method])
result = {"verified": True, "networkUsed": False, "modelFitted": False,
          "experimentModulesImported": False, "rawEvaluationSha256": digest(report_bytes),
          "pairsIndependentlyRebuilt": sum(s["pairs"] for s in summaries),
          "maximumArithmeticDifference": maximum_difference, "toleranceMgL": 1e-9,
          "windows": summaries}
receipt = report_path.parent / "independent-check.json"
if receipt.exists():
    assert json.loads(receipt.read_text(encoding="utf-8-sig")) == result, "Saved independent audit differs"
brief = {k: v for k, v in report.items() if k != "windows"}
brief["fullReportRawSha256"] = digest(report_bytes)
brief["windows"] = [{k: v for k, v in w.items() if k != "rows"} for w in report["windows"]]
assert json.loads((report_path.parent / "summary.json").read_bytes()) == brief, "Saved summary differs"
print(json.dumps(result, indent=2, allow_nan=False))
