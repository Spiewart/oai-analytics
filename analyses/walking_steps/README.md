# Walking from per-minute steps

Three questions, at 48 and 72 months: how much of the GT1M activity counts is walking (step `share`), how self-reported walking agrees with count-based and step-based device walking (steps `persons` and `pro_validity`), and how per-minute steps relate to per-minute counts (step `relation`). `oai report walking_steps` renders `report.pdf`, a two-page exploratory summary of both for the study team and the Northwestern accelerometry group.

## Part 1: share of the counts


What share of the OAI GT1M count-based measures (total wear counts, MV minutes, MV-bout minutes and light minutes) falls in walking minutes, at 48 and 72 months. A walking minute is a wear minute whose step count is at least a cadence threshold. Every share is reported at each threshold in `walking.cadences`.

The per-minute steps are **not public**. They are kept in `OAI_STEPS_DIR`, outside this repository and apart from the release (see `oai.steps`). This analysis writes aggregates only.

## Run

```bash
oai run walking_steps                                # headline at >= 40 steps/min
oai run walking_steps --variant primary_cadence_60   # headline at >= 60 steps/min
oai run walking_steps --variant any_step_day         # count people with one complete step day
```

The variants change only the headline sentence and the sample. Every threshold is always in the CSVs.

## Sample

Wear, valid days, intensity and bouts follow the release's rules (the `device.*` entries, as in `walking_validation`). Analysis days are a person's first valid days, chosen by wear, whose steps are complete. A day with any wear minute lacking steps is left out (`steps.day_rule`). A person needs `sample.min_step_days` such days.

## Outputs (`$OAI_RESULTS_DIR/walking_steps/<label>/`)

| File | Contents |
|---|---|
| `WALKING_SHARE.md` | Headline, sample flow, pooled shares by threshold, cadence bands |
| `flow.csv` | Per visit: persons in the files, valid persons, valid days, valid days dropped for incomplete steps, persons and days analysed, wear minutes |
| `walking_share.csv` | Per visit, threshold and measure: pooled share, per-person quartiles, and the number of persons with a non-zero denominator |
| `cadence_bands.csv` | Per visit and cadence band: minutes, counts, median counts per minute, share of minutes at MV, and share of minutes and of counts |
| `cadence_bands_person.csv` | Per visit and cadence band, across participants: mean (95% CI), median and quartiles of each person's share of wear minutes, share of counts, and share of the band's minutes at MV |

## Measures in `walking_share.csv`

| `measure` | Share |
|---|---|
| `wear_counts_in_walking` | Counts in walking minutes ÷ all wear counts |
| `mv_minutes_walking` | Walking MV minutes ÷ MV minutes (≥ `device.mv_cutpoint`) |
| `mv_bout_minutes_walking` | Walking minutes inside MV bouts ÷ MV-bout minutes |
| `light_minutes_walking` | Walking light minutes ÷ light minutes |
| `wear_minutes_walking` | Walking minutes ÷ wear minutes |
| `walking_minutes_reaching_mv` | Walking minutes at MV ÷ walking minutes |

## Part 2: self-reports against device walking

Self-reports: the 96-month walking-for-exercise item (coded as in walking_validation), and PASE item 2 at 48, 72 and 96 months as any walking and as walking on 3 or more days. Device walkers: the walking_validation rules (bout on at least 2 days a week; any bout; at least 150 bout minutes a week), each applied to count MV bouts and to step walking bouts at `reference.step_cadences` (the MV bout rule with steps in place of counts). Every definition in a comparison uses the same people. PASE at 48 and 72 months pairs with its own wave; the item and PASE at 96 months with the mean over valid waves (`pase.device_pairing`). The 96-month self-reports are also compared with an *either-wave* device walker (`device = "either valid wave"` in `pro_accuracy.csv`): a walker when any valid wave meets the definition.

| File | Contents |
|---|---|
| `device_flow.csv` | Persons, valid persons and valid persons with step measures per wave |
| `pro_flow.csv` | Per self-report: answers, and answers with device data |
| `pro_accuracy.csv` | Per self-report and device definition: 2 x 2, sensitivity and specificity (Wilson 95% CI), Youden's J, PPV, NPV, agreement, kappa |
| `pro_auc.csv` | AUC (stratified bootstrap 95% CI) of each continuous device measure for each yes/no self-report |
| `pro_spearman.csv` | Spearman's rho (Fisher-z 95% CI) of the PASE walking subscore with each continuous device measure |
| `PRO_VALIDITY.md` | Sensitivity / specificity by self-report and device definition |

Person-level device measures go to `$OAI_WORK_DIR/walking_steps/<label>/device.parquet`, never to results.

## Part 3: steps against counts within a minute

The step `relation` shows how per-minute steps relate to per-minute activity counts at 48 and 72 months (the Northwestern group's Q1). It uses the same analysis minutes as `share`, and the unit is the wear minute, pooled over participants.

The count bins are set by `relation.count_bin_edges`:
- sedentary: 0–99
- light, in four equal-width bins: 100–499, 500–999, 1000–1499 and 1500–2019
- moderate: 2020–5998
- vigorous: ≥ 5999

The step bands are `walking.band_edges`. The hexbin x-axis stops at the `relation.hex_x_quantile` of counts in each wave.

| File | Contents |
|---|---|
| `relation_hex.csv` | Per visit, the hexagon centres (`x` counts/min, `y` steps/min) and each hexagon's share of the wave's wear minutes |
| `relation_hex_meta.csv` | Per visit: the x-axis cut-off, the share of minutes beyond it, and the hexagon width and height |
| `relation_bins.csv` | Per visit and count bin: intensity, minutes (thousands), share of minutes, and the steps quartiles |
| `relation_bands.csv` | Per visit, count bin and step band: the share of the bin's minutes in the band |

## Caveats

- Steps are counted per minute, so a minute only partly spent walking shows a diluted cadence: 30 seconds at 100 steps/min records 50 steps. Higher thresholds therefore understate walking.
- A hip-worn GT1M records few steps during cycling, swimming or upper-body work. Those counts land in the "not walking" share at every threshold.
- Pooled shares are weighted towards the most active people. The per-person quartiles show the typical participant.
