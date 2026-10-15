# One-hour Willamette forecast: new-window test results

[Spiegazione italiana](WILLAMETTE_STABILITY_RESULTS.md).

**The fallback reduces the frozen ridge's error but does not beat persistence.**
The declared outcome is `no-overall-improvement`. The candidate remains research
code and does not qualify for the operational Oracle.

## 1. Fixed question and model

We forecast dissolved oxygen exactly one hour ahead at USGS-14211720,
Willamette River at Portland, Oregon. The eight-feature ridge, alpha=100,
was already trained on 2,559 archived 2024 pairs. Coefficients, means, scales
and intercept remain unchanged: this test performs no new fitting.

The [fixed rule](WILLAMETTE_STABILITY_PROTOCOL_EN.md) suppresses the entire
ridge correction if all twelve accepted past oxygen values, spaced exactly
30 minutes apart and ending at the origin, are numerically identical.
Otherwise it retains the complete ridge prediction. The rule receives no
future target. Equality concerns published precision, not physical river stability.

## 2. Freeze and capture

The protocol and calendar were committed in `14a7603`. The collector,
evaluator, dependencies and tests were committed and pushed as
`e8b4e133aa81ecda548480991584239a8ed142ea` before the new USGS requests.
Manifests bind each capture to that commit, a 14-file implementation inventory,
the protocol hash and frozen-model hash. The protocol JSON retains its
historical pre-capture phase description; its bytes were not changed afterward.

An exclusive persistent marker is written before HTTP. Concurrent starts
or restarts after interruption cannot silently repeat the fixed capture.
Original response bytes are compressed and SHA-256 committed. Complete
HTTP-error bodies and successful companion sources would also remain archived
on failure. All twelve requests succeeded in this run.

Git and local hashes establish reproducibility and integrity relative to
the saved archive, not a trusted external timestamp or physical sensor truth.
No new blockchain attestation was published.

## 3. Real measurements and completeness

Four fixed 28-day 2025 windows do not overlap the eleven previously captured
periods. There are 1,332 theoretical origins per window after allowing for
history and the one-hour target. All times are UTC; query endpoints are
inclusive. Sources must be approved, unqualified, finite and match the exact
station, series, statistic and units. Missing values are not interpolated.

| Season and UTC interval | Accepted pairs | Grid coverage | Past-flat histories |
| --- | ---: | ---: | ---: |
| Winter, February 1–March 1 | 1,276 / 1,332 | 95.80% | 439 |
| Spring, May 1–29 | 1,320 / 1,332 | 99.10% | 42 |
| Summer, June 1–29 | 1,298 / 1,332 | 97.45% | 0 |
| Autumn, November 1–29 | 1,319 / 1,332 | 99.02% | 52 |

All windows pass the 90% coverage and 1,000-pair screens. The comparison uses
5,213 pairs out of 5,328 theoretical origins; 115 lack the required complete
alignment and remain in the denominator. All 42,983 individual records in the
twelve responses pass record-level quality checks; time gaps still matter.
Signed instantaneous discharge is retained for unchanged pair eligibility
and diagnosis, although it is not one of the eight model inputs.

## 4. Comparison on identical pairs

Mean absolute error (MAE) is in mg/L; lower is better. The final row gives
equal weight to each seasonal MAE, as fixed before seeing results.

| Period | Persistence | Original ridge | Ridge with fallback |
| --- | ---: | ---: | ---: |
| Winter | 0.017085 | 0.028469 | 0.024586 |
| Spring | 0.083333 | 0.089813 | 0.089723 |
| Summer | 0.201695 | 0.193600 | 0.193600 |
| Autumn | 0.053980 | 0.062337 | 0.061973 |
| **Seasonal mean** | **0.089023** | **0.093555** | **0.092470** |

The fallback improves ridge by 0.001084 mg/L (1.1591%), but is worse than
persistence by 0.003447 mg/L (3.8720%). Three seasons remain worse than
persistence. Summer improves on persistence by about 4.0135%, but has no
past-flat histories: the new rule is not exercised there and equals ridge.

