# luyten_early_oa

Exam crepitus and self-reported crepitus (KOOS S2) within early-stage knee OA by the Luyten 2018
classification criteria: do they enrich for incident radiographic OA (KL ≥ 2) and incident
symptomatic OA (SOA) by 48 and 96 months?

- **Spec:** [docs/superpowers/specs/2026-10-22-luyten-early-oa-design.md](../../docs/superpowers/specs/2026-10-22-luyten-early-oa-design.md)
- **Plan:** [docs/superpowers/plans/2026-10-22-luyten-early-oa.md](../../docs/superpowers/plans/2026-10-22-luyten-early-oa.md)
- **Assumptions:** [ASSUMPTIONS.md](ASSUMPTIONS.md)

## Design

The unit is the knee (both knees, GEE clustered within person).

**Early-stage OA (Luyten 2018, as in Mahmoudian 2021):**
- baseline tibiofemoral KL 0–1;
- KOOS ≤ 85 in at least two of pain, symptoms, function in daily living (WOMAC function rescaled) and quality of life;
- joint-line tenderness or crepitus on examination.

Controls are KL 0–1 knees that do not meet the criteria.

**Steps:**
- `cohort`: knees, criteria, outcomes, flow and group metrics;
- `models`:
  - G1: early OA vs controls;
  - C1, Framing 1: crepitus vs tenderness only, within early OA;
  - C2, Framing 2: crepitus vs none, among KL 0–1 knees meeting the KOOS criterion;
- `compare`: grades the group against the Mahmoudian 2021 abstract.

```bash
uv run oai run luyten_early_oa
```

## Results

Run 2026-10-22 on the full release (`uv run oai run luyten_early_oa`). Counts are knees; ORs are
from logistic GEE clustered within person.

### The early-OA group (Part 1)

**Flow:**
- 9,592 knees (4,796 people), less 63 replaced at enrollment;
- 8,921 with a baseline KL reading, of which 5,028 are KL 0–1;
- 1,681 also meet the KOOS criterion;
- 1,098 (872 people) meet all three Luyten criteria. Their signs: crepitus and tenderness 334, crepitus only 266, tenderness only 498.

**Grading against the Mahmoudian 2021 abstract:** 4 replicated, 2 drift.
- Age: 58.9 vs 60.2 (published 59.2 vs 60.2).
- BMI: 28.8 vs 27.3 (published 28.3 vs 26.8).
- **The group is smaller:** 1,098 knees (21.8%) against 1,315 (27%).

**No ledger variant closes the gap:**

| Variant | Early-OA knees | Share of classifiable KL 0–1 knees | Graded vs abstract (replicated/drift) | G1 KL ≥ 2 by 96 months, adjusted OR | C1 exam crepitus, KL ≥ 2 by 96 months, model 2 OR |
|---|---|---|---|---|---|
| `default` | 1,098 | 21.8% | 4/2 | 1.47 (1.22–1.77) | 1.59 (1.13–2.22) |
| `right_knee` | 579 | 23.5% | 4/2 | 1.44 (1.10–1.88) | 1.36 (0.87–2.13) |
| `progression_incidence` | 1,097 | 22.9% | 3/3 | 1.41 (1.17–1.70) | 1.58 (1.13–2.22) |
| `kl_outcomes99` | 1,104 | 21.9% | 4/2 | 1.46 (1.21–1.76) | 1.60 (1.14–2.23) |
| `adl_omitted` | 1,043 | 20.7% | 3/3 | 1.45 (1.20–1.75) | 1.59 (1.12–2.24) |
| `koos_missing_exclude` | 1,092 | 21.8% | 4/2 | 1.48 (1.23–1.79) | 1.61 (1.15–2.26) |
| `sign_missing_exclude` | 1,098 | 22.7% | 3/3 | 1.42 (1.18–1.71) | 1.59 (1.13–2.22) |
| `s2_levels` | 1,098 | 21.8% | 4/2 | 1.47 (1.22–1.77) | 1.59 (1.13–2.23) |
| `horizon_complete` | 1,098 | 21.8% | 4/2 | 1.47 (1.22–1.77) | 1.59 (1.13–2.22) |
| `roa_kl2_jsn` | 1,098 | 21.8% | 4/2 | 1.36 (1.10–1.67) | 1.26 (0.86–1.84) |
| `roa_replacement_ignore` | 1,098 | 21.8% | 4/2 | 1.45 (1.20–1.75) | 1.62 (1.15–2.27) |

