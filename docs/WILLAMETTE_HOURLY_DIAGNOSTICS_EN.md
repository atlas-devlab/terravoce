# Diagnosing the frozen Willamette one-hour forecast

[Versione italiana](WILLAMETTE_HOURLY_DIAGNOSTICS.md).

This increment explains where the existing dissolved-oxygen forecast fails. It
does not train another model, introduce a new prediction rule or establish new
forecast skill. All **2,591 scored pairs** and the original predictions remain
in the analysis. No difficult target is removed or corrected to improve a score.

The work preserves Virdacora's original purpose: traceable environmental
evidence, distributed coordination and decision rights for affected communities
and young people. It changes neither the operational Oracle nor civic voting,
quorum, escrow or spending permissions. No funding is released.

## The starting result remains unchanged

The [four-season experiment](WILLAMETTE_MULTISEASON_EXPERIMENT.md) fitted one
ridge recipe on 2,559 complete pairs from four 2024 windows. It froze the weights
before acquiring four separate 2025 test windows. Its frozen artifacts are
preserved from repository base
`a1bd590f9b5d9dc77d0a5ee435ae509d7072d2d6`; this increment adds a separate
diagnostic protocol and report.

| 2025 window | Pairs | Persistence MAE mg/L | Frozen ridge MAE mg/L |
| --- | ---: | ---: | ---: |
| Winter, January 15–29 | 637 | 0.012873 | 0.024278 |
| Spring, April 15–29 | 647 | 0.027666 | 0.037157 |
| Summer, July 15–29 | 647 | 0.334776 | 0.308014 |
| Autumn, October 15–29 | 660 | 0.068182 | 0.070332 |
| Equal-weight mean of seasonal MAEs | 2,591 total | 0.110874 | 0.109945 |

The mean improvement is **0.837839%**, or **0.000928947 mg/L**, with observed
losses in three seasons. The original decision remains
`observed-seasonal-tradeoff`. The exploratory 48-hour block-bootstrap interval
for the MAE gain is **[-0.003821; +0.005414] mg/L**. The 24- and 72-hour
sensitivity intervals also include zero. The diagnostic report reproduces the
existing evaluation, rather than treating these windows as a new final test.

## Two meanings of "unchanged" must be kept separate

`byTarget` divides examples according to whether the **observed future target**
equals the last oxygen measurement. This is a retrospective label. At forecast
origin we cannot know which group an example will enter. The report explicitly
sets `targetUsesFutureInformation: true` for this diagnostic grouping; that
future information does not enter the frozen prediction.

`byHistory` instead examines **all twelve oxygen records at or before the
origin**, at 30-minute spacing. `flat` means all twelve archived values are
exactly equal. The twelve samples cover 5.5 hours. Checking only the three oxygen
deltas used by the model would miss changes between their selected timestamps.

The report also crosses both labels, producing `flatUnchanged`, `flatChanged`,
`changingUnchanged` and `changingChanged`. Every partition retains every scored
pair; its weighted group MAEs reconstruct the corresponding seasonal MAE.
Empty groups have `null` metrics, rather than a fabricated error of zero.

| Season | Future target unchanged | Twelve-sample history flat | Flat history followed by a changed target |
| --- | ---: | ---: | ---: |
| Winter | 555 / 637 | 371 / 637 | 19 / 371 |
| Spring | 482 / 647 | 124 / 647 | 26 / 124 |
| Summer | 149 / 647 | 0 / 647 | No flat-history examples |
| Autumn | 354 / 660 | 30 / 660 | 11 / 30 |

In winter, persistence has zero error on the 555 unchanged-target examples,
while the ridge corrections introduce MAE **0.015532 mg/L**. This explains one
mechanism of the observed error. It does not reveal the physical reason why the
published measurements were equal.

The past-only group is useful for forming a hypothesis, but it gives no
guarantee: **19 of 371 winter examples with a flat history still change one hour
later**. On all 371 flat-history winter examples, persistence MAE is
**0.005121 mg/L** and ridge MAE is **0.017504 mg/L**. In summer there are no
flat-history examples, so these data provide no summer estimate for that group.
Equality of rounded or recorded values does not establish physical constancy.

## Reconstructing the correction without claiming causation

For each pair, the module reconstructs the saved prediction as:

```text
prediction = current oxygen + residual intercept
             + sum(coefficient[j] * (input[j] - training mean[j]) / training scale[j])
```

There are exactly eight inputs: current oxygen; oxygen changes over 30 minutes,
2 hours and 5.5 hours; UTC clock sine and cosine; current temperature; and its
2-hour change. Training means, scales, coefficients and intercept remain frozen.

The seasonal `meanAbsoluteContributionsMgL` records the size of these additive
terms in this particular linear model. Terms can cancel, and inputs can be
correlated. These numbers are **not causal effects or a validated feature
importance ranking**. A clock or temperature term can produce a nonzero
correction even when the twelve oxygen values are flat.

Discharge is present in the source archive and was required for complete
three-series alignment in the original experiment. **It is not one of this
ridge model's eight inputs.** Wind, clouds, humidity, pollutants and human
activities are also absent. The module does not infer their effects.

