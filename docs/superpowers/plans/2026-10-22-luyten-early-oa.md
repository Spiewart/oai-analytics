# Crepitus in Luyten Early-Stage Knee OA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** First, replicate Mahmoudian 2021's early-stage knee OA group (the Luyten 2018 criteria) in OAI. Then test whether exam crepitus and self-reported crepitus enrich that group for incident KL ≥ 2 and incident SOA by 48 and 96 months. Both framings are tested: full Luyten (crepitus vs tenderness only) and KL 0–1 + KOOS (crepitus vs none).

**Architecture:** A new analysis, `analyses/luyten_early_oa/`, works on knees (both knees, clustered within person). It has three steps:
- `cohort` (Python): baseline knees, the criteria, outcomes and group metrics;
- `models` (R): enrichment table G1, Framing 1 table C1, Framing 2 table C2;
- `compare` (Python): grades the group against the Mahmoudian 2021 abstract.

The outcomes reuse `oai.derive.incident_soa` (`soa_status`, `roa_from_outcomes99`), run once per side through a side-swapped `Resolved`.

**Tech Stack:** Python ≥ 3.11 (uv, polars, pytest), R (renv, geepack, `oaimodels`).

**Spec:** `docs/superpowers/specs/2026-10-22-luyten-early-oa-design.md`

## Global Constraints

- Branch `claude/luyten-early-oa`, cut from `origin/main`. Commits carry the `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` trailer. No OAI data goes in git.
- The unit is the knee. Both knees of all enrollees are included unless a variant says otherwise. Models cluster on `ID` with `corstr = "exchangeable"`.
- Every subscale and exam column is read from the knee's own side. That includes `V00WOMADL{side}` and `V00KSX{side}KN2`. `V00KOOSQOL` is the only person-level input.
- Keys shared with `analyses/crepitus_soa_longterm/assumptions.toml` are copied verbatim (value, status, source, choices). A test fails if they drift.
- Mahmoudian targets come from the abstract only. Their outcome ORs are ranges with undefined outcomes, so they go in the README, not in `published.toml`.
- Exposure levels in metric keys:
  - exam crepitus: `yes` / `no`;
  - Framing 1 reference: `jlt_only`;
  - S2: `any` / `never` (`s2.levels` variant: `never` … `always`).
- Outcome keys are `roa48`, `roa96`, `soa48`, `soa96`.
- Shared modules and other analyses' outputs do not change. `oai run crepitus_soa_longterm --step cohort` gives identical `metrics_cohort.csv` before and after.

## Review Focus

1. **A knee with one KOOS subscale missing.** Under `luyten.koos_missing = "not_met"` the missing subscale counts as not ≤ 85, so the knee needs two of the remaining three. Under `"exclude"` the knee leaves the denominator. → Task 2 `test_koos_missing_rules`.
2. **Tenderness present, crepitus exam missing.** The knee meets the sign criterion (Luyten group), but its Framing 1 exposure is null, so it is not in C1. It is not in C2 either (exam required). → Task 2 `test_missing_crepitus_with_tenderness`.
3. **Person-level QoL with one painful knee.** Both knees get the same QoL. Only the knee-specific subscales differ, so one knee can meet KOOS and the other not. → Task 2 `test_qol_is_shared_but_knees_differ`.
4. **ROA unknown at 96 months, no earlier case.** The knee drops out of the `roa96` model under `known_or_case`, but stays in `roa48` if 48-month ROA is known. A knee that became a case at 24 months stays in both. → Task 3 `test_outcome_selection_by_horizon`.
5. **Left knee read from left columns.** A fixture participant whose right and left values differ on every input gets different criteria per knee. → Task 3 `test_left_knee_uses_left_columns`.

## File Map

| Path | Responsibility | Task |
|---|---|---|
| `analyses/luyten_early_oa/{analysis.toml,assumptions.toml,ASSUMPTIONS.md,published.toml,README.md}`, placeholder step files | Manifest, ledger, targets, docs | 1 |
| `tests/test_luyten_definition.py`, `tests/test_analyses.py`, `README.md` | Ledger checks; analysis list | 1 |
| `analyses/luyten_early_oa/luyten.py`, `tests/test_luyten_criteria.py` | Baseline knees, criteria, group metrics | 2 |
| `analyses/luyten_early_oa/{luyten.py,build_frame.py}`, `tests/test_luyten_build.py`, `tests/fixtures/oai_lo2018/AllClinical00.txt` | Outcomes, knee frame, step `cohort` | 3 |
| `analyses/luyten_early_oa/models.R` | Step `models`: G1, C1, C2 | 4 |
| `analyses/luyten_early_oa/compare.py`, `tests/test_luyten_realdata.py`, `README.md`, `TODO.md`, `analyses/crepitus/LITERATURE.md` | Step `compare`, real-data run, variants, results | 5 |

