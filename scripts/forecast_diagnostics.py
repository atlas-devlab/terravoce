"""Offline diagnosis of the frozen one-hour forecast; no fitting or new skill claim."""
import argparse
import json
import math
from datetime import timedelta
from pathlib import Path

import experiment_multiseason as trial

shared = trial.shared
ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = Path("docs/datasets/willamette-hourly-diagnostics/protocol.json")
EVIDENCE = Path("docs/evidence/willamette-hourly-diagnostics/report.json")
TEST_WINDOWS = ("winter-2025", "spring-2025", "summer-2025", "autumn-2025")
TRAIN_WINDOWS = ("winter-2024", "spring-2024", "summer-2024", "autumn-2024")


def input_files():
    """Fixed local inputs, with byte commitments separate from the derived report."""
    files = [
        str(trial.DATA / "protocol.json"),
        str(trial.EVIDENCE / "frozen-model.json"),
        str(trial.EVIDENCE / "evaluation.json.gz"),
        str(trial.EVIDENCE / "summary.json"),
        "docs/evidence/willamette-forecast/forecast.json",
        "docs/datasets/usgs-willamette-training-audit/protocol.json",
    ]
    for folder, windows in ((trial.DATA, TEST_WINDOWS),
                           (Path("docs/datasets/usgs-willamette-training-audit"), TRAIN_WINDOWS)):
        for window in windows:
            files.extend(str(folder / window / filename) for filename in
                         ("manifest.json", "oxygen.json.gz", "temperature.json.gz", "discharge.json.gz"))
    return [filename.replace("\\", "/") for filename in files]


def load_protocol(root):
    raw = (root / PROTOCOL).read_bytes()
    spec = json.loads(raw)
    if (spec["version"] != "willamette-hourly-diagnostics-v1" or
            spec["stationId"] != "USGS-14211720" or spec["horizonSeconds"] != 3600 or
            spec["contextBeforeOriginMinutes"] != 330 or spec["contextAfterTargetMinutes"] != 180 or
            spec["sampleSpacingMinutes"] != 30 or spec["illustrativeLowTargetMgL"] != 5 or
            spec["diagnosticOnly"] is not True or spec["testWindowsAlreadyObserved"] is not True or
            spec["newFinalValidation"] is not False or
            [item["file"] for item in spec["inputs"]] != input_files()):
        raise ValueError("Changed fixed diagnostic protocol")
    for item in spec["inputs"]:
        if shared.digest((root / item["file"]).read_bytes()) != item["rawSha256"]:
            raise ValueError(f"Diagnostic input commitment mismatch: {item['file']}")
    return spec, shared.digest(raw)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def group_score(rows):
    if not rows:
        return {"pairs": 0, "model": None, "persistence": None}
    return {"pairs": len(rows),
            "model": shared.metrics(rows, [r["newPrediction"] for r in rows]),
            "persistence": shared.metrics(rows, [r["persistence"] for r in rows])}


def summarize_groups(rows, histories):
    """Target labels are retrospective groups, never a decision at forecast origin."""
    grouped = {"byTarget": {"unchanged": [], "changed": []},
               "byHistory": {"flat": [], "changing": []},
               "byHistoryAndTarget": {"flatUnchanged": [], "flatChanged": [],
                                      "changingUnchanged": [], "changingChanged": []}}
    origins = set()
    for row in rows:
        history = histories.get(row["origin"], [])
        if (len(history) != 12 or any(not finite(v) for v in history) or
                any(not finite(row[key]) for key in ("actual", "persistence", "newPrediction")) or
                row["actual"] < 0 or row["persistence"] < 0 or history[-1] != row["persistence"] or
                row["origin"] in origins or
                shared.instant(row["target"]) - shared.instant(row["origin"]) != timedelta(hours=1)):
            raise ValueError("Invalid diagnostic row or twelve-sample history")
        origins.add(row["origin"])
        target_group = "unchanged" if row["actual"] == row["persistence"] else "changed"
        # Inspect all twelve records, not just the three deltas in the model.
        history_group = "flat" if all(value == history[0] for value in history) else "changing"
        grouped["byTarget"][target_group].append(row)
        grouped["byHistory"][history_group].append(row)
        grouped["byHistoryAndTarget"][history_group + target_group.capitalize()].append(row)
    result = {"pairs": len(rows)} | {
        axis: {name: group_score(values) for name, values in groups.items()}
        for axis, groups in grouped.items()}
    # A decomposition must retain every example and reproduce the original MAEs.
    for axis in grouped:
        if sum(group["pairs"] for group in result[axis].values()) != len(rows):
            raise AssertionError("Diagnostic partition dropped rows")
        if rows:
            for name, values in (("model", [r["newPrediction"] for r in rows]),
                                 ("persistence", [r["persistence"] for r in rows])):
                rebuilt = sum(g["pairs"] * g[name]["maeMgL"] for g in result[axis].values() if g["pairs"]) / len(rows)
                shared.close(rebuilt, shared.metrics(rows, values)["maeMgL"], "partition MAE")
    return result


