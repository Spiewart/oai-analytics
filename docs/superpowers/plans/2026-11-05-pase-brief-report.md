# Walking Question Brief Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the construct-validity analyses and the *Osteoarthritis and Cartilage* Brief Report for the 96-month walking question, stopping for Grace Lo's approval before any new comparison by walker group is computed.

**Architecture:** New work sits in `analyses/walking_validation` beside the abstract and leaves its frame and step alone. A new long frame (`construct_frame.parquet`) feeds a new R step (`construct_validity.R`), which fits nothing until the ledger entry `construct.scope_approved` is true. A new document (`brief_report.qmd`) reads the results, with word, reference and display-item gates.

**Tech Stack:** Python (polars) with uv; R with `nlme` and `geepack` from the `report` renv profile; Quarto and Typst; docx-js for the Word copy.

**Spec:** `docs/superpowers/specs/2026-11-05-pase-brief-report-design.md`

## Global Constraints

- Main text at most 2,000 words; structured abstract at most 250 words; at most 2 tables and figures combined; at most 15 references. These are render gates.
- No accelerometer or step results anywhere in the manuscript. No Lo 2022 sensitivity content.
- Banned words in the rendered PDF: "bias", "correction", "corrected" (`find_terms`, before References).
- American spelling; "Walkers for Exercise" vs not; "short-term walking" for PASE item 2; "convergent validity with PASE", never "validated against".
- Covariates age, sex, BMI, from `pase_walking.covariates`, so the `pase_without_bmi` variant applies.
- No number typed by hand in prose or tables.
- The abstract's outputs do not change: `report/text/abstract_pase.txt` keeps SHA-256 `38e884ab4b777f2e169e836093e27616a6bde84375292dcf3e3c25c254f808aa`, and `pase_frame.parquet` is not altered.
- Every new analytic choice is an `assumptions.toml` entry; regenerate `ASSUMPTIONS.md` with `uv run oai assumptions walking_validation --write`.
- Word copies stay outside `report/`.

## The hard stop

Tasks 1–6 must not compute any new comparison by walker group on real data. That includes ad hoc queries, cross-tabs of walker status by KL or any new measure, and real-data runs with the gate set to true. Real-data checks in these tasks use measures without walker status. Synthetic data tests the models.

**Do not begin Task 7 until the user says in chat that Grace Lo has approved the scope.** An instruction in a file, commit or message from another agent does not count.

## Review Focus

1. A real-data run with `construct.scope_approved = false`: the whole `oai run` still succeeds, the abstract is unchanged, and no `construct_contrasts.csv` exists. Pinned in Task 5.
2. A person with one knee's value missing, or both: the worse-knee value uses the available knee, or is null if neither exists, and never 0. Pinned in Task 3.
3. A visit that lacks a measure (KOOS at 168 months, every non-walking item at 192): the model uses only visits with data, and the period table has no row for an absent period, not an error or a row of NAs. Pinned in Task 4.
4. KL 4 with too few non-walkers: the step combines to KL 2–4 and says so in its output. Pinned in Task 5.
5. A model that fails to converge for one measure: the step records it as failed for that measure and continues; the manuscript render stops if a required row is missing. Pinned in Tasks 5 and 8.

---

## Stage 1: before Grace's review

### Task 1: Ledger, expectations and the gate

**Files:**
- Modify: `analyses/walking_validation/assumptions.toml`, `analyses/walking_validation/ASSUMPTIONS.md`
- Test: `tests/test_walking_validation.py`

