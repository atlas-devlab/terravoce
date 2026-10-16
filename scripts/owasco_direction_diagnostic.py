"""Offline, fixed two-hour direction diagnostic on two already-open Owasco months.

Uses saved predictions, not model prediction code. No network, fitting, threshold
search or bootstrap is present. All methods retain every accepted source row.
"""
import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_FILE = "docs/datasets/owasco-direction-diagnostic/protocol.json"
PROTOCOL_SHA256 = "438b66c99e1ed602ea572d15442e309c82be5972307619e1e63d37702c69d2bd"
PROPOSAL_SHA256 = "7e8e5c572d46fefda1c676c4083a523ccabfe3b84e2699ed1253094b23e1990b"
VERSION = "owasco-two-hour-direction-diagnostic-v1"
P = "persistence"
R = "same-frozen-ridge-without-fallback"
F = "small-correction-filter"
S = "two-hour-direction-selector"
METHODS = (P, R, F, S)
FEATURES = ["oxygenNow", "oxygenDelta30m", "oxygenDelta2h", "oxygenDelta5h30m",
            "clockSinUTC", "clockCosUTC", "temperatureNow", "temperatureDelta2h"]
TOL = 1e-9  # Development continuation/recomposition only, never signs or bins.
BINS = [("B1", "[0,0.025)"), ("B2", "[0.025,0.050)"),
        ("B3", "[0.050,0.075)"), ("B4", "[0.075,0.100]"),
        ("B5", "(0.100,+infinity)"), ("invalid", "undefined correction")]
SIGN_NAMES = {-1: "negative", 0: "zero", 1: "positive", None: "invalid"}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def number(value, label):
    if not finite(value):
        raise ValueError("Missing or nonfinite numeric field: " + label)
    return value


def instant(value):
    if not isinstance(value, str):
        raise ValueError("UTC timestamp required")
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.utcoffset() != timedelta(0):
        raise ValueError("UTC timezone required")
    return stamp


def reject_constant(value):
    raise ValueError("Non-standard JSON numeric constant: " + value)


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def loads(raw):
    return json.loads(raw, object_pairs_hook=no_duplicates, parse_constant=reject_constant)


def sign(value):
    if not finite(value):
        return None
    return 1 if value > 0 else -1 if value < 0 else 0


def select_prediction(persistence, ridge, two_hour_change):
    """Only information available at the origin; no actual/target argument.

    Return the selected number unchanged. Invalid R is not silently rescued by P.
    Finite negative R is allowed to route, then explicitly fails if selected.
    """
    if not finite(persistence) or persistence < 0 or not finite(two_hour_change):
        return {"selectedMethod": "invalid", "predictionMgL": None,
                "correctionMgL": None, "valid": False}
    if not finite(ridge):
        return {"selectedMethod": "invalid", "predictionMgL": None,
                "correctionMgL": None, "valid": False}
    correction = ridge - persistence
    if not finite(correction):
        return {"selectedMethod": "invalid", "predictionMgL": None,
                "correctionMgL": None, "valid": False}
    use_r = ((two_hour_change > 0 and correction > 0) or
             (two_hour_change < 0 and correction < 0))
    value = ridge if use_r else persistence
    return {"selectedMethod": R if use_r else P, "predictionMgL": value,
            "correctionMgL": correction, "valid": finite(value) and value >= 0}


def correction_bin(value):
    if not finite(value):
        return "invalid"
    score = abs(value)
    if score < .025:
        return "B1"
    if score < .050:
        return "B2"
    if score < .075:
        return "B3"
    return "B4" if score <= .100 else "B5"


def check_close(left, right, label):
    if not (finite(left) and finite(right)) or abs(left - right) > TOL:
        raise ValueError("Recomposition failed: " + label)


