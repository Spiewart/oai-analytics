# Lo 2018 crepitus replication, and dual-measure crepitus: design

**Date:** 2026-10-21
**Paper:** Lo GH, Strayhorn MT, Driban JB, Price LL, Eaton CB, McAlindon TE. Subjective crepitus as a risk factor for incident symptomatic knee osteoarthritis: data from the Osteoarthritis Initiative. *Arthritis Care Res* 2018;70:53–60. [doi:10.1002/acr.23246](https://doi.org/10.1002/acr.23246), PMC5671376.

## Why

The user is planning a full analysis of OAI crepitus measures against incident and progressive OA, knee replacement, activity and accelerometry (`analyses/crepitus/LITERATURE.md`). As with Lo 2022, the suite is first validated by replicating the published crepitus paper, so the definitions that later analyses reuse (symptomatic OA, observation periods, GEE set-up) are known to reproduce published numbers. On the way, the same cohort sizes the dual-measure question: KOOS S2 (self-report) against examiner-palpated patello-femoral crepitus, for concordance and for whether either or both predict incident symptomatic OA.

## What the paper did (full text, PMC)

- **Design:** person-based, right knee only (GEE adjusts for one clustering level; visits were chosen over knees).
- **Flow:** 4,796 → minus 35 with arthroplasty at enrollment → minus 305 with no baseline right-knee KL → minus 877 with baseline right-knee SOA → minus 84 with no valid SOA outcome at any follow-up → **3,495**.
- **Exposure:** KOOS S2, right knee ("Do you feel grinding, hear clicking or any other type of noise when your right knee moves?"), never / rarely / sometimes / often / always, at baseline, 12, 24 and 36 months (V00, V01, V03, V05). Never is the referent.
- **Symptoms (Sx):** yes to the 12-month frequent-pain question for the right knee, at baseline, 12, 24, 36, 48 months.
- **ROA:** tibiofemoral KL ≥ 2, central readings, baseline and annual visits to 48 months.
- **SOA:** Sx and ROA. A participant with a knee arthroplasty is counted as Sx, ROA and SOA.
- **Primary model:** repeated-measures logistic GEE, exchangeable, clustered on person. Crepitus at visit *t* predicts incident SOA at the next annual visit. Up to 4 observation periods (V00→V01, V01→V03, V03→V05, V05→V06). A person is censored after incident SOA. Adjusted for age, sex, BMI (baseline). Trend by Cochran–Armitage.
- **Observations:** 11,994 potential; 750 missing the outcome and 7 missing crepitus were excluded → **11,237** observations, **636** incident cases (258, 159, 126, 93 by period).
- **Four-year model:** baseline crepitus only, outcome incident SOA by 48 months, one observation per person (same 3,495, same 636 cases).
- **Subgroups by baseline status:** +ROA −Sx (1,085 people; 488 cases), −ROA +Sx (660; 67), −ROA −Sx (1,750; 81).
- **Interactions** of crepitus with age, sex, BMI (Table 5); strata men / women, age < 65 / ≥ 65 (Table 6).
- **Spearman** at baseline: crepitus with WOMAC pain R = 0.33; with KL R = 0.03 (p = 0.1); per subgroup 0.31 / 0.20 / 0.25 with WOMAC.

Tables 1–6 (cases / totals per crepitus level, unadjusted and adjusted ORs with 95% CI) were extracted from the PMC page. Every table's categories sum to its stated observations and cases, and the flow sums to 3,495. They should still be proofread against the PDF before they are treated as final targets.

## Checks already run on the release

Right-knee-only exclusions with Project 15 readings: 38 baseline arthroplasties (paper 35), 304 without a baseline right-knee KL (paper 305), **877 baseline right-knee SOA (paper 877)**, 3,577 remaining before the outcome step (paper 3,579). Counting arthroplasty in either knee gives 63 / 866, further from the paper.

## Decisions (go in `assumptions.toml`)

| Key | Default | Status | Alternatives |
|---|---|---|---|
| `cohort.side` | `"R"` | confirmed | `"L"` (sensitivity only) |
| `cohort.reading_project` | 15 | assumed (reproduces 877) | 37, 43 |
| `cohort.arthroplasty_scope` | `"right"` | assumed (38 vs 35, closer than either-knee) | `"either"` |
| `cohort.missing_baseline_pain` | `"not_sx"` | open (the paper lists no exclusion for it; 26 people) | `"exclude"` |
| `outcomes.pain_baseline_item` | `"P01KPR12CV"` | assumed | — |
| `outcomes.pain_followup_item` | `"V{visit}KPR12CV"` | assumed | — |
| `outcomes.roa_rule` | `"same_visit"` | open | `"ever"` (ROA carried forward once seen) |
| `outcomes.arthroplasty_scope` | `"right"` | open ("any participant with a knee arthroplasty") | `"either"` |
| `outcomes.arthroplasty_timing` | `"by_visit_days"` | assumed (replacement on or before that visit's day count) | — |
| `periods.after_missing_outcome` | `"continue"` | open (graded by 11,994 and 750) | `"stop"` |
| `model.corstr` | `"exchangeable"` | confirmed | `"independence"` |
| `model.covariates` | `["age", "sex", "bmi"]` | confirmed | — |
| `model.trend` | `"cochran_armitage"` | assumed (reported, not graded) | `"ordinal_term"` |

## Dual-measure extension (not graded)

Exam crepitus (`V##RKPFCRE`) exists at exactly Lo's exposure visits (V00, V01, V03, V05), so both measures can enter the same periods.

1. **Counts (2 × 2):** S2 (dichotomized at ≥ 1 and at ≥ 3) × exam, per visit and per observation period, with incident SOA in each cell, overall and by baseline subgroup and by enrollment cohort.
2. **Concordance:** percent agreement, Cohen's kappa (bootstrap CI), prevalence and bias indices, and the AUC of the ordinal S2 for exam crepitus, per visit.
3. **Prediction:** a four-level combined exposure (neither, S2 only, exam only, both). Adjusted ORs against neither, in both the one-year GEE and the four-year model. Se, Sp, PPV, NPV of each measure and of "both" and "either" for four-year incident SOA. Both measures in one model, with and without their interaction.

Preliminary counts (right knees, no baseline SOA, ascertained to 48 months, S2 ≥ 1, outcome without the arthroplasty rule): neither 1,460 (193 incident), S2 only 736 (122), exam only 679 (146), both 571 (179). At S2 ≥ 3, both is 198 (66).

## Out of scope

Patellofemoral-specific outcomes (not read in the OAI), MRI, TKR, activity and accelerometry. They are the next analyses and will reuse this cohort and its definitions. A Quarto comparison report is a later follow-up.
