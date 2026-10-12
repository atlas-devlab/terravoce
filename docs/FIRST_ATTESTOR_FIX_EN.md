# Fixing censorship by the first evidence attestor

[Versione italiana](FIRST_ATTESTOR_FIX.md).

TerraVoce's evidence registry now allows three agreeing attestors to publish
their evidence even when a fourth authorized identity submits different
metadata first. This is a registry correction tested on a local EVM. It does
not establish general resistance to a state-level adversary.

## 1. We reproduced the original problem first

At revision `9b6ced1add86e34aa08480d2f1c8d135ba7deb5b`, the first vote fixed the
region, metadata hash, observation time, evidence kind and archive URI for an
`evidenceHash`. Any later vote with a different field reverted with
`EvidenceMismatch`, even before quorum. One authorized key could therefore
block correct publication without controlling the majority.

The first regression test was run against the original contract and failed
with that error. The ordinary control with three matching identities succeeded.
The [previous report](evidence/autonomous-source/chain-run-before-first-attestor-fix.json)
preserves the original behavior; it is not a report of the corrected contract.

## 2. Each complete version gathers its own votes

In `TerraEvidenceRegistry.sol`, each complete metadata envelope is a separate
candidate. Here, an envelope means all five fields listed above, attached to
the environmental data commitment. The SHA-256 commitment to the 97 archived
USGS observations remains unchanged; the candidate identifier does not replace it.

```text
Environmental batch: the same data commitment
  attacker's version -> 1 vote  -> not accepted
  agreed version     -> 3 votes -> accepted
```

The candidate identifier is:

```text
keccak256(abi.encode(
  keccak256("TerraVoce.EvidenceCandidate.v1"),
  chainId, registryAddress, evidenceHash,
  regionId, metadataHash, observedAt, kind, uri
))
```

ABI encoding includes every field, including the URI's UTF-8 bytes. It binds
the candidate to the rule version, chain and registry, and avoids ambiguous
string concatenation. Different URI strings remain different candidates:
verifiers must agree on the exact complete envelope.

## 3. One identity still has one vote per batch

`hasAttested[evidenceHash][address]` remains global across candidates. An address
cannot vote for one version and then another, or increase its weight by
repeating transactions. Revoking and granting its role again does not reset
this restriction. A different data hash represents a different batch.

Role authorization, nonempty/nonzero input checks, the configured quorum and
signed transactions remain required. Money and token holdings do not increase
an attestor's vote weight.

## 4. The final result is one coherent envelope

At quorum, the registry copies the winning candidate's region, metadata,
time, kind, URI and vote count together. It never combines votes for different
envelopes. Once accepted, that envelope cannot be replaced by another candidate.
Unused identities can still submit additional matching attestations, preserving
the previous behavior.

The `isAcceptedForRegion` interface used by TerraAct is unchanged. While votes
are pending, `evidence(hash)` continues to expose the first candidate. That
view is **provisional**, with `accepted = false`, and does not authorize action.
If another candidate wins, the getter returns the complete winning envelope.
Use `candidate` and `EvidenceCandidateAttested` to inspect individual counts.
`acceptedCandidateId` identifies the winner and is zero before quorum.
The existing `EvidenceAttested` event remains available, but its count belongs
to the submitted candidate, not the sum of all votes for the batch.

Review also found that copying the first envelope into provisional final-result
storage made honest attestors pay to replace an attacker's long URI. A regression
test reproduced finalization costs of 141,150 gas for a 32-byte attacker URI
and 1,354,685 gas for 10,000 bytes. The provisional getter now reads the candidate
directly; final-result storage receives only the winning envelope. This removes
the attacker-controlled string-clearing cost without imposing a new arbitrary
URI limit. The attacker still pays to store its own candidate.

After correction, the same test uses 231,918 gas in both cases. The separate
final write costs more in the short-URI case, but its cost no longer grows with
the attacker's URI length. These figures describe this test configuration;
they are not public-network fee estimates or prices in any currency.

## 5. We repeated the attack with the 97 real observations

`source:e2e` reuses the original USGS capture without making new environmental
requests. Three separate Node processes verify the batch. In a new local
registry, the fourth identity submits an envelope with an altered region,
metadata hash, time, kind and URI first. The other three attest the reproduced
honest envelope.

The [new report](evidence/autonomous-source/chain-run.json) retains the malicious
transaction, the three honest transactions, both candidate identifiers and
the results of assertions against actual contract state:

