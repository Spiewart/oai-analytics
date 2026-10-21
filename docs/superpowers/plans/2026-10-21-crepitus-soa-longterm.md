# Crepitus → Incident Symptomatic OA to 96 and 120 Months Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the S2 and exam-crepitus analyses of incident symptomatic OA past 48 months.
- **96 months is primary:** combined Project 15 and 37 incidence data are documented as complete there.
- **120 months is a sensitivity analysis:** Project 43 coverage is undocumented.
- **ROA status by visit** comes from OUTCOMES99.

**Architecture:** `oai.derive.incident_soa` gains three things. Every new setting has a default that reproduces today's analyses:
- a visit schedule set by `periods.horizon`;
- an OUTCOMES99 ROA source;
- an exam carry-forward option.

A new analysis, `analyses/crepitus_soa_longterm/`, has two steps:
- `cohort` (Python): frames for both measures and a coverage report;
- `models` (R): Tables L1–L4 for S2 and exam.

A real-data regression test pins the 48-month settings to the existing analyses' outputs.

**Tech Stack:** Python ≥ 3.11 (uv, polars, pytest), R (renv, geepack).

**Spec:** `docs/superpowers/specs/2026-10-21-crepitus-soa-longterm-design.md`

## Global Constraints

- The Global Constraints of `docs/superpowers/plans/2026-10-21-exam-crepitus-incident-soa.md` apply. In particular, the Lo 2018 and exam-crepitus outputs must not change. Re-check them byte-for-byte after Tasks 1 and 2.
- Every new `incident_soa` setting is read with `A.get(key, default)`, using the default that reproduces current behavior. `lo2018_crepitus` and `exam_crepitus_soa` need no ledger change.
- Visit codes and months:

| Visit | V01 | V03 | V05 | V06 | V08 | V10 | V12 |
|---|---|---|---|---|---|---|---|
| Months | 12 | 24 | 36 | 48 | 72 | 96 | 120 |
| `V99E?XIOA` incident code | 3 | 4 | 5 | 6 | 7 | 8 | 9 |

  Code 1 = KL ≥ 2 at baseline; code 2 = no incidence. `V99E?XIOAN` uses the same codes.
- Ledger keys new to this analysis carry `status = "open"` unless the spec calls them documented.

## Review Focus

1. **A knee with KL ≥ 2 at baseline and no follow-up readings.** With `outcomes.roa_source = "outcomes99"`, it has ROA at V08, V10 and V12, so frequent pain there is SOA. → Task 2 `test_outcomes99_roa_is_carried_forward`.
2. **Horizon past 48 months with `roa_source = "readings"`.** Project 15 has no readings after V06, so this must raise, not silently produce null outcomes. → Task 2 `test_readings_refused_past_48_months`.
3. **Exam exposure for the V08→V10 period.** It is the V06 exam under `carry_v06`; under `"none"` the period is dropped and counted in `missing_crepitus`. → Task 1 `test_exam_carry_forward`.
4. **Defaults reproduce the 48-month analyses exactly**, including the four-period schedule and no period term. → Task 1 `test_default_schedule_is_lo2018s`, and Task 5's real-data regression test.
5. **Someone who left the study after 48 months.** They are not a non-event in the by-horizon logistic model (L3). They do contribute their observed periods to L1 and L2. → Task 3 `test_by_horizon_frame_needs_outcome_at_horizon`.

## File Map

| Path | Responsibility | Task |
|---|---|---|
| `src/oai/derive/incident_soa.py`, `tests/test_derive_incident_soa.py` | Horizon schedule, exam carry-forward | 1 |
| `src/oai/derive/incident_soa.py`, `tests/fixtures/oai_lo2018/*` (new `AllClinical08/10/12`, `kxr_sq_bu` unchanged, `OUTCOMES99` + `V99E?XIOA`/`XIOAN`), `tests/test_derive_incident_soa_outcomes99.py` | OUTCOMES99 ROA source | 2 |
| `analyses/crepitus_soa_longterm/{analysis.toml,assumptions.toml,ASSUMPTIONS.md,README.md,longterm.py,build_frame.py}`, `tests/test_longterm_*.py`, `tests/test_analyses.py`, `README.md` | Ledger, frames, coverage | 3 |
| `analyses/crepitus_soa_longterm/models.R` | Tables L1–L4 | 4 |
| `tests/test_longterm_realdata.py`, `analyses/crepitus_soa_longterm/README.md`, `TODO.md`, `analyses/crepitus/LITERATURE.md` | Regression anchor, run, results | 5 |

---

### Task 1: Visit schedule by horizon, and exam carry-forward

