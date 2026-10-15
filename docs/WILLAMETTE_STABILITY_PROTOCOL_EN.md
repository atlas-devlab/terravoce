# Willamette one-hour forecast: protocol for suppressing corrections after an unchanged oxygen history

[Versione italiana](WILLAMETTE_STABILITY_PROTOCOL.md)

**Update:** the historical definition below remains unchanged. Capture and
evaluation have now run; see the [results, verification and limitations](WILLAMETTE_STABILITY_RESULTS_EN.md).

Protocol defined on 14 October 2026, before collecting or evaluating the new
verification windows. This step defines the experiment and its checks. It does
not train a model, fetch new observations, or produce new forecast scores.

## What we want to test

The previous ridge forecast improved overall mean absolute error only slightly
and performed worse than persistence in three of four inspected seasonal
windows. The [error diagnosis](WILLAMETTE_HOURLY_DIAGNOSTICS_EN.md) also found
periods with twelve identical past dissolved-oxygen measurements. The ridge
can still predict a small change during these periods because its intercept,
clock, current oxygen, and temperature terms remain active.

Our single hypothesis is that removing this correction when the recorded oxygen
history is unchanged will improve one-hour forecasts on different, previously
unexamined windows. We will compare the guarded forecast with both persistence
and the same ridge forecast without the guard. Reusing exactly the same weights
isolates the effect of the rule from the effect of retraining.

The guard was proposed after inspecting the earlier results. Those earlier
windows are development evidence, not fresh validation of this hypothesis.

## One fixed rule, using only information up to the forecast origin

At forecast origin `t`, take twelve approved dissolved-oxygen values on the exact
30-minute grid, from `t - 5 h 30 min` through `t`, inclusive. Define:

```text
unchangedHistory = all twelve oxygen values are exactly equal

guardedForecast(t + 1 hour) =
    oxygen(t)                           if unchangedHistory
    oxygen(t) + frozenRidgeResidual(t)   otherwise
```

The first branch removes the **entire** residual correction: the intercept and
all eight feature contributions. The second branch retains the existing ridge
forecast in full. There are no intermediate multipliers, new thresholds,
parameter searches, smoothing, interpolation, or prediction clipping.

Equality applies to the published numeric oxygen values. It is not a fitted
tolerance and must not be replaced with a test of only the three oxygen-delta
features: readings can vary between the timestamps represented by those
features. Missing, invalid, or unapproved history does not count as unchanged.

For an illustrative example, suppose all twelve recorded values are `9.0 mg/L`
and the frozen ridge predicts `9.03 mg/L` one hour later. The guard predicts
`9.0 mg/L`. If the future recorded value is `9.0`, it helps; if the future value
is `9.1`, it can hurt. These numbers illustrate the rule and are not new USGS
results.

We therefore use the term **unchanged recorded oxygen history**, rather than
claiming the river or its ecosystem is stable. Identical rounded measurements
do not prove physical constancy, and past constancy does not guarantee the next
value. The future target cannot enter the guard or its selection.

## Frozen model and comparable cases

Station: **USGS-14211720**, on the Willamette. Target: dissolved oxygen exactly
one hour after the origin, in `mg/L`.

Reuse
[`docs/evidence/willamette-multiseason/frozen-model.json`](evidence/willamette-multiseason/frozen-model.json)
with raw-file SHA-256:

```text
0x72d7d14221c7b14c173dba59d69d2a1d36cbb27ee146378b9e046eea998762c9
```

This is the existing ridge model with `alpha = 100`, eight features, and centering
and scaling learned from the four 2024 training windows. The eight inputs are:
current oxygen; oxygen changes over 30 minutes, 2 hours, and 5 hours 30 minutes;
UTC clock sine and cosine; current water temperature; and its 2-hour change.
No new fit, rescaling, calibration, or weight selection is allowed in this test.

Use the same accepted origin/target pairs for all three forecasts. Preserve the
existing source identity, series, statistic, units, and quality checks. Only
approved, unqualified, finite measurements are accepted; oxygen must be
nonnegative. Preserve signed discharge rather than silently rejecting reverse
flow.

The existing alignment requires twelve consecutive measurements in oxygen,
temperature, and discharge, plus the exact future oxygen target. Discharge is
retained for comparable eligibility and diagnostic context, although it is not
one of the eight ridge inputs. This restricts the usable data and must be
reported; changing that restriction would be a separate experiment. No missing
measurement is interpolated or replaced.

## New verification windows fixed before capture

All boundaries below are UTC. Each interval lasts 28 days. They are historical
windows from 2025, chosen without inspecting their measurements. Using 2025
offers a reasonable prospect that the archive has approved observations, but
availability and approval status remain unverified at this step.

| Seasonal window | Start, inclusive | End, inclusive |
|---|---|---|
| Winter | `2025-02-01T00:00:00Z` | `2025-03-01T00:00:00Z` |
| Spring | `2025-05-01T00:00:00Z` | `2025-05-29T00:00:00Z` |
| Summer | `2025-06-01T00:00:00Z` | `2025-06-29T00:00:00Z` |
| Autumn | `2025-11-01T00:00:00Z` | `2025-11-29T00:00:00Z` |

Score origins from `start + 5 h 30 min` to `end - 1 hour`, inclusive, every
30 minutes. This yields **1,332 expected origins per window** before quality and
alignment exclusions. The history and target must remain within the same fixed
window; no adjacent observations are fetched to improve boundary coverage.

The repository's previously captured windows for this station are:

