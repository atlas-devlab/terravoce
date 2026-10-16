"""Post-score internal arithmetic audit of fixed Owasco attenuation.

Only the Python standard library and bound saved artifacts are used. No
production functions, model forecasts, network, fitting or alternative rules.
Default: compact UTF-8 JSON on stdout, with no file writes. --output explicitly
creates one new result file without overwrite. --repo is independent of cwd.
The fixed freeze receipt defaults to its public evidence location; before its
publication, --freeze-receipt may supply the identical hash-bound receipt.
This auxiliary audit was written after scoring, not in the pre-score freeze.
"""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

DEFAULT_REPO = Path(__file__).resolve().parents[1]
PROTOCOL = "docs/datasets/owasco-attenuation-diagnostic/protocol.json"
REPORT = "docs/evidence/owasco-attenuation-diagnostic/diagnostic.json"
FREEZE = "docs/evidence/owasco-attenuation-diagnostic/freeze-before-score.json"
PROTOCOL_SHA = "b952df8d503c986e3b84567a5c81dfcf5eb21ca27cefe81f3aa1e6f5d5acb2c1"
REPORT_SHA = "0a5dad4d240073028fc05d5671a86a36fe567e0b79a0a888e70f34c7d270974c"
FREEZE_SHA = "c31c7a81f77ea42b52805ed7b23d623193109401a6a2a3767fbfae0e028ed39d"
P, R, F, Q = ("persistence", "same-frozen-ridge-without-fallback",
              "small-correction-filter", "fixed-attenuated-correction")
