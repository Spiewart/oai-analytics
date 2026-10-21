# Palpable crepitus and incident symptomatic knee OA: design

**Date:** 2026-10-21
**Builds on:** `analyses/lo2018_crepitus` (Lo 2018 replication, considered methodologically replicated by the user on 2026-10-21) and `analyses/crepitus/LITERATURE.md`.

## Why

Lo 2018 showed that self-reported crepitus (KOOS S2) predicts incident symptomatic knee OA (SOA). No paper has asked the same of examiner-palpated crepitus. The one test of the exam item, Mahmoudian et al. (OARSI 2023 abstract), found no association with tibiofemoral structural development in 576 symptomatic KL 0–1 knees. That population is Lo's −ROA +Sx subgroup, the one where S2 did not predict either. Our replication cohort shows the same flat result there for the exam item, and a clear one in +ROA −Sx knees:

| Baseline subgroup (right knee, four-year SOA) | Exam crepitus: cases / n | No exam crepitus: cases / n |
|---|---|---|
| +ROA −Sx | 288 / 546 (53%) | 212 / 558 (38%) |
| −ROA +Sx | 24 / 236 (10%) | 45 / 441 (10%) |
| −ROA −Sx | 21 / 481 (4%) | 63 / 1,213 (5%) |

In repeated-measures form: 10,634 person-periods with an exam value (347 of 4,073 exposed periods became SOA vs 275 of 6,561 unexposed).

So the analysis has two parts:

1. **Exam crepitus → incident SOA with Lo 2018's design**, the new result.
2. **A replication of Mahmoudian 2023**, as the anchor that the exam item and the structural outcome are coded correctly, as Lo 2018 anchored S2.

## Part 1: exam crepitus → incident SOA

The cohort, symptomatic-OA definition, observation periods, censoring, covariates and subgroups are Lo 2018's, taken from the replication without change. Its assumptions and their defaults are inherited, including the two choices still open with Grace: blank baseline pain, and the 84 "no valid outcome".

- **Exposure:** exam crepitus (`V##RKPFCRE`, yes/no) at V00, V01, V03 and V05, predicting SOA at the next annual visit. Binary, so each table has one OR per model, not four.
- **Periods:** a period needs an exam value, and does not need S2 (`exposure.require_s2 = false`). The variant `require_s2` restricts to periods with both measures, so the exam and S2 estimates sit on the same rows.
- **Models**, for each table:
  - unadjusted;
  - adjusted for age, sex and BMI;
  - adjusted for age, sex, BMI and S2 (0–4 as a factor).
- **Tables:**
  - E1: one-year, everyone.
  - E2: one-year, by the three baseline subgroups.
  - E3: four-year (baseline exam only), everyone.
  - E4: four-year, by subgroup.
  - E5: interaction p-values of exam with age, sex, BMI and S2 (four-year).
  - E6: four-year, by sex and by age (< 65 vs ≥ 65).
- **Grading:** there is nothing published to grade Part 1 against. As a guard against drift between the two analyses, the cohort flow is graded against Lo 2018's published flow.

## Part 2: Mahmoudian 2023 replication (anchor)

From the abstract and its Table 1 (supplied by the user):

- **Who:** Progression and Incidence cohorts (no controls). Knees with tibiofemoral KL 0–1 at baseline and yes to the 12-month frequent-pain question. If both knees qualify, one is chosen at random. A baseline exam value and a 48-month (V06) reading are needed.
- **Exposure:** exam crepitus at baseline.
- **Outcomes at V06:**
  - (a) structural development: incident joint-space narrowing (JSN) and/or an increase in the number of osteophytes in either tibiofemoral compartment;
  - (b) (a) with frequent pain still present at V06.
- **Models:** logistic regression: crude; adjusted for age, sex and BMI; plus baseline KL.
- **Targets:**
  - 576 subjects, 264 (45.8%) with crepitus, 60% women, age 58.9 (8.5), BMI 29.6 (4.9);
  - events 310/576 and 153/576;
  - ORs 1.3 (1.0–1.8), 1.2 (0.8–1.7), 1.2 (0.9–1.7); with symptoms 1.1 (0.8–1.7), 1.1 (0.7–1.6), 1.0 (0.7–1.5).

OAI readings carry medial and lateral JSN (`V##XRJSM`, `V##XRJSL`) and four osteophyte grades (`V##XROSFM`, `V##XROSTM`, `V##XROSFL`, `V##XROSTL`) at V00 and V06.

### Decisions the abstract leaves open

| Key | Default | Alternatives |
|---|---|---|
| `mahmoudian.knee_pick` | `random` (seeded) | `right`, `left` |
| `mahmoudian.seed` | 2023 | any integer |
| `mahmoudian.jsn_rule` | `incident` (V06 grade ≥ 1 where baseline is 0, in either compartment) | `any_increase` |
| `mahmoudian.osteophyte_rule` | `sites` (more of the four sites graded ≥ 1) | `grade_sum` (the sum of the four grades rises) |
| `mahmoudian.reading_project` | 15 | 37, 43 |

All are `open` except the project (`assumed`, as in Lo 2018). The random knee means our counts and ORs can't match exactly. The seed fixes ours, and a variant per knee rule shows how much the pick moves them.

## Out of scope

Incident radiographic OA in all KL 0–1 knees, progression, TKR, activity and accelerometry; these are the next analyses. Anything after 48 months: Project 15 readings stop at V06.
