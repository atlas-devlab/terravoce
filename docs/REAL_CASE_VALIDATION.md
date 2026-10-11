# Real-data case validation — 2026-10-11

The global environmental mission and civic/treasury boundaries are preserved.
The first territorial adapter supplies real USGS data, not a deployed field pilot.
See [the case protocol and commands](../services/environmental-case/README.md).

## Observed behavior

- Pinned USGS archive: 673 approved oxygen records, 30-minute cadence, no gaps.
- 335 chronological one-hour comparisons: regression MAE 0.242038 mg/L,
  persistence MAE 0.204776 mg/L. The existing model does not beat persistence
  in this window. No observed low-oxygen events at the illustrative 5 mg/L
  threshold; false/missed-alert counts are not evidence of detection skill.
- First origin 2025-08-08 00:00 UTC, target 01:00 UTC: predicted 8.655594 mg/L,
  observed 8.2 mg/L, persistence 8.4 mg/L. Acceptance is delivery of an accurate
  review report, not a successful forecast or ecological improvement.
- Fresh same-source HTTPS retrieval matched all 12 approved input values and
  the approved exact-time target. The raw response hash differed; normalized
  committed IDs, times and values matched. The frozen original remains unchanged.
- Existing Oracle API accepted importer-signed real observations and reproduced
  the case assessment. These are importer signatures, not USGS sensor signatures.
- Existing bridge accepted a 3-of-4 local signer certificate. Community challenge
  triggered voting; both community and youth approved. Funds entered escrow
  and reached the executor only after the two fixed result reviewers approved.
- Local negative checks blocked premature execution/payment, one-review payment
  and an outsider review. Contract tests also cover youth rejection, case/amount/
  policy/action mismatch, replaced results, duplicate reviews/payouts, rejection,
  guardian cancellation and expired-case refund to treasury.

## Checks

Build and workspace checks passed with Node 24.18.0 and pnpm 11.7.0.
70 TypeScript/Solidity tests passed (45 Vitest and 25 Hardhat), including 13
real-data tests and 10 escrow tests. Seven existing Python bridge tests passed.
The existing synthetic blockchain end-to-end demonstration also passed.
The new replay, frozen-result verification, fresh-source verification and
real-data local-chain demonstration passed. CI now runs the frozen case and
local-chain path; it does not depend on USGS availability for its normal checks.

Published execution artifacts are under [evidence/usgs-case](evidence/usgs-case).
Case/result identifiers are stable across replay; demo transaction hashes belong
to ephemeral local Hardhat runs and may change. They are not public deployment
addresses or external audit attestations.

## Scope limits and next field gate

This is a retrospective finalized archive, not an as-of-origin provisional-data
availability backtest. One station/season and correlated rolling errors cannot
establish general scientific validity. The threshold and risk/confidence
heuristics remain illustrative. There is no new fitted model or LLM inference
in this case, and no claim that the current predictor authorizes physical action.

Review identities, the three certificate signers, civic voting, time and funding
are simulated. The real Open Autonomy/Tendermint outage cluster was not rerun
with this dataset. Reviewer addresses must represent accountable, distinct people
or organizations before field use; distinct addresses alone do not prove that.
The same-source fresh retrieval is not an independent physical measurement.

Source hashes and on-chain URIs do not publish or preserve the data automatically;
the repository carries the public snapshot and reports. Geographic replication,
continuous processing, operator recovery, public-chain deployment and independent
security/scientific review remain future gates. No real funds or actuator is used.

A new physical-sampling case requires an enrolled operator and scientific
reviewer, affected-community/youth representation, an agreed local protocol,
calibration/collection evidence, and committed outcome criteria. Until then
physical sampling, independent field review and ecological impact remain pending.
