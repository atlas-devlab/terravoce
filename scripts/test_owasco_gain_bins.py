"""Invented data only: fixed-bin arithmetic, cohort integrity and non-overwrite."""
import copy
import hashlib
import io
import json
import math
import tempfile
import unittest
from contextlib import redirect_stderr
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import owasco_gain_bins as g


def row(p=0., r=0., actual=0., index=0):
    origin = datetime(2001, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=30 * index)
    return {"origin": origin.isoformat().replace("+00:00", "Z"), "actual": actual,
            "predictionsMgL": {g.P: p, g.R: r, g.F: p if abs(r-p) <= .1 else r}}


def fixture(rows, maes=None):
    if maes is None:
        maes = [sum(abs(r["predictionsMgL"][m]-r["actual"]) for r in rows)/len(rows)
                for m in g.METHODS]
    return {"rows": rows, "scores": {m: {"pairs": len(rows), "maeMgL": mae}
                                     for m, mae in zip(g.METHODS, maes)}}


def bound(data, expected_pairs=None, origin_digest=None):
    raw = (json.dumps(data, allow_nan=True) + "\n").encode()
    binding = g.InputBinding(hashlib.sha256(raw).hexdigest(),
                             origin_digest or g.origin_hash(data["rows"]),
                             len(data["rows"]) if expected_pairs is None else expected_pairs)
    return raw, binding


def invented_protocol(path, binding):
    data = {"status": "ADOPTED_BEFORE_FIRST_BIN_CALCULATION",
            "adoptedAtUTC": "2000-01-01T00:00:00Z",
            "sourceProposalSHA256": g.PROPOSAL_SHA256,
            "inputBinding": {"rawFileSHA256": binding.sha256,
                             "orderedOriginTimestampListSHA256": binding.origin_sha256,
                             "existingSavedReferences_notNewCalculations": {
                                 m: {"pairs": binding.pairs} for m in ("P", "R", "F_original")}}}
    raw = json.dumps(data).encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


