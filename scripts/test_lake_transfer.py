"""Invented-data checks of lake depth, cohort, freeze, single attempt and frozen filtering."""
import copy
import gzip
import json
import math
import subprocess
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import lake_transfer as lake


def records(start, count=14, value=8):
    return {start + timedelta(minutes=30 * i): {"id": str(i), "value": value, "lastModified": "2026-01-01"}
            for i in range(count)}


def model(correction=.05):
    return {"recipe": {"name": "frozen-ridge"}, "model": {"mean": [0] * 8, "scale": [1] * 8,
        "coefficients": [0] * 8, "residualIntercept": correction},
        "training": {"featureRanges": [{"feature": str(j), "min": -100, "max": 100} for j in range(8)]}}


def collection(series=None, duplicate=False, approval="Approved", qualifier=None):
    source = lake.SOURCES["oxygen"]
    p = {"time": lake.WINDOW["start"], "monitoring_location_id": lake.STATION,
        "parameter_code": source["parameterCode"], "time_series_id": series or source["timeSeriesId"],
        "statistic_id": "00011", "unit_of_measure": "mg/l", "value": "8.1", "approval_status": approval,
        "qualifier": qualifier, "last_modified": "2026-01-01T00:00:00Z"}
    features = [{"id": "one", "properties": p}]
    return lake.encoded({"type": "FeatureCollection", "links": [], "features": features * (2 if duplicate else 1)})


