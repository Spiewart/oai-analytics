# Palpable Crepitus → Incident Symptomatic OA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Test examiner-palpated crepitus as a predictor of incident symptomatic knee OA, using Lo 2018's validated design. Anchor the exam item by replicating Mahmoudian 2023 (exam crepitus and tibiofemoral structural development in symptomatic KL 0–1 knees).

**Architecture:** The incident-SOA machinery in `analyses/lo2018_crepitus/lo2018.py` moves to `oai.derive.incident_soa`. Its period and four-year builders gain a `require` argument naming which crepitus measures an observation needs. A new analysis, `analyses/exam_crepitus_soa/`, has four steps:
- `cohort` (Python): exam-based periods and four-year frame;
- `anchor` (Python): the Mahmoudian cohort and outcomes;
- `models` (R): exam Tables E1–E6 and the Mahmoudian ORs;
- `compare` (Python): grades the cohort flow against Lo 2018 and the Mahmoudian targets.

**Tech Stack:** Python ≥ 3.11 (uv, polars, pytest), R (renv, geepack).

**Spec:** `docs/superpowers/specs/2026-10-21-exam-crepitus-incident-soa-design.md`

## Global Constraints

- Everything in `docs/superpowers/plans/2026-10-21-lo2018-crepitus-replication.md` Global Constraints applies: the branch is `claude/oai-crepitus-measures-768ff2`; commits carry the `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` trailer; no OAI data goes in git; right knee only for Part 1; person-level frames.
- Lo 2018 outputs must not change: `frame.parquet`, `persons.parquet` and `metrics_cohort.csv` from `oai run lo2018_crepitus --step cohort` stay identical to before Task 1.
- Inherited Lo 2018 decisions keep Lo 2018's defaults. If the Lo 2018 ledger changes (for example, after Grace answers on blank baseline pain), this analysis must fail a test until it follows.
- Exam exposure is binary (1 = crepitus present). Metric keys use `yes` / `no` for the two levels and `exam` for the OR term.
- Mahmoudian targets are entered verbatim from the abstract and its Table 1 (user-supplied, 2026-10-21). The `sig` rule follows the Lo 2018 plan: no `sig` when a bound is exactly 1.0.
- Part 2 uses both knees, then one knee per person. Its random pick is seeded (`mahmoudian.seed`).

## Review Focus

1. **Exam missing at V01, S2 present.** With `require=("exam_crepitus",)` the period is dropped and counted in `missing_crepitus`. The default `require=("koos_s2",)` keeps it. → Task 1 `test_require_exam_drops_periods_without_exam`.
2. **Both knees eligible for Mahmoudian.** The person contributes exactly one knee, and the same knee on every run with the same seed. → Task 4 `test_pick_knee_is_seeded_and_one_per_person`.
3. **A follow-up JSN of 0.5** (a within-grade reading) is not incident JSN under `jsn_rule = "incident"`; 1.0 is. → Task 4 `test_structural_development_rules`.
4. **Structural development with a blank V06 pain answer.** The symptomatic outcome is null for that person, so they leave model (b) only and are not counted as a non-event. → Task 4 `test_symptomatic_outcome_needs_followup_pain`.
5. **Inherited decisions drift from Lo 2018.** A shared key whose value differs from `analyses/lo2018_crepitus/assumptions.toml` fails a test. → Task 2 `test_inherited_decisions_match_lo2018`.

## File Map

| Path | Responsibility | Task |
|---|---|---|
| `src/oai/derive/incident_soa.py`, `tests/test_derive_incident_soa.py` | SOA status, cohort flow, periods and four-year frame with `require` | 1 |
| `analyses/lo2018_crepitus/lo2018.py` | Imports the moved code; keeps `LEVELS`, `cohort_metrics` | 1 |
| `analyses/exam_crepitus_soa/{analysis.toml,assumptions.toml,ASSUMPTIONS.md,published.toml,README.md}` | Manifest, ledger, anchor targets, docs | 2 |
| `tests/test_exam_soa_definition.py`, `tests/test_analyses.py`, `README.md` | Definition checks; analysis list | 2 |
| `analyses/exam_crepitus_soa/{exam_soa.py,build_frame.py}`, `tests/test_exam_soa_build.py` | Step `cohort`: exam frames and metrics | 3 |
| `analyses/exam_crepitus_soa/{mahmoudian.py,anchor.py}`, `tests/test_exam_soa_anchor.py`, `tests/fixtures/oai_lo2018/kxr_sq_bu0{0,6}.txt` and others | Step `anchor`: Mahmoudian cohort, outcomes, metrics | 4 |
| `analyses/exam_crepitus_soa/models.R` | Step `models`: Tables E1–E6, Mahmoudian ORs | 5 |
| `analyses/exam_crepitus_soa/compare.py`, `tests/test_exam_soa_realdata.py`, `TODO.md` | Step `compare`, real-data run, results | 6 |

