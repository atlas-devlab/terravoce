"""Independent stdlib check of the pinned three-response source fixture.

This is not a general collector, RFC canonical-JSON implementation, scientific
audit, receipt verifier or source-authenticity proof. It checks this experiment
without importing or executing its JavaScript verifier.
"""

import argparse
import datetime as dt
import hashlib
import json
import math
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATASET = ROOT / "docs/datasets/autonomous-source"
EVIDENCE = ROOT / "docs/evidence/autonomous-source/reproduction.json"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return "0x" + hashlib.sha256(raw).hexdigest()


def canonical(value):
    # The fixed envelope uses noncolliding ASCII keys and ordinary finite
    # numbers. Check that assumption instead of claiming universal JS encoding.
    def normalize(x):
        if isinstance(x, dict):
            require(all(re.fullmatch(r"[a-z][A-Za-z0-9]*", k) for k in x), "Unsupported canonical keys")
            require(sorted(x) == sorted(x, key=str.lower), "Unsupported canonical key ordering")
            return {k: normalize(x[k]) for k in sorted(x)}
        if isinstance(x, list):
            return [normalize(v) for v in x]
        if isinstance(x, float):
            require(math.isfinite(x), "Nonfinite canonical number")
            return int(x) if x.is_integer() else x
        return x
    return json.dumps(normalize(value), ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def timestamp(value):
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.tzinfo is not None, "Timestamp requires timezone")
    return parsed.astimezone(dt.timezone.utc)


def iso(value):
    return timestamp(value).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def read_bounded(path, maximum):
    with path.open("rb") as handle:
        raw = handle.read(maximum + 1)
    require(len(raw) <= maximum, "Fixture byte limit exceeded")
    return raw


def committed_hash():
    seal = subprocess.check_output(["git", "show", "HEAD:docs/evidence/autonomous-source/seal.json"], cwd=ROOT)
    return json.loads(seal)["evidenceHash"]