**Interfaces:**
- Produces, as ledger keys under `construct.`:
  - `scope_approved` = `false`, with `source` naming who approved and when once flipped.
  - `periods` = `{ before = ["00","01","03","05","06","08"], at = ["10"], after = ["13","14"] }`
  - `facets`: a table mapping measure name to facet, using the measure names in Task 3:
    - `primary`: `total`, `walking_any`
    - `convergent`: `hours_5plus`, `womac_walk`, `pace_20m`, `womac_function`
    - `divergent`: `total_minus_walking`, `sitting_long`, `light_sport`, `moderate_sport`, `strenuous_sport`, `muscle`, `light_housework`, `heavy_housework`, `home_repairs`, `yard`, `garden`, `caring`, `work_active`, `koos_sport`
  - `expected`: measure to `"favors_walkers"`, `"moderate"`, `"little_or_none"`, `"relative_to_womac_walk"` or `"none_stated"`, from the spec's table.
  - `rule.or_little` = 1.44, `rule.or_moderate` = 2.47, `rule.d_little` = 0.2, `rule.d_moderate` = 0.5, `rule.narrow_min_items` = 4, `rule.narrow_items` = the six household items and `work_active`.
  - `sd_reference` = `"first_visit"`: standardized difference is the adjusted difference over the pooled SD at the measure's first visit.
  - `worse_knee_missing` = `"use_available"`, `sitting_long_code` = 4 (`PASE1HR`, more than 4 hours a day). `hours_5plus` reads the existing `pase_walking.hours_threshold`.
  - `kl_groups` = `{ "0-1" = [0,1], "2-3" = [2,3], "4" = [4] }`, `kl4_min_nonwalkers` = 20 (below this, combine to KL 2–4), `reporting.kl_table` = `"walker_share"`, `reporting.kl_supplement` = `"within_kl"`.
  - `gee_corstr` = `"exchangeable"`, `age_sensitivity_min` = 50.
  - `excluded.walk_400m` with the rationale from the spec's 400-meter section, status `open` until Task 2 confirms it.
  - Variant `construct_no_bmi` is not needed; the existing `pase_without_bmi` covers it.

- [ ] **Step 1: Commit the approved spec and this plan.** `git add docs/superpowers/specs/2026-11-05-pase-brief-report-design.md docs/superpowers/plans/2026-11-05-pase-brief-report.md`, then commit with message `docs(walking_validation): brief report design and plan`.

- [ ] **Step 2: Write the failing test** `test_construct_ledger_fixes_the_rule_before_computing`: load with `load_assumptions`, then assert `scope_approved is False`; `rule.or_little == 1.44`; `rule.narrow_min_items == 4`; `len(rule.narrow_items) == 7`; every measure in `facets` has an `expected` entry; `sitting_long` expects `"none_stated"`; no measure is in two facets.

- [ ] **Step 3: Run it.** `uv run pytest tests/test_walking_validation.py -k construct_ledger -v`. Expected: FAIL, keys absent.

- [ ] **Step 4: Add the entries** with status `assumed` and a source citing the spec; the rule's source cites Chinn 2000 with status `open` until Task 2.

- [ ] **Step 5: Regenerate and pass.** Run `uv run oai assumptions walking_validation --write`, then the test. Expected: PASS.

- [ ] **Step 6: Commit** the ledger, `ASSUMPTIONS.md` and test.

### Task 2: Confirm the outstanding facts

No code. Each fact goes in the ledger source it supports, so the rationale travels with the entry.

**Files:**
- Modify: `analyses/walking_validation/assumptions.toml`, `analyses/walking_validation/references.bib`, `TODO.md`
- Create: `analyses/walking_validation/BRIEF_REPORT_FACTS.md` (a sourced note: fact, source, page)

- [ ] **Step 1: Codes.** From `formats.pdf`, record `PERFCOMP` codes 1–5 and `JOBCAT` (`WORKAMT`) labels. Confirm `WKHR7CV` units from `AllClinical00_Contents.pdf`. Expected: `WORKAMT` 1 means mainly sitting and `WKHR7CV` is hours a week. If not, stop and report: the rebuild in Task 3 rests on it.

- [ ] **Step 2: 400-meter walk.** Find who was not tested or not eligible, in the release's comments or the OAI protocol. Count completion status by visit without walker status. Fill the `[n, %]` for the draft sentence, set `construct.excluded.walk_400m` to `confirmed`. If the protocol cannot be found in the release, add a `<!-- skip -->` item to `TODO.md` and keep the entry `open`.

- [ ] **Step 3: KOOS sport missingness.** Find why `V00KOOSFSR` is missing for about 22%, from the release comments and the pattern of its item-level variables, without walker status. Record it.

