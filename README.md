# TerraVoce

An open source research prototype for making environmental data and decisions
traceable and reproducible.

The current example follows synthetic dissolved-oxygen observations through a
simple risk model, explicit policy rules, and a community decision on a local
simulated blockchain.

**Status: research MVP.** There is no public-chain deployment, live environmental
pilot, real treasury funding, connected physical actuator, or independent audit.
The risk model and its risk/confidence scores are demonstration heuristics,
without field validation. TerraVoce and TerraLex are working names; TerraLex
refers here to the experimental policy language in this repository.

> Per una spiegazione completa in italiano, leggi la
> [guida operativa](GUIDA_OPERATIVA.md).

## First goal: replay one open oxygen dataset

Replay **one openly licensed dissolved-oxygen time series from one monitoring
station, offline**. Compare the current model with a simple prediction that uses
the latest measured value, and report the errors. This replay is not implemented
yet; [issue #3](https://github.com/atlas-devlab/terravoce/issues/3) is the place to
suggest a dataset or help with the experiment. The result should be reproducible
by another person. See the [validation criteria](CONTRIBUTING.md#validation-target-for-the-replay).

## Everyone can take part

You do not need coding experience or an environmental qualification to ask a
question, share an idea, improve an explanation, translate a paragraph, or report
what happened when you tried the demo. Questions about what is unclear are useful.

| Small first step | Where to start |
| --- | --- |
| Ask a question, try the demo, or clarify or translate one part of the walkthrough. | [Issue #1](https://github.com/atlas-devlab/terravoce/issues/1) |
| Suggest a public oxygen dataset, or ask about a demonstration threshold. | [Issue #3](https://github.com/atlas-devlab/terravoce/issues/3) |
| If you want to contribute code, add one negative test for an existing policy rule. | [Issue #2](https://github.com/atlas-devlab/terravoce/issues/2) |

For a small change, fork the repository and open a pull request without waiting
for an assignment. A short issue comment can help avoid duplicate work. Larger
changes should start with a discussion. See [CONTRIBUTING.md](CONTRIBUTING.md).

**Puoi partecipare anche senza saper programmare:** una domanda, un'idea, una
traduzione o una prova della demo sono già contributi utili.

## How it works

1. Sensors sign observations with Ed25519; the oracle checks signatures and
   observation sequence numbers.
2. The oracle produces a reproducible assessment and evidence hash.
3. TerraLex compiles and evaluates a restricted environmental policy, including
   allowed actions, budget limits and a challenge window.
4. Smart contracts record evidence and policy versions, govern proposals, and
   constrain treasury transfers.
5. Affected-community and youth chambers participate in governance. Ownership of
   the experimental ENV token does not grant environmental voting rights.

## Repository map

| Path | Purpose |
| --- | --- |
| `packages/terralex` | Policy parser, compiler, evaluator and CLI |
| `packages/protocol` | Signed observation and assessment schemas |
| `packages/contracts` | Evidence, policy, civic governance, treasury and ENV contracts |
| `services/oracle` | Sensor API, deterministic analysis, storage and policy evaluation |
| `policies` | Demonstration policy for Po Delta water oxygen |
| `docs` | Architecture, API, invariants, threat model, deployment and validation |

## Run the current demo locally

Install **Node.js 24 or later** and **pnpm 11.7.0**, matching `package.json`.
From the repository root:

```sh
pnpm install --frozen-lockfile
pnpm build
pnpm check
pnpm test
pnpm terralex compile ../../policies/po-water-v1.terra
pnpm demo
pnpm e2e
```

`pnpm terralex` runs the CLI from `packages/terralex`, so the policy path above
is relative to that package. Run the command itself from the repository root.

`pnpm e2e` uses Hardhat's local simulated network and generated demo identities.
It does not require a wallet, an RPC provider, or real funds. Build the workspace
before running individual package tests, because internal package exports point
to their compiled output.

For the optional PostgreSQL-backed local service, install Docker and run:

```sh
docker compose up -d --build
```

The health endpoint is `http://localhost:8877/healthz`. Stop the services with
`docker compose stop` to preserve the local database volume. Compose uses
development credentials; keep this demonstration on a trusted local machine.
The example configuration contains placeholders, and the Node process reads
configuration from environment variables rather than automatically loading `.env`.
See [deployment notes](docs/deployment.md) for configuration and production gates.

See [validation](docs/VALIDATION.md) for the checks rerun for this source publication
and the boundaries of that verification.

## License

Project source is published under the [MIT License](LICENSE), consistent with
the MIT SPDX headers already present in the recovered Solidity contracts.
External dependencies retain their own licenses; see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