def validate_row(row, index, start, end):
    if not isinstance(row, dict):
        raise ValueError("Source row is not an object")
    origin, target = instant(row.get("origin")), instant(row.get("target"))
    if target - origin != timedelta(hours=1):
        raise ValueError("Target differs from exact one-hour horizon")
    offset = (origin - start).total_seconds()
    if offset < 19800 or target > end or offset % 1800 != 0:
        raise ValueError("Origin differs from frozen source-window grid")
    actual = number(row.get("actual"), "actual")
    if actual < 0:
        raise ValueError("Negative observed oxygen")
    history, features, predictions = (row.get(k) for k in ("oxygenHistory", "features", "predictionsMgL"))
    if not isinstance(history, list) or len(history) != 12:
        raise ValueError("Exactly twelve oxygen history samples required")
    values = []
    for j, item in enumerate(history):
        if not isinstance(item, dict) or instant(item.get("timeUTC")) != origin - timedelta(minutes=30*(11-j)):
            raise ValueError("Oxygen history differs from exact half-hour grid")
        v = number(item.get("value"), "oxygenHistory")
        if v < 0:
            raise ValueError("Negative observed oxygen history")
        values.append(v)
    if not isinstance(features, list) or len(features) != 8 or not all(finite(x) for x in features):
        raise ValueError("Eight finite frozen-order features required")
    expected = [values[-1], values[-1]-values[-2], values[-1]-values[-5], values[-1]-values[0]]
    if features[:4] != expected:
        raise ValueError("Saved oxygen features disagree with exact history")
    clock = (origin.hour*3600 + origin.minute*60 + origin.second)/86400*2*math.pi
    # This integrity comparison tolerates math-library last bits; routing does not.
    if abs(features[4]-math.sin(clock)) > 1e-12 or abs(features[5]-math.cos(clock)) > 1e-12:
        raise ValueError("Saved UTC-clock features disagree with origin")
    if not isinstance(predictions, dict) or any(m not in predictions for m in (P, R, F)):
        raise ValueError("Missing saved baseline, ridge or old-filter prediction")
    p = number(predictions[P], "saved P")
    if p != values[-1]:
        raise ValueError("Saved P differs from last oxygen history measurement")
    d = values[-1] - values[-5]
    route = select_prediction(p, predictions[R], d)
    c = route["correctionMgL"]
    if finite(predictions[R]) and finite(c):
        old_expected = p if abs(c) <= .1 else predictions[R]
        if predictions[F] != old_expected:
            raise ValueError("Saved old F differs from exact frozen 0.100 gate")
    elif predictions[F] is not None:
        raise ValueError("Nonfinite saved R requires original invalid F marker")
    preds = {P: p, R: predictions[R], F: predictions[F], S: route["predictionMgL"]}
    errors = {m: abs(v-actual) if finite(v) and finite(v-actual) else None for m, v in preds.items()}
    gains = {m: errors[P]-errors[m] if errors[m] is not None else None for m in METHODS}
    sg = SIGN_NAMES[sign(d)] + "_" + SIGN_NAMES[sign(c)]
    old_active = finite(c) and abs(c) > .1
    selected = route["selectedMethod"] == R
    comparison = ("invalid" if route["selectedMethod"] == "invalid" else
                  "both_ridge" if selected and old_active else "candidate_only_ridge" if selected
                  else "old_filter_only_ridge" if old_active else "both_persistence")
    return {"sourceRowIndex": index, "origin": row["origin"], "target": row["target"], "actual": actual,
            "oxygenHistory": history, "features": features, "twoHourChangeMgL": d,
            "ridgeCorrectionMgL": c, "signGroup": sg, "amplitudeBin": correction_bin(c),
            "selectedMethod": route["selectedMethod"], "candidateValid": route["valid"],
            "invalidRawRidge": not finite(predictions[R]) or predictions[R] < 0,
            "comparatorRoutingGroup": comparison,
            "predictionsMgL": {m: v if finite(v) else None for m, v in preds.items()},
            "absoluteErrorsMgL": errors, "gainsAgainstPersistenceMgL": gains}


def summarize(rows, denominator):
    n = len(rows)
    summaries = {}
    for method in METHODS:
        errors = [r["absoluteErrorsMgL"][method] for r in rows]
        gains = [r["gainsAgainstPersistenceMgL"][method] for r in rows]
        valid = all(v is not None for v in errors+gains)
        if valid:
            total_error, total_gain = math.fsum(errors), math.fsum(gains)
            wins, ties, losses = (sum(g > 0 for g in gains), sum(g == 0 for g in gains), sum(g < 0 for g in gains))
            positive, negative = math.fsum(g for g in gains if g > 0), math.fsum(-g for g in gains if g < 0)
            summaries[method] = {"count": n, "sumAbsoluteErrorMgL": total_error,
                "maeMgL": total_error/n if n else None, "sumGainMgL": total_gain,
                "meanGainMgL": total_gain/n if n else None,
                "globalGainContributionMgL": total_gain/denominator,
                "wins": wins, "ties": ties, "losses": losses,
                "positiveGainMagnitudeMgL": positive, "negativeGainMagnitudeMgL": negative,
                "invalidErrorCount": 0}
        else:
            summaries[method] = {"count": n, "sumAbsoluteErrorMgL": None, "maeMgL": None,
                "sumGainMgL": None, "meanGainMgL": None, "globalGainContributionMgL": None,
                "wins": None, "ties": None, "losses": None,
                "positiveGainMagnitudeMgL": None, "negativeGainMagnitudeMgL": None,
                "invalidErrorCount": sum(v is None for v in errors)}
    return {"count": n, "globalDenominator": denominator,
            "chooseRCount": sum(r["selectedMethod"] == R for r in rows),
            "choosePCount": sum(r["selectedMethod"] == P for r in rows),
            "invalidCandidateCount": sum(not r["candidateValid"] for r in rows),
            "invalidRawRidgeCount": sum(r["invalidRawRidge"] for r in rows), "methods": summaries}


