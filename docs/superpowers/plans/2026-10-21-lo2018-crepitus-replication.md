# Lo 2018 Crepitus Replication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replicate Lo et al. 2018 (KOOS S2 crepitus → incident symptomatic knee OA in the OAI) end to end, graded against its published flow and Tables 1–6, and add a dual-measure step (KOOS S2 × examiner crepitus) that reports 2 × 2 counts, concordance and predictive value on the same cohort.

**Architecture:** New analysis `analyses/lo2018_crepitus/`, laid out like `analyses/lo2022_walking/`: a Python step builds the right-knee cohort, person-period observations and person-level four-year frame (`lo2018.py` + `build_frame.py`), an R step fits the GEE and logistic models (`models.R`), a Python step grades `metrics_*.csv` against `published.toml` (`compare.py`), and a fourth pair of steps (`dual.py`, `dual.R`) handles the dual-measure extension. Crepitus column templates move from `analyses/crepitus/crepitus.py` into `oai.derive.crepitus` so both analyses share them.

**Tech Stack:** Python ≥ 3.11 (uv, polars, pytest), R (renv, geepack, testthat).

**Spec:** `docs/superpowers/specs/2026-10-21-lo2018-crepitus-replication-design.md`

## Global Constraints

- Everything in `docs/superpowers/plans/2026-09-30-assumptions-and-lo2022-replication.md` Global Constraints applies, except: work on the current branch `claude/oai-crepitus-measures-768ff2`, not `main`.
- Commit trailer: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- No OAI data in git. Run outputs stay in `$OAI_RESULTS_DIR/lo2018_crepitus/<label>/` and are reported in chat, not committed.
- Right knee only (`SIDE == "R"`); the person is the unit (`ID`), so every frame in this analysis has one row per person or per person-period, never per knee.
- Visits: exposure at V00, V01, V03, V05; outcome at V01, V03, V05, V06. Period *p* pairs exposure visit `EXPOSURE_VISITS[p-1]` with outcome visit `OUTCOME_VISITS[p-1]`.
- Crepitus levels are coded 0–4 and named `never, rarely, sometimes, often, always` in metric keys; `never` is the referent.
- Published targets are the PMC tables as extracted on 2026-10-21. Every value is entered verbatim; a human proofreads `published.toml` against the PDF before results are called final (TODO item, Task 7).
- A published OR gets `sig = true` when its rounded CI excludes 1, `sig = false` when it includes 1 with neither bound equal to 1.0, and no `sig` key when a bound is exactly 1.0.
- New synthetic data lives in `tests/fixtures/oai_lo2018/`. `tests/fixtures/oai/` and `tests/fixtures/oai_knee/` do not change.

## Review Focus

1. **A right-knee replacement during follow-up with no KL or pain at the next outcome visit** must make that visit's outcome SOA (the paper counts arthroplasty as Sx, ROA and SOA), not a missing outcome. → Task 4 `test_followup_replacement_is_soa_without_readings`.
2. **A missing outcome at V01 with SOA data at V03** must drop period 1, keep period 2 under `periods.after_missing_outcome = "continue"`, and count period 1 in `obs.potential` and `obs.missing_outcome`. → Task 5 `test_missing_middle_outcome_continues`.
3. **A blank baseline S2 with S2 present at V01** must exclude the person from the four-year frame but keep their later periods in the repeated-measures frame. → Task 5 `test_blank_baseline_s2_only_drops_four_year_row`.
4. **A mistyped number in `published.toml`** must fail a test, because every table's categories must sum to its stated totals. → Task 3 `test_published_categories_sum_to_totals`.
5. **A person whose only SOA-defining reading comes from another reading project** must not count: only `cohort.reading_project` readings define ROA. → Task 4 `test_other_project_readings_are_ignored`.

## File Map