---

### Task 1: Shared incident-SOA module with a `require` argument

**Files:**
- Create: `src/oai/derive/incident_soa.py`
- Modify: `analyses/lo2018_crepitus/lo2018.py` (import the moved names, delete their bodies)
- Create: `tests/soa_helpers.py` (inline frame builders, moved from `tests/test_lo2018_build.py`)
- Test: `tests/test_derive_incident_soa.py` (existing `tests/test_lo2018_build.py` keeps passing)

**Interfaces:**
- Produces (moved as is unless stated):
  - `EXPOSURE_VISITS`, `OUTCOME_VISITS`, `VISITS`, `SUBGROUPS`, `ROA_KL`, `COVARIATES`, `Cohort`
  - `soa_status(A) -> pl.DataFrame`, `build_cohort(A, soa) -> Cohort`, `crepitus_frame(A) -> pl.DataFrame`
  - `REQUIRE_COLUMNS = {"koos_s2": "crep", "exam_crepitus": "exam"}`
  - `periods(A, cohort, soa, crepitus, require: Sequence[str] = ("koos_s2",)) -> tuple[pl.DataFrame, dict[str, int]]`. An at-risk period whose outcome is present but which lacks any required measure counts in `missing_crepitus` and is dropped.
  - `four_year(cohort, soa, crepitus, require: Sequence[str] = ("koos_s2",)) -> pl.DataFrame`. Keeps people whose baseline values of every required measure are present.
- `lo2018.py` keeps `LEVELS`, `_spearman` and `cohort_metrics`, and re-imports the rest so `lo2018.<name>` still resolves.

- [ ] **Step 1: Save the current Lo 2018 cohort outputs.** Copy `frame.parquet`, `persons.parquet` and `metrics_cohort.csv` from `$OAI_WORK_DIR/lo2018_crepitus/default/` and `$OAI_RESULTS_DIR/lo2018_crepitus/default/` to the plan workspace.
- [ ] **Step 2: Write the failing tests** in `tests/test_derive_incident_soa.py`. Move the helpers `person`, `inline_cohort`, `inline_soa` and `inline_crepitus` from `tests/test_lo2018_build.py` into `tests/soa_helpers.py`, and import them in both test files.
  - `test_require_exam_drops_periods_without_exam`: S2 `[0, 1, 1, 1]`, exam `[1, None, 0, 0]`, no SOA.
    - Default: periods `[1, 2, 3, 4]`.
    - `require=("exam_crepitus",)`: periods `[1, 3, 4]`, `missing_crepitus == 1`.
  - `test_require_both_needs_both`: S2 `[0, None, 1, 1]`, exam `[1, 1, None, 0]`. `require=("koos_s2", "exam_crepitus")` gives periods `[1, 4]`, `missing_crepitus == 2`.
  - `test_four_year_require_exam`: S2 at baseline present, exam at baseline None. Default keeps the person; `require=("exam_crepitus",)` drops them.
  - `test_unknown_requirement_raises`: `require=("womac",)` raises `KeyError`.
- [ ] **Step 3: Run** `uv run pytest tests/test_derive_incident_soa.py -v`. Expected: FAIL (module missing).
- [ ] **Step 4: Implement** the module and slim `lo2018.py`.
- [ ] **Step 5: Run** `uv run pytest tests/test_derive_incident_soa.py tests/test_lo2018_build.py tests/test_lo2018_dual.py -q`, then `uv run oai run lo2018_crepitus --step cohort`. Compare against Step 1's copies: `pl.read_parquet(new).equals(pl.read_parquet(old))` for both frames, and `cmp` for `metrics_cohort.csv`. Expected: PASS, all identical.
- [ ] **Step 6: Commit** `refactor(incident_soa): Lo 2018 SOA, cohort and period builders move to oai.derive.incident_soa, with a require argument`.