---

### Task 1: Scaffold, ledger and targets

**Files:**
- Create: `analyses/luyten_early_oa/{analysis.toml,assumptions.toml,published.toml,README.md}`, the generated `ASSUMPTIONS.md`, and placeholder `build_frame.py`, `models.R` and `compare.py` (each exits non-zero with "not implemented")
- Modify: `tests/test_analyses.py` (add `"luyten_early_oa"`), `README.md` (Analyses row)
- Test: `tests/test_luyten_definition.py`

**Interfaces:**
- Produces:
  - Steps:
    - `cohort` (python, `build_frame.py`);
    - `models` (r, `models.R`, needs cohort);
    - `compare` (python, `compare.py`, needs models).
  - Inputs:
    - `enrollees`, `outcomes:99`, `kxr_sq_bu:00`;
    - `allclinical:00`, `allclinical:01`, `allclinical:03`, `allclinical:05`, `allclinical:06`, `allclinical:08`, `allclinical:10`;
    - `kxr_sq_bu:01` … `kxr_sq_bu:06`, which `soa_status` reads.
  - Aggregate outputs: `flow.csv`, `table_*.csv`, `metrics_*.csv`, `comparison.csv`, `assumptions.resolved.json`.
  - Inherited keys, verbatim from `crepitus_soa_longterm`:
    - `cohort.reading_project`;
    - `outcomes.pain_baseline_item`, `outcomes.pain_followup_item`;
    - `outcomes.arthroplasty_timing`, `outcomes.soa_missing`, `outcomes.replacement_counts`, `outcomes.missing_visit_days`;
    - `outcomes.roa_source`, `outcomes.roa_definition`, `outcomes.roa_unread`, `outcomes.roa_rule`;
    - `horizon.selection`, `model.corstr`.
  - New keys:
    - `cohort.knees` = `"both"` (confirmed: abstract counts knees; choices `both`, `right`);
    - `cohort.cohorts` = `"all"` (assumed: abstract's 4,796; choices `all`, `progression_incidence`);
    - `outcomes.arthroplasty_scope` = `"knee"` (assumed: the knee's own replacement; choices `knee`, `either`). Not inherited, because `"right"` means the cohort side there;
    - `periods.horizon` = `"10"` (confirmed: spec, 96 months);
    - `outcomes.roa_replacement` = `"event"` (assumed: replacing a KL 0–1 knee implies it progressed; choices `event`, `ignore`). `soa_status` already counts a replacement as SOA;
    - `luyten.kl_source` = `"project15"` (assumed; choices `project15`, `outcomes99`);
    - `luyten.koos_cutoff` = 85 (confirmed: "equal or less than 85");
    - `luyten.koos_min` = 2 (confirmed);
    - `luyten.adl_source` = `"womac_function"` (assumed: no KOOS daily-living subscale in the release; choices `womac_function`, `omit`);
    - `luyten.koos_missing` = `"not_met"` (open; choices `not_met`, `exclude`);
    - `luyten.sign_missing` = `"not_met"` (open; choices `not_met`, `exclude`);
    - `exposure.s2_coding` = `"any"` (assumed; choices `any`, `levels`);
    - `model.covariates` = `["age", "sex", "bmi"]` (confirmed: spec).
  - Variants:
    - `right_knee`, `progression_incidence`;
    - `kl_outcomes99`, `adl_omitted`;
    - `koos_missing_exclude`, `sign_missing_exclude`;
    - `s2_levels`, `horizon_complete`, `roa_kl2_jsn`, `roa_replacement_ignore`.
  - `published.toml [default]`:
    - `g.knees` 1315;
    - `g.share` `{ value = 0.27, tol = 0.005 }`;
    - `g.early.age_mean` 59.2, `g.control.age_mean` 60.2;
    - `g.early.bmi_mean` 28.3, `g.control.bmi_mean` 26.8;
    - `[related]` `"g"` → every `luyten.*` key, plus `cohort.knees` and `cohort.cohorts`.

- [ ] **Step 1: Write the failing tests:**
  - `test_manifest_and_assumptions_load`: the three step ids, and every new key present.
  - `test_inherited_decisions_match_longterm`: for each inherited key, value, status and choices equal those in `load_assumptions(analyses/crepitus_soa_longterm).items[key]`.
  - `test_enumerated_assumptions_reject_typos`: parametrized over the keys with `choices`.
  - `test_variants_resolve`: every variant resolves with `oai.assumptions` and changes only the keys it names.
- [ ] **Step 2: Run** `uv run pytest tests/test_luyten_definition.py -v`. Expected: FAIL (analysis missing).
- [ ] **Step 3: Write the files**, then run `uv run oai assumptions luyten_early_oa --write`.
- [ ] **Step 4: Run** `uv run pytest tests/test_luyten_definition.py tests/test_analyses.py tests/test_assumptions_ledgers.py -q`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(luyten_early_oa): manifest, ledger and Mahmoudian 2021 group targets`.

### Task 2: Baseline knees and the Luyten criteria

**Files:**
- Create: `analyses/luyten_early_oa/luyten.py`
- Test: `tests/test_luyten_criteria.py` (inline frames)

**Interfaces:**
- Consumes: `oai.derive.crepitus.crepitus_values`, `oai.derive.knee.find_col`, `oai.loader.read_table`, `mahmoudian.tf_readings` (imported from `analyses/exam_crepitus_soa`, as Lo 2018 is imported elsewhere).
- Produces:
  - `KOOS = ("pain", "symptoms", "adl", "qol")`.
  - `baseline_knees(A) -> pl.DataFrame`: one row per enrollee and side (both sides, or the right only under `cohort.knees = "right"`; cohorts 1–2 only under `progression_incidence`). Columns:
    - `ID, SIDE, cohort, age, sex, bmi`;
    - `kl0` (`luyten.kl_source`: Project 15 `V00XRKL`, or OUTCOMES99 `V99E{side}XIOA` 1 → KL ≥ 2, 2–9 → KL 0–1, as a 0/2 code);
    - `pain, symptoms, adl, qol` (Float64; `adl = 100 − V00WOMADL{side} × 100 / 68`, or null under `adl_source = "omit"`);
    - `exam0, s2_0` (Int64 from `crepitus_values`), `jlt_m, jlt_l` (Int64).
  - `criteria(knees, A) -> pl.DataFrame`: adds these columns:
    - `koos_n` (Int64: subscales ≤ cutoff; under `omit`, `adl` is not counted);
    - `koos_ok`, `sign_ok`, `kl01`, `luyten`, `kl01_koos` (Boolean; null where the knee leaves the denominator under an `exclude` rule);
    - `sign_group` (`"crepitus_jlt"`, `"crepitus_only"`, `"jlt_only"`, or null when `exam0` is null);
    - `f1_exposure` (Int64: 1 for crepitus, 0 for `jlt_only`; null outside the Luyten group or when `exam0` is null);
    - `f2_exposure` (Int64: `exam0` within `kl01_koos`, null elsewhere).
  - `group_metrics(knees) -> pl.DataFrame` (`metric, value`), with keys:
    - `g.knees`, `g.persons`, `g.kl01`, `g.share` (`g.knees / g.kl01`), `g.kl01_koos`;
    - `g.early.age_mean`, `g.control.age_mean`, `g.early.bmi_mean`, `g.control.bmi_mean`, `g.early.women`, `g.control.women` (controls = `kl01 & ~luyten`);
    - `g.sign.crepitus_jlt`, `g.sign.crepitus_only`, `g.sign.jlt_only`.

- [ ] **Step 1: Write the failing tests** on inline frames built with a `knee(**overrides)` helper in the test file:
  - `test_luyten_needs_all_three`: KL 1, pain 80, symptoms 80, tenderness 1 → `luyten`. The same knee with KL 2, or with only pain ≤ 85, or with no sign → not `luyten`.
  - `test_cutoff_is_inclusive`: pain 85.0 and symptoms 85.0 → `koos_ok`; 85.1 and 85.1 → not.
  - `test_koos_missing_rules`: pain 80, symptoms null, adl 80, qol 90. Under `not_met`, `koos_n == 2` and `koos_ok`. With adl 90 instead, `koos_n == 1` and not `koos_ok`. Under `exclude`, `koos_ok` is null and the knee is outside `g.kl01`.
  - `test_adl_omitted`: under `adl_source = "omit"`, adl ≤ 85 does not count.
  - `test_missing_crepitus_with_tenderness`: `exam0` null, `jlt_m` 1, KOOS met, KL 0 → `luyten`; `sign_group`, `f1_exposure` and `f2_exposure` null.
  - `test_sign_groups`: crepitus and tenderness → `crepitus_jlt`, `f1_exposure` 1; tenderness only → `jlt_only`, 0; `f2_exposure` equals `exam0` in `kl01_koos` knees whatever the sign.
  - `test_qol_is_shared_but_knees_differ`: one person, QoL 70 on both knees. The right knee has pain 70 and the left pain 95 → right `koos_ok`, left not.
  - `test_group_metrics_keys`: keys equal the list above, and `g.share == g.knees / g.kl01`.
- [ ] **Step 2: Run** `uv run pytest tests/test_luyten_criteria.py -v`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement** `baseline_knees`, `criteria` and `group_metrics`.
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit** `feat(luyten_early_oa): baseline knees, Luyten 2018 criteria and group metrics`.

### Task 3: Outcomes, knee frame and step `cohort`

**Files:**
- Modify: `analyses/luyten_early_oa/luyten.py`, `build_frame.py` (replace the placeholder)
- Modify: `tests/fixtures/oai_lo2018/AllClinical00.txt`. Add the columns `V00KOOSKPR`, `V00KOOSKPL`, `V00KOOSYMR`, `V00KOOSYML`, `V00WOMADLR`, `V00WOMADLL`, `V00KOOSQOL`, `V00RKMTTPN`, `V00RKLTTPN`, `V00LKMTTPN`, `V00LKLTTPN`, with values for the existing 18 participants and no new rows. Existing tests' counts must not change.
- Test: `tests/test_luyten_build.py`

**Interfaces:**
- Consumes: Task 2; `incident_soa.soa_status`, `incident_soa.setting`.
- Produces:
  - `for_side(A, side) -> Resolved`: `dataclasses.replace(A, values={**A.values, "cohort.side": side})`.
  - `knee_outcomes(A) -> pl.DataFrame`: `ID, SIDE, roa48, roa96, soa48, soa96` (Boolean, null when unknown under `horizon.selection`).
    - From `soa_status(for_side(A, side))` for each side in the cohort. The ROA series is `roa`, or `roa | replaced` under `outcomes.roa_replacement = "event"`.
    - `roaH` / `soaH`: True if any visit ≤ H is True. False if the visit-H value is known and no earlier one is True. Otherwise null.
    - Under `"complete"`, a case whose visit-H value is null is also null.
    - H is `"06"` for 48 months and `"10"` for 96 months.
  - `knee_frame(A) -> pl.DataFrame`: `criteria(baseline_knees(A))` joined to `knee_outcomes(A)`, minus knees replaced at baseline (`replaced` at V00).
  - `flow(knees) -> pl.DataFrame` (`step, knees, persons`), with steps:
    - `all`, `replaced_at_baseline`, `kl_read`, `kl01`;
    - `kl01_koos`, `luyten`, `f1`, `f2`.
  - `build_frame.py` writes:
    - `$OAI_FRAME_DIR/knees.parquet`;
    - `$OAI_RESULTS_DIR/flow.csv`;
    - `$OAI_RESULTS_DIR/metrics_cohort.csv`, with `group_metrics` plus case counts `o.<frame>.<outcome>.<level>.cases` and `.n`. Frames: `early` / `control`, `f1` (`yes` / `jlt_only`), `f2` (`yes` / `no`).

- [ ] **Step 1: Write the failing tests:**
  - `test_outcome_selection_by_horizon` (inline `soa_status`-shaped frames through the H-rule helper):
    - case at V03 → `soa48` and `soa96` True;
    - V06 False and V10 null, no case → `soa48` False, `soa96` null;
    - V06 null and V10 False → `soa48` null, `soa96` False;
    - under `complete`, a V03 case with V10 null → `soa96` null;
    - a knee replaced at V05 with `roa` False through V03 and null after → `roa96` True under `event`, and null under `ignore`.
  - `test_left_knee_uses_left_columns`: fixture participant 2000003 has right pain 95 and left pain 60, right symptoms 95 and left symptoms 70, left tenderness 1 → left `luyten`, right not.
  - `test_frame_one_row_per_knee`: on the fixture, `(ID, SIDE)` is unique; `right_knee` gives SIDE `"R"` only.
  - `test_replaced_at_baseline_excluded`: a fixture knee with `V99E?KBLRP` = 1 is absent, and is counted in the flow's `replaced_at_baseline`.
- [ ] **Step 2: Run** `uv run pytest tests/test_luyten_build.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement**, and extend the fixture.
- [ ] **Step 4: Run** `uv run pytest -q`, which covers the whole suite because the fixture changed. Then run `uv run oai run luyten_early_oa --step cohort`, and confirm `crepitus_soa_longterm`'s `metrics_cohort.csv` is unchanged (`cmp` against a copy taken first). Expected: PASS. On the release, `g.knees` is about 1,098, `g.kl01` about 5,028, and `g.kl01_koos` about 1,681 (the preview). The `o.f1.roa96` cases are about 142 (yes) and 79 (`jlt_only`) before selection.
- [ ] **Step 5: Commit** `feat(luyten_early_oa): incident KL >= 2 and SOA by 48 and 96 months per knee, knee frame and flow`.

### Task 4: Models (G1, C1, C2)

**Files:**
- Create: `analyses/luyten_early_oa/models.R` (replace the placeholder)

**Interfaces:**
- Consumes:
  - `knees.parquet`: `ID`, `luyten`, `kl01`, `kl01_koos`, `f1_exposure`, `f2_exposure`, `exam0`, `s2_0`, `age`, `sex`, `bmi`, the four outcomes;
  - `oaimodels::{read_frame, assumptions, fit_knee_gee}`.
- Produces: `table_g1.csv`, `table_c1.csv`, `table_c2.csv` and `metrics_models.csv`.
  - Table rows: `outcome, exposure, model, term, n, events, or, lo, hi`.
  - Metric keys: `<table>.<outcome>.<term>.<model>`, each with `.lo` and `.hi`.
    - Tables: `g1`, `c1`, `c2`.
    - Terms: `early`, `exam`, `s2_any` (under `s2_levels`, `s2_rarely` … `s2_always`).
    - Models: `or_unadj`, `or_adj`, `or_adj_other`.

Model specifications (each fit on knees with the outcome non-null and every term present; data ordered by `ID`; `fit_knee_gee(d, rhs, outcome, term, corstr = A[["model.corstr"]])`):
- **G1** (all `kl01` knees, term `early` = `luyten`):
  - `early`;
  - `early + age + sex + bmi`.
- **C1** (knees with `f1_exposure` non-null):
  - Exam: `f1_exposure`; `f1_exposure + age + sex + bmi`; and the adjusted model `+ s2` (`or_adj_other`).
  - S2: the same three with `s2` as the term and `f1_exposure` as the other measure.
- **C2:** as C1, with `f2_exposure` on knees where it is non-null.
- **S2 coding:** `s2` is `as.integer(s2_0 >= 1)`, or `factor(s2_0)` under `exposure.s2_coding = "levels"`.
- **Sparse groups:** where a group has fewer than 5 events, write the row with `or = NA`. Do not fail.

- [ ] **Step 1: Run** `uv run oai run luyten_early_oa --step models` before writing the file. Expected: FAIL (placeholder).
- [ ] **Step 2: Implement** `models.R`.
- [ ] **Step 3: Run** the step. Expected: it completes, and `metrics_models.csv` has `g1`, `c1` and `c2` keys for all four outcomes. The crude C1 `roa96` OR is in the direction of the preview (about 1.6).
- [ ] **Step 4: Commit** `feat(luyten_early_oa): enrichment (G1) and crepitus models in both framings (C1, C2)`.

### Task 5: Grading, real-data run, variants and results

**Files:**
- Create: `analyses/luyten_early_oa/compare.py` (copied from `exam_crepitus_soa`), `tests/test_luyten_realdata.py`
- Modify:
  - `analyses/luyten_early_oa/README.md` (Results);
  - `TODO.md`;
  - `analyses/crepitus/LITERATURE.md` (the Mahmoudian 2021 row and the "Progressive OA" coverage line).

- [ ] **Step 1: Write the real-data test** (`realdata`; skipped without R):
  - `run_analysis("luyten_early_oa")` completes;
  - `comparison.csv` has no `missing` verdicts;
  - the three `table_*` files exist;
  - the egress check passes.
- [ ] **Step 2: Run** `uv run pytest tests/test_luyten_realdata.py -m realdata -v`. Expected: FAIL until `compare.py` exists, then PASS.
- [ ] **Step 3: Run every variant.** Record in the README:
  - per variant: the `g.*` replicated / drift count and `g.knees` / `g.share`, which says which choices move us toward 1,315;
  - G1's adjusted ORs beside Mahmoudian's ranges (structural 1.1–1.4, clinical 2.1–2.5);
  - C1 and C2: cases/n by level and Model 1 / Model 2 ORs for all four outcomes, under the default and `s2_levels`.
- [ ] **Step 4: File** in `TODO.md` (`<!-- skip -->`):
  - get the Mahmoudian 2021 full text, for the progression definitions, Table 1 and the KOOS daily-living source, then extend `published.toml`;
  - any ledger choice where a variant matches the abstract better than the default.
- [ ] **Step 5: Run** `uv run pytest -q` and the R suite. Expected: PASS.
- [ ] **Step 6: Commit** `feat(luyten_early_oa): graded early-OA group and crepitus enrichment results to 96 months`.
