# Crepitus and Device-Measured Activity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Test, in both directions, crepitus (exam and KOOS S2; absolute and change) against GT1M steps/day and MV and light minutes at 48 and 72 months. The reverse-direction outcomes are S2 at 72 and 96 months and new exam crepitus at 120 months.

**Architecture:** First, `walking_steps`' person-wave device helpers move to `oai.derive.devices`, unchanged. Then a new analysis, `analyses/crepitus_activity/`, with two steps:
- `cohort` (Python): writes a person frame (device waves, crepitus counts, covariates) and a knee frame (exam at 48 and 120 months), both to OAI_FRAME_DIR, plus aggregate flow and descriptives;
- `models` (R): Tables A1–A3 and B1–B3.

**Tech Stack:** Python ≥ 3.11 (uv, polars, pytest), R (renv, geepack, MASS, `oaimodels`).

**Spec:** `docs/superpowers/specs/2026-11-12-crepitus-activity-design.md`

## Global Constraints

- Branch `claude/crepitus-activity`, cut from `origin/main`. Commits carry the `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` trailer. No OAI data goes in git, and the step files never enter the repo. Participant-level frames go to OAI_FRAME_DIR only; results hold aggregates.
- `walking_steps` outputs must not change. `device.parquet` from `oai run walking_steps --step persons` is identical (`DataFrame.equals`) before and after Task 1.
- Device rules are `walking_steps`' (keys `device.*`, `steps.day_rule`, `sample.min_step_days`), copied verbatim. A test fails if they drift.
- Crepitus counts are Int64 0–2:
  - exam: `V##{R,L}KPFCRE == 1`;
  - S2: `V##KSX{R,L}KN2 >= 1`.

  With `crepitus.count_missing = "both_required"`, a person missing either knee has a null count.
- Activity scale: steps per 1,000/day; MV and light per 10 min/day. Activity names: `steps`, `mv_min`, `light_min`. Crepitus names: `exam`, `s2`.
- Metric keys: `<table>.<activity>.<crepitus>.<term>.<model>` with `.lo`, `.hi`, `.n`.
  - Terms: `per_knee`, `k1`, `k2`, `change`.
  - Models: `m1`, `m2`.

## Review Focus

1. **A person valid at 48 months but not at 72.** They are in A1 and B3's activity-at-48 term, and out of A2, A3 and every change term. → Task 3 `test_wave_validity_drives_inclusion`.
2. **One knee's S2 missing at 72 months.** The count is null under `both_required`, so the person leaves B1 and A3-concurrent. Under `available_knees` the count is taken over one knee. → Task 3 `test_count_missing_rules`.
3. **Steps null but counts valid.** These are the 11 people whose step file is empty. They stay in the MV and light models and leave the steps models only. → Task 3 `test_steps_missing_keeps_count_measures`.
4. **B3 knee eligibility.** A knee with exam crepitus at 48 months, or no 120-month exam, is excluded. A person contributes 0, 1 or 2 knees. → Task 3 `test_exam120_knee_frame`.
5. **Change sign convention.** Change = later minus earlier, for both activity and S2 count. → Task 3 `test_change_is_later_minus_earlier`.

## File Map

| Path | Responsibility | Task |
|---|---|---|
| `src/oai/derive/devices.py`, `analyses/walking_steps/devices.py`, `tests/test_derive_devices.py` | Shared person-wave device measures | 1 |
| `analyses/crepitus_activity/{analysis.toml,assumptions.toml,ASSUMPTIONS.md,README.md}`, placeholders, `tests/test_crepitus_activity_definition.py`, `tests/test_analyses.py`, `README.md` | Scaffold and ledger | 2 |
| `analyses/crepitus_activity/{activity.py,build_frame.py}`, `tests/test_crepitus_activity_build.py` | Frames, flow, descriptives | 3 |
| `analyses/crepitus_activity/models.R` | Tables A1–A3, B1–B3 | 4 |
| `tests/test_crepitus_activity_realdata.py`, `README.md` (analysis), `TODO.md`, `analyses/crepitus/LITERATURE.md` | Real-data run, variants, results | 5 |

---

### Task 1: Shared device measures