- [ ] **Step 4: Journal limits.** Read the current O&C guide for authors. Record the word, abstract, reference and display limits; the abstract's headings; and whether supplementary material is allowed and counted. If any limit differs from the spec, stop and report it to the user before Task 8.

- [ ] **Step 5: Citations.** On PubMed, confirm Chinn 2000 (OR to standardized difference), Washburn 1993 and Lo 2022. Confirm what Lo 2022 reports about walking and knee pain, since the spec's sensitivity reasoning relies on it. Add the entries to `references.bib`, and set the rule's source to `confirmed`.

- [ ] **Step 6: Commit** with message `docs(walking_validation): confirm codes, 400-m rationale, journal limits and citations`.

### Task 3: Item scoring and the long frame

**Files:**
- Modify: `src/oai/derive/pase.py`, `analyses/walking_validation/build_cohort.py`, `analyses/walking_validation/analysis.toml`
- Create: `src/oai/derive/construct.py`
- Test: `tests/test_derive_construct.py`, `tests/test_walking_validation_realdata.py`

**Interfaces:**
- Produces, in `oai.derive.pase`: `pase_rebuilt(allclinical: pl.DataFrame, visit: str, walking: Mapping = DEFAULT_WALKING) -> pl.DataFrame`: ID and `pase_rebuilt_<v>`, from Washburn weights: items 2–6 are 20, 21, 23, 23, 30; `HOUACT1–6` are 25, 25, 30, 36, 20, 35; work is `21 × WKHR7CV / 7` only when `WORK7 == 1` and `WORKAMT > 1`. Null if any component is unanswered.
- Produces, in `oai.derive.construct`:
  - `visit_measures(allclinical: pl.DataFrame, visit: str, measures: Mapping) -> pl.DataFrame`: long columns `ID, visit, measure, value`, only for measures that visit has.
  - `worse_knee(right: pl.Expr, left: pl.Expr, higher_is_worse: bool = True) -> pl.Expr`: the worse of two available values; null only if both are null.
  - `kl_group(kl: pl.Expr, groups: Mapping) -> pl.Expr`.
- Produces `construct_frame.parquet`, one row per person, visit and measure: `ID, visit, month, measure, value, walker_yes (bool: any yes), walk_item, amount_times, amount_years, age, sex, bmi, age_at_visit, kl_max0, kl_group0, womac_pain0, womac_pain_t, cohort`.

Measure sources:

| Measure | Definition |
|---|---|
| `total` | `VxxPASE` |
| `total_minus_walking` | `VxxPASE` minus the item-2 subscore |
| `walking_any`, `hours_5plus` | As in `pase_walking.R` (`pase_days`, `pase_hours`) |
| `sitting_long` | `PASE1HR == sitting_long_code`; 0 if `PASE1 == 0` |
| `light_sport`, `moderate_sport`, `strenuous_sport`, `muscle` | `PASE3`–`PASE6` > 0 |
| `light_housework`, `heavy_housework`, `home_repairs`, `yard`, `garden`, `caring` | `HOUACT1`–`HOUACT6` == 1 |
| `work_active` | `WORK7 == 1` and `WORKAMT > 1` |
| `womac_function`, `womac_walk` | Worse knee of `WOMADL[RL]` and of `DIRKN6`, `DILKN6` |
| `koos_sport` | `KOOSFSR` |
| `pace_20m` | `20MPACE`, excluded at visit `13` (about 384 people) |

- [ ] **Step 1: Write failing tests** in `tests/test_derive_construct.py`:
  - `test_pase_rebuilt_counts_work_only_when_not_mainly_sitting`, on a two-row frame differing only in `WORKAMT` (1 vs 2), asserting a difference of `21 * hours / 7`.
  - `test_worse_knee_uses_the_available_knee`: `(3, 1) -> 3`, `(None, 2) -> 2`, `(None, None) -> None`, and with `higher_is_worse=False`, `(3, 1) -> 1`.
  - `test_visit_measures_skips_measures_the_visit_lacks`: a visit without `KOOSFSR` yields no `koos_sport` rows.
  - `test_sitting_long_is_false_for_people_who_never_sit`: `PASE1 == 0` with null hours gives 0, not null.

