"""Counterexamples for post-hoc accounting, data integrity and convex-loss reasoning."""
import copy
import unittest
from datetime import datetime, timedelta, timezone

import diagnose_stability_errors as d


def row(current, actual, correction, minute=0, flat=False):
    origin = datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=minute)
    stamp = lambda value: value.isoformat().replace("+00:00", "Z")
    history = [{"timeUTC": stamp(origin - timedelta(minutes=30 * j)),
                "value": current if flat or j == 0 else current - .1} for j in range(11, -1, -1)]
    return {"origin": stamp(origin), "target": stamp(origin + timedelta(hours=1)), "actual": actual,
            "predictionsMgL": {d.P: current, d.R: current + correction,
                               d.C: current if flat else current + correction},
            "features": [0.] * 8, "oxygenHistory": history, "historyFlat": flat}


def windows():
    return [{"window": {"season": season}, "rows": [row(10, 10, .2, minute=i * 24 * 60)]}
            for i, season in enumerate(("winter", "spring", "summer", "autumn"))]


class ErrorMechanismsTests(unittest.TestCase):
    def test_equal_season_contribution_does_not_use_pooled_denominator(self):
        cohort = windows()
        cohort[0]["rows"] = [row(10, 11, .5, minute=i * 30) for i in range(3)]
        groups = d.partition(cohort, d.OUTCOMES, d.outcome)
        by_name = {item["group"]: item for item in groups}
        # One season contributes +.5/4, the other three each contribute -.2/4.
        self.assertAlmostEqual(by_name["rise"]["macroMAEGainContributionMgL"], .125)
        self.assertAlmostEqual(by_name["unchanged"]["macroMAEGainContributionMgL"], -.15)
        self.assertAlmostEqual(sum(g["macroMAEGainContributionMgL"] for g in groups), -.025)
        # The pooled gain would be +.15 and even have the wrong sign for macro gain.
        self.assertAlmostEqual(sum(d.gain(r, d.C) for w in cohort for r in w["rows"]) / 6, .15)
        self.assertEqual(by_name["fall"]["pairs"], 0)
        self.assertIsNone(by_name["fall"]["pooledScores"][d.C])

    def test_overshooting_can_help_tie_or_harm(self):
        self.assertEqual(d.behavior(row(10, 11, 1.5), d.C), "overshoot-helps")
        self.assertEqual(d.behavior(row(10, 11, 2), d.C), "overshoot-tie")
        self.assertEqual(d.behavior(row(10, 11, 2.5), d.C), "overshoot-harms")
        self.assertEqual(d.behavior(row(10, 9, -1.5), d.C), "overshoot-helps")
        self.assertEqual(d.behavior(row(10, 11, -.1), d.C), "wrong-direction")

    def test_fallback_preserves_flat_history_but_can_miss_a_change(self):
        stable = row(10, 10, .1, flat=True)
        changing = row(10, 11, .1, flat=True)
        self.assertEqual(d.behavior(stable, d.C), "no-correction-unchanged")
        self.assertEqual(d.behavior(changing, d.C), "no-correction-changed")
        self.assertEqual(d.gain(changing, d.C), 0)
        self.assertGreater(d.gain(changing, d.R), 0)

    def test_future_label_does_not_define_a_known_past_group(self):
        before = row(10, 10, .03)
        after = copy.deepcopy(before)
        after["actual"] = 8
        self.assertNotEqual(d.outcome(before), d.outcome(after))
        self.assertEqual(before["features"], after["features"])
        self.assertEqual(before["historyFlat"], after["historyFlat"])
        self.assertEqual(before["predictionsMgL"], after["predictionsMgL"])

    def test_magnitude_boundary_float_noise_is_not_a_new_bucket(self):
        self.assertEqual(d.magnitude(row(9.3, 9.6, 0)), "(0.1,0.3]")
        self.assertEqual(d.magnitude(row(9.6, 9.7, 0)), "(0,0.1]")
        self.assertEqual(d.magnitude(row(10, 10.4, 0)), ">0.3")

    def test_convex_right_derivative_accounts_for_zero_residual_cusp(self):
        cohort = [row(10, 10, -.4), row(10, 11, .2)]
        # |-.4*lambda| + |1-.2*lambda| has mean right derivative +.1 at zero.
        self.assertAlmostEqual(d.attenuation_slope(cohort, d.C), .1)
        baseline = sum(abs(r["actual"] - r["predictionsMgL"][d.P]) for r in cohort) / 2
        for scale in (.1, 1., 10.):
            scaled_loss = sum(abs(r["actual"] - r["predictionsMgL"][d.P] - scale *
                (r["predictionsMgL"][d.C] - r["predictionsMgL"][d.P])) for r in cohort) / 2
            self.assertGreaterEqual(scaled_loss + 1e-12, baseline + .1 * scale)

    def test_malformed_history_and_duplicate_origins_are_rejected(self):
        good = windows()
        d.validate_rows(good)
        bad = copy.deepcopy(good)
        bad[0]["rows"][0]["oxygenHistory"][0]["timeUTC"] = bad[0]["rows"][0]["origin"]
        with self.assertRaisesRegex(ValueError, "history"):
            d.validate_rows(bad)
        bad = copy.deepcopy(good)
        bad[1]["rows"] = copy.deepcopy(bad[0]["rows"])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            d.validate_rows(bad)
        bad = copy.deepcopy(good)
        bad[0]["rows"][0]["historyFlat"] = True
        with self.assertRaisesRegex(ValueError, "flat-history"):
            d.validate_rows(bad)

    def test_partition_must_cover_all_observations(self):
        with self.assertRaisesRegex(ValueError, "Partition"):
            d.partition(windows(), ["rise"], d.outcome)


if __name__ == "__main__":
    unittest.main()
