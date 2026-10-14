# Threat model

## Protected assets

- integrity and availability of environmental observations;
- legitimacy of affected-community and youth votes;
- stablecoin held by the intervention treasury;
- physical safety of people, ecosystems, and infrastructure;
- reproducibility of policy and model decisions.

## Principal threats and current controls

| Threat | MVP control | Remaining production work |
| --- | --- | --- |
| Compromised sensor | Ed25519 signatures and sequence replay protection bind identity and payload; they cannot establish that a compromised sensor measured truthfully | hardware roots, calibration checks, revocation, independent corroboration |
| Malicious oracle | role-gated quorum for a complete candidate envelope; one vote per identity/root; first-attestor locking corrected in local EVM tests; test identities remain under one host administrator | independently administered operators, governed enrollment, reproducible runtimes; majority capture remains demonstrated in the autonomous-source test |
| AI prompt/model manipulation | no LLM in execution path; deterministic model | signed model artifacts, independent model families |
| Policy substitution | canonical TerraLex hash and active policy registry | formal compiler verification and governance timelock |
| Allowed policy used for another action | on-chain action, executor, region, amount binding | audited action-adapter contracts |
| Token plutocracy | civic credentials, no token-weighted environmental vote | private proof-of-personhood and appeal process |
| Permanent guardian veto | one pause per proposal with fixed expiration | distributed guardian set and accountability proofs |
| Treasury capture | no admin withdrawal; governor-only release | audited stablecoin behavior and emergency migration design |
| Membership manipulation | nullifier uniqueness and proposal-time snapshot | Semaphore/MACI, credential issuers, anti-coercion |
| Data censorship | content hashes expose changes against a retained external commitment; unavailable sources stop this discovery flow; separate candidate votes remove the first-attestor envelope lock | independently retained mirrors, omission detection, radio/mesh ingestion gateways; network-level availability and source independence remain unproven |

The [autonomous-source experiment](AUTONOMOUS_SOURCE_TEST.md) distinguishes
archive tampering, false initial publication, attestor capture, enrollment
capture and the original first-attestor censorship. The [bounded correction](FIRST_ATTESTOR_FIX.md)
tests the replacement candidate rule. Its local EVM run is not a test of
independently administered Open Autonomy nodes or physical sensor truth.

## Non-goals of this MVP

The software does not autonomously control pumps, gates, drones, chemical
dosing, land acquisition, or human access to critical resources. Production
physical actions require separate audited adapters with device authentication,
hard operating envelopes, emergency stops, and local legal authorization.

