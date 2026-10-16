"""Offline fixed attenuation diagnostic on the two already-open Owasco months.

Consumes saved P/R/F predictions. No fitting, model prediction, network access,
threshold search or new observations are part of this diagnostic.
"""
import argparse
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import owasco_direction_diagnostic as integrity

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_FILE = "docs/datasets/owasco-attenuation-diagnostic/protocol.json"
PROTOCOL_SHA256 = "b952df8d503c986e3b84567a5c81dfcf5eb21ca27cefe81f3aa1e6f5d5acb2c1"
DEPENDENCY_FILE = "scripts/owasco_direction_diagnostic.py"
DEPENDENCY_SHA256 = "cdcc85324dd68a13b09895b6808351e385e731d622d6a97f8793fbbf754e9a02"
VERSION = "owasco-fixed-attenuation-diagnostic-v1"
P, R, F = integrity.P, integrity.R, integrity.F
Q = "fixed-attenuated-correction"
METHODS = (P, R, F, Q)
FEATURES = integrity.FEATURES
THRESHOLD = .100
TOL = 1e-9  # Only development criterion/recomposition, never routing.
sha, encoded, loads = integrity.sha, integrity.encoded, integrity.loads
finite, number, instant = integrity.finite, integrity.number, integrity.instant
bound_path, compare_exact = integrity.bound_path, integrity.compare_exact
check_close, correction_bin = integrity.check_close, integrity.correction_bin
BINS = integrity.BINS


def attenuate_prediction(persistence, ridge):
    """Exact binary64 arithmetic in the adopted order; actual is not an input."""
    invalid = {"predictionMgL": None, "correctionMgL": None,
               "attenuatedCorrectionMgL": None, "gateActive": None,
               "predictionChangedFromPersistence": None, "valid": False}
    if not finite(persistence) or persistence < 0 or not finite(ridge):
        return invalid
    c = ridge-persistence
    if not finite(c):
        return invalid
    active = abs(c) > THRESHOLD
    if active:
        magnitude = abs(c)-THRESHOLD
        correction = magnitude if c > 0 else -magnitude
        value = persistence+correction
    else:
        correction, value = 0.0, persistence
    return {"predictionMgL": value if finite(value) else None, "correctionMgL": c,
            "attenuatedCorrectionMgL": correction, "gateActive": active,
            "predictionChangedFromPersistence": value != persistence if finite(value) else None,
            "valid": finite(value) and value >= 0}


