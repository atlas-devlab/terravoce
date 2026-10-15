"""Invented-data counterexamples for threshold selection and its later-check boundary."""
import copy
import math
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import evaluate_threshold_development as runner
import threshold_development as plan


def stamp(value):
    return value.isoformat().replace("+00:00", "Z")


def row(origin, current, actual, ridge, phase):
    return {"origin": stamp(origin), "target": stamp(origin + timedelta(hours=1)),
        "oxygenHistory": [{"timeUTC": stamp(origin - timedelta(minutes=30 * j)), "value": current}
                          for j in range(11, -1, -1)],
        "actual": actual, "phase": phase,
        "predictionsMgL": {runner.P: current, runner.R: ridge, runner.C: current}}


def archive(selection=((8, 8, 8.04), (8, 8.3, 8.3)), later=((8, 8, 8.04), (8, 8.3, 8.3))):
    windows = []
    for season, month in zip(plan.SEASONS, (2, 5, 6, 11)):
        start = datetime(2025, month, 1, tzinfo=timezone.utc)
        rows = []
        for phase, day, cases in (("selection", 1, selection), ("laterCheck", 15, later)):
            for i, (current, actual, ridge) in enumerate(cases):
                rows.append(row(start + timedelta(days=day - 1, hours=6, minutes=30 * i),
                                current, actual, ridge, phase))
        windows.append({"window": {"id": season, "season": season, "start": stamp(start),
            "end": stamp(start + timedelta(days=28))}, "rows": rows, "dataScreenPassed": True,
            "quality": {"oxygen": {"accepted": 100, "excluded": 2}}})
    return {"windows": windows}


class ThresholdRunnerTests(unittest.TestCase):
    def test_selected_threshold_is_only_one_scored_on_later_targets(self):
        calls = []
        original = runner.summarize

        def observe(rows, threshold=None):
            calls.append((rows[0]["phase"], threshold))
            return original(rows, threshold)

        with patch.object(runner, "summarize", side_effect=observe):
            result = runner.develop(archive())
        self.assertEqual(result["selectedThresholdMgL"], .2)
        self.assertEqual(result["status"], "promising-in-development-only")
        self.assertEqual([t for phase, t in calls if phase == "laterCheck"], [.2] * 4)
        self.assertFalse(result["laterCheck"]["otherThresholdsScored"])
        self.assertAlmostEqual(result["selection"]["candidates"][-1]["macroMAEMgL"], 0)
        self.assertAlmostEqual(result["laterCheck"]["macroMAEMgL"][runner.P], .15)

    def test_no_eligible_candidate_never_reads_later_outcomes(self):
        data = archive(selection=((8, 8, 8.04),))
        for window in data["windows"]:
            for item in window["rows"]:
                if item["phase"] == "laterCheck":
                    item["actual"], item["predictionsMgL"] = "must not be scored", {}
        result = runner.develop(data)
        self.assertEqual(result["status"], "no-promising-threshold")
        self.assertIsNone(result["selectedThresholdMgL"])
        self.assertIsNone(result["laterCheck"])

    def test_later_failure_does_not_switch_to_a_different_candidate(self):
        # Selection chooses .2; on later targets .1 would help, but must not be examined.
        result = runner.develop(archive(later=((8, 8.15, 8.15),)))
        self.assertEqual(result["selectedThresholdMgL"], .2)
        self.assertEqual(result["status"], "selected-threshold-failed-later-development-check")
        self.assertEqual(result["laterCheck"]["thresholdMgL"], .2)
        self.assertFalse(result["laterCheck"]["screen"]["passed"])

    def test_no_window_loss_gate_is_not_hidden_by_macro_gain(self):
        parts = {}
        for season in plan.SEASONS:
            p, candidate = (.1, .101) if season == "winter" else (.1, .01)
            parts[season] = {"methods": {
                runner.P: {"scores": {"maeMgL": p}}, runner.FILTER: {
                    "scores": {"maeMgL": candidate}, "nonfinitePredictions": 0, "negativePredictions": 0}}}
        screen = runner.passes_screen(parts)
        self.assertGreater(screen["macroGainOverPersistenceMgL"], 0)
        self.assertFalse(screen["passed"])

    def test_negative_prediction_cannot_be_selected_even_with_lower_mae(self):
        result = runner.develop(archive(selection=((2, 0, -.1),)))
        self.assertIsNone(result["selectedThresholdMgL"])
        self.assertTrue(all(c["selectionSummary"]["invalidOrNegativePredictions"] == 4
                            for c in result["selection"]["candidates"]))

    def test_nonfinite_values_fail_without_dropping_the_bad_origin(self):
        rows = archive()["windows"][0]["rows"][:2]
        rows[1]["predictionsMgL"][runner.R] = math.nan
        with self.assertRaisesRegex(ValueError, "Nonfinite comparator"):
            runner.summarize(rows, .05)
        rows[1]["predictionsMgL"][runner.R] = 8.3
        rows[1]["actual"] = math.inf
        with self.assertRaisesRegex(ValueError, "finite nonnegative observed"):
            runner.summarize(rows, .05)

    def test_missing_or_false_quality_screen_fails_before_any_scoring(self):
        for field, value in (("dataScreenPassed", False), ("quality", None)):
            data = archive()
            data["windows"][0][field] = value
            with patch.object(runner, "summarize") as scoring:
                with self.assertRaisesRegex(ValueError, "quality screen"):
                    runner.develop(data)
                scoring.assert_not_called()

    def test_metrics_preserve_direction_and_count_exact_nonzero_changes(self):
        rows = archive(selection=((8, 8.5, 8.25), (8, 7.5, 7.75)))["windows"][0]["rows"][:2]
        result = runner.summarize(rows, .2)
        self.assertEqual(result["pairs"], 2)
        self.assertEqual(result["methods"][runner.FILTER]["nonzeroCorrections"], 2)
        metrics = result["methods"][runner.FILTER]["scores"]
        self.assertEqual(metrics["maeMgL"], .25)
        self.assertEqual(metrics["rmseMgL"], .25)
        self.assertEqual(metrics["biasMgL"], 0)
        rows[0]["predictionsMgL"][runner.R] = math.nextafter(8, math.inf)
        self.assertEqual(runner.summarize(rows, 0)["methods"][runner.FILTER]["nonzeroCorrections"], 2)

    def test_expected_grid_reports_missing_origins_without_imputing_them(self):
        data = archive()
        result = runner.develop(data)
        counts = result["windows"][0]["gridByPart"]
        self.assertEqual(counts["selection"], {"expectedOrigins": 659, "acceptedPairs": 2,
                                              "missingOrIncompleteOrigins": 657})
        self.assertEqual(counts["laterCheck"]["expectedOrigins"], 660)
        self.assertEqual(counts["excludedBetween"]["expectedOrigins"], 13)
        self.assertEqual(sum(g["expectedOrigins"] for g in counts.values()), 1332)

    def test_commit_mismatch_is_detected_before_any_archive_is_read(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            first = runner.IMPLEMENTATION_FILES[0]
            (root / first).parent.mkdir(parents=True)
            (root / first).write_bytes(b"changed")
            with patch.object(runner.stability, "git_bytes", return_value=b"committed"), \
                    patch.object(plan, "preflight") as preflight:
                with self.assertRaisesRegex(ValueError, "changed from frozen Git"):
                    runner.evaluate(root, "a" * 40)
                preflight.assert_not_called()
        with self.assertRaisesRegex(ValueError, "full frozen Git"):
            runner.commitment(Path("."), "HEAD")


if __name__ == "__main__":
    unittest.main()
