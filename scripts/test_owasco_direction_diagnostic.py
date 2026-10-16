"""Invented fixtures only; never open environmental observations or predictions."""
import copy
import inspect
import json
import math
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest import mock

import owasco_direction_diagnostic as d


def row(origin="2020-01-01T06:00:00Z", p=10.0, past=11.0, ridge=9.5, actual=9.6):
    stamp = d.instant(origin)
    history = [{"timeUTC": (stamp-timedelta(minutes=30*(11-j))).isoformat().replace("+00:00", "Z"),
                "value": p if j == 11 else past} for j in range(12)]
    values = [v["value"] for v in history]
    clock = (stamp.hour*3600+stamp.minute*60+stamp.second)/86400*2*math.pi
    old = None if not d.finite(ridge) else p if abs(ridge-p) <= .1 else ridge
    return {"origin": origin, "target": (stamp+timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
            "actual": actual, "oxygenHistory": history,
            "features": [p, p-values[-2], p-values[-5], p-values[0], math.sin(clock), math.cos(clock), 17.0, -.3],
            "predictionsMgL": {d.P: p, d.R: ridge, d.F: old}}


def source(rows):
    return {"stationId": "USGS-425327076313601", "horizonSeconds": 3600,
            "window": {"start": "2020-01-01T00:00:00Z", "end": "2020-01-03T00:00:00Z"},
            "rows": rows, "scores": {m: None if any(not d.finite(r["predictionsMgL"][m]) for r in rows) else
                {"pairs": len(rows), "maeMgL": math.fsum(abs(r["predictionsMgL"][m]-r["actual"]) for r in rows)/len(rows)}
                for m in (d.P, d.R, d.F)}}


def binding(data, name="invented"):
    return {"id": name, "file": name+".json", "rawSha256": d.sha(d.encoded(data)),
            "pairs": len(data["rows"]), "window": data["window"]}


class DirectionTest(unittest.TestCase):
    def test_selector_is_past_only_and_exact_sign(self):
        self.assertEqual(list(inspect.signature(d.select_prediction).parameters), ["persistence", "ridge", "two_hour_change"])
        cases = [(10, 9, -1, d.R), (10, 11, 1, d.R), (10, 9, 1, d.P),
                 (10, 11, -1, d.P), (10, 9, 0, d.P), (10, 10, -1, d.P),
                 (10, 10, 1, d.P), (10, 11, -0.0, d.P)]
        for p, r, change, expected in cases:
            with self.subTest(case=(p, r, change)):
                self.assertEqual(d.select_prediction(p, r, change)["selectedMethod"], expected)
        tiny = math.nextafter(10.0, math.inf)
        self.assertEqual(d.select_prediction(10, tiny, math.ulp(0.0))["predictionMgL"], tiny)

    def test_new_gate_replaces_amplitude_gate(self):
        selected = d.select_prediction(10, 10.001, 1)
        self.assertEqual(selected["selectedMethod"], d.R)
        self.assertEqual(selected["predictionMgL"], 10.001)
        self.assertEqual(d.select_prediction(10, 12, -1)["selectedMethod"], d.P)

    def test_no_clipping_or_silent_invalid_r_rescue(self):
        self.assertEqual(d.select_prediction(1, -2, -1)["predictionMgL"], -2)
        self.assertFalse(d.select_prediction(1, -2, -1)["valid"])
        safe = d.select_prediction(1, -2, 1)
        self.assertTrue(safe["valid"])
        self.assertEqual(safe["predictionMgL"], 1)
        for invalid in (None, float("nan"), float("inf"), float("-inf"), True):
            with self.subTest(value=invalid):
                result = d.select_prediction(1, invalid, 0)
                self.assertEqual(result["selectedMethod"], "invalid")
                self.assertIsNone(result["predictionMgL"])

    def test_fixed_bin_exact_boundaries(self):
        for value, expected in ((0, "B1"), (.025, "B2"), (.05, "B3"), (.075, "B4"), (.1, "B4"),
                                (math.nextafter(.1, math.inf), "B5"), (None, "invalid")):
            self.assertEqual(d.correction_bin(value), expected)

    def test_full_cohort_mae_partitions_and_empty_nulls(self):
        data = source([row(), row("2020-01-01T06:30:00Z", past=9, ridge=9.5, actual=10.0),
                       row("2020-01-01T07:00:00Z", past=10, ridge=9.5, actual=9.5)])
        result = d.analyze_month(data, binding(data))
        self.assertEqual(result["overall"]["count"], 3)
        self.assertEqual(result["overall"]["chooseRCount"], 1)
        self.assertEqual(result["overall"]["choosePCount"], 2)
        candidate = result["overall"]["methods"][d.S]
        self.assertAlmostEqual(candidate["maeMgL"], (.1+0+.5)/3)
        self.assertAlmostEqual(candidate["meanGainMgL"], .3/3)
        self.assertEqual((candidate["wins"], candidate["ties"], candidate["losses"]), (1, 2, 0))
        empty = result["originSignGroups"]["zero_zero"]["methods"][d.S]
        self.assertIsNone(empty["maeMgL"])
        self.assertIsNone(empty["meanGainMgL"])
        self.assertEqual(empty["sumGainMgL"], 0)
        self.assertEqual(empty["globalGainContributionMgL"], 0)
        self.assertEqual(result["posthocIllustrativeRowIndices"]["selectedRImproves"], 0)
        self.assertEqual(result["posthocIllustrativeRowIndices"]["retainedPAvoidsRidgeLoss"], 1)
        self.assertEqual(result["posthocIllustrativeRowIndices"]["retainedPMissesRidgeGain"], 2)

    def test_invalid_rows_stay_and_block_success(self):
        data = source([row(ridge=None), row("2020-01-01T06:30:00Z")])
        result = d.analyze_month(data, binding(data))
        self.assertEqual(len(result["rows"]), 2)
        self.assertEqual(result["overall"]["count"], 2)
        self.assertEqual(result["overall"]["invalidCandidateCount"], 1)
        self.assertFalse(result["candidateValidOnAllRows"])
        self.assertFalse(result["developmentMonthPass"])
        self.assertIsNone(result["overall"]["methods"][d.S]["maeMgL"])
        self.assertEqual(result["oldFilterRoutingComparison"]["invalid"]["count"], 1)

    def test_negative_unselected_r_is_comparator_flag_only(self):
        data = source([row(p=1, past=0, ridge=-1, actual=1)])
        result = d.analyze_month(data, binding(data))
        self.assertTrue(result["candidateValidOnAllRows"])
        self.assertEqual(result["overall"]["invalidRawRidgeCount"], 1)
        self.assertEqual(result["overall"]["methods"][d.R]["maeMgL"], 2)
        self.assertEqual(result["overall"]["methods"][d.S]["maeMgL"], 0)
        data2 = source([row(p=1, past=2, ridge=-1, actual=1)])
        self.assertFalse(d.analyze_month(data2, binding(data2))["candidateValidOnAllRows"])

    def test_exact_history_and_feature_integrity(self):
        for mutate in (lambda r: r["oxygenHistory"].pop(),
                       lambda r: r["oxygenHistory"][0].update(timeUTC=r["origin"]),
                       lambda r: r["features"].__setitem__(2, -.9),
                       lambda r: r["features"].__setitem__(4, 0),
                       lambda r: r["features"].__setitem__(7, None),
                       lambda r: r["predictionsMgL"].__setitem__(d.P, 9),
                       lambda r: r["predictionsMgL"].__setitem__(d.F, 10),
                       lambda r: r.update(target="2020-01-01T08:00:00Z")):
            r = row()
            mutate(r)
            data = source([r])
            with self.assertRaises(ValueError):
                d.analyze_month(data, binding(data))

    def test_duplicate_reordered_or_wrong_source_cohort_rejected(self):
        original = source([row(), row("2020-01-01T06:30:00Z")])
        for change in (lambda x: x["rows"].reverse(),
                       lambda x: x["rows"].__setitem__(1, copy.deepcopy(x["rows"][0])),
                       lambda x: x.update(stationId="OTHER"),
                       lambda x: x["scores"][d.P].update(pairs=1)):
            data = copy.deepcopy(original)
            change(data)
            with self.assertRaises(ValueError):
                d.analyze_month(data, binding(data))
        with self.assertRaises(ValueError):
            d.analyze_month(original, binding(original) | {"pairs": 3})

    def test_target_change_cannot_change_routes(self):
        a, b = source([row(actual=0)]), source([row(actual=100)])
        left, right = (d.analyze_month(x, binding(x))["rows"][0] for x in (a, b))
        self.assertEqual(left["selectedMethod"], right["selectedMethod"])
        self.assertEqual(left["predictionsMgL"][d.S], right["predictionsMgL"][d.S])
        self.assertNotEqual(left["absoluteErrorsMgL"], right["absoluteErrorsMgL"])

    def test_occupancy_anchor_not_first_accepted_origin(self):
        data = source([row(), row("2020-01-02T06:00:00Z")])
        result = d.analyze_month(data, binding(data))["activationOccupancy"]
        self.assertEqual(result["activeDayCount"], 2)
        self.assertEqual(result["blocks"]["24"]["activeBlockCount"], 2)
        self.assertEqual(result["blocks"]["48"]["activeBlockCount"], 1)
        self.assertEqual(result["blocks"]["24"]["items"][0]["startUTC"], "2020-01-01T00:00:00Z")


class ReplayTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        model = {"recipe": {"features": d.FEATURES, "featureWidth": 8, "horizonSeconds": 3600}}
        raw = d.encoded(model)
        (self.root/"model.json").write_bytes(raw)
        self.model_hash = d.sha(raw)
        sample = source([row(), row("2020-01-01T06:30:00Z", past=9, ridge=9.5, actual=10)])
        self.months = []
        for name in ("invented-a", "invented-b"):
            b = binding(sample, name)
            (self.root/b["file"]).write_bytes(d.encoded(sample))
            self.months.append(b)
        self.spec = {"version": "owasco-direction-diagnostic-v1", "status": "ADOPTED_BEFORE_FIRST_SELECTOR_SCORE",
            "proposalSHA256": "invented-proposal", "adoptedAtUTC": "2020-01-01T00:00:00Z",
            "stationId": "USGS-425327076313601", "horizonSeconds": 3600, "features": d.FEATURES,
            "model": {"file": "model.json", "rawSha256": self.model_hash}, "months": self.months,
            "continuation": {"numericalToleranceMgL": 1e-9, "requireBothMonths": True}}
        self.protocol = self.root/"protocol.json"
        self.write_spec()

    def write_spec(self):
        raw = d.encoded(self.spec)
        self.protocol.write_bytes(raw)
        self.protocol_hash = d.sha(raw)

    def args(self):
        return {"protocol_sha256": self.protocol_hash, "proposal_sha256": "invented-proposal"}

    def test_run_and_verified_replay_write_nothing(self):
        output = self.root/"result"
        d.run(self.root, self.protocol, output, **self.args())
        report = output/"diagnostic.json"
        original = report.read_bytes()
        times = {p: p.stat().st_mtime_ns for p in self.root.rglob("*") if p.is_file()}
        result = d.verify_report(self.root, self.protocol, report, **self.args())
        self.assertTrue(result["verified"])
        self.assertFalse(result["writes"])
        self.assertEqual(report.read_bytes(), original)
        self.assertEqual(times, {p: p.stat().st_mtime_ns for p in self.root.rglob("*") if p.is_file()})
        with self.assertRaises(ValueError):
            d.run(self.root, self.protocol, output, **self.args())

    def test_report_tampering_and_false_receipt_rejected(self):
        output = self.root/"result"
        d.run(self.root, self.protocol, output, **self.args())
        file = output/"diagnostic.json"
        original = d.loads(file.read_bytes())
        changes = [lambda r: r["months"][0]["overall"]["methods"][d.S].update(maeMgL=0.0),
                   lambda r: r["implementation"].update(rawSha256="0"*64),
                   lambda r: r["protocol"].update(sha256="0"*64),
                   lambda r: r.update(createdAtUTC="1999-01-01T00:00:00Z"),
                   lambda r: r["months"][0]["rows"].pop(),
                   lambda r: r["developmentContinuation"].update(passed=False)]
        for mutate in changes:
            modified = copy.deepcopy(original)
            mutate(modified)
            file.write_bytes(d.encoded(modified))
            with self.assertRaises(ValueError):
                d.verify_report(self.root, self.protocol, file, **self.args())

    def test_input_model_protocol_binding_rejects_alteration(self):
        for filename in ("model.json", "invented-a.json", "protocol.json"):
            path = self.root/filename
            original = path.read_bytes()
            path.write_bytes(original+b" ")
            with self.assertRaises(ValueError):
                d.replay(self.root, self.protocol, **self.args())
            path.write_bytes(original)

    def test_model_feature_order_and_false_source_manifest(self):
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

    def test_strict_json_and_no_network_or_forecast_dependencies(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'):
            with self.assertRaises(ValueError):
                d.loads(raw)
        source_code = Path(d.__file__).read_text()
        self.assertNotIn("import lake_transfer", source_code)
        self.assertNotIn("import requests", source_code)
        self.assertNotIn("import urllib", source_code)
        # Pure replay does not rely on imports or subprocess calls to rerun R.
        with mock.patch("socket.socket", side_effect=AssertionError("Network forbidden")):
            result = d.replay(self.root, self.protocol, **self.args())
        self.assertEqual(len(result["months"]), 2)


if __name__ == "__main__":
    unittest.main()