### Task 2: Analysis scaffold, ledger and anchor targets

**Files:**
- Create: `analyses/exam_crepitus_soa/{analysis.toml,assumptions.toml,published.toml,README.md}`, generated `ASSUMPTIONS.md`, placeholder step files (as in Lo 2018 Task 3)
- Modify: `tests/test_analyses.py` (add `"exam_crepitus_soa"`), `README.md` (Analyses row)
- Test: `tests/test_exam_soa_definition.py`

**Interfaces:**
- Produces:
  - Steps:
    - `cohort` (python, `build_frame.py`);
    - `anchor` (python, `anchor.py`);
    - `models` (r, `models.R`, needs cohort and anchor);
    - `compare` (python, `compare.py`, needs models).
  - Inputs: Lo 2018's inputs.
  - Aggregate outputs: `flow.csv`, `table_*.csv`, `comparison.csv`, `metrics_*.csv`, `assumptions.resolved.json`.
  - Inherited keys, copied with Lo 2018's value, status and source:
    - `cohort.side`, `cohort.reading_project`, `cohort.arthroplasty_scope`, `cohort.missing_baseline_pain`;
    - `outcomes.pain_baseline_item`, `outcomes.pain_followup_item`, `outcomes.roa_rule`, `outcomes.arthroplasty_scope`, `outcomes.arthroplasty_timing`, `outcomes.soa_missing`, `outcomes.replacement_counts`, `outcomes.missing_visit_days`;
    - `periods.after_missing_outcome`;
    - `model.corstr`, `model.covariates`, `model.missing_covariates`.
  - New keys:
    - `exposure.require_s2` = false (assumed; spec);
    - `mahmoudian.knee_pick` = `"random"` (open; choices `random`, `right`, `left`);
    - `mahmoudian.seed` = 2023 (assumed);
    - `mahmoudian.jsn_rule` = `"incident"` (open; choices `incident`, `any_increase`);
    - `mahmoudian.osteophyte_rule` = `"sites"` (open; choices `sites`, `grade_sum`);
    - `mahmoudian.reading_project` = 15 (assumed);
    - `mahmoudian.missing_followup_pain` = `"exclude"` (open; choices `exclude`, `not_sx`).
  - Variants:
    - `require_s2`;
    - `exclude_missing_pain` (as in Lo 2018);
    - `mahmoudian_right`;
    - `mahmoudian_left`;
    - `mahmoudian_any_jsn_increase`;
    - `mahmoudian_osteophyte_grade_sum`.
  - `published.toml [default]`:
    - Lo 2018 flow keys and values: `flow.all.persons` 4796, `flow.arthroplasty.excluded` 35, `flow.no_baseline_kl.excluded` 305, `flow.baseline_soa.excluded` 877, `flow.no_outcome.excluded` 84, `flow.persons` 3495.
    - Mahmoudian counts and descriptives: `m.subjects` 576, `m.crepitus` 264, `m.women` `{count = 346, tol = 4}`, `m.age_mean` 58.9, `m.bmi_mean` 29.6, `m.structural.events` 310, `m.structural_sx.events` 153.
    - Mahmoudian ORs (no `sig` where a bound is 1.0):
      - `m.structural.or_crude` `{or = 1.3, lo = 1.0, hi = 1.8}`;
      - `m.structural.or_adj` `{or = 1.2, lo = 0.8, hi = 1.7, sig = false}`;
      - `m.structural.or_adj_kl` `{or = 1.2, lo = 0.9, hi = 1.7, sig = false}`;
      - `m.structural_sx.or_crude` `{or = 1.1, lo = 0.8, hi = 1.7, sig = false}`;
      - `m.structural_sx.or_adj` `{or = 1.1, lo = 0.7, hi = 1.6, sig = false}`;
      - `m.structural_sx.or_adj_kl` `{or = 1.0, lo = 0.7, hi = 1.5, sig = false}`.
    - A `[related]` map: `flow` → `cohort.*`; `m` → `mahmoudian.*`.

