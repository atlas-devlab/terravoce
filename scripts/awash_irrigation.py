"""Offline water-use proxy replay. No fitting, irrigation attribution or funding action."""
from __future__ import annotations
import argparse
import calendar
import datetime as dt
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs/datasets/awash-irrigation"
EVIDENCE = ROOT / "docs/evidence/awash-irrigation"

def digest(raw: bytes) -> str:
    return "0x" + hashlib.sha256(raw).hexdigest()

def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def same_value(left, right):
    if type(left) in (int, float) and type(right) in (int, float):
        return math.isclose(left, right, rel_tol=0, abs_tol=1e-10)
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(same_value(left[k], right[k]) for k in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(same_value(a, b) for a, b in zip(left, right))
    return type(left) is type(right) and left == right

def write_new(path: Path, value):
    raw = (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError(f"Refusing to replace evidence: {path}")
    else:
        path.write_bytes(raw)

def protocol():
    p = read_json(DATA / "protocol.json")
    if p["version"] != "terravoce-awash-observation-game-v1" or p["unit"] != "mm/day":
        raise ValueError("Unsupported experiment protocol")
    return p

def dekad(code: str):
    year, month, number = int(code[:4]), int(code[5:7]), int(code[-1])
    if code != f"{year:04}-{month:02}-D{number}" or number not in (1, 2, 3):
        raise ValueError("Invalid dekad")
    first = (number - 1) * 10 + 1
    last = number * 10 if number < 3 else calendar.monthrange(year, month)[1]
    return {"code": code, "start": f"{year:04}-{month:02}-{first:02}",
            "end": f"{year:04}-{month:02}-{last:02}", "days": last - first + 1}

def aggregate(clip, bbox):
    """Native pixels weighted by overlap area on a sphere; no precipitation upsampling."""
    if clip["crs"] != "EPSG:4326" or clip["unit"] != "mm/day":
        raise ValueError("Wrong CRS or daily-mean unit")
    c, a, b, f, d, e = clip["affineTransform"]
    if not (a > 0 and e < 0 and b == d == 0):
        raise ValueError("Unsupported rotated/native grid")
    xmin, ymin, xmax, ymax = bbox
    if not (-180 <= xmin < xmax <= 180 and -90 <= ymin < ymax <= 90):
        raise ValueError("Invalid rectangle")
    w = clip["window"]
    expected = {"col": math.floor((xmin-c)/a), "row": math.floor((ymax-f)/e),
                "width": math.ceil((xmax-c)/a)-math.floor((xmin-c)/a),
                "height": math.ceil((ymin-f)/e)-math.floor((ymax-f)/e)}
    if w != expected or w["width"] * w["height"] > 4096:
        raise ValueError("Native window does not cover the protocol rectangle")
    values = clip["values"]
    if len(values) != w["height"] or any(len(row) != w["width"] for row in values):
        raise ValueError("Pixel array shape mismatch")
    numerator, valid_area, total_area, valid_count, missing = 0., 0., 0., 0, 0
    for j, row in enumerate(values):
        north = f + (w["row"] + j) * e
        south = north + e
        lat_weight = math.sin(math.radians(min(ymax, north))) - math.sin(math.radians(max(ymin, south)))
        for i, raw in enumerate(row):
            west = c + (w["col"] + i) * a
            east = west + a
            area = lat_weight * math.radians(min(xmax, east) - max(xmin, west))
            if area <= 0:
                continue
            total_area += area
            if raw == clip["noDataValue"]:
                missing += 1
                continue
            if type(raw) not in (int, float) or not math.isfinite(raw):
                raise ValueError("Non-numeric native pixel")
            value = raw * clip["scale"] + clip["offset"]
            if not math.isfinite(value) or value < 0:
                raise ValueError("Invalid water-flux pixel")
            numerator += value * area
            valid_area += area
            valid_count += 1
    theoretical = math.radians(xmax-xmin) * (math.sin(math.radians(ymax))-math.sin(math.radians(ymin)))
    if not math.isclose(total_area, theoretical, rel_tol=1e-9):
        raise ValueError("Area denominator mismatch")
    fraction = valid_area / total_area
    return {"dailyMeanMm": numerator / valid_area if valid_area else None,
            "validAreaFraction": fraction, "nativePixels": valid_count + missing,
            "validPixels": valid_count, "missingPixels": missing}

def load_phase(phase: str):
    p = protocol()
    folder = DATA / phase
    manifest_path = folder / "manifest.json"
    manifest = read_json(manifest_path)
    if manifest["protocolHash"] != digest((DATA / "protocol.json").read_bytes()):
        raise ValueError("Protocol hash mismatch")
    periods = p["history"] if phase == "history" else [p["target"]]
    expected_keys = {(metric, period) for metric in p["mapsets"] for period in periods}
    seen, records = set(), []
    for entry in manifest["records"]:
        key = (entry["metric"], entry["period"])
        if key in seen or key not in expected_keys:
            raise ValueError("Duplicate or unexpected record")
        seen.add(key)
        raw_files = {}
        for role in ("extraction", "metadata", "mapset"):
            path = folder / entry[role + "Path"]
            if path.parent != folder or path.suffix != ".json":
                raise ValueError("Unsafe archived evidence path")
            raw = path.read_bytes()
            if digest(raw) != entry[role + "Hash"]:
                raise ValueError("Archived source hash mismatch")
            raw_files[role] = json.loads(raw)
        clip = raw_files["extraction"]
        meta, mapset = raw_files["metadata"]["response"], raw_files["mapset"]["response"]
        mapset_code = p["mapsets"][entry["metric"]]
        raster_code = f"WAPOR-3.{mapset_code}.{entry['period']}"
        period = dekad(entry["period"])
        member = meta["dimensions"][0]["member"]
        if (meta["code"] != raster_code or mapset["code"] != mapset_code or clip["rasterCode"] != raster_code
            or clip["period"] != period or member["startDate"] != period["start"]
            or member["endDate"] != period["end"] or member["numberOfDays"] != period["days"]
            or clip["affineTransform"] != meta["affineTransform"]
            or clip["source"]["downloadUrl"] != meta["downloadUrl"]
            or clip["noDataValue"] != meta["noDataValue"]):
            raise ValueError("Native raster identity or period mismatch")
        for field in ("measureUnit", "scale", "offset"):
            clip_field = "unit" if field == "measureUnit" else field
            if meta[field] != mapset[field] or clip[clip_field] != meta[field]:
                raise ValueError("Source unit/scale mismatch")
        result = aggregate(clip, p["bboxWgs84"])
        complete = result["validAreaFraction"] >= p["minimumValidAreaFraction"] - 1e-12
        records.append({"metric": entry["metric"], "period": period, "unit": p["unit"], **result,
            "periodTotalMm": result["dailyMeanMm"] * period["days"] if complete else None,
            "complete": complete, "nativePixelDegrees": [meta["affineTransform"][1], -meta["affineTransform"][5]],
            "nature": "remote-sensing-estimate", "sourceRaster": raster_code,
            "sourceUpdated": meta["updated"], "extractionHash": entry["extractionHash"]})
    if seen != expected_keys:
        raise ValueError("Incomplete period/metric inventory")
    records.sort(key=lambda row: (row["period"]["start"], row["metric"]))
    return {"version": "awash-offline-replay-v1", "phase": phase,
            "protocolHash": manifest["protocolHash"], "manifestHash": digest(manifest_path.read_bytes()),
            "capturedAt": manifest["capturedAt"], "records": records}

def prediction():
    p, history = protocol(), load_phase("history")
    last = [row for row in history["records"] if row["metric"] == "aeti"][-1]
    if not last["complete"] or last["dailyMeanMm"] is None:
        raise ValueError("No complete last history value; prediction stays pending")
    return {"version": "awash-sealed-persistence-v1", "protocolHash": history["protocolHash"],
            "historyManifestHash": history["manifestHash"], "inputPeriod": last["period"]["code"],
            "targetPeriod": p["target"], "predictedDailyMeanMm": last["dailyMeanMm"],
            "unit": p["unit"], "method": "persistence", "trainedModel": False,
            "scope": "retrospective learning game using current revised FAO estimates",
            "irrigationWithdrawalM3": None, "operationalEligible": False}

def verify_seal():
    saved = read_json(EVIDENCE / "prediction.json")
    if not same_value(saved, prediction()):
        raise ValueError("Sealed prediction does not reproduce from history")
    return saved

def evaluation():
    forecast, target = verify_seal(), load_phase("target")
    if read_json(DATA / "target/manifest.json")["predictionHashBeforeAcquisition"] != digest((EVIDENCE / "prediction.json").read_bytes()):
        raise ValueError("Prediction changed after target acquisition")
    actual = next(row for row in target["records"] if row["metric"] == "aeti")
    if not actual["complete"]:
        raise ValueError("Target has missing area; evaluation stays pending")
    error = forecast["predictedDailyMeanMm"] - actual["dailyMeanMm"]
    return {"version": "awash-learning-result-v1", "predictionHash": digest((EVIDENCE / "prediction.json").read_bytes()),
            "targetManifestHash": target["manifestHash"], "targetPeriod": forecast["targetPeriod"],
            "predictedDailyMeanMm": forecast["predictedDailyMeanMm"], "actualEstimatedDailyMeanMm": actual["dailyMeanMm"],
            "signedErrorMmPerDay": error, "absoluteErrorMmPerDay": abs(error), "unit": "mm/day",
            "scoredRounds": 1, "skillEstablished": False, "irrigationWithdrawalM3": None,
            "irrigationAttributionEstablished": False, "ecologicalImprovementVerified": False,
            "fundingRelease": False, "operationalEligible": False}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["history", "seal", "score", "verify"])
    args = parser.parse_args()
    if args.command == "history":
        result = load_phase("history")
        write_new(EVIDENCE / "history.json", result)
    elif args.command == "seal":
        if (DATA / "target/manifest.json").exists():
            raise ValueError("Target already acquired; cannot create a new blind prediction")
        result = prediction()
        write_new(EVIDENCE / "prediction.json", result)
    elif args.command == "score":
        result = evaluation()
        write_new(EVIDENCE / "target.json", load_phase("target"))
        write_new(EVIDENCE / "result.json", result)
    else:
        for filename, expected in (("history.json", load_phase("history")),
                                   ("target.json", load_phase("target")), ("result.json", evaluation())):
            if not same_value(read_json(EVIDENCE / filename), expected):
                raise ValueError(f"Evidence does not reproduce: {filename}")
        result = {"verified": True, "scope": "archived native pixel extracts and deterministic scoring; not field validation",
                  "result": evaluation()}
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))

if __name__ == "__main__":
    main()