def contribution_breakdown(row, model, feature_names):
    """Exact additive decomposition of a fixed linear prediction, not causal effects."""
    trial.validate_model(model)
    if len(feature_names) != 8 or len(row["features"]) != 8 or any(not finite(v) for v in row["features"]):
        raise ValueError("Expected exactly eight finite frozen-model features")
    parts = []
    for j, name in enumerate(feature_names):
        standardized = (row["features"][j] - model["mean"][j]) / model["scale"][j]
        parts.append({"feature": name, "inputValue": row["features"][j],
                      "standardizedValue": standardized,
                      "contributionMgL": standardized * model["coefficients"][j]})
    correction = model["residualIntercept"] + sum(part["contributionMgL"] for part in parts)
    predicted = row["persistence"] + correction
    shared.close(predicted, row["newPrediction"], "reconstructed frozen prediction")
    return {"residualInterceptMgL": model["residualIntercept"], "contributions": parts,
            "totalCorrectionMgL": correction, "reconstructedPredictionMgL": predicted}


def load_sources(root, window, protocol):
    """Read exact audited values and preserve source record metadata, signs and gaps."""
    folder = root / trial.DATA / window["id"]
    manifest = json.loads((folder / "manifest.json").read_bytes())
    sources = {}
    for kind in trial.KINDS:
        source, spec = manifest["sources"][kind], protocol["sources"][kind]
        raw = shared.compressed_body(folder / source["file"])
        if shared.digest(raw) != source["rawSha256"]:
            raise ValueError("Context source hash mismatch")
        records, _ = shared.read_collection(raw, protocol["stationId"], spec["parameterCode"],
            spec["timeSeriesId"], spec["unit"], shared.instant(window["start"]),
            shared.instant(window["end"]), spec["scale"])
        for feature in json.loads(raw)["features"]:
            props = feature["properties"]
            time = shared.instant(props["time"])
            if time in records:
                records[time] |= {"approvalStatus": props["approval_status"],
                                  "qualifier": props["qualifier"], "sourceValue": props["value"],
                                  "sourceUnit": spec["unit"],
                                  "valueUnit": "m3/s" if kind == "discharge" else spec["unit"]}
        sources[kind] = records
    return sources


def event_context(row, sources, window, spec):
    origin, target = shared.instant(row["origin"]), shared.instant(row["target"])
    if target - origin != timedelta(hours=1):
        raise ValueError("Context requires the fixed one-hour horizon")
    first = origin - timedelta(minutes=spec["contextBeforeOriginMinutes"])
    last = target + timedelta(minutes=spec["contextAfterTargetMinutes"])
    context = []
    time = first
    while time <= last:
        sample = {"timeUTC": shared.iso(time),
                  "minutesFromOrigin": int((time - origin).total_seconds() / 60),
                  "temporalRole": "history" if time <= origin else "future-diagnostic-only"}
        for kind in trial.KINDS:
            # Missing/qualified records remain absent; no interpolation or zero filling.
            sample[kind] = sources[kind].get(time)
        context.append(sample)
        time += timedelta(minutes=spec["sampleSpacingMinutes"])
    return {"originUTC": row["origin"], "targetUTC": row["target"],
            "observedTargetMgL": row["actual"], "forecastMgL": row["newPrediction"],
            "persistenceMgL": row["persistence"], "context": context,
            "contextExceedsArchiveWindow": first < shared.instant(window["start"]) or last > shared.instant(window["end"]),
            "historicalLiveAvailabilityEstablished": False,
            "physicalCauseEstablished": False}


