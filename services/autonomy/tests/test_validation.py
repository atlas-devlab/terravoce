import copy
import importlib.util
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("validation", ROOT / "packages/terravoce/skills/oracle_abci/validation.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.fixture
def vector():
    # Public manifest whose digest was produced by TerraAutonomyBridge.actionDigest
    # on Hardhat; checks Python/Solidity ABI and Ethereum hashing interoperability.
    job = json.loads((Path(__file__).parent / "solidity-job-vector.json").read_text())
    result = {"assessment": copy.deepcopy(job["expectedAssessment"]),
              "actionDraft": copy.deepcopy(job["expectedDraft"]), "decision": {"allowed": True}}
    return job, result


def test_matches_solidity_digest(vector):
    job, result = vector
    assert module.action_digest(job, result) == job["digest"]


@pytest.mark.parametrize("field,value", [("chainId", 1), ("validUntil", 123),
                                         ("bridge", "0x0000000000000000000000000000000000000001")])
def test_rejects_changed_domain(vector, field, value):
    job, result = vector
    job[field] = value
    with pytest.raises(ValueError, match="Manifest digest"):
        module.action_digest(job, result)


def test_denied_policy_never_gets_digest(vector):
    job, result = vector
    result["decision"]["allowed"] = False
    with pytest.raises(ValueError, match="TerraLex denied"):
        module.action_digest(job, result)


def test_oracle_disagreement_is_rejected(vector):
    job, result = vector
    result["assessment"]["risk"] = 0
    with pytest.raises(ValueError, match="differs"):
        module.action_digest(job, result)


def test_amount_conversion_and_irreversibility(vector):
    job, result = vector
    job["request"]["amount"] = "1"
    with pytest.raises(ValueError, match="asset amount"):
        module.action_digest(job, result)
    job["request"]["amount"] = "40000000"
    job["request"]["riskTier"] = 1
    with pytest.raises(ValueError, match="autonomy scope"):
        module.action_digest(job, result)
