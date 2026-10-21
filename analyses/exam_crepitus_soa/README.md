# Palpable crepitus and incident symptomatic knee OA

Does examiner-palpated patello-femoral crepitus (`V##RKPFCRE`) predict incident symptomatic knee OA, as self-reported crepitus (KOOS S2) did in Lo 2018? No paper has asked this. The cohort, outcome, periods and models are the Lo 2018 replication's (`analyses/lo2018_crepitus`), shared through `oai.derive.incident_soa`.

The exam item is anchored by a replication of Mahmoudian et al. (OARSI 2023 abstract 179). That study found baseline exam crepitus not associated with tibiofemoral structural development over 4 years in 576 symptomatic KL 0–1 knees: adjusted OR 1.2 (0.9–1.7).

Design: [spec](../../docs/superpowers/specs/2026-10-21-exam-crepitus-incident-soa-design.md) · [plan](../../docs/superpowers/plans/2026-10-21-exam-crepitus-incident-soa.md) · [assumptions](ASSUMPTIONS.md) · [anchors](published.toml).

## Steps

| Step | Does | Outputs |
|---|---|---|
| `cohort` | Lo 2018 cohort; exam-crepitus person-periods and four-year frame | `flow.csv`, `metrics_cohort.csv`; frames `frame.parquet`, `persons.parquet` |
| `anchor` | Mahmoudian cohort (KL 0–1, frequent pain, one knee each) and structural outcomes | `metrics_anchor.csv`; frame `anchor.parquet` |
| `models` | Tables E1–E6 (one-year GEE, four-year logistic; unadjusted, adjusted, adjusted for S2) and the Mahmoudian ORs | `table_e1.csv` … `table_e6.csv`, `table_m1.csv`, `metrics_models.csv` |
| `compare` | Grades the cohort flow (against Lo 2018) and the Mahmoudian anchors | `comparison.csv` |

```bash
oai run exam_crepitus_soa
oai run exam_crepitus_soa --variant require_s2
```

## Results

Not run yet.
