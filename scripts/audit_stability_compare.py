"""Compare audit receipts across platforms, preserving exact discrete evidence."""
import math


def assert_same_receipt(actual, expected, path="receipt", tolerance=1e-9):
    if isinstance(expected, float):
        assert type(actual) in (int, float) and math.isfinite(actual) and math.isfinite(expected), path
        assert abs(actual - expected) <= tolerance, f"{path}: arithmetic differs beyond {tolerance}"
    elif isinstance(expected, dict):
        assert isinstance(actual, dict) and actual.keys() == expected.keys(), f"{path}: fields differ"
        for key in expected:
            assert_same_receipt(actual[key], expected[key], f"{path}.{key}", tolerance)
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected), f"{path}: list differs"
        for index, (got, wanted) in enumerate(zip(actual, expected)):
            assert_same_receipt(got, wanted, f"{path}[{index}]", tolerance)
    else:
        assert type(actual) is type(expected) and actual == expected, f"{path}: discrete evidence differs"
