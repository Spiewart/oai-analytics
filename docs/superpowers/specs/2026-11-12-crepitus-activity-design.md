# Crepitus and device-measured activity at 48 and 72 months: design

**Question.** Does crepitus (absolute or changing) predict a change in device-measured activity and step counts? In the other direction, does activity (or its change) predict crepitus later?

**Data.**
- **Device:** GT1M accelerometry at 48 months (V06) and 72 months (V08). Counts come from the public release; per-minute steps come from Northwestern, read from `OAI_STEPS_DIR` and never stored in the repo. The person-wave measures are `walking_steps`' (`person_wave`, its device rules).
- **Valid wear:** 1,928 people at 48 months, 1,394 at 72 months, 1,343 at both.
- **Crepitus:**

| Measure | Visits | Variable |
|---|---|---|
| KOOS S2 | 36, 48, 72, 96 months | `V##KSX{R,L}KN2`, 0–4 |
| Exam crepitus | 36, 48, 120 months | `V##{R,L}KPFCRE`, present/absent; none at 72 or 96 months |

Among valid 48-month wearers, 63% have exam crepitus in at least one knee and 54% report S2 in at least one knee.

## Decisions (user, 2026-11-12)

1. **Crepitus per person = knee count, 0/1/2.**
   - Exam: knees with crepitus present.
   - S2: knees with S2 ≥ 1 ("at least rarely").
   - A count needs both knees known (assumed; variant: count over the available knees).
   - Change in S2 between visits is the change in the count, from −2 to +2.
2. **Activity → crepitus covers three outcomes:**
   - S2 count at 72 months;
   - S2 count at 96 months;
   - new exam crepitus at 120 months in knees free of it at 48 months: 931 knees, 184 new.

## Design

**Activity measures:**
- steps/day (primary);
- MV minutes/day and light minutes/day from counts (secondary).

Each is a mean over the person's valid days (`walking_steps` rules), scaled per 1,000 steps or per 10 minutes.

**Direction A: crepitus → activity** (one row per person; linear model with robust, sandwich SEs):
- **A1, cross-sectional:** activity at 48 months ~ crepitus count at 48 months (exam, S2); and at 72 months ~ S2 at 72 months.
- **A2, absolute crepitus predicts change:** activity at 72 months ~ crepitus at 48 months + activity at 48 months (ANCOVA). Exam and S2 are tested separately, then together.
- **A3, change predicts change:**
  - activity at 72 months ~ change in S2 from 48 to 72 months (concurrent) + S2 at 48 months + activity at 48 months;
  - activity at 72 months ~ change in S2 and in exam from 36 to 48 months (preceding) + their 36-month values + activity at 48 months.

**Direction B: activity → crepitus:**
- **B1:** S2 count at 72 months ~ activity at 48 months + S2 count at 48 months; then adding the change in activity from 48 to 72 months. Proportional-odds (ordinal) regression on the 0/1/2 count.
- **B2:** S2 count at 96 months ~ activity at 48 months + change in activity + S2 count at 72 months. Ordinal.
- **B3:** new exam crepitus at 120 months (knee level, knees without exam crepitus at 48 months) ~ activity at 48 months + change in activity. Logistic GEE clustered within person.

**Covariates:**
- Model 1: age, sex, BMI and wear hours/day at the exposure wave.
- Model 2: Model 1 plus the higher KL grade of the two knees (Project 15 at 48 months; Project 37 or later readings are not used) and the worse knee's WOMAC pain at 48 months. Pain may be a confounder or a mediator, so both models are reported.

**Reporting:**
- every estimate per crepitus knee (count as linear) and by level (1 and 2 knees vs 0);
- n and the outcome's mean (A) or cases (B) per level;
- no p-value-driven selection.

## Out of scope

Bout-based walking definitions, cadence bands, the Walking Question and PASE, MRI, and time-to-event models.

## Authorship note

The step data come from Northwestern. Its analyst is to be a co-author on publications that use them, and the PARR group offers input (memory: nw-step-data).
