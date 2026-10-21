# Crepitus and incident symptomatic knee OA beyond 48 months

Extends `analyses/lo2018_crepitus` (KOOS S2) and `analyses/exam_crepitus_soa` (examiner crepitus) from 48 months to 96 months (primary) and 120 months (sensitivity). Radiographic OA at each visit comes from OUTCOMES99's earliest-incidence variables, which combine reading Projects 15, 37 and 43.

Design: [spec](../../docs/superpowers/specs/2026-10-21-crepitus-soa-longterm-design.md) · [plan](../../docs/superpowers/plans/2026-10-21-crepitus-soa-longterm.md) · [assumptions](ASSUMPTIONS.md).

## Steps

| Step | Does | Outputs |
|---|---|---|
| `cohort` | Lo 2018 cohort; for each measure the time-varying periods, the baseline-exposure hazard frame and the by-horizon frame; coverage of the later readings | `flow.csv`, `metrics_cohort.csv`, `coverage.csv`; frames `{s2,exam}_{periods,hazard,horizon}.parquet` |
| `models` | Tables L1–L4 | `table_l1.csv` … `table_l4.csv`, `metrics_models.csv` |

```bash
oai run crepitus_soa_longterm                       # 96 months
oai run crepitus_soa_longterm --variant horizon_120  # 120 months
oai run crepitus_soa_longterm --variant lo2018_48m   # reproduces the 48-month analyses
```

## Results

Run 2026-10-21 on the full release. Right knee; Lo 2018 cohort (3,577 people at 96 months). Radiographic OA comes from OUTCOMES99. The exam is carried forward from V06 for the periods after 48 months. All ORs are adjusted for age, sex and BMI.

**Regression anchor.** With 48-month settings (`--variant lo2018_48m`) the L1 exam ORs equal `exam_crepitus_soa`'s E1, and the adjusted S2 ORs equal `lo2018_crepitus`'s Table 1, to within 1e-9 (`tests/test_longterm_realdata.py`).

**Follow-up.**

| | 48 mo | 96 mo (default) | 120 mo |
|---|---|---|---|
| People with an outcome at the last visit | 3,318 | 3,061 | 2,140 |
| Incident SOA cases (by-horizon frame) | 655 | 906 | 991 |

- **ROA source:** at 48 months, Project 15 and OUTCOMES99 disagree on radiographic OA for 20 of 2,883 knees. All 20 have ROA only in OUTCOMES99, which takes the earliest incidence from either project.
- **Project 37 (72/96 months):** reads only 80 of the 1,106 knees with ROA and no frequent pain, by design. Their ROA is already established, so OUTCOMES99 carries it forward.
- **Project 43 (to 120 months):** reads 275 of them. Its selection is not documented, so the 120-month results are provisional.

**Exam crepitus**, adjusted OR (95% CI):

| Model | 96 months | + S2 | 120 months |
|---|---|---|---|
| L1, time-varying, one period ahead | 1.88 (1.63–2.16) | 1.75 (1.52–2.02) | 1.78 (1.56–2.04) |
| L2, baseline exam, discrete-time hazard | 1.67 (1.46–1.92) | 1.55 (1.35–1.78) | 1.62 (1.42–1.85) |
| L3, baseline exam, SOA by the horizon | 1.84 (1.57–2.17) | 1.69 (1.43–1.99) | 1.93 (1.62–2.29) |

- **By subgroup (L4, hazard, 96 months):**
  - ROA without frequent pain: 1.38 (1.16–1.63), 639 cases;
  - no ROA with pain: 1.05 (0.70–1.59);
  - neither: 1.14 (0.82–1.59).
  - The exam × subgroup Wald test is p = 0.55. With longer follow-up the subgroup difference seen at 48 months (p = 0.003 in the four-year logistic model) is no longer clear.
- **Both measures together (L4 joint, hazard):** exam OR 1.39 (1.15–1.68) adjusted for S2 (0–4). The exam × any-S2 interaction is 1.28 (0.96–1.70).

**KOOS S2**, adjusted ORs against "never" for rarely / sometimes / often / always:

| Model, 96 months | Rarely | Sometimes | Often | Always |
|---|---|---|---|---|
| L1 | 1.55 | 1.77 | 2.05 | 2.81 (2.06–3.83) |
| L2 | 1.46 | 1.40 | 2.07 | 3.05 (2.20–4.23) |
| L3 | 1.55 | 1.47 | 2.22 | 3.67 (2.43–5.53) |

By subgroup (L4), "always" is 3.22 with ROA and no pain, 1.75 with pain but no ROA, and 2.83 with neither (S2 × subgroup p = 0.37). In the group without ROA or pain, "often" and "always" reach significance by 96 months (2.28, 1.28–4.09; 2.83, 1.16–6.87), as Lo 2018 found at 4 years (trend p = 0.03).

**Variants** (exam L1 / L2 / L3 adjusted; S2 "always" L3):

| Variant | Exam L1 | Exam L2 | Exam L3 | S2 always L3 |
|---|---|---|---|---|
| default (96 months) | 1.88 | 1.67 | 1.84 | 3.67 |
| `horizon_120` | 1.78 | 1.62 | 1.93 | 3.70 |
| `roa_kl2_jsn` | 1.93 | 1.64 | 1.75 | 2.55 |
| `exam_no_carry` | 1.90 | 1.67 | 1.84 | 3.67 |
| `period_term_none` | 1.81 | 1.69 | 1.84 | 3.67 |

The choice of ROA definition matters most for S2: with KL ≥ 2 plus JSN there are 744 cases by 96 months, against 906.
