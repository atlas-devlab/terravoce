"""Synthetic-only checks; all source bodies, Git reads and HTTP calls are invented."""
import copy
import gzip
import json
import subprocess
import tempfile
import unittest
from contextlib import ExitStack, contextmanager
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import owasco_temporal_validation as temporal


def synthetic_model():
    return {"recipe": {"name": "synthetic-frozen-ridge", "features": temporal.FEATURES,
            "featureWidth": 8, "horizonSeconds": 3600, "alpha": 100},
        "model": {"alpha": 100, "mean": [0] * 8, "scale": [1] * 8,
            "coefficients": [0] * 8, "residualIntercept": .05},
        "training": {"featureRanges": [{"feature": f, "min": -100, "max": 100}
                                       for f in temporal.FEATURES]}}


def synthetic_catalogue():
    return {"type": "FeatureCollection", "links": [], "features": [
        {"id": s["timeSeriesId"], "properties": {"monitoring_location_id": temporal.STATION,
         "parameter_code": s["parameterCode"], "statistic_id": "00011", "unit_of_measure": s["unit"],
         "sublocation_identifier": "EXO 1", "web_description": "Depth at 3 feet", "primary": "Primary",
         "computation_identifier": "Instantaneous"}} for s in temporal.SOURCES.values()]}


def synthetic_collection(kind, count=1345, start=None):
    start = temporal.lake.shared.instant(temporal.WINDOW["start"]) if start is None else start
    spec = temporal.SOURCES[kind]
    return temporal.encoded({"type": "FeatureCollection", "links": [], "features": [
        {"id": f"synthetic-{kind}-{i}", "properties": {
            "time": temporal.lake.shared.iso(start + timedelta(minutes=30 * i)),
            "monitoring_location_id": temporal.STATION, "parameter_code": spec["parameterCode"],
            "time_series_id": spec["timeSeriesId"], "statistic_id": "00011", "unit_of_measure": spec["unit"],
            "value": "8" if kind == "oxygen" else "20", "approval_status": "Approved", "qualifier": None,
            "last_modified": "2026-01-01T00:00:00Z"}} for i in range(count)]})


