# crepitus_activity

Crepitus and device-measured activity at 48 and 72 months, in both directions.

**Direction A:** do crepitus at a visit, or its change between visits, predict GT1M steps/day and MV and light minutes/day, or their change from 48 to 72 months?

**Direction B:** do activity at 48 months, and its change to 72 months, predict:
- KOOS S2 crepitus at 72 and 96 months;
- new exam crepitus at 120 months?

- **Spec:** [docs/superpowers/specs/2026-11-12-crepitus-activity-design.md](../../docs/superpowers/specs/2026-11-12-crepitus-activity-design.md)
- **Plan:** [docs/superpowers/plans/2026-11-12-crepitus-activity.md](../../docs/superpowers/plans/2026-11-12-crepitus-activity.md)
- **Assumptions:** [ASSUMPTIONS.md](ASSUMPTIONS.md)

The per-minute steps come from Northwestern (`OAI_STEPS_DIR`, never in the repo). Their terms: Jing is a co-author on publications that use them, and the PARR group offers input.

```bash
uv run oai run crepitus_activity
```

## Results

Run 2026-11-12 on the full release with the Northwestern steps (`uv run oai run crepitus_activity`).
- **Estimates in direction A:** differences in steps/day per 1,000 and in MV or light minutes/day per 10.
- **Estimates in direction B:** odds ratios per 1,000 steps/day or per 10 minutes/day.
- **Models:**
  - Model 1: age, sex, BMI and wear hours.
  - Model 2: Model 1 plus the higher KL grade and the worse knee's WOMAC pain at 48 months.
- **Crepitus** is the number of knees with it (0, 1 or 2).

### Flow

- **Device:** 1,928 people with valid wear at 48 months, 1,343 at both waves.
- **Crepitus counts at 48 months** (both knees known): exam 1,812; S2 1,920.
- **S2 at 96 months** among people valid at both waves: 1,311.
- **Exam at 120 months:** 931 knees free of exam crepitus at 48 months were examined again; 184 had new crepitus.

### Unadjusted

Mean steps/day at 48 months by exam crepitus count:

| Exam crepitus knees | People | Mean steps/day |
|---|---|---|
| 0 | 641 | 6,631 |
| 1 | 344 | 6,062 |
| 2 | 826 | 5,957 |

By S2 count (0, 1, 2 knees) it is 6,045, 6,148 and 6,367 (879, 468 and 571 people). See `descriptives.csv` for every measure and wave.

### Direction A: crepitus → activity (steps/day, thousands)

| Model term | Model 1 | Model 2 |
|---|---|---|
| A1, exam per crepitus knee, 48 months | −0.03 (−0.16 to 0.10) | 0.03 (−0.10 to 0.17) |
| A1, S2 per crepitus knee, 48 months | −0.07 (−0.21 to 0.06) | −0.02 (−0.16 to 0.12) |
| A1, S2 per crepitus knee, 72 months | −0.06 (−0.22 to 0.10) | −0.04 (−0.21 to 0.13) |
| A2, exam at 48 → steps at 72 (adjusting for steps at 48) | 0.07 (−0.04 to 0.17) | 0.06 (−0.05 to 0.18) |
| A2, S2 at 48 → steps at 72 | −0.10 (−0.21 to 0.01) | −0.09 (−0.20 to 0.03) |
| A3, S2 change 48→72 (concurrent) | 0.02 (−0.11 to 0.14) | −0.02 (−0.15 to 0.11) |
| A3, S2 change 36→48 (preceding) | −0.13 (−0.26 to 0.00) | −0.11 (−0.25 to 0.03) |
| A3, exam change 36→48 (preceding) | 0.09 (−0.02 to 0.20) | 0.09 (−0.03 to 0.21) |

### Direction B: activity → crepitus (odds ratio per 1,000 steps/day)

| Outcome | Steps at 48 months | Change in steps, 48→72 |
|---|---|---|
| B1, S2 count at 72 months | 0.98 (0.95–1.02) | 1.00 (0.94–1.06) |
| B2, S2 count at 96 months | 0.99 (0.95–1.03) | 1.00 (0.94–1.07) |
| B3, new exam crepitus at 120 months | 1.00 (0.93–1.08) | 1.03 (0.92–1.15) |

All are Model 1; Model 2 is within 0.02 of each. The MV and light-minute models are in `table_a*.csv` and `table_b*.csv`. They are close to null as well, with two exceptions, from among about 200 estimates:
- each extra 10 light min/day gained from 48 to 72 months goes with slightly lower odds of S2 at 96 months, OR 0.97 (0.95–0.99);
- each 10 light min/day at 48 months goes with OR 1.03 (1.00–1.05) for new exam crepitus at 120 months.

### Variants

| Variant | Change in the estimates |
|---|---|
| `available_knees` | Estimates unchanged; n rises slightly. |
| `log_activity` | Ratios: A2 exam 1.01 (0.99–1.03); A2 S2 0.98 (0.96–1.00). |
| `s2_cut_2` | S2 counts a knee at "sometimes" or more. The A2 S2 estimate is −0.13 (−0.24 to −0.01) thousand steps per knee. Everything else is unchanged. |

### Reading

- **The unadjusted difference is explained by covariates.** People with exam crepitus in both knees walk about 700 fewer steps/day at 48 months, but age, sex, BMI and wear time account for it.
- **Direction A:** neither crepitus measure, nor its change, predicts steps at 72 months or their change beyond about ±100–150 steps/day per crepitus knee.
- **Direction B:** activity and its change do not predict later S2 or new exam crepitus.
- **Different signs for the two measures:**
  - S2 estimates lean slightly negative (fewer steps): A2 −0.10; preceding S2 change −0.13.
  - Exam estimates lean slightly positive: A2 0.07; preceding exam change 0.09.
  - All of these CIs include 0, except under `s2_cut_2`.
- **Design limit:** with two device waves, these models show only which measure moves ahead of the other. They cannot rule out both changing together for a shared reason.
