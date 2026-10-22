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

Not yet run.
