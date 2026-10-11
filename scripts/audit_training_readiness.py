"""Offline source-readiness audit. Does not fit, choose or calibrate a model."""
import argparse
import json
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import audit_willamette as shared

ROOT = Path(__file__).resolve().parents[1]
KINDS = ("oxygen", "temperature", "discharge")


def audit(root=ROOT):
    folder = root / "docs/datasets/usgs-willamette-training-audit"
    raw_protocol = (folder / "protocol.json").read_bytes()
    protocol = json.loads(raw_protocol)
    if protocol["version"] != "willamette-training-readiness-v1" or protocol["stationId"] != "USGS-14211720" or set(protocol["sources"]) != set(KINDS):
        raise ValueError("Unexpected source-audit protocol")
    windows = []
    for window in protocol["windows"]:
        if window["id"] not in ("winter-2024", "spring-2024", "summer-2024", "autumn-2024"):
            raise ValueError("Unexpected seasonal window identifier")
        path = folder / window["id"]
        if not (path / "manifest.json").exists():
            windows.append({"window": window, "status": "unavailable", "readinessScreenPassed": False})
            continue
        manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
        if manifest["version"] != "training-capture-v1" or manifest["protocolHash"] != shared.digest(raw_protocol) or manifest["window"] != window:
            raise ValueError("Capture protocol mismatch")
        if manifest["status"] == "unavailable":
            windows.append({"window": window, "status": "unavailable", "error": manifest["error"], "readinessScreenPassed": False})
            continue
        if manifest["status"] != "captured" or set(manifest["sources"]) != set(KINDS):
            raise ValueError("Unexpected capture manifest")
        start, end = shared.instant(window["start"]), shared.instant(window["end"])
        sources, quality, source_hashes, ranges = {}, {}, {}, {}
        for kind in KINDS:
            spec, source = protocol["sources"][kind], manifest["sources"][kind]
            if source["file"] != f"{kind}.json.gz":
                raise ValueError("Unexpected source filename")
            url = urlparse(source["sourceUrl"])
            if url.scheme != "https" or url.netloc != "api.waterdata.usgs.gov" or url.path != "/ogcapi/v1/collections/continuous/items" or url.fragment or parse_qs(url.query) != {
                "f": ["json"], "monitoring_location_id": [protocol["stationId"]], "parameter_code": [spec["parameterCode"]],
                "time": [f"{window['start']}/{window['end']}"], "limit": ["10000"]}:
                raise ValueError("Source query mismatch")
            raw = shared.compressed_body(path / source["file"])
            if shared.digest(raw) != source["rawSha256"]:
                raise ValueError("Source hash mismatch")
            measurements, quality[kind] = shared.read_collection(raw, protocol["stationId"], spec["parameterCode"], spec["timeSeriesId"], spec["unit"], start, end, spec["scale"])
            if quality[kind]["total"] != source["records"]:
                raise ValueError("Capture count mismatch")
            sources[kind], source_hashes[kind] = measurements, source["rawSha256"]
            values = [m["value"] for m in measurements.values()]
            ranges[kind] = {"min": min(values) if values else None, "max": max(values) if values else None,
                "mean": sum(values) / len(values) if values else None,
                "unit": {"oxygen": "mg/L", "temperature": "degC", "discharge": "m3/s"}[kind],
                "negativeRecords": sum(v < 0 for v in values),
                "firstAcceptedUTC": shared.iso(min(measurements)) if values else None,
                "lastAcceptedUTC": shared.iso(max(measurements)) if values else None}
        rows, alignment = shared.make_pairs(sources["oxygen"], sources["temperature"], sources["discharge"], start, end)
        first_origin, last_origin = start + timedelta(hours=5.5), end - timedelta(hours=1)
        expected = {first_origin + timedelta(minutes=30 * i) for i in range(int((last_origin - first_origin).total_seconds() / 1800) + 1)}
        valid = {shared.instant(row["origin"]) for row in rows} & expected
        present = set(sources["oxygen"]) & expected
        full_grid = {"expectedOrigins": len(expected), "acceptedExactGridPairs": len(valid),
            "missingApprovedOxygenOrigins": len(expected - present),
            "presentOriginsWithIncompleteHistoryOrTarget": len(present - valid),
            "acceptedGridFraction": len(valid) / len(expected),
            "interpretation": "Fixed UTC grid includes entirely missing oxygen origins; separate from the predeclared conditional-origin screen"}
        skipped_fraction = alignment["skipped"] / alignment["eligibleOrigins"] if alignment["eligibleOrigins"] else None
        screen = protocol["preliminaryReadiness"]
        passed = len(rows) >= screen["minimumPairsPerWindow"] and skipped_fraction is not None and skipped_fraction <= screen["maximumSkippedOriginFraction"]
        windows.append({"window": window, "status": "audited", "sourceHashes": source_hashes, "quality": quality,
            "ranges": ranges, "alignment": alignment, "fullExpectedGrid": full_grid, "skippedOriginFraction": skipped_fraction,
            "readinessScreenPassed": passed, "approvedTargetsBelowIllustrative5MgL": sum(r["actual"] < 5 for r in rows)})
    return {"version": "willamette-training-readiness-report-v1", "protocolHash": shared.digest(raw_protocol),
        "stationId": protocol["stationId"], "windows": windows, "totalAcceptedPairs": sum(w.get("alignment", {}).get("acceptedPairs", 0) for w in windows),
        "allFourWindowsPassAvailabilityScreen": len(windows) == 4 and all(w["readinessScreenPassed"] for w in windows),
        "availabilityScreen": protocol["preliminaryReadiness"], "screenMeaning": protocol["readinessMeaning"],
        "modelFitted": False, "forecastSkillEvaluated": False, "operationalModelChanged": False,
        "decision": "use this audit to plan a separate one-hour experiment; no model promotion",
        "limitations": ["Four selected fortnight windows are not a full year or proof of representativeness",
            "Finalized archival data do not establish historical live availability",
            "Missing/provisional/qualified records are excluded without interpolation",
            "No prediction, uncertainty calibration or critical-event detection skill is evaluated",
            "These inspected values cannot be called an untouched final test of a future model"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    result = audit(args.root)
    if args.verify:
        shared.compare_saved(result, json.loads(args.verify.read_text(encoding="utf-8")))
    if args.output:
        raw = (json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if args.output.exists():
            shared.compare_saved(result, json.loads(args.output.read_bytes()))
        else:
            with args.output.open("xb") as destination:
                destination.write(raw)
    if args.summary:
        print(json.dumps({"preliminaryScreenPassed": result["allFourWindowsPassAvailabilityScreen"], "totalPairs": result["totalAcceptedPairs"],
            "modelFitted": False, "windows": [{"id": w["window"]["id"], "status": w["status"], "passes": w["readinessScreenPassed"],
                "alignment": w.get("alignment"), "fullExpectedGrid": w.get("fullExpectedGrid"), "oxygen": w.get("ranges", {}).get("oxygen"), "temperature": w.get("ranges", {}).get("temperature")}
                for w in result["windows"]]}, indent=2, allow_nan=False))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
