# First real-data environmental case

This module delivers a reproducible oxygen **data review**, using real USGS
measurements. It is a territorial module of Virdacora's global mission:
distributed analysis, resilient evidence, verifiable intervention funding,
and decision rights for affected communities and young people.

The data are real. The clock, civic identities, result reviewers, consensus
certificate signers, and token transfers in the demonstration are simulated.
No field operator has been commissioned and no ecological improvement is claimed.

## Separate numerical experiment

`pnpm forecast:replay` and `pnpm forecast:verify` (repository root) run a
separate observation-only oxygen/temperature/discharge comparison. See the
[protocol, results and rollback boundary](../../docs/WILLAMETTE_FORECAST_EXPERIMENT.md).
It does not replace the assessment or change the real-data review/escrow below.

## Source and scientific protocol

- USGS station `USGS-14211720`, Willamette River at Portland, Oregon, a tidal stream.
- Continuous dissolved oxygen, parameter `00300`, series
  `1ccd1e712b6b4cb69fdcfbf407f7358b`, statistic `00011`, normalized to mg/L.
- Fixed interval: 2025-08-01 00:00 UTC through 2025-08-15 00:00 UTC inclusive.
- Accept only `Approved`, unqualified, finite nonnegative measurements. Preserve
  excluded record IDs/reasons; reject mixed units/series, duplicates, off-grid
  times, bad hashes, or incomplete paginated captures. Never interpolate gaps.
- Forecast origin evaluation starts 2025-08-08 00:00 UTC. Use the previous
  12 measurements, including the origin, for a rolling 1-hour prediction.
  Those points span 5.5 hours at the expected 30-minute cadence.
- Compare `terravoce-linear-risk-v1` with persistence (the latest measurement).
  Require an exact approved target timestamp. Report MAE, RMSE, false alerts,
  missed low-oxygen events and missing pairs. A 5 mg/L threshold is illustrative,
  not a local ecological/legal standard. No parameter tuning is performed.

The public-domain snapshot, station metadata and retrieval manifest are in
[`docs/datasets/usgs-willamette`](../../docs/datasets/usgs-willamette).
Raw response files retain their exact UTF-8 bodies and SHA-256 hashes. Data are
subject to upstream revisions; the manifest is a pinned research capture.
The first seven days precede the evaluation period; each prediction uses only
measurements at or before its origin. Evaluation windows overlap and errors
are correlated; this is one site and season, not a general performance estimate.
Approval and revisions in this archive can postdate a prediction origin. This
is a retrospective comparison on finalized data, not a backtest of which values
were available to a live service at that historical instant.

## Observation to result

1. Load and validate the pinned source. The local importer signs the normalized
   observations with an ephemeral Ed25519 key. This authenticates the importer,
   **not USGS or the original sensor**. Send the 12 origin observations through
   the existing Oracle API and reproduce its assessment independently.
2. Precommit the first evaluation origin, the exact follow-up timestamp,
   assessment, source/manifest hashes, policy hash, 10 TEST budget, objective and
   acceptance rules into `caseHash`. The action is `DATA_REVIEW`, not aeration or
   extra physical sampling. Never select a case after seeing a favourable error.
3. Submit through `TerraAutonomyBridge`. This new end-to-end script uses a local
   3-of-4 signature fixture; it does **not** launch Open Autonomy ABCI replicas.
   The separate existing outage test remains the real cluster test.
4. Challenge the proposal and vote in both civic chambers. Execution transfers
   valueless mock tokens to `TerraResultEscrow`, not to the executor.
5. Deliver the approved follow-up observation and prediction/persistence errors,
   committing the report into `resultHash`. Payment acceptance concerns delivery
   and reproducibility, never an artificially successful prediction.
6. Reproduce the result against the committed source and policy. Two fixed,
   distinct reviewers (scientific and community) must approve the **same** hash.
   They cannot be the executor. A single review, an outsider, an amended report,
   or a reused payout cannot unlock funds. Reviewers can reject, a Governor
   guardian can cancel, and anyone can refund on expiry. Refunds go to treasury.

