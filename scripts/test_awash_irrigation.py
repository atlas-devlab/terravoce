import copy
import tempfile
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch
import awash_irrigation as awash

class AwashTests(unittest.TestCase):
    def test_actual_dekad_length_including_leap_day(self):
        self.assertEqual(awash.dekad("2024-02-D3")["days"], 9)
        self.assertEqual(awash.dekad("2025-02-D3")["days"], 8)
        self.assertEqual(awash.dekad("2024-01-D3")["days"], 11)

    def test_source_scale_and_daily_period_units(self):
        replay = awash.load_phase("history")
        self.assertEqual(len(replay["records"]), 6)
        last = next(r for r in replay["records"] if r["metric"] == "aeti" and r["period"]["code"] == "2024-02-D3")
        self.assertAlmostEqual(last["periodTotalMm"], last["dailyMeanMm"] * 9)
        self.assertEqual(last["validAreaFraction"], 1)
        self.assertGreater(last["nativePixels"], 400)
        precip = next(r for r in replay["records"] if r["metric"] == "precipitation")
        self.assertEqual(precip["nativePixels"], 2)  # Native coarse weather pixels stay coarse.

    def test_missing_native_area_is_not_zero_or_complete(self):
        clip = awash.read_json(awash.DATA / "history/aeti-2024-02-D3.pixels.json")
        clip["values"][2][2] = clip["noDataValue"]
        result = awash.aggregate(clip, awash.protocol()["bboxWgs84"])
        self.assertLess(result["validAreaFraction"], 1)
        self.assertEqual(result["missingPixels"], 1)
        history = awash.load_phase("history")
        for r in history["records"]:
            if r["metric"] == "aeti" and r["period"]["code"] == "2024-02-D3":
                r["complete"] = False
        with patch.object(awash, "load_phase", return_value=history):
            with self.assertRaisesRegex(ValueError, "pending"):
                awash.prediction()

    def test_native_window_and_unit_errors_are_rejected(self):
        original = awash.read_json(awash.DATA / "history/aeti-2024-02-D3.pixels.json")
        for field, value in (("unit", "mm/period"), ("crs", "EPSG:3857")):
            clip = copy.deepcopy(original)
            clip[field] = value
            with self.assertRaises(ValueError): awash.aggregate(clip, awash.protocol()["bboxWgs84"])
        clip = copy.deepcopy(original)
        clip["window"]["col"] += 1
        with self.assertRaisesRegex(ValueError, "cover"): awash.aggregate(clip, awash.protocol()["bboxWgs84"])

    def test_prediction_never_reads_target(self):
        original = awash.load_phase
        def history_only(phase):
            self.assertEqual(phase, "history")
            return original(phase)
        with patch.object(awash, "load_phase", side_effect=history_only):
            forecast = awash.prediction()
        self.assertFalse(forecast["trainedModel"])
        self.assertIsNone(forecast["irrigationWithdrawalM3"])
        self.assertFalse(forecast["operationalEligible"])

    def test_evidence_cannot_be_silently_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.json"
            awash.write_new(path, {"value": 1})
            awash.write_new(path, {"value": 1})
            with self.assertRaisesRegex(ValueError, "Refusing"):
                awash.write_new(path, {"value": 2})

    def test_tampered_source_pixels_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "data"
            shutil.copytree(awash.DATA, copied)
            path = copied / "history/aeti-2024-02-D3.pixels.json"
            changed = awash.read_json(path)
            changed["values"][0][0] += 1
            path.write_text(__import__("json").dumps(changed), encoding="utf-8")
            with patch.object(awash, "DATA", copied):
                with self.assertRaisesRegex(ValueError, "hash mismatch"):
                    awash.load_phase("history")

    def test_sealed_target_result_replays_without_skill_or_funding_claim(self):
        result = awash.evaluation()
        self.assertAlmostEqual(result["absoluteErrorMmPerDay"], abs(result["predictedDailyMeanMm"]-result["actualEstimatedDailyMeanMm"]))
        self.assertEqual(result["scoredRounds"], 1)
        self.assertFalse(result["skillEstablished"])
        self.assertFalse(result["fundingRelease"])
        self.assertIsNone(result["irrigationWithdrawalM3"])

if __name__ == "__main__":
    unittest.main()