**Files:**
- Modify: `src/oai/derive/incident_soa.py`
- Test: `tests/test_derive_incident_soa.py`

**Interfaces:**
- Produces:
  - `ALL_EXPOSURE_VISITS = ("00", "01", "03", "05", "06", "08", "10")` and `ALL_OUTCOME_VISITS = ("01", "03", "05", "06", "08", "10", "12")`.
  - `schedule(horizon: str) -> pl.DataFrame`: columns `period` (1…), `start_visit`, `end_visit`, one row per pair with `end_visit <= horizon`. `schedule("06")` equals today's `PERIODS`.
  - `periods(...)` gains a `period` schedule from `A.get("periods.horizon", "06")`.
    - **Exam:** under `A.get("exposure.exam_after_48m", "carry_v06")`, the exam for start visits V08 and V10 is the V06 value with `carry_v06`, and null with `none`.
    - **S2:** S2 at V08 and V10 is read from those visits.
  - `crepitus_frame(A)` reads S2 and exam at every exposure visit of the schedule. A visit without an exam column contributes a null `exam_crepitus` (use `crepitus_values` per measure and join).
  - `four_year(...)` keeps its name and logic. Its outcome visits become the schedule's `end_visit`s.
- Defaults keep `EXPOSURE_VISITS`, `OUTCOME_VISITS`, `VISITS` and `PERIODS` as today's 48-month values, still exported.

- [ ] **Step 1: Write the failing tests:**
  - `test_default_schedule_is_lo2018s`: `schedule("06").equals(PERIODS)`; `schedule("10")["end_visit"].to_list() == ["01", "03", "05", "06", "08", "10"]`; `schedule("12").height == 7`.
  - `test_exam_carry_forward`: inline frames for one person through V10 (extend the `soa_helpers` builders with a `visits` argument). Exam `[0, 0, 0, 0, 1, None]` at V00–V10 (V08 and V10 have no exam). With horizon `"10"` and `carry_v06`, periods 5 and 6 have `exam == 1`. With `none`, `require=("exam_crepitus",)` drops period 6 and counts it in `missing_crepitus`.
- [ ] **Step 2: Run** `uv run pytest tests/test_derive_incident_soa.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q`. Then `uv run oai run lo2018_crepitus --step cohort` and `uv run oai run exam_crepitus_soa --step cohort`, and compare their frames and `metrics_cohort.csv` with copies saved before Step 3. Expected: PASS, identical.
- [ ] **Step 5: Commit** `feat(incident_soa): visit schedule by horizon and exam carry-forward past 48 months`.

### Task 2: ROA from OUTCOMES99

**Files:**
- Modify: `src/oai/derive/incident_soa.py`; the fixture: add `AllClinical08.txt`, `AllClinical10.txt` and `AllClinical12.txt` (VISDYS, frequent pain, S2; exam at V12), and the `V99ERXIOA`, `V99ELXIOA`, `V99ERXIOAN`, `V99ELXIOAN` columns to `OUTCOMES99.txt`
- Test: `tests/test_derive_incident_soa_outcomes99.py`

**Interfaces:**
- Produces:
  - `INCIDENT_CODE_VISIT = {3: "01", 4: "03", 5: "05", 6: "06", 7: "08", 8: "10", 9: "12"}`.
  - `roa_from_outcomes99(A) -> pl.DataFrame`: `ID, SIDE, visit, roa` for every schedule visit. `roa` is True if the code is 1, or an incident code whose visit is ≤ `visit`; False if code 2 or a later incident visit; null if missing.
    - Column `XIOA` when `A.get("outcomes.roa_definition", "kl2") == "kl2"`; `XIOAN` for `"kl2_jsn"`. For XIOAN, code 0 is null and code 2 means none.
  - `soa_status(A)`:
    - uses `roa_from_outcomes99` when `A.get("outcomes.roa_source", "readings") == "outcomes99"`;
    - takes KL from Project 15 at V00 for the cohort's `no_baseline_kl` step, as today;
    - covers every schedule visit;
    - raises `ValueError` naming the key when the horizon is past `"06"` with `roa_source = "readings"`.