| Path | Responsibility | Task |
|---|---|---|
| `src/oai/derive/crepitus.py` | `Measure`, `MEASURES`, `crepitus_values()` | 1 |
| `analyses/crepitus/crepitus.py`, `tests/test_crepitus.py` | Import templates from `oai.derive.crepitus` | 1 |
| `src/oai/replication.py`, `tests/test_replication.py` | Optional `sig`; `{value, tol}` floats | 2 |
| `analyses/lo2018_crepitus/{analysis.toml,assumptions.toml,ASSUMPTIONS.md,published.toml,README.md}` | Manifest, ledger, targets, docs | 3 |
| `tests/test_lo2018_definition.py`, `tests/test_analyses.py`, `README.md` | Target and manifest checks; analysis list | 3 |
| `tests/fixtures/oai_lo2018/*.txt` | Synthetic release, one participant per rule | 4 |
| `analyses/lo2018_crepitus/lo2018.py`, `tests/test_lo2018_build.py` | SOA status, cohort flow, periods, four-year frame, metrics | 4, 5 |
| `analyses/lo2018_crepitus/build_frame.py` | Step `cohort`: writes frames and `metrics_cohort.csv` | 5 |
| `r/oaimodels/R/models.R`, `r/oaimodels/tests/testthat/test-logit.R` | `fit_logit()` for one-row-per-person models | 6 |
| `analyses/lo2018_crepitus/models.R` | Step `models`: Tables 1–6, `metrics_models.csv` | 6 |
| `analyses/lo2018_crepitus/compare.py`, `tests/test_lo2018_realdata.py`, `TODO.md` | Step `compare`, real-data run, triage | 7 |
| `analyses/lo2018_crepitus/{dual.py,dual.R}`, `tests/test_lo2018_dual.py` | Steps `dual_counts`, `dual_models` | 8 |

---

### Task 1: Shared crepitus templates

**Files:**
- Create: `src/oai/derive/crepitus.py`
- Modify: `analyses/crepitus/crepitus.py` (drop `Measure`, `MEASURES`; import them)
- Test: `tests/test_derive_crepitus.py`

**Interfaces:**
- Produces:
  - `Measure(name: str, template: str, kind: str, label: str)` (frozen dataclass, moved as is)
  - `MEASURES: tuple[Measure, ...]` with `exam_crepitus`, `exam_grind_pain`, `koos_s2` (templates unchanged)
  - `measure(name: str) -> Measure`; unknown name raises `KeyError`
  - `crepitus_values(visit: str, names: Sequence[str], sides: Sequence[str] = ("R", "L")) -> pl.DataFrame` with columns `ID` (Int64), `SIDE`, `visit`, one Int64 column per name; raises `KeyError` when the visit lacks a column

- [ ] **Step 1: Write the failing tests** in `tests/test_derive_crepitus.py`. Monkeypatch `oai.derive.crepitus.read_table` to return `pl.DataFrame({"ID": [1], "V00RKPFCRE": [1], "V00KSXRKN2": [3]})`.
  - `test_crepitus_values_is_wide_per_side`: `crepitus_values("00", ["exam_crepitus", "koos_s2"], sides=("R",))` equals `{"ID": [1], "SIDE": ["R"], "visit": ["00"], "exam_crepitus": [1], "koos_s2": [3]}`.
  - `test_missing_column_raises`: `crepitus_values("00", ["exam_grind_pain"], sides=("R",))` raises `KeyError`.
  - `test_measure_lookup`: `measure("koos_s2").template == "V{visit}KSX{side}KN2"`.
- [ ] **Step 2: Run** `uv run pytest tests/test_derive_crepitus.py -v`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement** `src/oai/derive/crepitus.py`; values cast with `strict=False` as in `analyses/crepitus/crepitus.py`. Change `analyses/crepitus/crepitus.py` to `from oai.derive.crepitus import MEASURES, Measure` and keep its behaviour.
- [ ] **Step 4: Run** `uv run pytest tests/test_derive_crepitus.py tests/test_crepitus.py -v` and `uv run oai run crepitus`. Expected: PASS, and `availability.csv` byte-identical to the previous run (`cmp` against a copy taken before the change).
- [ ] **Step 5: Commit** `refactor(crepitus): crepitus column templates move to oai.derive.crepitus`.

### Task 2: Grading for ORs without a significance flag, and toleranced floats

**Files:**
- Modify: `src/oai/replication.py` (module docstring, `_grade_or`, the float branch of `grade`)
- Test: `tests/test_replication.py`

**Interfaces:**
- Produces: published values may be `{or, lo, hi}` without `sig` (graded on |diff| ≤ 0.1 only) and `{value, tol}` (a float within `tol`; `kind = "value"`).