def diagnose(root=ROOT):
    root = Path(root).resolve()
    spec, protocol_hash = load_protocol(root)
    # Existing replay checks model, raw sources, every pair, metrics and bootstrap.
    # It uses saved weights, never fit(), typescript_fit() or decimal_ridge().
    replay_difference = trial.verify_evaluation(root)
    p, frozen, _ = trial.frozen(root)
    report = json.loads(shared.compressed_body(root / trial.EVIDENCE / "evaluation.json.gz"))
    windows, events = [], []
    for saved_window in report["windows"]:
        window, rows = saved_window["window"], saved_window["rows"]
        sources = load_sources(root, window, p)
        histories, contributions = {}, []
        for row in rows:
            origin = shared.instant(row["origin"])
            timestamps = [origin - timedelta(minutes=30 * i) for i in range(11, -1, -1)]
            history = [sources["oxygen"][time] for time in timestamps]
            if [record["id"] for record in history] != row["evidence"]["oxygen"]:
                raise ValueError("Context/history evidence mismatch")
            histories[row["origin"]] = [record["value"] for record in history]
            contributions.append(contribution_breakdown(row, frozen["model"], p["model"]["features"]))
        groups = summarize_groups(rows, histories)
        windows.append({"window": window, "groups": groups,
                        "fullExpectedGrid": saved_window["fullExpectedGrid"],
                        "scores": {name: saved_window["scores"][name] for name in ("new", "persistence")},
                        "meanAbsoluteContributionsMgL": {
                            name: sum(abs(c["contributions"][j]["contributionMgL"]) for c in contributions) / len(rows)
                            for j, name in enumerate(p["model"]["features"])},
                        "residualInterceptMgL": frozen["model"]["residualIntercept"],
                        "pairsOutsideTrainingRange": saved_window["featureExtrapolation"]["pairs"]})
        for row, decomposition in zip(rows, contributions):
            if row["actual"] < spec["illustrativeLowTargetMgL"]:
                events.append({"windowId": window["id"], "targetRecordId": row["evidence"]["targetOxygen"],
                               "contributionBreakdown": decomposition,
                               **event_context(row, sources, window, spec)})
    return {"version": spec["version"], "diagnosticProtocolHash": protocol_hash,
            "inputs": spec["inputs"], "stationId": p["stationId"], "horizonSeconds": 3600,
            "sourceReplayMaximumDifference": replay_difference,
            "originalDecision": report["decision"], "macro": report["macro"],
            "windows": windows, "illustrativeLowTargetMgL": spec["illustrativeLowTargetMgL"],
            "events": events, "allScoredPairsRetained": sum(w["groups"]["pairs"] for w in windows),
            "contributionMeaning": "Additive terms in the frozen linear model; not physical causal effects",
            "contextUnits": {"oxygen": "mg/L", "temperature": "degC", "discharge": "m3/s; signed instantaneous flow retained"},
            "targetUsesFutureInformation": True,
            "targetGroupingMeaning": "Observed future target is used only for retrospective diagnosis, never for prediction or a selection gate",
            "historyGroupingMeaning": "Twelve archived oxygen values identical at/before origin; does not establish physical constancy or historical live availability",
            "modelFitted": False, "forecastSkillEstablished": False, "newFinalValidation": False,
            "operationalModelChanged": False, "fundingRelease": False,
            "limitations": [
                "Previously inspected 2025 windows are diagnostic/development data, not an unseen final test",
                "No record is removed or corrected to improve the score",
                "Future context is explanatory only and cannot be used at forecast origin",
                "Approved finalized source values and record modification times do not establish historical live availability or physical truth",
                "A signed flow reversal near an oxygen fall is a temporal association, not an established cause",
                "No wind, clouds, humidity, pollutant or human activity measurement enters this model",
                "The illustrative 5 mg/L filter selects examples; it is not a calibrated ecological/legal alert threshold",
                "This is a point-forecast diagnosis; no calibrated predictive interval or new model is produced"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "verify"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output.resolve() if args.output else root / EVIDENCE
    result = diagnose(root)
    if args.command == "run":
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("xb") as destination:
            destination.write(trial.encoded(result))
        print(json.dumps({"report": str(output), "pairs": result["allScoredPairsRetained"],
                          "events": len(result["events"]), "modelFitted": False,
                          "originalDecision": result["originalDecision"]}))
    else:
        difference = shared.compare_saved(result, json.loads(output.read_bytes()), "forecast diagnostics")
        print(json.dumps({"diagnosticsVerified": True, "maximumDifference": difference,
                          "pairs": result["allScoredPairsRetained"], "modelFitted": False}))


if __name__ == "__main__":
    main()