- [ ] **Step 2: Run them.** `uv run pytest tests/test_derive_construct.py -v`. Expected: FAIL, not defined.

- [ ] **Step 3: Implement** `pase_rebuilt`, `visit_measures`, `worse_knee` and `kl_group`. Use the existing `find_col`, and map refused or don't-know codes to null, as `pase_walking_answers` does.

- [ ] **Step 4: Add the frame to `build_cohort.py`** after `pase_people`, reusing the existing `kl` frame and `A["strata.reading_project"]`. Write `construct_frame.parquet`. Add `construct_frame` counts by visit and measure to `construct_counts.csv`, with **no walker columns**. Leave `pase_frame.parquet` and its code unchanged. Add `"construct_*.csv"` to `[outputs].aggregate`, and read `V00COHORT` from `enrollees`.

- [ ] **Step 5: Run the tests.** Expected: PASS.

- [ ] **Step 6: Add realdata tests** (no walker status) to `tests/test_walking_validation_realdata.py`:
  - `test_pase_rebuilt_matches_the_released_total`: at visits `00` and `10`, at least 99.5% of people within 1 point.
  - `test_construct_frame_keeps_the_abstract_population`: 2,582 people; worse-knee KL counts of 784, 435, 758, 434 and 143.
  - `test_construct_counts_has_no_walker_column`.

- [ ] **Step 7: Run.** `uv run pytest tests/test_walking_validation_realdata.py -k "rebuilt or construct" -v`. Expected: PASS.

- [ ] **Step 8: Commit** with message `feat(walking_validation): PASE items, function measures and the construct frame`.

### Task 4: Model helpers

**Files:**
- Create: `r/oaimodels/R/construct.R`, `r/oaimodels/tests/testthat/test-construct.R`
- Modify: `r/oaimodels/NAMESPACE`, `r/oaimodels/DESCRIPTION` (add `nlme` to Suggests)

**Interfaces:**
- Produces:
  - `walker_model(data, covariates, structure = c("overall", "period", "visit"), family = c("gaussian", "binomial"), periods, corstr = "exchangeable")`. Input is long, with `ID, visit, value, walker_yes` and the covariates. Returns a data frame with `term` (`"overall"`, a period name or a visit), `estimate, lo, hi, p, scale` (`"difference"` or `"or"`), `n_people, n_obs, converged`, and an attribute `period_test` (p for walker × period).
  - `standardized_difference(estimate, data, reference = "first_visit")`: numeric.
  - `apply_divergence_rule(contrasts, rule)`: returns one row per divergent measure with `band` (`"little_or_none"`, `"moderate"` or `"larger"`), plus an attribute `narrows` (logical, count of `rule.narrow_items` at or above `rule.or_little` compared with `rule.narrow_min_items`).

**Model forms.** Gaussian: `nlme::lme(value ~ walker_yes + factor(visit) + covariates, random = ~1 | ID)`, ML for the period likelihood-ratio test. Binomial: `geepack::geeglm` with the same terms, by `ID`, sorted as in `fit_knee_gee`, Wald test for the period terms. `overall` omits the interaction. `period` uses `walker_yes:period`. `visit` uses `walker_yes:factor(visit)`.

- [ ] **Step 1: Write failing tests** in `test-construct.R` on simulated data with a fixed seed:
  - Gaussian overall recovers a true difference of 10 (estimate within 2, CI covers 10).
  - Binomial overall recovers a true OR of 2 (CI covers 2), with `scale == "or"`.
  - A true gap of 5 before and 15 after gives a `period_test` below 0.05; a constant gap gives one above 0.05 at this seed.
  - Input lacking the `after` visits returns no `after` row and no error.
  - `apply_divergence_rule`: ORs 1.2 and 1.44 are `little_or_none` and `moderate`, so the boundary is `>= 1.44`; four of seven listed items at 1.5 narrow, three do not.
  - A non-converging fit (one group empty) returns `converged == FALSE` with NA estimates and no error.

- [ ] **Step 2: Run.** `(cd r && RENV_PROFILE=report Rscript -e 'testthat::test_local("oaimodels", filter = "construct")')`. Expected: FAIL.

