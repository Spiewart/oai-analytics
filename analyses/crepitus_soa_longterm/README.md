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

Not run yet.