| Check | Expected and verified result |
| --- | --- |
| Malicious first candidate | One vote; not accepted |
| First and second honest votes | No premature acceptance |
| Third honest vote | Honest envelope accepted with three votes |
| Every finalized field | Matches the honest envelope |
| Attacker's invented region | Not accepted |
| Second vote by the same malicious identity | Rejected as a duplicate |
| Conflicting envelope after finalization | Rejected |

This is a test with a **malicious attesting identity**. The harness controls
all keys and signs transactions; the verification processes are not independent
operators and do not hold their own signing keys. No networked ABCI/Open Autonomy
cluster or compromised remote node is exercised here. The EVM ends when the
command finishes. Retained receipts are not independent public-chain consensus
proofs verified through an explorer.

## 6. We checked variants and compatibility

`packages/contracts/test/TerraEvidenceRegistry.ts` adds 15 tests. They cover each
of the five alterable fields, all 24 arrival orders of one malicious and three
honest identities, split candidate votes, duplicates including role re-enrollment,
authorization, invalid input, complete encoding, isolation between registries,
finalization immutability and provisional getter behavior. One test compares
honest finalization after malicious URIs of 32 and 10,000 bytes to prevent the
resource regression described above.

The 24 orders are cases executed against the Solidity contract inside one test;
they are not 24 operators or an attack probability. The Python model separately
compares 120 abstract orders with the legacy rule. It explains the design but
does not prove distributed consensus. Existing governance, treasury, escrow
and environmental-case checks remain part of compatibility validation.

## 7. We updated the evidence without deleting its history

The current chain report uses `autonomous-source-local-chain-test-v2`. Offline
verification checks the recovery scenario and hashes of 13 files, adding the
demonstration script to the previous artifact list. The metadata commitment
changes with the code; the environmental data commitment and original
measurements remain unchanged.

The report is pinned to Git. After modifying the registry, `source:verify`
must reject the old report: run the new experiment, retain its output and
checkpoint it in Git. This check was not disabled to make validation pass.
Offline verification checks report consistency and file commitments; it does
not query the ephemeral blockchain after that chain has ended.

## 8. What this correction does not resolve

- Three captured identities can still attest a falsehood, and the enrollment
  administrator can still add operators. The contract does not enforce a fixed
  population of four operators or establish their independence.
- False or incomplete initial publisher data can deceive every honest replica.
  Agreement does not establish calibration or physical environmental truth.
- One malicious identity plus one absent honest identity leaves only two honest
  votes. The quorum remains three; it was not lowered to manufacture progress.
- Role revocation does not automatically retract accepted evidence. Challenges,
  corrections and distributed retention remain future work.
- The registry is not a proxy, and the Governor's registry reference is immutable.
  This patch affects new instances; it does not repair an already deployed
  registry. A real migration needs a separate plan and authorization review.

The correction supports TerraVoce's original mission: reduce a single identity's
power to censor environmental evidence. It does not change the Willamette model,
the Awash case, TerraLex, civic chambers or treasury limits. It does not activate
physical intervention, an LLM, real spending or public-chain publication.

## Reproduce the experiment

From the repository root, with Node.js 24, pnpm 11.7.0 and locked dependencies:

```sh
pnpm install --frozen-lockfile
pnpm build
pnpm check
pnpm contracts:test
pnpm source:verify
pnpm source:e2e
pnpm e2e
pnpm case:e2e
python scripts/audit_autonomous_source.py
python scripts/explore_evidence_quorum.py
```

`source:verify` requires the updated report already checkpointed in Git. The
experiments use retained archives and local test identities. They need no
funded wallets, new credentials, Docker or changes to the USGS service.

## Contribute from another country

Read [CONTRIBUTING.md](../CONTRIBUTING.md) for the project's contribution and
evidence standards. The implementation paths are:

| Area | File |
| --- | --- |
| Shared vote/finalization boundary | `packages/contracts/contracts/TerraEvidenceRegistry.sol` |
| Focused regression tests | `packages/contracts/test/TerraEvidenceRegistry.ts` |
| Real-data adversarial EVM experiment | `packages/contracts/scripts/source-evidence-e2e.ts` |
| Checkpoint/report verification | `services/environmental-case/src/discovery-cli.ts` |
| Rules to preserve | `docs/invariants.md` |

For a focused contract check:

```sh
pnpm --filter @terravoce/contracts test --grep "TerraEvidenceRegistry candidate quorum"
```

A useful contribution describes a concrete trigger, adds a reproducible
regression case and preserves the valid control. Keep source independence,
enrollment capture, physical truth and public deployment separate from claims
about this local fix. Do not commit credentials, funded-wallet keys or private
sensor identities. Submit changes through a focused pull request, retaining
the research scope and community-governance boundaries.