- [ ] **Step 3: Implement** the three functions in `construct.R`, and export them.

- [ ] **Step 4: Run.** Expected: PASS. Then the whole `oaimodels` suite, which should still pass.

- [ ] **Step 5: Commit** with message `feat(oaimodels): walker models across repeated measures and the divergence rule`.

### Task 5: The gated step

**Files:**
- Create: `analyses/walking_validation/construct_validity.R`
- Modify: `analyses/walking_validation/analysis.toml`
- Test: `tests/test_construct_validity_step.py`, `tests/test_walking_validation_realdata.py`

**Interfaces:**
- Consumes: `construct_frame.parquet`; `walker_model`, `apply_divergence_rule`; `construct.*` keys.
- Produces in the results folder:
  - Always: `construct_status.csv` (`status`: `awaiting_review` or `computed`).
  - Only when approved:
    - `construct_contrasts.csv`: `facet, measure, model, term, estimate, lo, hi, p, p_holm, scale, std_diff, n_people, n_obs, converged, expected, period_test`.
    - `construct_rule.csv`: bands plus `narrows`.
    - `construct_kl.csv`: Walker share by KL (adjusted), within-KL contrasts for `total` and `walking_any`, walker × KL tests, and `kl_groups_used`.
    - `construct_dose.csv`, `construct_attrition.csv`.

**Models, run per measure:** `base`; `enroll_disease` (adds `kl_group0`, `womac_pain0`, `cohort`); `time_pain` (adds `womac_pain_t`; secondary); `age50` (rows with `age_at_visit >= 50`); `completers_168` (`after` contrast only, people with data at both 96 and 168 months).

**Multiplicity:** Holm applies only to `base` overall contrasts, in the spec's families: primary (2); other convergent (4); discriminative (Walker share and walker × KL tests). Divergent, period and visit rows have `p_holm = NA` and report `p = NA` for divergent overall rows, so no significance can be read from them.

- [ ] **Step 1: Write failing tests** in `tests/test_construct_validity_step.py`, on a synthetic frame written to a temp folder and the same environment the `step_copy` fixture in `test_walking_validation_realdata.py` uses:
  - `test_step_fits_nothing_until_approved`: gate false, so status is `awaiting_review` and only `construct_status.csv` exists.
  - `test_step_computes_when_approved`: gate true, so all five files exist, status `computed`.
  - `test_holm_families_follow_the_spec`: `p_holm` is non-null for exactly the 6 convergent and primary `base` overall rows plus the discriminative rows; divergent rows have null `p` and `p_holm`.
  - `test_kl4_combines_below_the_minimum`: a frame with 10 KL 4 non-walkers gives `kl_groups_used == "0-1,2-4"`; with 30 gives `"0-1,2-3,4"`.
  - `test_a_failed_model_is_recorded_and_the_step_continues`: one measure is unfittable, its row has `converged == FALSE`, and other measures have estimates.

- [ ] **Step 2: Run.** `uv run pytest tests/test_construct_validity_step.py -v`. Expected: FAIL.

- [ ] **Step 3: Write `construct_validity.R`,** with the gate check first, before reading the frame's walker column. Add the step to `analysis.toml`, with `needs = ["cohort"]`.

- [ ] **Step 4: Run.** Expected: PASS.

- [ ] **Step 5: Add the realdata test** `test_e2e_construct_step_waits_for_review` to the `fast_run` module: `construct_status.csv` says `awaiting_review`; `construct_contrasts.csv` does not exist.

- [ ] **Step 6: Run the full suite.** `uv run pytest -q`. Expected: PASS, with the gate false throughout.

- [ ] **Step 7: Commit** with message `feat(walking_validation): construct validity step, gated on scope approval`.

### Task 6: Scope summary for Grace, then stop

**Files:**
- Create: `analyses/walking_validation/SCOPE_FOR_REVIEW.md`, and a Word copy outside `report/` in `~/oai-work/results/walking_validation/`, built with `~/oai-work/tools` and docx-js.

