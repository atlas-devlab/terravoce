# Willamette one hour ahead: where regression helps and where it fails

[Spiegazione in italiano](WILLAMETTE_ERROR_MECHANISMS.md).

**Regression usefully corrects some changes, but introduces too much error
when the recorded value stays unchanged.** In winter, spring and autumn,
that cost exceeds the benefit. In summer, the benefit prevails. This is a
decomposition of observed errors, not a physical explanation of river
behaviour.

This document accompanies the [diagnostic report](evidence/willamette-error-mechanisms/diagnostic.json)
and [notebook](notebooks/willamette-error-mechanisms.ipynb). It builds on the
[completed test](WILLAMETTE_STABILITY_RESULTS_EN.md): USGS station 14211720,
one-hour dissolved oxygen forecasts, and 5,213 pairs from 2025. The question,
data and frozen model remain the same. This is neither new training nor
a new independent evaluation.

## 1. Separate what is known before and after the forecast

At the forecast origin, we know the earlier measurements and the correction
proposed by regression. The target, one hour later, is used for evaluation.
Only after observing it can we divide the cases into:

- recorded value unchanged from the latest measurement;
- recorded value rising;
- recorded value falling.

**These future-defined groups are diagnostic categories, not an operational
selector.** A rule cannot choose persistence by already knowing that the
target will be unchanged. Intermediate measurements after the origin are
also future information and cannot become inputs to that forecast.

The comparison uses the same timestamps for persistence, full ridge and
ridge with the previously tested fallback: when all twelve past oxygen
measurements are equal, the fallback cancels the correction; otherwise it
uses ridge. In the following tables, “candidate” means this previously
tested rule, not a new variant.

## 2. The balance between useful and unnecessary corrections

The table compares the candidate with the unchanged latest measurement.
MAE is mean absolute error, measured in mg/L; lower is better.

| Window | Target relative to latest measurement | Pairs | Persistence MAE | Candidate MAE |
| --- | --- | ---: | ---: | ---: |
| Winter | Unchanged | 1,058 | 0.000000 | 0.011724 |
| Winter | Rising | 106 | 0.100000 | 0.081257 |
| Winter | Falling | 112 | 0.100000 | 0.092451 |
| Spring | Unchanged | 645 | 0.000000 | 0.026336 |
| Spring | Rising | 332 | 0.163855 | 0.140814 |
| Spring | Falling | 343 | 0.162099 | 0.159467 |
| Summer | Unchanged | 346 | 0.000000 | 0.045556 |
| Summer | Rising | 477 | 0.278197 | 0.241904 |
| Summer | Falling | 475 | 0.271789 | 0.252931 |
| Autumn | Unchanged | 747 | 0.000000 | 0.024384 |
| Autumn | Rising | 285 | 0.125263 | 0.099033 |
| Autumn | Falling | 287 | 0.123693 | 0.123006 |

In all four windows, the candidate has lower MAE than persistence on both
the rising and falling groups. This does not mean it anticipates every rise
or fall: these are group averages. In the unchanged groups, any nonzero
correction introduces error because the reference is already exact against
the published value.

To reconstruct seasonal MAE, multiply each group MAE by its fraction of
cases, then sum the three parts. Do not average three differently sized
groups equally. In winter, for example, the 1,058 unchanged cases represent
82.92% of 1,276 cases: their cost exceeds the benefit in the 218 changing
cases. In summer, a much larger share of targets changes, reversing the
balance.

The four seasonal MAEs retain equal weight in the primary result. We do
not replace this with a more favourable pooled average. The original result
remains unchanged:

| Method | Mean of the four seasonal MAEs, mg/L |
| --- | ---: |
| Unchanged latest measurement | 0.089023 |
| Full ridge | 0.093555 |
| Ridge with fallback | 0.092470 |

“Unchanged” describes the precision of published values. It does not prove
that physical oxygen concentration was exactly constant or that smaller
changes were absent. This analysis has not established instrumental
accuracy or a resolution scientifically justified as a model threshold.

## 3. Why MAE and RMSE give different signals

MAE counts errors in proportion to their size. MSE squares errors; RMSE
is the square root of MSE, returning to mg/L. RMSE therefore gives larger
errors more weight.

