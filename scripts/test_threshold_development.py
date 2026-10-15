"""Synthetic counterexamples for the past-only rule and development selection policy."""
import copy
import math
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import threshold_development as td


def stamp(value):
    return value.isoformat().replace("+00:00", "Z")


def time_row(origin):
    return {"origin": stamp(origin), "target": stamp(origin + timedelta(hours=1)),
            "oxygenHistory": [{"timeUTC": stamp(origin - timedelta(minutes=30 * j))}
                              for j in range(11, -1, -1)]}


def fake_summaries():
    # Deliberately invented losses: no real river targets or archived predictions.
    return [{"thresholdMgL": threshold, "seasonalMAE": {s: .11 for s in td.SEASONS},
             "nonzeroCorrections": 100 - i * 10, "invalidOrNegativePredictions": 0}
            for i, threshold in enumerate(td.THRESHOLDS)]


class ThresholdDevelopmentTests(unittest.TestCase):
    def test_symmetric_small_corrections_are_suppressed_and_large_ones_kept(self):
        self.assertEqual(td.apply_filter(8, 8.125, .25), 8)
        self.assertEqual(td.apply_filter(8, 7.875, .25), 8)
        self.assertEqual(td.apply_filter(8, 8.5, .25), 8.5)
        self.assertEqual(td.apply_filter(8, 7.5, .25), 7.5)

    def test_boundary_is_inclusive_without_hidden_epsilon(self):
        self.assertEqual(td.apply_filter(8, 8.25, .25), 8)
        beyond = math.nextafter(8.25, math.inf)
        self.assertEqual(td.apply_filter(8, beyond, .25), beyond)
        self.assertEqual(td.apply_filter(8, 8.25, 0), 8.25)

    def test_invalid_inputs_and_overflow_are_rejected(self):
        for current, model, threshold in ((True, 8, .1), (8, math.nan, .1),
                (8, 8, -1), (8, 8, True), (-1, 8, .1), (1e308, -1e308, .1)):
            with self.subTest(inputs=(current, model, threshold)), self.assertRaises(ValueError):
                td.apply_filter(current, model, threshold)
        # No implicit clipping of negative model output; the eligibility screen must reject it.
        self.assertEqual(td.apply_filter(2, -1, 0), -1)

    def test_split_uses_no_outcomes_and_purges_overlapping_evidence(self):
        start = datetime(2025, 2, 1, tzinfo=timezone.utc)
        boundary = start + timedelta(days=14)
        window = {"start": stamp(start), "end": stamp(start + timedelta(days=28))}
        rows = [time_row(boundary - timedelta(hours=1.5) + timedelta(minutes=30 * i)) for i in range(15)]
        groups, receipt = td.split_window(window, rows)
        self.assertEqual([len(groups[k]) for k in ("selection", "excludedBetween", "laterCheck")], [1, 13, 1])
        self.assertEqual(receipt["retainedOriginGapSeconds"], 7 * 3600)
        self.assertIs(type(receipt["retainedOriginGapSeconds"]), int)
        self.assertLess(td.instant(receipt["latestSelectionTargetUTC"]), td.instant(receipt["earliestLaterHistoryUTC"]))
        # This metadata preflight works without actual values, features or predictions.
        self.assertNotIn("actual", rows[0])

    def test_missing_half_duplicate_and_broken_history_fail(self):
        start = datetime(2025, 2, 1, tzinfo=timezone.utc)
        boundary = start + timedelta(days=14)
        window = {"start": stamp(start), "end": stamp(start + timedelta(days=28))}
        rows = [time_row(boundary - timedelta(hours=1.5)), time_row(boundary + timedelta(hours=5.5))]
        for bad in (rows[:1], rows + rows[:1]):
            with self.assertRaises(ValueError):
                td.split_window(window, bad)
        bad = copy.deepcopy(rows)
        bad[1]["oxygenHistory"][0]["timeUTC"] = bad[1]["origin"]
        with self.assertRaises(ValueError):
            td.split_window(window, bad)

    def test_no_candidate_and_baseline_tie_retain_persistence(self):
        baseline = {s: .1 for s in td.SEASONS}
        candidates = fake_summaries()
        self.assertIsNone(td.choose_from_summaries(baseline, candidates)["thresholdMgL"])
        for candidate in candidates:
            candidate["seasonalMAE"] = baseline.copy()
        self.assertEqual(td.choose_from_summaries(baseline, candidates)["decision"], "retain-persistence")

    def test_macro_gain_does_not_hide_a_losing_season(self):
        baseline = {s: .1 for s in td.SEASONS}
        candidates = fake_summaries()
        candidates[1]["seasonalMAE"] = {s: .01 for s in td.SEASONS}
        candidates[1]["seasonalMAE"]["winter"] = .101
        self.assertEqual(td.choose_from_summaries(baseline, candidates)["decision"], "retain-persistence")

    def test_ties_prefer_fewer_corrections_then_larger_threshold(self):
        baseline = {s: .1 for s in td.SEASONS}
        candidates = fake_summaries()
        for candidate in candidates:
            candidate["seasonalMAE"] = {s: .09 for s in td.SEASONS}
        self.assertEqual(td.choose_from_summaries(baseline, candidates)["thresholdMgL"], .2)
        candidates[3]["nonzeroCorrections"] = 1
        self.assertEqual(td.choose_from_summaries(baseline, candidates)["thresholdMgL"], .1)
        candidates[4]["nonzeroCorrections"] = 1
        self.assertEqual(td.choose_from_summaries(baseline, candidates)["thresholdMgL"], .2)

    def test_fewer_corrections_cannot_override_a_real_mae_difference(self):
        baseline = {s: .1 for s in td.SEASONS}
        candidates = fake_summaries()
        candidates[1]["seasonalMAE"] = {s: .08 for s in td.SEASONS}
        candidates[4]["seasonalMAE"] = {s: .09 for s in td.SEASONS}
        candidates[4]["nonzeroCorrections"] = 0
        self.assertEqual(td.choose_from_summaries(baseline, candidates)["thresholdMgL"], .025)

    def test_invalid_predictions_and_omitted_grid_candidates_cannot_win(self):
        baseline = {s: .1 for s in td.SEASONS}
        candidates = fake_summaries()
        candidates[0]["seasonalMAE"] = {s: .01 for s in td.SEASONS}
        candidates[0]["invalidOrNegativePredictions"] = 1
        self.assertEqual(td.choose_from_summaries(baseline, candidates)["decision"], "retain-persistence")
        with self.assertRaises(ValueError):
            td.choose_from_summaries(baseline, candidates[:-1])
        candidates[0]["thresholdMgL"] = False
        with self.assertRaises(ValueError):
            td.choose_from_summaries(baseline, candidates)

    def test_changed_plan_is_rejected_before_reading_any_development_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            plan = root / td.PLAN
            plan.parent.mkdir(parents=True)
            plan.write_bytes((td.ROOT / td.PLAN).read_bytes().replace(
                b'"oneThresholdSharedAcrossWindows": true', b'"oneThresholdSharedAcrossWindows": false'))
            # No archive exists here: the plan commitment must fail first.
            with self.assertRaisesRegex(ValueError, "plan commitment changed"):
                td.preflight(root)


if __name__ == "__main__":
    unittest.main()
