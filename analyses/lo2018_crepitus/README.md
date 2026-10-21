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
| `dual_models` | Concordance and predictive value of each measure and both | `dual_concordance.csv` (per exposure visit: 2 × 2, agreement, kappa, prevalence and bias indices, AUC of S2 for exam), `dual_prediction.csv` (ORs of S2 only, exam only and both vs neither; the S2 × exam interaction), `dual_classification.csv` (Se, Sp, PPV, NPV for four-year SOA) |

```bash
oai run lo2018_crepitus
oai run lo2018_crepitus --variant stop_after_missing_outcome
```

## Replication status

Run 2026-10-21 on the full release. 266 graded metrics: counts within max(3%, 2), means within 0.5, correlations within 0.03, odds ratios within 0.1 with the same significance.

| Run | Replicated | Drift | Persons | Observations | Cases |
|---|---|---|---|---|---|
| Paper | | | 3,495 | 11,237 | 636 |
| `default` | 209 | 57 | 3,576 | 11,248 | 641 |
| `exclude_missing_pain` | **220** | 46 | 3,550 | 11,179 | 635 |
| `corstr_independence` | 210 | 56 | 3,576 | 11,248 | 641 |
| `soa_known_false` | 185 | 81 | 3,577 | 11,958 | 641 |
| `stop_after_missing_outcome` | 171 | 95 | 3,576 | 10,643 | 599 |
| `roa_ever` | 170 | 96 | 3,576 | 11,449 | 662 |
| `arthroplasty_either` | 167 | 99 | 3,564 | 11,191 | 663 |
| `left_knee` (not the paper) | 67 | 199 | 3,614 | 11,401 | 615 |

- **Replicates:** every Table 1 metric (one-year model: cases, totals and all eight ORs); observations, cases and cases per period; mean age and BMI; all five Spearman correlations; the baseline-SOA exclusion (877, exact).
- **Drifts:** the persons count (about 80 more than the paper), the "potential observation" and missing-outcome counts, and, because they count persons, cells of the four-year Tables 3, 4 and 6.
- **Unexplained:** the paper excludes 84 people with "no valid outcome measure assessments of SOA at any of the follow up visit time points"; on this release only 1 cohort member has no SOA at any follow-up, and 3,547 have one or more analyzable observations. The paper's 11,994 potential observations are also fewer than ours (13,071), which suggests it did not count periods after a participant's last visit. Both are filed in `TODO.md` as questions for the authors.
