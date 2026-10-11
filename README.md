# TerraVoce

An open source research prototype for making environmental data and decisions
traceable and reproducible.

TerraVoce's long-term mission is a global environmental coordination system:
distributed AI analysis, resilient public evidence, blockchain funding for
verifiable interventions, and decision rights for affected communities and young
people. The local prototypes below test individual parts of that mission.

The examples follow both synthetic observations and a pinned real USGS oxygen
dataset through a simple risk model, explicit policy rules, and civic decisions
on a local simulated blockchain. The real-data case verifies delivery of a
data-review report and gates payment on two result reviews.

**Status: research MVP.** There is no public-chain deployment, live environmental
pilot, real treasury funding, connected physical actuator, or independent audit.
The risk model and its risk/confidence scores are demonstration heuristics,
without field validation. TerraVoce and TerraLex are working names; TerraLex
refers here to the experimental policy language in this repository.

> Per una spiegazione completa in italiano, leggi la
> [guida operativa](GUIDA_OPERATIVA.md).

## First real-data case: review USGS oxygen measurements

The [real-data module](services/environmental-case/README.md) replays 673 approved
USGS measurements from the Willamette River at Portland. Chronological 1-hour
evaluation gives 335 pairs: current-model MAE 0.242 mg/L versus persistence
0.205 mg/L. The simpler baseline performs better on this window. There are no
low-oxygen events under the illustrative threshold, so alert detection remains
unevaluated. This is one reproducible territorial module of the global mission.

The path includes source hashes/quality flags, Oracle ingestion, TerraLex,
the existing proposal bridge, community/youth voting, a committed follow-up
report and two-review escrow payment. Governance, reviewers and funds are
simulated; no physical sampling or independent field review has occurred.
After `pnpm build`, run `pnpm case:replay`, `pnpm case:verify` and `pnpm case:e2e`.
[Issue #3](https://github.com/atlas-devlab/terravoce/issues/3) remains a place to
discuss methods and limitations. See the [validation criteria](CONTRIBUTING.md#validation-target-for-the-replay).

## Observation-only multivariate forecasting experiment

A separate [Willamette experiment](docs/WILLAMETTE_FORECAST_EXPERIMENT.md) joins
real oxygen, temperature and signed instantaneous discharge measurements.
Training, selection, interval calibration and final evaluation use separate
chronological phases. The small summer improvement does not transfer to the
predeclared autumn and winter windows: frozen-model MAE is 0.306 versus 0.102
mg/L in autumn, and 1.279 versus 0.012 mg/L in winter. Its unchanged empirical
interval has zero winter coverage. An independent Python implementation checks
the numerical calculations against the TypeScript implementation; this is a
code cross-check by the same project, not an independent scientific audit.
The experiment is unsuitable for operational promotion. No operational Oracle,
governance or funding behavior changes. Run `pnpm forecast:replay` and
`pnpm forecast:verify` after building. This remains a reusable part of the
environmental coordination mission. Run
`python3 scripts/audit_willamette.py --external --summary`
to reproduce the seasonal check offline. See the executed
[audit notebook](docs/notebooks/willamette-forecast-audit.ipynb).

A subsequent [training-source readiness audit](docs/WILLAMETTE_TRAINING_READINESS.md)
archives four 2024 seasonal windows with 2,559 complete one-hour pairs. It also
exposes missing forecast origins: autumn has only 90.15% expected-grid coverage.
That readiness audit itself does not fit a model or claim forecast skill.

The subsequent [fixed four-season test](docs/WILLAMETTE_MULTISEASON_EXPERIMENT.md)
learns the same eight-feature ridge recipe on those 2,559 training pairs and
freezes the weights before acquiring four later 2025 windows. On 2,591 test pairs,
equal-season mean MAE is 0.109945 versus persistence 0.110874 mg/L: a 0.84%
point gain, with losses in winter, spring and autumn. The predeclared 48-hour
block-bootstrap interval for the absolute gain spans -0.003821 to 0.005414 mg/L;
24/72-hour checks also include zero. The result fails the declared improvement
rule. Two archived summer targets below the illustrative 5 mg/L threshold are
not anticipated. The 10% aspiration is not an acceptance gate. No model promotion
or operational behavior changes. Reproduce offline with
`python scripts/experiment_multiseason.py verify-fit` and `verify`.
See the executed [four-season notebook](docs/notebooks/willamette-multiseason.ipynb).

## Awash irrigation observation and prediction game

The separate [Awash learning game](docs/AWASH_IRRIGATION_GAME.md) archives small
FAO WaPOR evapotranspiration and precipitation windows near Wonji, Ethiopia.
A history-only persistence prediction was saved and pushed before target
acquisition: 2.9814 versus the next period's FAO estimate of 3.0417 mm/day,
absolute error 0.0603 mm/day. This is one retrospective round using revised
source estimates, not established forecasting skill or measured irrigation.
Native rainfall pixels remain coarse; missing values are not zero-filled.
The research evidence envelope cannot claim verified withdrawals, ecological
improvement or funding eligibility. Run `pnpm irrigation:verify` offline.
The Willamette forecast and operational Oracle/governance remain separate.

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
| `services/autonomy` | Replicated Oracle certification and 3-of-4 proposal bridge |
| `services/ai-advisor` | Local observation-only language advisor with verified citations |
| `services/environmental-case` | Real USGS data review, chronological replay and result reproduction |
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

## Replica del servizio Oracle

Il [ponte Open Autonomy](services/autonomy/README.md) aggiunge consenso 3-di-4 tra
Oracle replicati e un contratto che presenta proposte reversibili al Governor.
La prova locale spegne un nodo completo e verifica il blocco con due nodi spenti,
mantenendo i diritti delle camere civiche e la protezione della tesoreria.

## AI locale in modalità osservazione

Il [modulo AI advisor](services/ai-advisor/README.md) integra un modello locale
in modalità osservazione: seleziona fatti e citazioni verificabili per spiegare
un assessment e suggerisce un campionamento aggiuntivo oppure si astiene.
Qwen3 1.7B è stato selezionato su una piccola suite sintetica; il rapporto
[di validazione](docs/AI_VALIDATION.md) include anche il modello scartato.
L'advisor non presenta proposte sulla blockchain. Il primo replay numerico su
dati USGS reali è disponibile nel modulo environmental-case e mostra che la
regressione attuale non supera la baseline su quella finestra. Il collegamento
dell'advisory al consenso resta da implementare, come descritto nel
[progetto tecnico](docs/AI_DESIGN.md).