@contextmanager
def fixture():
    """Only temporary synthetic files; no real protocol/model/cache is read."""
    with tempfile.TemporaryDirectory(prefix="synthetic-owasco-") as directory, ExitStack() as stack:
        root = Path(directory)
        for file in temporal.REQUIRED_FILES | {temporal.PREVIOUS}:
            path = root / file
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(("synthetic fixture: " + file + "\n").encode())
        (root / temporal.MODEL).write_bytes(temporal.encoded(synthetic_model()))
        (root / temporal.DEVELOPMENT).write_bytes(temporal.encoded({
            "selectedThresholdMgL": .1, "status": "promising-in-development-only"}))
        metadata_file = "docs/datasets/owasco-lake-transfer/time-series-metadata.json.gz"
        metadata_raw = temporal.encoded(synthetic_catalogue())
        (root / metadata_file).write_bytes(gzip.compress(metadata_raw, mtime=0))
        model_hash = temporal.sha((root / temporal.MODEL).read_bytes())
        development_hash = temporal.sha((root / temporal.DEVELOPMENT).read_bytes())
        previous_hash = temporal.sha((root / temporal.PREVIOUS).read_bytes())
        spec = {"version": "owasco-frozen-temporal-v1", "stationId": temporal.STATION,
            "window": copy.deepcopy(temporal.WINDOW), "sources": copy.deepcopy(temporal.SOURCES),
            "horizonSeconds": 3600, "features": temporal.FEATURES[:], "methods": list(temporal.METHODS),
            "primaryMetric": "MAE in mg/L on the identical accepted origin-target cohort",
            "baseModel": {"file": temporal.MODEL, "rawSha256": model_hash},
            "development": {"file": temporal.DEVELOPMENT, "rawSha256": development_hash,
                            "selectedThresholdMgL": .1},
            "previousPrimaryEvaluation": {"file": temporal.PREVIOUS, "rawSha256": previous_hash},
            "sourceChoice": {"metadataFile": metadata_file, "metadataRawSha256": temporal.sha(metadata_raw)},
            "eligibility": {"expectedOrigins": 1332, "minimumAcceptedPairs": 1000,
                            "minimumExpectedGridCoverage": .9},
            "uncertainty": {"blockHours": [48, 24, 72], "iterations": 5000, "seed": 20261015,
                            "confidenceFraction": .95, "minimumNonemptyBlocks": 4},
            "decision": {"numericalToleranceMgL": temporal.TOL, "primaryBaseline": temporal.P,
                         "operationalPromotion": False, "practicalEnvironmentalBenefitDefined": False},
            "capture": {"maximumBodyBytes": temporal.LIMIT, "exclusiveAttemptBeforeHTTP": True,
                "automaticRetries": False, "redirects": False, "replaceFailedWindow": False,
                "officialHost": "api.waterdata.usgs.gov",
                "endpoint": "https://api.waterdata.usgs.gov/ogcapi/v1/collections/continuous/items",
                "explicitTimeSeriesFilter": True},
            "implementationFiles": sorted(temporal.REQUIRED_FILES)}
        protocol_raw = temporal.encoded(spec)
        (root / temporal.PROTOCOL).write_bytes(protocol_raw)
        historical = {file: temporal.sha((root / file).read_bytes()) for file in temporal.HISTORICAL_HASHES}
        for name, value in {"PROTOCOL_SHA256": temporal.sha(protocol_raw), "HISTORICAL_HASHES": historical,
                            "MODEL_HASH": model_hash, "DEVELOPMENT_HASH": development_hash,
                            "PREVIOUS_HASH": previous_hash}.items():
            stack.enter_context(patch.object(temporal, name, value))
        revision = "a" * 40
        snapshot = {file: (root / file).read_bytes() for file in spec["implementationFiles"]}

        def git_show(arguments, **kwargs):
            if arguments[:2] != ["git", "show"] or not arguments[2].startswith(revision + ":"):
                raise AssertionError("Only the invented frozen Git object can be read")
            return subprocess.CompletedProcess(arguments, 0, stdout=snapshot[arguments[2].split(":", 1)[1]])

        git = stack.enter_context(patch.object(temporal.subprocess, "run", side_effect=git_show))
        network = stack.enter_context(patch.object(temporal, "download",
            side_effect=AssertionError("HTTP must be explicitly mocked by the synthetic test")))
        yield SimpleNamespace(root=root, spec=spec, snapshot=snapshot, revision=revision,
                              network=network, git=git)


