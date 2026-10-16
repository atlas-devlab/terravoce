"""Post-score arithmetic audit of the fixed, already-open Owasco direction check.

Standalone standard-library replay of saved P/R/F and targets; no production
selector imports, forecast recomputation, fitting or network access. The core
arithmetic is preserved from the separate reviewer's original outside helper.
Default output is compact JSON on stdout only. An explicit --output writes that
same JSON once, refusing overwrite. Repository lookup is independent of cwd:

    python -B scripts/audit_owasco_direction.py
    python -B /path/to/scripts/audit_owasco_direction.py --repo /path/to/repo

This auxiliary script was added after scoring; it is not part of the pre-score
freeze and does not establish environmental or temporal validation.
"""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FREEZE = "docs/evidence/owasco-direction-diagnostic/freeze-before-score.json"
PROTOCOL = "docs/datasets/owasco-direction-diagnostic/protocol.json"
REPORT = "docs/evidence/owasco-direction-diagnostic/diagnostic.json"
P, R, F, S = ("persistence", "same-frozen-ridge-without-fallback",
              "small-correction-filter", "two-hour-direction-selector")
METHODS = (P, R, F, S)
EPS = 1e-12
CHECKS = 0
FAILURES = []
MAX_DIFFERENCE = 0.0


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def utc(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def finite(x):
    return type(x) in (int, float) and math.isfinite(x)


def verify(actual, expected, label, exact=False):
    global CHECKS, MAX_DIFFERENCE
    CHECKS += 1
    if isinstance(expected, dict):
        ok = isinstance(actual, dict) and actual.keys() == expected.keys()
        if ok:
            for key in expected:
                verify(actual[key], expected[key], label + "." + key, exact)
            return
    elif isinstance(expected, list):
        ok = isinstance(actual, list) and len(actual) == len(expected)
        if ok:
            for i, (a, b) in enumerate(zip(actual, expected)):
                verify(a, b, label + "[" + str(i) + "]", exact)
            return
    elif type(expected) is bool or expected is None or isinstance(expected, str):
        ok = type(actual) is type(expected) and actual == expected
    elif type(expected) is int:
        ok = type(actual) is int and actual == expected
    elif isinstance(expected, float):
        difference = abs(actual - expected) if finite(actual) else math.inf
        if math.isfinite(difference):
            MAX_DIFFERENCE = max(MAX_DIFFERENCE, difference)
        ok = finite(actual) and (actual == expected if exact else difference <= EPS)
    else:
        ok = actual == expected
    if not ok and len(FAILURES) < 30:
        FAILURES.append({"path": label, "actual": actual, "expected": expected})


def phase(x):
    return "invalid" if not finite(x) else "positive" if x > 0 else "negative" if x < 0 else "zero"


def bin_id(c):
    if c is None:
        return "invalid"
    a = abs(c)
    return "B1" if a < .025 else "B2" if a < .05 else "B3" if a < .075 else "B4" if a <= .1 else "B5"


def derive(raw, i):
    """Route using two past endpoints and saved R; actual is read afterwards."""
    p, r, f = (raw["predictionsMgL"][m] for m in (P, R, F))
    history = raw["oxygenHistory"]
    d = history[-1]["value"] - history[-5]["value"]
    c = r - p if finite(r) else None
    route_valid = finite(p) and p >= 0 and finite(d) and finite(c)
    use_r = route_valid and ((d > 0 and c > 0) or (d < 0 and c < 0))
    selected = R if use_r else P if route_valid else "invalid"
    s = r if use_r else p if route_valid else None
    # Future target first enters arithmetic here, after routing is fixed.
    actual = raw["actual"]
    pred = dict(zip(METHODS, (p, r, f, s)))
    err = {m: abs(x - actual) if finite(x) else None for m, x in pred.items()}
    gain = {m: err[P] - e if e is not None else None for m, e in err.items()}
    old_active = finite(c) and abs(c) > .1
    comparison = "invalid" if not route_valid else (
        "both_ridge" if use_r and old_active else "candidate_only_ridge" if use_r else
        "old_filter_only_ridge" if old_active else "both_persistence")
    verify(p, history[-1]["value"], "source.P.history." + str(i), exact=True)
    verify(d, raw["features"][2], "source.d2h.feature." + str(i), exact=True)
    verify(f, r if old_active else p, "source.oldF.rule." + str(i), exact=True)
    verify(utc(raw["target"]) - utc(raw["origin"]) == timedelta(hours=1), True,
           "source.oneHour." + str(i))
    return {"sourceRowIndex": i, "origin": raw["origin"], "target": raw["target"],
            "actual": actual, "oxygenHistory": history, "features": raw["features"],
            "twoHourChangeMgL": d, "ridgeCorrectionMgL": c,
            "signGroup": phase(d) + "_" + phase(c), "amplitudeBin": bin_id(c),
            "selectedMethod": selected, "candidateValid": finite(s) and s >= 0,
            "invalidRawRidge": not finite(r) or r < 0, "comparatorRoutingGroup": comparison,
            "predictionsMgL": pred, "absoluteErrorsMgL": err, "gainsAgainstPersistenceMgL": gain}


def stats(rows, full_n):
    n, methods = len(rows), {}
    for m in METHODS:
        errors = [r["absoluteErrorsMgL"][m] for r in rows]
        gains = [r["gainsAgainstPersistenceMgL"][m] for r in rows]
        invalid = sum(x is None for x in errors)
        valid = invalid == 0
        total_e, total_g = (math.fsum(errors), math.fsum(gains)) if valid else (None, None)
        methods[m] = {"count": n, "sumAbsoluteErrorMgL": total_e,
            "maeMgL": total_e/n if valid and n else None, "sumGainMgL": total_g,
            "meanGainMgL": total_g/n if valid and n else None,
            "globalGainContributionMgL": total_g/full_n if valid else None,
            "wins": sum(g > 0 for g in gains) if valid else None,
            "ties": sum(g == 0 for g in gains) if valid else None,
            "losses": sum(g < 0 for g in gains) if valid else None,
            "positiveGainMagnitudeMgL": math.fsum(g for g in gains if g > 0) if valid else None,
            "negativeGainMagnitudeMgL": math.fsum(-g for g in gains if g < 0) if valid else None,
            "invalidErrorCount": invalid}
    return {"count": n, "globalDenominator": full_n,
            "chooseRCount": sum(r["selectedMethod"] == R for r in rows),
            "choosePCount": sum(r["selectedMethod"] == P for r in rows),
            "invalidCandidateCount": sum(not r["candidateValid"] for r in rows),
            "invalidRawRidgeCount": sum(r["invalidRawRidge"] for r in rows), "methods": methods}


def occupied(rows, start):
    accepted_days = Counter(r["origin"][:10] for r in rows)
    active_days = Counter(r["origin"][:10] for r in rows if r["selectedMethod"] == R)
    result = {"originDays": [{"originDayUTC": day, "acceptedPairs": n,
              "activations": active_days[day]} for day, n in sorted(accepted_days.items())],
              "activeDayCount": len(active_days), "blocks": {}}
    for hours in (24, 48, 72):
        accepted, active = Counter(), Counter()
        for row in rows:
            k = int((utc(row["origin"]) - start).total_seconds() // (hours*3600))
            accepted[k] += 1
            active[k] += row["selectedMethod"] == R
        items = [{"blockIndex": k, "startUTC": (start + timedelta(hours=k*hours)).isoformat().replace("+00:00", "Z"),
                  "acceptedPairs": n, "activations": active[k]} for k, n in sorted(accepted.items())]
        result["blocks"][str(hours)] = {"blockHours": hours,
            "anchorUTC": start.isoformat().replace("+00:00", "Z"), "occupiedBlockCount": len(items),
            "activeBlockCount": sum(n > 0 for n in active.values()), "items": items}
    return result


def audit_month(source, saved, binding, protocol):
    label, n = binding["id"], binding["pairs"]
    verify(len(source["rows"]), n, label + ".N")
    verify({k: source["window"][k] for k in ("start", "end")}, binding["window"], label + ".sourceWindow")
    rows = [derive(raw, i) for i, raw in enumerate(source["rows"])]
    verify(saved["rows"], rows, label + ".rows", exact=True)
    verify([r["origin"] for r in rows], sorted(set(r["origin"] for r in rows)), label + ".uniqueOrderedOrigins")
    overall = stats(rows, n)
    verify(saved["overall"], overall, label + ".overall")
    verify(overall["chooseRCount"] + overall["choosePCount"], n, label + ".routingDenominator")
    partitions = []
    for report_key, row_key in (("originSignGroups", "signGroup"), ("oldFilterRoutingComparison", "comparatorRoutingGroup")):
        groups = {key: stats([r for r in rows if r[row_key] == key], n) for key in saved[report_key]}
        verify(saved[report_key], groups, label + "." + report_key)
        partitions.append(list(groups.values()))
    selection = {key: stats([r for r in rows if r["selectedMethod"] == method], n)
                 for key, method in (("selectedR", R), ("retainedP", P), ("invalid", "invalid"))}
    verify(saved["selectionGroups"], selection, label + ".selectionGroups")
    partitions.append(list(selection.values()))
    bins = []
    for b in protocol["fixedBins"] + [{"id": "invalid"}]:
        group = [r for r in rows if r["amplitudeBin"] == b["id"]]
        entry = stats(group, n)
        # Labels are metadata; numeric membership uses the fixed protocol intervals above.
        stored = next(item for item in saved["fixedAmplitudeBins"] if item["id"] == b["id"])
        entry.update(id=b["id"], interval=stored["interval"], selectedR=stats([r for r in group if r["selectedMethod"] == R], n))
        bins.append(entry)
    verify(saved["fixedAmplitudeBins"], bins, label + ".fixedAmplitudeBins")
    partitions.append(bins)
    for i, partition in enumerate(partitions):
        verify(sum(p["count"] for p in partition), n, label + ".partitionN." + str(i))
        for method in METHODS:
            for key in ("sumAbsoluteErrorMgL", "sumGainMgL", "positiveGainMagnitudeMgL", "negativeGainMagnitudeMgL"):
                value = overall["methods"][method][key]
                if value is not None:
                    verify(math.fsum(p["methods"][method][key] for p in partition), value,
                           label + ".recomposition." + str(i) + "." + method + "." + key)
    for method in METHODS:
        metric = overall["methods"][method]
        verify(metric["meanGainMgL"], overall["methods"][P]["maeMgL"] - metric["maeMgL"], label + ".gainIdentity." + method)
        verify(metric["wins"] + metric["ties"] + metric["losses"], n, label + ".WTL.N." + method)
        verify(metric["positiveGainMagnitudeMgL"] - metric["negativeGainMagnitudeMgL"], metric["sumGainMgL"], label + ".gainSigns." + method)
        if method != S:
            verify(source["scores"][method]["pairs"], n, label + ".savedN." + method)
            verify(metric["maeMgL"], source["scores"][method]["maeMgL"], label + ".savedMAE." + method)
            verify(saved["savedComparatorMAE"][method], source["scores"][method]["maeMgL"], label + ".referenceMAE." + method)
    examples = {"selectedRImproves": None, "selectedRWorsens": None,
                "retainedPAvoidsRidgeLoss": None, "retainedPMissesRidgeGain": None}
    for row in rows:
        selected = row["selectedMethod"] == R
        ridge_gain = row["gainsAgainstPersistenceMgL"][R]
        key = ("selectedRImproves" if ridge_gain > 0 else "selectedRWorsens" if ridge_gain < 0 else None) if selected else (
            "retainedPAvoidsRidgeLoss" if ridge_gain < 0 else "retainedPMissesRidgeGain" if ridge_gain > 0 else None)
        if key and examples[key] is None:
            examples[key] = row["sourceRowIndex"]
    verify(saved["posthocIllustrativeRowIndices"], examples, label + ".firstChronologicalExamples")
    occupancy = occupied(rows, utc(binding["window"]["start"]))
    verify(saved["activationOccupancy"], occupancy, label + ".activationOccupancy")
    gain = overall["methods"][P]["maeMgL"] - overall["methods"][S]["maeMgL"]
    valid = overall["invalidCandidateCount"] == 0
    passed = valid and gain > protocol["continuation"]["numericalToleranceMgL"]
    verify(saved["gainOverPersistenceMgL"], gain, label + ".gain")
    verify(saved["candidateValidOnAllRows"], valid, label + ".validity")
    verify(saved["developmentMonthPass"], passed, label + ".continuation")
    retained = selection["retainedP"]["methods"][R]
    return {"id": label, "N": n, "overall": overall, "gainOverPersistenceMgL": gain,
        "developmentMonthPass": passed, "retainedP": {"count": selection["retainedP"]["count"],
        "missedRidgeGainCount": retained["wins"], "missedRidgeGainSumMgL": retained["positiveGainMagnitudeMgL"],
        "avoidedRidgeLossCount": retained["losses"], "avoidedRidgeLossSumMgL": retained["negativeGainMagnitudeMgL"]},
        "oldFilterRoutingComparison": saved["oldFilterRoutingComparison"],
        "firstChronologicalExamples": examples, "activationOccupancy": occupancy}



def main(argv=None):
    global REPO, CHECKS, FAILURES, MAX_DIFFERENCE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO,
                        help="Repository root; default is this script's parent repository")
    parser.add_argument("--output", type=Path,
                        help="Optional new JSON file; default writes only stdout")
    args = parser.parse_args(argv)
    REPO = args.repo.resolve()
    CHECKS, FAILURES, MAX_DIFFERENCE = 0, [], 0.0
    if args.output is not None and args.output.exists():
        raise FileExistsError("Audit result already exists")
    protocol, report = load(REPO / PROTOCOL), load(REPO / REPORT)
    freeze = load(REPO / FREEZE)
    verify(digest(REPO / REPORT), "4820b19a9df12356721d5466bacc9c985ce54db162a9d73b68ee0459d9c0b93e", "report.rawSHA256")
    verify(digest(REPO / PROTOCOL), "438b66c99e1ed602ea572d15442e309c82be5972307619e1e63d37702c69d2bd", "protocol.rawSHA256")
    verify(digest(REPO / FREEZE), "093ca3edc0720a21c51e2c4db594088cf7042eb4bdab59e5d52901f1cfcb0e61", "freeze.rawSHA256")
    for file, expected in freeze["files"].items():
        verify(digest(REPO / file), expected, "freeze.file." + file)
    verify(freeze["freezeCommit"], "b8b350c6c92ecc15bbb6ccdffc449755f3ff92af", "freeze.commit")
    verify(freeze["realSelectorScoringPerformed"], False, "freeze.preScoreFlag")
    verify(utc(report["createdAtUTC"]) >= utc(freeze["frozenAtUTC"]) >= utc(protocol["adoptedAtUTC"]), True, "receipt.chronology")
    verify(report["protocol"]["sha256"], digest(REPO / PROTOCOL), "report.protocolBinding")
    verify(report["implementation"]["rawSha256"], digest(REPO / report["implementation"]["file"]), "report.implementationBinding")
    verify(digest(REPO / protocol["model"]["file"]), protocol["model"]["rawSha256"], "model.rawHashOnly")
    verify(report["model"], protocol["model"], "report.modelBinding")
    months = []
    verify(len(report["months"]), len(protocol["months"]), "monthCount")
    for binding in protocol["months"]:
        verify(digest(REPO / binding["file"]), binding["rawSha256"], "source.hash." + binding["id"])
    if not FAILURES:
        for binding in protocol["months"]:
            source = load(REPO / binding["file"])
            saved = next(m for m in report["months"] if m["id"] == binding["id"])
            months.append(audit_month(source, saved, binding, protocol))
        decision = all(m["developmentMonthPass"] for m in months)
        verify(report["developmentContinuation"]["passed"], decision, "jointContinuation")
    else:
        decision = None
    compact_months = []
    for month in months:
        overall = month["overall"]
        compact_months.append({
            "id": month["id"], "N": month["N"],
            "chooseRCount": overall["chooseRCount"], "choosePCount": overall["choosePCount"],
            "invalidCandidateCount": overall["invalidCandidateCount"],
            "invalidRawRidgeCount": overall["invalidRawRidgeCount"],
            "methods": overall["methods"],
            "gainOverPersistenceMgL": month["gainOverPersistenceMgL"],
            "developmentMonthPass": month["developmentMonthPass"],
            "retainedP": month["retainedP"],
            "oldFilterRoutingComparison": {
                key: {"count": value["count"],
                      "candidateSumGainMgL": value["methods"][S]["sumGainMgL"],
                      "oldFilterSumGainMgL": value["methods"][F]["sumGainMgL"]}
                for key, value in month["oldFilterRoutingComparison"].items()},
            "firstChronologicalExamples": month["firstChronologicalExamples"],
            "activationOccupancy": {
                "activeDayCount": month["activationOccupancy"]["activeDayCount"],
                "occupiedDayCount": len(month["activationOccupancy"]["originDays"]),
                "blocks": {hours: {
                    "activeBlockCount": block["activeBlockCount"],
                    "occupiedBlockCount": block["occupiedBlockCount"],
                    "anchorUTC": block["anchorUTC"]}
                    for hours, block in month["activationOccupancy"]["blocks"].items()}}
        })
    result = {
        "version": "owasco-direction-portable-arithmetic-review-v1",
        "createdAtUTC": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "reviewTiming": "POST_SCORE_AUXILIARY_REVIEW_NOT_IN_PRE_SCORE_FREEZE",
        "status": "PASS" if not FAILURES else "FAIL",
        "checks": CHECKS, "failures": FAILURES,
        "arithmeticComparisonToleranceMgL": EPS,
        "maximumNumericDifferenceMgL": MAX_DIFFERENCE,
        "exactPerRowRoutingAndSavedValues": bool(months) and not FAILURES,
        "auditedRows": sum(m["N"] for m in months),
        "productionSelectorImported": False,
        "auditScript": "scripts/audit_owasco_direction.py",
        "auditScriptSHA256": digest(Path(__file__)),
        "preservedOutsideHelperSHA256": "5d30c41266490ef9356f0a45970dfee0c1665eca6fa8456088971f6dd336107a",
        "report": REPORT, "reportSHA256": digest(REPO / REPORT),
        "protocol": PROTOCOL, "protocolSHA256": digest(REPO / PROTOCOL),
        "sourceBindings": protocol["months"],
        "freezeReceipt": FREEZE, "freezeReceiptSHA256": digest(REPO / FREEZE),
        "months": compact_months,
        "developmentContinuationPassed": decision,
        "limits": [
            "Internal same-Codex-family arithmetic review, not independent environmental validation.",
            "Post-score auxiliary audit; not part of the protocol/code frozen before the first candidate score.",
            "No R recomputation, fit, new observations, new period, threshold search or alternative selector.",
            "July/August are opened development months; arithmetic does not establish temporal generalization, causal or ecological effects, as-of-origin availability or live performance.",
            "Freeze chronology is consistent with the preserved receipt and file hashes; the remote push was not independently queried by this offline audit.",
            "Temperature histories and measurement QA/QC are not independently validated.",
            "Every daily/block item is audited, but stdout summarizes occupancy; empty/invalid handling is exercised only where encountered in the saved artifacts.",
            "The stdout result is not an authenticated timestamp or an independent certificate."
        ]
    }
    serialized = json.dumps(result, ensure_ascii=False, allow_nan=False,
                            separators=(",", ":")) + "\n"
    if args.output is not None:
        with args.output.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized)
    sys.stdout.buffer.write(serialized.encode("utf-8"))
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    raise SystemExit(main())
