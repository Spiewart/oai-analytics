# crepitus_activity

Crepitus and device-measured activity at 48 and 72 months, in both directions.

**Direction A:** do crepitus at a visit, or its change between visits, predict GT1M steps/day and MV and light minutes/day, or their change from 48 to 72 months?

**Direction B:** do activity at 48 months, and its change to 72 months, predict:
- KOOS S2 crepitus at 72 and 96 months;
- new exam crepitus at 120 months?

- **Spec:** [docs/superpowers/specs/2026-11-12-crepitus-activity-design.md](../../docs/superpowers/specs/2026-11-12-crepitus-activity-design.md)
- **Plan:** [docs/superpowers/plans/2026-11-12-crepitus-activity.md](../../docs/superpowers/plans/2026-11-12-crepitus-activity.md)
- **Assumptions:** [ASSUMPTIONS.md](ASSUMPTIONS.md)

The per-minute steps come from Northwestern (`OAI_STEPS_DIR`, never in the repo). Their terms: the Northwestern analyst who prepared them is a co-author on publications that use them, and the PARR group offers input.

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
| A2, exam at 48 → steps at 72 (adjusting for steps at 48) | 0.07 (−0.03 to 0.18) | 0.07 (−0.04 to 0.18) |
| A2, S2 at 48 → steps at 72 | −0.09 (−0.20 to 0.02) | −0.07 (−0.19 to 0.05) |
| A3, S2 change 48→72 (concurrent) | 0.03 (−0.10 to 0.15) | −0.01 (−0.14 to 0.12) |
| A3, S2 change 36→48 (preceding) | −0.12 (−0.25 to 0.01) | −0.10 (−0.23 to 0.04) |
| A3, exam change 36→48 (preceding) | 0.11 (−0.01 to 0.22) | 0.10 (−0.01 to 0.22) |

**Wear time:**
- A1 adjusts for wear at its own wave.
- A2 and A3 adjust for wear at both 48 and 72 months.
- A1 at 72 months includes only people valid at 48 months (1,332 of the 1,394 valid at 72).

### Direction B: activity → crepitus (odds ratio per 1,000 steps/day, Model 1)

| Outcome | Steps at 48 months | Change in steps, 48→72 |
|---|---|---|
| B1, S2 count at 72 months | 0.98 (0.95–1.02), n=1,821 | 1.01 (0.95–1.08), n=1,325 |
| B2, S2 count at 96 months | 0.99 (0.95–1.03), n=1,765 | 1.01 (0.95–1.08), n=1,299 |
| B3, new exam crepitus at 120 months (knees) | 1.00 (0.93–1.08), n=931 | 1.01 (0.90–1.13), n=737 |

**The two columns come from different models and samples:**
- "Steps at 48 months" is the model without change: everyone valid at 48 months, adjusted for wear at 48.
- "Change" is the model with both steps at 48 and the change: people valid at both waves, adjusted for wear at both.

Model 2 is within 0.02 of each estimate.

### Estimates whose CI excludes the null

Across all three activity measures, both models and both directions, 6 of the 174 default estimates have a 95% CI that excludes the null. At nominal 95%, about 9 would be expected by chance. All six involve light minutes:

| Estimate | Model 1 | Model 2 |
|---|---|---|
| B2: change in light minutes 48→72 → S2 at 96 months, OR per 10 min/day | 0.98 (0.96–1.00) | 0.97 (0.95–0.99) |
| B1: light minutes at 48 months, in the model with change → S2 at 72 months | 1.02 (1.00–1.04) | 1.02 (1.00–1.04) |
| B3: light minutes at 48 months → new exam crepitus at 120 months | 1.03 (1.00–1.05), CI includes 1 | 1.03 (1.00–1.06) |
| A1: two S2 knees vs none at 72 months, difference in light min/day | +9.7 (+0.5 to +19.0) | +8.9 (−0.8 to +18.7) |

No steps or MV estimate excludes the null.

### Variants

| Variant | How the estimates move |
|---|---|
| `available_knees` | Estimates unchanged, with n slightly larger. The same 6 CIs exclude the null. |
| `log_activity` | A estimates become ratios: A2 exam 1.01 (0.99–1.03), A2 S2 0.98 (0.96–1.00). B estimates become ORs per one unit of log(x + 1), so they are not comparable with the default's per-1,000-steps scale. Three CIs exclude the null, all light minutes: B2 change OR 0.55 (Model 1) and 0.48 (Model 2), and B3 at 48 months 2.62 (Model 2). |
| `s2_cut_2` | S2 counts a knee at "sometimes" or more. Four CIs exclude the null, three of them in A1 at 72 months (Model 1). S2 per knee: steps −0.17 (−0.35 to −0.00), MV −0.14 (−0.26 to −0.02) per 10 min/day; two S2 knees vs none, MV −0.27 (−0.51 to −0.04). The fourth is B3's light-minutes Model 2 estimate above. |

### Reading

- **The unadjusted difference is explained by covariates.** People with exam crepitus in both knees walk about 700 fewer steps/day at 48 months, but age, sex, BMI and wear time account for it.
- **Direction A:**
  - Neither crepitus measure, nor its change, predicts steps at 72 months or the change in steps.
  - Per crepitus knee, the point estimates are within ±120 steps/day. The CIs reach about −250 to +220 steps/day; for two knees vs none, about ±500.
- **Direction B:** steps at 48 months and their change do not predict later S2 or new exam crepitus. The ORs are 0.98–1.01 per 1,000 steps/day, with CIs within 0.90–1.13.
- **Different signs for the two measures:**
  - S2 estimates lean slightly negative (fewer steps): A2 −0.09; preceding S2 change −0.12.
  - Exam estimates lean slightly positive: A2 0.07; preceding exam change 0.11.
  - All of these CIs include 0.
- **Light minutes:** the few nominally significant estimates are all light minutes, and their number is about what chance gives across 174 estimates.
- **Design limit:** with two device waves, these models show only which measure moves ahead of the other. They cannot rule out both changing together for a shared reason.
