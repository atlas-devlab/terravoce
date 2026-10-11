"""Independent numerical audit: Python stdlib + high-precision Cholesky, no Node imports.

The TypeScript replay establishes its own report; this audit reconstructs features
and ridge solutions from the raw USGS response bodies using a different solver.
This is independent code verification, not independent environmental measurement.
"""
import argparse
import gzip
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parents[1]
TOLERANCE = 1e-9


def instant(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Timestamp requires an explicit UTC offset")
    return parsed.astimezone(timezone.utc)


def iso(value):
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def digest(raw):
    return "0x" + hashlib.sha256(raw).hexdigest()


def compressed_body(path):
    with gzip.open(path, "rb") as source:
        raw = source.read(10_000_001)
    if len(raw) > 10_000_000:
        raise ValueError("Decompressed source exceeds size limit")
    return raw


def read_collection(raw, station, code, series, unit, start, end, scale=1.0):
    obj = json.loads(raw)
    if obj["type"] != "FeatureCollection" or any(x["rel"] == "next" for x in obj["links"]):
        raise ValueError("Incomplete collection")
    if len(obj["features"]) >= 10000 or obj.get("numberReturned", len(obj["features"])) != len(obj["features"]):
        raise ValueError("Wrong collection count")
    records, excluded, ids, times = {}, [], set(), set()
    for feature in obj["features"]:
        p, identity = feature["properties"], feature["id"]
        t = instant(p["time"])
        if identity in ids or t in times:
            raise ValueError("Duplicate source identity or timestamp")
        ids.add(identity)
        times.add(t)
        if (p["monitoring_location_id"], p["parameter_code"], p["time_series_id"], p["statistic_id"], p["unit_of_measure"]) != (station, code, series, "00011", unit):
            raise ValueError("Mixed source identity or units")
        if not start <= t <= end:
            raise ValueError("Out-of-period measurement")
        try:
            value = float(p["value"])
        except (TypeError, ValueError):
            value = float("nan")
        reason = ("not-approved" if p["approval_status"] != "Approved" else
                  "qualified" if p["qualifier"] not in (None, "") else
                  "invalid" if not math.isfinite(value) or (code == "00300" and value < 0) else None)
        if reason:
            excluded.append({"id": identity, "reason": reason})
        else:
            records[t] = {"id": identity, "value": value * scale, "lastModified": p["last_modified"]}
    return records, {"total": len(ids), "accepted": len(records), "excluded": excluded}


def make_pairs(oxygen, temperature, discharge, start, end):
    rows, skipped, eligible = [], 0, 0
    for origin in sorted(oxygen):
        if origin < start + timedelta(hours=5.5) or origin + timedelta(hours=1) > end:
            continue
        eligible += 1
        history_times = [origin - timedelta(minutes=30 * i) for i in range(11, -1, -1)]
        target = origin + timedelta(hours=1)
        if target not in oxygen or any(t not in source for source in (oxygen, temperature, discharge) for t in history_times):
            skipped += 1
            continue
        o = [oxygen[t]["value"] for t in history_times]
        t = [temperature[t]["value"] for t in history_times]
        q = [discharge[t]["value"] for t in history_times]
        clock = (origin.hour * 3600 + origin.minute * 60 + origin.second) / 86400 * 2 * math.pi
        x = [o[-1], o[-1] - o[-2], o[-1] - o[-5], o[-1] - o[0], math.sin(clock), math.cos(clock),
             t[-1], t[-1] - t[-5], q[-1], q[-1] - q[-5]]
        # Closed-form OLS on this evenly spaced window, evaluated at t=6.5 hours.
        xs = [i / 2 for i in range(12)]
        xm, ym = sum(xs) / 12, sum(o) / 12
        slope = sum((a - xm) * (b - ym) for a, b in zip(xs, o)) / sum((a - xm) ** 2 for a in xs)
        linear = math.floor(max(0.0, ym + slope * (6.5 - xm)) * 1_000_000 + 0.5) / 1_000_000
        rows.append({"origin": iso(origin), "target": iso(target), "actual": oxygen[target]["value"],
                     "persistence": o[-1], "linear": linear, "features": x,
                     "evidence": {"oxygen": [oxygen[h]["id"] for h in history_times],
                                  "temperature": [temperature[h]["id"] for h in history_times],
                                  "discharge": [discharge[h]["id"] for h in history_times],
                                  "targetOxygen": oxygen[target]["id"]}})
    return rows, {"eligibleOrigins": eligible, "acceptedPairs": len(rows), "skipped": skipped}


def decimal_ridge(rows, width, alpha):
    """Solve the symmetric positive-definite system via Decimal Cholesky (50 digits)."""
    with localcontext() as ctx:
        ctx.prec = 50
        D, n = Decimal, Decimal(len(rows))
        x = [[D(str(v)) for v in r["features"][:width]] for r in rows]
        y = [D(str(r["actual"])) - D(str(r["persistence"])) for r in rows]
        means = [sum(r[j] for r in x) / n for j in range(width)]
        scales = [(sum((r[j] - means[j]) ** 2 for r in x) / n).sqrt() or D(1) for j in range(width)]
        intercept = sum(y) / n
        z = [[(v - means[j]) / scales[j] for j, v in enumerate(r)] for r in x]
        a = [[sum(r[j] * r[k] for r in z) + (D(str(alpha)) if j == k else D(0)) for k in range(width)] for j in range(width)]
        b = [sum(r[j] * (value - intercept) for r, value in zip(z, y)) for j in range(width)]
        lower = [[D(0)] * width for _ in range(width)]
        for j in range(width):
            for k in range(j + 1):
                v = a[j][k] - sum(lower[j][i] * lower[k][i] for i in range(k))
                lower[j][k] = v.sqrt() if j == k else v / lower[k][k]
        forward = []
        for j in range(width):
            forward.append((b[j] - sum(lower[j][k] * forward[k] for k in range(j))) / lower[j][j])
        weights = [D(0)] * width
        for j in reversed(range(width)):
            weights[j] = (forward[j] - sum(lower[k][j] * weights[k] for k in range(j + 1, width))) / lower[j][j]
        return {"alpha": alpha, "mean": list(map(float, means)), "scale": list(map(float, scales)),
                "coefficients": list(map(float, weights)), "residualIntercept": float(intercept)}


def prediction(candidate, row):
    if candidate["name"] == "persistence":
        return row["persistence"]
    if candidate["name"] == "existing-linear":
        return row["linear"]
    m = candidate["model"]
    width = len(m["coefficients"])
    if not width or len(m["mean"]) != width or len(m["scale"]) != width or len(row["features"]) < width:
        raise ValueError("Incomplete model vectors or input features")
    return row["persistence"] + m["residualIntercept"] + sum((v - mean) / scale * w for v, mean, scale, w in
        zip(row["features"], m["mean"], m["scale"], m["coefficients"]))


def metrics(rows, forecasts):
    if not rows:
        raise ValueError("Empty scoring phase")
    if len(forecasts) != len(rows):
        raise ValueError("Incomplete forecasts")
    errors = [p - r["actual"] for r, p in zip(rows, forecasts)]
    return {"pairs": len(rows), "maeMgL": sum(map(abs, errors)) / len(errors),
            "rmseMgL": math.sqrt(sum(e * e for e in errors) / len(errors)), "biasMgL": sum(errors) / len(errors)}


def close(actual, expected, label, tolerance=TOLERANCE):
    if not math.isfinite(actual) or not math.isfinite(expected) or abs(actual - expected) > tolerance:
        raise AssertionError(f"{label}: {actual} != {expected}")
    return abs(actual - expected)


def load_original(root):
    original = root / "docs/datasets/usgs-willamette"
    extra = root / "docs/datasets/usgs-willamette-multivariate"
    manifest = json.loads((extra / "manifest.json").read_text(encoding="utf-8"))
    oxygen_manifest = json.loads((original / "manifest.json").read_text(encoding="utf-8"))
    raw = (original / "continuous.json").read_bytes()
    if digest(raw) != manifest["oxygenSourceHash"] or digest((original / "station.json").read_bytes()) != manifest["stationHash"]:
        raise ValueError("Oxygen or station hash mismatch")
    start, end = instant(manifest["start"]), instant(manifest["end"])
    oxygen, oq = read_collection(raw, manifest["stationId"], "00300", oxygen_manifest["timeSeriesId"], "mg/l", start, end)
    covariates, qualities = {}, {"oxygen": oq}
    for kind in ("temperature", "discharge"):
        source = manifest["sources"][kind]
        raw = compressed_body(extra / source["file"])
        if digest(raw) != source["rawSha256"]:
            raise ValueError("Covariate hash mismatch")
        records, quality = read_collection(raw, manifest["stationId"], source["parameterCode"], source["timeSeriesId"],
                                          source["unit"], start, end, 0.028316846592 if kind == "discharge" else 1.0)
        covariates[kind], qualities[kind] = records, quality
    rows, alignment = make_pairs(oxygen, covariates["temperature"], covariates["discharge"], start, end)
    return manifest, rows, qualities, alignment


def original_audit(root=ROOT):
    manifest, rows, qualities, alignment = load_original(root)
    report_path = root / "docs/evidence/willamette-forecast/forecast.json"
    report_bytes = report_path.read_bytes()
    report = json.loads(report_bytes)
    selection = instant(manifest["experiment"]["selectionStart"])
    calibration = instant(manifest["experiment"]["calibrationStart"])
    holdout = instant(manifest["experiment"]["holdoutStart"])
    train = [r for r in rows if instant(r["target"]) <= selection]
    validation = [r for r in rows if instant(r["origin"]) >= selection and instant(r["target"]) <= calibration]
    calibrating = [r for r in rows if instant(r["origin"]) >= calibration and instant(r["target"]) <= holdout]
    testing = [r for r in rows if instant(r["origin"]) >= holdout]
    phase_counts = {"training": len(train), "selection": len(validation), "calibration": len(calibrating), "holdout": len(testing)}
    if any(v != report["splits"][k]["pairs"] for k, v in phase_counts.items()):
        raise AssertionError("Split counts differ")
    candidates, largest_difference = [], 0.0
    for saved in report["candidates"]:
        candidate = {"name": saved["name"], "model": None}
        if saved["model"] is not None:
            model = decimal_ridge(train, len(saved["features"]), saved["model"]["alpha"])
            candidate["model"] = model
            for key in ("mean", "scale", "coefficients"):
                if len(model[key]) != len(saved["model"][key]):
                    raise AssertionError("Incomplete saved model vector")
                for i, (a, b) in enumerate(zip(model[key], saved["model"][key])):
                    largest_difference = max(largest_difference, close(a, b, f"{saved['name']} {key}[{i}]"))
            largest_difference = max(largest_difference, close(model["residualIntercept"], saved["model"]["residualIntercept"], "intercept"))
        for phase_name, phase in (("selection", validation), ("holdout", testing)):
            score = metrics(phase, [prediction(candidate, r) for r in phase])
            for key in ("maeMgL", "rmseMgL", "biasMgL"):
                largest_difference = max(largest_difference, close(score[key], saved[phase_name][key], f"{candidate['name']} {phase_name} {key}"))
        candidates.append(candidate)
    selected = min(candidates, key=lambda c: metrics(validation, [prediction(c, r) for r in validation])["maeMgL"])
    if selected["name"] != report["selected"]:
        raise AssertionError("Independent selection differs")
    error_quantiles = sorted(abs(prediction(selected, r) - r["actual"]) for r in calibrating)
    halfwidth = error_quantiles[math.ceil(len(error_quantiles) * manifest["experiment"]["intervalCoverage"]) - 1]
    close(halfwidth, report["interval"]["halfWidthMgL"], "calibration interval")
    forecasts = [prediction(selected, r) for r in testing]
    covered = sum(abs(p - r["actual"]) <= halfwidth for p, r in zip(forecasts, testing))
    close(covered / len(testing), report["interval"]["holdoutCoverage"], "coverage")
    if len(report["rows"]) != len(testing):
        raise AssertionError("Incomplete holdout lineage")
    for r, saved, p in zip(testing, report["rows"], forecasts):
        if (r["origin"], r["target"], r["evidence"]) != (saved["origin"], saved["target"], saved["evidence"]):
            raise AssertionError("Record lineage mismatch")
        if len(r["features"]) != len(saved["features"]):
            raise AssertionError("Incomplete saved feature vector")
        for i, (a, b) in enumerate(zip(r["features"], saved["features"])):
            close(a, b, f"feature[{i}]")
        close(r["actual"], saved["actual"], "actual")
        close(p, saved["selectedPredictionMgL"], "prediction")
    daily = []
    by_day = defaultdict(list)
    for r, p in zip(testing, forecasts):
        by_day[r["origin"][:10]].append((r, p))
    for day, values in sorted(by_day.items()):
        subset, predictions = zip(*values)
        score, base = metrics(subset, predictions), metrics(subset, [r["persistence"] for r in subset])
        daily.append({"originDayUTC": day, "model": score, "persistence": base,
                      "maeImprovementPercent": (1 - score["maeMgL"] / base["maeMgL"]) * 100,
                      "coverage": sum(abs(p - r["actual"]) <= halfwidth for r, p in values) / len(values)})
    return {"version": "independent-willamette-audit-v1", "scope": "independent code/solver; same source measurements",
            "reportFileHash": digest(report_bytes), "reportCommitment": report["reportHash"],
            "passed": True, "solver": "Python stdlib Decimal Cholesky, 50 digits; no TypeScript imports",
            "numericTolerance": TOLERANCE, "largestCoefficientOrMetricDifference": largest_difference,
            "checkedCandidates": len(candidates), "checkedHoldoutRows": len(testing),
            "sourceQuality": qualities, "alignment": alignment, "phaseCounts": phase_counts,
            "selected": selected["name"], "daily": daily,
            "readiness": "share with caveats as a research result; not eligible for operational promotion",
            "reasons": ["Three held-out days are insufficient for generalization",
                        "Selected model loses against persistence on one of three days",
                        "Empirical 90% interval covers only 76.92% in the holdout",
                        "Finalized archive does not establish historical real-time data availability"]}


def frozen_validation(root=ROOT):
    folder = root / "docs/datasets/usgs-willamette-validation"
    protocol_raw = (folder / "protocol.json").read_bytes()
    protocol = json.loads(protocol_raw)
    report_bytes = (root / "docs/evidence/willamette-forecast/forecast.json").read_bytes()
    report = json.loads(report_bytes)
    if (digest(report_bytes), report["reportHash"], report["selected"], report["interval"]["halfWidthMgL"]) != (
            protocol["frozenReportFileHash"], protocol["frozenReportHash"], protocol["frozenCandidate"], protocol["frozenIntervalHalfWidthMgL"]):
        raise ValueError("Frozen model or interval commitment changed")
    selected = next(c for c in report["candidates"] if c["name"] == report["selected"])
    original_manifest, original_rows, _, _ = load_original(root)
    train = [r for r in original_rows if instant(r["target"]) <= instant(original_manifest["experiment"]["selectionStart"])]
    width = len(selected["features"])
    training_ranges = [{"feature": name, "min": min(r["features"][j] for r in train), "max": max(r["features"][j] for r in train)}
                       for j, name in enumerate(selected["features"])]
    windows = []
    for window in protocol["windows"]:
        path = folder / window["id"]
        if not (path / "manifest.json").exists():
            windows.append({"window": window, "status": "blocked; predeclared source capture unavailable"})
            continue
        manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
        if manifest["protocolHash"] != digest(protocol_raw) or manifest["window"] != window:
            raise ValueError("External capture protocol mismatch")
        start, end = instant(window["start"]), instant(window["end"])
        sources, qualities, hashes = {}, {}, {}
        for kind, spec in protocol["sources"].items():
            source = manifest["sources"][kind]
            if source["file"] != f"{kind}.json.gz":
                raise ValueError("Unexpected source filename")
            url, query = urlparse(source["sourceUrl"]), parse_qs(urlparse(source["sourceUrl"]).query)
            if url.scheme != "https" or url.netloc != "api.waterdata.usgs.gov" or url.path != "/ogcapi/v1/collections/continuous/items" or query != {
                    "f": ["json"], "monitoring_location_id": [protocol["stationId"]], "parameter_code": [spec["parameterCode"]],
                    "time": [f"{window['start']}/{window['end']}"], "limit": ["10000"]}:
                raise ValueError("External source URL mismatch")
            raw = compressed_body(path / source["file"])
            if digest(raw) != source["rawSha256"]:
                raise ValueError("External raw-body hash mismatch")
            records, quality = read_collection(raw, protocol["stationId"], spec["parameterCode"], spec["timeSeriesId"], spec["unit"], start, end, spec["scale"])
            if quality["total"] != source["records"]:
                raise ValueError("External manifest count mismatch")
            sources[kind], qualities[kind], hashes[kind] = records, quality, source["rawSha256"]
        rows, alignment = make_pairs(sources["oxygen"], sources["temperature"], sources["discharge"], start, end)
        if not rows:
            windows.append({"window": window, "status": "blocked; no complete approved exact-join pairs", "quality": qualities, "alignment": alignment})
            continue
        predicted = [prediction(selected, r) for r in rows]
        model_score = metrics(rows, predicted)
        persistence = metrics(rows, [r["persistence"] for r in rows])
        linear = metrics(rows, [r["linear"] for r in rows])
        halfwidth = protocol["frozenIntervalHalfWidthMgL"]
        outside = [[j for j in range(width) if r["features"][j] < training_ranges[j]["min"] - TOLERANCE or
                    r["features"][j] > training_ranges[j]["max"] + TOLERANCE] for r in rows]
        daily = []
        for day in sorted({r["origin"][:10] for r in rows}):
            indices = [i for i, r in enumerate(rows) if r["origin"].startswith(day)]
            subset = [rows[i] for i in indices]
            ps = [predicted[i] for i in indices]
            daily.append({"originDayUTC": day, "model": metrics(subset, ps),
                          "persistence": metrics(subset, [r["persistence"] for r in subset]),
                          "coverage": sum(abs(p - r["actual"]) <= halfwidth for p, r in zip(ps, subset)) / len(subset)})
        windows.append({"window": window, "status": "evaluated without fitting or calibration", "sourceHashes": hashes,
                        "quality": qualities, "alignment": alignment, "selectedModel": model_score,
                        "persistence": persistence, "existingLinear": linear,
                        "maeImprovementOverPersistencePercent": None if persistence["maeMgL"] == 0 else
                            (1 - model_score["maeMgL"] / persistence["maeMgL"]) * 100,
                        "unchangedIntervalCoverage": sum(abs(p - r["actual"]) <= halfwidth for p, r in zip(predicted, rows)) / len(rows),
                        "featureExtrapolation": {"pairs": sum(bool(x) for x in outside), "fraction": sum(bool(x) for x in outside) / len(rows),
                            "bySelectedFeature": {name: sum(j in x for x in outside) for j, name in enumerate(selected["features"])},
                            "interpretation": "Univariate training-range diagnostic; not a probability or a validated applicability domain"},
                        "observedTargetsBelowIllustrative5MgL": sum(r["actual"] < 5 for r in rows),
                        "negativePredictions": sum(p < 0 for p in predicted), "daily": daily,
                        "rows": [{**r, "selectedPredictionMgL": p, "lowerMgL": p - halfwidth, "upperMgL": p + halfwidth,
                                  "outsideTrainingFeatures": [selected["features"][j] for j in out]} for r, p, out in zip(rows, predicted, outside)]})
    return {"version": "frozen-seasonal-validation-v1", "protocolHash": digest(protocol_raw),
            "frozenReportHash": report["reportHash"], "selected": selected["name"], "refitted": False, "recalibrated": False,
            "operationalModelChanged": False, "independentFieldMeasurement": False, "trainingFeatureRanges": training_ranges,
            "windows": windows, "decision": "retain as an isolated research experiment; no operational promotion",
            "scope": "Later archival windows, frozen model/interval; correlation and finalized-data limitations remain"}


def compare_saved(actual, saved, path="report"):
    """Exact structure/text/counts, explicit absolute tolerance for finite floats."""
    if isinstance(actual, dict) and isinstance(saved, dict):
        if actual.keys() != saved.keys():
            raise AssertionError(f"{path}: different fields")
        return max((compare_saved(actual[k], saved[k], f"{path}.{k}") for k in actual), default=0.0)
    if isinstance(actual, list) and isinstance(saved, list):
        if len(actual) != len(saved):
            raise AssertionError(f"{path}: different row/vector counts")
        return max((compare_saved(a, b, f"{path}[{i}]") for i, (a, b) in enumerate(zip(actual, saved))), default=0.0)
    if type(actual) is float and type(saved) is float:
        return close(actual, saved, path)
    if type(actual) is not type(saved) or actual != saved:
        raise AssertionError(f"{path}: different exact value")
    return 0.0


def verify_saved_seasonal(result, folder):
    raw = compressed_body(folder / "seasonal-validation.json.gz")
    saved = json.loads(raw)
    largest = compare_saved(result, saved)
    brief = {k: v for k, v in saved.items() if k != "windows"}
    brief["fullDecompressedReportSha256"] = digest(raw)
    brief["windows"] = [{k: v for k, v in w.items() if k != "rows"} for w in saved["windows"]]
    summary = json.loads((folder / "seasonal-summary.json").read_text(encoding="utf-8"))
    compare_saved(brief, summary, "saved summary")
    return {"verified": True, "fullSavedReportSha256": digest(raw), "numericTolerance": TOLERANCE,
            "largestNumericDifference": largest, "structureAndSourceHashes": "exact",
            "scope": "offline reproduction; floating-point portability check, not scientific validation"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--external", action="store_true", help="Evaluate the predeclared later seasonal windows with a frozen model")
    parser.add_argument("--summary", action="store_true", help="Print a compact summary while saving the full report")
    parser.add_argument("--summary-output", type=Path, help="Save a compact report with the full decompressed report hash")
    parser.add_argument("--verify-artifacts", type=Path, help="Verify saved full seasonal report and summary without overwriting them")
    args = parser.parse_args()
    checked = original_audit(args.root)
    result = frozen_validation(args.root) if args.external else checked
    artifact_check = None
    if args.verify_artifacts:
        if not args.external:
            raise ValueError("Seasonal artifact verification requires --external")
        artifact_check = verify_saved_seasonal(result, args.verify_artifacts)
    content = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    def save(path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = text.encode("utf-8")
        existing = gzip.decompress(path.read_bytes()) if path.exists() and path.suffix == ".gz" else path.read_bytes() if path.exists() else None
        if existing is not None and existing.decode("utf-8").replace("\r\n", "\n") != text:
            raise ValueError("Different existing audit: choose a new output path")
        if existing is None:
            path.write_bytes(gzip.compress(raw, mtime=0) if path.suffix == ".gz" else raw)
    if args.output:
        save(args.output, content)
    if args.summary_output:
        if not args.external:
            raise ValueError("Summary artifact is for external validation")
        brief = {k: v for k, v in result.items() if k != "windows"}
        brief["fullDecompressedReportSha256"] = digest(content.encode("utf-8"))
        brief["windows"] = [{k: v for k, v in w.items() if k != "rows"} for w in result["windows"]]
        save(args.summary_output, json.dumps(brief, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    if args.summary and args.external:
        print(json.dumps({"decision": result["decision"], "artifactVerification": artifact_check,
              "windows": [{k: v for k, v in w.items() if k not in ("rows", "daily")}
              for w in result["windows"]]}, indent=2, allow_nan=False))
    else:
        print(content)


if __name__ == "__main__":
    main()
