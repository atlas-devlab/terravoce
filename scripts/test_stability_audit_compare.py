"""Portability must tolerate floating arithmetic, never changes to discrete evidence."""
import copy
import math
import unittest

from audit_stability_compare import assert_same_receipt


class AuditReceiptTests(unittest.TestCase):
    def receipt(self):
        return {"verified": True, "hash": "0xoriginal", "pairs": 5213,
                "windows": [{"maeMgL": .08902329404576162}], "maximumArithmeticDifference": 0.0}

    def test_cross_platform_roundoff_within_predeclared_tolerance_is_accepted(self):
        expected = self.receipt()
        linux = copy.deepcopy(expected)
        linux["maximumArithmeticDifference"] = 1.7763568394002505e-15
        linux["windows"][0]["maeMgL"] += 1.1102230246251565e-16
        assert_same_receipt(linux, expected)
        self.assertEqual(expected, self.receipt())

    def test_wrong_metrics_hash_counts_types_or_fields_are_rejected(self):
        original = self.receipt()
        variants = [original | {"hash": "0xaltered"}, original | {"pairs": 5214},
                    original | {"pairs": 5213.0}, original | {"verified": 1},
                    original | {"windows": [{"maeMgL": .08902329404576162 + 1e-7}]},
                    original | {"maximumArithmeticDifference": math.nan},
                    original | {"maximumArithmeticDifference": math.inf},
                    original | {"unexpected": None}, original | {"windows": []}]
        for changed in variants:
            with self.subTest(changed=changed), self.assertRaises(AssertionError):
                assert_same_receipt(changed, original)


if __name__ == "__main__":
    unittest.main()