def validate_row(row, index, start, end):
    if not isinstance(row, dict):
        raise ValueError("Source row is not an object")
    origin, target = instant(row.get("origin")), instant(row.get("target"))
    if target-origin != timedelta(hours=1):
        raise ValueError("Target differs from exact one-hour horizon")
    offset = (origin-start).total_seconds()
    if offset < 19800 or target > end or offset % 1800 != 0:
        raise ValueError("Origin differs from frozen source-window grid")
    actual = number(row.get("actual"), "actual")
    if actual < 0:
        raise ValueError("Negative observed oxygen")
    history, features, saved = (row.get(k) for k in ("oxygenHistory", "features", "predictionsMgL"))
    if not isinstance(history, list) or len(history) != 12:
        raise ValueError("Exactly twelve oxygen history samples required")
    values = []
    for j, item in enumerate(history):
        if not isinstance(item, dict) or instant(item.get("timeUTC")) != origin-timedelta(minutes=30*(11-j)):
            raise ValueError("Oxygen history differs from exact half-hour grid")
        value = number(item.get("value"), "oxygenHistory")
        if value < 0:
            raise ValueError("Negative observed oxygen history")
        values.append(value)
    if not isinstance(features, list) or len(features) != 8 or not all(finite(v) for v in features):
        raise ValueError("Eight finite frozen-order features required")
    expected = [values[-1], values[-1]-values[-2], values[-1]-values[-5], values[-1]-values[0]]
    if features[:4] != expected:
        raise ValueError("Saved oxygen features disagree with exact history")
    clock = (origin.hour*3600+origin.minute*60+origin.second)/86400*2*math.pi
    if abs(features[4]-math.sin(clock)) > 1e-12 or abs(features[5]-math.cos(clock)) > 1e-12:
        raise ValueError("Saved UTC-clock features disagree with origin")
    if not isinstance(saved, dict) or any(m not in saved for m in (P, R, F)):
        raise ValueError("Missing saved baseline, ridge or old-filter prediction")
    p, ridge, old = (saved[m] for m in (P, R, F))
    number(p, "saved P")
    if p != values[-1]:
        raise ValueError("Saved P differs from last oxygen history measurement")
    route = attenuate_prediction(p, ridge)
    c = route["correctionMgL"]
    if finite(p) and finite(ridge) and finite(c):
        if old != (p if abs(c) <= THRESHOLD else ridge):
            raise ValueError("Saved old F differs from exact frozen 0.100 gate")
    elif old is not None:
        raise ValueError("Invalid saved contrast requires original invalid F marker")
    preds = {P: p, R: ridge, F: old, Q: route["predictionMgL"]}
    errors = {m: abs(v-actual) if finite(v) and finite(v-actual) else None for m, v in preds.items()}
    gains = {m: errors[P]-errors[m] if errors[P] is not None and errors[m] is not None else None for m in METHODS}
    paired = errors[F]-errors[Q] if errors[F] is not None and errors[Q] is not None else None
    return {"sourceRowIndex": index, "origin": row["origin"], "target": row["target"], "actual": actual,
            "ridgeCorrectionMgL": c, "attenuatedCorrectionMgL": route["attenuatedCorrectionMgL"],
            "correctionSign": "invalid" if not finite(c) else "positive" if c > 0 else "negative" if c < 0 else "zero",
            "amplitudeBin": correction_bin(c), "gateActive": route["gateActive"],
            "predictionChangedFromPersistence": route["predictionChangedFromPersistence"],
            "candidateValid": route["valid"], "invalidRawRidge": not finite(ridge) or ridge < 0,
            "predictionsMgL": {m: v if finite(v) else None for m, v in preds.items()},
            "absoluteErrorsMgL": errors, "gainsAgainstPersistenceMgL": gains,
            "gainAgainstOldFilterMgL": paired}


def summarize(rows, denominator):
    n, methods = len(rows), {}
    for method in METHODS:
        errors = [r["absoluteErrorsMgL"][method] for r in rows]
        gains = [r["gainsAgainstPersistenceMgL"][method] for r in rows]
        if all(v is not None for v in errors+gains):
            total_error, total_gain = math.fsum(errors), math.fsum(gains)
            methods[method] = {"count": n, "sumAbsoluteErrorMgL": total_error,
                "maeMgL": total_error/n if n else None, "sumGainMgL": total_gain,
                "meanGainMgL": total_gain/n if n else None,
                "globalGainContributionMgL": total_gain/denominator,
                "wins": sum(g > 0 for g in gains), "ties": sum(g == 0 for g in gains),
                "losses": sum(g < 0 for g in gains),
                "positiveGainMagnitudeMgL": math.fsum(g for g in gains if g > 0),
                "negativeGainMagnitudeMgL": math.fsum(-g for g in gains if g < 0),
                "invalidErrorCount": 0}
        else:
            methods[method] = {"count": n, "sumAbsoluteErrorMgL": None, "maeMgL": None,
                "sumGainMgL": None, "meanGainMgL": None, "globalGainContributionMgL": None,
                "wins": None, "ties": None, "losses": None,
                "positiveGainMagnitudeMgL": None, "negativeGainMagnitudeMgL": None,
                "invalidErrorCount": sum(v is None for v in errors)}
    gains = [r["gainAgainstOldFilterMgL"] for r in rows]
    if all(v is not None for v in gains):
        total = math.fsum(gains)
        paired = {"count": n, "sumGainMgL": total, "meanGainMgL": total/n if n else None,
            "globalGainContributionMgL": total/denominator,
            "wins": sum(g > 0 for g in gains), "ties": sum(g == 0 for g in gains),
            "losses": sum(g < 0 for g in gains),
            "positiveGainMagnitudeMgL": math.fsum(g for g in gains if g > 0),
            "negativeGainMagnitudeMgL": math.fsum(-g for g in gains if g < 0), "invalidCount": 0}
    else:
        paired = {"count": n, "sumGainMgL": None, "meanGainMgL": None,
            "globalGainContributionMgL": None, "wins": None, "ties": None, "losses": None,
            "positiveGainMagnitudeMgL": None, "negativeGainMagnitudeMgL": None,
            "invalidCount": sum(v is None for v in gains)}
    return {"count": n, "globalDenominator": denominator,
            "gateActiveCount": sum(r["gateActive"] is True for r in rows),
            "retainedPCount": sum(r["gateActive"] is False for r in rows),
            "invalidRoutingCount": sum(r["gateActive"] is None for r in rows),
            "changedPredictionCount": sum(r["predictionChangedFromPersistence"] is True for r in rows),
            "gateActiveButUnchangedCount": sum(r["gateActive"] is True and r["predictionChangedFromPersistence"] is False for r in rows),
            "invalidCandidateCount": sum(not r["candidateValid"] for r in rows),
            "invalidRawRidgeCount": sum(r["invalidRawRidge"] for r in rows),
            "methods": methods, "candidateAgainstOldFilter": paired}