class LakeTransferTests(unittest.TestCase):
    def setUp(self):
        self.start = lake.shared.instant(lake.WINDOW["start"])

    def pairs(self, correction=.05, oxygen=None, temperature=None):
        return lake.make_rows(records(self.start) if oxygen is None else oxygen,
            records(self.start, value=20) if temperature is None else temperature,
            self.start, self.start + timedelta(hours=6.5), model(correction))

    def test_target_changes_cannot_change_frozen_filter_or_input_features(self):
        oxygen = records(self.start)
        before, _ = self.pairs(oxygen=oxygen)
        oxygen[self.start + timedelta(hours=6.5)]["value"] = .5
        after, _ = self.pairs(oxygen=oxygen)
        self.assertNotEqual(before[0]["actual"], after[0]["actual"])
        self.assertEqual(before[0]["predictionsMgL"], after[0]["predictionsMgL"])
        self.assertEqual(before[0]["features"], after[0]["features"])
        self.assertEqual(after[0]["predictionsMgL"][lake.F], 8)
        self.assertAlmostEqual(after[0]["predictionsMgL"][lake.R], 8.05)

    def test_large_correction_is_retained_even_when_target_disagrees(self):
        rows, _ = self.pairs(correction=.2)
        self.assertAlmostEqual(rows[0]["predictionsMgL"][lake.F], 8.2)
        self.assertEqual(rows[0]["predictionsMgL"][lake.C], 8)
        self.assertEqual(set(rows[0]["predictionsMgL"]), set(lake.METHODS))

    def test_exact_target_required_and_quarter_hour_samples_are_not_interpolated(self):
        oxygen = records(self.start)
        del oxygen[self.start + timedelta(hours=6.5)]
        for minutes in (375, 405):
            oxygen[self.start + timedelta(minutes=minutes)] = {"id": str(minutes), "value": 8}
        rows, grid = self.pairs(oxygen=oxygen)
        self.assertEqual(rows, [])
        self.assertEqual(grid["expectedOrigins"], 1)
        self.assertEqual(grid["presentOriginsWithIncompleteHistoryOrTarget"], 1)

    def test_missing_temperature_history_removes_origin_from_every_method(self):
        temperature = records(self.start)
        del temperature[self.start + timedelta(hours=2)]
        rows, grid = self.pairs(temperature=temperature)
        self.assertEqual(rows, [])
        self.assertEqual(grid["acceptedGridFraction"], 0)

    def test_entire_fixed_grid_denominator_includes_missing_oxygen_origins(self):
        rows, grid = lake.make_rows({}, {}, self.start, self.start + timedelta(days=28), model())
        self.assertFalse(rows)
        self.assertEqual(grid["expectedOrigins"], 1332)
        self.assertEqual(grid["missingApprovedOxygenOrigins"], 1332)

    def test_same_source_at_another_depth_is_rejected(self):
        s = lake.SOURCES["oxygen"]
        with self.assertRaisesRegex(ValueError, "Mixed source identity"):
            lake.shared.read_collection(collection(series="other-depth"), lake.STATION, s["parameterCode"],
                s["timeSeriesId"], s["unit"], self.start, self.start + timedelta(days=28))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            lake.shared.read_collection(collection(duplicate=True), lake.STATION, s["parameterCode"],
                s["timeSeriesId"], s["unit"], self.start, self.start + timedelta(days=28))

    def test_unapproved_or_qualified_records_cannot_become_model_inputs(self):
        s = lake.SOURCES["oxygen"]
        for options in ({"approval": "Provisional"}, {"qualifier": "e"}):
            accepted, qa = lake.shared.read_collection(collection(**options), lake.STATION, s["parameterCode"],
                s["timeSeriesId"], s["unit"], self.start, self.start + timedelta(days=28))
            self.assertFalse(accepted)
            self.assertEqual(len(qa["excluded"]), 1)

    def test_metrics_keep_bad_prediction_in_shared_cohort(self):
        rows, _ = self.pairs()
        rows[0]["predictionsMgL"][lake.F] = None
        summary = lake.summarize(rows)
        self.assertIsNone(summary["scores"][lake.F])
        self.assertEqual(summary["scores"][lake.P]["pairs"], 1)
        self.assertEqual(summary["predictionDiagnostics"][lake.F]["nonfinitePredictions"], 1)
        self.assertTrue(lake.invalid_prediction(summary))

    def test_negative_comparator_does_not_disqualify_nonnegative_filtered_prediction(self):
        rows, _ = self.pairs(correction=-.02, oxygen=records(self.start, value=.01))
        summary = lake.summarize(rows)
        self.assertAlmostEqual(rows[0]["predictionsMgL"][lake.R], -.01)
        self.assertEqual(rows[0]["predictionsMgL"][lake.F], .01)
        self.assertEqual(summary["predictionDiagnostics"][lake.R]["negativePredictions"], 1)
        self.assertFalse(lake.invalid_prediction(summary))
        rows[0]["predictionsMgL"][lake.F] = -.01
        self.assertTrue(lake.invalid_prediction(lake.summarize(rows)))

    def test_nonfinite_ridge_cannot_be_hidden_by_flat_history_or_drop_origin(self):
        with patch.object(lake.shared, "prediction", return_value=math.inf):
            rows, grid = self.pairs()
        self.assertEqual(len(rows), 1)
        self.assertEqual(grid["acceptedExactGridPairs"], 1)
        self.assertEqual(rows[0]["predictionsMgL"][lake.C], 8)
        self.assertIsNone(rows[0]["predictionsMgL"][lake.F])
        self.assertTrue(lake.invalid_prediction(lake.summarize(rows)))

    def test_catalogue_requires_same_exo1_deployment_for_both_series(self):
        features = [{"id": s["timeSeriesId"], "properties": {"monitoring_location_id": lake.STATION,
            "parameter_code": s["parameterCode"], "statistic_id": "00011", "unit_of_measure": s["unit"],
            "sublocation_identifier": "EXO 1", "web_description": "Depth at 3 feet", "primary": "Primary",
            "computation_identifier": "Instantaneous"}} for s in lake.SOURCES.values()]
        catalogue = {"type": "FeatureCollection", "links": [], "features": features}
        lake.validate_metadata(catalogue)
        catalogue["features"][1]["properties"]["sublocation_identifier"] = "EXO 2"
        with self.assertRaisesRegex(ValueError, "same fixed EXO 1"):
            lake.validate_metadata(catalogue)

    def test_paired_bootstrap_preserves_identical_methods_and_error_direction(self):
        rows, _ = self.pairs(correction=.2)
        testrows = []
        for day in range(5):
            r = copy.deepcopy(rows[0])
            r["origin"] = lake.shared.iso(self.start + timedelta(days=day))
            r["actual"] = 8.4
            testrows.append(r)
        result = lake.bootstrap(testrows, self.start, 24,
            {"iterations": 20, "seed": 1, "confidenceFraction": .95, "minimumNonemptyBlocks": 4})
        self.assertEqual(result["gainAgainstPersistence"][lake.P], {"lowerGainMgL": 0, "upperGainMgL": 0})
        self.assertAlmostEqual(result["gainAgainstPersistence"][lake.F]["lowerGainMgL"], .2)
        self.assertEqual(result["gainAgainstPersistence"][lake.F], result["gainAgainstPersistence"][lake.R])

    def test_capture_freeze_rejects_changed_bytes_before_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file = "scripts/lake_transfer.py"
            path = root / file
            path.parent.mkdir()
            path.write_bytes(b"original\n")
            for args in (["init", "-q"], ["add", "."], ["-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "freeze"]):
                subprocess.run(["git", *args], cwd=root, capture_output=True, check=True)
            revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, check=True).stdout.decode().strip()
            path.write_bytes(b"changed\n")
            with patch.object(lake, "REQUIRED_FILES", {file}), patch.object(lake, "download") as network:
                with self.assertRaisesRegex(ValueError, "differ from frozen"):
                    lake.implementation(root, revision, {"implementationFiles": [file]})
                network.assert_not_called()

    def test_failed_capture_is_archived_and_attempt_is_not_repeatable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / lake.DATA).mkdir(parents=True)
            spec = {"window": lake.WINDOW, "sources": lake.SOURCES, "stationId": lake.STATION}
            frozen = {"frozenAtCommit": "a" * 40, "implementationFiles": [], "implementationSnapshotHash": "b" * 64,
                "verifiedAgainstCurrentFilesAndGit": True}
            with patch.object(lake, "frozen_inputs", return_value=(spec, "hash", None)), \
                    patch.object(lake, "implementation", return_value=frozen), \
                    patch.object(lake, "download", return_value=(503, b"unavailable")) as network:
                result = lake.capture(root, "a" * 40)
                self.assertFalse(result["captureEligible"])
                self.assertEqual(network.call_count, 2)
                self.assertEqual(gzip.decompress((root / lake.DATA / "oxygen.json.gz").read_bytes()), b"unavailable")
                # Failed HTTP bodies are still bound into the offline evidence receipt.
                self.assertEqual(lake.evaluate(root)["decision"], "insufficient-data")
                (root / lake.DATA / "oxygen.json.gz").write_bytes(gzip.compress(b"altered", mtime=0))
                with self.assertRaisesRegex(ValueError, "Archived source body changed"):
                    lake.evaluate(root)
                with self.assertRaisesRegex(ValueError, "already exist"):
                    lake.capture(root, "a" * 40)
                self.assertEqual(network.call_count, 2)

    def test_exclusive_attempt_survives_failure_before_output_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / lake.DATA).mkdir(parents=True)
            (root / lake.DATA / "capture-attempt.json").write_bytes(b"previous-start")
            spec = {"window": lake.WINDOW}
            with patch.object(lake, "frozen_inputs", return_value=(spec, "hash", None)), \
                    patch.object(lake, "implementation", return_value={}), patch.object(lake, "download") as network:
                with self.assertRaises(FileExistsError):
                    lake.capture(root, "a" * 40)
                network.assert_not_called()

    def test_source_url_pins_depth_series_and_inclusive_window(self):
        from urllib.parse import parse_qs, urlparse
        spec = {"window": lake.WINDOW, "sources": lake.SOURCES, "stationId": lake.STATION}
        query = parse_qs(urlparse(lake.source_url(spec, "oxygen")).query)
        self.assertEqual(query["time_series_id"], [lake.SOURCES["oxygen"]["timeSeriesId"]])
        self.assertEqual(query["time"], [lake.WINDOW["start"] + "/" + lake.WINDOW["end"]])
        self.assertEqual(query["limit"], ["10000"])


if __name__ == "__main__":
    unittest.main()
