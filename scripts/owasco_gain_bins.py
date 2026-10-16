"""Fixed descriptive decomposition of saved Owasco predictions; offline, no fit.

The CLI accepts only the pinned 1,275-row archive. It creates a new explicit
output directory and never replaces an existing output or the input artifact.
Only saved P/R/F values are used; no model, sensor archive or network is read.
"""
import argparse
import hashlib
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


P = "persistence"
R = "same-frozen-ridge-without-fallback"
F = "small-correction-filter"
METHODS = (P, R, F)
STRATA = ("unchanged", "changed")
TOL = 1e-9  # Recomposition only; never changes bins, equality, or the gate.
PROPOSAL_SHA256 = "1b965fa73b53af73ed18c84ccd78ff62bd11de081eda3d82e4eca6effa7ff2ba"
ADOPTED_PROTOCOL_SHA256 = "ef5882854644c39becba2374f0e365c398be3e52572f1ee1bdfef22e624fed13"
INPUT_REPOSITORY_PATH = "docs/evidence/owasco-lake-transfer/evaluation.json"
PROTOCOL_REPOSITORY_PATH = "docs/datasets/owasco-gain-diagnostic/protocol.json"
BINS = (
    ("B1", "[0,0.025)"),
    ("B2", "[0.025,0.050)"),
    ("B3", "[0.050,0.075)"),
    ("B4", "[0.075,0.100]"),
    ("B5", "(0.100,+infinity)"),
)


@dataclass(frozen=True)
class InputBinding:
    """Different bindings are for invented unit fixtures, never CLI overrides."""

    sha256: str
    origin_sha256: str
    pairs: int


PINNED_INPUT = InputBinding(
    "7bd27ec609a7c4f471385498b61fff7b9d74546de13711559e84fcb16536ff85",
    "c6361869f5df11bb39f8ac394b2c1fd3f4153e54a89067ea767353607764ed97",
    1275,
)


def _finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except (OverflowError, ValueError):
        return False


def _number(value, label):
    if not _finite(value):
        raise ValueError(f"Missing or nonfinite numeric field: {label}")
    return value


def _sum(values):
    try:
        value = math.fsum(values)
    except (OverflowError, ValueError) as exc:
        raise ValueError("Nonfinite or overflowing aggregate") from exc
    return _number(value, "aggregate")


def _close(actual, expected, label):
    if not (_finite(actual) and _finite(expected)) or abs(actual - expected) > TOL:
        raise ValueError(f"Recomposition failed ({label}): {actual} versus {expected}")


def _no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError(f"Non-standard JSON constant: {value}")


def _utc_metadata(value, label):
    try:
        if not isinstance(value, str):
            raise ValueError("Timestamp must be a string")
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.utcoffset() != timedelta(0):
            raise ValueError("UTC timezone required")
        return parsed
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"Invalid UTC metadata: {label}") from exc


def canonical_origins(rows):
    """Preserve multiplicity; the binding detects substitutions, never deduplicate."""
    result = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict) or not isinstance(row.get("origin"), str):
            raise ValueError(f"Missing origin in row {i}")
        try:
            stamp = datetime.fromisoformat(row["origin"].replace("Z", "+00:00"))
            if stamp.utcoffset() is None:
                raise ValueError("Timezone required")
            result.append(stamp.astimezone(timezone.utc).isoformat(
                timespec="microseconds").replace("+00:00", "Z"))
        except (ValueError, OverflowError) as exc:
            raise ValueError(f"Invalid aware origin in row {i}") from exc
    return result


def origin_hash(rows):
    stamps = canonical_origins(rows)
    return hashlib.sha256(("\n".join(sorted(stamps)) + "\n").encode("utf-8")).hexdigest()


def bin_index(score):
    """Binary64 comparison, deliberately no rounding, epsilon or deadband."""
    if not _finite(score) or score < 0:
        raise ValueError("Need a finite nonnegative correction magnitude")
    if score < .025:
        return 0
    if score < .050:
        return 1
    if score < .075:
        return 2
    if score <= .100:
        return 3
    return 4


