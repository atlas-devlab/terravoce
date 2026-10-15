# Owasco Lake: first one-hour transfer test

[Spiegazione italiana](OWASCO_LAKE_TRANSFER.md).

**Status: protocol prepared; lake acquisition and results are pending.**
This document describes the experiment before inspecting lake observations.
It does not yet assign an advantage to any of the four methods.

## 1. The question being tested

Can the model developed on the Willamette predict dissolved oxygen one hour
ahead at a lake sonde without learning from that lake's outcomes?
This is a strict geographical and ecosystem transfer probe.
We are not building a locally optimized Owasco forecasting model.
A failure would be a result to preserve, not a reason to change the lake,
window or threshold after seeing its errors.

## 2. Source selection and its rationale

The source is **USGS-425327076313601, Owasco Lake platform, New York**.
This natural lake has a reported maximum depth of approximately 50 metres.
Its catchment includes agriculture; we do not describe it as pristine.
Selection uses metadata and instrument documentation, not observed values
or candidate forecast performance. The provider remains USGS: this changes
geography and ecosystem, but is not corroboration by an independent provider.

| Measurement | Code | Pinned time series | Catalogue location |
|---|---|---|---|
| Dissolved oxygen, mg/L | `00300` | `b3904dc881b44599bc5f7eeb63da5a40` | EXO 1; Depth at 3 feet |
| Water temperature, °C | `00010` | `d584a0bd0b6f4e979451c8498c85a192` | EXO 1; Depth at 3 feet |

These are two parameters from the **same EXO 1 sonde**, with primary
instantaneous series. The USGS study reports measurements every 15 minutes.
The catalogue's `data_gap_interval: PT1H12M` is a gap-detection threshold,
not the sampling cadence. A documentation discrepancy remains explicit:
the catalogue says **3 feet**, while the study table gives **0.76 m** for
the near-surface Owasco deployment. Preserve both descriptions; an exact
depth has not been independently verified. Do not mix EXO 2, EXO 3 or
temperature-chain sensors into these records.

We considered NEON's Lake Suggs, but its file listing requires authentication
and temperature at the same depth had not yet been verified. Lake Houston
samples successive depths with hourly observations at each depth; we do
not interpolate those observations to manufacture a half-hour history.

## 3. The filter selected on Willamette development data

The [archived development run](evidence/willamette-threshold-development/evaluation.json)
selected **τ = 0.10 mg/L** using only previously inspected Willamette windows.
The regression coefficients remained unchanged.

| Development part | Persistence MAE | Filter MAE |
|---|---:|---:|
| Selection A, equal mean of four windows | 0.08488555 mg/L | 0.08191451 mg/L |
| Internal later check B, same mean | 0.09348669 mg/L | 0.08802214 mg/L |

The descriptive improvement on B is approximately **5.845%**. Both parts had
already been inspected: **this is not new independent validation**, nor does
it establish that the threshold works on Owasco. No other threshold was
scored on B.

## 4. Four methods on the identical accepted origins

- **P, persistence:** repeat the latest dissolved-oxygen measurement.
- **R, frozen regression:** apply the complete original correction.
- **C, previous fallback:** use P if all twelve historical oxygen values
  are equal; otherwise use R.
- **F, small-correction filter:** use P when `abs(R - P) <= 0.10 mg/L`;
  otherwise use R. This is a separate rule from C.

The same eight inputs keep their order: current oxygen; oxygen changes over
30 minutes, 2 hours and 5 hours 30 minutes; UTC clock sine/cosine; current
water temperature; and its change over 2 hours. Coefficients, standardization
and UTC clock remain fixed. No local-time adjustment, refitting, additional
variable or threshold selection is allowed using lake data.

## 5. Window and quality rules fixed before observations

The [protocol](datasets/owasco-lake-transfer/protocol.json) fixes **1–29 July
2020 at 00:00 UTC, inclusive query endpoints**: one 28-day window.
Each exact UTC `:00` or `:30` origin needs twelve consecutive half-hour
oxygen and temperature records, plus the exact oxygen target one hour later.
The history ends at the origin and spans 5 hours 30 minutes.
There is no interpolation, averaging or gap filling. Unused quarter-hour
records remain in the raw archive. Accepted values must be approved,
unqualified and finite, with nonnegative oxygen, exact series identities
and correct units. Duplicate records, pagination and truncation must be detected.

Discharge is not one of the eight regression inputs. It was required when
constructing the Willamette cohort; the lake eligibility rules explicitly
require oxygen and temperature only. This changes the cohort requirement;
it does not replace missing discharge with a fabricated zero.

There are **1,332 expected origins**. The practical completeness screen requires
at least 1,000 pairs and 90% of the expected origin grid. These are not
statistical power calculations, instrument-accuracy claims or ecological
validation criteria.

## 6. How the result will be assessed

**MAE in mg/L** on the identical accepted cohort is the primary metric.
F must have lower MAE than P beyond the `1e-9 mg/L` numerical tolerance,
adequate completeness, and finite nonnegative predictions.
Paired calendar-block bootstrap runs with 48-, 24- and 72-hour blocks and
5,000 resamples each must all return positive lower gain bounds for
`absolute error P - absolute error F`.
These are exploratory intervals conditional on this window, not prediction
intervals or three independent confirmations. RMSE, signed bias, extreme
errors, daily comparisons and departures from univariate training ranges
remain diagnostics.

## 7. Traceability, limitations and pending results

The protocol requires committing and publishing the exact implementation,
metadata, threshold and calendar before the first lake measurement request.
Capture permits one exclusive attempt, preserves raw response bodies and
failure evidence, and forbids automatic retries or window replacement.
Hashes link the archives to the code; they do not independently authenticate
the sensor's physical truth.

The model was trained on **2024** Willamette data, while the lake archive is
from **2020**. This does not simulate information available to a historical
forecaster in 2020. One sonde in one summer cannot establish skill across
the entire lake, deep layers, four seasons, other lakes or live operation.
Practical environmental benefits and operational promotion are not defined.

**Results: pending.** Planned outputs are `docs/evidence/owasco-lake-transfer/evaluation.json`
and `docs/notebooks/owasco-lake-transfer.ipynb`; neither is presented here as
a completed artifact. This experiment changes no operational Oracle, quorum,
governance, treasury, token or spending. Its purpose is understandable,
verifiable environmental evidence supporting communities and youth.

## Primary sources

- [Official Owasco platform page](https://waterdata.usgs.gov/monitoring-location/USGS-425327076313601/).
- [USGS SIR 2024-5010: instruments, depths, sampling and quality](https://pubs.usgs.gov/publication/sir20245010/full).
- [Official API catalogue, EXO 1 sonde](https://api.waterdata.usgs.gov/ogcapi/v1/collections/time-series-metadata/items?monitoring_location_id=USGS-425327076313601&sublocation_identifier=EXO%201&limit=50&f=json).
