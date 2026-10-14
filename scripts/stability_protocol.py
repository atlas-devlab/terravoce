"""Validate the pre-capture one-hour stability experiment and its pure past-only rule."""
import json
import math
from datetime import timedelta
from pathlib import Path

import audit_willamette as shared

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = Path("docs/datasets/usgs-willamette-stability/protocol.json")
MODEL_HASH = "0x72d7d14221c7b14c173dba59d69d2a1d36cbb27ee146378b9e046eea998762c9"
BASE_PROTOCOL_HASH = "0x40c8b28cc139c8b195a2aacdb5374157b0811186024d2a8370c796f4b9475fb4"
SEASONS = ("winter", "spring", "summer", "autumn")
WINDOWS = (("2025-02-01T00:00:00Z", "2025-03-01T00:00:00Z"),
           ("2025-05-01T00:00:00Z", "2025-05-29T00:00:00Z"),
           ("2025-06-01T00:00:00Z", "2025-06-29T00:00:00Z"),
           ("2025-11-01T00:00:00Z", "2025-11-29T00:00:00Z"))
WINDOW_IDS = ("winter-february-2025", "spring-may-2025", "summer-june-2025", "autumn-november-2025")
PREVIOUS_FILES = [
    "docs/datasets/usgs-willamette-training-audit/protocol.json",
    "docs/datasets/usgs-willamette-multiseason/protocol.json",
    "docs/datasets/usgs-willamette-validation/protocol.json",
    "docs/datasets/usgs-willamette-multivariate/manifest.json"]


def apply_rule(history, origin_utc, ridge_prediction):
    """Prototype with no target argument: suppress the entire residual only on a flat history."""
    if len(history) != 12 or type(ridge_prediction) not in (int, float) or not math.isfinite(ridge_prediction):
        raise ValueError("Need twelve history records and a finite ridge prediction")
    origin = shared.instant(origin_utc)
    if origin.minute not in (0, 30) or origin.second or origin.microsecond:
        raise ValueError("Forecast origin must lie on the exact half-hour UTC grid")
    for index, record in enumerate(history):
        if (set(record) != {"timeUTC", "value"} or type(record["value"]) not in (int, float) or
                not math.isfinite(record["value"]) or record["value"] < 0 or
                shared.instant(record["timeUTC"]) != origin - timedelta(minutes=30 * (11 - index))):
            raise ValueError("History must contain exact past-only 30-minute oxygen records")
    current = history[-1]["value"]
    flat = all(record["value"] == current for record in history)
    # Select the branch directly: zero multiplied by an overflowed residual is not zero.
    prediction = current if flat else ridge_prediction
    return {"historyFlat": flat, "residualMultiplier": 0 if flat else 1,
            "predictionMgL": prediction, "persistenceMgL": current,
            "ridgePredictionMgL": ridge_prediction}


def previous_windows(root):
    windows = []
    for filename in PREVIOUS_FILES:
        data = json.loads((root / filename).read_bytes())
        if data["stationId"] != "USGS-14211720":
            raise ValueError("Previously inspected source station changed")
        candidates = data.get("windows", data.get("testWindows", [data]))
        windows.extend((shared.instant(w["start"]), shared.instant(w["end"])) for w in candidates)
    return windows