The secondary root mean squared error (RMSE), which gives greater weight
to large errors, is lower than persistence in all four windows:

| Season | Persistence RMSE, mg/L | Candidate RMSE, mg/L |
| --- | ---: | ---: |
| Winter | 0.041334 | 0.040482 |
| Spring | 0.149848 | 0.139865 |
| Summer | 0.338969 | 0.303065 |
| Autumn | 0.089646 | 0.085858 |

This describes a tradeoff between error measures, not a passing primary
test. No RMSE uncertainty intervals were estimated, and the MAE acceptance
criterion was not replaced after inspecting results.

## 5. Uncertainty and decision

The paired bootstrap shares the same calendar-block draws for all three
methods within each season, then equally averages seasonal gains. There
are 5,000 draws with a fixed seed. Gain is baseline MAE minus candidate MAE;
positive values favor the candidate.

| Block length | Exploratory 95% gain interval versus persistence, mg/L | Versus ridge, mg/L |
| --- | ---: | ---: |
| 48 hours, primary | [-0.005432, -0.001667] | [0.000785, 0.001375] |
| 24 hours | [-0.005008, -0.001943] | [0.000779, 0.001425] |
| 72 hours | [-0.005191, -0.001722] | [0.000765, 0.001390] |

The candidate fails the declared requirement to beat both baselines without
a seasonal point-MAE loss. Ten percent was not an acceptance threshold.
These intervals are exploratory, conditional on the selected windows and
block assumptions. They are not forecast intervals, joint 95% guarantees
or evidence of environmental utility.

## 6. What this establishes

The rule applies to 533 past-flat histories; 99 have a changed future target.
It removes some unhelpful corrections, but flat history does not guarantee
a flat future. No threshold search or refitting followed these results.
These windows are now inspected evidence: another recipe needs separate
verification data.

In winter, 29.47% of pairs contain temperature outside the training range.
This is an extrapolation diagnostic, not an established cause of error.
The report retains RMSE, signed bias, p95 errors, daily results, large
errors and every twelve-sample history. No forecasts are negative or nonfinite.
No target falls below the illustrative 5 mg/L level, so this test does not
establish hypoxia alert performance.

These finalized retrospective records were revised in 2026. They do not
establish historical as-of-origin availability, prospective live skill,
basin-wide validity, pollutant attribution or field benefit. Persistence
remains the reference to beat before 24-hour or three-month experiments.
Transparent evidence supports community and youth decision rights; this
research result changes no governance, quorum, treasury or spending route.

## 7. Offline reproduction

From the repository root, with Python 3.10+ and Git:

```sh
python scripts/evaluate_stability.py verify --report docs/evidence/willamette-stability/evaluation.json.gz
python scripts/audit_stability_evidence.py .
python -m unittest discover -s scripts -p 'test_*.py' -q
node --test scripts/test-capture-stability.mjs
```

Full replay reproduces the report with maximum difference 0.0. A separate
arithmetic audit, written after evaluation, rebuilds all origins, features,
forecasts and scores from original JSON without importing experiment modules;
its observed difference is also 0.0, within 1e-9 tolerance. This is independent
code verification, not an independent measurement of the river. All 63 Python
and 5 Node tests pass, including future-label separation, tamper rejection
and exclusive capture reservation.

See the [JSON summary](evidence/willamette-stability/summary.json),
[full compressed report](evidence/willamette-stability/evaluation.json.gz)
and [executed companion notebook](notebooks/willamette-stability.ipynb).

References: [USGS continuous-data documentation](https://api.waterdata.usgs.gov/docs/ogcapi/migration/),
[monitoring station](https://waterdata.usgs.gov/monitoring-location/USGS-14211720/),
[time-series forecast evaluation](https://otexts.com/fpp3/tscv.html).
