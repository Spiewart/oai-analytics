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

Run 2026-10-21 on the full release (default settings: right knee; exam value required, S2 not).

**Palpable crepitus predicts incident symptomatic OA**, with an effect size like S2's, and largely independent of it. Each row below is adjusted for age, sex and BMI. Cells give cases / n in exposed and unexposed rows.

| Table | Group | Exam crepitus | No exam crepitus | Adjusted OR (95% CI) |
|---|---|---|---|---|
| E1, one-year | All | 348 / 4,088 | 275 / 6,572 | 1.86 (1.58–2.19) |
| E3, four-year | All | 333 / 1,263 | 321 / 2,213 | 1.91 (1.60–2.28) |
| E4, four-year | +ROA −Sx | 288 / 546 | 213 / 559 | 1.81 (1.42–2.31) |
| E4, four-year | −ROA +Sx | 24 / 236 | 45 / 441 | 0.90 (0.53–1.55) |
| E4, four-year | −ROA −Sx | 21 / 481 | 63 / 1,213 | 0.74 (0.44–1.23) |
| E6, four-year | Men | 123 / 505 | 106 / 966 | 2.41 (1.80–3.22) |
| E6, four-year | Women | 210 / 758 | 215 / 1,247 | 1.67 (1.34–2.09) |
| E6, four-year | Age < 65 | 184 / 741 | 197 / 1,409 | 1.87 (1.48–2.35) |
| E6, four-year | Age ≥ 65 | 149 / 522 | 124 / 804 | 2.04 (1.55–2.69) |

- **Adjusting for S2:** adding KOOS S2 (0–4) to the model barely moves the OR: 1.72 (1.46–2.03) one-year, 1.76 (1.47–2.10) four-year. The two measures carry largely separate information. Their agreement is poor (kappa about 0.1; `analyses/lo2018_crepitus` dual step).
- **Where the signal sits:** the effect is confined to knees with radiographic OA but no frequent pain, as S2's was in Lo 2018. In symptomatic knees without radiographic OA (Mahmoudian's population) it is null.
- **Interactions (E5, four-year):** sex p = 0.047 overall (larger in men, as for S2 in Lo 2018). Age p = 0.41, BMI p = 0.96, S2 p = 0.64.

**Anchors.**
- **Flow:** matches Lo 2018 as in the replication (877 baseline-SOA exclusions exact; the 84 "no valid outcome" is the open question).
- **Mahmoudian 2023:** we reproduce the null, but not the cohort.

| | Ours (default) | Mahmoudian 2023 |
|---|---|---|
| Subjects | 811 | 576 |
| With crepitus | 277 (34%) | 264 (45.8%) |
| Women | 447 (55%) | 60% |
| Age, BMI | 58.7, 28.0 | 58.9, 29.6 |
| Structural development | 124 (15%) | 310 (54%) |
| With persistent symptoms | 64 (8%) | 153 (27%) |
| OR crude / adjusted / plus KL | 1.21 / 1.06 / 1.01 | 1.3 / 1.2 / 1.2 |
| OR with symptoms | 1.26 / 1.15 / 1.09 | 1.1 / 1.1 / 1.0 |

- **Event rates:** structural development is about a third as common as published under every rule tried (JSN incident vs any increase, osteophyte sites vs grade sum, knee pick).
- **Blank grades:** Project 15 leaves osteophyte grades blank for most KL 0–1 knees. Keeping only the graded knees gives 309 subjects with 39% events, but that subset is selected. The paper probably used another reading or rule, so this is filed as a question for the authors.
- **The exam results above don't use these grades.**

| Variant | Anchors replicated (of 13) | Subjects | Events | E3 adjusted OR |
|---|---|---|---|---|
| default | 4 | 811 | 124 / 64 | 1.91 |
| `require_s2` | 4 | 811 | 124 / 64 | 1.91 |
| `exclude_missing_pain` | 4 | 811 | 124 / 64 | 1.90 |
| `mahmoudian_osteophyte_grade_sum` | 4 | 811 | 126 / 66 | 1.91 |
| `mahmoudian_any_jsn_increase` | 3 | 811 | 128 / 67 | 1.91 |
| `mahmoudian_left` | 3 | 811 | 121 / 62 | 1.91 |
| `mahmoudian_right` | 1 | 811 | 126 / 64 | 1.91 |
| `mahmoudian_exclude_blank_osteophytes` | 0 | 309 | 121 / 60 | 1.91 |
