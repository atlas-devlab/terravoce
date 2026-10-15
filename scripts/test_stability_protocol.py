"""Past-only fallback and pre-capture protocol checks using synthetic records."""
import copy
import json
import math
import shutil
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import stability_protocol as trial


class StabilityProtocolTests(unittest.TestCase):
    def setUp(self):
        self.origin = datetime(2025, 2, 2, 12, tzinfo=timezone.utc)
        self.origin_utc = trial.shared.iso(self.origin)

    def history(self, value=9.):
        return [{"timeUTC": trial.shared.iso(self.origin - timedelta(minutes=30 * (11 - index))),
                 "value": value} for index in range(12)]

    def definition(self):
        spec = json.loads((trial.ROOT / trial.PROTOCOL).read_bytes())
        return spec, trial.previous_windows(trial.ROOT)

    @contextmanager
    def uncaptured_fixture(self):
        """The pre-capture guard is tested in isolation, also after the real run."""
        work = trial.ROOT / "work"
        work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="stability-preflight-", dir=work) as temporary:
            root = Path(temporary).resolve()
            self.assertTrue(root.is_relative_to(work.resolve()))
            for filename in [*trial.PREVIOUS_FILES, str(trial.PROTOCOL),
                             "docs/evidence/willamette-multiseason/frozen-model.json"]:
                destination = root / filename
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(trial.ROOT / filename, destination)
            yield root

    def test_flat_history_suppresses_the_entire_ridge_correction(self):
        history = self.history()
        original = copy.deepcopy(history)
        result = trial.apply_rule(history, self.origin_utc, 9.03)
        self.assertTrue(result["historyFlat"])
        self.assertEqual(result["residualMultiplier"], 0)
        self.assertEqual(result["predictionMgL"], 9.)
        self.assertEqual(result["persistenceMgL"], 9.)
        self.assertEqual(result["ridgePredictionMgL"], 9.03)
        self.assertEqual(history, original)

    def test_an_interior_change_invisible_to_the_three_model_deltas_keeps_ridge(self):
        history = self.history()
        history[3]["value"] = 8.9
        current = history[-1]["value"]
        self.assertEqual([current - history[index]["value"] for index in (10, 7, 0)], [0., 0., 0.])
        result = trial.apply_rule(history, self.origin_utc, 9.03)
        self.assertFalse(result["historyFlat"])
        self.assertEqual(result["residualMultiplier"], 1)
        self.assertEqual(result["predictionMgL"], 9.03)

    def test_a_one_ulp_change_is_not_rounded_or_given_an_epsilon_tolerance(self):
        history = self.history()
        history[3]["value"] = math.nextafter(9., math.inf)
        self.assertNotEqual(history[3]["value"], history[-1]["value"])
        result = trial.apply_rule(history, self.origin_utc, 9.03)
        self.assertFalse(result["historyFlat"])
        self.assertEqual(result["predictionMgL"], 9.03)

    def test_rejects_future_misordered_missing_duplicate_and_target_bearing_records(self):
        variants = {}
        future = self.history()
        future[-1]["timeUTC"] = trial.shared.iso(self.origin + timedelta(minutes=30))
        variants["future record"] = future
        misordered = self.history()
        misordered[1], misordered[2] = misordered[2], misordered[1]
        variants["misordered records"] = misordered
        variants["missing record"] = self.history()[:-1]
        duplicate = self.history()
        duplicate[2] = copy.deepcopy(duplicate[1])
        variants["duplicate timestamp"] = duplicate
        extra = self.history()
        extra[0]["actual"] = 9.1
        variants["future target field"] = extra
        missing_value = self.history()
        del missing_value[0]["value"]
        variants["missing value"] = missing_value
        extra_record = self.history()
        extra_record.append(copy.deepcopy(extra_record[-1]))
        variants["thirteenth record"] = extra_record
        for description, history in variants.items():
            with self.subTest(case=description):
                with self.assertRaises(ValueError):
                    trial.apply_rule(history, self.origin_utc, 9.03)
        for minute in (1, 15, 31):
            origin = self.origin.replace(minute=minute)
            history = [{"timeUTC": trial.shared.iso(origin - timedelta(minutes=30 * (11 - index))),
                        "value": 9.} for index in range(12)]
            with self.subTest(off_grid_origin=minute):
                with self.assertRaisesRegex(ValueError, "half-hour UTC grid"):
                    trial.apply_rule(history, trial.shared.iso(origin), 9.03)

    def test_rejects_nonfinite_negative_and_boolean_oxygen_or_invalid_ridge_reference(self):
        for value in (None, float("nan"), float("inf"), -float("inf"), -.1, True, False):
            with self.subTest(oxygen=value):
                history = self.history()
                history[3]["value"] = value
                with self.assertRaises(ValueError):
                    trial.apply_rule(history, self.origin_utc, 9.03)
        for reference in (None, float("nan"), float("inf"), -float("inf"), True, False):
            with self.subTest(ridge_reference=reference):
                with self.assertRaises(ValueError):
                    trial.apply_rule(self.history(), self.origin_utc, reference)

    def test_nonflat_negative_prediction_is_retained_for_evaluation_to_reject(self):
        history = self.history()
        history[3]["value"] = 8.9
        result = trial.apply_rule(history, self.origin_utc, -.25)
        self.assertFalse(result["historyFlat"])
        self.assertEqual(result["residualMultiplier"], 1)
        self.assertEqual(result["predictionMgL"], -.25)

    def test_flat_branch_does_not_multiply_zero_by_an_overflowed_residual(self):
        result = trial.apply_rule(self.history(1e308), self.origin_utc, -1e308)
        self.assertEqual(result["predictionMgL"], 1e308)
        self.assertTrue(math.isfinite(result["predictionMgL"]))

    def test_rejects_changes_to_horizon_rule_counts_coverage_and_operational_permissions(self):
        spec, seen = self.definition()
        changes = (("horizonSeconds", 7200),
                   ("rule.historySamples", 11),
                   ("rule.sampleSpacingSeconds", 3600),
                   ("rule.flatResidualMultiplier", .5),
                   ("rule.changingResidualMultiplier", .5),
                   ("rule.multiplyFullResidualIncludingIntercept", False),
                   ("rule.parameterSearchPermitted", True),
                   ("eligibility.expectedOriginsPerWindow", 1333),
                   ("eligibility.minimumAcceptedPairsPerWindow", 999),
                   ("eligibility.minimumExpectedGridCoveragePerWindow", .8),
                   ("decision.operationalPromotion", True),
                   ("decision.tenPercentIsAcceptanceGate", True),
                   ("evaluation.futureTargetGroupingPermittedForPrediction", True),
                   ("evaluation.removeLargeErrorsPermitted", True),
                   ("evaluation.clipPredictionsPermitted", True),
                   ("baseModel.newFitPermitted", True))
        for key, value in changes:
            with self.subTest(setting=key):
                changed = copy.deepcopy(spec)
                parts = key.split(".")
                parent = changed
                for part in parts[:-1]:
                    parent = parent[part]
                parent[parts[-1]] = value
                with self.assertRaises(ValueError):
                    trial.validate_definition(changed, seen)

    def test_equal_endpoints_overlap_because_source_queries_are_inclusive(self):
        spec, seen = self.definition()
        trial.validate_definition(spec, seen)
        for window in spec["testWindows"]:
            for boundary in ("start", "end"):
                with self.subTest(window=window["id"], boundary=boundary):
                    endpoint = trial.shared.instant(window[boundary])
                    old = ((endpoint - timedelta(days=1), endpoint) if boundary == "start"
                           else (endpoint, endpoint + timedelta(days=1)))
                    with self.assertRaisesRegex(ValueError, "overlaps"):
                        trial.validate_definition(spec, seen + [old])

    def test_preflight_checks_only_existing_metadata_and_keeps_experiment_unexecuted(self):
        with self.uncaptured_fixture() as root:
            with patch.object(trial.shared, "decimal_ridge", side_effect=AssertionError("Unexpected training")):
                result = trial.preflight(root)
        self.assertTrue(result["protocolVerified"])
        self.assertEqual(result["horizonSeconds"], 3600)
        self.assertEqual(result["previouslyInspectedWindowsChecked"], 11)
        self.assertEqual(result["expectedOriginsPerWindow"], 1332)
        self.assertEqual(len(result["newWindows"]), 4)
        self.assertEqual(result["frozenModelHash"], trial.MODEL_HASH)
        for key in ("newModelFitted", "newTestValuesAcquired", "forecastSkillEvaluated",
                    "captureAndEvaluationRunnerImplemented"):
            self.assertFalse(result[key], key)

    def test_preflight_rejects_altered_weights_and_already_present_capture(self):
        with self.uncaptured_fixture() as root:
            model_path = "docs/evidence/willamette-multiseason/frozen-model.json"
            model = root / model_path
            original = model.read_bytes()
            model.write_bytes(original + b" ")
            with self.assertRaisesRegex(ValueError, "Frozen model or original protocol bytes changed"):
                trial.preflight(root)
            model.write_bytes(original)
            spec, _ = self.definition()
            (root / trial.PROTOCOL.parent / spec["testWindows"][0]["id"]).mkdir()
            with self.assertRaisesRegex(ValueError, "captures already exist"):
                trial.preflight(root)


if __name__ == "__main__":
    unittest.main()
