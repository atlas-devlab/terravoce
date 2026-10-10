# TerraVoce

An open source research prototype for environmental coordination: signed sensor
observations, reproducible risk assessments, executable environmental policies,
and community governance enforced by Solidity smart contracts.

The current example models dissolved oxygen in the Po Delta using synthetic
observations. It demonstrates the path from evidence to an authorized, budgeted
intervention on an ephemeral local blockchain.

**Status: research MVP.** There is no public-chain deployment, live environmental
pilot, real treasury funding, connected physical actuator, or independent audit.
The risk model is a simple deterministic mathematical model. TerraVoce and
TerraLex are working names; TerraLex refers here to the experimental policy
language in this repository.

> Per una spiegazione completa in italiano, leggi la
> [guida operativa](GUIDA_OPERATIVA.md).

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

## Run locally

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

## Help build it

We welcome contributions from developers, environmental researchers, data and
sensor specialists, and people interested in community governance. Useful first
steps include clearer examples, more negative test cases, API documentation,
scientific criticism of demo assumptions, and accessible Italian/English guides.

**Invito alla community:** aiutaci a costruire TerraVoce. Cerchiamo contributi
al codice e ai test, competenze su dati e sensori ambientali, e confronto sulle
regole di partecipazione delle comunità. Puoi iniziare con una piccola attività,
fare una domanda o proporre un miglioramento nelle issue. Il progetto è un
prototipo aperto: ogni contributo deve poter essere discusso e verificato.

Read [CONTRIBUTING.md](CONTRIBUTING.md), browse the
[open issues](https://github.com/atlas-devlab/terravoce/issues), or propose a small,
reproducible improvement. Use synthetic data in examples and tests.

## License

Project source is published under the [MIT License](LICENSE), consistent with
the MIT SPDX headers already present in the recovered Solidity contracts.
External dependencies retain their own licenses; see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