- [ ] **Step 1: Save copies** of the Lo 2018 and exam cohort outputs (as in Task 1 Step 4).
- [ ] **Step 2: Write the failing tests:**
  - `test_outcomes99_roa_is_carried_forward`: participant 2000003 (KL 3 at baseline) and a new fixture code-1 knee have `roa == True` at V08, V10 and V12.
  - `test_incident_visit_sets_roa_from_then_on`: a code-7 knee has `roa` False at V06 and True at V08 and V10.
  - `test_readings_refused_past_48_months`: horizon `"10"` with `roa_source = "readings"` raises `ValueError` matching `outcomes.roa_source`.
  - `test_kl2_jsn_definition`: a knee with XIOA 4 and XIOAN 2 has ROA at V03 under `kl2` and none under `kl2_jsn`.
  - `test_followup_soa_at_96_months`: a fixture participant without SOA by 48 months, with code-1 ROA and frequent pain at V10, has `soa` True at V10.
- [ ] **Step 3: Run** `uv run pytest tests/test_derive_incident_soa_outcomes99.py -v`. Expected: FAIL.
- [ ] **Step 4: Implement**, and extend the fixture. Existing fixture participants get XIOA codes consistent with their Project 15 KL.
- [ ] **Step 5: Run** `uv run pytest -q` and the byte-for-byte check from Step 1. Expected: PASS, identical.
- [ ] **Step 6: Commit** `feat(incident_soa): radiographic OA by visit from OUTCOMES99, carried forward, to 120 months`.

### Task 3: Long-term analysis, ledger, frames and coverage

**Files:**
- Create:
  - `analyses/crepitus_soa_longterm/{analysis.toml,assumptions.toml,README.md,longterm.py,build_frame.py}`;
  - the generated `ASSUMPTIONS.md`;
  - a placeholder `models.R`.
- Modify: `tests/test_analyses.py`, `README.md`
- Test: `tests/test_longterm_definition.py`, `tests/test_longterm_build.py`

**Interfaces:**
- Produces:
  - Steps:
    - `cohort` (python, `build_frame.py`);
    - `models` (r, `models.R`, needs cohort).
  - Inputs: the `exam_crepitus_soa` inputs plus `allclinical:08`, `allclinical:10`, `allclinical:12`.
  - Ledger:
    - **Inherited:** every key shared with `analyses/lo2018_crepitus/assumptions.toml`, identical (parametrize the test over the intersection of the two ledgers). Exception: `outcomes.roa_rule` stays `"same_visit"` and is ignored under `outcomes99`.
    - **New keys:**

| Key | Value | Status | Choices |
|---|---|---|---|
| `periods.horizon` | `"10"` | assumed | `"06"`, `"10"`, `"12"` |
| `outcomes.roa_source` | `"outcomes99"` | assumed | `"readings"`, `"outcomes99"` |
| `outcomes.roa_definition` | `"kl2"` | open | `"kl2"`, `"kl2_jsn"` |
| `exposure.exam_after_48m` | `"carry_v06"` | open | `"carry_v06"`, `"none"` |
| `model.period_term` | `"factor"` | assumed | `"factor"`, `"none"` |

    - **Variants:**
      - `horizon_120`;
      - `roa_kl2_jsn`;
      - `exam_no_carry`;
      - `period_term_none`;
      - `lo2018_48m` (horizon `"06"`, `roa_source = "readings"`, `period_term = "none"`; the regression anchor).
  - `longterm.py`:
    - `frames_for(A, measure: str) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame, dict]`, returning `(periods, hazard, by_horizon, counts)` for `measure` in `{"koos_s2", "exam_crepitus"}`:
      - `periods`: the time-varying exposure frame (L1).
      - `hazard`: baseline exposure (`crep0`/`exam0`) repeated on each at-risk period, with `period` and `event` (L2).
      - `by_horizon`: one row per person with a known outcome at the horizon or an earlier case, with `event` (L3).
    - `coverage(A) -> pl.DataFrame`: `metric, value`, covering:
      - people with an outcome at each schedule visit;
      - Project 37 and Project 43 right-knee reads per subgroup;
      - knees whose ROA at V06 differs between Project 15 and OUTCOMES99.
  - `build_frame.py` writes:
    - `$OAI_FRAME_DIR/{s2,exam}_{periods,hazard,horizon}.parquet`;
    - `$OAI_RESULTS_DIR/flow.csv`, `metrics_cohort.csv` and `coverage.csv`.

- [ ] **Step 1: Write the failing tests:**
  - `test_manifest_and_assumptions_load` (steps, new keys, variants);
  - `test_inherited_decisions_match_lo2018` (parametrized over the ledger intersection, excluding `outcomes.roa_rule` with a comment);
  - `test_enumerated_assumptions_reject_typos`;
  - `test_frames_for_both_measures` (fixture: the three frames are non-empty; `hazard` has `crep0` or `exam0` constant within ID);
  - `test_by_horizon_frame_needs_outcome_at_horizon` (a fixture participant with no data after V06 and no earlier SOA is absent from `by_horizon`, but present in `periods`).