**Files:**
- Create: `src/oai/derive/devices.py`. Move into it `COUNT_MEASURES`, `step_bout_measures`, `step_bouts_daily`, `person_wave`, `DEVICE_KEYS` and `device_rules`, unchanged.
- Modify: `analyses/walking_steps/devices.py`. It re-exports them (`from oai.derive.devices import ...`) and keeps `combine`, `walker_definitions` and `either_week`.
- Test: `tests/test_derive_devices.py`

**Interfaces:**
- Produces:
  - `oai.derive.devices.person_wave(minutes, rules, cadences, min_step_days) -> pl.DataFrame`;
  - `device_rules(A) -> DeviceRules`;
  - `DEVICE_KEYS`.

- [ ] **Step 1: Save** `device.parquet` (from `$OAI_WORK_DIR/walking_steps/default/`) and `device_flow.csv` to the plan workspace.
- [ ] **Step 2: Write the failing test:**
  - `test_shared_module_is_walking_steps_module`: `oai.derive.devices.person_wave is devices.person_wave` (walking_steps' module imported via sys.path), and the same for `device_rules`.
- [ ] **Step 3: Run** `uv run pytest tests/test_derive_devices.py -v`. Expected: FAIL (no module).
- [ ] **Step 4: Move the code.**
- [ ] **Step 5: Run** `uv run pytest tests/test_derive_devices.py tests/test_walking_steps.py tests/test_steps.py -q`, then `uv run oai run walking_steps --step persons`, and compare against Step 1's copies. Expected: PASS; `device.parquet` equal; `device_flow.csv` identical.
- [ ] **Step 6: Commit** `refactor(devices): walking_steps person-wave device measures move to oai.derive.devices`.

### Task 2: Scaffold and ledger

**Files:**
- Create: `analyses/crepitus_activity/{analysis.toml,assumptions.toml,README.md}`, the generated `ASSUMPTIONS.md`, and placeholder `build_frame.py` and `models.R`
- Modify: `tests/test_analyses.py`, `README.md` (Analyses row)
- Test: `tests/test_crepitus_activity_definition.py`

**Interfaces:**
- Produces:
  - Steps:
    - `cohort` (python, `build_frame.py`);
    - `models` (r, `models.R`, needs cohort).
  - Inputs:
    - `enrollees`;
    - `allclinical:05`, `allclinical:06`, `allclinical:08`, `allclinical:10`, `allclinical:12`;
    - `acceldatabymin:06`, `acceldatabymin:08`;
    - `kxr_sq_bu:06`.
  - Outputs:
    - `flow.csv`, `table_*.csv`, `metrics_*.csv`, `descriptives.csv`, `assumptions.resolved.json`.
  - Inherited keys, verbatim from `walking_steps`: every `device.*`, `steps.day_rule`, `sample.min_step_days`.
  - New keys:
    - `crepitus.count_missing` = `"both_required"` (assumed; choices `both_required`, `available_knees`);
    - `crepitus.s2_cut` = 1 (assumed: "at least rarely", as in the Luyten and dual analyses);
    - `activity.measures` = `["steps", "mv_min", "light_min"]` (confirmed: spec);
    - `activity.transform` = `"none"` (assumed; choices `none`, `log`; log is `log(x + 1)`, effects as ratios);
    - `model.covariates` = `["age", "sex", "bmi", "wear_hr"]` (confirmed: spec);
    - `model.covariates_2` = `["kl_max", "womac_pain_max"]` (confirmed: spec);
    - `model.corstr` = `"exchangeable"` (B3).
  - Variants: `available_knees`, `log_activity`, `s2_cut_2` (`crepitus.s2_cut` = 2, "sometimes" or more).

- [ ] **Step 1: Write the failing tests:**
  - `test_manifest_and_assumptions_load` (the two step ids; every new key);
  - `test_device_keys_match_walking_steps` (parametrized; value, status, source and choices);
  - `test_enumerated_assumptions_reject_typos`;
  - `test_variants_resolve` (each changes only its keys).
- [ ] **Step 2: Run** `uv run pytest tests/test_crepitus_activity_definition.py -v`. Expected: FAIL.
- [ ] **Step 3: Write the files.** Extract the inherited ledger blocks with a script, not by hand. Then run `uv run oai assumptions crepitus_activity --write`.
- [ ] **Step 4: Run** `uv run pytest tests/test_crepitus_activity_definition.py tests/test_analyses.py tests/test_assumptions_ledgers.py -q`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(crepitus_activity): manifest and ledger, device rules inherited from walking_steps`.

### Task 3: Frames, flow and descriptives

**Files:**
- Create: `analyses/crepitus_activity/activity.py`, `build_frame.py` (replace the placeholder)
- Test: `tests/test_crepitus_activity_build.py` (inline frames; IO stays in thin readers)

**Interfaces:**
- Consumes: Task 1 (`person_wave`, `device_rules`), `oai.derive.accel.read_minutes(visit, steps=True)`, `oai.derive.crepitus.crepitus_values`, `oai.derive.knee.xray_readings`.
- Produces:
  - `crepitus_counts(knees: pl.DataFrame, A) -> pl.DataFrame`: from `ID, SIDE, visit, koos_s2, exam_crepitus` to `ID, visit, s2_count, exam_count`. Each count is Int64 or null under `crepitus.count_missing`.
  - `person_frame(device: pl.DataFrame, counts: pl.DataFrame, covariates: pl.DataFrame, A) -> pl.DataFrame`: one row per person valid at 48 months. Columns:
    - `ID`, `valid72` (Boolean);
    - for each activity measure m: `m_48`, `m_72` (null when not valid at 72, or when steps are null for `steps`), `m_change` (= `m_72 − m_48`);
    - `wear_hr_48`, `wear_hr_72`;
    - `s2_36`, `s2_48`, `s2_72`, `s2_96`, `exam_36`, `exam_48`;
    - `s2_change_48_72`, `s2_change_36_48`, `exam_change_36_48`;
    - `age`, `sex`, `bmi` (48 months: `V06AGE`, `P02SEX`, `V06BMI`), `kl_max` (higher Project 15 V06 KL of the two knees), `womac_pain_max` (higher `V06WOMKP{R,L}`).
  - `exam120_knees(knees: pl.DataFrame, persons: pl.DataFrame) -> pl.DataFrame`: `ID, SIDE, event` (exam crepitus at 120 months), knees with exam 0 at 48 months and non-null at 120 months, joined to the person's activity and covariates.
  - `flow_and_descriptives(persons, knees) -> (flow, descriptives)`:
    - flow: valid at 48 months, at both waves, with each crepitus measure, B3 knees and events;
    - descriptives: n, mean and SD of each activity measure at 48 and 72 months by `exam_48` and `s2_48` level. Aggregate only; cells under 5 are left to `oai check-egress`.
  - `build_frame.py` writes:
    - `$OAI_FRAME_DIR/persons.parquet`, `$OAI_FRAME_DIR/knees120.parquet`;
    - `$OAI_RESULTS_DIR/flow.csv`, `$OAI_RESULTS_DIR/descriptives.csv`.

- [ ] **Step 1: Write the failing tests** (inline frames):
  - `test_count_missing_rules`: one person with right S2 2 and left S2 null → `s2_count` null under `both_required`, 1 under `available_knees`; right 0 and left 3 → 1; both ≥ 1 → 2; `s2_cut = 2` with S2 1 and 1 → 0.
  - `test_wave_validity_drives_inclusion`: person A is valid at 48 months only → in the frame with `valid72` False and `steps_72`, `steps_change` null. Person B is invalid at 48 months → absent.
  - `test_steps_missing_keeps_count_measures`: valid at both waves with steps null at 72 months → `mv_min_72` present, `steps_72` and `steps_change` null.
  - `test_change_is_later_minus_earlier`: `steps_48` 5,000, `steps_72` 4,000 → `steps_change` −1,000; S2 count 0 at 48 and 2 at 72 months → `s2_change_48_72` 2.
  - `test_exam120_knee_frame`: knees (exam 48, exam 120) = (1, 1) excluded; (0, null) excluded; (0, 1) event True; (0, 0) event False. The person's `steps_48` is carried onto each knee.
- [ ] **Step 2: Run** `uv run pytest tests/test_crepitus_activity_build.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `activity.py` and `build_frame.py`.
- [ ] **Step 4: Run** the tests, then `uv run oai run crepitus_activity --step cohort`. Expected: PASS. On the release:
  - about 1,928 persons, `valid72` about 1,343;
  - B3: about 931 knees, 184 events (the 2026-11-12 count).
- [ ] **Step 5: Commit** `feat(crepitus_activity): person and knee frames with activity waves, crepitus counts and covariates`.

### Task 4: Models

**Files:**
- Create: `analyses/crepitus_activity/models.R` (replace the placeholder)

**Interfaces:**
- Consumes: `persons.parquet`, `knees120.parquet`; `oaimodels::{read_frame, assumptions, fit_knee_gee}`; `geepack::geeglm`; `MASS::polr`.
- Produces: `table_a1.csv` … `table_a3.csv`, `table_b1.csv` … `table_b3.csv`, `metrics_models.csv`.
  - Rows: `table, activity, crepitus, term, model, n, estimate, lo, hi`.
  - Estimates:
    - A: difference in the activity unit (or ratio under `log`);
    - B1, B2: odds ratio (proportional odds) per activity unit;
    - B3: odds ratio per activity unit.

Model specifications. Every model uses complete cases on its own terms. A models are `geeglm(gaussian, id = ID, corstr = "independence")` on persons, which gives sandwich SEs. `cov1` and `cov2` mean `model.covariates`, then plus `model.covariates_2`. Wear hours are taken at the outcome wave for the A models, and at 48 months for B.
- **A1:**
  - `m_48 ~ count_48 + cov1(48)`;
  - `m_72 ~ s2_72 + cov1(72)`.
  - The count enters linear (`per_knee`), then as a factor (`k1`, `k2`).
- **A2:** `m_72 ~ count_48 + m_48 + cov1`, for exam and for S2. Then `both`: exam and S2 together, reported under crepitus `both_exam` and `both_s2`.
- **A3:**
  - concurrent: `m_72 ~ s2_change_48_72 + s2_48 + m_48 + cov` (term `change`);
  - preceding: `m_72 ~ X_change_36_48 + X_36 + m_48 + cov`, for X in exam and S2.
- **B1:** `polr(factor(s2_72) ~ m_48 + factor(s2_48) + cov)`; then `+ m_change` (term `change`, with `m_48` still in the model).
- **B2:** `polr(factor(s2_96) ~ m_48 + m_change + factor(s2_72) + cov)`.
- **B3:** `fit_knee_gee(knees120, "m_48 + m_change + cov", outcome = "event", term = ...)`.
- **Every model** is run as `m1` (`cov1`) and `m2` (`cov2`). A fit error or a factor level with fewer than 5 observations writes NA, not a failure.

- [ ] **Step 1: Run** the step before writing the file. Expected: FAIL (placeholder).
- [ ] **Step 2: Implement** `models.R`.
- [ ] **Step 3: Run** `uv run oai run crepitus_activity --step models`. Expected: it completes, and all six tables have rows for each activity measure.
- [ ] **Step 4: Commit** `feat(crepitus_activity): crepitus -> activity (A1-A3) and activity -> crepitus (B1-B3) models`.

### Task 5: Real-data run, variants and results

**Files:**
- Create: `tests/test_crepitus_activity_realdata.py`
- Modify: `analyses/crepitus_activity/README.md` (Results), `TODO.md`, `analyses/crepitus/LITERATURE.md` (the "Accelerometry" coverage line)

- [ ] **Step 1: Write the real-data test** (`realdata`; skipped without R or without `OAI_STEPS_DIR`):
  - the analysis runs end to end;
  - all six tables exist;
  - the egress check passes.
- [ ] **Step 2: Run** `uv run pytest tests/test_crepitus_activity_realdata.py -m realdata -v`. Expected: PASS.
- [ ] **Step 3: Run the variants** `available_knees`, `log_activity` and `s2_cut_2`. Write the README results:
  - flow and descriptives;
  - per direction, the key `per_knee` and `change` estimates for steps under `m1` and `m2`, and the MV and light estimates in brief;
  - how the variants move them.

  Wording is neutral. Report the estimates with their CIs. Two waves of activity cannot separate direction from shared change, and the README says so.
- [ ] **Step 4: Add to TODO.md** (`<!-- skip -->`): before any publication, the Northwestern authorship terms (Jing co-author, PARR input).
- [ ] **Step 5: Run** `uv run pytest -q` and the R suite. Expected: PASS.
- [ ] **Step 6: Commit** `feat(crepitus_activity): results — crepitus and activity in both directions at 48 and 72 months`.