def check_partition(parts, overall):
    if sum(p["count"] for p in parts) != overall["count"]:
        raise ValueError("Partition changed the common monthly denominator")
    for method in METHODS:
        for key in ("sumAbsoluteErrorMgL", "sumGainMgL", "positiveGainMagnitudeMgL", "negativeGainMagnitudeMgL"):
            value = overall["methods"][method][key]
            if value is not None:
                check_close(math.fsum(p["methods"][method][key] for p in parts), value, "partition "+method+key)
    for key in ("sumGainMgL", "positiveGainMagnitudeMgL", "negativeGainMagnitudeMgL"):
        value = overall["candidateAgainstOldFilter"][key]
        if value is not None:
            check_close(math.fsum(p["candidateAgainstOldFilter"][key] for p in parts), value, "paired partition "+key)


def occupancy(rows, start):
    days = sorted({r["origin"][:10] for r in rows})
    daily = [{"originDayUTC": day, "acceptedPairs": sum(r["origin"].startswith(day) for r in rows),
              "gateActiveCount": sum(r["origin"].startswith(day) and r["gateActive"] is True for r in rows)} for day in days]
    result = {"originDays": daily, "activeDayCount": sum(day["gateActiveCount"] > 0 for day in daily), "blocks": {}}
    for hours in (24, 48, 72):
        indices = sorted({int((instant(r["origin"])-start).total_seconds()//(hours*3600)) for r in rows})
        blocks = []
        for index in indices:
            chosen = [r for r in rows if int((instant(r["origin"])-start).total_seconds()//(hours*3600)) == index]
            blocks.append({"blockIndex": index, "startUTC": (start+timedelta(hours=hours*index)).isoformat().replace("+00:00", "Z"),
                           "acceptedPairs": len(chosen), "gateActiveCount": sum(r["gateActive"] is True for r in chosen)})
        result["blocks"][str(hours)] = {"blockHours": hours, "anchorUTC": start.isoformat().replace("+00:00", "Z"),
            "occupiedBlockCount": len(blocks), "activeBlockCount": sum(b["gateActiveCount"] > 0 for b in blocks), "items": blocks}
    return result


def analyze_month(source, binding):
    original = source.get("rows")
    if not isinstance(original, list) or not original or len(original) != binding["pairs"]:
        raise ValueError("Saved cohort differs from bound row count")
    if source.get("stationId") != "USGS-425327076313601" or source.get("horizonSeconds") != 3600:
        raise ValueError("Source station or horizon differs")
    if any(source.get("window", {}).get(k) != binding["window"][k] for k in ("start", "end")):
        raise ValueError("Source window differs from adopted binding")
    start, end = (instant(binding["window"][k]) for k in ("start", "end"))
    rows = [validate_row(r, i, start, end) for i, r in enumerate(original)]
    stamps = [instant(r["origin"]) for r in rows]
    if stamps != sorted(set(stamps)):
        raise ValueError("Saved origins must be unique and increasing")
    n, refs = len(rows), {}
    overall = summarize(rows, n)
    for method in (P, R, F):
        score = source.get("scores", {}).get(method)
        computed = overall["methods"][method]["maeMgL"]
        if computed is None:
            if score is not None:
                raise ValueError("Saved invalid-comparator score must be null")
            refs[method] = None
        else:
            if not isinstance(score, dict) or score.get("pairs") != n:
                raise ValueError("Saved comparator denominator missing")
            refs[method] = number(score.get("maeMgL"), "saved MAE")
            check_close(refs[method], computed, "saved "+method+" MAE")
    selection = {key: summarize([r for r in rows if r["gateActive"] is active], n)
                 for key, active in (("active", True), ("retainedP", False), ("invalid", None))}
    signs = {key: summarize([r for r in rows if r["correctionSign"] == key], n)
             for key in ("negative", "zero", "positive", "invalid")}
    bins = [{"id": key, "interval": label, **summarize([r for r in rows if r["amplitudeBin"] == key], n)}
            for key, label in BINS]
    outcome = {key: summarize([r for r in rows if r["gateActive"] is True and
               (r["gainAgainstOldFilterMgL"] is not None and sign_test(r["gainAgainstOldFilterMgL"]))], n)
               for key, sign_test in (("attenuationHelpsOldF", lambda x: x > 0),
                                      ("attenuationWorsensOldF", lambda x: x < 0),
                                      ("attenuationTiesOldF", lambda x: x == 0))}
    outcome["retainedP"] = selection["retainedP"]
    outcome["invalid"] = summarize([r for r in rows if r["gateActive"] is None or
                                   (r["gateActive"] is True and r["gainAgainstOldFilterMgL"] is None)], n)
    for parts in (selection.values(), signs.values(), bins, outcome.values()):
        check_partition(list(parts), overall)
    for method in METHODS:
        value = overall["methods"][method]
        if value["meanGainMgL"] is not None:
            check_close(value["meanGainMgL"], overall["methods"][P]["maeMgL"]-value["maeMgL"], "gain "+method)
    paired = overall["candidateAgainstOldFilter"]["meanGainMgL"]
    if paired is not None:
        check_close(paired, overall["methods"][F]["maeMgL"]-overall["methods"][Q]["maeMgL"], "paired gain")
    old_active = [i for i, r in enumerate(original) if finite(r["predictionsMgL"][R]) and
                  finite(r["predictionsMgL"][P]) and finite(r["predictionsMgL"][R]-r["predictionsMgL"][P]) and
                  abs(r["predictionsMgL"][R]-r["predictionsMgL"][P]) > THRESHOLD]
    active = [r["sourceRowIndex"] for r in rows if r["gateActive"] is True]
    if old_active != active:
        raise ValueError("Attenuation changed the original filter gate origins")
    predicates = {"candidateHelpsP": lambda r: r["gainsAgainstPersistenceMgL"][Q] is not None and r["gainsAgainstPersistenceMgL"][Q] > 0,
                  "candidateWorsensP": lambda r: r["gainsAgainstPersistenceMgL"][Q] is not None and r["gainsAgainstPersistenceMgL"][Q] < 0,
                  "attenuationHelpsOldF": lambda r: r["gateActive"] is True and r["gainAgainstOldFilterMgL"] is not None and r["gainAgainstOldFilterMgL"] > 0,
                  "attenuationWorsensOldF": lambda r: r["gateActive"] is True and r["gainAgainstOldFilterMgL"] is not None and r["gainAgainstOldFilterMgL"] < 0}
    examples = {key: next((r["sourceRowIndex"] for r in rows if pred(r)), None) for key, pred in predicates.items()}
    mae_q, mae_p = (overall["methods"][m]["maeMgL"] for m in (Q, P))
    gain = mae_p-mae_q if mae_p is not None and mae_q is not None else None
    valid = overall["invalidCandidateCount"] == 0
    contexts = [{"sourceRowIndex": i, "oxygenHistory": original[i]["oxygenHistory"],
                 "features": original[i]["features"], "row": rows[i]} for i in active]
    return {"id": binding["id"], "input": {k: binding[k] for k in ("file", "rawSha256", "pairs", "window")},
            "savedComparatorMAE": refs, "overall": overall, "selectionGroups": selection,
            "originCorrectionSignGroups": signs, "fixedAmplitudeBins": bins,
            "attenuationOutcomeGroups": outcome, "posthocIllustrativeRowIndices": examples,
            "activationOccupancy": occupancy(rows, start),
            "allGateActiveContexts": contexts, "gainOverPersistenceMgL": gain,
            "candidateValidOnAllRows": valid, "developmentMonthPass": valid and gain is not None and gain > TOL,
            "checks": {"sameCohort": True, "allPartitionsRecompose": True, "savedComparatorScoresPreserved": True,
                       "sameGateActiveOriginsAsOldF": True, "historyGridAndOxygenFeaturesMatch": True,
                       "temperatureHistoryUnavailableInSavedRows": True}, "rows": rows}


def read_protocol(path, expected_sha256=PROTOCOL_SHA256):
    raw = Path(path).read_bytes()
    if sha(raw) != expected_sha256:
        raise ValueError("Adopted protocol SHA-256 mismatch")
    spec = loads(raw)
    if (spec.get("version") != "owasco-attenuation-diagnostic-v1" or
            spec.get("status") != "ADOPTED_BEFORE_FIRST_ATTENUATION_SCORE" or
            spec.get("stationId") != "USGS-425327076313601" or spec.get("horizonSeconds") != 3600 or
            spec.get("features") != FEATURES or spec.get("rule", {}).get("thresholdMgL") != THRESHOLD or
            spec.get("continuation", {}).get("numericalToleranceMgL") != TOL or
            spec.get("continuation", {}).get("requireBothMonths") is not True or
            spec.get("dependencies") != [{"file": DEPENDENCY_FILE, "rawSha256": DEPENDENCY_SHA256}]):
        raise ValueError("Fixed attenuation protocol fields differ")
    instant(spec.get("adoptedAtUTC"))
    if not isinstance(spec.get("months"), list) or len(spec["months"]) != 2:
        raise ValueError("Exactly two adopted opened months required")
    return spec, sha(raw)


def replay(root, protocol_file, protocol_sha256=PROTOCOL_SHA256):
    root = Path(root).resolve()
    spec, digest = read_protocol(protocol_file, protocol_sha256)
    dependency = bound_path(root, DEPENDENCY_FILE).read_bytes()
    if sha(dependency) != DEPENDENCY_SHA256 or sha(Path(integrity.__file__).read_bytes()) != DEPENDENCY_SHA256:
        raise ValueError("Read-only integrity dependency SHA-256 mismatch")
    model_raw = bound_path(root, spec["model"]["file"]).read_bytes()
    if sha(model_raw) != spec["model"]["rawSha256"]:
        raise ValueError("Frozen model SHA-256 mismatch")
    model = loads(model_raw)
    if (model.get("recipe", {}).get("features") != FEATURES or
            model.get("recipe", {}).get("featureWidth") != 8 or model.get("recipe", {}).get("horizonSeconds") != 3600):
        raise ValueError("Frozen model recipe/order differs")
    months = []
    for binding in spec["months"]:
        raw = bound_path(root, binding["file"]).read_bytes()
        if sha(raw) != binding["rawSha256"]:
            raise ValueError("Saved evaluation SHA-256 mismatch: "+binding["id"])
        months.append(analyze_month(loads(raw), binding))
    return {"version": VERSION, "scope": "Descriptive development check on two already-open months; not new validation",
            "protocol": {"file": PROTOCOL_FILE, "sha256": digest, "adoptedAtUTC": spec["adoptedAtUTC"]},
            "model": spec["model"], "dependencies": spec["dependencies"],
            "implementation": {"file": "scripts/owasco_attenuation_diagnostic.py", "rawSha256": sha(Path(__file__).read_bytes())},
            "rule": "c=R-P; if abs(c)<=0.100 Q=P; otherwise magnitude=abs(c)-0.100, signed by c, then Q=P+signed magnitude. Exact binary64 operation order.",
            "definitions": {"gain": "absoluteErrorP-absoluteErrorMethod; positive is better than P",
                "pairedGain": "absoluteErrorOldF-absoluteErrorQ; positive means attenuation helped relative to old F",
                "denominators": "All methods retain full common monthly N; group means use group count and contributions monthly N",
                "gate": "Same strict amplitude gate as old F; gateActive may be true while Q rounds to P",
                "emptyGroups": "Counts/sums/contributions zero, within-group means null",
                "examples": "First chronological matching row chosen retrospectively; no influence on prediction or candidate choice",
                "rowContext": "Every row binds sourceRowIndex to input raw SHA; complete histories/features repeated only for all active origins",
                "invalidity": "No row drops or rescue; invalid candidate blocks continuation; finite negative raw R remains scored and flagged even when Q is nonnegative",
                "temperatureIntegrity": "Frozen feature names/order checked; temperature features finite but archived rows lack temperatureHistory"},
            "months": months,
            "developmentContinuation": {"rule": "All rows candidate-valid and MAE_P-MAE_Q>1e-9 in BOTH months",
                "passed": all(m["developmentMonthPass"] for m in months),
                "meaning": "Conservative development screen, not statistical significance, future validation or ecological benefit",
                "septemberAuthorizedOrAcquired": False, "automaticModelChange": False},
            "limits": ["No fit, model-prediction recomputation, new observations, threshold scan, bootstrap or causal inference.",
                "Finalized archived measurements do not establish real-time as-of-origin availability.",
                "Published equal readings and decimal precision do not establish physical stability or sensor accuracy.",
                "Original P/R/F and previous directional diagnostic evidence remain unchanged."]}


def verify_report(root, protocol_file, report_file, protocol_sha256=PROTOCOL_SHA256):
    raw = Path(report_file).read_bytes()
    stored = loads(raw)
    expected = replay(root, protocol_file, protocol_sha256)
    if instant(stored.get("createdAtUTC")) < instant(expected["protocol"]["adoptedAtUTC"]):
        raise ValueError("Report creation metadata predates adoption")
    compare_exact({k: v for k, v in stored.items() if k != "createdAtUTC"}, expected)
    return {"verified": True, "writes": False, "reportSHA256": sha(raw)}


def run(root, protocol_file, output_dir, protocol_sha256=PROTOCOL_SHA256):
    output = Path(output_dir)
    if output.exists():
        raise ValueError("Output directory already exists; overwrite forbidden")
    report = replay(root, protocol_file, protocol_sha256)
    report["createdAtUTC"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if instant(report["createdAtUTC"]) < instant(report["protocol"]["adoptedAtUTC"]):
        raise ValueError("Report creation predates adoption")
    raw = encoded(report)
    output.mkdir(parents=True, exist_ok=False)
    target = output/"diagnostic.json"
    with target.open("xb") as handle:
        handle.write(raw)
    return {"file": str(target.resolve()), "sha256": sha(raw),
            "developmentContinuationPassed": report["developmentContinuation"]["passed"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output-dir", type=Path)
    mode.add_argument("--verify-report", type=Path)
    args = parser.parse_args(argv)
    try:
        result = (verify_report(ROOT, args.protocol, args.verify_report) if args.verify_report is not None
                  else run(ROOT, args.protocol, args.output_dir))
        print(encoded(result).decode("utf-8").strip())
        return 0
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
        print("Stopped: "+str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
