# How much of the activity counts is walking

What share of the OAI GT1M count-based measures (total wear counts, MV minutes, MV-bout minutes and light minutes) falls in walking minutes, at 48 and 72 months. A walking minute is a wear minute whose step count is at least a cadence threshold. Every share is reported at each threshold in `walking.cadences`.

The per-minute steps are **not public**. They are kept in `OAI_STEPS_DIR`, outside this repository and apart from the release (see `oai.steps`). This analysis writes aggregates only.

## Run

```bash
oai run walking_counts                                # headline at >= 40 steps/min
oai run walking_counts --variant primary_cadence_60   # headline at >= 60 steps/min
oai run walking_counts --variant any_step_day         # count people with one complete step day
```

The variants change only the headline sentence and the sample. Every threshold is always in the CSVs.

## Sample

Wear, valid days, intensity and bouts follow the release's rules (the `device.*` entries, as in `walking_validation`). Analysis days are a person's first valid days, chosen by wear, whose steps are complete. A day with any wear minute lacking steps is left out (`steps.day_rule`). A person needs `sample.min_step_days` such days.

## Outputs (`$OAI_RESULTS_DIR/walking_counts/<label>/`)

| File | Contents |
|---|---|
| `WALKING_SHARE.md` | Headline, sample flow, pooled shares by threshold, cadence bands |
| `flow.csv` | Per visit: persons in the files, valid persons, valid days, valid days dropped for incomplete steps, persons and days analysed, wear minutes |
| `walking_share.csv` | Per visit, threshold and measure: pooled share, per-person quartiles, and the number of persons with a non-zero denominator |
| `cadence_bands.csv` | Per visit and cadence band: minutes, counts, median counts per minute, share of minutes at MV, and share of minutes and of counts |

## Measures in `walking_share.csv`

| `measure` | Share |
|---|---|
| `wear_counts_in_walking` | Counts in walking minutes ÷ all wear counts |
| `mv_minutes_walking` | Walking MV minutes ÷ MV minutes (≥ `device.mv_cutpoint`) |
| `mv_bout_minutes_walking` | Walking minutes inside MV bouts ÷ MV-bout minutes |
| `light_minutes_walking` | Walking light minutes ÷ light minutes |
| `wear_minutes_walking` | Walking minutes ÷ wear minutes |
| `walking_minutes_reaching_mv` | Walking minutes at MV ÷ walking minutes |

## Caveats

- Steps are counted per minute, so a minute only partly spent walking shows a diluted cadence: 30 seconds at 100 steps/min records 50 steps. Higher thresholds therefore understate walking.
- A hip-worn GT1M records few steps during cycling, swimming or upper-body work. Those counts land in the "not walking" share at every threshold.
- Pooled shares are weighted towards the most active people. The per-person quartiles show the typical participant.