def check_partition(parts, overall):
    if sum(p["count"] for p in parts) != overall["count"]:
        raise ValueError("Partition changed the identical full-cohort denominator")
    for m in METHODS:
        for key in ("sumAbsoluteErrorMgL", "sumGainMgL", "positiveGainMagnitudeMgL", "negativeGainMagnitudeMgL"):
            value = overall["methods"][m][key]
            if value is not None:
                check_close(math.fsum(p["methods"][m][key] for p in parts), value, "partition "+m+key)


def occupancy(rows, start):
    days = sorted({r["origin"][:10] for r in rows})
    daily = [{"originDayUTC": day, "acceptedPairs": sum(r["origin"].startswith(day) for r in rows),
              "activations": sum(r["origin"].startswith(day) and r["selectedMethod"] == R for r in rows)} for day in days]
    result = {"originDays": daily, "activeDayCount": sum(d["activations"] > 0 for d in daily), "blocks": {}}
    for hours in (24, 48, 72):
        indices = sorted({int((instant(r["origin"])-start).total_seconds()//(hours*3600)) for r in rows})
        blocks = []
        for idx in indices:
            chosen = [r for r in rows if int((instant(r["origin"])-start).total_seconds()//(hours*3600)) == idx]
            blocks.append({"blockIndex": idx, "startUTC": (start+timedelta(hours=hours*idx)).isoformat().replace("+00:00", "Z"),
                           "acceptedPairs": len(chosen), "activations": sum(r["selectedMethod"] == R for r in chosen)})
        result["blocks"][str(hours)] = {"blockHours": hours, "anchorUTC": start.isoformat().replace("+00:00", "Z"),
            "occupiedBlockCount": len(blocks), "activeBlockCount": sum(b["activations"] > 0 for b in blocks), "items": blocks}
    return result


def analyze_month(source, binding):
    rows = source.get("rows")
    if not isinstance(rows, list) or len(rows) != binding["pairs"] or not rows:
        raise ValueError("Saved cohort differs from the bound row count")
    if source.get("stationId") != "USGS-425327076313601" or source.get("horizonSeconds") != 3600:
        raise ValueError("Source station or horizon differs")
    if any(source.get("window", {}).get(k) != binding["window"][k] for k in ("start", "end")):
        raise ValueError("Source window differs from adopted binding")
    start, end = (instant(binding["window"][k]) for k in ("start", "end"))
    analyzed = [validate_row(r, i, start, end) for i, r in enumerate(rows)]
    stamps = [instant(r["origin"]) for r in analyzed]
    if stamps != sorted(set(stamps)):
        raise ValueError("Saved origins must be unique and increasing, without deduplication")
    n = len(analyzed)
    overall = summarize(analyzed, n)
    refs = {}
    for m in (P, R, F):
        score = source.get("scores", {}).get(m)
        computed = overall["methods"][m]["maeMgL"]
        if computed is None:
            if score is not None:
                raise ValueError("Saved invalid-comparator score must be null")
            refs[m] = None
        else:
            if not isinstance(score, dict) or score.get("pairs") != n:
                raise ValueError("Saved comparator score/denominator missing")
            refs[m] = score.get("maeMgL")
            check_close(number(refs[m], "saved MAE"), overall["methods"][m]["maeMgL"], "saved "+m+" MAE")
    groups = {d+"_"+c: summarize([r for r in analyzed if r["signGroup"] == d+"_"+c], n)
              for d in ("negative", "zero", "positive") for c in ("negative", "zero", "positive", "invalid")}
    selection = {key: summarize([r for r in analyzed if r["selectedMethod"] == value], n)
                 for key, value in (("selectedR", R), ("retainedP", P), ("invalid", "invalid"))}
    bins = [{"id": key, "interval": label,
             **summarize([r for r in analyzed if r["amplitudeBin"] == key], n),
             "selectedR": summarize([r for r in analyzed if r["amplitudeBin"] == key and r["selectedMethod"] == R], n)}
            for key, label in BINS]
    routing = {key: summarize([r for r in analyzed if r["comparatorRoutingGroup"] == key], n) for key in
               ("both_ridge", "candidate_only_ridge", "old_filter_only_ridge", "both_persistence", "invalid")}
    for partition in (list(groups.values()), list(selection.values()), bins, list(routing.values())):
        check_partition(partition, overall)
    for m in METHODS:
        metric = overall["methods"][m]
        if metric["meanGainMgL"] is not None:
            check_close(metric["meanGainMgL"], overall["methods"][P]["maeMgL"]-metric["maeMgL"], "full-cohort gain "+m)
    # Outcomes choose examples only AFTER origin-only routes; never used by route.
    predicates = {
        "selectedRImproves": lambda r: r["selectedMethod"] == R and r["gainsAgainstPersistenceMgL"][S] > 0,
        "selectedRWorsens": lambda r: r["selectedMethod"] == R and r["gainsAgainstPersistenceMgL"][S] < 0,
        "retainedPAvoidsRidgeLoss": lambda r: r["selectedMethod"] == P and r["gainsAgainstPersistenceMgL"][R] is not None and r["gainsAgainstPersistenceMgL"][R] < 0,
        "retainedPMissesRidgeGain": lambda r: r["selectedMethod"] == P and r["gainsAgainstPersistenceMgL"][R] is not None and r["gainsAgainstPersistenceMgL"][R] > 0}
    examples = {key: next((r["sourceRowIndex"] for r in analyzed if pred(r)), None) for key, pred in predicates.items()}
    mae_s = overall["methods"][S]["maeMgL"]
    gain = overall["methods"][P]["maeMgL"]-mae_s if mae_s is not None else None
    valid = overall["invalidCandidateCount"] == 0
    return {"id": binding["id"], "input": {k: binding[k] for k in ("file", "rawSha256", "pairs", "window")},
            "savedComparatorMAE": refs, "overall": overall, "originSignGroups": groups,
            "selectionGroups": selection, "fixedAmplitudeBins": bins, "oldFilterRoutingComparison": routing,
            "activationOccupancy": occupancy(analyzed, start), "posthocIllustrativeRowIndices": examples,
            "gainOverPersistenceMgL": gain,
            "candidateValidOnAllRows": valid,
            "developmentMonthPass": valid and gain is not None and gain > TOL,
            "checks": {"sameCohort": True, "allPartitionsRecompose": True,
                       "savedComparatorScoresPreserved": True, "historyGridAndOxygenFeaturesMatch": True,
                       "temperatureHistoryUnavailableInSavedRows": True}, "rows": analyzed}


def read_protocol(path, expected_sha256=PROTOCOL_SHA256, proposal_sha256=PROPOSAL_SHA256):
    raw = Path(path).read_bytes()
    if sha(raw) != expected_sha256:
        raise ValueError("Adopted protocol SHA-256 mismatch")
    spec = loads(raw)
    if (spec.get("version") != "owasco-direction-diagnostic-v1" or
            spec.get("status") != "ADOPTED_BEFORE_FIRST_SELECTOR_SCORE" or
            spec.get("proposalSHA256") != proposal_sha256 or
            spec.get("stationId") != "USGS-425327076313601" or
            spec.get("horizonSeconds") != 3600 or spec.get("features") != FEATURES or
            spec.get("continuation", {}).get("numericalToleranceMgL") != TOL or
            spec.get("continuation", {}).get("requireBothMonths") is not True):
        raise ValueError("Fixed direction protocol fields differ")
    instant(spec.get("adoptedAtUTC"))
    if not isinstance(spec.get("months"), list) or len(spec["months"]) != 2:
        raise ValueError("Exactly two adopted opened months required")
    return spec, sha(raw)


def bound_path(root, name):
    if not isinstance(name, str) or Path(name).is_absolute() or ".." in Path(name).parts:
        raise ValueError("Canonical repository-relative file required")
    path = (root/name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Bound file escapes repository")
    return path


def replay(root, protocol_file, protocol_sha256=PROTOCOL_SHA256, proposal_sha256=PROPOSAL_SHA256):
    root = Path(root).resolve()
    spec, digest = read_protocol(protocol_file, protocol_sha256, proposal_sha256)
    model_raw = bound_path(root, spec["model"]["file"]).read_bytes()
    if sha(model_raw) != spec["model"]["rawSha256"]:
        raise ValueError("Frozen model SHA-256 mismatch")
    model = loads(model_raw)
    if (model.get("recipe", {}).get("features") != FEATURES or
            model.get("recipe", {}).get("featureWidth") != 8 or
            model.get("recipe", {}).get("horizonSeconds") != 3600):
        raise ValueError("Frozen model recipe/order differs")
    months = []
    for binding in spec["months"]:
        raw = bound_path(root, binding["file"]).read_bytes()
        if sha(raw) != binding["rawSha256"]:
            raise ValueError("Saved evaluation SHA-256 mismatch: "+binding["id"])
        months.append(analyze_month(loads(raw), binding))
    return {"version": VERSION, "scope": "Descriptive development check on two already-open months; not new validation",
            "protocol": {"file": PROTOCOL_FILE, "sha256": digest, "adoptedAtUTC": spec["adoptedAtUTC"]},
            "proposalSHA256": proposal_sha256, "model": spec["model"],
            "implementation": {"file": "scripts/owasco_direction_diagnostic.py", "rawSha256": sha(Path(__file__).read_bytes())},
            "rule": "S=R iff (O(t)-O(t-2h)>0 and R-P>0) or both contrasts<0; otherwise P. No amplitude gate.",
            "definitions": {"gain": "absoluteErrorP-absoluteErrorMethod; positive is better than P",
                "denominators": "Each method uses the full common monthly N; group means use group count; contributions use monthly N",
                "zeroTwoHourChange": "No net change between endpoints, not a flat path or physically stable lake",
                "temperatureIntegrity": "All eight feature names/order checked against model; T features finite but archived rows have no temperatureHistory for independent reconstruction",
                "emptyGroups": "Counts/sums/contributions zero; within-group means null",
                "examples": "First chronological matching row, selected retrospectively after routing; illustrative, not causal or representative of frequency",
                "invalidity": "No rows dropped or invalid R rescued by P; finite negative unselected R stays numeric and only flags comparator invalidity"},
            "months": months,
            "developmentContinuation": {"rule": "All rows candidate-valid and MAE_P-MAE_S>1e-9 in BOTH months",
                "passed": all(m["developmentMonthPass"] for m in months),
                "meaning": "Prespecified conservative development screen only; neither future skill nor ecological benefit established",
                "septemberAuthorizedOrAcquired": False, "automaticModelChange": False},
            "limits": ["No training, new observations, threshold scan, bootstrap, inference or causal attribution.",
                "Archived finalized measurements do not establish as-of-origin availability or live performance.",
                "Occupancy counts are not numbers of independent observations.",
                "The frozen raw ridge and original filter outcomes are preserved; direction selector is a separate diagnostic candidate."]}


def compare_exact(stored, expected, path="report"):
    if type(stored) is not type(expected):
        raise ValueError("Saved report mismatch at "+path)
    if isinstance(expected, dict):
        if stored.keys() != expected.keys():
            raise ValueError("Saved report key mismatch at "+path)
        for key in expected:
            compare_exact(stored[key], expected[key], path+"."+key)
    elif isinstance(expected, list):
        if len(stored) != len(expected):
            raise ValueError("Saved report length mismatch at "+path)
        for i, (a, b) in enumerate(zip(stored, expected)):
            compare_exact(a, b, path+"["+str(i)+"]")
    elif (stored.hex() != expected.hex() if isinstance(expected, float) else stored != expected):
        raise ValueError("Saved report value mismatch at "+path)


def verify_report(root, protocol_file, report_file, protocol_sha256=PROTOCOL_SHA256, proposal_sha256=PROPOSAL_SHA256):
    raw = Path(report_file).read_bytes()
    stored = loads(raw)
    expected = replay(root, protocol_file, protocol_sha256, proposal_sha256)
    created = instant(stored.get("createdAtUTC"))
    if created < instant(expected["protocol"]["adoptedAtUTC"]):
        raise ValueError("Report creation metadata predates adoption")
    compare_exact({k: v for k, v in stored.items() if k != "createdAtUTC"}, expected)
    return {"verified": True, "writes": False, "reportSHA256": sha(raw)}


def run(root, protocol_file, output_dir, protocol_sha256=PROTOCOL_SHA256, proposal_sha256=PROPOSAL_SHA256):
    output = Path(output_dir)
    if output.exists():
        raise ValueError("Output directory already exists; overwrite forbidden")
    report = replay(root, protocol_file, protocol_sha256, proposal_sha256)
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
        print(json.dumps(result, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
        print("Stopped: "+str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
