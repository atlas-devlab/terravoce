"""Independent fixture reconstruction must reject corruption without Node."""
import json
import pathlib
import shutil
import tempfile
import unittest

import audit_autonomous_source as reference


class AutonomousSourceReferenceTests(unittest.TestCase):
    def fixture(self):
        work = (reference.ROOT / "work").resolve()
        work.mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix="source-reference-", dir=work)
        root = pathlib.Path(temporary.name).resolve()
        self.assertTrue(root.is_relative_to(work))
        self.addCleanup(temporary.cleanup)
        dataset = root / "dataset"
        evidence = root / "reproduction.json"
        shutil.copytree(reference.DATASET, dataset)
        shutil.copyfile(reference.EVIDENCE, evidence)
        return dataset, evidence, reference.committed_hash()

    def rewrite_observations(self, dataset, change, rewrite_manifest):
        path = dataset / "response-02.json"
        raw = json.loads(path.read_bytes())
        change(raw)
        body = json.dumps(raw).encode()
        path.write_bytes(body)
        if rewrite_manifest:
            path = dataset / "manifest.json"
            archive = json.loads(path.read_bytes())
            entry = archive["responses"][2]
            entry["bytes"], entry["rawSha256"] = len(body), reference.sha(body)
            path.write_text(json.dumps(archive), encoding="utf-8")

    def test_reconstructs_exact_fixture_without_javascript(self):
        result = reference.audit()
        self.assertEqual(result["observations"], 97)
        self.assertEqual(result["evidenceHash"], reference.committed_hash())
        self.assertFalse(result["physicalTruthVerified"])
        self.assertFalse(result["operationalEligible"])

    def test_changed_raw_measurement_fails(self):
        dataset, evidence, expected = self.fixture()
        self.rewrite_observations(dataset, lambda raw: raw["features"][0]["properties"].update(value="9.9"), False)
        with self.assertRaisesRegex(ValueError, "Raw response hash mismatch"):
            reference.audit(dataset, evidence, expected)

    def test_raw_and_manifest_rewrite_still_fails_external_checkpoint(self):
        dataset, evidence, expected = self.fixture()
        self.rewrite_observations(dataset, lambda raw: raw["features"][0]["properties"].update(value="9.9"), True)
        with self.assertRaisesRegex(ValueError, "External evidence commitment mismatch"):
            reference.audit(dataset, evidence, expected)

    def test_changed_normalized_observation_fails(self):
        dataset, evidence, expected = self.fixture()
        saved = json.loads(evidence.read_bytes())
        saved["reproduction"]["observations"][0]["value"] = 9.9
        evidence.write_text(json.dumps(saved), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Saved reproduction mismatch"):
            reference.audit(dataset, evidence, expected)

    def test_external_hash_must_not_be_substituted(self):
        with self.assertRaisesRegex(ValueError, "External evidence commitment mismatch"):
            reference.audit(expected_hash="0x" + "f" * 64)

    def test_unit_change_is_detected_by_independent_reconstruction(self):
        dataset, evidence, expected = self.fixture()
        self.rewrite_observations(dataset, lambda raw: raw["features"][0]["properties"].update(unit_of_measure="ppm"), True)
        with self.assertRaisesRegex(ValueError, "Observation identity or unit mismatch"):
            reference.audit(dataset, evidence, expected)


if __name__ == "__main__":
    unittest.main()