METHODS = (P, R, F, Q)
EPS = 1e-12  # Audit aggregation tolerance only; never routing or outcome signs.
BINS = {"B1": "[0,0.025)", "B2": "[0.025,0.050)", "B3": "[0.050,0.075)",
        "B4": "[0.075,0.100]", "B5": "(0.100,+infinity)", "invalid": "undefined correction"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def utc(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def finite(x):
    return type(x) in (int, float) and math.isfinite(x)


class Checks:
    def __init__(self):
        self.count, self.failed, self.largest = 0, [], 0.0

    def equal(self, got, wanted, path, exact=False):
        self.count += 1
        if isinstance(wanted, dict):
            good = isinstance(got, dict) and got.keys() == wanted.keys()
            if good:
                for key in wanted:
                    self.equal(got[key], wanted[key], path + "." + key, exact)
                return
        elif isinstance(wanted, list):
            good = isinstance(got, list) and len(got) == len(wanted)
            if good:
                for i, (a, b) in enumerate(zip(got, wanted)):
                    self.equal(a, b, path + "[" + str(i) + "]", exact)
                return
        elif type(wanted) is float:
            distance = abs(got-wanted) if finite(got) else math.inf
            if math.isfinite(distance):
                self.largest = max(self.largest, distance)
            good = finite(got) and (float(got).hex() == wanted.hex() if exact else distance <= EPS)
        else:
            good = type(got) is type(wanted) and got == wanted
        if not good and len(self.failed) < 30:
            self.failed.append({"field": path, "actual": got, "expected": wanted})


def label(x):
    return "invalid" if not finite(x) else "positive" if x > 0 else "negative" if x < 0 else "zero"


def amplitude(c):
    if not finite(c):
        return "invalid"
    a = abs(c)
    return "B1" if a < .025 else "B2" if a < .050 else "B3" if a < .075 else "B4" if a <= .100 else "B5"


def reconstruct(source_row, index, checks):
    # Route and attenuate before reading the target. Preserve adopted binary64 order.
    p, r, f = (source_row["predictionsMgL"][m] for m in (P, R, F))
    c = r-p if finite(r) and finite(p) else None
    defined = finite(p) and p >= 0 and finite(c)
    if defined:
        active = abs(c) > .100
        if active:
            h = abs(c)-.100
            h = h if c > 0 else -h
            q = p+h
        else:
            h, q = 0.0, p
    else:
        active = h = q = None
    changed = q != p if finite(q) else None
    valid = finite(q) and q >= 0
    y = source_row["actual"]
    checks.equal(f, r if active else p if defined else None, "source.oldF." + str(index), exact=True)
    origin = utc(source_row["origin"])
    checks.equal(utc(source_row["target"])-origin == timedelta(hours=1), True, "source.horizon."+str(index))
    history = source_row["oxygenHistory"]
    checks.equal(len(history), 12, "source.historyN."+str(index))
    for j, item in enumerate(history):
        checks.equal(utc(item["timeUTC"]) == origin-timedelta(minutes=30*(11-j)), True, "source.historyClock."+str(index)+"."+str(j))
        checks.equal(finite(item["value"]) and item["value"] >= 0, True, "source.historyValue."+str(index)+"."+str(j))
    values = [h["value"] for h in history]
    checks.equal(p, values[-1], "source.P."+str(index), exact=True)
    checks.equal(source_row["features"][:4], [values[-1], values[-1]-values[-2], values[-1]-values[-5], values[-1]-values[0]], "source.oxygenFeatures."+str(index), exact=True)
    checks.equal(finite(y) and y >= 0, True, "source.actual."+str(index))
    preds = dict(zip(METHODS, (p, r, f, q if finite(q) else None)))
    errors = {m: abs(v-y) if finite(v) and finite(v-y) else None for m, v in preds.items()}
    gains = {m: errors[P]-e if errors[P] is not None and e is not None else None for m, e in errors.items()}
    paired = errors[F]-errors[Q] if errors[F] is not None and errors[Q] is not None else None
    return {"sourceRowIndex": index, "origin": source_row["origin"], "target": source_row["target"], "actual": y,
        "ridgeCorrectionMgL": c, "attenuatedCorrectionMgL": h, "correctionSign": label(c),
        "amplitudeBin": amplitude(c), "gateActive": active, "predictionChangedFromPersistence": changed,
        "candidateValid": valid, "invalidRawRidge": not finite(r) or r < 0,
        "predictionsMgL": preds, "absoluteErrorsMgL": errors,
        "gainsAgainstPersistenceMgL": gains, "gainAgainstOldFilterMgL": paired}


def gain_summary(gains, n, denominator, invalid_key):
    invalid = sum(g is None for g in gains)
    good = invalid == 0
    total = math.fsum(gains) if good else None
    return {"count": n, "sumGainMgL": total, "meanGainMgL": total/n if good and n else None,
        "globalGainContributionMgL": total/denominator if good else None,
        "wins": sum(g > 0 for g in gains) if good else None,
        "ties": sum(g == 0 for g in gains) if good else None,
        "losses": sum(g < 0 for g in gains) if good else None,
        "positiveGainMagnitudeMgL": math.fsum(g for g in gains if g > 0) if good else None,
        "negativeGainMagnitudeMgL": math.fsum(-g for g in gains if g < 0) if good else None, invalid_key: invalid}


def summarize(rows, denominator):
    n, methods = len(rows), {}
    for method in METHODS:
        errors = [r["absoluteErrorsMgL"][method] for r in rows]
        gains = [r["gainsAgainstPersistenceMgL"][method] for r in rows]
        stats = gain_summary(gains, n, denominator, "invalidErrorCount")
        good = all(e is not None for e in errors+gains)
        total = math.fsum(errors) if good else None
        stats.update(sumAbsoluteErrorMgL=total, maeMgL=total/n if good and n else None)
        methods[method] = stats
    return {"count": n, "globalDenominator": denominator,
        "gateActiveCount": sum(r["gateActive"] is True for r in rows),
        "retainedPCount": sum(r["gateActive"] is False for r in rows),
        "invalidRoutingCount": sum(r["gateActive"] is None for r in rows),
        "changedPredictionCount": sum(r["predictionChangedFromPersistence"] is True for r in rows),
        "gateActiveButUnchangedCount": sum(r["gateActive"] is True and r["predictionChangedFromPersistence"] is False for r in rows),
        "invalidCandidateCount": sum(not r["candidateValid"] for r in rows),
        "invalidRawRidgeCount": sum(r["invalidRawRidge"] for r in rows),
        "methods": methods,
        "candidateAgainstOldFilter": gain_summary([r["gainAgainstOldFilterMgL"] for r in rows], n, denominator, "invalidCount")}


def partition_check(parts, overall, checks, name):
    checks.equal(sum(p["count"] for p in parts), overall["count"], name+".N")
    for method in METHODS:
        for key in ("sumAbsoluteErrorMgL", "sumGainMgL", "positiveGainMagnitudeMgL", "negativeGainMagnitudeMgL"):
            total = overall["methods"][method][key]
            if total is not None:
                checks.equal(math.fsum(p["methods"][method][key] for p in parts), total, name+"."+method+"."+key)
    for key in ("sumGainMgL", "positiveGainMagnitudeMgL", "negativeGainMagnitudeMgL"):
        total = overall["candidateAgainstOldFilter"][key]
        if total is not None:
            checks.equal(math.fsum(p["candidateAgainstOldFilter"][key] for p in parts), total, name+".vsF."+key)


def occupancy(rows, start):
    days = Counter(r["origin"][:10] for r in rows)
    active_days = Counter(r["origin"][:10] for r in rows if r["gateActive"] is True)
    result = {"originDays": [{"originDayUTC": day, "acceptedPairs": n, "gateActiveCount": active_days[day]} for day, n in sorted(days.items())],
        "activeDayCount": len(active_days), "blocks": {}}
    for hours in (24, 48, 72):
        accepted, active = Counter(), Counter()
        for row in rows:
            block = int((utc(row["origin"])-start).total_seconds()//(hours*3600))
            accepted[block] += 1
            active[block] += row["gateActive"] is True
        items = [{"blockIndex": k, "startUTC": (start+timedelta(hours=k*hours)).isoformat().replace("+00:00", "Z"),
                  "acceptedPairs": n, "gateActiveCount": active[k]} for k, n in sorted(accepted.items())]
        result["blocks"][str(hours)] = {"blockHours": hours, "anchorUTC": start.isoformat().replace("+00:00", "Z"),
            "occupiedBlockCount": len(items), "activeBlockCount": sum(n > 0 for n in active.values()), "items": items}
    return result


def month_audit(source, saved, binding, checks):
    name, n = binding["id"], binding["pairs"]
    checks.equal(len(source["rows"]), n, name+".N")
    checks.equal(source["stationId"], "USGS-425327076313601", name+".station")
    checks.equal(source["horizonSeconds"], 3600, name+".horizon")
    checks.equal({k: source["window"][k] for k in ("start", "end")}, binding["window"], name+".window")
    rows = [reconstruct(raw, i, checks) for i, raw in enumerate(source["rows"])]
    checks.equal(saved["rows"], rows, name+".rows", exact=True)
    checks.equal([r["origin"] for r in rows], sorted(set(r["origin"] for r in rows)), name+".uniqueOrderedOrigins")
    checks.equal(saved["input"], {k: binding[k] for k in ("file", "rawSha256", "pairs", "window")}, name+".inputBinding")
    overall = summarize(rows, n)
    checks.equal(saved["overall"], overall, name+".overall")
    checks.equal(overall["gateActiveCount"]+overall["retainedPCount"]+overall["invalidRoutingCount"], n, name+".routeN")
    active = [r["sourceRowIndex"] for r in rows if r["gateActive"] is True]
    old_active = [i for i, r in enumerate(source["rows"]) if finite(r["predictionsMgL"][R]) and abs(r["predictionsMgL"][R]-r["predictionsMgL"][P]) > .100]
    checks.equal(active, old_active, name+".sameOldFGateSet")
    selection = {k: summarize([r for r in rows if r["gateActive"] is flag], n) for k, flag in (("active", True), ("retainedP", False), ("invalid", None))}
    signs = {k: summarize([r for r in rows if r["correctionSign"] == k], n) for k in ("negative", "zero", "positive", "invalid")}
    bins = [{"id": k, "interval": text, **summarize([r for r in rows if r["amplitudeBin"] == k], n)} for k, text in BINS.items()]
    outcome = {}
    for group, direction in (("attenuationHelpsOldF", "positive"), ("attenuationWorsensOldF", "negative"), ("attenuationTiesOldF", "zero")):
        outcome[group] = summarize([r for r in rows if r["gateActive"] is True and label(r["gainAgainstOldFilterMgL"]) == direction], n)
    outcome["retainedP"] = selection["retainedP"]
    outcome["invalid"] = summarize([r for r in rows if r["gateActive"] is None or (r["gateActive"] is True and r["gainAgainstOldFilterMgL"] is None)], n)
    for key, wanted in (("selectionGroups", selection), ("originCorrectionSignGroups", signs), ("fixedAmplitudeBins", bins), ("attenuationOutcomeGroups", outcome)):
        checks.equal(saved[key], wanted, name+"."+key)
        partition_check(wanted if isinstance(wanted, list) else list(wanted.values()), overall, checks, name+".recompose."+key)
    cross = {}
    for p_sign in ("negative", "zero", "positive"):
        for f_sign in ("negative", "zero", "positive"):
            chosen = [r for r in rows if label(r["gainsAgainstPersistenceMgL"][Q]) == p_sign and label(r["gainAgainstOldFilterMgL"]) == f_sign]
            cross[p_sign+"_vsP__"+f_sign+"_vsOldF"] = summarize(chosen, n)
    # This is an additional descriptive audit table, never a prediction condition.
    partition_check(list(cross.values()), overall, checks, name+".expost3x3")
    for method in METHODS:
        metric = overall["methods"][method]
        if metric["meanGainMgL"] is not None:
            checks.equal(metric["meanGainMgL"], overall["methods"][P]["maeMgL"]-metric["maeMgL"], name+".gainIdentity."+method)
            checks.equal(metric["wins"]+metric["ties"]+metric["losses"], n, name+".WTL.N."+method)
        if method != Q:
            checks.equal(source["scores"][method]["pairs"], n, name+".originalScoreN."+method)
            checks.equal(metric["maeMgL"], source["scores"][method]["maeMgL"], name+".originalMAE."+method)
            checks.equal(saved["savedComparatorMAE"][method], source["scores"][method]["maeMgL"], name+".savedComparator."+method)
    checks.equal(overall["candidateAgainstOldFilter"]["meanGainMgL"], overall["methods"][F]["maeMgL"]-overall["methods"][Q]["maeMgL"], name+".pairedGainIdentity")
    examples = {"candidateHelpsP": None, "candidateWorsensP": None, "attenuationHelpsOldF": None, "attenuationWorsensOldF": None}
    for row in rows:
        g_p, g_f = row["gainsAgainstPersistenceMgL"][Q], row["gainAgainstOldFilterMgL"]
        matches = {"candidateHelpsP": finite(g_p) and g_p > 0, "candidateWorsensP": finite(g_p) and g_p < 0,
            "attenuationHelpsOldF": row["gateActive"] is True and finite(g_f) and g_f > 0,
            "attenuationWorsensOldF": row["gateActive"] is True and finite(g_f) and g_f < 0}
        for key, yes in matches.items():
            if yes and examples[key] is None:
                examples[key] = row["sourceRowIndex"]
    checks.equal(saved["posthocIllustrativeRowIndices"], examples, name+".firstChronologicalExamples")
    occupied = occupancy(rows, utc(binding["window"]["start"]))
    checks.equal(saved["activationOccupancy"], occupied, name+".occupancy")
    contexts = [{"sourceRowIndex": i, "oxygenHistory": source["rows"][i]["oxygenHistory"], "features": source["rows"][i]["features"], "row": rows[i]} for i in active]
    checks.equal(saved["allGateActiveContexts"], contexts, name+".allActiveContexts", exact=True)
    valid = overall["invalidCandidateCount"] == 0
    gain = overall["methods"][P]["maeMgL"]-overall["methods"][Q]["maeMgL"]
    passed = valid and gain > 1e-9
    checks.equal(saved["candidateValidOnAllRows"], valid, name+".validity")
    checks.equal(saved["gainOverPersistenceMgL"], gain, name+".primaryGain")
    checks.equal(saved["developmentMonthPass"], passed, name+".decision")
    return {"id": name, "N": n, "overall": overall, "gainOverPersistenceMgL": gain,
        "developmentMonthPass": passed, "selectionGroups": selection, "attenuationOutcomeGroups": outcome,
        "descriptivePostTarget3x3": cross, "firstChronologicalExamples": examples,
        "activationOccupancy": {"activeDayCount": occupied["activeDayCount"], "occupiedDayCount": len(occupied["originDays"]),
            "blocks": {k: {"activeBlockCount": v["activeBlockCount"], "occupiedBlockCount": v["occupiedBlockCount"]} for k, v in occupied["blocks"].items()}},
        "allActiveContextsVerified": len(contexts)}


def audit(repo, freeze_path):
    checks = Checks()
    for file, expected in ((PROTOCOL, PROTOCOL_SHA), (REPORT, REPORT_SHA)):
        checks.equal(digest(repo/file), expected, "binding."+file)
    checks.equal(digest(freeze_path), FREEZE_SHA, "binding.freezeReceipt")
    protocol, report, freeze = load(repo/PROTOCOL), load(repo/REPORT), load(freeze_path)
    checks.equal(freeze["commit"], "c69f63ca3f5a8d2dad322cad53e3d1dcb32f7ac2", "freeze.commit")
    checks.equal(freeze["candidateEnvironmentalScoreExists"], False, "freeze.preScoreFlag")
    checks.equal(utc(report["createdAtUTC"]) >= utc(freeze["verifiedAtUTC"]) >= utc(protocol["adoptedAtUTC"]), True, "freeze.receiptChronology")
    for bound in freeze["files"]:
        checks.equal(digest(repo/bound["file"]), bound["sha256"], "freeze.file."+bound["file"])
    for bound in protocol["months"]+protocol["dependencies"]+[protocol["model"]]:
        checks.equal(digest(repo/bound["file"]), bound["rawSha256"], "input."+bound["file"])
    checks.equal(report["protocol"], {"file": PROTOCOL, "sha256": PROTOCOL_SHA, "adoptedAtUTC": protocol["adoptedAtUTC"]}, "report.protocol")
    checks.equal(report["implementation"]["rawSha256"], digest(repo/report["implementation"]["file"]), "report.implementation")
    checks.equal(report["model"], protocol["model"], "report.model")
    checks.equal(report["dependencies"], protocol["dependencies"], "report.dependencies")
    checks.equal(protocol["rule"]["thresholdMgL"], .100, "protocol.threshold")
    checks.equal(protocol["continuation"]["numericalToleranceMgL"], 1e-9, "protocol.decisionTolerance")
    months = []
    if not checks.failed:
        checks.equal(len(report["months"]), 2, "report.twoMonths")
        for bound in protocol["months"]:
            saved = next(m for m in report["months"] if m["id"] == bound["id"])
            months.append(month_audit(load(repo/bound["file"]), saved, bound, checks))
    decision = all(m["developmentMonthPass"] for m in months) if len(months) == 2 else None
    checks.equal(report["developmentContinuation"]["passed"], decision, "bothMonthDecision")
    return {"version": "owasco-attenuation-independent-arithmetic-review-v1",
        "createdAtUTC": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "reviewTiming": "POST_SCORE_AUXILIARY_REVIEW_NOT_IN_PRE_SCORE_FREEZE",
        "status": "PASS" if not checks.failed else "FAIL", "checks": checks.count, "failures": checks.failed,
        "arithmeticComparisonToleranceMgL": EPS, "maximumNumericDifferenceMgL": checks.largest,
        "exactBinary64PerRowReconstruction": bool(months) and not checks.failed,
        "auditedRows": sum(m["N"] for m in months), "productionFunctionsImported": False,
        "script": "scripts/audit_owasco_attenuation.py", "scriptSHA256": digest(Path(__file__)),
        "reportSHA256": REPORT_SHA, "protocolSHA256": PROTOCOL_SHA,
        "freezeReceiptSHA256": FREEZE_SHA, "freezeReceiptExpectedPublicLocation": FREEZE,
        "sourceBindings": protocol["months"], "months": months, "developmentContinuationPassed": decision,
        "limits": ["Internal separate Codex-family arithmetic review, not independent environmental validation.",
            "No production functions imported, R recomputed, training, new observations, new period, threshold scan, bootstrap or alternative forecast.",
            "The 3x3 cross-partition uses observed future targets only to explain outcomes; it is an auxiliary descriptive audit, not a frozen prediction rule or extra success condition.",
            "July/August are opened development archives; neither internal arithmetic agreement nor a positive development gain proves temporal generalization, ecological benefit or live as-of-origin availability.",
            "Freeze chronology is consistent with the preserved hash-bound receipt; its remote-push claim and creation timestamps are not independently authenticated by this offline audit.",
            "Temperature histories, sensor accuracy and measurement QA/QC are not independently validated; counts of overlapping rows/blocks are not independent environmental events.",
            "Invalid-handling coverage is limited to the values actually encountered here; synthetic boundary tests are separate."]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    parser.add_argument("--freeze-receipt", type=Path, help="Optional identical hash-bound receipt before publication")
    parser.add_argument("--output", type=Path, help="Optional new JSON file; no overwrite")
    args = parser.parse_args(argv)
    if args.output is not None and args.output.exists():
        raise FileExistsError("Output already exists")
    repo = args.repo.resolve()
    result = audit(repo, args.freeze_receipt or repo/FREEZE)
    raw = (json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(",", ":"))+"\n").encode("utf-8")
    if args.output is not None:
        with args.output.open("xb") as handle:
            handle.write(raw)
    sys.stdout.buffer.write(raw)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