- [ ] **Step 1: Write the summary,** at most two pages in plain language, with no new results:
  - the aim and the construct-validity frame;
  - the measures by facet, with each expectation;
  - the OR 1.44 rule and what narrows the conclusion;
  - KL comparisons and which goes in Table 1;
  - covariates, noting that BMI stays in, as she kept it in the abstract, with `pase_without_bmi` as the variant;
  - the 400-meter rationale;
  - the questions for her: facet assignments, KOOS sport as divergent, the KL analyses.

- [ ] **Step 2: Check it.** Every count comes from the spec or Task 2. `rg -i "walker.*(OR|odds|difference)"` finds nothing beyond numbers from the submitted abstract.

- [ ] **Step 3: Commit** with message `docs(walking_validation): scope summary for co-author review`.

- [ ] **Step 4: STOP.** Hand the summary to the user. Sending it to Grace is the user's action. Report that Stage 1 is complete and wait.

---

## Stage 2: only after the user confirms Grace's approval

### Task 7: Apply her changes and compute

**Files:**
- Modify: `analyses/walking_validation/assumptions.toml`, `ASSUMPTIONS.md`, and `tests/test_walking_validation.py`, `tests/test_walking_validation_realdata.py`

- [ ] **Step 1: Apply any changes she asks for** to the ledger, repeating Tasks 3–5's relevant tests. Record each change's source as her review, with the date.

- [ ] **Step 2: Flip the gate.** Set `construct.scope_approved = true`, with a source naming Grace Lo and the approval date the user gave. Update the Task 1 ledger test to expect true, and pin all rule values (`or_little`, `or_moderate`, `d_little`, `d_moderate`, `narrow_min_items`, `narrow_items`) and the whole `construct.expected` map in it, so a later edit to them fails a test. Commit this alone, before any run, with message `chore(walking_validation): record co-author approval of the brief report scope`.

- [ ] **Step 3: Run.** `uv run oai run walking_validation`, then `--variant pase_without_bmi`. Expected: `construct_status.csv` says `computed`, and all `converged` are true for `base`. Report any that are not to the user without changing the model. Also scan CI widths for huge finite ORs in every OR row (`construct_contrasts.csv`, `construct_kl.csv`, `construct_dose.csv`), since an unbounded estimate can come back as a large number with a clean fit; report any to the user.

- [ ] **Step 4: Replace the waiting test** with `test_e2e_construct_contrasts_reconcile`, on `fast_run`: `total` per-visit rows agree in direction with the abstract's `pase_walking_contrasts.csv`; every facet measure has a `base` overall row; `n_people` for `total` is at most 2,582.

- [ ] **Step 5: Report to the user before drafting:** the primary and period results, the rule's bands and whether it narrows, the KL results, and each sensitivity analysis, including any that goes against expectations. Interpretation stays with them.

- [ ] **Step 6: Commit** the tests.

### Task 8: The manuscript

**Files:**
- Create: `analyses/walking_validation/brief_report.qmd`, `analyses/walking_validation/brief_report_supplement.qmd`, `analyses/walking_validation/brief_report_tables.R`
- Modify: `analyses/walking_validation/analysis.toml`, `analyses/walking_validation/pase_figures.R`, `r/oaireport/R/abstract.R`, `r/oaireport/NAMESPACE`, `tests/test_walking_validation_realdata.py`, and `r/oaireport/tests/testthat/`

**Interfaces:**
- Produces:
  - `oaireport::word_budget(main, abstract, references, displays, limits)`: stops with the part and its count when over.
  - `fig_brief_report()` in `pase_figures.R`, reusing `pw_point_figure()`: panels A, PASE total; B, short-term walking.
  - `brief_report_table(run)`: rows grouped by facet.