The escrow binds one exact proposal (region/evidence/policy/action/amount/case
URI/recipient). Its deadline is 30 days after binding. Case terms and reviewers
cannot be replaced; a revised case requires a new proposal. A refund does not
restore the Governor's autonomous epoch allowance, conservatively retaining
the original spending accounting. The on-chain hash/URI is an attestation,
not storage or proof of physical truth. Reviewers remain a trust boundary.

## Reproduce

From the repository root, with the versions required in `package.json`:

```sh
pnpm install --frozen-lockfile
pnpm build
pnpm case:replay
pnpm case:verify
pnpm case:e2e
```

The commands create `outputs/real-case/{replay,case,result,verification,chain-run}.json`.
Offline commands need neither an API key nor a wallet, Docker or Ollama.
Case/result files use exclusive creation; an altered existing artifact is
rejected. Hashes identify content but do not prevent filesystem deletion.
The local chain report is replaced on each demonstration run. The Hardhat
network is ephemeral; its transaction hashes are not public-chain explorer links.

Optional fresh check against USGS (two HTTPS requests, no key at this volume):

```sh
pnpm --filter @terravoce/environmental-case verify-live
```

It checks all 12 input records and the exact target against newly retrieved,
approved/unqualified values. Missing, revised or newly qualified observations
stop verification; raw-response changes are disclosed. It writes a
content-addressed `upstream-*.json`. This is a second retrieval from the **same**
source, not an independent instrument or reviewer. For a new capture without
overwriting the frozen dataset:

```sh
pnpm --filter @terravoce/environmental-case fetch ../../work/usgs-new-capture
```

## First observed result

673 approved measurements, no missing intervals, 335 exact forecast/target pairs.

| Method | MAE mg/L | RMSE mg/L |
| --- | ---: | ---: |
| Current regression | 0.242038 | 0.329716 |
| Persistence | 0.204776 | 0.297351 |

The existing model is worse than persistence on this window. No measurements
fall below the illustrative threshold; zero false/missed alerts cannot establish
low-oxygen detection ability. Risk/confidence remain uncalibrated heuristics.
The selected case predicts 8.655594 mg/L for 2025-08-08 01:00 UTC; the observed
approved value is 8.2 mg/L, compared with a persistence prediction of 8.4 mg/L.
The verified deliverable is an honest data-review report, not restoration.

Published reports are in [`docs/evidence/usgs-case`](../../docs/evidence/usgs-case).
The language-model advisor is not invoked in this run and cannot authorize
funding. The original four-replica outage experiment is not rerun here.

## Field transition and global scope

The implementation completes the real-data/software workflow. A physical pilot
remains pending: identify a willing local operator, an independent environmental
reviewer, and representatives of the affected community and youth; agree a
site-specific measurement protocol and decision rights; then submit a new case
with sampling evidence, calibration records and explicit acceptance criteria.
Do not treat archival target measurements as a commissioned field action.

Portland is an accessible validation source, not a claim that Virdacora already
represents that community. The Po example and global mission remain intact.
Other territories need their own source adapters, methods, civic registrations
and policies; token ownership continues to confer no environmental voting rights.

## Primary sources

- [USGS station and metadata](https://waterdata.usgs.gov/monitoring-location/USGS-14211720/)
- [USGS API, public-domain status and collection descriptions](https://api.waterdata.usgs.gov/ogcapi/v1/)
- [Continuous schema: units, approval and qualifiers](https://api.waterdata.usgs.gov/ogcapi/v1/collections/continuous/schema?f=html)
- [Provisional data statement](https://waterdata.usgs.gov/provisional-data-statement/)

Attribution: U.S. Geological Survey, Water Data for the Nation, continuous oxygen
measurements for USGS-14211720, 2025-08-01–2025-08-15 UTC; access date and exact
URLs/hashes are recorded in `manifest.json`. Snapshot content is US Government
work in the public domain; Source terms follow [LICENSE_POLICY.md](../../LICENSE_POLICY.md); external data retain their own terms.