class TemporalValidationTests(unittest.TestCase):
    def test_wrong_window_series_threshold_seed_and_reduced_block_rule_stop_before_http(self):
        changes = [lambda s: s["window"].update(start="2020-07-01T00:00:00Z"),
                   lambda s: s["sources"]["oxygen"].update(timeSeriesId="another-depth"),
                   lambda s: s["development"].update(selectedThresholdMgL=.2),
                   lambda s: s["uncertainty"].update(seed=20261016),
                   lambda s: s["uncertainty"].update(blockHours=[48])]
        for change in changes:
            with self.subTest(change=change), fixture() as f:
                spec = copy.deepcopy(f.spec)
                change(spec)
                raw = temporal.encoded(spec)
                (f.root / temporal.PROTOCOL).write_bytes(raw)
                # Even a changed hash pin cannot turn another window/recipe into this study.
                with patch.object(temporal, "PROTOCOL_SHA256", temporal.sha(raw)):
                    with self.assertRaises(ValueError):
                        temporal.capture(f.root, f.revision)
                f.network.assert_not_called()
                self.assertFalse((f.root / temporal.DATA / "capture-attempt.json").exists())

    def test_protocol_byte_change_and_historical_byte_change_are_rejected(self):
        for changed in (temporal.PROTOCOL, Path("scripts/lake_transfer.py")):
            with self.subTest(file=changed), fixture() as f:
                path = f.root / changed
                path.write_bytes(path.read_bytes() + b"\n")
                with self.assertRaisesRegex(ValueError, "protocol bytes changed|Historical frozen file changed"):
                    temporal.capture(f.root, f.revision)
                f.network.assert_not_called()

    def test_changed_commit_bytes_and_short_commit_stop_before_attempt_or_http(self):
        with fixture() as f:
            f.snapshot["scripts/owasco_temporal_validation.py"] = b"different committed adapter"
            with self.assertRaisesRegex(ValueError, "differ from frozen Git"):
                temporal.capture(f.root, f.revision)
            with self.assertRaisesRegex(ValueError, "full frozen Git commit"):
                temporal.preflight(f.root, "main")
            f.network.assert_not_called()
            self.assertFalse((f.root / temporal.DATA / "capture-attempt.json").exists())

    def test_exclusive_attempt_precedes_each_request_and_complete_synthetic_receipt_verifies(self):
        original_globals = (temporal.lake.DATA, temporal.lake.PROTOCOL, copy.deepcopy(temporal.lake.WINDOW))
        with fixture() as f:
            def response(url):
                attempt = json.loads((f.root / temporal.DATA / "capture-attempt.json").read_bytes())
                self.assertEqual(attempt["window"], temporal.WINDOW)
                self.assertEqual(attempt["protocolSHA256"], temporal.PROTOCOL_SHA256)
                self.assertTrue(attempt["verifiedAgainstCurrentFilesAndGit"])
                self.assertEqual(len(attempt["implementationFiles"]), 17)
                self.assertEqual(f.git.call_count, 17)
                query = parse_qs(urlparse(url).query)
                self.assertEqual(query["time"], [temporal.WINDOW["start"] + "/" + temporal.WINDOW["end"]])
                kind = next(k for k, s in temporal.SOURCES.items() if query["time_series_id"] == [s["timeSeriesId"]])
                return 200, synthetic_collection(kind)

            self.assertFalse(temporal.preflight(f.root, f.revision)["captureStarted"])
            f.git.reset_mock()
            f.network.side_effect = response
            manifest = temporal.capture(f.root, f.revision)
            self.assertTrue(manifest["captureEligible"])
            self.assertEqual(f.network.call_count, 2)
            f.network.reset_mock()
            f.network.side_effect = AssertionError("Offline evaluation must never use HTTP")
            report = temporal.evaluate(f.root)
            self.assertEqual(report["window"], temporal.WINDOW)
            self.assertEqual(report["decision"], "no-overall-improvement")
            self.assertEqual(report["fullExpectedGrid"]["expectedOrigins"], 1332)
            self.assertEqual(len(report["rows"]), 1332)
            self.assertEqual(report["rows"][0]["origin"], "2020-08-01T05:30:00.000Z")
            self.assertEqual(report["rows"][-1]["target"], "2020-08-29T00:00:00.000Z")
            self.assertEqual([b["blockHours"] for b in report["bootstrap"]], [48, 24, 72])
            self.assertEqual(report["recompositionChecks"]["status"], "passed")
            path = f.root / "synthetic-report.json"
            path.write_bytes(temporal.encoded(report))
            temporal.verify(f.root, path)
            changed = copy.deepcopy(report)
            changed["scores"][temporal.F]["maeMgL"] = 1
            path.write_bytes(temporal.encoded(changed))
            with self.assertRaises(AssertionError):
                temporal.verify(f.root, path)
            f.network.assert_not_called()
        self.assertEqual(original_globals, (temporal.lake.DATA, temporal.lake.PROTOCOL, temporal.lake.WINDOW))

    def test_http_and_transport_failures_are_archived_and_cannot_be_retried(self):
        with fixture() as f:
            f.network.side_effect = [(503, b"synthetic service unavailable"), OSError("synthetic connection failure")]
            manifest = temporal.capture(f.root, f.revision)
            self.assertFalse(manifest["captureEligible"])
            self.assertEqual(f.network.call_count, 2)
            body = f.root / temporal.DATA / "oxygen.json.gz"
            self.assertEqual(gzip.decompress(body.read_bytes()), b"synthetic service unavailable")
            self.assertFalse((f.root / temporal.DATA / "temperature.json.gz").exists())
            attempt = (f.root / temporal.DATA / "capture-attempt.json").read_bytes()
            report = temporal.evaluate(f.root)
            self.assertEqual(report["decision"], "insufficient-data")
            self.assertEqual(report["rows"], [])
            with self.assertRaisesRegex(ValueError, "already exist"):
                temporal.capture(f.root, f.revision)
            self.assertEqual((f.root / temporal.DATA / "capture-attempt.json").read_bytes(), attempt)
            self.assertEqual(f.network.call_count, 2)

    def test_attempt_only_after_interrupted_capture_is_still_not_repeatable(self):
        with fixture() as f:
            path = f.root / temporal.DATA / "capture-attempt.json"
            path.write_bytes(b"invented prior interrupted attempt")
            with self.assertRaisesRegex(ValueError, "already exist"):
                temporal.capture(f.root, f.revision)
            self.assertEqual(path.read_bytes(), b"invented prior interrupted attempt")
            f.network.assert_not_called()

    def test_wrong_period_response_is_archived_as_failure_without_substitution(self):
        with fixture() as f:
            july = temporal.lake.shared.instant("2020-07-01T00:00:00Z")
            f.network.side_effect = [(200, synthetic_collection("oxygen", count=1, start=july)),
                                     (200, synthetic_collection("temperature", count=1, start=july))]
            manifest = temporal.capture(f.root, f.revision)
            self.assertFalse(manifest["captureEligible"])
            self.assertIn("Out-of-period", manifest["sources"]["oxygen"]["error"])
            self.assertEqual(temporal.evaluate(f.root)["decision"], "insufficient-data")
            self.assertEqual(f.network.call_count, 2)

    def test_false_manifest_commitments_urls_timers_and_states_are_rejected_offline(self):
        with fixture() as f:
            f.network.side_effect = [(503, b"synthetic failure"), (503, b"synthetic failure")]
            good = temporal.capture(f.root, f.revision)
            path = f.root / temporal.DATA / "manifest.json"
            changes = [lambda m: m.update(attemptSHA256="0" * 64),
                lambda m: m.update(protocolSHA256="0" * 64), lambda m: m.update(captureEligible=True),
                lambda m: m["sources"]["oxygen"].update(sourceUrl="https://example.invalid/another-window"),
                lambda m: m["sources"]["oxygen"].update(file="other.json.gz"),
                lambda m: m["sources"]["oxygen"].update(startedAtUTC="2000-01-01T00:00:00Z"),
                lambda m: m["sources"]["oxygen"].pop("rawBytes"),
                lambda m: m["sources"]["oxygen"].update(status="captured")]
            f.network.reset_mock()
            f.network.side_effect = AssertionError("Manifest validation is offline")
            for change in changes:
                with self.subTest(change=change):
                    altered = copy.deepcopy(good)
                    change(altered)
                    path.write_bytes(temporal.encoded(altered))
                    with self.assertRaises(ValueError):
                        temporal.evaluate(f.root)
            f.network.assert_not_called()

    def test_modified_archived_failure_body_is_not_accepted_offline(self):
        with fixture() as f:
            f.network.side_effect = [(503, b"synthetic failure"), (503, b"synthetic failure")]
            temporal.capture(f.root, f.revision)
            (f.root / temporal.DATA / "oxygen.json.gz").write_bytes(gzip.compress(b"changed", mtime=0))
            with self.assertRaisesRegex(ValueError, "Archived source body changed"):
                temporal.evaluate(f.root)
            self.assertEqual(f.network.call_count, 2)

    def test_valid_but_empty_collections_fail_completeness_without_division_by_zero(self):
        with fixture() as f:
            f.network.side_effect = [(200, synthetic_collection("oxygen", count=0)),
                                     (200, synthetic_collection("temperature", count=0))]
            self.assertTrue(temporal.capture(f.root, f.revision)["captureEligible"])
            report = temporal.evaluate(f.root)
            self.assertFalse(report["dataScreenPassed"])
            self.assertEqual(report["decision"], "insufficient-data")
            self.assertEqual(report["fullExpectedGrid"]["expectedOrigins"], 1332)

    def test_recomposition_rejects_a_different_daily_cohort_or_error_sum(self):
        row = {"actual": 8, "predictionsMgL": {m: 8 for m in temporal.METHODS}}
        summary = temporal.lake.summarize([row])
        daily = [{"originDayUTC": "invented", **temporal.lake.summarize([row])}]
        temporal.check_recomposition([row], summary, daily)
        daily[0]["scores"][temporal.F]["maeMgL"] = .2
        with self.assertRaisesRegex(ValueError, "recomposition failed"):
            temporal.check_recomposition([row], summary, daily)
        daily[0]["scores"][temporal.F]["pairs"] = 2
        with self.assertRaisesRegex(ValueError, "cohort differs"):
            temporal.check_recomposition([row], summary, daily)


if __name__ == "__main__":
    unittest.main()