- [ ] **Step 1: Write the failing tests:**
  - `test_or_without_sig_ignores_significance`: published `{"or": 1.8, "lo": 1.0, "hi": 3.3}`, ours `1.85 (0.98–3.4)` → `verdict == "replicated"`.
  - `test_toleranced_value`: published `{"value": 0.33, "tol": 0.03}`; ours 0.35 → `replicated`, ours 0.37 → `drift`, `kind == "value"`.
  - `test_value_table_rejects_unknown_keys`: `{"value": 0.33, "tolerance": 0.03}` raises `ValueError`.
- [ ] **Step 2: Run** `uv run pytest tests/test_replication.py -v`. Expected: the three new tests FAIL.
- [ ] **Step 3: Implement.** In `_grade_or`, compare significance only when `"sig" in pub`. Add a `{value, tol}` branch beside the count tables, reusing `_check_keys` with `{"value", "tol"}`.
- [ ] **Step 4: Run** `uv run pytest tests/test_replication.py tests/test_lo2022_definition.py -v`. Expected: PASS (Lo 2022 grading unchanged).
- [ ] **Step 5: Commit** `feat(replication): ORs without a published significance flag; floats with their own tolerance`.

### Task 3: Analysis scaffold, ledger and published targets

**Files:**
- Create: `analyses/lo2018_crepitus/{analysis.toml,assumptions.toml,published.toml,README.md}`, generated `ASSUMPTIONS.md`
- Modify: `tests/test_analyses.py` (add `"lo2018_crepitus"` to the expected list), `README.md` (Analyses row)
- Test: `tests/test_lo2018_definition.py`

**Interfaces:**
- Produces:
  - Steps in `analysis.toml`: `cohort` (python, `build_frame.py`), `models` (r, `models.R`, needs cohort), `compare` (python, `compare.py`, needs models), `dual_counts` (python, `dual.py`, needs cohort), `dual_models` (r, `dual.R`, needs dual_counts). Inputs: `enrollees`, `allclinical:00`, `:01`, `:03`, `:05`, `:06`, `kxr_sq_bu:00`, `:01`, `:03`, `:05`, `:06`, `outcomes:99`. Aggregate outputs: `flow.csv`, `table*.csv`, `dual_*.csv`, `comparison.csv`, `metrics_*.csv`, `assumptions.resolved.json`.
  - Every key in the spec's Decisions table, with its default, status, source (page or check) and `choices` where it lists alternatives; plus `dual.s2_cuts = [1, 3]` (assumed). Variants: `left_knee`, `arthroplasty_either`, `exclude_missing_pain`, `roa_ever`, `stop_after_missing_outcome`, `corstr_independence`.
  - Metric keys (all later tasks emit exactly these):

| Group | Keys | Published |
|---|---|---|
| Flow | `flow.all.persons`, `flow.arthroplasty.excluded`, `flow.no_baseline_kl.excluded`, `flow.baseline_soa.excluded`, `flow.no_outcome.excluded`, `flow.persons` | 4796, 35, 305, 877, 84, 3495 |
| Observations | `obs.potential`, `obs.missing_outcome`, `obs.missing_crepitus`, `obs.n`, `obs.cases`, `obs.cases.p1`…`p4` | 11994, 750, 7, 11237, 636, 258, 159, 126, 93 |
| Descriptives | `d.age_mean`, `d.bmi_mean`, `d.male`; `d.obs.<level>`; `d.base.<level>` | 61.1, 28.2, 1476; 7313, 1213, 1701, 626, 384; 2195, 391, 561, 229, 119 |
| Correlations | `r.womac`, `r.kl`, `r.womac.roa_nosx`, `r.womac.noroa_sx`, `r.womac.noroa_nosx` | `{value, tol = 0.03}`: 0.33, 0.03, 0.31, 0.20, 0.25 |
| Table 1 (1-year) | `t1.<level>.cases`, `t1.<level>.n` (all five levels); `t1.<level>.or_unadj`, `t1.<level>.or_adj` (rarely…always) | spec / PMC Table 1 |
| Table 2 | `t2.<sub>.persons`, `.obs`, `.cases`; then as Table 1 under `t2.<sub>.` | subs `roa_nosx`, `noroa_sx`, `noroa_nosx` |
| Table 3 (4-year) | as Table 1 under `t3.` | |
| Table 4 | as Table 2 under `t4.` (no `.obs`) | |
| Table 6 | `t6.<stratum>.persons`, `.cases`, then as Table 1 | strata `men`, `women`, `age_lt65`, `age_ge65` |

  Table 5 (interaction p-values) goes in `README.md` as a reference table and is not graded.

