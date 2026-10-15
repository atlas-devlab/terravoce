"""Synthetic evidence for leakage boundaries, frozen replay, missingness and paired decisions."""
import copy
import contextlib
import gzip
import io
import json
import math
import subprocess
import tempfile
import unittest
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode

import evaluate_stability as trial


class StabilityEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads((trial.ROOT / trial.protocol.PROTOCOL).read_bytes())
        self.model = json.loads((trial.ROOT / self.spec["baseModel"]["file"]).read_bytes())
        self.source_spec = json.loads((trial.ROOT / self.spec["baseModel"]["protocolFile"]).read_bytes())
        self.start = datetime(2025, 2, 1, tzinfo=timezone.utc)

    def synthetic_sources(self, target=7., missing=None):
        sources = {}
        for kind, spec in self.source_spec["sources"].items():
            features = []
            for index in range(17):
                if (kind, index) == missing:
                    continue
                value = (target if index == 13 else 9.) if kind == "oxygen" else (12. if kind == "temperature" else -3.)
                features.append({"id": f"{kind}-{index}", "properties": {
                    "time": trial.shared.iso(self.start + timedelta(minutes=30 * index)),
                    "value": str(value), "monitoring_location_id": self.source_spec["stationId"],
                    "parameter_code": spec["parameterCode"], "time_series_id": spec["timeSeriesId"],
                    "statistic_id": "00011", "unit_of_measure": spec["unit"], "approval_status": "Approved",
                    "qualifier": None, "last_modified": "2026-01-01T00:00:00Z"}})
            sources[kind] = {"type": "FeatureCollection", "features": features, "links": [], "numberReturned": len(features)}
        return sources

    def rows(self, target=7., missing=None):
        end = self.start + timedelta(hours=8)
        records = {}
        for kind, obj in self.synthetic_sources(target, missing).items():
            spec = self.source_spec["sources"][kind]
            records[kind], _ = trial.shared.read_collection(trial.base.encoded(obj), self.source_spec["stationId"],
                spec["parameterCode"], spec["timeSeriesId"], spec["unit"], self.start, end, spec["scale"])
        pairs, _ = trial.shared.make_pairs(records["oxygen"], records["temperature"], records["discharge"], self.start, end)
        return pairs, records["oxygen"]

    def info(self):
        return {"window": self.spec["testWindows"][0], "status": "audited",
                "fullExpectedGrid": {"expectedOrigins": 1332, "acceptedExactGridPairs": 4, "acceptedGridFraction": 4 / 1332}}

    def test_future_target_changes_errors_but_cannot_change_first_forecast(self):
        first, oxygen = self.rows(7.)
        changed, changed_oxygen = self.rows(12.)
        a = trial.evaluate_rows(first, oxygen, self.info(), self.spec, self.model)
        b = trial.evaluate_rows(changed, changed_oxygen, self.info(), self.spec, self.model)
        self.assertEqual(a["rows"][0]["predictionsMgL"], b["rows"][0]["predictionsMgL"])
        self.assertEqual(a["rows"][0]["oxygenHistory"], b["rows"][0]["oxygenHistory"])
        self.assertEqual(a["rows"][0]["predictionsMgL"][trial.FALLBACK], 9.)
        self.assertEqual(a["rows"][0]["actual"], 7.)
        self.assertEqual(b["rows"][0]["actual"], 12.)
        self.assertNotEqual(a["scores"][trial.PERSISTENCE], b["scores"][trial.PERSISTENCE])
        self.assertEqual(len(a["rows"][0]["oxygenHistory"]), 12)
        self.assertTrue(all(trial.shared.instant(h["timeUTC"]) <= trial.shared.instant(a["rows"][0]["origin"])
                            for h in a["rows"][0]["oxygenHistory"]))

    def test_predictor_receives_only_past_features_and_no_target_fields(self):
        rows, oxygen = self.rows()
        original = trial.shared.prediction
        def guarded(candidate, row):
            self.assertEqual(set(row), {"persistence", "features"})
            return original(candidate, row)
        with patch.object(trial.shared, "prediction", side_effect=guarded):
            result = trial.evaluate_rows(rows, oxygen, self.info(), self.spec, self.model)
        self.assertEqual(result["rows"][0]["residualMultiplier"], 0)
        self.assertTrue(any(not r["historyFlat"] for r in result["rows"]))
        for row in result["rows"]:
            if not row["historyFlat"]:
                self.assertEqual(row["predictionsMgL"][trial.FALLBACK], row["predictionsMgL"][trial.RIDGE])

    def test_missing_covariate_or_target_removes_pairs_without_interpolation_and_signed_flow_is_retained(self):
        complete, _ = self.rows()
        missing_history, _ = self.rows(missing=("temperature", 3))
        missing_target, _ = self.rows(missing=("oxygen", 13))
        self.assertLess(len(missing_history), len(complete))
        self.assertFalse(any(r["target"] == trial.shared.iso(self.start + timedelta(hours=6.5)) for r in missing_target))
        self.assertTrue(all(r["features"][8] < 0 for r in complete))

    def test_empty_window_and_flat_subgroup_have_null_metrics(self):
        result = trial.evaluate_rows([], {}, self.info(), self.spec, self.model)
        self.assertFalse(result["dataScreenPassed"])
        self.assertTrue(all(value is None for value in result["scores"].values()))
        self.assertEqual(result["daily"], [])
        self.assertEqual(result["subgroups"]["past-flat"]["pairs"], 0)
        self.assertTrue(all(value is None for value in result["subgroups"]["past-flat"]["scores"].values()))

    def test_archived_read_window_checks_three_sources_and_retains_failed_companion_bodies(self):
        window = {"id": "synthetic", "start": trial.shared.iso(self.start),
                  "end": trial.shared.iso(self.start + timedelta(hours=8))}
        manifest = {"version": trial.CAPTURE_VERSION, "protocolHash": "0xprotocol", "frozenModelHash": "0xmodel",
                    "window": window, "status": "captured", "sources": {}}
        with tempfile.TemporaryDirectory(prefix="stability-archive-") as temporary:
            root = Path(temporary)
            folder = root / trial.DATA / window["id"]
            folder.mkdir(parents=True)
            for kind, obj in self.synthetic_sources().items():
                raw = trial.base.encoded(obj)
                spec = self.source_spec["sources"][kind]
                source = {"file": f"{kind}.json.gz", "rawSha256": trial.shared.digest(raw), "records": len(obj["features"]),
                    "captureStatus": "captured", "sourceUrl": "https://api.waterdata.usgs.gov/ogcapi/v1/collections/continuous/items?" + urlencode({
                        "f": "json", "monitoring_location_id": self.source_spec["stationId"], "parameter_code": spec["parameterCode"],
                        "time": f"{window['start']}/{window['end']}", "limit": "10000"})}
                manifest["sources"][kind] = source
                (folder / source["file"]).write_bytes(gzip.compress(raw, mtime=0))
            (folder / "manifest.json").write_bytes(trial.base.encoded(manifest))
            rows, info = trial.base.read_window(root / trial.DATA, window, self.source_spec, "0xprotocol", trial.CAPTURE_VERSION, "0xmodel")
            self.assertEqual(len(rows), 4)
            self.assertEqual(info["fullExpectedGrid"]["acceptedGridFraction"], 1.)
            self.assertEqual(len(trial.verify_archived_bodies(root, window, self.source_spec, manifest)), 3)
            manifest["status"] = "unavailable"
            manifest["sources"]["discharge"]["captureStatus"] = "unavailable"
            # Failed HTTP/schema responses can be non-JSON, but their complete bytes remain committed.
            failed = b"USGS upstream error"
            manifest["sources"]["discharge"]["rawSha256"] = trial.shared.digest(failed)
            (folder / "discharge.json.gz").write_bytes(gzip.compress(failed, mtime=0))
            self.assertEqual(len(trial.verify_archived_bodies(root, window, self.source_spec, manifest)), 3)
            (folder / "discharge.json.gz").write_bytes(gzip.compress(b"altered", mtime=0))
            with self.assertRaisesRegex(ValueError, "Archived source body hash"):
                trial.verify_archived_bodies(root, window, self.source_spec, manifest)

    def toy_windows(self):
        return [{"window": {"start": "2025-01-01T00:00:00Z"}, "rows": [
            {"origin": f"2025-01-{day:02d}T06:00:00Z", "actual": 10., "predictionsMgL": {
                trial.PERSISTENCE: 10. + day / 10, trial.RIDGE: 10. + day / 5, trial.FALLBACK: 10.}}
            for day in range(1, 15)]} for _ in range(4)]

    def test_bootstrap_uses_exactly_one_shared_draw_for_three_methods(self):
        class Draws:
            count = 0
            def randrange(self, size):
                self.count += 1
                return self.count % size
        draws = Draws()
        uncertainty = self.spec["uncertainty"] | {"iterations": 11}
        with patch.object(trial.random, "Random", return_value=draws):
            result = trial.bootstrap(self.toy_windows(), 48, uncertainty)
        self.assertEqual(draws.count, 11 * 4 * 7)
        self.assertEqual(result["nonemptyBlocksPerSeason"], [7] * 4)
        for bound in ("lowerGainMgL", "upperGainMgL"):
            self.assertAlmostEqual(result["gainAgainstBaselines"][trial.RIDGE][bound],
                                   2 * result["gainAgainstBaselines"][trial.PERSISTENCE][bound])
        # Multiple rows in the same calendar block are not extra resampling units.
        toy = self.toy_windows()[0]
        self.assertEqual(len(trial.calendar_blocks(toy["window"], [toy["rows"][0]] * 50 + [toy["rows"][-1]], 48)), 2)

    def test_bootstrap_keeps_equal_season_weight_and_is_deterministic(self):
        windows = self.toy_windows()
        for index, window in enumerate(windows):
            for row in window["rows"]:
                row["predictionsMgL"] = {trial.PERSISTENCE: 11. + index, trial.RIDGE: 12. + index, trial.FALLBACK: 10.}
        windows[-1]["rows"] *= 30
        uncertainty = self.spec["uncertainty"] | {"iterations": 100}
        a = trial.bootstrap(windows, 48, uncertainty)
        self.assertEqual(a, trial.bootstrap(windows, 48, uncertainty))
        self.assertAlmostEqual(a["gainAgainstBaselines"][trial.PERSISTENCE]["lowerGainMgL"], 2.5)
        self.assertAlmostEqual(a["gainAgainstBaselines"][trial.RIDGE]["upperGainMgL"], 3.5)
        windows[0]["rows"] = []
        self.assertEqual(trial.bootstrap(windows, 48, uncertainty)["status"], "insufficient-blocks")
        windows = self.toy_windows()
        windows[0]["predictionDiagnostics"] = {"nonfiniteScoreMethods": [trial.RIDGE]}
        self.assertEqual(trial.bootstrap(windows, 48, uncertainty)["status"], "invalid-prediction")

    def decision_fixture(self):
        windows = [{"dataScreenPassed": True, "subgroups": {"past-flat": {"pairs": 1}},
            "predictionDiagnostics": {"nonfinitePredictions": {m: 0 for m in trial.METHODS},
                "negativePredictions": {m: 0 for m in trial.METHODS}, "nonfiniteScoreMethods": []},
            "scores": {m: {"maeMgL": .99 if m == trial.FALLBACK else 1.} for m in trial.METHODS}} for _ in range(4)]
        bands = [{"status": "estimated", "gainAgainstBaselines": {m: {"lowerGainMgL": .001} for m in trial.BASELINES}} for _ in range(3)]
        return windows, trial.macro_scores(windows), bands

    def test_decision_rejects_one_season_loss_and_requires_each_baseline_and_each_sensitivity(self):
        windows, macro, bands = self.decision_fixture()
        classify = lambda: trial.classify(windows, macro, bands, self.spec["decision"])
        self.assertEqual(classify(), "credible-exploratory-improvement")  # Less than 10% is allowed.
        windows[2]["scores"][trial.RIDGE]["maeMgL"] = .98
        self.assertEqual(classify(), "observed-seasonal-tradeoff")
        windows[2]["scores"][trial.RIDGE]["maeMgL"] = 1.
        bands[2]["gainAgainstBaselines"][trial.RIDGE]["lowerGainMgL"] = 0.
        self.assertEqual(classify(), "inconclusive-gain")
        macro["gainAgainstBaselines"][trial.RIDGE]["gainMgL"] = 0.
        self.assertEqual(classify(), "no-overall-improvement")
        for window in windows:
            window["subgroups"]["past-flat"]["pairs"] = 0
        self.assertEqual(classify(), "stability-rule-not-exercised")
        windows[0]["predictionDiagnostics"]["negativePredictions"][trial.FALLBACK] = 1
        self.assertEqual(classify(), "invalid-prediction")
        windows[0]["dataScreenPassed"] = False
        self.assertEqual(classify(), "insufficient-data")

    def test_negative_predictions_are_unclipped_and_nonfinite_values_are_reported_as_invalid(self):
        rows, oxygen = self.rows()
        for value in (-.5, float("nan"), float("inf")):
            with self.subTest(value=value), patch.object(trial.shared, "prediction", return_value=value):
                result = trial.evaluate_rows(rows, oxygen, self.info(), self.spec, self.model)
            if math.isfinite(value):
                changing = next(row for row in result["rows"] if not row["historyFlat"])
                self.assertEqual(changing["predictionsMgL"][trial.FALLBACK], -.5)
                self.assertGreater(result["predictionDiagnostics"]["negativePredictions"][trial.FALLBACK], 0)
            else:
                self.assertEqual(result["predictionDiagnostics"]["nonfinitePredictions"][trial.RIDGE], len(rows))
                self.assertIsNone(result["scores"][trial.RIDGE])
                trial.base.encoded(result)  # Standard JSON, never NaN or Infinity.

    def test_missing_season_never_silently_becomes_three_season_macro_and_evaluation_cannot_fit(self):
        inputs = trial.frozen_inputs(trial.ROOT)
        with tempfile.TemporaryDirectory(prefix="stability-empty-") as temporary, \
             patch.object(trial.base, "fit", side_effect=AssertionError("fit forbidden")), \
             patch.object(trial.base, "typescript_fit", side_effect=AssertionError("fit forbidden")), \
             patch.object(trial.shared, "decimal_ridge", side_effect=AssertionError("fit forbidden")), \
             patch.object(trial, "frozen_inputs", return_value=inputs), \
             patch.object(trial.base, "read_window", side_effect=lambda folder, window, *args: ([], {"window": window, "status": "unavailable"})):
            report = trial.evaluate(Path(temporary))
        self.assertEqual(len(report["windows"]), 4)
        self.assertEqual(report["decision"], "insufficient-data")
        self.assertIsNone(report["macro"]["seasonalMeanMAEMgL"])
        self.assertFalse(report["modelRefittedDuringEvaluation"])

    def test_git_commit_snapshot_rejects_current_changes_and_manifest_rewrites(self):
        with tempfile.TemporaryDirectory(prefix="stability-git-") as temporary:
            root = Path(temporary)
            files = ["scripts/a.py", "protocol.json"]
            for filename in files:
                destination = root / filename
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(b"frozen\n")
            def git(*args):
                return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True).stdout
            git("init")
            git("add", ".")
            git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-m", "synthetic snapshot")
            items = [{"file": f, "rawSha256": trial.shared.digest((root / f).read_bytes())} for f in files]
            manifest = {"frozenAtCommit": git("rev-parse", "HEAD").decode().strip(), "implementationFiles": items,
                        "implementationSnapshotHash": trial.implementation_hash(items)}
            with patch.object(trial, "IMPLEMENTATION_FILES", files):
                self.assertTrue(trial.verify_implementation(root, manifest)["verifiedAgainstCurrentFilesAndGit"])
                (root / files[0]).write_bytes(b"changed\n")
                with self.assertRaisesRegex(ValueError, "Implementation bytes differ"):
                    trial.verify_implementation(root, manifest)
                manifest["implementationFiles"][0]["rawSha256"] = trial.shared.digest(b"changed\n")
                manifest["implementationSnapshotHash"] = trial.implementation_hash(manifest["implementationFiles"])
                with self.assertRaisesRegex(ValueError, "Implementation bytes differ"):
                    trial.verify_implementation(root, manifest)

    def test_cli_exclusive_report_and_offline_reverification_detect_tampering(self):
        report = {"decision": "insufficient-data", "macro": {"seasonalMeanMAEMgL": None}, "bootstrap": []}
        with tempfile.TemporaryDirectory(prefix="stability-report-") as temporary:
            path = Path(temporary) / "report.json.gz"
            with patch.object(sys, "argv", ["evaluate_stability.py", "evaluate", "--output", str(path)]), \
                 patch.object(trial, "evaluate", return_value=report), contextlib.redirect_stdout(io.StringIO()):
                trial.main()
            self.assertEqual(trial.read_report(path), report)
            with patch.object(sys, "argv", ["evaluate_stability.py", "evaluate", "--output", str(path)]), \
                 patch.object(trial, "evaluate", side_effect=AssertionError("must refuse before replay")):
                with self.assertRaisesRegex(ValueError, "never overwrite"):
                    trial.main()
            with patch.object(sys, "argv", ["evaluate_stability.py", "verify", "--report", str(path)]), \
                 patch.object(trial, "evaluate", return_value=report), contextlib.redirect_stdout(io.StringIO()):
                trial.main()
            path.write_bytes(gzip.compress(trial.base.encoded(report | {"decision": "credible-exploratory-improvement"}), mtime=0))
            with patch.object(sys, "argv", ["evaluate_stability.py", "verify", "--report", str(path)]), \
                 patch.object(trial, "evaluate", return_value=report):
                with self.assertRaises(AssertionError):
                    trial.main()


if __name__ == "__main__":
    unittest.main()