| Archive year | Previously inspected intervals, UTC |
|---|---|
| 2024 | 1–15 January, 1–15 April, 1–15 July, 1–15 October |
| 2025 | 15–29 January, 15–29 April, 15–29 July, 1–15 August, 1–15 October, 15–29 October |
| 2026 | 1–15 January |

The four proposed windows do not overlap these intervals, including their
inclusive endpoints. The separate autonomous-source capture on 1–2 July 2025
belongs to station `USGS-14182500`, not the forecasting station.

These are fresh verification data for this experiment, not newly occurring
events. The method is being defined in October 2026 and its recipe was informed
by other 2025 observations. We cannot claim that it was available at the 2025
origins or that finalized archival values match what a live service would have
seen then.

If a window is unavailable, insufficient, or not approved, retain it in the
report and declare the limitation. Do not substitute a different date range
after seeing values or scores.

## Three forecasts and one primary error measure

Evaluate on identical accepted cases:

1. **Persistence:** predict the current oxygen value one hour later.
2. **Plain frozen ridge:** retain the original full residual correction.
3. **Guarded frozen ridge:** apply the single unchanged-history rule above.

The primary measure is **mean absolute error (MAE), in mg/L**. Calculate it
separately for each seasonal window, then take the arithmetic mean of the four
seasonal MAEs. Each season receives the same weight even if accepted case
counts differ. This summary characterizes the selected windows, not an entire
year or every river condition.

Define a positive gain as `baseline MAE - guarded MAE`. Report the gain against
persistence and against plain ridge. Relative percentages are supplementary;
if a baseline MAE is zero, its relative gain is undefined rather than an
invented percentage.

Also report the unchanged-history subset: its count by season, how often the
next value actually changes, and guarded versus plain-ridge errors. The future
value is used only for scoring and retrospective diagnostics. An empty subset
in a season gives no evidence about the rule in that season. If there are no
unchanged-history cases across all four windows, report
`stability-rule-not-exercised`.

## Criteria declared before observing the new results

Call the result a credible exploratory improvement only if all the following
conditions hold:

- Every window has at least **1,000 accepted pairs** and at least **90% coverage**
  of its fixed 1,332-origin grid. These are practical completeness checks, not
  a statistical power calculation.
- The guarded forecast has lower equally weighted seasonal MAE than **both**
  persistence and plain ridge, beyond `1e-9 mg/L` numerical tolerance.
- In each seasonal window, the guarded point MAE is no worse than either
  baseline beyond the same numerical tolerance.
- The lower endpoint of the paired 95% block-bootstrap interval for the macro
  gain exceeds `1e-9 mg/L` against **both** baselines, using the main 48-hour
  blocks and the predeclared 24-hour and 72-hour sensitivity checks.
- The guard is exercised on at least one accepted case. All forecasts are
  finite and none of the guarded oxygen predictions is negative. Invalid
  outputs are reported; they are not removed to improve a score.

The bootstrap resamples calendar blocks within each season and keeps the three
forecasts and observed target paired. Recompute the four equally weighted
seasonal error differences in each replicate. Use **5,000 replicates** for each
block length, seed `20261014 + blockHours`, Python `Random` MT19937, and the
2.5th/97.5th percentiles with linear interpolation. Require at least four nonempty
blocks in each season for each block length; report the counts and any inability
to calculate a required interval. The 24- and 72-hour results are
conditions fixed in advance, not alternatives from which to select the most
favorable result.

Separate a missing-data verdict, an unexercised rule, a lack of overall gain,
an observed seasonal tradeoff, and an uncertain gain. A positive point estimate
with an interval including zero remains inconclusive. An observed seasonal
point-MAE check does not establish statistical noninferiority for every season.

These intervals are exploratory, conditional on the selected windows and the
block-dependence assumptions. The separate 95% intervals do not provide a joint
95% coverage statement for all comparisons and block lengths. The numerical
tolerance is an arithmetic allowance, not an ecological benefit threshold.

Report RMSE, signed bias, 95th-percentile absolute error, large errors, daily
results, feature-range extrapolation, and coverage/exclusion counts as well.
Keep abrupt changes and large misses in the primary score when they pass the
predeclared data-quality checks. There is no required **10%** gain and no
ecological utility threshold established by this experiment.

## Freeze order and what this implementation step contains

Before acquiring the four new windows:

1. Commit the protocol, this explanation and its Italian counterpart, the
   verification checks, and the exact frozen-model reference.
2. Freeze the forecast and evaluation implementation before new target values
   are inspected. The future capture manifest must bind the committed protocol
   and the frozen-model file hash, together with source URLs, raw-body hashes,
   and capture times.
3. Capture the declared windows and evaluate the fixed rule once. Record
   failures and exclusions without changing the recipe or dates. Any revision
   after looking at results is a new development step and needs distinct
   verification data.

The check command prepared for this protocol step is:

```powershell
python scripts/stability_protocol.py
```

Its scope is to verify the definition, window non-overlap, and frozen weights.
It does not fit, capture, or evaluate a model. A new-data capture command and an
evaluation runner are **not implemented in this step**. A passing protocol
check therefore does not demonstrate forecast improvement.

## Connection to Virdacora's mission

This remains a bounded research experiment on one station and one-hour oxygen
forecasts. It does not establish field reliability, causal pollution effects,
ecological improvement, or forecasts at 24 hours or three months. It does not
change the LLM, Oracle operational routing, blockchain contracts, voting, or
treasury decisions.

The contribution is a testable forecasting rule with auditable provenance and
explicit limits. Environmental evidence must remain reviewable, and the
communities and young people affected retain decision rights. A favorable
forecast score cannot automatically authorize intervention or spending.
