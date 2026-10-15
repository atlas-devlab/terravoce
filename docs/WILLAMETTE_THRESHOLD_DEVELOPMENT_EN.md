# Willamette one-hour forecasts: developing the correction filter

[Spiegazione italiana](WILLAMETTE_THRESHOLD_DEVELOPMENT.md).

**First we specify how to choose a threshold; then we will calculate results
on the data already studied. No threshold has been selected or shown better.**
MAE, the mean absolute forecast error in mg/L, remains the primary criterion.

## 1. A simple example

The latest dissolved-oxygen reading is 8.00 mg/L. The regression proposes 8.04.
With an illustrative threshold of 0.05 mg/L, we discard the 0.04 correction
and predict 8.00. If it proposes 8.30, we keep the 8.30 prediction.
If the future observation were 8.04, discarding the first correction would
be harmful: the filter can lose. We will check this without assuming that
every small correction is unnecessary.

The rule uses only the latest reading and the regression prediction:

```text
d = ridge_prediction - latest_reading
if abs(d) <= threshold: filtered_prediction = latest_reading
otherwise: filtered_prediction = ridge_prediction
```

The future observation is used to score errors, never to decide whether to
correct. Ridge weights remain frozen. The earlier twelve-identical-readings
fallback remains a comparator; it is not implicitly stacked with this filter.

## 2. Five thresholds and a simple alternative

The declared grid is **0; 0.025; 0.05; 0.10; 0.20 mg/L**.
A zero threshold produces the same prediction as the full ridge.
We separately include persistence: always repeating the latest reading.
If no filter provides an advantage, persistence remains the choice.

These are five engineering candidates, not universal scientific thresholds,
sensor accuracies or ecological limits. The value 0.05 already appeared in
the [diagnosis](WILLAMETTE_ERROR_MECHANISMS_EN.md): this search follows inspection
of the results and will be described as exploratory development.
We will choose one common threshold for all four windows, without tuning it
separately for each season.

## 3. Separating examples without mixing past and future

We use the four archived 28-day windows from 2025 at station USGS-14211720.
They sample seasonal periods; they do not cover four complete seasons.
For each window, the boundary is `start + 14 days`, in UTC.

- **Selection:** the one-hour target must strictly precede the boundary.
- **Internal check:** the first of the twelve historical readings must be
  at or after the boundary. History spans five hours and thirty minutes.
- **Boundary interval:** origins meeting neither condition are excluded.

Preflight checks that the last selection target precedes the first historical
reading of the check, and that their forecast origins are at least seven
hours apart. It reports dates, counts and exclusions for each window.
Both groups must contain data; a positive count does not demonstrate
adequate statistical power.
This prevents overlapping evidence at the boundary, but does not make nearby
river observations independent. Missing observations are not interpolated.

**Both halves have already been inspected.** The check is a temporal diagnostic
within development, not a new blind test. Common-threshold selection also
uses a November window while some checks are in February: this is not a
globally prospective simulation. A test on unused data requires a later
stage with its calendar and implementation fixed before examining targets.

## 4. The selection rule, before scoring real candidates

We will calculate each candidate's MAE on the same selection origins.
The primary MAE will average the four window MAEs, weighting windows equally.
A candidate will be eligible only if it:

1. improves on persistence's primary MAE by more than `1e-9 mg/L`;
2. worsens no individual window MAE by more than `1e-9 mg/L`;
3. produces zero invalid predictions, including nonfinite or negative values.

Among eligible candidates, we choose the lowest primary MAE. For ties within
`1e-9 mg/L`, we prefer fewer applied corrections; if still tied, the larger
threshold. A tie with persistence favors persistence.
If no candidate is eligible, we retain persistence.
The `1e-9` tolerance handles arithmetic: it does not express environmental
usefulness, statistical uncertainty or a demonstrated practical minimum gain.

On the internal check, we will examine only the selected threshold, compared
with persistence and previous methods on identical origins. We require the
same average gain, no window deterioration and zero invalid predictions.
If it fails, we record failure without looking for another threshold there.
RMSE and large errors will be descriptive, without replacing primary MAE.

## 5. What is being prepared now

The [protocol](datasets/willamette-threshold-development/protocol.json) and
[script](../scripts/threshold_development.py) make the rule, temporal split
and criteria reviewable. Synthetic tests cover boundary cases.
Preflight may read the existing archive to verify its integrity and temporal
partition; it does not calculate real-data errors for the five candidates.
The selector is tested on invented summaries; the runner that calculates
real-data MAEs has not been implemented or run. This stage selects no
threshold, retrains nothing, acquires no new targets and does not define
the calendar for the next one-hour test. From the repository root:

```sh
python scripts/threshold_development.py preflight
python -m unittest discover -s scripts -p 'test_threshold_development.py'
```

The principle of preserving time order is explained in
[Forecasting: Principles and Practice, §5.10](https://otexts.com/fpp3/toolbox.html#time-series-cross-validation).
Our grid, half-window split and seven-hour separation are declared engineering
choices: they are not a standard prescribed by the book, and this single
internal check is not equivalent to rolling-origin cross-validation.

Virdacora preserves verifiable, understandable environmental evidence useful
to communities. An experimental numerical filter does not certify physical
sensor truth or activate the Oracle, governance, interventions or spending.
