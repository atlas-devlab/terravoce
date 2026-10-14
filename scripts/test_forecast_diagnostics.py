"""Frozen-model diagnostics: temporal boundaries, complete history and arithmetic."""
import copy
import json
import math
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import experiment_multiseason as trial
import forecast_diagnostics as diag


class ForecastDiagnosticTests(unittest.TestCase):
    def rows_and_histories(self):
        origins = [f"2025-01-01T{hour:02d}:00:00.000Z" for hour in (6, 7, 8, 9)]
        rows = [{"origin": origin, "target": f"2025-01-01T{hour + 1:02d}:00:00.000Z",
                 "actual": actual, "persistence": 10.0, "newPrediction": prediction,
                 "features": [10.0, 0.0, 0.0, 0.0, 0.0, 1.0, 15.0, 0.0],
                 "evidence": {"oxygen": [f"{hour}-{i}" for i in range(12)],
                              "targetOxygen": f"target-{hour}"}}
                for origin, hour, actual, prediction in zip(origins, (6, 7, 8, 9),
                                                           (10.0, 9.0, 10.0, 12.0),
                                                           (10.2, 9.6, 9.9, 11.5))]
        histories = {origin: [10.0] * 12 for origin in origins}
        # This interior change is invisible to the model's three oxygen deltas.
        # Full-history stability and target equality must remain distinct.
        histories[origins[2]][3] = 9.0
        histories[origins[3]][3] = 9.0
        return rows, histories

    def assert_metrics(self, metrics, mae, rmse, bias):
        self.assertAlmostEqual(metrics["maeMgL"], mae)
        self.assertAlmostEqual(metrics["rmseMgL"], rmse)
        self.assertAlmostEqual(metrics["biasMgL"], bias)

    def test_history_and_target_are_separate_and_partitions_reconstruct_errors(self):
        rows, histories = self.rows_and_histories()
        original = copy.deepcopy((rows, histories))
        result = diag.summarize_groups(rows, histories)
        self.assertEqual(result["pairs"], 4)
        self.assertEqual((rows, histories), original)
        self.assertEqual(result["byTarget"]["unchanged"]["pairs"], 2)
        self.assertEqual(result["byTarget"]["changed"]["pairs"], 2)
        self.assertEqual(result["byHistory"]["flat"]["pairs"], 2)
        self.assertEqual(result["byHistory"]["changing"]["pairs"], 2)
        expected = {"flatUnchanged": (.2, .2, .2, 0., 0., 0.),
                    "flatChanged": (.6, .6, .6, 1., 1., 1.),
                    "changingUnchanged": (.1, .1, -.1, 0., 0., 0.),
                    "changingChanged": (.5, .5, -.5, 2., 2., -2.)}
        for name, values in expected.items():
            with self.subTest(group=name):
                group = result["byHistoryAndTarget"][name]
                self.assertEqual(group["pairs"], 1)
                self.assert_metrics(group["model"], *values[:3])
                self.assert_metrics(group["persistence"], *values[3:])
        self.assert_metrics(result["byHistory"]["flat"]["model"], .4, math.sqrt(.2), .4)
        self.assert_metrics(result["byHistory"]["changing"]["model"], .3, math.sqrt(.13), -.3)
        for partition in ("byTarget", "byHistory", "byHistoryAndTarget"):
            groups = list(result[partition].values())
            self.assertEqual(sum(group["pairs"] for group in groups), 4)
            for method, expected_mae in (("model", .35), ("persistence", .75)):
                weighted_mae = sum(group["pairs"] * group[method]["maeMgL"] for group in groups) / 4
                self.assertAlmostEqual(weighted_mae, expected_mae)

    def test_empty_groups_have_no_fabricated_zero_error(self):
        result = diag.summarize_groups([], {})
        self.assertEqual(result["pairs"], 0)
        for partition in ("byTarget", "byHistory", "byHistoryAndTarget"):
            for group in result[partition].values():
                self.assertEqual(group["pairs"], 0)
                self.assertIsNone(group["model"])
                self.assertIsNone(group["persistence"])

    def test_rejects_incomplete_nonfinite_and_mismatched_histories(self):
        rows, histories = self.rows_and_histories()
        first = rows[0]["origin"]
        malformed = ([10.] * 11, [10.] * 13,
                     [float("nan")] + [10.] * 11,
                     [float("inf")] + [10.] * 11,
                     [10.] * 11 + [9.])
        for values in malformed:
            with self.subTest(history=values):
                changed = copy.deepcopy(histories)
                changed[first] = values
                with self.assertRaises(ValueError):
                    diag.summarize_groups(rows, changed)

    def test_eight_standardized_contributions_reconstruct_the_saved_prediction(self):
        names = [f"feature-{i}" for i in range(8)]
        model = {"alpha": 100, "mean": [1.] * 8, "scale": [2.] * 8,
                 "coefficients": [.1, -.2, .3, -.4, .5, -.6, .7, -.8],
                 "residualIntercept": .25}
        row = {"persistence": 10., "features": [3., -1., 5., -3., 7., -5., 9., -7.],
               "newPrediction": 21.25}
        # Standardized inputs are [1,-1,2,-2,3,-3,4,-4], giving a correction
        # of .25 + .1 + .2 + .6 + .8 + 1.5 + 1.8 + 2.8 + 3.2 = 11.25.
        original = copy.deepcopy((row, model))
        result = diag.contribution_breakdown(row, model, names)
        self.assertEqual((row, model), original)
        self.assertEqual(len(result["contributions"]), 8)
        self.assertEqual([c["feature"] for c in result["contributions"]], names)
        for contribution, value, standardized, expected in zip(
                result["contributions"], row["features"], (1., -1., 2., -2., 3., -3., 4., -4.),
                (.1, .2, .6, .8, 1.5, 1.8, 2.8, 3.2)):
            self.assertEqual(contribution["inputValue"], value)
            self.assertEqual(contribution["standardizedValue"], standardized)
            self.assertAlmostEqual(contribution["contributionMgL"], expected)
        self.assertAlmostEqual(result["residualInterceptMgL"], .25)
        self.assertAlmostEqual(result["totalCorrectionMgL"], 11.25)
        self.assertAlmostEqual(result["reconstructedPredictionMgL"], 21.25)

    def test_event_context_marks_all_post_origin_data_as_future_and_keeps_missing_signed_flow(self):
        origin = datetime(2025, 7, 18, 5, tzinfo=timezone.utc)
        target = origin + timedelta(hours=1)
        origin_iso = trial.shared.iso(origin)
        target_iso = trial.shared.iso(target)
        row = {"origin": origin_iso, "target": target_iso, "persistence": 8.5,
               "actual": 3.5, "newPrediction": 8.53566}
        def measurement(identity, value):
            return {"id": identity, "value": value, "lastModified": "2026-10-01T00:00:00Z"}
        sources = {"oxygen": {origin: measurement("origin-o", 8.5),
                              target: measurement("target-o", 3.5)},
                   "temperature": {origin: measurement("origin-t", 20.)},
                   "discharge": {origin: measurement("origin-q", -2.5),
                                 origin + timedelta(minutes=30): measurement("future-q", -1.5)}}
        window = {"id": "summer-2025", "start": "2025-07-15T00:00:00Z",
                  "end": "2025-07-29T00:00:00Z"}
        spec = {"contextBeforeOriginMinutes": 330, "contextAfterTargetMinutes": 180,
                "sampleSpacingMinutes": 30}
        original = copy.deepcopy(sources)
        result = diag.event_context(row, sources, window, spec)
        self.assertEqual(sources, original)
        self.assertEqual(result["originUTC"], origin_iso)
        self.assertEqual(result["targetUTC"], target_iso)
        context = {entry["minutesFromOrigin"]: entry for entry in result["context"]}
        self.assertEqual(min(context), -330)
        self.assertEqual(max(context), 240)
        self.assertEqual(len(context), 20)
        for minutes, entry in context.items():
            self.assertEqual(entry["timeUTC"], trial.shared.iso(origin + timedelta(minutes=minutes)))
            self.assertEqual(entry["temporalRole"], "history" if minutes <= 0 else "future-diagnostic-only")
        self.assertEqual(context[0]["oxygen"], sources["oxygen"][origin])
        self.assertEqual(context[0]["discharge"]["value"], -2.5)
        self.assertEqual(context[30]["discharge"]["value"], -1.5)
        self.assertIsNone(context[30]["oxygen"])
        self.assertIsNone(context[30]["temperature"])
        self.assertEqual(context[60]["oxygen"]["id"], "target-o")
        self.assertIsNone(context[-30]["oxygen"])

    def test_full_diagnosis_cannot_train_or_establish_forecast_skill(self):
        with patch.object(trial, "fit", side_effect=AssertionError("Unexpected fit")), \
                patch.object(trial, "typescript_fit", side_effect=AssertionError("Unexpected TS fit")), \
                patch.object(trial.shared, "decimal_ridge", side_effect=AssertionError("Unexpected Decimal fit")):
            report = diag.diagnose(trial.ROOT)
        self.assertFalse(report["modelFitted"])
        self.assertFalse(report["forecastSkillEstablished"])
        self.assertFalse(report["operationalModelChanged"])
        self.assertTrue(report["targetUsesFutureInformation"])

    def test_changed_future_values_cannot_change_features_or_frozen_prediction(self):
        origin = datetime(2025, 7, 18, 5, tzinfo=timezone.utc)
        times = [origin + timedelta(minutes=30 * i) for i in range(-11, 9)]
        sources = {kind: {time: {"id": f"{kind}-{i}", "value": value + i * .01,
                                 "lastModified": "2026-04-29T00:00:00Z"}
                          for i, time in enumerate(times)}
                   for kind, value in (("oxygen", 8.), ("temperature", 25.), ("discharge", -10.))}
        before, _ = trial.shared.make_pairs(sources["oxygen"], sources["temperature"], sources["discharge"],
                                             times[0], times[-1])
        changed = copy.deepcopy(sources)
        for kind in changed:
            for time in changed[kind]:
                if time > origin:
                    changed[kind][time]["value"] += 10
        after, _ = trial.shared.make_pairs(changed["oxygen"], changed["temperature"], changed["discharge"],
                                            times[0], times[-1])
        a = next(row for row in before if row["origin"] == trial.shared.iso(origin))
        b = next(row for row in after if row["origin"] == trial.shared.iso(origin))
        self.assertNotEqual(a["actual"], b["actual"])
        self.assertEqual(a["features"], b["features"])
        self.assertEqual(a["evidence"], b["evidence"])
        model = {"name": "fixed-test-model", "model": {"alpha": 100, "mean": [0.] * 8,
                 "scale": [1.] * 8, "coefficients": [.1] * 8, "residualIntercept": .05}}
        self.assertEqual(trial.shared.prediction(model, a), trial.shared.prediction(model, b))

    def test_changed_input_is_rejected_before_replay(self):
        work = diag.ROOT / "work"
        work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="diagnostic-commitment-", dir=work) as temporary:
            root = Path(temporary).resolve()
            self.assertTrue(root.is_relative_to(work.resolve()))
            protocol_raw = (diag.ROOT / diag.PROTOCOL).read_bytes()
            protocol = json.loads(protocol_raw)
            path = root / diag.PROTOCOL
            path.parent.mkdir(parents=True)
            path.write_bytes(protocol_raw)
            first = protocol["inputs"][0]["file"]
            altered = root / first
            altered.parent.mkdir(parents=True)
            altered.write_bytes((diag.ROOT / first).read_bytes() + b" ")
            with patch.object(trial, "verify_evaluation", side_effect=AssertionError("Must reject before replay")):
                with self.assertRaisesRegex(ValueError, "Diagnostic input commitment mismatch"):
                    diag.diagnose(root)


if __name__ == "__main__":
    unittest.main()