## Examining two low targets without inventing an alert system

The illustrative filter `actual < 5 mg/L` selects two examples for context:

| Origin UTC | Target UTC | Last oxygen mg/L | Recorded target mg/L | Frozen forecast mg/L |
| --- | --- | ---: | ---: | ---: |
| 2025-07-18 05:00 | 2025-07-18 06:00 | 8.5 | 3.5 | 8.535660 |
| 2025-07-20 06:30 | 2025-07-20 07:30 | 8.3 | 3.8 | 8.293159 |

Their target record IDs are respectively
`c80b70af-704b-4edc-8636-d6cf49410efc` and
`fba3b442-adce-4f3e-86ba-090b56f550f9`. Both have publisher status `Approved`,
no qualifier and `lastModified` of
`2026-04-29T21:15:15.518161+00:00` in the retained archive. Modification dates
postdate the 2025 forecast origins. These are finalized retrospective values;
the archive does not establish which values or approval states a live service
could have obtained at those historical instants.

Each example includes oxygen, temperature and discharge every 30 minutes, from
330 minutes before the origin to 180 minutes after the target. This means the
last contextual timestamp is 240 minutes after the origin. Missing accepted
records remain `null`; they are not interpolated or replaced with zero.

**Every timestamp after the origin is marked `future-diagnostic-only`.** This
includes the observation at origin +30 minutes, before the one-hour target.
For example, the first case's 8.1 mg/L at 05:30 and the second case's 7.2 mg/L
at 07:00 are visible only as retrospective context, not as forecast inputs.

Discharge `value` is converted to **m³/s** using the original conversion factor
`0.028316846592`; `sourceValue` preserves the publisher's string in **ft³/s**.
`sourceUnit` and `valueUnit` make this distinction explicit. Signed flow is
preserved: the first case has approximately -515.367 m³/s at origin and
+80.137 m³/s at target. A flow reversal near an oxygen drop is a temporal
association, not proof of a physical cause. The three series still come from
the same USGS source environment, not independent field instruments verified
by this experiment.

The 5 mg/L filter is not a calibrated local ecological or legal threshold. Two
selected targets do not validate alerts, identify pollution, establish event
duration or demonstrate ecological harm or recovery. Neither publisher
approval nor reproducible hashes prove physical truth.

## Reproduce offline

The [diagnostic protocol](datasets/willamette-hourly-diagnostics/protocol.json)
pins the exact source inputs with SHA-256 hashes. The
[retained report](evidence/willamette-hourly-diagnostics/report.json) is derived
from those inputs. Changed bytes are rejected before replay, including a
modified model or source artifact. This diagnostic declaration follows
inspection of the 2025 results; it is not preregistration of an unseen test.

From the repository root, verify the retained report and run its focused tests:

```sh
python scripts/forecast_diagnostics.py verify
python -m unittest discover -s scripts -p test_forecast_diagnostics.py
```

To create and verify a separate local output without replacing the retained
report:

```sh
python scripts/forecast_diagnostics.py run --output outputs/willamette-hourly-diagnostics/report.json
python scripts/forecast_diagnostics.py verify --output outputs/willamette-hourly-diagnostics/report.json
```

`run` uses exclusive creation and refuses an existing destination. `verify`
recomputes the diagnosis without fitting and compares it with the selected
report within the existing numerical tolerance. The root pnpm aliases are:

```sh
pnpm forecast:diagnose
pnpm forecast:diagnose:verify
```

The first creates the separate `outputs/willamette-hourly-diagnostics/report.json`
and refuses to overwrite it. The second verifies the **retained report in
`docs/evidence`**. To verify the separate local output, use the Python command
with `--output` shown above. The Python commands use only the standard library.
No fresh environmental request, LLM, wallet or Docker cluster is part of the
diagnosis; the pnpm aliases also require pnpm to be available.

The focused suite contains eight tests covering complete-history versus target
grouping, reconstruction of counts and errors, empty groups, invalid histories,
the eight additive terms, future-only context with missing records and negative
flow, blocked training calls, unchanged predictions when only future values
change, and refusal of altered source inputs. These are software checks; they
are not independent environmental validation.

## One next experiment, declared before fitting

The diagnosis suggests one bounded candidate for a later experiment: shrink
the ridge residual correction toward persistence, or fall back to persistence,
using only a declared rule based on the complete past history. For example,
a past-flatness rule must be defined before model selection and cannot use the
future-target label. This increment does not fit, tune or evaluate that
candidate as a new forecast model.

The next protocol must specify the single candidate, temporal training and
development split, treatment of overlapping histories and one-hour targets,
seasonal checks and a fresh temporal holdout before final evaluation. The four
2025 windows already inspected can serve as diagnosis or development data;
they cannot become an untouched final test for a variant chosen after seeing
them. Keep persistence as the main comparator on the same accepted pairs and
retain missing periods and difficult events. Advancing to 24 hours or three
months requires its own evidence, rather than extending this result by claim.

Methodological reading:
[time-series cross-validation](https://otexts.com/fpp3/toolbox.html#time-series-cross-validation).
Publisher documentation:
[USGS OGC API](https://api.waterdata.usgs.gov/docs/ogcapi/).
