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

Run 2026-10-21 on the full release. Right knee; Lo 2018 cohort (3,576 people at 96 months). Radiographic OA comes from OUTCOMES99, and is unknown after a knee's last reading without ROA (`V99E?XNOA`). The exam is carried forward from V06 for the periods after 48 months. All ORs are adjusted for age, sex and BMI.

**Regression anchor.** With 48-month settings (`--variant lo2018_48m`) the L1 exam ORs equal `exam_crepitus_soa`'s E1, and the adjusted S2 ORs equal `lo2018_crepitus`'s Table 1, to within 1e-9 (`tests/test_longterm_realdata.py`).

**How to read the three models.**
- **L2 (discrete-time hazard, baseline measure)** uses every observed period and does not count dropouts as non-cases. It is the censoring-robust estimate.
- **L3 (SOA by the horizon)** keeps people whose outcome at the horizon is known, plus anyone who became a case earlier (`horizon.selection = "known_or_case"`). That keeps cases who later left and drops non-cases who left, so it favours cases. `--variant horizon_complete` keeps only people with a known outcome at the horizon. Neither matches Lo 2018's four-year table, which counted missing outcomes as non-events.

**Follow-up and coverage** (exam frames; case counts are the same for S2 to within one).

| | 48 mo (`lo2018_48m`) | 96 mo (default) | 120 mo (`horizon_120`) |
|---|---|---|---|
| People with a known outcome at the last visit | 2,902 | 2,772 | 1,857 |
| Incident SOA cases | 655 | 906 | 991 |
| People in L3 (`known_or_case`) | 2,893 | 2,783 | 2,261 |

- **ROA source:** at 48 months, Project 15 and OUTCOMES99 disagree on radiographic OA for 20 of 2,883 knees. All 20 have ROA only in OUTCOMES99, which takes the earliest incidence from either project.
- **Baseline definition:** the baseline subgroups and exclusions still use Project 15 KL, while follow-up ROA uses OUTCOMES99. Only those 20 knees can differ.
- **Project 37 (72/96 months):** of the 3,576-person cohort's right knees, it reads 80 with ROA and no frequent pain, 466 with pain and no ROA, and 1,281 with neither. The low count in the first group is by design: their ROA is established and carried forward.
- **Project 43 (to 120 months):** reads 275, 377 and 1,123 in the same groups. Its selection is not documented, so the 120-month results are provisional.

**Exam crepitus**, adjusted OR (95% CI):

| Model | 96 months | + S2 (0–4) | 120 months |
|---|---|---|---|
| L1, time-varying, one period ahead | 1.88 (1.63–2.16) | 1.75 (1.51–2.01) | 1.77 (1.55–2.03) |
| L2, baseline exam, discrete-time hazard | 1.66 (1.45–1.91) | 1.54 (1.33–1.77) | 1.61 (1.41–1.84) |
| L3, baseline exam, SOA by the horizon | 1.80 (1.52–2.13) | — | 1.89 (1.57–2.26) |

- **By subgroup (L4, hazard, 96 months):**
  - ROA without frequent pain: 1.38 (1.16–1.63), 639 cases;
  - no ROA with pain: 1.06 (0.70–1.60);
  - neither: 1.13 (0.80–1.58).
- **The subgroup difference fades with follow-up.** In the same hazard model, the exam × subgroup Wald p is 0.016 at 48 months and 0.56 at 96 months.
- **Both measures together (L4 joint, hazard, 96 months)**, with an exam × any-S2 term:
  - exam OR when S2 is "never": 1.38 (1.14–1.67);
  - exam OR when S2 is reported at all: 1.76 (1.42–2.17);
  - interaction 1.28 (0.96–1.70).
  - The single S2-adjusted exam OR is the L2 + S2 figure above, 1.54.

**KOOS S2**, adjusted ORs against "never", 96 months:

| Model | Rarely | Sometimes | Often | Always |
|---|---|---|---|---|
| L1 | 1.55 | 1.77 | 2.09 | 2.82 (2.06–3.85) |
| L2 | 1.47 | 1.42 | 2.11 | 3.11 (2.23–4.34) |
| L3 | 1.59 | 1.45 | 2.35 | 3.80 (2.47–5.83) |

- **By subgroup (L4), "always":** 3.22 with ROA and no pain, 1.80 with pain and no ROA, and 2.91 with neither (S2 × subgroup p = 0.37).
- **No ROA or pain at baseline:** "often" and "always" are associated by 96 months: 2.41 (1.35–4.31) and 2.91 (1.19–7.12). This is the group where Lo 2018 found an association only over 4 years (trend p = 0.03).

**Variants**, adjusted ORs:

| Variant | Exam L1 | Exam L2 | Exam L3 | S2 always L2 | Known at last visit |
|---|---|---|---|---|---|
| default (96 months) | 1.88 | 1.66 | 1.80 | 3.11 | 2,772 |
| `horizon_120` | 1.77 | 1.61 | 1.89 | 2.96 | 1,857 |
| `horizon_complete` | 1.88 | 1.66 | 1.79 | 3.11 | 2,772 |
| `roa_unread_as_none` | 1.88 | 1.67 | 1.84 | 3.05 | 3,061 |
| `roa_kl2_jsn` | 1.95 | 1.64 | 1.73 | 2.39 | 2,652 |
| `exam_no_carry` | 1.90 | 1.66 | 1.80 | 3.11 | 2,772 |
| `period_term_none` | 1.82 | 1.67 | 1.80 | 3.19 | 2,772 |

The exam OR holds between 1.6 and 2.0 under every choice. The ROA definition (KL ≥ 2 vs KL ≥ 2 with JSN; 744 vs 906 cases) moves S2 the most.

`table_l4.csv` reports the measure × subgroup Wald test as `model = "x_subgroup"` with its p-value in the `p` column, fitted on the complete-case rows it reports.