- [ ] **Step 2: Run** `uv run pytest tests/test_longterm_definition.py tests/test_longterm_build.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement**, then run `uv run oai assumptions crepitus_soa_longterm --write`.
- [ ] **Step 4: Run** the tests, then `uv run oai run crepitus_soa_longterm --step cohort`. Expected: PASS. On the release, the exam cases by 96 months number about 896 (655 + 241) before `by_horizon` drops people whose outcome at 96 months is unknown.
- [ ] **Step 5: Commit** `feat(crepitus_soa_longterm): ledger, frames for S2 and exam to 96/120 months, and coverage report`.

### Task 4: Models (Tables L1–L4)

**Files:**
- Create: `analyses/crepitus_soa_longterm/models.R`

**Interfaces:**
- Consumes: the six parquet frames; `oaimodels::{fit_knee_gee, fit_logit, read_frame, assumptions}`.
- Produces: `table_l1.csv`, `table_l2.csv`, `table_l3.csv` and `table_l4.csv`, with rows `measure, group, model, n, events, or, lo, hi` (S2 rows: one per level 1–4 vs never; exam rows: one). Also `metrics_models.csv`, with keys `l{1-4}.{s2|exam}.<group>.<level|exam>.<model>` plus `.lo` and `.hi`.
- Models:
  - **L1:** `fit_knee_gee` on `*_periods`, with right-hand side `exposure [+ factor(period)] [+ age + sex + bmi] [+ factor(crep)]` (the S2 term only for exam). The period term is present when `model.period_term = "factor"`.
  - **L2:** `fit_knee_gee` on `*_hazard`, the same right-hand sides with the baseline exposure.
  - **L3:** `fit_logit` on `*_horizon` (no period term).
  - **L4:** L2 within each baseline subgroup, plus the Wald p for exposure × subgroup from `anova()` on two nested `geepack::geeglm` fits; and L2 with both measures and their interaction (exam frame, `factor(crep0)` plus `exam0:I(crep0 >= 1)`).

- [ ] **Step 1: Run** `uv run oai run crepitus_soa_longterm --step models`. Expected: FAIL (placeholder).
- [ ] **Step 2: Implement.**
- [ ] **Step 3: Run** the step. Expected: it completes. `metrics_models.csv` has an `l1.exam.all.exam.or_adj` key, and the L3 exam OR at 96 months is consistent with the spec's preview direction (10.4% vs 7.6% new cases after 48 months).
- [ ] **Step 4: Commit** `feat(crepitus_soa_longterm): Tables L1-L4 for S2 and exam crepitus`.

### Task 5: Regression anchor, real-data run and results

**Files:**
- Create: `tests/test_longterm_realdata.py`
- Modify: `analyses/crepitus_soa_longterm/README.md`, `TODO.md`, `analyses/crepitus/LITERATURE.md`

- [ ] **Step 1: Write the real-data tests** (`realdata`; skipped without R):
  - `test_longterm_runs_and_egress_is_clean`: default run; all tables exist; the egress check passes.
  - `test_48_month_settings_reproduce_existing_analyses`: run the `lo2018_48m` variant, then compare against the existing analyses' default metrics:
    - the L1 exam ORs must equal `exam_crepitus_soa`'s `e1.exam.or_unadj`, `or_adj` and `or_adj_s2` within 1e-9;
    - the L1 S2 level ORs must equal `lo2018_crepitus`'s `t1.<level>.or_unadj` and `or_adj` within 1e-9;
    - `metrics_cohort` `obs.n` must equal both analyses'.
- [ ] **Step 2: Run** `uv run pytest tests/test_longterm_realdata.py -m realdata -v`. Expected: PASS once Tasks 1–4 are in.
- [ ] **Step 3: Run the variants** `horizon_120`, `roa_kl2_jsn`, `exam_no_carry` and `period_term_none`. Record in the README:
  - L1–L3 adjusted ORs for both measures at 96 months (default) and 120 months;
  - the coverage table;
  - how far ROA at 48 months differs between Project 15 and OUTCOMES99.
- [ ] **Step 4: File** a `TODO.md` item (`<!-- skip -->`) to ask OAI/NDA for Project 43's documentation (selection and reading protocol), with the 120-month results marked provisional until then. Update the LITERATURE coverage line for incident SOA.
- [ ] **Step 5: Run** `uv run pytest -q` and the R suite. Expected: PASS.
- [ ] **Step 6: Commit** `feat(crepitus_soa_longterm): results to 96 and 120 months, regression-anchored to the 48-month analyses`.
