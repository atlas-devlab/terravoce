"""Source availability must include absent origins and never imply a model fit."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import audit_training_readiness as readiness


class TrainingReadinessTests(unittest.TestCase):
    def test_missing_origins_stay_in_the_denominator_and_no_fit_occurs(self):
        with patch.object(readiness.shared, "decimal_ridge", side_effect=AssertionError("Unexpected fit")):
            report = readiness.audit()
        self.assertFalse(report["modelFitted"])
        self.assertFalse(report["forecastSkillEvaluated"])
        self.assertFalse(report["operationalModelChanged"])
        autumn = next(w for w in report["windows"] if w["window"]["id"] == "autumn-2024")
        self.assertEqual(autumn["alignment"]["eligibleOrigins"], 608)
        self.assertEqual(autumn["fullExpectedGrid"]["expectedOrigins"], 660)
        self.assertEqual(autumn["fullExpectedGrid"]["missingApprovedOxygenOrigins"], 52)
        self.assertAlmostEqual(autumn["fullExpectedGrid"]["acceptedGridFraction"], 595 / 660)

    def fixture(self):
        work = (readiness.ROOT / "work").resolve()
        work.mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix="training-readiness-", dir=work)
        root = Path(temporary.name).resolve()
        self.assertTrue(root.is_relative_to(work))
        self.addCleanup(temporary.cleanup)
        shutil.copytree(readiness.ROOT / "docs/datasets/usgs-willamette-training-audit", root / "docs/datasets/usgs-willamette-training-audit")
        return root

    def test_a_tampered_source_hash_is_rejected(self):
        root = self.fixture()
        path = root / "docs/datasets/usgs-willamette-training-audit/winter-2024/manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["sources"]["oxygen"]["rawSha256"] = "0xwrong"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Source hash mismatch"):
            readiness.audit(root)

    def test_an_unavailable_window_is_retained_and_not_counted_as_ready(self):
        root = self.fixture()
        path = root / "docs/datasets/usgs-willamette-training-audit/winter-2024/manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest.update(status="unavailable", error="fixed source request failed")
        path.write_text(json.dumps(manifest), encoding="utf-8")
        report = readiness.audit(root)
        self.assertFalse(report["allFourWindowsPassAvailabilityScreen"])
        self.assertEqual(len(report["windows"]), 4)
        self.assertEqual(report["windows"][0]["window"]["id"], "winter-2024")
        self.assertFalse(report["windows"][0]["readinessScreenPassed"])


if __name__ == "__main__":
    unittest.main()
