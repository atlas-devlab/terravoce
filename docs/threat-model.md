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
| Compromised sensor | Ed25519 signatures, sequence replay protection | hardware roots, revocation, cross-sensor anomaly detection |
| Malicious oracle | independent attestation quorum | stake/slashing, diverse operators, reproducible containers |
| AI prompt/model manipulation | no LLM in execution path; deterministic model | signed model artifacts, independent model families |
| Policy substitution | canonical TerraLex hash and active policy registry | formal compiler verification and governance timelock |
| Allowed policy used for another action | on-chain action, executor, region, amount binding | audited action-adapter contracts |
| Token plutocracy | civic credentials, no token-weighted environmental vote | private proof-of-personhood and appeal process |
| Permanent guardian veto | one pause per proposal with fixed expiration | distributed guardian set and accountability proofs |
| Treasury capture | no admin withdrawal; governor-only release | audited stablecoin behavior and emergency migration design |
| Membership manipulation | nullifier uniqueness and proposal-time snapshot | Semaphore/MACI, credential issuers, anti-coercion |
| Data censorship | multiple sensors/oracles and content hashes | IPFS/Filecoin mirrors, radio/mesh ingestion gateways |

## Non-goals of this MVP

The software does not autonomously control pumps, gates, drones, chemical
dosing, land acquisition, or human access to critical resources. Production
physical actions require separate audited adapters with device authentication,
hard operating envelopes, emergency stops, and local legal authorization.