def validate_definition(spec, seen):
    if (spec["version"] != "willamette-stability-one-hour-v1" or
            spec["phase"] != "protocol-only-before-new-test-capture" or
            spec["stationId"] != "USGS-14211720" or spec["horizonSeconds"] != 3600 or
            spec["previouslyInspectedProtocolFiles"] != PREVIOUS_FILES):
        raise ValueError("Changed one-hour protocol identity")
    base = spec["baseModel"]
    if (base["file"] != "docs/evidence/willamette-multiseason/frozen-model.json" or
            base["protocolFile"] != PREVIOUS_FILES[1] or base["rawSha256"] != MODEL_HASH or
            base["protocolRawSha256"] != BASE_PROTOCOL_HASH or base["newFitPermitted"] is not False):
        raise ValueError("This experiment must reuse the exact frozen model")
    rule = spec["rule"]
    if (rule["historySamples"] != 12 or rule["sampleSpacingSeconds"] != 1800 or
            rule["historySpanSeconds"] != 19800 or rule["flatResidualMultiplier"] != 0 or
            rule["changingResidualMultiplier"] != 1 or
            rule["multiplyFullResidualIncludingIntercept"] is not True or rule["parameterSearchPermitted"] is not False):
        raise ValueError("Changed fixed persistence-fallback rule")
    if len(spec["testWindows"]) != 4:
        raise ValueError("Need exactly four fixed test windows")
    for window, identity, season, expected in zip(spec["testWindows"], WINDOW_IDS, SEASONS, WINDOWS):
        if (window["id"] != identity or window["season"] != season or (window["start"], window["end"]) != expected):
            raise ValueError("Changed fixed test calendar")
        start, end = shared.instant(window["start"]), shared.instant(window["end"])
        if end - start != timedelta(days=28):
            raise ValueError("Need a 28-day window")
        # The upstream queries include both endpoints: equal endpoints also overlap.
        if any(start <= old_end and end >= old_start for old_start, old_end in seen):
            raise ValueError("New test window overlaps previously inspected measurements")
        expected_origins = int(((end - timedelta(hours=1)) - (start + timedelta(hours=5.5))).total_seconds() / 1800) + 1
        if expected_origins != spec["eligibility"]["expectedOriginsPerWindow"]:
            raise ValueError("Wrong complete-grid denominator")
    screen = spec["eligibility"]
    u, decision, evaluation = spec["uncertainty"], spec["decision"], spec["evaluation"]
    if (evaluation["methods"] != ["persistence", "same-frozen-ridge-without-fallback", "same-frozen-ridge-with-fallback"] or
            evaluation["primaryBaseline"] != "persistence" or
            evaluation["mechanismBaseline"] != "same-frozen-ridge-without-fallback" or
            evaluation["primaryMetric"] != "MAE in mg/L on identical accepted origin-target pairs" or
            evaluation["futureTargetGroupingPermittedForPrediction"] is not False or
            evaluation["removeLargeErrorsPermitted"] is not False or evaluation["clipPredictionsPermitted"] is not False):
        raise ValueError("Changed fixed comparisons or evaluation boundaries")
    if (screen["minimumAcceptedPairsPerWindow"] != 1000 or screen["minimumExpectedGridCoveragePerWindow"] != .9 or
            u["primaryBlockHours"] != 48 or u["sensitivityBlockHours"] != [24, 72] or
            u["sensitivityLowerBoundsAreRequired"] is not True or u["iterations"] != 5000 or
            u["baseSeed"] != 20261014 or u["confidenceFraction"] != .95 or
            u["minimumNonemptyBlocksPerSeason"] != 4 or decision["numericalToleranceMgL"] != 1e-9 or
            decision["tenPercentIsAcceptanceGate"] is not False or
            decision["practicalEnvironmentalBenefitDefined"] is not False or decision["operationalPromotion"] is not False):
        raise ValueError("Changed predeclared completeness, uncertainty or decision settings")


def preflight(root=ROOT):
    root = Path(root).resolve()
    raw = (root / PROTOCOL).read_bytes()
    spec = json.loads(raw)
    seen = previous_windows(root)
    validate_definition(spec, seen)
    for path, expected in ((spec["baseModel"]["file"], MODEL_HASH),
                           (spec["baseModel"]["protocolFile"], BASE_PROTOCOL_HASH)):
        if shared.digest((root / path).read_bytes()) != expected:
            raise ValueError("Frozen model or original protocol bytes changed")
    existing = [w["id"] for w in spec["testWindows"] if (root / PROTOCOL.parent / w["id"]).exists()]
    if existing:
        raise ValueError("This pre-capture phase cannot claim unseen windows when captures already exist")
    return {"protocolVerified": True, "protocolHash": shared.digest(raw),
            "stationId": spec["stationId"], "horizonSeconds": 3600,
            "previouslyInspectedWindowsChecked": len(seen),
            "newWindows": spec["testWindows"], "expectedOriginsPerWindow": 1332,
            "frozenModelHash": MODEL_HASH, "newModelFitted": False,
            "newTestValuesAcquired": False, "forecastSkillEvaluated": False,
            "captureAndEvaluationRunnerImplemented": False,
            "scope": "Protocol and synthetic rule checks only; new-window source quality remains unknown"}


if __name__ == "__main__":
    print(json.dumps(preflight(), indent=2))