- [ ] **Step 1: Write the failing tests:**
  - `test_manifest_and_assumptions_load`: the four step ids, and every new key present.
  - `test_inherited_decisions_match_lo2018`: for each inherited key, value and choices equal `load_assumptions(analyses/lo2018_crepitus).items[key]`.
  - `test_flow_targets_match_lo2018_published`: every `flow.*` key equals Lo 2018's `published.toml` value.
  - `test_published_sig_follows_the_rule`: as in Lo 2018.
  - `test_enumerated_assumptions_reject_typos`: parametrized over the `mahmoudian.*` keys with `choices`.
- [ ] **Step 2: Run** `uv run pytest tests/test_exam_soa_definition.py -v`. Expected: FAIL.
- [ ] **Step 3: Write the files**, then run `uv run oai assumptions exam_crepitus_soa --write`.
- [ ] **Step 4: Run** `uv run pytest tests/test_exam_soa_definition.py tests/test_analyses.py tests/test_assumptions_ledgers.py -q`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(exam_crepitus_soa): manifest, ledger inherited from Lo 2018, and Mahmoudian 2023 anchor targets`.

### Task 3: Exam-crepitus cohort step

**Files:**
- Create: `analyses/exam_crepitus_soa/exam_soa.py`, `analyses/exam_crepitus_soa/build_frame.py`
- Test: `tests/test_exam_soa_build.py` (fixture `tests/fixtures/oai_lo2018`)

**Interfaces:**
- Consumes: Task 1's module.
- Produces:
  - `require_for(A) -> tuple[str, ...]`: `("exam_crepitus",)`, or `("exam_crepitus", "koos_s2")` when `exposure.require_s2`.
  - `exposure_metrics(cohort, frame, counts, persons) -> pl.DataFrame` (`metric, value`), with keys:
    - `flow.*` (the six Lo 2018 flow keys);
    - `obs.potential`, `obs.missing_outcome`, `obs.missing_crepitus`, `obs.n`, `obs.cases`, `obs.cases.p1`…`p4`;
    - `d.obs.yes`, `d.obs.no`, `d.base.yes`, `d.base.no`, `d.age_mean`, `d.bmi_mean`, `d.male`.
  - `build_frame.py` writes:
    - `$OAI_FRAME_DIR/frame.parquet` and `persons.parquet` (same columns as Lo 2018's);
    - `$OAI_RESULTS_DIR/flow.csv` and `metrics_cohort.csv`.

- [ ] **Step 1: Write the failing tests:**
  - `test_require_for`: default `("exam_crepitus",)`; with the `require_s2` variant, both measures.
  - `test_exposure_metrics_keys`: on a fixture run, the set of keys equals the list above, and `d.base.yes + d.base.no == persons.height`.
  - `test_flow_is_lo2018s`: on the fixture, `flow.*` values equal `lo2018.cohort_metrics(...)`'s.
- [ ] **Step 2: Run** `uv run pytest tests/test_exam_soa_build.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the tests, then `uv run oai run exam_crepitus_soa --step cohort`. Expected: PASS. On the release, `obs.n` is about 10,634 and `obs.cases` about 622 (the spec's preview); `flow.persons` is 3,576.
- [ ] **Step 5: Commit** `feat(exam_crepitus_soa): exam-crepitus periods, four-year frame and cohort metrics`.

### Task 4: Mahmoudian 2023 anchor cohort and outcomes

**Files:**
- Modify: `tests/fixtures/oai_lo2018/kxr_sq_bu00.txt` and `kxr_sq_bu06.txt`. Add the columns `V##XRJSL`, `V##XROSFM`, `V##XROSTM`, `V##XROSFL`, `V##XROSTL` (0 for existing rows), and rows for new participants 2000013–2000018 in every fixture table. Existing tests' expected counts change only where those six participants enter.
- Create: `analyses/exam_crepitus_soa/mahmoudian.py`, `analyses/exam_crepitus_soa/anchor.py`
- Test: `tests/test_exam_soa_anchor.py`

**Interfaces:**
- Produces:
  - `TF_FEATURES = ("JSM", "JSL", "OSFM", "OSTM", "OSFL", "OSTL")`.
  - `tf_readings(visit: str, project: int) -> pl.DataFrame`: `ID, SIDE, kl` plus the six features as Float64, one reading project, deduplicated as in `xray_readings`.
  - `structural_development(base: pl.DataFrame, fu: pl.DataFrame, jsn_rule: str, osteophyte_rule: str) -> pl.DataFrame`: `ID, SIDE, structural` (bool; null if any needed feature is missing). Rules:
    - JSN `incident`: either compartment is 0 at baseline and ≥ 1 at V06. JSN `any_increase`: either compartment's grade rises.
    - Osteophytes `sites`: more of the four sites graded ≥ 1 than at baseline. Osteophytes `grade_sum`: the sum of the four grades rises.
    - `structural` = JSN rule OR osteophyte rule.
  - `pick_knee(knees: pl.DataFrame, rule: str, seed: int) -> pl.DataFrame`: one row per ID. `random` draws with `numpy.random.default_rng(seed)` over knees sorted by ID and SIDE; `right` / `left` take that side.
  - `anchor_frame(A) -> pl.DataFrame`: one row per subject with `ID, SIDE, exam0, structural, structural_sx, age, sex, bmi, kl0`. Eligibility:
    - `V00COHORT` in {1, 2};
    - baseline KL 0–1 in that knee;
    - `P01KP{side}12CV == 1`;
    - baseline exam present;
    - `structural` not null.

    `structural_sx = structural & (V06KP{side}12CV == 1)`. A null V06 pain answer leaves `structural_sx` null under `missing_followup_pain = "exclude"`, and counts as not symptomatic (`structural_sx = False`) under `"not_sx"`.
  - `anchor_metrics(frame) -> pl.DataFrame`: `m.subjects`, `m.crepitus`, `m.women`, `m.age_mean`, `m.bmi_mean`, `m.structural.events`, `m.structural_sx.events`.
  - `anchor.py` writes `$OAI_FRAME_DIR/anchor.parquet` and `$OAI_RESULTS_DIR/metrics_anchor.csv`.

New fixture participants:
- 13: both knees eligible;
- 14: incident medial JSN (0 → 1);
- 15: V06 JSN 0.5 only;
- 16: one new osteophyte site;
- 17: KL 2 (ineligible);
- 18: Non-exposed control cohort (ineligible).

Set 14's V06 pain blank.

- [ ] **Step 1: Write the failing tests:**
  - `test_structural_development_rules`: on inline frames,
    - JSN 0 → 1 is structural; 0 → 0.5 is not under `incident`, but is under `any_increase`;
    - one site 0 → 1 is structural under `sites`;
    - grades 1 → 2 at one site is structural under `grade_sum` but not under `sites`.
  - `test_pick_knee_is_seeded_and_one_per_person`: two IDs with both knees. One row per ID; identical result for the same seed on two calls; `right` returns all `"R"`.
  - `test_anchor_eligibility`: on the fixture, participants 17 and 18 are absent, and 13 appears once.
  - `test_symptomatic_outcome_needs_followup_pain`: participant 14 has `structural == True` and `structural_sx` null by default, False under `not_sx`.
  - `test_anchor_metrics_keys`: keys equal the `m.*` count and descriptive keys in `published.toml`.
- [ ] **Step 2: Run** `uv run pytest tests/test_exam_soa_anchor.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `mahmoudian.py` and `anchor.py`, and extend the fixture.
- [ ] **Step 4: Run** `uv run pytest -q` (the whole suite: the fixture change touches Lo 2018's tests), then `uv run oai run exam_crepitus_soa --step anchor`. Expected: PASS. On the release, `m.subjects` is within about 10% of 576 and `m.crepitus / m.subjects` near 0.46.
- [ ] **Step 5: Commit** `feat(exam_crepitus_soa): Mahmoudian 2023 anchor cohort and tibiofemoral structural outcomes`.

### Task 5: Models (Tables E1–E6, Mahmoudian ORs)

**Files:**
- Create: `analyses/exam_crepitus_soa/models.R`

**Interfaces:**
- Consumes:
  - `frame.parquet` (`exam`, `crep`, `event`, covariates, `subgroup`);
  - `persons.parquet` (`exam0`, `crep0`, ...);
  - `anchor.parquet`;
  - `oaimodels::{fit_knee_gee, fit_logit, read_frame, assumptions}`.
- Produces: `table_e1.csv` … `table_e6.csv`, `table_m1.csv` and `metrics_models.csv`.
  - E table rows: `group, model, n, events, exposed_n, exposed_events, or, lo, hi`.
  - Per-group metrics, for E1–E4 and E6: `e1.yes.cases`, `e1.yes.n`, `e1.no.cases`, `e1.no.n`, and `e1.exam.or_unadj`, `e1.exam.or_adj`, `e1.exam.or_adj_s2`, each with `.lo` and `.hi`. Groups are prefixed as in Lo 2018 (`e2.<sub>.`, `e4.<sub>.`, `e6.<stratum>.`).
  - Mahmoudian metrics: `m.structural.or_crude`, `m.structural.or_adj`, `m.structural.or_adj_kl`, the same three under `m.structural_sx`, each with `.lo` and `.hi`.

Model specifications:
- E1, E2: `fit_knee_gee`, `outcome = "event"`, `term = "exam"`. Right-hand sides:
  - `exam`;
  - `exam + age + sex + bmi`;
  - `exam + age + sex + bmi + factor(crep)`, on rows with `crep` present; its own n is reported.
- E3, E4, E6: `fit_logit` on persons, the same three right-hand sides with `exam0` and `factor(crep0)`. E6's strata are adjusted as in Lo 2018 Table 6.
- E5: Wald p of `exam0:<covariate>` for age, sex, bmi and `crep0` (numeric), overall and per subgroup.
- Mahmoudian (`table_m1.csv`): `fit_logit(anchor, rhs, outcome = "structural" | "structural_sx", term = "exam0")`. Right-hand sides: `exam0`; `exam0 + age + sex + bmi`; `exam0 + age + sex + bmi + factor(kl0)`. Rows with a null outcome are dropped for that outcome only.

- [ ] **Step 1: Run** `uv run oai run exam_crepitus_soa --step models` once before writing the file. Expected: FAIL (placeholder).
- [ ] **Step 2: Implement** `models.R`.
- [ ] **Step 3: Run** the step. Expected: it completes, and `metrics_models.csv` has every `m.*` OR key in `published.toml` (checked in Task 6). The E3 four-year adjusted OR is consistent with the spec's preview (exposed 53% vs 38% in +ROA −Sx).
- [ ] **Step 4: Commit** `feat(exam_crepitus_soa): exam-crepitus Tables E1-E6 and Mahmoudian 2023 models`.

### Task 6: Grading, real-data run and results

**Files:**
- Create: `analyses/exam_crepitus_soa/compare.py` (Lo 2018's), `tests/test_exam_soa_realdata.py`
- Modify: `analyses/exam_crepitus_soa/README.md` (Results), `TODO.md`, `analyses/crepitus/LITERATURE.md` (coverage line for incident SOA)

- [ ] **Step 1: Write the real-data test** (`realdata`; skipped without R). `run_analysis("exam_crepitus_soa")` completes. `comparison.csv` has no `missing` verdicts. `flow.baseline_soa.excluded` is replicated. The six `table_*` files exist. The egress check passes.
- [ ] **Step 2: Run** `uv run pytest tests/test_exam_soa_realdata.py -m realdata -v`. Expected: FAIL until `compare.py` exists, then PASS.
- [ ] **Step 3: Run the variants**: the four `mahmoudian_*` variants, `require_s2` and `exclude_missing_pain`. Record in the README:
  - the replicated / drift count for the `m.*` anchors per variant;
  - the E1, E3 and E4 ORs under default and `require_s2`.

  File a `TODO.md` item (`<!-- skip -->`) for any Mahmoudian definition where a variant matches the abstract better than the default, with the question for the authors.
- [ ] **Step 4: Run** `uv run pytest -q` and the R suite. Expected: PASS.
- [ ] **Step 5: Commit** `feat(exam_crepitus_soa): graded anchors and results for palpable crepitus and incident symptomatic OA`.
