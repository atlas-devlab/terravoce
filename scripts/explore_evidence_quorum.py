"""Finite design exploration, not a deployed registry or a BFT proof.

All 24 arrival orders of four distinct signers are examined for each count of
compromised identities. Everyone eventually submits one vote for the same
content root. Honest signers agree on one complete metadata envelope; malicious
signers agree on a different envelope. Network loss, concurrency, role changes,
physical truth and cryptographic encoding are outside this abstract model.
"""

import itertools
import json

QUORUM = 3
SIGNERS = tuple(range(4))
HONEST = "honest-envelope"
FALSE = "attacker-envelope"


def first_writer(votes):
    """Model only the existing first-envelope lock and duplicate restriction."""
    locked = None
    counted = set()
    for signer, envelope in votes:
        if signer in counted:
            continue
        if locked is None:
            locked = envelope
        if envelope != locked:
            continue
        counted.add(signer)
        if len(counted) >= QUORUM:
            return locked
    return None


def candidate_quorum(votes):
    """Proposed rule: one vote per identity/root, separate complete envelopes."""
    seen = set()
    counts = {}
    for signer, envelope in votes:
        if signer in seen:
            continue
        seen.add(signer)
        counts[envelope] = counts.get(envelope, 0) + 1
        if counts[envelope] >= QUORUM:
            return envelope
    return None


def explore():
    rows = []
    for compromised in range(5):
        counts = {
            "firstWriter": {HONEST: 0, FALSE: 0, "unaccepted": 0},
            "candidateQuorum": {HONEST: 0, FALSE: 0, "unaccepted": 0},
        }
        for order in itertools.permutations(SIGNERS):
            votes = [(s, FALSE if s < compromised else HONEST) for s in order]
            for name, rule in (("firstWriter", first_writer), ("candidateQuorum", candidate_quorum)):
                counts[name][rule(votes) or "unaccepted"] += 1
        assert all(sum(outcomes.values()) == 24 for outcomes in counts.values())
        rows.append({"compromised": compromised, "honest": 4 - compromised, "arrivalOrders": 24, **counts})

    # The attacker's first position accounts for six distinct permutations.
    # These are counts of orders, not probabilities of real adversarial behavior.
    assert rows[1]["firstWriter"] == {HONEST: 18, FALSE: 0, "unaccepted": 6}
    assert rows[1]["candidateQuorum"] == {HONEST: 24, FALSE: 0, "unaccepted": 0}
    assert rows[2]["candidateQuorum"] == {HONEST: 0, FALSE: 0, "unaccepted": 24}
    assert rows[3]["candidateQuorum"] == {HONEST: 0, FALSE: 24, "unaccepted": 0}
    assert candidate_quorum([(0, FALSE), (0, FALSE), (0, FALSE)]) is None
    assert candidate_quorum([(0, FALSE), (1, HONEST), (2, HONEST), (3, HONEST)]) == HONEST
    return {
        "version": "evidence-quorum-design-model-v1",
        "scope": "abstract finite arrival-order model; proposed rule is not implemented in Solidity",
        "identities": 4,
        "quorum": QUORUM,
        "examinedArrivalOrders": 120,
        "rows": rows,
        "duplicateIdentityCannotReachQuorum": True,
        "networkedConsensusTest": False,
        "physicalTruthVerified": False,
        "operationalEligible": False,
        "limits": [
            "A state may deliberately choose the first position; order counts are not attack probabilities",
            "One-node outage and one malicious node simultaneously leave only two honest signers",
            "A captured three-identity quorum can approve a false envelope under either design",
            "An honest quorum can reproduce false initial publisher data",
            "Production requires explicit envelope encoding, domain separation, interfaces and correction lifecycle",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(explore(), indent=2))