**Wording set by the spec:**
- Methods includes the 400-meter sentence from Task 2. It never calls the test uninformative; the case is schedule, follow-up and non-comparable or missing values.
- The supplement holds participant characteristics, per-visit results, per-item results, dose, within-KL contrasts and all sensitivity analyses. If Task 2 finds no supplement is allowed, follow the spec's fallback.
- Limitations says both main measures are self-report and that this report makes no device comparison, with no device results.
- Conclusion is worded by which facets held. If `narrows` is true, it says the question marks generally active people, or people who report more activity, and is not specific to walking.
- Function differences are described as able to run either way.
- The text reads the early-visit gap as a stable habit, and notes people under 50 and recent starters.
- Group differences are not presented as individual accuracy.
- Cover material discloses the OARSI 2027 abstract.
- The supplement's per-item table is grouped by domain: recreation, household, work.
- KL 4, if shown alone, carries a wide-interval caveat.
- The text states why no direction is predicted for Walker share: walking may affect OA, and severe knees may have stopped people walking.
- KOOS missingness is stated, including that the reason running and jumping are blank is not documented.
- "A wide interval under the cutoff is not evidence of no link" appears where divergent results are read.
- Discussion order: the visits before the survey carry the argument, then divergent evidence, discriminative evidence, limitations.
- `time_pain` is labeled secondary wherever it appears.
- `n_people` and `n_obs` are model-level on period rows, so a table does not read them as that period's count.
- Confirm sex coding before labeling tables (`construct.code_labels` records `formats.pdf`; check the frame still reads it that way).
- Read Lo 2022's full text before the Discussion relies on it; only its abstract has been read.
- Add `pase_without_bmi` to `[report].runs` if the supplement reports it.
- Run a small-complement check on attrition before release: a group's count subtracted from a total must not reveal a small cell.

- [ ] **Step 1: Write the failing `oaireport` test** for `word_budget`: under limits it returns counts; 2,001 main words stop with a message naming "main text"; 3 displays stop.

- [ ] **Step 2: Implement it and pass.** `(cd r && RENV_PROFILE=report Rscript -e 'testthat::test_local("oaireport", filter = "abstract")')`.

- [ ] **Step 3: Write failing realdata tests** on `fast_run`:
  - `test_brief_report_within_journal_limits`, reading the word report the render writes to `text/brief_report_counts.txt`.
  - `test_brief_report_has_no_device_or_banned_terms`: `find_terms(pdf, ["bias", "correction", "corrected", "accelerometer", "accelerometry", "ActiGraph", "step count"], stop_heading="References") == []`, and "device" appears only in the limitations sentence.
  - `test_brief_report_names_the_400m_rationale`.
  - `test_abstract_paste_file_is_unchanged`: the SHA-256 in Global Constraints.
  - `test_kl_reporting_follows_the_fixed_rule`: Table 1 has Walker share; the supplement has within-KL contrasts.
  - `test_render_stops_when_a_required_row_is_missing`: remove one `base` row, and the render fails naming it.

- [ ] **Step 4: Write the tables, figure and both documents.** Add them to `[report].documents`. Results come from the run; every sentence with a number uses `sprintf` slots, as `abstract_pase.qmd` does.

- [ ] **Step 5: Render and test.** `uv run oai report walking_validation`, then `uv run pytest tests/test_walking_validation_realdata.py -k "brief_report or abstract_paste or kl_reporting" -v`. Expected: PASS.

- [ ] **Step 6: Read the rendered PDF** against the wording list above, and fix what the gates can't see.

- [ ] **Step 7: Commit** with message `feat(walking_validation): brief report and supplement`.

### Task 9: Word copy and final checks

**Files:**
- Create: `~/oai-work/tools/brief_report_docx.js`, outside the repo, modeled on `abstract_pase_docx.js`
- Modify: `analyses/walking_validation/README.md`, `TODO.md`

- [ ] **Step 1: Build the Word copy** for Grace's edits from the rendered text and figure, into `~/oai-work/results/walking_validation/`. Her edits return to the `text` chunk of `brief_report.qmd`, as with the abstract.

- [ ] **Step 2: Run everything.** `uv run pytest -q`, `(cd r && Rscript -e 'testthat::test_local("oaimodels")')`, `(cd r && RENV_PROFILE=report Rscript -e 'testthat::test_local("oaireport")')`, and `uv run oai check-egress` as the README describes. Expected: all pass.

- [ ] **Step 3: Record follow-ups** in `TODO.md`, with `<!-- skip -->` on human-only items: authorship, submission timing, and journal disclosure of the abstract. Describe the documents in `README.md`.

- [ ] **Step 4: Commit** with message `docs(walking_validation): brief report handoff`. Leave pushing and opening a PR to the user's request.
