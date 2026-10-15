# Owasco Lake: first one-hour transfer test

[Spiegazione italiana](OWASCO_LAKE_TRANSFER.md).

**Status: completed, `no-overall-improvement`.** The filter does not beat
persistence on MAE: it is almost identical, slightly worse. Exploratory
intervals include zero; they establish neither a benefit nor statistically
confirmed deterioration. Sections 1–6 preserve the design fixed before
capture; section 8 reports outcomes without changing the threshold.

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

## 7. Traceability and limitations

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

Commit `c06f1a79f073f71764aef501e9ae0f298a775377` was pushed before the first
request for either series. Both responses returned HTTP 200 and were archived
completely without repeating capture. The
[complete report](evidence/owasco-lake-transfer/evaluation.json) and
[executed notebook](notebooks/owasco-lake-transfer.ipynb) retain the results.
This experiment changes no operational Oracle, quorum,
governance, treasury, token or spending. Its purpose is understandable,
verifiable environmental evidence supporting communities and youth.

## 8. Observed result

All 2,685 oxygen and 2,684 temperature records are approved and unqualified.
The exact grid yields **1,275 pairs out of 1,332**, **95.7207%**: 44 origins
without DO on the required grid and 13 with incomplete history or target.
The declared completeness screen passes.

| Method | MAE, mg/L | RMSE, mg/L |
| --- | ---: | ---: |
| Persistence P | 0.038667 | 0.068428 |
| Frozen ridge R | 0.048166 | 0.067191 |
| Previous fallback C | 0.047860 | 0.067450 |
| Filter F, threshold 0.10 | 0.038692 | 0.068125 |

MAE F−P is **+0.000025693 mg/L**, approximately +0.06645%: a small point
disadvantage, not evidence of significant deterioration. Digits serve
arithmetic reproducibility, not claims about physical sensor accuracy.
The filter changes only **4 predictions**: 2 wins, 2 losses and 1,271 ties.
An ability to select useful events has not been demonstrated.

| Bootstrap blocks | Lower filter gain over persistence | Upper gain, mg/L |
| --- | ---: | ---: |
| 48 hours, primary | −0.000403597 | +0.000422240 |
| 24 hours | −0.000396982 | +0.000398638 |
| 72 hours | −0.000525352 | +0.000460663 |

All include zero. Slightly better secondary RMSE does not change the primary
MAE outcome. No threshold was adjusted using lake results.

A timestamp check finds 84 oxygen and 82 temperature samples on July 27–28
with `minute % 15 = 10`. Missing exact-grid origins therefore do not equal
the same number of physical gaps. The cause is unknown; timestamps were
neither rounded nor shifted to recover examples.

**819 pairs (64.24%)** have at least one input outside univariate training
ranges, mainly current temperature (814 pairs). This identifies unseen input
values, not a causal explanation or a validated reliability domain. No target
is below the illustrative 5 mg/L level: no alert skill or local ecological
threshold is validated.

Replay and a [separate standard-library-only audit](../scripts/audit_owasco_evidence.py)
reconstruct the cohort, features, forecasts, scores and 48-hour bootstrap
within 1.78×10⁻¹⁵. This is independent code/arithmetic verification, not a
second independent observation of the lake. The notebook completes six code
cells without errors. From the repository root, without network access:

```sh
python scripts/evaluate_threshold_development.py verify --report docs/evidence/willamette-threshold-development/evaluation.json
python scripts/lake_transfer.py verify --report docs/evidence/owasco-lake-transfer/evaluation.json
python scripts/audit_owasco_evidence.py
python -m unittest discover -s scripts -p 'test_*.py'
```

## Primary sources

- [Official Owasco platform page](https://waterdata.usgs.gov/monitoring-location/USGS-425327076313601/).
- [USGS SIR 2024-5010: instruments, depths, sampling and quality](https://pubs.usgs.gov/publication/sir20245010/full).
- [Official API catalogue, EXO 1 sonde](https://api.waterdata.usgs.gov/ogcapi/v1/collections/time-series-metadata/items?monitoring_location_id=USGS-425327076313601&sublocation_identifier=EXO%201&limit=50&f=json).
