"""Acceptance rules, calendar dependence and train/test separation for the new experiment."""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import experiment_multiseason as trial


class MultiseasonTests(unittest.TestCase):
    def toy(self, gain):
        return [{"window": {"start": "2025-01-01T00:00:00Z"}, "rows": [
            {"origin": f"2025-01-{day:02d}T06:00:00Z", "actual": 10, "persistence": 11, "newPrediction": 11 - gain}
            for day in range(1, 15)]} for _ in range(4)]

    def test_paired_bootstrap_known_gain_and_null_with_calendar_blocks(self):
        p, _ = trial.protocol(trial.ROOT)
        u = p["uncertainty"] | {"iterations": 100}
        for gain in (0, .2):
            band = trial.bootstrap(self.toy(gain), 48, u)
            self.assertEqual(band["nonemptyBlocksPerSeason"], [7] * 4)
            self.assertAlmostEqual(band["lowerGainMgL"], gain)
            self.assertAlmostEqual(band["upperGainMgL"], gain)
        rows = self.toy(.2)[0]["rows"]
        # Repeated measurements inside one calendar block do not become extra independent blocks.
        self.assertEqual(len(trial.calendar_blocks(self.toy(.2)[0]["window"], [rows[0]] * 50 + [rows[-1]], 48)), 2)

    def test_macro_bootstrap_keeps_equal_season_weights_despite_unequal_counts(self):
        p, _ = trial.protocol(trial.ROOT)
        windows = self.toy(0)
        windows[3] = self.toy(.4)[3]
        windows[3]["rows"] *= 10
        band = trial.bootstrap(windows, 48, p["uncertainty"] | {"iterations": 100})
        self.assertAlmostEqual(band["lowerGainMgL"], .1)
        self.assertAlmostEqual(band["upperGainMgL"], .1)

    def test_ten_percent_is_not_a_gate_and_seasonal_loss_is_retained(self):
        p, _ = trial.protocol(trial.ROOT)
        windows = [{"dataScreenPassed": True, "negativePredictions": 0,
            "scores": {"new": {"maeMgL": .99}, "persistence": {"maeMgL": 1}}} for _ in range(4)]
        bands = [{"status": "estimated", "lowerGainMgL": .001} for _ in range(3)]
        self.assertEqual(trial.classify(windows, {"gainMgL": .01}, bands, p["decision"]), "credible-exploratory-improvement")
        windows[0]["scores"]["new"]["maeMgL"] = 1.01
        self.assertEqual(trial.classify(windows, {"gainMgL": .01}, bands, p["decision"]), "observed-seasonal-tradeoff")
        windows[0]["scores"]["new"]["maeMgL"] = .99
        bands[1]["lowerGainMgL"] = -.001
        self.assertEqual(trial.classify(windows, {"gainMgL": .01}, bands, p["decision"]), "inconclusive-gain")
        self.assertEqual(trial.classify(windows, {"gainMgL": 0}, bands, p["decision"]), "no-overall-improvement")
        windows[0]["dataScreenPassed"] = False
        self.assertEqual(trial.classify(windows, {"gainMgL": .01}, bands, p["decision"]), "insufficient-data")

    def test_malformed_model_vectors_and_nonpositive_scales_are_rejected(self):
        model = {"alpha": 100, "mean": [0] * 8, "scale": [1] * 8, "coefficients": [0] * 8, "residualIntercept": 0}
        trial.validate_model(model)
        for key, value in [("scale", [0] * 8), ("coefficients", [float("nan")] * 8), ("mean", [0] * 7), ("alpha", 1)]:
            changed = copy.deepcopy(model)
            changed[key] = value
            with self.assertRaises(ValueError):
                trial.validate_model(changed)

    def test_evaluation_cannot_call_training_or_either_solver(self):
        with patch.object(trial, "fit", side_effect=AssertionError("Unexpected fit")), \
                patch.object(trial, "typescript_fit", side_effect=AssertionError("Unexpected TS fit")), \
                patch.object(trial.shared, "decimal_ridge", side_effect=AssertionError("Unexpected Decimal fit")):
            report = trial.evaluate(trial.ROOT)
        self.assertFalse(report["modelRefittedDuringEvaluation"])
        self.assertFalse(report["operationalModelChanged"])

    def test_changed_frozen_commitment_is_rejected_before_prediction(self):
        work = trial.ROOT / "work"
        work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="multiseason-test-", dir=work) as temporary:
            root = Path(temporary).resolve()
            self.assertTrue(root.is_relative_to(work.resolve()))
            (root / trial.DATA).mkdir(parents=True)
            (root / trial.EVIDENCE).mkdir(parents=True)
            shutil.copyfile(trial.ROOT / trial.DATA / "protocol.json", root / trial.DATA / "protocol.json")
            model = json.loads((trial.ROOT / trial.EVIDENCE / "frozen-model.json").read_bytes())
            model["protocolHash"] = "0xwrong"
            (root / trial.EVIDENCE / "frozen-model.json").write_bytes(trial.encoded(model))
            with self.assertRaisesRegex(ValueError, "Frozen model/protocol mismatch"):
                trial.evaluate(root)

    def test_capture_cannot_be_scored_with_different_frozen_weights(self):
        p, ph = trial.protocol(trial.ROOT)
        window = p["testWindows"][0]
        work = trial.ROOT / "work"
        work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="capture-commitment-", dir=work) as temporary:
            folder = Path(temporary)
            (folder / window["id"]).mkdir()
            (folder / window["id"] / "manifest.json").write_bytes(trial.encoded({
                "version": "multiseason-test-capture-v1", "protocolHash": ph, "window": window,
                "frozenModelHash": "0xdifferent", "status": "unavailable", "error": "fixed request failed"}))
            with self.assertRaisesRegex(ValueError, "Capture protocol/model commitment mismatch"):
                trial.read_window(folder, window, p, ph, "multiseason-test-capture-v1", "0xexpected")


if __name__ == "__main__":
    unittest.main()
