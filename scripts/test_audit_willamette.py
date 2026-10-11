"""Regression tests for independent audit and frozen-model validation boundaries."""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import audit_willamette as audit


class IndependentAuditTests(unittest.TestCase):
    def test_high_precision_solver_against_known_solution(self):
        rows = [{"features": [x, 8.0], "actual": 2 * x, "persistence": 0.0} for x in (-1.0, 0.0, 1.0)]
        model = audit.decimal_ridge(rows, 2, 3)
        self.assertAlmostEqual(audit.prediction({"name": "test", "model": model}, {"features": [1, 8], "persistence": 0}), 1)
        self.assertEqual(model["coefficients"][1], 0)

    def test_quality_checks_timestamps_and_signed_discharge(self):
        with self.assertRaisesRegex(ValueError, "explicit UTC offset"):
            audit.instant("2025-08-01T00:00:00")
        extra = audit.ROOT / "docs/datasets/usgs-willamette-multivariate"
        raw = json.loads(audit.compressed_body(extra / "discharge.json.gz"))
        raw["features"] = [raw["features"][0]]
        raw["numberReturned"] = 1
        raw["links"] = []
        raw["features"][0]["properties"]["value"] = "-100"
        start, end = audit.instant("2025-08-01T00:00:00Z"), audit.instant("2025-08-15T00:00:00Z")
        args = ("USGS-14211720", "00060", "25161ce7dc08491389080de10c85fd9e", "ft^3/s", start, end, 0.028316846592)
        result, quality = audit.read_collection(json.dumps(raw), *args)
        self.assertAlmostEqual(result[start]["value"], -2.8316846592)
        self.assertEqual(quality["accepted"], 1)
        qualified = copy.deepcopy(raw)
        qualified["features"][0]["properties"]["qualifier"] = "e"
        self.assertEqual(audit.read_collection(json.dumps(qualified), *args)[1]["accepted"], 0)
        duplicate = copy.deepcopy(raw)
        duplicate["features"].append(copy.deepcopy(duplicate["features"][0]))
        duplicate["features"][1]["id"] = "different-id"
        duplicate["features"][1]["properties"]["time"] = "2025-08-01T02:00:00+02:00"
        duplicate["numberReturned"] = 2
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            audit.read_collection(json.dumps(duplicate), *args)

    def test_prediction_count_mismatch_cannot_hide_unscored_rows(self):
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            audit.metrics([{"actual": 8}], [8, 9])

    def test_truncated_vectors_and_nonfinite_expected_values_are_rejected(self):
        with self.assertRaisesRegex(AssertionError, "nan"):
            audit.close(1.0, float("nan"), "changed metric")
        candidate = {"name": "test", "model": {"mean": [1, 2], "scale": [1], "coefficients": [1, 2], "residualIntercept": 0}}
        with self.assertRaisesRegex(ValueError, "Incomplete model vectors"):
            audit.prediction(candidate, {"features": [1, 2], "persistence": 8})

    def test_independent_reconstruction_matches_all_declared_candidates(self):
        report = audit.original_audit()
        self.assertTrue(report["passed"])
        self.assertLess(report["largestCoefficientOrMetricDifference"], report["numericTolerance"])
        self.assertEqual(report["checkedCandidates"], 14)

    def test_external_evaluation_never_refits_and_exposes_season_failure(self):
        with patch.object(audit, "decimal_ridge", side_effect=AssertionError("Unexpected refit")):
            report = audit.frozen_validation()
        self.assertFalse(report["refitted"])
        self.assertFalse(report["recalibrated"])
        self.assertFalse(report["operationalModelChanged"])
        self.assertEqual(len(report["windows"]), 2)
        for window in report["windows"]:
            self.assertGreater(window["selectedModel"]["maeMgL"], window["persistence"]["maeMgL"])
            self.assertEqual(window["featureExtrapolation"]["fraction"], 1.0)

    def test_saved_artifact_portability_has_bounded_float_tolerance_and_exact_lineage(self):
        report = audit.frozen_validation()
        verified = audit.verify_saved_seasonal(report, audit.ROOT / "docs/evidence/willamette-forecast")
        self.assertTrue(verified["verified"])
        self.assertLessEqual(verified["largestNumericDifference"], audit.TOLERANCE)
        self.assertLess(audit.compare_saved({"value": 1.0}, {"value": 1.0 + 1e-12}), audit.TOLERANCE)
        with self.assertRaises(AssertionError):
            audit.compare_saved({"value": 1.0}, {"value": 1.0 + 1e-6})
        with self.assertRaises(AssertionError):
            audit.compare_saved({"ids": ["a", "b"]}, {"ids": ["a"]})
        with self.assertRaises(AssertionError):
            audit.compare_saved({"hash": "original"}, {"hash": "changed"})
        with self.assertRaises(AssertionError):
            audit.compare_saved({"pairs": 660}, {"pairs": 659})

    def test_frozen_commitment_and_capture_hash_tampering_are_rejected(self):
        work = (audit.ROOT / "work").resolve()
        work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="forecast-audit-", dir=work) as name:
            root = Path(name).resolve()
            self.assertTrue(root.is_relative_to(work))  # Keep recursive temp cleanup inside the workspace.
            for folder in ("usgs-willamette", "usgs-willamette-multivariate", "usgs-willamette-validation"):
                shutil.copytree(audit.ROOT / "docs/datasets" / folder, root / "docs/datasets" / folder)
            evidence = root / "docs/evidence/willamette-forecast"
            evidence.mkdir(parents=True)
            report_file = evidence / "forecast.json"
            original = (audit.ROOT / "docs/evidence/willamette-forecast/forecast.json").read_bytes()
            report_file.write_bytes(original + b" ")
            with self.assertRaisesRegex(ValueError, "commitment changed"):
                audit.frozen_validation(root)
            report_file.write_bytes(original)
            capture = root / "docs/datasets/usgs-willamette-validation/autumn-2025/manifest.json"
            obj = json.loads(capture.read_text(encoding="utf-8"))
            obj["sources"]["oxygen"]["rawSha256"] = "0xwrong"
            capture.write_text(json.dumps(obj), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "raw-body hash mismatch"):
                audit.frozen_validation(root)


if __name__ == "__main__":
    unittest.main()