def _load(raw, binding):
    source_hash = hashlib.sha256(raw).hexdigest()
    if source_hash != binding.sha256:
        raise ValueError("Input SHA-256 does not match the bound archive")
    try:
        data = json.loads(raw, object_pairs_hook=_no_duplicate_keys,
                          parse_constant=_invalid_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid JSON artifact") from exc
    if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
        raise ValueError("Artifact requires a rows array")
    rows = data["rows"]
    if type(binding.pairs) is not int or binding.pairs <= 0 or len(rows) != binding.pairs:
        raise ValueError("Row count differs from the fixed cohort")
    timestamp_hash = origin_hash(rows)
    if timestamp_hash != binding.origin_sha256:
        raise ValueError("Ordered origin SHA-256 does not match the fixed cohort")
    scores = data.get("scores")
    if not isinstance(scores, dict):
        raise ValueError("Missing saved scores")
    references = {}
    for method in METHODS:
        saved = scores.get(method)
        if not isinstance(saved, dict) or type(saved.get("pairs")) is not int:
            raise ValueError(f"Missing saved pair count: {method}")
        if saved["pairs"] != binding.pairs:
            raise ValueError(f"Saved pair count differs from cohort: {method}")
        mae = _number(saved.get("maeMgL"), f"scores.{method}.maeMgL")
        if mae < 0:
            raise ValueError(f"Negative saved MAE: {method}")
        references[method] = mae
    return rows, references, source_hash, timestamp_hash


def _observations(rows):
    result = []
    for i, row in enumerate(rows):
        predictions = row.get("predictionsMgL")
        if not isinstance(predictions, dict):
            raise ValueError(f"Missing saved predictions in row {i}")
        actual = _number(row.get("actual"), f"rows[{i}].actual")
        p, r, f = (_number(predictions.get(m), f"rows[{i}].{m}") for m in METHODS)
        score = _number(abs(r - p), f"rows[{i}].score")
        # This is an integrity comparison with saved F, not a new forecast.
        if f != (p if score <= .100 else r):
            raise ValueError(f"Saved original filter disagrees with frozen gate in row {i}")
        ep = _number(abs(p - actual), f"rows[{i}].errorP")
        er = _number(abs(r - actual), f"rows[{i}].errorR")
        ef = _number(abs(f - actual), f"rows[{i}].errorF")
        gain = _number(ep - er, f"rows[{i}].gain")
        result.append({"bin": bin_index(score), "stratum": (
            "unchanged" if actual == p else "changed"),
            "ep": ep, "er": er, "ef": ef, "gain": gain})
    return result


def _summary(rows, denominator):
    count = len(rows)
    ep, er, gain = (_sum(r[key] for r in rows) for key in ("ep", "er", "gain"))
    _close(gain, ep - er, "cell gain sum")
    return {
        "count": count,
        "localDenominator": count,
        "globalDenominator": denominator,
        "cohortFraction": count / denominator,
        "sumErrorP": ep, "sumErrorR": er, "sumGain": gain,
        "meanErrorP": ep / count if count else None,
        "meanErrorR": er / count if count else None,
        "meanGain": gain / count if count else None,
        "globalErrorContributionP": ep / denominator,
        "globalErrorContributionR": er / denominator,
        "globalGainContribution": gain / denominator,
    }


def analyze_bytes(raw, binding=PINNED_INPUT):
    """Validate the complete binding before calculating any row error or bin."""
    rows, refs, source_hash, timestamp_hash = _load(raw, binding)
    observations = _observations(rows)
    n = binding.pairs
    overall = _summary(observations, n)
    bins = []
    for j, (name, interval) in enumerate(BINS):
        selected = [r for r in observations if r["bin"] == j]
        bins.append({"id": name, "interval": interval, **_summary(selected, n),
                     "observedChange": {s: _summary(
                         [r for r in selected if r["stratum"] == s], n) for s in STRATA}})
    strata = {s: _summary([r for r in observations if r["stratum"] == s], n)
              for s in STRATA}
    if sum(b["count"] for b in bins) != n or sum(s["count"] for s in strata.values()) != n:
        raise ValueError("Partition changed the fixed denominator")
    for b in bins:
        if sum(c["count"] for c in b["observedChange"].values()) != b["count"]:
            raise ValueError("Bin strata do not recompose counts")
        for key in ("sumErrorP", "sumErrorR", "sumGain"):
            _close(_sum(c[key] for c in b["observedChange"].values()), b[key], key)
    for key in ("sumErrorP", "sumErrorR", "sumGain"):
        _close(_sum(b[key] for b in bins), overall[key], f"bin totals {key}")
        _close(_sum(s[key] for s in strata.values()), overall[key], f"stratum totals {key}")
        for s in STRATA:
            _close(_sum(b["observedChange"][s][key] for b in bins),
                   strata[s][key], f"stratum cells {key}")
    for method, key in ((P, "meanErrorP"), (R, "meanErrorR")):
        _close(overall[key], refs[method], f"saved {method} MAE")
    _close(overall["meanGain"], refs[P] - refs[R], "saved unfiltered gain")
    _close(refs[P] - overall["meanGain"], refs[R], "ridge from baseline and gain")
    filter_mae = _sum(r["ef"] for r in observations) / n
    filter_gain = bins[4]["sumGain"] / n
    _close(filter_mae, refs[F], "saved original-filter MAE")
    _close(refs[P] - filter_gain, refs[F], "B5 original-filter bridge")
    _close(refs[P] - filter_mae, filter_gain, "B5 gain")
    return {
        "version": "owasco-gain-bins-v1",
        "scope": "Descriptive decomposition of an already inspected window; not independent validation",
        "sourceProposalSHA256": PROPOSAL_SHA256,
        "input": {"sha256": source_hash, "orderedOriginTimestampListSHA256": timestamp_hash,
                  "pairs": n},
        "definitions": {"score": "abs(saved R-saved P)",
                        "gain": "abs(saved P-actual)-abs(saved R-actual)",
                        "unchanged": "actual == saved P exactly; outcome-dependent, not deployable",
                        "denominators": "Within-cell means use count; all global contributions use N",
                        "emptyCells": "Zero sums/counts/contributions; null within-cell means",
                        "boundary": "No epsilon or rounding; exact score 0.100 is inactive B4"},
        "savedReferenceMAE": refs,
        "overall": overall, "bins": bins, "observedChangeTotals": strata,
        "originalFilter": {"activeBin": "B5", "globalDenominator": n,
                           "sumGain": bins[4]["sumGain"],
                           "globalGainContribution": filter_gain, "maeMgL": filter_mae},
        "checks": {"bindingPassed": True, "recompositionPassed": True,
                   "savedFilterMatchesFrozenGateExactly": True, "toleranceMgL": TOL},
        "limits": ["No thresholds selected, new model fitted or saved forecast recomputed.",
                   "No confidence intervals, causal/ecological conclusions or operational validation.",
                   "A negative coarse-bin sum does not rule out every amplitude filter.",
                   "Changed/unchanged strata use future outcomes; they are descriptive only."],
    }


def read_adopted_protocol(protocol_file, binding=PINNED_INPUT,
                          expected_sha256=ADOPTED_PROTOCOL_SHA256):
    """Read the pinned adoption before accessing saved prediction rows."""
    path = Path(protocol_file).resolve()
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise ValueError("Adopted protocol SHA-256 does not match")
    try:
        protocol = json.loads(raw, object_pairs_hook=_no_duplicate_keys,
                              parse_constant=_invalid_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid adopted protocol JSON") from exc
    if (not isinstance(protocol, dict)
            or protocol.get("status") != "ADOPTED_BEFORE_FIRST_BIN_CALCULATION"
            or protocol.get("sourceProposalSHA256") != PROPOSAL_SHA256):
        raise ValueError("Need the adopted fixed-bin protocol")
    _utc_metadata(protocol.get("adoptedAtUTC"), "protocol.adoptedAtUTC")
    receipt = protocol.get("inputBinding")
    if (not isinstance(receipt, dict)
            or receipt.get("rawFileSHA256") != binding.sha256
            or receipt.get("orderedOriginTimestampListSHA256") != binding.origin_sha256):
        raise ValueError("Adopted protocol and input binding disagree")
    refs = receipt.get("existingSavedReferences_notNewCalculations")
    if (not isinstance(refs, dict)
            or any(not isinstance(refs.get(m), dict)
                   or type(refs[m].get("pairs")) is not int
                   or refs[m]["pairs"] != binding.pairs for m in ("P", "R", "F_original"))):
        raise ValueError("Adopted protocol and cohort denominator disagree")
    return {"file": PROTOCOL_REPOSITORY_PATH, "sha256": digest, "status": protocol["status"],
            "adoptedAtUTC": protocol["adoptedAtUTC"]}


def _replay(input_file, protocol_file, binding, protocol_sha256):
    """Produce all deterministic report fields; no output directory or clock read."""
    source = Path(input_file).resolve()
    protocol = read_adopted_protocol(protocol_file, binding, protocol_sha256)
    report = analyze_bytes(source.read_bytes(), binding)
    report["protocol"] = protocol
    report["protocolSHA256"] = protocol["sha256"]
    report["input"]["file"] = INPUT_REPOSITORY_PATH
    report["implementationSHA256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return report


def _check_created_metadata(value, protocol):
    created = _utc_metadata(value, "createdAtUTC")
    adopted = _utc_metadata(protocol["adoptedAtUTC"], "protocol.adoptedAtUTC")
    if created < adopted:
        raise ValueError("Report creation metadata predates protocol adoption")
    # Format and adoption chronology are checkable. The claimed creation instant
    # cannot itself be authenticated by replay, and is not compared with now.


def _compare_json(stored, expected, path="report"):
    """Check every deterministic key, type and value, including list order."""
    if type(stored) is not type(expected):
        raise ValueError(f"Report mismatch at {path}: different JSON type")
    if isinstance(expected, dict):
        if stored.keys() != expected.keys():
            raise ValueError(f"Report mismatch at {path}: different keys")
        for key in expected:
            _compare_json(stored[key], expected[key], f"{path}.{key}")
    elif isinstance(expected, list):
        if len(stored) != len(expected):
            raise ValueError(f"Report mismatch at {path}: different list length")
        for i, (left, right) in enumerate(zip(stored, expected)):
            _compare_json(left, right, f"{path}[{i}]")
    elif (stored.hex() != expected.hex() if isinstance(expected, float) else stored != expected):
        raise ValueError(f"Report mismatch at {path}: different value")


def verify_report(input_file, protocol_file, report_file, binding=PINNED_INPUT,
                  protocol_sha256=ADOPTED_PROTOCOL_SHA256):
    """Offline replay of saved-value errors only. This function writes no files."""
    path = Path(report_file).resolve()
    raw = path.read_bytes()
    try:
        stored = json.loads(raw, object_pairs_hook=_no_duplicate_keys,
                            parse_constant=_invalid_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid saved report JSON") from exc
    if not isinstance(stored, dict) or "createdAtUTC" not in stored:
        raise ValueError("Saved report requires createdAtUTC metadata")
    expected = _replay(input_file, protocol_file, binding, protocol_sha256)
    _check_created_metadata(stored["createdAtUTC"], expected["protocol"])
    deterministic = {k: v for k, v in stored.items() if k != "createdAtUTC"}
    _compare_json(deterministic, expected)
    return {"file": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
            "verified": True, "writes": False, "createdAtUTC": stored["createdAtUTC"]}


def run(input_file, output_dir, protocol_file, binding=PINNED_INPUT,
        protocol_sha256=ADOPTED_PROTOCOL_SHA256):
    """Optional bindings are invented-fixture seams, not exposed by the CLI."""
    destination = Path(output_dir).resolve()
    if destination.exists():
        raise ValueError("Output directory must not already exist; nothing will be overwritten")
    report = _replay(input_file, protocol_file, binding, protocol_sha256)
    report["createdAtUTC"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    _check_created_metadata(report["createdAtUTC"], report["protocol"])
    encoded = (json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    destination.mkdir(parents=True, exist_ok=False)
    target = destination / "diagnostic.json"
    with target.open("xb") as stream:
        stream.write(encoded)
    return {"file": str(target), "sha256": hashlib.sha256(encoded).hexdigest()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Pinned saved evaluation.json")
    parser.add_argument("--protocol", required=True, type=Path, help="Pinned adopted protocol.json")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output-dir", type=Path, help="New directory, never reused")
    mode.add_argument("--verify-report", type=Path, help="Replay and compare a saved report; no writes")
    args = parser.parse_args(argv)
    try:
        result = (verify_report(args.input, args.protocol, args.verify_report)
                  if args.verify_report is not None
                  else run(args.input, args.output_dir, args.protocol))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Stopped: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