In each of the four windows, the candidate has lower RMSE than persistence,
while MAE is worse in three windows. This can happen when some benefits on
large errors outweigh many harmful small corrections in squared-error
scoring. The report checks this arithmetic balance; it does not establish
alerting ability or ecological usefulness.

| Target group | Contribution to MAE advantage, mg/L | Contribution to MSE advantage, (mg/L)² |
| --- | ---: | ---: |
| Unchanged | −0.012136 | −0.000665 |
| Rising | +0.006589 | +0.007002 |
| Falling | +0.002099 | +0.000332 |
| **Sum** | **−0.003447** | **+0.006670** |

Advantage means persistence error minus candidate error: positive is a
benefit. Each contribution retains the full denominator of its season,
followed by equal weighting of all four seasons. Values are rounded; the
JSON retains full precision. Benefits on rising targets dominate the
squared-error balance in this diagnosis; this does not mean all large
errors or ecological risks were reduced.

MSE can be decomposed by adding group contributions weighted by their
number of cases. Group RMSEs cannot be added to reconstruct overall RMSE.
The mean of seasonal RMSEs and the square root of mean seasonal MSE are
also different quantities and must be named correctly.

MAE remains the previously agreed primary criterion. We do not promote
the test by choosing the most favourable metric after seeing the results.
We can jointly choose a different objective for a future experiment, but
must declare it beforehand and justify it against community use. An
ecological threshold, a missed-alert cost and alerting performance have
not yet been validated.

## 4. Two examples at opposite ends of the comparison

These examples are selected retrospectively as the largest absolute-error
benefit and harm of the candidate against persistence among all 5,213 pairs.
They are diagnostic examples, not events selected by an ecological
threshold. All times are UTC.

| Origin → target | Latest measurement | Recorded target | Candidate prediction | Persistence → candidate absolute error |
| --- | ---: | ---: | ---: | ---: |
| 2 June 2025, 06:00 → 07:00 | 7.0 | 9.5 | 7.768627 | 2.500000 → 1.731373 |
| 3 June 2025, 07:30 → 08:30 | 9.3 | 9.6 | 8.825073 | 0.300000 → 0.774927 |

Concentrations, predictions and absolute errors are in mg/L. In the first
case, the model predicts a rise and the target rises substantially: absolute
error falls by 0.768627 mg/L, but the prediction remains far from the
target. In the second, the model predicts a fall while the recorded target
rises: absolute error increases by 0.474927 mg/L.

The report also reconstructs the sum of numerical regression contributions.
In the harmful case, the preceding two-hour oxygen change contributes about
−0.346651 mg/L and the last half-hour change about −0.108046 mg/L to the
final correction. In the helpful case, these two contributions are about
+0.470238 and +0.303107 mg/L. This explains the prediction's calculation;
it does not establish those variables as physical causes of future oxygen
or show that the model has identified a river mechanism.

The 07:00 target in the first example is not an input to the forecast reconstructed
with an origin of 06:00. This is a retrospective reconstruction, not a forecast
actually issued in 2025. The same temporal boundary applies to the second example. These
observations do not establish a physical cause, episode duration, ecosystem impact or absence
of measurement problems.

## 5. Why “always use half the correction” is insufficient here

We can check this idea without retraining. Let `r` be the recorded change
over the hour and `d` the correction already proposed by the model. A
constant weight `lambda` produces:

```text
prediction(lambda) = latest measurement + lambda × d
absolute error(lambda) = |r − lambda × d|
lambda = 0: persistence; lambda = 1: the full method being considered
```

The mean of these errors is convex in the weight. Its right-hand derivative
at zero is `|d|` when `r = 0`, and `−sign(r) × d` otherwise. We first average
within each season and then give the four seasons equal weight, as in the
original test.

| Correction being attenuated | Derivative of mean MAE at zero weight |
| --- | ---: |
| Full ridge, without fallback | +0.003327639 mg/L per unit weight |
| Ridge with fallback | +0.002243274 mg/L per unit weight |