- [ ] **Step 1: Write the failing tests** in `tests/test_lo2018_definition.py`:
  - `test_manifest_and_assumptions_load`: `load_analysis(...)` has the five step ids above; `load_assumptions(...)` has every Decisions key.
  - `test_published_categories_sum_to_totals`: for `t1` and each `t2.<sub>`: Σ `n` = `obs.n` or `.obs`, Σ `cases` = `obs.cases` or `.cases`; for `t3`: Σ `n` = `flow.persons`; for `t4.<sub>`: Σ `n` = `t2.<sub>.persons`; `t6.men.persons + t6.women.persons == 3495`, same for age strata, and their cases sum to 636; Σ `d.obs.*` = 11237; Σ `d.base.*` = 3495; `obs.potential − obs.missing_outcome − obs.missing_crepitus == obs.n`; the flow subtracts to `flow.persons`.
  - `test_published_sig_follows_the_rule`: every OR's `sig` (present or absent) matches Global Constraints.
  - `test_enumerated_assumptions_reject_typos` (parametrized over the keys with `choices`), as in `tests/test_lo2022_definition.py`.
- [ ] **Step 2: Run** `uv run pytest tests/test_lo2018_definition.py -v`. Expected: FAIL.
- [ ] **Step 3: Write the files.** `published.toml` carries a `[related]` map (flow keys → `cohort.*`; `obs.*` → `periods.after_missing_outcome`, `outcomes.*`; `t*` → `model.*`, `outcomes.*`), a `[default]` section and no variant sections. `README.md` states the replication target, the step list, how to run, and Table 5. Run `uv run oai assumptions lo2018_crepitus --write`.
- [ ] **Step 4: Run** `uv run pytest tests/test_lo2018_definition.py tests/test_analyses.py tests/test_assumptions_ledgers.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(lo2018_crepitus): manifest, assumptions ledger and published targets from Lo 2018 Tables 1-6`.

### Task 4: Symptomatic-OA status and cohort flow

**Files:**
- Create: `tests/fixtures/oai_lo2018/` (Enrollees, AllClinical00/01/03/05/06, kxr_sq_bu00/01/03/05/06, OUTCOMES99; OUTCOMES99 header copied from `tests/fixtures/oai_knee/OUTCOMES99.txt`), `analyses/lo2018_crepitus/lo2018.py`
- Test: `tests/test_lo2018_build.py`

**Interfaces:**
- Consumes: `oai.derive.knee.{xray_readings, frequent_knee_pain, knee_replacement, visit_days, find_col}`, `oai.derive.crepitus.crepitus_values` (Task 1), `oai.assumptions.Resolved`.
- Produces:
  - `EXPOSURE_VISITS = ("00", "01", "03", "05")`, `OUTCOME_VISITS = ("01", "03", "05", "06")`, `LEVELS = ("never", "rarely", "sometimes", "often", "always")`, `SUBGROUPS = ("roa_nosx", "noroa_sx", "noroa_nosx")`
  - `soa_status(A) -> pl.DataFrame`: one row per `ID` × visit in `("00", *OUTCOME_VISITS)` for the cohort side, columns `sx`, `roa`, `replaced`, `soa` (nullable booleans). `soa` is True when `replaced`; else `sx & roa` (null if either is null). `roa` follows `outcomes.roa_rule`. `replaced` is True from the first visit whose `V##VISDYS` is on or after the replacement day, for the knee(s) named by `outcomes.arthroplasty_scope`.
  - `Cohort(people: pl.DataFrame, flow: pl.DataFrame)`; `build_cohort(A, soa: pl.DataFrame) -> Cohort`. `people` has `ID, age, sex, bmi, kl0, sx0, womac0, subgroup`. `flow` has `step, persons, excluded` for the six flow steps.

Fixture participants (IDs 2000001–2000010), one rule each: baseline right replacement (excluded at `arthroplasty`); no Project 15 right reading at V00 (excluded at `no_baseline_kl`); baseline KL 3 with frequent pain (excluded at `baseline_soa`); no outcome data at any follow-up (excluded at `no_outcome`); incident SOA at V03; never SOA with all visits; right replacement between V03 and V05 with V05 readings blank; V01 blank but V03/V05/V06 present; KL 2 at V01 then KL 1 at V03 with frequent pain at V03; a Project 37 KL 3 reading at V03 with no Project 15 reading that visit.