Notes on this table:
- Every variant is graded against the abstract's both-knee, all-cohort targets. For `right_knee` and `progression_incidence` that is a different population, so their drift in group size is expected.
- Under the `exclude` rules the share's denominator is the KL 0–1 knees with a known status. For `sign_missing_exclude` that is about 4,840 knees, not 5,028.
- `horizon_complete` cannot change the KL ≥ 2 outcome: OUTCOMES99 carries ROA forward, so a case always has a known 96-month value. It does change SOA. G1's adjusted SOA by 96 months goes from 1.89 (1.53–2.34) to 1.76 (1.41–2.19), and the C1 exam OR (model 2) from 1.36 (0.95–1.96) to 1.34 (0.91–1.97).

The full text should say which choice explains the extra ~200 knees (TODO.md). The abstract's 27% also implies a KL 0–1 denominator of about 4,870, smaller than our 5,028, so the gap is not only in the numerator.

**Enrichment (G1):** the group does enrich for progression, as Mahmoudian found.

| Outcome | Early OA, cases/knees | Controls, cases/knees | Crude OR | Adjusted OR (age, sex, BMI) |
|---|---|---|---|---|
| KL ≥ 2 by 48 months | 145/932 | 332/3,517 | 1.79 (1.45–2.20) | 1.54 (1.24–1.92) |
| KL ≥ 2 by 96 months | 225/792 | 563/3,009 | 1.70 (1.43–2.03) | 1.47 (1.22–1.77) |
| SOA by 48 months | 110/911 | 189/3,467 | 2.39 (1.87–3.05) | 2.04 (1.57–2.64) |
| SOA by 96 months | 174/774 | 339/2,972 | 2.21 (1.81–2.70) | 1.89 (1.53–2.34) |

Mahmoudian's abstract gives ranges over undefined outcomes: structural 1.1–1.4, clinical 2.1–2.5. Our adjusted KL ≥ 2 ORs (1.47–1.54) are above the structural range. Our adjusted SOA ORs (1.89–2.04) are below the clinical range; only the crude SOA ORs (2.21–2.39) fall inside it.

### Crepitus within early OA (Part 2)

- Model 1: age, sex and BMI.
- Model 2: Model 1 plus the other crepitus measure.

**Framing 1 (C1), within the 1,098 early-OA knees: exam crepitus vs tenderness only.**

| Outcome | Crepitus, cases/knees | Tenderness only, cases/knees | Exam, model 1 | Exam, model 2 | Self-report (any vs never), model 2 |
|---|---|---|---|---|---|
| KL ≥ 2 by 48 months | 88/504 | 57/428 | 1.31 (0.91–1.90) | 1.30 (0.90–1.89) | 1.13 (0.75–1.71) |
| KL ≥ 2 by 96 months | 144/443 | 81/349 | 1.60 (1.15–2.24) | 1.59 (1.13–2.22) | 1.11 (0.78–1.59) |
| SOA by 48 months | 64/496 | 46/415 | 1.09 (0.72–1.66) | 1.08 (0.71–1.64) | 1.22 (0.77–1.94) |
| SOA by 96 months | 108/429 | 66/345 | 1.37 (0.96–1.97) | 1.36 (0.95–1.96) | 1.08 (0.74–1.59) |

**Framing 2 (C2), within the 1,674 KL 0–1 knees meeting the KOOS criterion with an exam: crepitus vs none.**

| Outcome | Crepitus, cases/knees | No crepitus, cases/knees | Exam, model 1 | Exam, model 2 | Self-report (any vs never), model 2 |
|---|---|---|---|---|---|
| KL ≥ 2 by 48 months | 88/504 | 130/905 | 1.12 (0.82–1.53) | 1.12 (0.82–1.53) | 1.01 (0.73–1.41) |
| KL ≥ 2 by 96 months | 144/443 | 189/745 | 1.32 (1.01–1.72) | 1.32 (1.01–1.73) | 0.94 (0.70–1.25) |
| SOA by 48 months | 64/496 | 101/879 | 1.00 (0.70–1.42) | 0.98 (0.68–1.40) | 1.15 (0.79–1.67) |
| SOA by 96 months | 108/429 | 149/730 | 1.19 (0.89–1.59) | 1.20 (0.89–1.62) | 0.91 (0.66–1.23) |

**Reading:**
- In early-stage OA, crepitus on examination enriches for incident radiographic OA by 96 months:
  - against tenderness only, OR 1.6;
  - against no crepitus among KL 0–1 knees meeting the KOOS criterion, OR 1.3.
- It is unchanged by adjusting for self-report.
- The 48-month and SOA estimates point the same way but their CIs include 1.
- Self-reported crepitus adds nothing within early OA (ORs 0.9–1.2; five levels in `s2_levels` show no gradient). In the whole Lo 2018 cohort, by contrast, it predicts SOA.
- With KL ≥ 2 and joint-space narrowing as the outcome (`roa_kl2_jsn`), the exam OR falls to 1.26 (0.86–1.84). The association is weaker when incidence also requires narrowing.
- The right-knee variant (579 knees) has the same direction with a wider CI.
