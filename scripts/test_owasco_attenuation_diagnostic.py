"""Entirely invented fixtures; no archived environmental rows are opened."""
import copy
import inspect
import math
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest import mock

import owasco_attenuation_diagnostic as d


def row(origin="2020-01-01T06:00:00Z", p=10.0, ridge=10.18, actual=10.10):
    stamp = d.instant(origin)
    history = [{"timeUTC": (stamp-timedelta(minutes=30*(11-j))).isoformat().replace("+00:00", "Z"),
                "value": p if j == 11 else p-.01} for j in range(12)]
    values = [item["value"] for item in history]
    clock = (stamp.hour*3600+stamp.minute*60+stamp.second)/86400*2*math.pi
    old = None if not d.finite(ridge) or not d.finite(ridge-p) else p if abs(ridge-p) <= .1 else ridge
    return {"origin": origin, "target": (stamp+timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
            "actual": actual, "oxygenHistory": history,
            "features": [p, p-values[-2], p-values[-5], p-values[0], math.sin(clock), math.cos(clock), 17.0, -.3],
            "predictionsMgL": {d.P: p, d.R: ridge, d.F: old}}


def source(rows):
    return {"stationId": "USGS-425327076313601", "horizonSeconds": 3600,
            "window": {"start": "2020-01-01T00:00:00Z", "end": "2020-01-03T00:00:00Z"},
            "rows": rows, "scores": {method: None if any(not d.finite(r["predictionsMgL"][method]) for r in rows) else
                {"pairs": len(rows), "maeMgL": math.fsum(abs(r["predictionsMgL"][method]-r["actual"]) for r in rows)/len(rows)}
                for method in (d.P, d.R, d.F)}}


def binding(data, name="invented"):
    return {"id": name, "file": name+".json", "rawSha256": d.sha(d.encoded(data)),
            "pairs": len(data["rows"]), "window": data["window"]}


class AttenuationTest(unittest.TestCase):
    def test_exact_boundary_and_nextafter(self):
        for ridge in (.1, -.1, math.nextafter(.1, 0.0), math.nextafter(-.1, 0.0), 0.0, -0.0):
            value = d.attenuate_prediction(0.0, ridge)
            self.assertFalse(value["gateActive"])
            self.assertEqual(value["predictionMgL"], 0.0)
        for ridge in (math.nextafter(.1, math.inf), math.nextafter(-.1, -math.inf)):
            value = d.attenuate_prediction(0.0, ridge)
            self.assertTrue(value["gateActive"])
            expected = abs(ridge)-.1
            self.assertEqual(value["attenuatedCorrectionMgL"], expected if ridge > 0 else -expected)

    def test_exact_operation_order_for_positive_and_negative(self):
        for p, ridge in ((10.0, 10.18), (10.0, 9.82), (2.0, 2.1), (1e10, 1e10+1)):
            c = ridge-p
            result = d.attenuate_prediction(p, ridge)
            expected = p if abs(c) <= .1 else p+((abs(c)-.1) if c > 0 else -(abs(c)-.1))
            self.assertEqual(result["predictionMgL"].hex(), expected.hex())
        # This chosen binary64 example distinguishes adopted order from R-sign*.1.
        adopted = d.attenuate_prediction(.01, .12)["predictionMgL"]
        self.assertNotEqual(adopted.hex(), (.12-.1).hex())

    def test_active_gate_and_changed_prediction_are_separate(self):
        result = d.attenuate_prediction(2.0, 2.1)
        self.assertTrue(result["gateActive"])
        self.assertFalse(result["predictionChangedFromPersistence"])
        data = source([row(p=2.0, ridge=2.1, actual=2.0)])
        monthly = d.analyze_month(data, binding(data))
        self.assertEqual(monthly["overall"]["gateActiveCount"], 1)
        self.assertEqual(monthly["overall"]["gateActiveButUnchangedCount"], 1)
        self.assertEqual(monthly["overall"]["changedPredictionCount"], 0)
        self.assertTrue(monthly["checks"]["sameGateActiveOriginsAsOldF"])

    def test_no_future_target_or_two_hour_route_input(self):
        self.assertEqual(list(inspect.signature(d.attenuate_prediction).parameters), ["persistence", "ridge"])
        a, b = source([row(actual=0.0)]), source([row(actual=100.0)])
        left, right = (d.analyze_month(x, binding(x))["rows"][0] for x in (a, b))
        for key in ("gateActive", "predictionChangedFromPersistence", "ridgeCorrectionMgL", "attenuatedCorrectionMgL", "predictionsMgL"):
            self.assertEqual(left[key], right[key])
        self.assertNotEqual(left["absoluteErrorsMgL"], right["absoluteErrorsMgL"])

    def test_invalid_inputs_never_silently_use_p(self):
        for invalid in (None, True, math.nan, math.inf, -math.inf):
            self.assertFalse(d.attenuate_prediction(10.0, invalid)["valid"])
            self.assertIsNone(d.attenuate_prediction(10.0, invalid)["predictionMgL"])
            self.assertFalse(d.attenuate_prediction(invalid, 10.0)["valid"])
        self.assertFalse(d.attenuate_prediction(-1.0, 1.0)["valid"])
        self.assertFalse(d.attenuate_prediction(1e308, -1e308)["valid"])

    def test_negative_r_comparator_does_not_invalidate_nonnegative_q(self):
        safe = source([row(p=.2, ridge=-.05, actual=.1)])
        report = d.analyze_month(safe, binding(safe))
        self.assertTrue(report["candidateValidOnAllRows"])
        self.assertEqual(report["overall"]["invalidRawRidgeCount"], 1)
        self.assertGreaterEqual(report["rows"][0]["predictionsMgL"][d.Q], 0)
        self.assertAlmostEqual(report["overall"]["methods"][d.R]["maeMgL"], .15)
        bad = source([row(p=.2, ridge=-.2, actual=.1)])
        report = d.analyze_month(bad, binding(bad))
        self.assertFalse(report["candidateValidOnAllRows"])
        self.assertFalse(report["developmentMonthPass"])
        self.assertLess(report["rows"][0]["predictionsMgL"][d.Q], 0)

    def test_full_cohort_paired_gains_and_recomposition(self):
        data = source([row(actual=10.1), row("2020-01-01T06:30:00Z", actual=10.0),
                       row("2020-01-01T07:00:00Z", actual=10.2),
                       row("2020-01-01T07:30:00Z", ridge=10.01, actual=10.0)])
        report = d.analyze_month(data, binding(data))
        q = report["overall"]["methods"][d.Q]
        self.assertEqual((report["overall"]["count"], q["count"]), (4, 4))
        self.assertAlmostEqual(q["maeMgL"], (.02+.08+.12+0)/4)
        self.assertEqual((q["wins"], q["ties"], q["losses"]), (2, 1, 1))
        self.assertEqual(report["selectionGroups"]["active"]["count"], 3)
        self.assertEqual(report["attenuationOutcomeGroups"]["attenuationHelpsOldF"]["count"], 2)
        self.assertEqual(report["attenuationOutcomeGroups"]["attenuationWorsensOldF"]["count"], 1)
        self.assertAlmostEqual(report["overall"]["candidateAgainstOldFilter"]["sumGainMgL"], .06)
        self.assertEqual(report["posthocIllustrativeRowIndices"],
                         {"candidateHelpsP": 0, "candidateWorsensP": 1,
                          "attenuationHelpsOldF": 0, "attenuationWorsensOldF": 2})
        self.assertEqual(len(report["allGateActiveContexts"]), 3)
        self.assertNotIn("oxygenHistory", report["rows"][0])
        self.assertEqual(report["allGateActiveContexts"][0]["oxygenHistory"], data["rows"][0]["oxygenHistory"])
        self.assertTrue(report["checks"]["allPartitionsRecompose"])

    def test_invalid_row_is_retained_and_blocks_continuation(self):
        data = source([row(ridge=None), row("2020-01-01T06:30:00Z")])
        report = d.analyze_month(data, binding(data))
        self.assertEqual(len(report["rows"]), 2)
        self.assertEqual(report["overall"]["invalidCandidateCount"], 1)
        self.assertEqual(report["selectionGroups"]["invalid"]["count"], 1)
        self.assertIsNone(report["overall"]["methods"][d.Q]["maeMgL"])
        self.assertFalse(report["developmentMonthPass"])

    def test_empty_group_means_null_and_examples_null(self):
        data = source([row(ridge=10.01, actual=10.0)])
        report = d.analyze_month(data, binding(data))
        empty = report["selectionGroups"]["active"]
        self.assertEqual(empty["count"], 0)
        self.assertIsNone(empty["methods"][d.Q]["maeMgL"])
        self.assertIsNone(empty["candidateAgainstOldFilter"]["meanGainMgL"])
        self.assertEqual(empty["methods"][d.Q]["sumGainMgL"], 0)
        self.assertEqual(empty["methods"][d.Q]["globalGainContributionMgL"], 0)
        self.assertTrue(all(v is None for v in report["posthocIllustrativeRowIndices"].values()))

    def test_source_integrity_and_no_cohort_repairs(self):
        for mutate in (lambda r: r["oxygenHistory"].pop(),
                       lambda r: r["oxygenHistory"][0].update(timeUTC=r["origin"]),
                       lambda r: r["features"].__setitem__(2, -.9),
                       lambda r: r["features"].__setitem__(4, 0),
                       lambda r: r["features"].__setitem__(7, None),
                       lambda r: r["predictionsMgL"].__setitem__(d.P, None),
                       lambda r: r["predictionsMgL"].__setitem__(d.F, 10),
                       lambda r: r.update(target="2020-01-01T08:00:00Z")):
            sample = row()
            mutate(sample)
            data = source([sample])
            with self.assertRaises(ValueError):
                d.analyze_month(data, binding(data))
        data = source([row(), row("2020-01-01T06:30:00Z")])
        for mutate in (lambda x: x["rows"].reverse(), lambda x: x["rows"].__setitem__(1, x["rows"][0]),
                       lambda x: x.update(stationId="OTHER"), lambda x: x["scores"][d.P].update(pairs=1)):
            modified = copy.deepcopy(data)
            mutate(modified)
            with self.assertRaises(ValueError):
                d.analyze_month(modified, binding(modified))
        with self.assertRaises(ValueError):
            d.analyze_month(data, binding(data) | {"pairs": 3})

    def test_occupancy_uses_window_anchor(self):
        data = source([row(), row("2020-01-02T06:00:00Z")])
        report = d.analyze_month(data, binding(data))["activationOccupancy"]
        self.assertEqual(report["activeDayCount"], 2)
        self.assertEqual(report["blocks"]["24"]["activeBlockCount"], 2)
        self.assertEqual(report["blocks"]["48"]["activeBlockCount"], 1)
        self.assertEqual(report["blocks"]["24"]["items"][0]["startUTC"], "2020-01-01T00:00:00Z")


class ReplayTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        (self.root/"scripts").mkdir()
        (self.root/d.DEPENDENCY_FILE).write_bytes(Path(d.integrity.__file__).read_bytes())
        model = {"recipe": {"features": d.FEATURES, "featureWidth": 8, "horizonSeconds": 3600}}
        raw = d.encoded(model)
        (self.root/"model.json").write_bytes(raw)
        self.model_hash = d.sha(raw)
        sample = source([row(), row("2020-01-01T06:30:00Z", ridge=10.01, actual=10.0)])
        self.months = []
        for name in ("invented-a", "invented-b"):
            item = binding(sample, name)
            (self.root/item["file"]).write_bytes(d.encoded(sample))
            self.months.append(item)
        self.spec = {"version": "owasco-attenuation-diagnostic-v1", "status": "ADOPTED_BEFORE_FIRST_ATTENUATION_SCORE",
            "adoptedAtUTC": "2020-01-01T00:00:00Z", "stationId": "USGS-425327076313601",
            "horizonSeconds": 3600, "features": d.FEATURES,
            "model": {"file": "model.json", "rawSha256": self.model_hash}, "months": self.months,
            "dependencies": [{"file": d.DEPENDENCY_FILE, "rawSha256": d.DEPENDENCY_SHA256}],
            "rule": {"thresholdMgL": .1}, "continuation": {"numericalToleranceMgL": 1e-9, "requireBothMonths": True}}
        self.protocol = self.root/"protocol.json"
        self.write_spec()

    def write_spec(self):
        raw = d.encoded(self.spec)
        self.protocol.write_bytes(raw)
        self.protocol_hash = d.sha(raw)

    def args(self):
        return {"protocol_sha256": self.protocol_hash}

    def test_exclusive_output_and_no_write_verification(self):
        output = self.root/"result"
        d.run(self.root, self.protocol, output, **self.args())
        report = output/"diagnostic.json"
        raw = report.read_bytes()
        before = {p: p.stat().st_mtime_ns for p in self.root.rglob("*") if p.is_file()}
        verified = d.verify_report(self.root, self.protocol, report, **self.args())
        self.assertTrue(verified["verified"])
        self.assertFalse(verified["writes"])
        self.assertEqual(report.read_bytes(), raw)
        self.assertEqual(before, {p: p.stat().st_mtime_ns for p in self.root.rglob("*") if p.is_file()})
        with self.assertRaises(ValueError):
            d.run(self.root, self.protocol, output, **self.args())

    def test_report_tamper_and_false_receipts_rejected(self):
        output = self.root/"result"
        d.run(self.root, self.protocol, output, **self.args())
        target = output/"diagnostic.json"
        original = d.loads(target.read_bytes())
        for mutate in (lambda x: x["months"][0]["overall"]["methods"][d.Q].update(maeMgL=0.0),
                       lambda x: x["implementation"].update(rawSha256="0"*64),
                       lambda x: x["dependencies"][0].update(rawSha256="0"*64),
                       lambda x: x["protocol"].update(sha256="0"*64),
                       lambda x: x.update(createdAtUTC="1999-01-01T00:00:00Z"),
                       lambda x: x["months"][0]["rows"].pop(),
                       lambda x: x["developmentContinuation"].update(passed=False)):
            sample = copy.deepcopy(original)
            mutate(sample)
            target.write_bytes(d.encoded(sample))
            with self.assertRaises(ValueError):
                d.verify_report(self.root, self.protocol, target, **self.args())

    def test_input_model_protocol_dependency_pins(self):
        for filename in ("model.json", "invented-a.json", "protocol.json", d.DEPENDENCY_FILE):
            target = self.root/filename
            original = target.read_bytes()
            target.write_bytes(original+b" ")
            with self.assertRaises(ValueError):
                d.replay(self.root, self.protocol, **self.args())
            target.write_bytes(original)

    def test_changed_threshold_feature_order_and_path_escape_rejected(self):
        self.spec["rule"]["thresholdMgL"] = .099
        self.write_spec()
        with self.assertRaises(ValueError):
            d.replay(self.root, self.protocol, **self.args())
        self.spec["rule"]["thresholdMgL"] = .1
        model = d.loads((self.root/"model.json").read_bytes())
        model["recipe"]["features"] = list(reversed(d.FEATURES))
        raw = d.encoded(model)
        (self.root/"model.json").write_bytes(raw)
        self.spec["model"]["rawSha256"] = d.sha(raw)
        self.write_spec()
        with self.assertRaises(ValueError):
            d.replay(self.root, self.protocol, **self.args())
        self.spec["model"]["file"] = "../outside.json"
        self.write_spec()
        with self.assertRaises(ValueError):
            d.replay(self.root, self.protocol, **self.args())

    def test_both_months_required_for_continuation(self):
        # The first invented window improves; the second deliberately worsens.
        second = source([row(actual=10.0)])
        item = binding(second, "invented-b")
        (self.root/item["file"]).write_bytes(d.encoded(second))
        self.spec["months"][1] = item
        self.write_spec()
        report = d.replay(self.root, self.protocol, **self.args())
        self.assertTrue(report["months"][0]["developmentMonthPass"])
        self.assertFalse(report["months"][1]["developmentMonthPass"])
        self.assertFalse(report["developmentContinuation"]["passed"])
        self.assertFalse(report["developmentContinuation"]["septemberAuthorizedOrAcquired"])

    def test_strict_json_and_offline_replay(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'):
            with self.assertRaises(ValueError):
                d.loads(raw)
        code = Path(d.__file__).read_text()
        for forbidden in ("import requests", "import urllib", "import lake_transfer", "subprocess"):
            self.assertNotIn(forbidden, code)
        with mock.patch("socket.socket", side_effect=AssertionError("Network forbidden")):
            report = d.replay(self.root, self.protocol, **self.args())
        self.assertEqual(len(report["months"]), 2)


if __name__ == "__main__":
    unittest.main()