class OwascoGainBinsTests(unittest.TestCase):
    def analyze(self, data, **kwargs):
        return g.analyze_bytes(*bound(data, **kwargs))

    def test_all_boundaries_and_adjacent_binary64_values_have_no_epsilon(self):
        for boundary, below, exact, above in ((.025, 0, 1, 1), (.05, 1, 2, 2),
                                              (.075, 2, 3, 3), (.1, 3, 3, 4)):
            for sign in (-1, 1):
                for magnitude, expected in ((math.nextafter(boundary, -math.inf), below),
                                            (boundary, exact),
                                            (math.nextafter(boundary, math.inf), above)):
                    with self.subTest(boundary=boundary, sign=sign, magnitude=magnitude):
                        # P=0 avoids inventing an exactly decimal subtraction at a nonzero P.
                        result = self.analyze(fixture([row(r=sign*magnitude)]))
                        self.assertEqual(result["bins"][expected]["count"], 1)
                        self.assertEqual(result["originalFilter"]["activeBin"], "B5")
        self.assertEqual(g.bin_index(0), 0)

    def test_actual_binary_subtraction_is_not_decimal_rounding(self):
        result = self.analyze(fixture([row(p=10., r=10.1)]))
        self.assertEqual(result["bins"][3]["count"], 1)
        self.assertEqual(result["bins"][4]["count"], 0)
        # The above subtraction is just below .1 in binary64, so saved F stays P.

    def test_global_denominator_empty_bins_cells_and_filter_bridge(self):
        rows = [row(index=i) for i in range(1273)]
        rows += [row(r=.03, index=1273), row(r=.2, actual=.2, index=1274)]
        result = self.analyze(fixture(rows, [.2/1275, .03/1275, 0.]))
        b1, b2, b3, b4, b5 = result["bins"]
        self.assertEqual([b["count"] for b in result["bins"]], [1273, 1, 0, 0, 1])
        self.assertAlmostEqual(b2["meanGain"], -.03)
        self.assertAlmostEqual(b2["globalGainContribution"], -.03/1275)
        self.assertAlmostEqual(b5["meanGain"], .2)
        self.assertAlmostEqual(result["overall"]["meanGain"], .17/1275)
        self.assertAlmostEqual(result["originalFilter"]["globalGainContribution"], .2/1275)
        self.assertEqual(result["originalFilter"]["maeMgL"], 0.)
        self.assertEqual(b1["globalDenominator"], 1275)
        for empty in (b3, b4, b2["observedChange"]["changed"],
                      b5["observedChange"]["unchanged"]):
            self.assertEqual(empty["count"], 0)
            self.assertEqual(empty["sumGain"], 0.)
            self.assertEqual(empty["globalGainContribution"], 0.)
            for key in ("meanGain", "meanErrorP", "meanErrorR"):
                self.assertIsNone(empty[key])
        self.assertEqual(result["observedChangeTotals"]["unchanged"]["count"], 1274)
        self.assertEqual(result["observedChangeTotals"]["changed"]["count"], 1)
        json.dumps(result, allow_nan=False)

    def test_outcome_strata_use_exact_equality_not_tolerance(self):
        rows = [row(p=1., r=1., actual=1., index=0),
                row(p=1., r=1., actual=math.nextafter(1., math.inf), index=1)]
        result = self.analyze(fixture(rows))
        self.assertEqual(result["observedChangeTotals"]["unchanged"]["count"], 1)
        self.assertEqual(result["observedChangeTotals"]["changed"]["count"], 1)

    def test_wrong_raw_hash_and_wrong_canonical_hash_stop_before_scoring(self):
        raw, binding = bound(fixture([row()]))
        for bad_raw, bad_binding in ((raw+b" ", binding),
                                     (raw, g.InputBinding(binding.sha256, "0"*64, 1))):
            with self.subTest(binding=bad_binding), patch.object(g, "_observations") as scoring:
                with self.assertRaisesRegex(ValueError, "SHA-256"):
                    g.analyze_bytes(bad_raw, bad_binding)
                scoring.assert_not_called()

    def test_missing_and_duplicate_rows_stop_without_changing_denominator(self):
        data = fixture([row(index=0), row(index=1)])
        missing = copy.deepcopy(data)
        missing["rows"].pop()
        with self.assertRaisesRegex(ValueError, "Row count"):
            self.analyze(missing, expected_pairs=2)
        duplicate = copy.deepcopy(data)
        duplicate["rows"][1] = copy.deepcopy(duplicate["rows"][0])
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.analyze(duplicate, origin_digest=g.origin_hash(data["rows"]))
        # The fingerprint retains both occurrences; it never silently deduplicates.
        self.assertEqual(len(g.canonical_origins(duplicate["rows"])), 2)
        self.assertNotEqual(g.origin_hash(duplicate["rows"]), g.origin_hash(data["rows"]))

    def test_duplicate_instants_with_different_offsets_are_rejected(self):
        data = fixture([row(index=0), row(index=1)])
        original_digest = g.origin_hash(data["rows"])
        data["rows"][1]["origin"] = "2001-01-01T01:00:00+01:00"
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.analyze(data, origin_digest=original_digest)

    def test_missing_nonfinite_boolean_and_overflowing_fields_are_rejected(self):
        for value in (None, True, "0", math.nan, math.inf, -math.inf):
            for field in ("actual", g.P, g.R, g.F):
                data = fixture([row()])
                if field == "actual":
                    data["rows"][0][field] = value
                else:
                    data["rows"][0]["predictionsMgL"][field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    self.analyze(data)
        data = fixture([row()])
        del data["rows"][0]["predictionsMgL"][g.R]
        with self.assertRaisesRegex(ValueError, "numeric field"):
            self.analyze(data)
        data = fixture([row()])
        data["rows"][0]["predictionsMgL"].update({g.P: -1e308, g.R: 1e308, g.F: 1e308})
        with self.assertRaisesRegex(ValueError, "score"):
            self.analyze(data)

    def test_bad_timestamp_or_saved_score_is_rejected(self):
        data = fixture([row()])
        data["rows"][0]["origin"] = "2001-01-01T00:00:00"
        with self.assertRaisesRegex(ValueError, "aware origin"):
            self.analyze(data)
        for field, value in (("pairs", 2), ("pairs", True), ("maeMgL", -.1),
                             ("maeMgL", None), ("maeMgL", .01)):
            data = fixture([row()])
            data["scores"][g.R][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.analyze(data)

    def test_original_filter_is_checked_exactly_even_inside_recomposition_tolerance(self):
        for r, wrong_f in ((.1, .1), (math.nextafter(.1, math.inf), 0.),
                            (.03, math.nextafter(0., math.inf))):
            data = fixture([row(r=r)])
            data["rows"][0]["predictionsMgL"][g.F] = wrong_f
            with self.subTest(r=r), self.assertRaisesRegex(ValueError, "frozen gate"):
                self.analyze(data)

    def test_strict_json_rejects_duplicate_keys_and_nonstandard_constants(self):
        for raw in (b'{"rows": [], "rows": []}', b'{"other": NaN}'):
            binding = g.InputBinding(hashlib.sha256(raw).hexdigest(), "0"*64, 1)
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                g.analyze_bytes(raw, binding)

    def test_new_output_only_input_unchanged_and_invalid_input_leaves_no_output(self):
        raw, binding = bound(fixture([row(r=.03)]))
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/"input.json"
            source.write_bytes(raw)
            protocol = Path(tmp)/"protocol.json"
            protocol_hash = invented_protocol(protocol, binding)
            output = Path(tmp)/"new-output"
            receipt = g.run(source, output, protocol, binding, protocol_hash)
            report_bytes = Path(receipt["file"]).read_bytes()
            self.assertEqual(receipt["sha256"], hashlib.sha256(report_bytes).hexdigest())
            self.assertEqual(source.read_bytes(), raw)
            self.assertIn(b'null', report_bytes)
            report = json.loads(report_bytes)
            self.assertEqual(report["protocolSHA256"], protocol_hash)
            self.assertEqual(report["input"]["file"], g.INPUT_REPOSITORY_PATH)
            self.assertEqual(report["protocol"]["file"], g.PROTOCOL_REPOSITORY_PATH)
            self.assertFalse(Path(report["input"]["file"]).is_absolute())
            self.assertFalse(Path(report["protocol"]["file"]).is_absolute())
            with self.assertRaisesRegex(ValueError, "already exist"):
                g.run(source, output, protocol, binding, protocol_hash)
            self.assertEqual(Path(receipt["file"]).read_bytes(), report_bytes)
            bad_output = Path(tmp)/"never-created"
            source.write_bytes(raw+b" ")
            with self.assertRaises(ValueError):
                g.run(source, bad_output, protocol, binding, protocol_hash)
            self.assertFalse(bad_output.exists())

    def test_wrong_protocol_stops_before_saved_prediction_input_is_read(self):
        raw, binding = bound(fixture([row()]))
        with tempfile.TemporaryDirectory() as tmp:
            protocol = Path(tmp)/"protocol.json"
            digest = invented_protocol(protocol, binding)
            protocol.write_bytes(protocol.read_bytes()+b" ")
            output = Path(tmp)/"not-created"
            with patch.object(g, "analyze_bytes") as scoring:
                with self.assertRaisesRegex(ValueError, "protocol SHA-256"):
                    g.run(Path(tmp)/"not-even-present.json", output, protocol, binding, digest)
                scoring.assert_not_called()
            self.assertFalse(output.exists())

    def test_report_replay_rejects_altered_sums_contributions_and_provenance_without_writes(self):
        raw, binding = bound(fixture([row(r=.03)]))
        with tempfile.TemporaryDirectory() as tmp:
            source, protocol = Path(tmp)/"input.json", Path(tmp)/"protocol.json"
            source.write_bytes(raw)
            protocol_hash = invented_protocol(protocol, binding)
            receipt = g.run(source, Path(tmp)/"output", protocol, binding, protocol_hash)
            report_file = Path(receipt["file"])
            original = json.loads(report_file.read_bytes())
            # A valid historical timestamp is metadata, not the current replay time.
            original["createdAtUTC"] = "2001-01-01T00:00:00Z"
            report_file.write_text(json.dumps(original), encoding="utf-8")
            before = report_file.read_bytes()
            verified = g.verify_report(source, protocol, report_file, binding, protocol_hash)
            self.assertTrue(verified["verified"])
            self.assertFalse(verified["writes"])
            self.assertEqual(report_file.read_bytes(), before)
            paths_before = sorted(str(p) for p in Path(tmp).rglob("*"))
            mutations = [
                ("sum", lambda d: d["bins"][0].__setitem__("sumGain", .5)),
                ("contribution", lambda d: d["bins"][0].__setitem__("globalGainContribution", .5)),
                ("implementation", lambda d: d.__setitem__("implementationSHA256", "0"*64)),
                ("protocol", lambda d: d.__setitem__("protocolSHA256", "0"*64)),
                ("extra", lambda d: d.__setitem__("unexpected", True)),
                ("type", lambda d: d["bins"][0].__setitem__("count", True)),
            ]
            for name, mutate in mutations:
                altered = copy.deepcopy(original)
                mutate(altered)
                report_file.write_text(json.dumps(altered), encoding="utf-8")
                before = report_file.read_bytes()
                with self.subTest(name=name), self.assertRaisesRegex(ValueError, "Report mismatch"):
                    g.verify_report(source, protocol, report_file, binding, protocol_hash)
                self.assertEqual(report_file.read_bytes(), before)
                self.assertEqual(sorted(str(p) for p in Path(tmp).rglob("*")), paths_before)
            for stamp in (None, "not-a-date", "2001-01-01T00:00:00",
                          "2001-01-01T00:00:00+01:00", "1999-12-31T23:59:59Z"):
                altered = copy.deepcopy(original)
                altered["createdAtUTC"] = stamp
                report_file.write_text(json.dumps(altered), encoding="utf-8")
                with self.subTest(stamp=stamp), self.assertRaises(ValueError):
                    g.verify_report(source, protocol, report_file, binding, protocol_hash)
            self.assertEqual(source.read_bytes(), raw)

    def test_cli_cannot_override_pinned_binding_and_failure_is_explicit(self):
        raw, _ = bound(fixture([row()]))
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/"invented.json"
            source.write_bytes(raw)
            protocol = Path(tmp)/"protocol.json"
            invented_protocol(protocol, bound(fixture([row()]))[1])
            output = Path(tmp)/"not-created"
            err = io.StringIO()
            with redirect_stderr(err):
                status = g.main(["--input", str(source), "--protocol", str(protocol),
                                 "--output-dir", str(output)])
            self.assertEqual(status, 2)
            self.assertIn("Stopped: Adopted protocol SHA-256", err.getvalue())
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
