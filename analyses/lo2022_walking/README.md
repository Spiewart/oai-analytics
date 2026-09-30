# lo2022_walking

Replication of Lo GH et al. *Association Between Walking for Exercise and Symptomatic
and Structural Progression in Individuals With Knee Osteoarthritis.* Arthritis Rheumatol
2022;74:1660–7 (doi:10.1002/art.42241). It tests whether the suite reproduces a
published OAI analysis.

| Step | Lang | Output |
|---|---|---|
| `cohort` (`build_frame.py`) | Python | knee frame, `flow.csv`, `table1.csv`, `table3.csv`, `metrics_cohort.csv` |
| `models` (`models.R`) | R | `table2.csv`, `metrics_models.csv` (GEE logistic, knees clustered on participant) |
| `compare` (`compare.py`) | Python | `comparison.csv`, a graded verdict against `published.toml` |

```bash
oai run lo2022_walking                                  # the paper's primary analysis
oai run lo2022_walking --variant missing_as_nonwalkers  # Supplementary Table 2
oai run lo2022_walking --variant missing_as_walkers     # Supplementary Table 3
oai assumptions lo2022_walking                          # what was assumed, and why
```

Every analytic choice is in [assumptions.toml](assumptions.toml) (rendered as
[ASSUMPTIONS.md](ASSUMPTIONS.md)). Results stay in `$OAI_RESULTS_DIR` and are not committed.