- [ ] **Step 1: Write the failing tests** (each sets `OAI_DATA_DIR` to the fixture, as `tests/test_derive_knee.py` does):
  - `test_flow_counts_each_exclusion`: flow `excluded` = 1, 1, 1, 1 at the four exclusion steps; `flow.persons` = 6.
  - `test_followup_replacement_is_soa_without_readings`: the replaced participant has `soa == True` at V05 and V06.
  - `test_other_project_readings_are_ignored`: the Project 37 participant has `roa` null at V03.
  - `test_roa_rule_same_visit_vs_ever`: the KL 2 → 1 participant has `soa` False at V03 by default and True with `--set outcomes.roa_rule=ever` (resolve `A` with `load_assumptions(ANALYSIS).resolve("lo2018_crepitus", variant, overrides)`, as `built()` in `tests/test_lo2022_build.py` does).
  - `test_missing_baseline_pain_is_not_sx_by_default`: a blank `P01KPR12CV` gives `sx0 == False` and the person stays in the cohort; with `cohort.missing_baseline_pain = "exclude"` they leave at `baseline_soa`.
- [ ] **Step 2: Run** `uv run pytest tests/test_lo2018_build.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `soa_status` and `build_cohort` in `lo2018.py`. The `arthroplasty` step excludes baseline replacements in the knee(s) named by `cohort.arthroplasty_scope`; the cohort side comes from `cohort.side`. Sex from Enrollees `P02SEX`, age `V00AGE`, BMI `P01BMI`, WOMAC pain `V00WOMKPR`. `subgroup` from `kl0 >= 2` and `sx0`. The `no_outcome` step drops people whose `soa` is null at every outcome visit.
- [ ] **Step 4: Run** `uv run pytest tests/test_lo2018_build.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(lo2018_crepitus): right-knee symptomatic OA status (arthroplasty counted as SOA) and cohort flow`.

### Task 5: Observation periods, four-year frame and cohort metrics

**Files:**
- Modify: `analyses/lo2018_crepitus/lo2018.py`
- Create: `analyses/lo2018_crepitus/build_frame.py`
- Test: `tests/test_lo2018_build.py`

**Interfaces:**
- Consumes: Task 4's `soa_status`, `build_cohort`, constants.
- Produces:
  - `periods(A, cohort: Cohort, soa: pl.DataFrame, crepitus: pl.DataFrame) -> tuple[pl.DataFrame, dict[str, int]]`. Frame columns: `ID, period (1-4), crep (0-4), exam (0/1, nullable), event (bool), age, sex, bmi, subgroup`. Counts dict: `potential, missing_outcome, missing_crepitus`. `crepitus` is `crepitus_values` for the cohort side at `EXPOSURE_VISITS`, stacked.
  - `four_year(cohort: Cohort, soa: pl.DataFrame, crepitus: pl.DataFrame) -> pl.DataFrame`: one row per person with baseline S2 present: `ID, crep0, exam0, event, age, sex, bmi, subgroup, kl0, womac0`.
  - `cohort_metrics(cohort, periods_frame, counts, persons) -> pl.DataFrame` (`metric, value`) for every `flow.*`, `obs.*`, `d.*`, `r.*` key in Task 3. Spearman via `pl.corr(..., method="spearman")` on the four-year frame.
  - `build_frame.py` writes `$OAI_FRAME_DIR/frame.parquet` (periods), `$OAI_FRAME_DIR/persons.parquet`, `$OAI_RESULTS_DIR/flow.csv`, `$OAI_RESULTS_DIR/metrics_cohort.csv`.

Period rules (from the paper, with the open choice named):
- A person is at risk in period *p* until an earlier period's outcome visit showed SOA. Every at-risk period is *potential*.
- Outcome missing (`soa` null at the outcome visit): the observation is dropped and counted in `missing_outcome`. With `"continue"` later periods stay potential; with `"stop"` the person's follow-up ends.
- Crepitus missing at the exposure visit with the outcome present: dropped and counted in `missing_crepitus`.
- `event` = `soa` at the outcome visit. Four-year `event` = any period's outcome showed SOA.

- [ ] **Step 1: Write the failing tests** (pure functions on small inline frames, no fixture):
  - `test_censored_after_incident_soa`: SOA at V03 → periods 1 and 2 only; period 2 `event == True`.
  - `test_missing_middle_outcome_continues`: outcome null at V01, present after → periods 2–4 kept; counts `potential == 4`, `missing_outcome == 1`; with `"stop"`, no periods and `potential == 1`.
  - `test_missing_crepitus_is_counted_separately`: S2 null at V01, outcome present at V03 → `missing_crepitus == 1`.
  - `test_blank_baseline_s2_only_drops_four_year_row`: S2 null at V00, present at V01 → absent from `four_year`, present in `periods` from period 2.
  - `test_cohort_metrics_has_every_published_key`: the metric names returned for a fixture run equal the `flow.*`, `obs.*`, `d.*`, `r.*` keys of `published.toml`.
- [ ] **Step 2: Run** `uv run pytest tests/test_lo2018_build.py -v`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement** `periods`, `four_year`, `cohort_metrics` and `build_frame.py`.
- [ ] **Step 4: Run** `uv run pytest tests/test_lo2018_build.py -v`, then `uv run oai run lo2018_crepitus --step cohort`. Expected: PASS; on the real release `flow.csv` shows 877 at `baseline_soa`.
- [ ] **Step 5: Commit** `feat(lo2018_crepitus): observation periods with censoring, four-year frame and cohort metrics`.

### Task 6: Models (Tables 1–6)

**Files:**
- Modify: `r/oaimodels/R/models.R`, `r/oaimodels/NAMESPACE`
- Create: `r/oaimodels/tests/testthat/test-logit.R`, `analyses/lo2018_crepitus/models.R`

**Interfaces:**
- Consumes: `frame.parquet`, `persons.parquet` (Task 5) via `oaimodels::read_frame(path = ...)`; `oaimodels::fit_knee_gee(data, rhs, term = ..., corstr = ..., id = "ID")`.
- Produces:
  - `fit_logit(data, rhs, outcome = "y", term) -> c(or, lo, hi, log_or, se)`: `stats::glm` binomial, 95% Wald.
  - `models.R` writes `table1.csv` … `table6.csv` (rows: group, level, cases, n, or_unadj, lo, hi, or_adj, lo, hi, p_trend) and `metrics_models.csv` with every `t1`–`t4`, `t6` key from Task 3 (`.lo`, `.hi` suffixes for ORs).

Model specifications:
- Tables 1–2: `fit_knee_gee` on `frame.parquet`, `outcome = "event"`, `rhs = "factor(crep)"` (unadjusted) and `"factor(crep) + age + sex + bmi"` (adjusted), `term = "factor(crep)<k>"` for k = 1..4, `corstr = A[["model.corstr"]]`. Table 2 repeats within each `subgroup`.
- Tables 3–4: `fit_logit` on `persons.parquet`, `outcome = "event"`, `rhs = "factor(crep0)"` and `"factor(crep0) + age + sex + bmi"`, `term = "factor(crep0)<k>"`.
- Table 6: four-year model within `sex` (adjusted for age + bmi) and within `age < 65` / `age >= 65` (adjusted for sex + bmi).
- Table 5: four-year model, interaction p from the Wald test of `crep0:<covariate>` with `crep0` numeric 0–4, overall and per subgroup; written to `table5.csv` only.
- `p_trend`: `stats::prop.trend.test(cases, n)` when `model.trend = "cochran_armitage"`; the Wald p of numeric `crep` (or `crep0`) in the adjusted model when `"ordinal_term"`.

- [ ] **Step 1: Write the failing R test** `test-logit.R`: on a simulated frame with a known log-odds of 0.7 for `x` (seed 1, n = 5,000), `fit_logit(d, "x", term = "x")[["log_or"]]` is within 0.1 of 0.7, and an unknown `term` errors.
- [ ] **Step 2: Run** `cd r && Rscript -e 'testthat::test_local("oaimodels", filter = "logit")'`. Expected: FAIL.
- [ ] **Step 3: Implement** `fit_logit` (export it) and `analyses/lo2018_crepitus/models.R`.
- [ ] **Step 4: Run** the R test (PASS), then `uv run oai run lo2018_crepitus --step models`. Expected: `metrics_models.csv` has no missing keys (checked by `compare.py` in Task 7).
- [ ] **Step 5: Commit** `feat(lo2018_crepitus): GEE and logistic models for Tables 1-6`.

### Task 7: Grading, real-data run and triage

**Files:**
- Create: `analyses/lo2018_crepitus/compare.py` (same as Lo 2022's), `tests/test_lo2018_realdata.py`
- Modify: `analyses/lo2018_crepitus/README.md` (Replication status), `TODO.md`

**Interfaces:**
- Consumes: `metrics_cohort.csv`, `metrics_models.csv`, `published.toml`, `oai.replication.{grade, select_section, summarize}`.

- [ ] **Step 1: Write the real-data test** (marked `realdata`, skipped without R + geepack, like `tests/test_lo2022_realdata.py`): `run_analysis("lo2018_crepitus")` completes; `comparison.csv` has no `missing` verdicts; `flow.baseline_soa.excluded` is `replicated`; `check_egress` on the results folder reports no problems.
- [ ] **Step 2: Run** `uv run pytest tests/test_lo2018_realdata.py -m realdata -v`. Expected: FAIL until `compare.py` exists, then PASS.
- [ ] **Step 3: Triage.** Run each variant from Task 3 (`uv run oai run lo2018_crepitus --variant <name>`) and record replicated / drift counts per variant in the README table. Any open entry whose variant beats the default by more than five replicated rows becomes a `TODO.md` item marked `<!-- skip -->` with the question for the authors. Add a `<!-- skip -->` item to proofread `published.toml` against the PDF.
- [ ] **Step 4: Run** `uv run pytest -q`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(lo2018_crepitus): grading against Lo 2018 and replication status`.

