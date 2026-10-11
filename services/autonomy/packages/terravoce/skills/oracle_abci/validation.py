"""Validate the independent Oracle result and bind it to a governed job manifest."""
from decimal import Decimal
from eth_abi import encode
from eth_utils import keccak


def action_digest(job, result):
    draft = result.get("actionDraft")
    assessment = result.get("assessment", {})
    if not result.get("decision", {}).get("allowed") or not draft:
        raise ValueError("TerraLex denied the action")
    if draft != job["expectedDraft"] or assessment != job["expectedAssessment"]:
        raise ValueError("Oracle result differs from the frozen, governed job")
    if draft["reversible"] is not True:
        raise ValueError("Irreversible action")
    amount = Decimal(str(draft["requestedAmount"])) * (10 ** job["assetDecimals"])
    if amount != amount.to_integral_value() or int(amount) != int(job["request"]["amount"]):
        raise ValueError("Invalid asset amount")
    r = job["request"]
    if r["riskTier"] != 0 or r["requestAutonomy"] is not True:
        raise ValueError("Invalid autonomy scope")
    if r["regionId"].lower() != "0x" + keccak(text=draft["regionId"]).hex():
        raise ValueError("Region mismatch")
    if r["actionHash"].lower() != "0x" + keccak(text=draft["action"]).hex():
        raise ValueError("Action mismatch")
    if r["evidenceHash"] != draft["evidenceHash"] or r["policyHash"] != draft["policyHash"]:
        raise ValueError("Evidence or policy mismatch")
    b32 = lambda value: bytes.fromhex(value.removeprefix("0x"))
    encoded = encode(
        ["bytes32", "uint256", "address", "address", "bytes32", "uint64",
         "bytes32", "bytes32", "bytes32", "bytes32", "address", "uint96", "uint8", "bool", "bytes32"],
        [keccak(text="TerraVoce/OpenAutonomy/v1"), job["chainId"], job["bridge"], job["governor"],
         b32(job["jobId"]), job["validUntil"], b32(r["regionId"]), b32(r["evidenceHash"]),
         b32(r["policyHash"]), b32(r["actionHash"]), r["recipient"], int(r["amount"]),
         r["riskTier"], r["requestAutonomy"], keccak(text=r["metadataURI"])],
    )
    digest = "0x" + keccak(encoded).hex()
    if digest != job["digest"]:
        raise ValueError("Manifest digest mismatch")
    return digest