def audit(dataset=DATASET, evidence_file=EVIDENCE, expected_hash=None):
    expected_hash = expected_hash if expected_hash is not None else committed_hash()
    require(re.fullmatch(r"0x[0-9a-f]{64}", expected_hash), "Invalid external hash")
    protocol_raw = read_bounded(dataset / "protocol.json", 65536)
    p = json.loads(protocol_raw)
    require(isinstance(p["limits"]["maxResponseBytes"], int) and 100 <= p["limits"]["maxResponseBytes"] <= 2_000_000, "Unsupported fixture response limit")
    archive = json.loads(read_bounded(dataset / "manifest.json", 65536))
    saved = json.loads(read_bounded(evidence_file, 2_000_000))
    require(archive["protocolHash"] == sha(protocol_raw), "Protocol hash mismatch")
    require(len(archive["responses"]) == 3, "Reference checker supports this three-response fixture only")
    raws = []
    for entry in archive["responses"]:
        require(re.fullmatch(r"[a-z][a-z0-9-]*\.json", entry["file"]), "Unsafe archive filename")
        raw = read_bounded(dataset / entry["file"], p["limits"]["maxResponseBytes"])
        require(len(raw) == entry["bytes"] and sha(raw) == entry["rawSha256"], "Raw response hash mismatch")
        raws.append(json.loads(raw))
    catalog, station, observations = raws
    require(not any(link["rel"] == "next" for link in catalog["links"]), "Reference checker requires a complete single catalog page")
    require(not any(link["rel"] == "next" for link in observations["links"]), "Incomplete observations")
    west, south, east, north = p["territory"]["bbox"]

    def inside(feature):
        geometry = feature.get("geometry")
        if not geometry or geometry["type"] != "Point":
            return False
        longitude, latitude = geometry["coordinates"][:2]
        return west <= longitude <= east and south <= latitude <= north

    candidates = []
    for feature in catalog["features"]:
        a = feature["properties"]
        if not isinstance(a.get("monitoring_location_id"), str) or not re.fullmatch(r"USGS-\d+", a["monitoring_location_id"]) or not re.fullmatch(r"[a-f0-9]{32}", feature["id"]):
            continue
        if a.get("parameter_code") != p["metric"]["parameterCode"] or a.get("statistic_id") != p["metric"]["statisticId"] or str(a.get("unit_of_measure")).lower() != "mg/l" or not inside(feature) or a["monitoring_location_id"] in p["alreadyConnectedStationIds"]:
            continue
        if not isinstance(a.get("begin"), str) or not isinstance(a.get("end"), str):
            continue
        try:
            begin, end = timestamp(a["begin"]), timestamp(a["end"])
        except ValueError:
            continue
        if begin > timestamp(p["window"]["start"]) or end < timestamp(p["window"]["end"]):
            continue
        candidates.append((a["monitoring_location_id"], feature["id"]))
    require(len(candidates) == len(set(candidates)), "Duplicate catalog candidate")
    require(bool(candidates), "No candidate")
    station_id, series_id = sorted(candidates)[0]
    a = station["properties"]
    require(station["id"] == station_id == a["id"] and a["agency_code"] == "USGS" and inside(station) and a["hydrologic_unit_code"].startswith(p["territory"]["hydrologicUnitPrefix"]), "First candidate station mismatch")
    accepted, excluded, ids, times = [], [], set(), set()
    for feature in observations["features"]:
        a = feature["properties"]
        require(a["monitoring_location_id"] == station_id and a["time_series_id"] == series_id and a["parameter_code"] == p["metric"]["parameterCode"] and a["statistic_id"] == p["metric"]["statisticId"] and a["unit_of_measure"].lower() == "mg/l", "Observation identity or unit mismatch")
        time = iso(a["time"])
        require(timestamp(p["window"]["start"]) <= timestamp(time) <= timestamp(p["window"]["end"]), "Observation outside window")
        require(feature["id"] not in ids and time not in times, "Duplicate observation")
        ids.add(feature["id"]); times.add(time)
        try:
            value = float(a["value"]) if isinstance(a.get("value"), str) and a["value"].strip() else math.nan
        except ValueError:
            value = math.nan
        reason = "publisher-not-approved" if a.get("approval_status") != "Approved" else "publisher-qualified" if a.get("qualifier") not in (None, "") else "missing-or-invalid-value" if not math.isfinite(value) or value < 0 else "missing-modification-time" if not isinstance(a.get("last_modified"), str) else None
        if reason:
            excluded.append({"id": feature["id"], "reason": reason})
        else:
            accepted.append({"id": feature["id"], "time": time, "value": value, "unit": "mg/L", "approval": "Approved", "lastModified": iso(a["last_modified"])})
    accepted.sort(key=lambda row: row["time"])
    require(len(accepted) >= 2, "Insufficient observations")
    a = station["properties"]
    reproduction = {
        "selected": {"stationId": station_id, "seriesId": series_id},
        "station": {"name": a["monitoring_location_name"], "hydrologicUnit": a["hydrologic_unit_code"], "coordinates": station["geometry"]["coordinates"]},
        "observations": accepted,
        "quality": {"total": len(observations["features"]), "accepted": len(accepted), "excluded": excluded},
        "discovery": {"catalogPages": 1, "catalogRecords": len(catalog["features"]), "eligibleCandidates": len(candidates), "attempts": []},
        "publisher": "USGS", "sourceSignature": "none; HTTPS publisher retrieval only", "independentPublishers": 1,
        "physicalTruthVerified": False, "ecologicalImprovementVerified": False, "operationalEligible": False, "fundingRelease": False,
    }
    core = {"version": "autonomous-source-evidence-v1", "protocolHash": sha(protocol_raw), "archiveHash": sha(canonical(archive)), "reproduction": reproduction}
    evidence_hash = sha(b"terravoce-autonomous-evidence-v1:" + canonical(core))
    require(evidence_hash == expected_hash, "External evidence commitment mismatch")
    require(canonical(saved) == canonical({**core, "evidenceHash": evidence_hash}), "Saved reproduction mismatch")
    return {"verified": True, "evidenceHash": evidence_hash, "selected": reproduction["selected"], "observations": len(accepted), "scope": "independent Python check of this pinned three-response fixture; not scientific validation", "physicalTruthVerified": False, "operationalEligible": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=pathlib.Path, default=DATASET)
    parser.add_argument("--evidence-file", type=pathlib.Path, default=EVIDENCE)
    parser.add_argument("--expected-evidence-hash")
    args = parser.parse_args()
    print(json.dumps(audit(args.dataset_dir, args.evidence_file, args.expected_evidence_hash), indent=2))
