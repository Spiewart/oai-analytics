# Lo 2018 replication: crepitus and incident symptomatic knee OA

Replicates Lo GH et al., "Subjective crepitus as a risk factor for incident symptomatic knee osteoarthritis: data from the Osteoarthritis Initiative", *Arthritis Care Res* 2018;70:53–60 ([doi:10.1002/acr.23246](https://doi.org/10.1002/acr.23246)). It then adds a dual-measure step comparing KOOS S2 (self-report) with examiner-palpated patello-femoral crepitus on the same cohort.

Design: [spec](../../docs/superpowers/specs/2026-10-21-lo2018-crepitus-replication-design.md) · [plan](../../docs/superpowers/plans/2026-10-21-lo2018-crepitus-replication.md) · [assumptions](ASSUMPTIONS.md) · [targets](published.toml).

## What is replicated

Right knee only, one row per person. KOOS S2 (never to always) at V00, V01, V03, V05 predicts incident symptomatic OA (frequent pain with KL ≥ 2; a knee replacement counts) at the next annual visit. GEE, exchangeable, censored after the first case, adjusted for age, sex and BMI. A second model uses baseline S2 only, with incident symptomatic OA by 48 months.

Graded targets: the flow (4,796 → 3,495), the observation counts (11,994 potential, 11,237 analyzed, 636 cases), descriptives, the baseline Spearman correlations, and Tables 1–4 and 6. Every table in `published.toml` is checked to sum to its totals (`tests/test_lo2018_definition.py`).

Table 5 (interaction p-values, four-year model) is not graded:

| Group | Age | Sex | BMI |
|---|---|---|---|
| Overall | 0.02 | 0.009 | 0.3 |
| +ROA −Sx | 0.008 | 0.004 | 0.7 |
| −ROA +Sx | 0.3 | 0.6 | 0.3 |
| −ROA −Sx | 0.8 | 0.5 | 0.7 |

## Steps

| Step | Does | Outputs |
|---|---|---|
| `cohort` | Cohort flow, person-period observations, four-year frame, descriptives | `flow.csv`, `metrics_cohort.csv`; frames `frame.parquet`, `persons.parquet` |
| `models` | GEE and logistic models for Tables 1–6 | `table1.csv` … `table6.csv`, `metrics_models.csv` |
| `compare` | Grades the metrics against `published.toml` | `comparison.csv` |
| `dual_counts` | KOOS S2 × exam crepitus 2 × 2 counts | `dual_counts.csv` |
| `dual_models` | Concordance and predictive value of each measure and both | `dual_concordance.csv`, `dual_prediction.csv` |

```bash
oai run lo2018_crepitus
oai run lo2018_crepitus --variant stop_after_missing_outcome
```

## Replication status

Not run yet.