Both derivatives are positive. By convexity, on these four windows,
**no positive constant weight between zero and one can beat persistence
on mean seasonal MAE**. This conclusion concerns this family of forecasts,
the same data, the same reference and this metric. It is not a general
impossibility result for river forecasting or improvement on future data.
Nor does it rule out conditional rules based on information already
available at the origin.

This check does not search for a favourable weight, retrain regression
or constitute a new independent evaluation.

## 6. One hypothesis to discuss for the next test

A simple candidate is to avoid intervening when the model's correction
is very small:

```text
if |full correction| <= threshold: prediction = latest measurement
otherwise: prediction = full ridge prediction
```

Correction magnitude can be computed at the origin without reading the
target. The rule does not know whether the river will remain unchanged.
A small correction can help, and a large correction can be wrong: the
hypothesis may fail. We have not chosen a threshold, measured this
variant's performance or frozen a new protocol.

The diagnosis offers a clue: splitting cases retrospectively by full-ridge
correction shows that small interventions concentrate part of the cost.
The descriptive 0.05 mg/L cut below was introduced after inspecting the
data; it is not a selected or validated threshold for a new forecast.

| Absolute full-ridge correction | Pairs | Contribution to candidate MAE advantage over persistence, mg/L |
| --- | ---: | ---: |
| At most 0.05 mg/L | 4,140 | −0.006605 |
| Above 0.05 mg/L | 1,073 | +0.003158 |

These are contributions to the seasonal mean, so they add: the net is
about −0.003447 mg/L, consistent with the failed test. They are not the
conditional MAEs of the two groups. Within the above-0.05 mg/L group,
the winter advantage remains negative: this cut does not automatically
meet the requirement of avoiding deterioration in every season.

The threshold would be a statistical parameter, not sensor accuracy or an
ecological limit. We do not automatically set it to 0.1 mg/L. We do not
simultaneously add discharge, weather, an LLM or another horizon; doing so
would prevent us from isolating the effect of this change.

If we agree on this direction, before acquiring new evaluation data we
will need to:

1. Treat the already observed windows as development only, with a small
   threshold search and internal temporal splits declared before selection.
   Record unsuccessful attempts too.
2. Freeze one candidate, existing weights, a calendar of later, previously
   uninspected periods, checks against already inspected periods, quality
   rules and evaluation code before
   acquiring new targets. Report an insufficient window rather than
   replacing it after seeing the result.
3. Compare persistence, full ridge, the tested fallback and the new candidate
   on identical timestamps. Retain denominators, gaps, signed discharge,
   exploratory block intervals and equal seasonal weighting.
4. Agree on success beforehand: primary MAE, no seasonal deterioration,
   uncertainty of the advantage and secondary checks on large errors.
   Exact requirements, including any practical environmental usefulness,
   must be declared before evaluation.
5. Separate retrospective evaluation on revised archives from an online
   test. The latter requires captures and predictions retained before
   the target, including evidence of which inputs were then available.
   A final archive alone does not reconstruct that historical availability.

**Decision to discuss: shall we develop this single rule for small
corrections, retaining MAE as the primary objective and the requirement
not to worsen any of the four seasons?**

## 7. What this means for Virdacora

Virdacora should make environmental evidence verifiable and understandable
to communities. Publishing a failed test, distinguishing average benefit
from large-error risk and retaining original measurements are part of that
work. This diagnosis does not attribute responsibility for pollution or
establish benefits in the field. Hashes and provenance make archives
auditable; they do not, by themselves, certify a sensor's physical truth.

We do not change the operational Oracle, quorum, community and youth voting
or treasury. We do not automatically authorize interventions or expenditure.
We remain with one-hour oxygen forecasting before studying 24 hours or
three months.

## 8. Reproduce the diagnosis

From the repository root, with Python 3.10+ and Git, without network access:

```sh
python scripts/diagnose_stability_errors.py verify
python -m unittest discover -s scripts -p 'test_*.py'
```

The verifier checks pinned hashes, replays the completed evaluation from the
archives and rebuilds the decomposition. It rejects changed counts, discrete
evidence or numerical differences beyond the arithmetic tolerance of 1e-9.
That tolerance is neither a sensor threshold nor a forecasting threshold.
