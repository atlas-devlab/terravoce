# TerraVoce architecture

This document describes the intended architecture. The current research MVP
uses synthetic sensor data and a deterministic mathematical risk model. A real
Open Autonomy service now runs four Oracle/agent/validator replicas locally and
certifies one immutable job with a 3-of-4 quorum. Treasury operations use a local
simulated blockchain; independently operated replicas, a public deployment and
a field pilot are future work. A separate local language advisor selects grounded
facts and citations in observation-only mode; it is not wired into the bridge.
See [bridge validation](AUTONOMY_VALIDATION.md) and [AI validation](AI_VALIDATION.md).

## Design decision

AI inference does not run inside the blockchain. Models are too expensive to
execute on-chain, model weights are difficult to reproduce across runtimes, and
opaque inference would make consensus depend on a vendor. Instead, independent
oracle operators reproduce numerical assessments and validate a canonical
proposal. The implemented language advisor generates a local advisory outside
consensus. Future consensus validators will check its evidence and permitted
action rather than require identical generated text. Model provenance and
advisory hashes still need to be bound into the evidence protocol. Contracts enforce quorum, authorization,
delays, budgets, and execution. See [the AI design proposal](AI_DESIGN.md).

## Components

1. Sensors sign canonical observations with Ed25519 keys.
2. Oracle replicas verify signatures and retain the raw observations.
3. The assessment engine computes anomaly, trend, forecast, confidence, and
   risk using a versioned deterministic model.
4. TerraLex evaluates whether an assessment may create an autonomous reversible
   action. The compiled policy and its hash are public.
5. The evidence registry requires its configured attestation quorum; the current
   test sets up attestations through a fixture. Separately, Open Autonomy collects
   three operator signatures and TerraAutonomyBridge submits a reversible
   proposal. Distributed publication of evidence attestations remains future work.
6. TerraAct routes the proposal through an autonomous challenge window or a
   two-chamber vote, depending on risk.
7. The treasury releases one stable funding asset only through an executable
   proposal. Autonomous spending also has an immutable epoch cap.

## Trust boundaries

```text
sensor key -> signed observation -> oracle quorum -> evidence hash
                                                |
TerraLex source -> canonical compiler -> policy hash
                                                |
                                                v
community registry -> TerraAct governor -> locked treasury -> recipient
         youth chamber ----^       ^
         guardian pause -----------|
```

Raw data and model artifacts may be mirrored through object storage and
content-addressed networks. Only hashes, concise metadata, votes, and treasury
state belong on-chain.

## Deployment target

The contracts are EVM portable. The first deployment should use a low-cost
public testnet on an OP Stack-compatible L2. Production administration must be a
multisig behind a timelock; deployer keys must renounce direct control after the
bootstrap ceremony.