### Task 8: Dual-measure counts, concordance and prediction

**Files:**
- Create: `analyses/lo2018_crepitus/dual.py`, `analyses/lo2018_crepitus/dual.R`
- Test: `tests/test_lo2018_dual.py`

**Interfaces:**
- Consumes: `frame.parquet`, `persons.parquet` (columns `crep`, `exam`, `crep0`, `exam0`, `event`, `subgroup`, covariates); `A["dual.s2_cuts"]`; `oaimodels::{kappa_ci, auc_ci, classification, fit_knee_gee, fit_logit}`.
- Produces:
  - `combo(s2: pl.Expr, exam: pl.Expr, cut: int) -> pl.Expr` in `dual.py`: `"neither"`, `"s2_only"`, `"exam_only"`, `"both"`, null if either input is null.
  - `dual.py` writes `$OAI_FRAME_DIR/dual_periods.parquet` and `dual_persons.parquet` (frames plus `combo_s2ge<cut>` columns) and `$OAI_RESULTS_DIR/dual_counts.csv`: `frame (periods|persons), cut, group (all or subgroup), combo, n, events`.
  - `dual.R` writes `dual_concordance.csv` (per exposure visit and cut: n, agreement, kappa with CI, prevalence index, bias index; AUC of `crep` for `exam`) and `dual_prediction.csv` (per frame and cut: OR vs `"neither"` for each combo, unadjusted and adjusted; Se, Sp, PPV, NPV of S2, exam, both and either for four-year `event`; the interaction OR of S2 and exam from a model with both measures: `crep:exam` in the periods frame, `crep0:exam0` in the persons frame).

- [ ] **Step 1: Write the failing tests:**
  - `test_combo_levels`: (s2, exam) = (0, 0), (3, 0), (0, 1), (4, 1), (None, 1) at cut 3 → neither, neither, exam_only, both, null; at cut 1 the second is `s2_only`.
  - `test_dual_counts_cells_sum_to_frame`: for an inline persons frame, `n` over the four combos equals the rows with both measures, and `events` sums to their events.
- [ ] **Step 2: Run** `uv run pytest tests/test_lo2018_dual.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `dual.py` and `dual.R`.
- [ ] **Step 4: Run** `uv run pytest tests/test_lo2018_dual.py -v`, then `uv run oai run lo2018_crepitus`. Expected: PASS; `dual_counts.csv` for persons at cut 1 is within a few percent of the spec's preliminary counts (neither 1,460, S2 only 736, exam only 679, both 571); arthroplasty-as-SOA raises events slightly.
- [ ] **Step 5: Commit** `feat(lo2018_crepitus): KOOS S2 x exam crepitus counts, concordance and predictive value`.
