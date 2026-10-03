# Answer-Level Sub-Analyses (Amendment 12) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the pre-specified answer-level sub-analyses of spec amendment 12 to `walking_validation`:
- PASE item 2's days and hours answers, separately and combined into estimated weekly walking, against the same visit's device wave;
- the 96-month item's amount answers as frequency-restricted walker definitions;
- the descriptive bias-analysis implications;

with a report section whose tables and figures all carry legends.

**Architecture:**
- **Python cohort step.** It puts the raw PASE item-2 answer codes and the per-wave MV minutes into the person frame.
- **R helpers.** Small, unit-tested functions in `oaimodels` (`R/agreement.R`) do the statistics.
- **New R step `components`.** It writes three aggregate CSVs.
- **Report.** `report.qmd` gains one section. Nothing already in the results folder changes: every existing CSV stays byte-identical.

**Tech Stack:** Python 3.11 (uv, polars, pytest), R (renv `report` profile, testthat 3e, hexbin), Quarto/Typst via `oaireport`.

**Spec:** `docs/superpowers/specs/2026-10-01-walking-validation-design.md`, §15b amendment 12 (with amendment 11 for legends).

## Global Constraints

- **Privacy and egress.**
  - The repository is public. Participant-level data stays under `OAI_WORK_DIR`.
  - Results and reports are aggregate only. `oai check-egress` must report 0 problems on `walking_validation/default` and `walking_validation/report`.
  - Hexagonal cells of the agreement figure with fewer than `components.min_cell_count` (10) participants are not written.
- **Public text.** Public text (code, docs, report) says "the original authors" or "the study team" and never describes a personal relationship.
- **R environment.**
  - `r/renv.lock` must not change. `hexbin` is already in the `report` profile lock.
  - `oaimodels` lists `hexbin` under Suggests only, and its tests skip without it.
- **Existing outputs.** Every CSV already produced by `oai run walking_validation` and `oai run lo2022_walking` stays byte-identical. This branch only adds files.
- **Randomness.** Every bootstrap and permutation uses `bias.seed` through `oaimodels::with_seed` / `preserve_rng`, so results are reproducible and the caller's RNG is untouched.
- **Answer codes.**
  - PASE: `VxxPASE2` 0 never, 1 = 1–2 days, 2 = 3–4 days, 3 = 5–7 days; 77 refused, 88 don't know. `VxxPASE2HR` 1 = under 1 hour, 2 = 1 to under 2 hours, 3 = 2–4 hours, 4 = over 4 hours; 88 don't know; skipped when never.
  - Item amounts (format names in parentheses): `V10WKTMAR4` (TMSMNTH) 1 = 1–3, 2 = 4–8, 3 = 9 or more times/month. `V10WKMOAR4` (MNTHYR) 1 = 1–4, 2 = 5–8, 3 = 9–12 months/year. `V10WKYRAR4` (YEAR7Z) 1 = 1–5, 2 = 6–10, 3 = 11–20, 4 = over 20 years; 88 don't know.
  - Source: the release's `formats.pdf` (TIME10X, TIME18X, TMSMNTH, MNTHYR, YEAR7Z). A code outside the answer codes is no answer, never a category.
- **Style.** ruff (line length 100). R in `oaimodels` style: namespaced calls, a hand-written NAMESPACE, testthat 3e.
- **Commits.**
  - Every commit ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
  - Commits are signed through 1Password. If signing fails, stop with the work staged and report BLOCKED; never bypass it.
  - Never set `assume-unchanged` or `skip-worktree`.
- **Branch.** Work on branch `feat/answer-level-components`. Do not push.

## Review Focus

1. **"Don't know" or refused answers** (PASE 77/88; amount 88) must be "no answer". They are never a category, they never crash, and walkers without an amount band are counted. Pinned in Task 1 (`test_pase_walking_answers_*`) and Task 2 (`answer_levels treats codes outside the answers as no level`).
2. **A never-walker with an hours answer** (inconsistent data): the hours answer is ignored. Pinned in Task 1 (`test_pase_walking_answers_ignores_hours_after_never`).
3. **A category, bin or cut with nobody in it**, or a visit with no paired participants (the `wave48`/`wave72` variants leave the other visit nearly empty): rows are still written with n = 0 and NA estimates, and nothing crashes. Pinned in Task 2 (`level_shares` / `weekly_bins` / `youden_ci` empty cases) and Task 3 (`test_components_handles_a_visit_without_paired_participants`).
4. **Privacy of the agreement figure:** only hexagonal cells with ≥ `components.min_cell_count` participants are written. Pinned in Task 2 (`hex_cells keeps only cells with at least min_count points`) and Task 3 (realdata: every written cell's count ≥ 10).
5. **Totals must reconcile.**
   - The category ns at a visit must sum to the participants with a PASE answer and a valid device wave there.
   - Each cut's Se and Sp denominators must sum to n.
   - The item levels plus the no-band count must equal the sample.

   Pinned in Task 3 (`test_e2e_components_reconcile`).

---

### Task 1: PASE answer codes, per-wave MV minutes and the components ledger

**Files:**
- Modify: `src/oai/derive/pase.py` (add `pase_walking_answers`)
- Modify: `analyses/walking_validation/wv.py:12` (`MEASURES` gains `"mv_min"`)
- Modify: `analyses/walking_validation/build_cohort.py` (PASE loop, about lines 56–62)
- Modify: `analyses/walking_validation/assumptions.toml` (new `components.*` keys), then regenerate `ASSUMPTIONS.md`
- Test: `tests/test_derive_walking.py`, `tests/test_walking_validation.py`, `tests/test_walking_validation_cohort.py`

**Interfaces:**
- Produces:
  - `oai.derive.pase.pase_walking_answers(allclinical: pl.DataFrame, visit: str) -> pl.DataFrame` with columns `ID`, `pase_days_<v>` (Int64, 0–3 or null) and `pase_hours_<v>` (Int64, 1–4 or null; null when days is 0).
  - Frame (`frame.parquet`) columns `pase_days_06`, `pase_hours_06`, `pase_days_08`, `pase_hours_08`, `mv_min`, `mv_min_06`, `mv_min_08`.
  - Ledger keys:
    - `components.pase_frequency_cuts` ([1, 2, 3]);
    - `components.pase_weekly_hours_bins` ([0.0, 2.0, 5.0, 10.0]);
    - `components.item_times_cuts` ([1, 2, 3]);
    - `components.item_months_cuts` ([1, 2, 3]);
    - `components.min_cell_count` (10);
    - `components.answer_labels` (a table of label lists, keyed `pase_days`, `pase_hours`, `times`, `months`, `years`).

- [ ] **Step 1: Write the failing tests for `pase_walking_answers`**

Append to `tests/test_derive_walking.py`, and add `pase_walking_answers` to the import from `oai.derive.pase` at the top:

```python
def test_pase_walking_answers_keeps_the_answer_codes():
    ac = pase_frame([0, 1, 2, 3, 77, 88, None], [None, 1, 4, 2, 3, 2, 1])
    out = pase_walking_answers(ac, "V06")
    assert out.columns == ["ID", "pase_days_06", "pase_hours_06"]
    assert out["pase_days_06"].to_list() == [0, 1, 2, 3, None, None, None]
    assert out["pase_hours_06"].to_list() == [None, 1, 4, 2, None, None, None]


def test_pase_walking_answers_ignores_hours_after_never():
    ac = pase_frame([0, 0], [2, 4])
    assert pase_walking_answers(ac, "V06")["pase_hours_06"].to_list() == [None, None]


def test_pase_walking_answers_drops_hours_codes_outside_the_answers():
    ac = pase_frame([1, 2, 3], [88, 5, 0])
    assert pase_walking_answers(ac, "V06")["pase_hours_06"].to_list() == [None, None, None]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_derive_walking.py -q -k pase_walking_answers`
Expected: FAIL with `ImportError: cannot import name 'pase_walking_answers'`.

- [ ] **Step 3: Implement `pase_walking_answers`**

Add to `src/oai/derive/pase.py`, after `score_pase`:

```python
DAYS_CODES = (0, 1, 2, 3)  # VxxPASE2: never, 1-2, 3-4, 5-7 days (77 refused, 88 don't know)
HOURS_CODES = (1, 2, 3, 4)  # VxxPASE2HR: <1, 1 to <2, 2-4, >4 hours (88 don't know)


def pase_walking_answers(allclinical: pl.DataFrame, visit: str) -> pl.DataFrame:
    """ID, pase_days_<v>, pase_hours_<v>: PASE item 2's answer codes (walking outside the home).

    A code outside the answer codes (refused, don't know) is no answer (null). Hours are asked
    only after a days answer other than never, so they are null when days is 0 or missing.
    """
    v = visit.removeprefix("V")
    col = partial(find_col, allclinical, where=f"allclinical{v}")
    raw_days = pl.col(col(f"V{v}PASE2")).cast(pl.Int64)
    raw_hours = pl.col(col(f"V{v}PASE2HR")).cast(pl.Int64)
    days = pl.when(raw_days.is_in(DAYS_CODES)).then(raw_days)
    hours = pl.when(raw_days.is_in(DAYS_CODES[1:]) & raw_hours.is_in(HOURS_CODES)).then(raw_hours)
    return allclinical.select(
        pl.col(col("ID")).alias("ID"),
        days.alias(f"pase_days_{v}"),
        hours.alias(f"pase_hours_{v}"),
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_derive_walking.py -q`
Expected: PASS (all tests in the file).

- [ ] **Step 5: Write the failing test for `mv_min` in `combine_waves`**

Find the existing `combine_waves` tests in `tests/test_walking_validation.py` with `grep -n "combine_waves" tests/test_walking_validation.py`. Their device fixture builds a frame with the columns of `MEASURES`. Add `"mv_min"` with any values to that fixture's column list, then append:

```python
def test_combine_waves_carries_mv_minutes_per_wave():
    device = pl.DataFrame(
        {
            "ID": [1, 1, 2],
            "wave": ["06", "08", "06"],
            "valid": [True, True, True],
            "purposeful_min": [10.0, 20.0, 5.0],
            "counts_per_day": [1.0, 1.0, 1.0],
            "light_min": [1.0, 1.0, 1.0],
            "bout_days_per_week": [1.0, 1.0, 1.0],
            "mv_min": [30.0, 50.0, 12.0],
        }
    )
    out = combine_waves(device, "mean").sort("ID")
    assert out["mv_min"].to_list() == [40.0, 12.0]
    assert out["mv_min_06"].to_list() == [30.0, 12.0]
    assert out["mv_min_08"].to_list() == [50.0, None]
```

Run: `uv run pytest tests/test_walking_validation.py -q -k mv_minutes`
Expected: FAIL with a `ColumnNotFoundError` or `KeyError` mentioning `mv_min`.

- [ ] **Step 6: Add `mv_min` to `MEASURES`**

In `analyses/walking_validation/wv.py`, change the line

```python
MEASURES = ("purposeful_min", "counts_per_day", "light_min", "bout_days_per_week")
```

to

```python
# Device measures carried into the frame, combined and per wave. mv_min (all moderate-to-vigorous
# minutes, bouted or not) is a comparator for estimated weekly walking (spec amendment 12a).
MEASURES = ("purposeful_min", "counts_per_day", "light_min", "bout_days_per_week", "mv_min")
```

Then add `"mv_min"` to every synthetic device frame in the tests. Find them with `grep -rn "bout_days_per_week\"\]" tests/` and `grep -rn "\"bout_days_per_week\"" tests/test_walking_validation*.py`. In `tests/test_walking_validation_cohort.py`, `device_frame()` becomes:

```python
def device_frame():
    rows = [(i, "06", True, 30.0, 100000.0, 200.0, 3.0, 45.0) for i in DEVICE_IDS]
    rows += [(1, "08", True, 35.0, 110000.0, 210.0, 2.0, 50.0)]  # person 1 has both waves
    measures = ["purposeful_min", "counts_per_day", "light_min", "bout_days_per_week", "mv_min"]
    return pl.DataFrame(rows, schema=["ID", "wave", "valid", *measures], orient="row")
```

Run: `uv run pytest tests/test_walking_validation.py tests/test_walking_validation_cohort.py -q`
Expected: PASS.

- [ ] **Step 7: Write the failing cohort-step test for the PASE answer columns**

In `tests/test_walking_validation_cohort.py`, in the `cohort` fixture, add this after the `score_pase` monkeypatch:

```python
    monkeypatch.setattr(
        pase,
        "pase_walking_answers",
        lambda df, visit: pl.DataFrame(
            {"ID": [1, 2], f"pase_days_{visit}": [3, 0], f"pase_hours_{visit}": [2, None]}
        ),
    )
```

Append this test:

```python
def test_cohort_frame_carries_pase_answers_and_mv_minutes(cohort):
    cohort()
    frame = pl.read_parquet(cohort.frames / "frame.parquet").sort("ID")
    for visit in ("06", "08"):
        assert frame.filter(pl.col("ID") == 1)[f"pase_days_{visit}"].item() == 3
        assert frame.filter(pl.col("ID") == 1)[f"pase_hours_{visit}"].item() == 2
        # person 2 has answers but no PASE subscore row in this fixture: the answers must survive
        assert frame.filter(pl.col("ID") == 2)[f"pase_days_{visit}"].item() == 0
        assert frame.filter(pl.col("ID") == 2)[f"pase_hours_{visit}"].item() is None
    assert "pase_days_10" not in frame.columns  # 96 months has no device wave to pair with
    assert {"mv_min", "mv_min_06", "mv_min_08"} <= set(frame.columns)
```

Run: `uv run pytest tests/test_walking_validation_cohort.py -q -k pase_answers`
Expected: FAIL. The frame lacks `pase_days_06`, giving a `ColumnNotFoundError`.

- [ ] **Step 8: Join the answers in the cohort step**

In `analyses/walking_validation/build_cohort.py`:
- change `from oai.derive.pase import score_pase` to `from oai.derive.pase import pase_walking_answers, score_pase`;
- replace the PASE loop with:

```python
pase = None
for visit in ("06", "08", "10"):
    table = read_table("allclinical", visit)
    scored = score_pase(table, visit, A["pase.walking_scoring"]).select(
        "ID", pl.col("pase_walking").alias(f"pase_walking_{visit}")
    )
    if visit in ("06", "08"):  # the visits with a device wave of their own (spec amendment 12a)
        scored = scored.join(
            pase_walking_answers(table, visit), on="ID", how="full", coalesce=True
        )
    pase = scored if pase is None else pase.join(scored, on="ID", how="full", coalesce=True)
```

Run: `uv run pytest tests/test_walking_validation_cohort.py -q`
Expected: PASS.

- [ ] **Step 9: Add the ledger keys**

Append to `analyses/walking_validation/assumptions.toml`, before the first `[variants.` table:

```toml
[components.pase_frequency_cuts]
value = [1, 2, 3]
status = "assumed"
source = "Spec amendment 12a: PASE item 2 frequency cuts on the days code (>= 1: at least 1-2 days; >= 2: at least 3-4 days; = 3: 5-7 days)"

[components.pase_weekly_hours_bins]
value = [0.0, 2.0, 5.0, 10.0]
status = "assumed"
source = "Spec amendment 12a: bin edges of estimated weekly walking hours (0; under 2; 2 to under 5; 5 to under 10; 10 or more)"

[components.item_times_cuts]
value = [1, 2, 3]
status = "assumed"
source = "Spec amendment 12b: frequency-restricted walker = a walker whose times-per-month band is at least k"

[components.item_months_cuts]
value = [1, 2, 3]
status = "assumed"
source = "Spec amendment 12b: the same for the months-per-year band (secondary)"

[components.min_cell_count]
value = 10
status = "assumed"
source = "Spec amendment 12 outputs: hexagonal cells of the agreement figure with fewer participants are not written, so the report stays aggregate"

[components.answer_labels]
value = { pase_days = ["Never", "1–2 days", "3–4 days", "5–7 days"], pase_hours = ["Under 1 hour", "1 to under 2 hours", "2–4 hours", "Over 4 hours"], times = ["1–3 times/month", "4–8 times/month", "9 or more times/month"], months = ["1–4 months/year", "5–8 months/year", "9–12 months/year"], years = ["1–5 years", "6–10 years", "11–20 years", "Over 20 years"] }
status = "confirmed"
source = "formats.pdf in the OAI release: TIME10X (VxxPASE2), TIME18X (VxxPASE2HR), TMSMNTH (V10WKTMAR4), MNTHYR (V10WKMOAR4), YEAR7Z (V10WKYRAR4); codes 77 (refused) and 88 (don't know) are no answer"
```

Run: `uv run oai assumptions walking_validation --write && uv run pytest tests/test_assumptions_ledgers.py tests/test_assumptions.py -q`
Expected: `ASSUMPTIONS.md` is rewritten and the tests PASS. If the ledger loader rejects a key or a status, read `src/oai/assumptions.py`, fix the TOML to its schema, and note what you changed in the report.

- [ ] **Step 10: Full suite, then commit**

Run: `uv run ruff check && uv run ruff format --check && uv run python scripts/check_no_data.py && uv run pytest -q`
Expected: all pass.

```bash
git add src/oai/derive/pase.py analyses/walking_validation/wv.py analyses/walking_validation/build_cohort.py analyses/walking_validation/assumptions.toml analyses/walking_validation/ASSUMPTIONS.md tests/test_derive_walking.py tests/test_walking_validation.py tests/test_walking_validation_cohort.py
git commit -m "feat(walking_validation): PASE item-2 answer codes and per-wave MV minutes in the frame; components ledger

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Agreement helpers in oaimodels

**Files:**
- Create: `r/oaimodels/R/agreement.R`
- Modify: `r/oaimodels/NAMESPACE`, `r/oaimodels/DESCRIPTION` (Suggests gains `hexbin`)
- Test: `r/oaimodels/tests/testthat/test-agreement.R`

**Interfaces:**
- Consumes: `wilson(k, n)`, `classification(test, reference)`, `with_seed(seed, expr)` and `quiet_exact_ties(expr)` from `R/validity.R` and `R/rng.R`.
- Produces (all exported):
  - `answer_levels(walker, code, n_codes)`: a factor with levels `c("none", "1", …, n_codes)`. Non-walkers are `"none"`, walkers get their code, and walkers whose code is outside 1..n_codes get NA.
  - `level_shares(reference, level)`: a data.frame with `level`, `estimate`, `lo`, `hi`, `k`, `n` (Wilson share of `reference` TRUE per level, in factor order).
  - `youden_ci(test, reference, reps = 1000, seed = 1)`: c(estimate, lo, hi, n).
  - `kappa_ci(a, b, reps = 1000, seed = 1)`: c(estimate, lo, hi, n).
  - `cut_classification(code, reference, cuts, reps = 1000, seed = 1)`: a data.frame with `cut`, `measure` (se, sp, ppv, npv, j), `estimate`, `lo`, `hi`, `n`.
  - `paired_agreement(x, y)`: c(estimate, lo, hi, loa_lo, loa_hi, n). The estimate is the one-sample Hodges–Lehmann estimate of x − y, and the limits are the 2.5th and 97.5th percentiles of x − y.
  - `weekly_bins(hours, edges)`: a factor with levels `"0"`, `"<e2"`, `"e2–e3"`, …, `"eK+"`.
  - `hex_cells(x, y, bins = 30, min_count = 10)`: a data.frame with `x`, `y`, `count`, `dx`, `dy`. These are hexagon centres and half-sizes for cells with at least `min_count` points.

- [ ] **Step 1: Write the failing tests**

Create `r/oaimodels/tests/testthat/test-agreement.R`:

```r
test_that("answer_levels treats codes outside the answers as no level", {
  walker <- c(FALSE, TRUE, TRUE, TRUE, NA)
  code <- c(NA, 2, 88, 3, 1)
  lv <- answer_levels(walker, code, n_codes = 3)
  expect_equal(levels(lv), c("none", "1", "2", "3"))
  expect_equal(as.character(lv), c("none", "2", NA, "3", NA))
})

test_that("level_shares gives each level's share with Wilson intervals, in factor order", {
  ref <- c(TRUE, FALSE, TRUE, TRUE, FALSE, NA)
  lv <- factor(c("b", "a", "b", "a", "a", "b"), levels = c("b", "a", "c"))
  s <- level_shares(ref, lv)
  expect_equal(s$level, c("b", "a", "c"))
  expect_equal(s$k, c(2, 1, 0))
  expect_equal(s$n, c(2, 3, 0))
  expect_equal(s$estimate[1:2], c(1, 1 / 3))
  expect_true(is.na(s$estimate[3]))
  w <- wilson(1, 3)
  expect_equal(s$lo[2], unname(w[["lo"]]))
  expect_error(level_shares(ref, as.character(lv)), "factor")
})

test_that("youden_ci is Se + Sp - 1 with a reproducible bootstrap interval", {
  test <- c(rep(TRUE, 8), rep(FALSE, 2), rep(TRUE, 3), rep(FALSE, 7))
  ref <- c(rep(TRUE, 10), rep(FALSE, 10))
  j <- youden_ci(test, ref, reps = 200, seed = 1)
  expect_equal(j[["estimate"]], 0.8 + 0.7 - 1)
  expect_equal(j[["n"]], 20)
  expect_true(j[["lo"]] <= j[["estimate"]] && j[["estimate"]] <= j[["hi"]])
  expect_identical(j, youden_ci(test, ref, reps = 200, seed = 1))
  expect_true(is.na(youden_ci(test, rep(TRUE, 20), reps = 10)[["estimate"]]))
  empty <- youden_ci(logical(0), logical(0), reps = 10)
  expect_true(is.na(empty[["estimate"]]))
  expect_equal(empty[["n"]], 0)
})

test_that("kappa_ci matches a hand-computed Cohen's kappa", {
  a <- c(rep(TRUE, 20), rep(TRUE, 5), rep(FALSE, 10), rep(FALSE, 15))
  b <- c(rep(TRUE, 20), rep(FALSE, 5), rep(TRUE, 10), rep(FALSE, 15))
  # agreement 35/50 = 0.7; chance 0.5 * 0.6 + 0.5 * 0.4 = 0.5; kappa = (0.7 - 0.5) / 0.5 = 0.4
  k <- kappa_ci(a, b, reps = 200, seed = 1)
  expect_equal(k[["estimate"]], 0.4)
  expect_equal(k[["n"]], 50)
  expect_true(k[["lo"]] < 0.4 && k[["hi"]] > 0.4)
})

test_that("cut_classification matches hand-computed tables at each cut", {
  code <- c(0, 1, 2, 3, 3, 0, 1, 2, NA)
  ref <- c(FALSE, FALSE, TRUE, TRUE, TRUE, FALSE, TRUE, FALSE, TRUE)
  cc <- cut_classification(code, ref, cuts = c(1, 3), reps = 50, seed = 1)
  at <- function(cut, m) cc[cc$cut == cut & cc$measure == m, ]
  # cut 1: TP 4, FP 2, FN 0, TN 2
  expect_equal(at(1, "se")$estimate, 1)
  expect_equal(at(1, "sp")$estimate, 0.5)
  expect_equal(at(1, "ppv")$estimate, 4 / 6)
  expect_equal(at(1, "npv")$estimate, 1)
  expect_equal(at(1, "j")$estimate, 0.5)
  expect_equal(at(1, "se")$n, 4)
  expect_equal(at(1, "ppv")$n, 6)
  # cut 3: TP 2, FP 0, FN 2, TN 4
  expect_equal(at(3, "se")$estimate, 0.5)
  expect_equal(at(3, "sp")$estimate, 1)
  expect_equal(at(3, "npv")$estimate, 4 / 6)
  expect_equal(at(3, "j")$estimate, 0.5)
})

test_that("paired_agreement gives the Hodges-Lehmann difference and percentile limits", {
  x <- c(10, 12, 15, 20, 30)
  y <- c(8, 11, 10, 25, 20)
  d <- x - y  # 2, 1, 5, -5, 10
  walsh <- outer(d, d, "+") / 2
  a <- paired_agreement(x, y)
  expect_equal(a[["estimate"]], stats::median(walsh[upper.tri(walsh, diag = TRUE)]))
  expect_equal(a[["loa_lo"]], unname(stats::quantile(d, 0.025)))
  expect_equal(a[["loa_hi"]], unname(stats::quantile(d, 0.975)))
  expect_equal(a[["n"]], 5)
  expect_true(a[["lo"]] <= a[["estimate"]] && a[["estimate"]] <= a[["hi"]])
  expect_true(is.na(paired_agreement(1, NA)[["estimate"]]))
})

test_that("weekly_bins puts zero in its own bin and is left-closed", {
  b <- weekly_bins(c(0, 0.75, 2, 4.5, 5, 9.99, 10, 30, NA), c(0, 2, 5, 10))
  expect_equal(levels(b), c("0", "<2", "2–5", "5–10", "10+"))
  expect_equal(as.character(b), c("0", "<2", "2–5", "2–5", "5–10", "5–10", "10+", "10+", NA))
  expect_error(weekly_bins(1, c(1, 2)), "start at 0")
})

test_that("hex_cells keeps only cells with at least min_count points", {
  skip_if_not_installed("hexbin")
  set.seed(3)
  x <- c(rep(1, 40), stats::runif(30, 0, 10))
  y <- c(rep(1, 40), stats::runif(30, 0, 10))
  cells <- hex_cells(x, y, bins = 10, min_count = 10)
  expect_true(nrow(cells) >= 1)
  expect_true(all(cells$count >= 10))
  expect_true(sum(cells$count) <= length(x))
  expect_true(any(abs(cells$x - 1) < 1 & abs(cells$y - 1) < 1))
  expect_true(all(cells$dx > 0 & cells$dy > 0))
  expect_equal(nrow(hex_cells(1:5, 1:5, bins = 10, min_count = 10)), 0)
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd r && RENV_PROFILE=report Rscript -e 'testthat::test_local("oaimodels", filter = "agreement")'`
Expected: FAIL with `could not find function "answer_levels"`, and similar for the others.

- [ ] **Step 3: Implement the helpers**

Create `r/oaimodels/R/agreement.R`:

```r
# Agreement between a self-report and the device (spec amendment 12): answer levels, shares by
# level, classification at cuts with Youden's J, Cohen's kappa, paired differences, weekly bins and
# aggregate hexagonal cells for a scatter.

#' Levels of an amount answer: "none" for non-walkers, the band code for walkers who gave one
#'
#' A walker whose code is outside 1..n_codes (88, don't know; or missing) has no level (NA).
answer_levels <- function(walker, code, n_codes) {
  band <- ifelse(!is.na(code) & code %in% seq_len(n_codes), code, NA)
  level <- ifelse(is.na(walker), NA, ifelse(!walker, "none", ifelse(is.na(band), NA, as.character(band))))
  factor(level, levels = c("none", as.character(seq_len(n_codes))))
}

#' Share of `reference` TRUE at each level of the factor `level`, with Wilson 95% intervals
level_shares <- function(reference, level) {
  if (!is.factor(level)) stop("level_shares(): level must be a factor (its levels give the order)", call. = FALSE)
  ok <- !is.na(reference) & !is.na(level)
  r <- as.logical(reference[ok])
  l <- level[ok]
  do.call(rbind, lapply(levels(level), function(lv) {
    k <- sum(r[l == lv])
    n <- sum(l == lv)
    w <- wilson(k, n)
    data.frame(level = lv, estimate = w[["estimate"]], lo = w[["lo"]], hi = w[["hi"]], k = k, n = n)
  }))
}

#' Youden's J (Se + Sp - 1) with a person-level percentile bootstrap interval
youden_ci <- function(test, reference, reps = 1000, seed = 1) {
  ok <- !is.na(test) & !is.na(reference)
  t <- as.logical(test[ok])
  r <- as.logical(reference[ok])
  j <- function(t, r) if (!any(r) || all(r)) NA_real_ else mean(t[r]) + mean(!t[!r]) - 1
  if (!length(t)) return(c(estimate = NA_real_, lo = NA_real_, hi = NA_real_, n = 0))
  boots <- with_seed(seed, replicate(reps, {
    i <- sample.int(length(t), replace = TRUE)
    j(t[i], r[i])
  }))
  q <- if (all(is.na(boots))) c(NA_real_, NA_real_) else stats::quantile(boots, c(0.025, 0.975), na.rm = TRUE, names = FALSE)
  c(estimate = j(t, r), lo = q[1], hi = q[2], n = length(t))
}

#' Cohen's kappa for two binary ratings, with a person-level percentile bootstrap interval
kappa_ci <- function(a, b, reps = 1000, seed = 1) {
  ok <- !is.na(a) & !is.na(b)
  a <- as.logical(a[ok])
  b <- as.logical(b[ok])
  kappa <- function(a, b) {
    pe <- mean(a) * mean(b) + mean(!a) * mean(!b)
    if (!length(a) || pe == 1) NA_real_ else (mean(a == b) - pe) / (1 - pe)
  }
  if (!length(a)) return(c(estimate = NA_real_, lo = NA_real_, hi = NA_real_, n = 0))
  boots <- with_seed(seed, replicate(reps, {
    i <- sample.int(length(a), replace = TRUE)
    kappa(a[i], b[i])
  }))
  q <- if (all(is.na(boots))) c(NA_real_, NA_real_) else stats::quantile(boots, c(0.025, 0.975), na.rm = TRUE, names = FALSE)
  c(estimate = kappa(a, b), lo = q[1], hi = q[2], n = length(a))
}

#' Classification of `reference` by `code >= cut`, at each cut: Se, Sp, PPV, NPV (Wilson) and J
cut_classification <- function(code, reference, cuts, reps = 1000, seed = 1) {
  do.call(rbind, lapply(cuts, function(cut) {
    test <- code >= cut
    cl <- classification(test, reference)
    j <- youden_ci(test, reference, reps = reps, seed = seed)
    rbind(
      data.frame(cut = cut, measure = cl$measure, estimate = cl$estimate, lo = cl$lo, hi = cl$hi, n = cl$n),
      data.frame(cut = cut, measure = "j", estimate = j[["estimate"]], lo = j[["lo"]], hi = j[["hi"]], n = j[["n"]])
    )
  }))
}

#' Paired agreement in the same units: the Hodges-Lehmann estimate of x - y (median of the Walsh
#' averages) with its Wilcoxon interval, and the 2.5th and 97.5th percentiles of x - y (limits of
#' agreement, without assuming normal differences)
paired_agreement <- function(x, y) {
  ok <- !is.na(x) & !is.na(y)
  d <- x[ok] - y[ok]
  if (length(d) < 2) {
    return(c(estimate = NA_real_, lo = NA_real_, hi = NA_real_, loa_lo = NA_real_, loa_hi = NA_real_, n = length(d)))
  }
  walsh <- outer(d, d, "+") / 2
  w <- quiet_exact_ties(stats::wilcox.test(d, conf.int = TRUE, exact = FALSE))
  loa <- stats::quantile(d, c(0.025, 0.975), names = FALSE)
  c(estimate = stats::median(walsh[upper.tri(walsh, diag = TRUE)]), lo = w$conf.int[1], hi = w$conf.int[2],
    loa_lo = loa[1], loa_hi = loa[2], n = length(d))
}

#' Bins of weekly hours from edges c(0, e2, ..., eK): "0", "<e2", "e2–e3", ..., "eK+" (left-closed)
weekly_bins <- function(hours, edges) {
  if (!length(edges) || edges[1] != 0) stop("weekly_bins(): edges must start at 0", call. = FALSE)
  inner <- edges[-1]
  fmt <- function(x) format(x, trim = TRUE, drop0trailing = TRUE)
  labels <- c("0", paste0("<", fmt(inner[1])), if (length(inner) > 1) paste0(fmt(utils::head(inner, -1)), "–", fmt(inner[-1])),
              paste0(fmt(utils::tail(inner, 1)), "+"))
  idx <- ifelse(is.na(hours), NA, ifelse(hours == 0, 1L, findInterval(hours, c(0, inner)) + 1L))
  factor(labels[idx], levels = labels)
}

#' Hexagonal cells of a scatter, as aggregate counts: centres (x, y), count and the hexagon's
#' half-width (dx) and vertex height (dy). Cells with fewer than `min_count` points are dropped,
#' so no cell describes fewer participants than that.
hex_cells <- function(x, y, bins = 30, min_count = 10) {
  empty <- data.frame(x = numeric(), y = numeric(), count = integer(), dx = numeric(), dy = numeric())
  ok <- !is.na(x) & !is.na(y)
  if (sum(ok) < min_count) return(empty)
  if (!requireNamespace("hexbin", quietly = TRUE)) stop("hex_cells() needs the hexbin package", call. = FALSE)
  hb <- hexbin::hexbin(x[ok], y[ok], xbins = bins)
  centres <- hexbin::hcell2xy(hb)
  # hexbin's own drawing geometry: inner radius 0.5 and outer 1/sqrt(3) in bin units
  sx <- hb@xbins / diff(hb@xbnds)
  sy <- (hb@xbins * hb@shape) / diff(hb@ybnds)
  cells <- data.frame(x = centres$x, y = centres$y, count = hb@count,
                      dx = 0.5 / sx, dy = (1 / sqrt(3)) / (2 * sy))
  cells[cells$count >= min_count, , drop = FALSE]
}
```

In `r/oaimodels/NAMESPACE`, append:

```
export(answer_levels)
export(level_shares)
export(youden_ci)
export(kappa_ci)
export(cut_classification)
export(paired_agreement)
export(weekly_bins)
export(hex_cells)
```

In `r/oaimodels/DESCRIPTION`, change the Suggests line to:

```
Suggests: testthat (>= 3.0.0), lme4, ordinal, geepack, survival, quantreg, hexbin
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd r && RENV_PROFILE=report Rscript -e 'testthat::test_local("oaimodels", filter = "agreement")'`
Expected: PASS, with 0 failures and 0 warnings.

- [ ] **Step 5: Both profiles, then commit**

Run: `cd r && Rscript -e 'testthat::test_local("oaimodels", stop_on_failure = TRUE)' && RENV_PROFILE=report Rscript -e 'testthat::test_local("oaimodels", stop_on_failure = TRUE)'`
Expected: PASS. In the default profile the hexbin test skips. Confirm `r/renv.lock` is unchanged with `git diff --exit-code -- r/renv.lock`.

```bash
git add r/oaimodels/R/agreement.R r/oaimodels/NAMESPACE r/oaimodels/DESCRIPTION r/oaimodels/tests/testthat/test-agreement.R
git commit -m "feat(oaimodels): agreement helpers (answer levels, shares, cut classification with J, kappa, paired agreement, weekly bins, hexagonal cells)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The `components` step

**Files:**
- Create: `analyses/walking_validation/components.R`
- Modify: `analyses/walking_validation/analysis.toml` (new step after `validity`)
- Test: `tests/test_walking_validation_realdata.py`

**Interfaces:**
- Consumes:
  - the Task 1 frame columns and ledger keys;
  - the Task 2 helpers;
  - the existing `oaimodels::jonckheere`, `spearman_ci`, `deattenuate`, `wave_reliability` and `classification`.
- Produces three CSVs in the run's results folder:
  - **`validity_components_pase.csv`** with columns `visit` ("06"/"08"), `component` (frequency, duration, weekly), `comparator`, `level`, `statistic`, `estimate`, `lo`, `hi`, `n`. The rows:
    - frequency × device_walker × level "0".."3": statistic `share`;
    - frequency × bout_days_per_week × level "0".."3": statistic `median` (lo/hi = IQR);
    - frequency × bout_days_per_week × level "all": statistics `jt_p` and `rho`;
    - frequency × device_walker × level "cut1".."cut3": statistics `se`, `sp`, `ppv`, `npv`, `j`;
    - duration × purposeful_min × level "1".."4": statistic `median`;
    - duration × purposeful_min × level "all": statistics `jt_p` and `rho`;
    - weekly × {purposeful_week, mv_week, light_week}:
      - level "all"/"pase_walkers": statistics `rho` and `rho_deattenuated`;
      - level "all": statistics `reliability`, `jt_p`, `hl_diff` (min/week) and `loa` (lo/hi);
      - level per bin ("0", "<2", "2–5", "5–10", "10+"): statistic `median`;
    - weekly × purposeful_week × level "guideline": statistics `se`, `sp`, `ppv`, `npv`, `j`, `kappa`.
  - **`validity_components_item.csv`** with columns `sample` (validation, lo_subset), `component` (times, months, years), `level`, `statistic`, `estimate`, `lo`, `hi`, `n`. The rows:
    - level "no_band": statistic `count`;
    - level "none"/"1".."k": statistics `share` and `median` (bout-days per week);
    - times/months × level "all": statistic `jt_p`;
    - times/months × level "cut1".."cut3": statistics `se`, `sp`, `ppv`, `npv`, `j`;
    - lo_subset × times × "cut1".."cut3": statistic `correction` (1/J, with lo = 1/J_hi and hi = 1/J_lo, or NA when the J limit ≤ 0).
  - **`validity_components_hex.csv`** with columns `visit`, `x` (mean of self-report and device, min/week), `y` (self-report − device), `count`, `dx`, `dy`. It holds the purposeful_week comparator only, and only cells with count ≥ `components.min_cell_count`.

- [ ] **Step 1: Write the failing realdata tests**

Append to `tests/test_walking_validation_realdata.py`:

```python
COMPONENTS_SCHEMA = {"visit": pl.Utf8, "level": pl.Utf8, "sample": pl.Utf8}


def _components(results: Path, name: str) -> pl.DataFrame:
    path = results / f"validity_components_{name}.csv"
    header = path.read_text().splitlines()[0].replace('"', "").split(",")
    overrides = {k: v for k, v in COMPONENTS_SCHEMA.items() if k in header}
    return pl.read_csv(path, null_values=["NA"], schema_overrides=overrides)


@pytest.mark.realdata
def test_e2e_components_reconcile(fast_run):
    out = fast_run.out
    work = fast_run.settings.work_dir / fast_run.analysis.name / out.name
    frame = pl.read_parquet(work / "frame.parquet")
    pase, item, hexes = (_components(out, n) for n in ("pase", "item", "hex"))
    for v in ("06", "08"):
        paired = frame.filter(
            pl.col(f"pase_days_{v}").is_not_null() & pl.col(f"device_walker_{v}").is_not_null()
        )
        at = pase.filter(pl.col("visit") == v)
        shares = at.filter((pl.col("component") == "frequency") & (pl.col("statistic") == "share"))
        assert shares["n"].sum() == paired.height  # every answer in exactly one category
        for cut in (1, 2, 3):
            rows = at.filter(pl.col("level") == f"cut{cut}")
            se_n = rows.filter(pl.col("statistic") == "se")["n"].item()
            sp_n = rows.filter(pl.col("statistic") == "sp")["n"].item()
            assert se_n + sp_n == paired.height  # the cut's 2x2 adds up to n
            assert se_n == paired[f"device_walker_{v}"].sum()
    for sample, rows in (("validation", frame), ("lo_subset", frame.filter("in_lo"))):
        for component in ("times", "months", "years"):
            sel = item.filter((pl.col("sample") == sample) & (pl.col("component") == component))
            levels_n = sel.filter(pl.col("statistic") == "share")["n"].sum()
            no_band = sel.filter(pl.col("level") == "no_band")["n"].item()
            assert levels_n + no_band == rows.height
    correction = item.filter(
        (pl.col("sample") == "lo_subset") & (pl.col("statistic") == "correction")
    )
    assert correction.height == 3
    assert hexes.height > 0
    assert (hexes["count"] >= 10).all()


@pytest.mark.realdata
def test_components_handles_a_visit_without_paired_participants(step_copy):
    _edit_frame(
        step_copy,
        lambda f: f.with_columns(pl.lit(None, dtype=pl.Boolean).alias("device_walker_08")),
    )
    done = step_copy.run("components")
    assert done.returncode == 0, done.stderr
    pase = _components(step_copy.results, "pase")
    later = pase.filter(pl.col("visit") == "08")
    assert later.height > 0
    shares = later.filter(pl.col("statistic") == "share")
    assert (shares["n"] == 0).all()
    assert shares["estimate"].is_null().all()
```

Run: `uv run pytest -m realdata -q tests/test_walking_validation_realdata.py -k components`
Expected: FAIL. The results folder lacks `validity_components_pase.csv`, so a `FileNotFoundError` is raised, and the second test fails because `select_steps` finds no step `components`. This takes several minutes, because the module fixture runs both analyses.

- [ ] **Step 2: Add the step to the manifest**

In `analyses/walking_validation/analysis.toml`, insert after the `validity` step:

```toml
[[steps]]
id = "components"
lang = "r"
stage = "local"
entry = "components.R"
needs = ["cohort"]
```

`[outputs].aggregate` already matches `validity_*.csv`.

- [ ] **Step 3: Write the step**

Create `analyses/walking_validation/components.R`:

```r
# Step `components`: answer-level sub-analyses (spec amendment 12). PASE item 2's days and hours
# answers, separately and combined into estimated weekly walking, against the device wave of the
# same visit (12a); the 96-month item's amount answers as frequency-restricted walker definitions
# (12b); and the record-level correction factor each definition would bring (12c, descriptive).
A <- oaimodels::assumptions()
visits <- c("06", "08")
weekly <- c(purposeful_week = "purposeful_min", mv_week = "mv_min", light_week = "light_min")
persons <- oaimodels::read_frame(required = c(
  "ID", "walker", "in_lo", "device_walker", "bout_days_per_week",
  "amount_times", "amount_months", "amount_years",
  paste0("pase_days_", visits), paste0("pase_hours_", visits),
  paste0("device_walker_", visits), paste0("bout_days_per_week_", visits),
  as.vector(outer(unname(weekly), visits, paste, sep = "_"))
))
out_dir <- Sys.getenv("OAI_RESULTS_DIR")
reps <- A[["validity.bootstrap_reps"]]
perms <- A[["validity.jt_permutations"]]
seed <- A[["bias.seed"]]
scoring <- A[["pase.walking_scoring"]]
freq_cuts <- A[["components.pase_frequency_cuts"]]
hour_edges <- A[["components.pase_weekly_hours_bins"]]
guideline <- A[["reference.min_bout_minutes_per_week"]]
item_cuts <- list(times = A[["components.item_times_cuts"]], months = A[["components.item_months_cuts"]])
min_cell <- A[["components.min_cell_count"]]
n_codes <- c(times = 3, months = 3, years = 4)
q <- function(x, p) if (any(!is.na(x))) unname(stats::quantile(x, p, na.rm = TRUE)) else NA_real_
# Small or empty selections give NA rather than an error or a misleading p = 1
safe_rho <- function(x, y) {
  n <- sum(stats::complete.cases(x, y))
  if (n < 4) return(c(rho = NA_real_, lo = NA_real_, hi = NA_real_, n = n))
  oaimodels::spearman_ci(x, y)
}
safe_jt <- function(x, group) {
  ok <- !is.na(x) & !is.na(group)
  if (length(unique(group[ok])) < 2) return(NA_real_)
  oaimodels::jonckheere(x[ok], droplevels(group[ok]), permutations = perms, seed = seed)[["p"]]
}
# Between-wave Spearman correlation of a device measure among everyone valid at both waves; for a
# single wave's measure this is its reliability (wave_reliability(r, 0) = r).
between_wave <- function(m) {
  a <- persons[[paste0(m, "_06")]]
  b <- persons[[paste0(m, "_08")]]
  both <- !is.na(a) & !is.na(b)
  if (sum(both) < 4) return(NA_real_)
  stats::cor(a[both], b[both], method = "spearman")
}

pase <- list(); item <- list(); hex <- list()
add <- function(...) pase[[length(pase) + 1]] <<- data.frame(..., stringsAsFactors = FALSE)
add_item <- function(...) item[[length(item) + 1]] <<- data.frame(..., stringsAsFactors = FALSE)
add_rows <- function(adder, base, rows) {
  for (i in seq_len(nrow(rows))) {
    do.call(adder, c(base, list(statistic = rows$measure[i], estimate = rows$estimate[i],
                                lo = rows$lo[i], hi = rows$hi[i], n = rows$n[i])))
  }
}

# 12a: PASE item 2, at each visit with its own device wave
for (v in visits) {
  days <- persons[[paste0("pase_days_", v)]]
  hours <- persons[[paste0("pase_hours_", v)]]
  dw <- persons[[paste0("device_walker_", v)]]
  bout_days <- persons[[paste0("bout_days_per_week_", v)]]
  at <- !is.na(days) & !is.na(dw)  # a PASE answer and a valid device wave at this visit

  # Frequency alone
  freq <- factor(days[at], levels = 0:3)
  shares <- oaimodels::level_shares(dw[at], freq)
  for (i in seq_len(nrow(shares))) {
    add(visit = v, component = "frequency", comparator = "device_walker", level = shares$level[i],
        statistic = "share", estimate = shares$estimate[i], lo = shares$lo[i], hi = shares$hi[i], n = shares$n[i])
    b <- bout_days[at][which(freq == shares$level[i])]
    add(visit = v, component = "frequency", comparator = "bout_days_per_week", level = shares$level[i],
        statistic = "median", estimate = q(b, 0.5), lo = q(b, 0.25), hi = q(b, 0.75), n = sum(!is.na(b)))
  }
  add(visit = v, component = "frequency", comparator = "bout_days_per_week", level = "all",
      statistic = "jt_p", estimate = safe_jt(bout_days[at], freq), lo = NA, hi = NA, n = sum(at))
  rho <- safe_rho(days[at], bout_days[at])
  add(visit = v, component = "frequency", comparator = "bout_days_per_week", level = "all",
      statistic = "rho", estimate = rho[["rho"]], lo = rho[["lo"]], hi = rho[["hi"]], n = rho[["n"]])
  cuts <- oaimodels::cut_classification(days[at], dw[at], freq_cuts, reps = reps, seed = seed)
  for (k in unique(cuts$cut)) {
    add_rows(add, list(visit = v, component = "frequency", comparator = "device_walker", level = paste0("cut", k)),
             cuts[cuts$cut == k, ])
  }

  # Duration alone, among PASE walkers
  walking <- at & days >= 1 & !is.na(hours)
  dur <- factor(hours[walking], levels = 1:4)
  pm <- persons[[paste0("purposeful_min_", v)]][walking]
  for (lv in levels(dur)) {
    x <- pm[which(dur == lv)]
    add(visit = v, component = "duration", comparator = "purposeful_min", level = lv,
        statistic = "median", estimate = q(x, 0.5), lo = q(x, 0.25), hi = q(x, 0.75), n = sum(!is.na(x)))
  }
  add(visit = v, component = "duration", comparator = "purposeful_min", level = "all",
      statistic = "jt_p", estimate = safe_jt(pm, dur), lo = NA, hi = NA, n = sum(walking))
  rho <- safe_rho(hours[walking], pm)
  add(visit = v, component = "duration", comparator = "purposeful_min", level = "all",
      statistic = "rho", estimate = rho[["rho"]], lo = rho[["lo"]], hi = rho[["hi"]], n = rho[["n"]])

  # Combined: estimated weekly walking (days x hours/day at the ledgered midpoints), in min/week
  report_min <- ifelse(is.na(days), NA,
                       ifelse(days == 0, 0, scoring$days[days + 1] * scoring$hours[hours] * 60))
  for (comp in names(weekly)) {
    device_min <- persons[[paste0(weekly[[comp]], "_", v)]] * 7
    ok <- at & !is.na(report_min) & !is.na(device_min)
    reliability <- oaimodels::wave_reliability(between_wave(weekly[[comp]]), 0)
    add(visit = v, component = "weekly", comparator = comp, level = "all", statistic = "reliability",
        estimate = reliability, lo = NA, hi = NA, n = NA)
    for (who in c("all", "pase_walkers")) {
      sel <- ok & (who == "all" | days >= 1)
      rho <- safe_rho(report_min[sel], device_min[sel])
      add(visit = v, component = "weekly", comparator = comp, level = who, statistic = "rho",
          estimate = rho[["rho"]], lo = rho[["lo"]], hi = rho[["hi"]], n = rho[["n"]])
      add(visit = v, component = "weekly", comparator = comp, level = who, statistic = "rho_deattenuated",
          estimate = if (is.na(rho[["rho"]]) || is.na(reliability)) NA else
            oaimodels::deattenuate(rho[["rho"]], reliability_y = reliability),
          lo = NA, hi = NA, n = rho[["n"]])
    }
    bins <- oaimodels::weekly_bins(report_min[ok] / 60, hour_edges)
    for (lv in levels(bins)) {
      x <- device_min[ok][which(bins == lv)]
      add(visit = v, component = "weekly", comparator = comp, level = lv, statistic = "median",
          estimate = q(x, 0.5), lo = q(x, 0.25), hi = q(x, 0.75), n = sum(!is.na(x)))
    }
    add(visit = v, component = "weekly", comparator = comp, level = "all", statistic = "jt_p",
        estimate = safe_jt(device_min[ok], bins), lo = NA, hi = NA, n = sum(ok))
    a <- oaimodels::paired_agreement(report_min[ok], device_min[ok])
    add(visit = v, component = "weekly", comparator = comp, level = "all", statistic = "hl_diff",
        estimate = a[["estimate"]], lo = a[["lo"]], hi = a[["hi"]], n = a[["n"]])
    add(visit = v, component = "weekly", comparator = comp, level = "all", statistic = "loa",
        estimate = NA, lo = a[["loa_lo"]], hi = a[["loa_hi"]], n = a[["n"]])
    if (comp == "purposeful_week") {
      self_meets <- report_min[ok] >= guideline
      device_meets <- device_min[ok] >= guideline
      cl <- oaimodels::classification(self_meets, device_meets)
      base <- list(visit = v, component = "weekly", comparator = comp, level = "guideline")
      add_rows(add, base, cl)
      j <- oaimodels::youden_ci(self_meets, device_meets, reps = reps, seed = seed)
      kap <- oaimodels::kappa_ci(self_meets, device_meets, reps = reps, seed = seed)
      add_rows(add, base, data.frame(measure = c("j", "kappa"), estimate = c(j[["estimate"]], kap[["estimate"]]),
                                     lo = c(j[["lo"]], kap[["lo"]]), hi = c(j[["hi"]], kap[["hi"]]),
                                     n = c(j[["n"]], kap[["n"]])))
      cells <- oaimodels::hex_cells((report_min[ok] + device_min[ok]) / 2, report_min[ok] - device_min[ok],
                                    bins = 30, min_count = min_cell)
      if (nrow(cells)) hex[[length(hex) + 1]] <- data.frame(visit = v, cells)
    }
  }
}

# 12b and 12c: the 96-month item's amount answers
samples <- list(validation = rep(TRUE, nrow(persons)), lo_subset = persons$in_lo)
inv <- function(x) ifelse(!is.na(x) & x > 0, 1 / x, NA)
for (sample in names(samples)) {
  s <- samples[[sample]] & !is.na(persons$device_walker) & !is.na(persons$walker)
  for (component in names(n_codes)) {
    level <- oaimodels::answer_levels(persons$walker[s], persons[[paste0("amount_", component)]][s], n_codes[[component]])
    no_band <- sum(persons$walker[s] & is.na(level))
    add_item(sample = sample, component = component, level = "no_band", statistic = "count",
             estimate = no_band, lo = NA, hi = NA, n = no_band)
    shares <- oaimodels::level_shares(persons$device_walker[s], level)
    bd <- persons$bout_days_per_week[s]
    for (i in seq_len(nrow(shares))) {
      add_item(sample = sample, component = component, level = shares$level[i], statistic = "share",
               estimate = shares$estimate[i], lo = shares$lo[i], hi = shares$hi[i], n = shares$n[i])
      b <- bd[which(level == shares$level[i])]
      add_item(sample = sample, component = component, level = shares$level[i], statistic = "median",
               estimate = q(b, 0.5), lo = q(b, 0.25), hi = q(b, 0.75), n = sum(!is.na(b)))
    }
    if (component %in% names(item_cuts)) {
      add_item(sample = sample, component = component, level = "all", statistic = "jt_p",
               estimate = safe_jt(bd, level), lo = NA, hi = NA, n = sum(!is.na(level)))
      # A frequency-restricted walker: a walker whose band is at least k. Non-walkers are code 0
      # (always below the cut); walkers without a band are left out (NA).
      code <- rep(NA_real_, length(level))
      code[which(level == "none")] <- 0
      banded <- which(!is.na(level) & level != "none")
      code[banded] <- as.numeric(as.character(level[banded]))
      cuts <- oaimodels::cut_classification(code, persons$device_walker[s], item_cuts[[component]],
                                            reps = reps, seed = seed)
      for (k in unique(cuts$cut)) {
        add_rows(add_item, list(sample = sample, component = component, level = paste0("cut", k)),
                 cuts[cuts$cut == k, ])
      }
      if (sample == "lo_subset" && component == "times") {
        js <- cuts[cuts$measure == "j", ]
        for (i in seq_len(nrow(js))) {
          add_item(sample = sample, component = component, level = paste0("cut", js$cut[i]),
                   statistic = "correction", estimate = inv(js$estimate[i]), lo = inv(js$hi[i]),
                   hi = inv(js$lo[i]), n = js$n[i])
        }
      }
    }
  }
}

write <- function(rows, name, empty) {
  df <- if (length(rows)) do.call(rbind, rows) else empty
  utils::write.csv(df, file.path(out_dir, name), row.names = FALSE)
}
write(pase, "validity_components_pase.csv", NULL)
write(item, "validity_components_item.csv", NULL)
write(hex, "validity_components_hex.csv",
      data.frame(visit = character(), x = numeric(), y = numeric(), count = integer(), dx = numeric(), dy = numeric()))
cat(sprintf("components: %d PASE rows, %d item rows, %d hexagonal cells\n",
            length(pase), length(item), sum(vapply(hex, nrow, integer(1)))))
```

- [ ] **Step 4: Run the realdata tests to verify they pass**

Run: `uv run pytest -m realdata -q tests/test_walking_validation_realdata.py -k components`
Expected: PASS, both tests. If the second test fails because a statistic errors on an empty selection, guard that call in the same way as `safe_rho` and `safe_jt`, and re-run.

- [ ] **Step 5: Full run, existing outputs unchanged, egress**

Before running, snapshot the current results: `mkdir -p /tmp/oai-pre-components && cp ~/oai-work/results/walking_validation/default/*.csv /tmp/oai-pre-components/`. Put this under the session scratchpad if one is configured.

Run: `uv run oai run walking_validation`. It takes about 8 minutes.

Then, for each CSV in the snapshot, run `cmp` against the new results folder. Expected: every existing CSV is byte-identical. The only new files are the three `validity_components_*.csv`.

Run: `uv run oai check-egress ~/oai-work/results/walking_validation/default`
Expected: 0 problems.

Print the headline rows for the report to check against later:

```bash
uv run python -c "
import polars as pl, pathlib
r = pathlib.Path('~/oai-work/results/walking_validation/default').expanduser()
p = pl.read_csv(r / 'validity_components_pase.csv', null_values=['NA'], schema_overrides={'visit': pl.Utf8, 'level': pl.Utf8})
print(p.filter(pl.col('statistic').is_in(['share','rho','j','kappa','hl_diff','loa'])).to_pandas().to_string())
"
```

- [ ] **Step 6: Commit**

```bash
git add analyses/walking_validation/components.R analyses/walking_validation/analysis.toml tests/test_walking_validation_realdata.py
git commit -m "feat(walking_validation): components step — PASE item-2 answers and weekly walking vs the same visit's device wave; item amount answers as frequency-restricted walkers

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Report section "Answer-level sub-analyses"

**Files:**
- Modify: `analyses/walking_validation/report.qmd`. Insert a new top-level section between the PASE benchmark section and `# Bias analysis of Lo et al. 2022`.

**Interfaces:**
- Consumes:
  - `run$validity_components_pase`, `run$validity_components_item` and `run$validity_components_hex` (CSV stems via `oaireport::load_results`);
  - `assumption("components.answer_labels")`;
  - the report's existing helpers: `num`, `count`, `wave`, `assumption`, `named`, `oaireport::compare_table`, `table_note`, `figure_group`, `save_figure`, `theme_oai`, `oai_palette`.
- Produces:
  - five tables, each with a legend;
  - three figures, each with a legend, saved as `components_roc`, `components_calibration` and `components_agreement` (PDF and PNG).

This section is deliberately plain. A later plan redesigns the whole report for an external audience. It must still be correct, legible and fully legended.

- [ ] **Step 1: Add the setup chunk and the frequency table**

Insert before `# Bias analysis of Lo et al. 2022`:

````markdown
# Answer-level sub-analyses

```{r components-setup}
cp <- run$validity_components_pase
ci <- run$validity_components_item
hx <- run$validity_components_hex
cp$visit <- sprintf("%02d", as.integer(cp$visit))
if (nrow(hx)) hx$visit <- sprintf("%02d", as.integer(hx$visit))
answer_labels <- lapply(assumption("components.answer_labels"), unlist)
comp_jt_b <- assumption("validity.jt_permutations")
comp_p <- function(p) {
  floor_p <- 1 / (comp_jt_b + 1)
  ifelse(is.na(p), "–", ifelse(p <= floor_p, sprintf("≤ %s", formatC(floor_p, format = "g", digits = 1)),
                              formatC(p, format = "g", digits = 2)))
}
cp_get <- function(v, component, comparator, level, statistic, col = "estimate") {
  x <- cp[cp$visit == v & cp$component == component & cp$comparator == comparator &
          cp$level == level & cp$statistic == statistic, col]
  if (length(x) == 1) x else NA
}
ci_get <- function(sample, component, level, statistic, col = "estimate") {
  x <- ci[ci$sample == sample & ci$component == component & ci$level == level & ci$statistic == statistic, col]
  if (length(x) == 1) x else NA
}
est_ci <- function(est, lo, hi, digits = 2) {
  ifelse(is.na(est), "–", ifelse(is.na(lo), num(est, digits),
         sprintf("%s (%s to %s)", num(est, digits), num(lo, digits), num(hi, digits))))
}
pct_ci <- function(est, lo, hi) {
  ifelse(is.na(est), "–", sprintf("%s (%s–%s)", num(100 * est, 0), num(100 * lo, 0), num(100 * hi, 0)))
}
med_iqr <- function(m, lo, hi, digits = 1) ifelse(is.na(m), "–", sprintf("%s (%s–%s)", num(m, digits), num(lo, digits), num(hi, digits)))
comp_visits <- c("06", "08")
```

PASE item 2 asks about walking outside the home in the past 7 days in two parts: on how many days, and for how many hours a day. Each part is compared here with the device wave of the same visit, first separately and then combined into an estimate of weekly walking time. The walking item's own amount answers are then examined the same way. These analyses are secondary. They were pre-specified on 2026-10-02 after an exploratory look at the PASE frequency answer, and they are reported for every pre-listed cut, without choosing an optimal one.

```{r components-frequency}
freq_table <- do.call(rbind, lapply(comp_visits, function(v) {
  data.frame(
    Answer = answer_labels$pase_days,
    n = count(sapply(0:3, function(l) cp_get(v, "frequency", "device_walker", as.character(l), "share", "n"))),
    `Device walkers, % (95% CI)` = sapply(0:3, function(l) pct_ci(
      cp_get(v, "frequency", "device_walker", as.character(l), "share"),
      cp_get(v, "frequency", "device_walker", as.character(l), "share", "lo"),
      cp_get(v, "frequency", "device_walker", as.character(l), "share", "hi"))),
    `Bout-days/week, median (IQR)` = sapply(0:3, function(l) med_iqr(
      cp_get(v, "frequency", "bout_days_per_week", as.character(l), "median"),
      cp_get(v, "frequency", "bout_days_per_week", as.character(l), "median", "lo"),
      cp_get(v, "frequency", "bout_days_per_week", as.character(l), "median", "hi"))),
    check.names = FALSE)
}))
tinytable::group_tt(oaireport::compare_table(freq_table, widths = c(1.6, 0.7, 1.8, 1.8)),
                    i = stats::setNames(list(1, 5), wave(comp_visits)))
```

```{r note-components-frequency}
#| results: asis
trend <- vapply(comp_visits, function(v) sprintf("%s: Jonckheere–Terpstra p %s, Spearman ρ %s",
  wave(v), comp_p(cp_get(v, "frequency", "bout_days_per_week", "all", "jt_p")),
  est_ci(cp_get(v, "frequency", "bout_days_per_week", "all", "rho"),
         cp_get(v, "frequency", "bout_days_per_week", "all", "rho", "lo"),
         cp_get(v, "frequency", "bout_days_per_week", "all", "rho", "hi"))), character(1))
cat(oaireport::table_note(sprintf(
  "Validation-sample participants with a PASE walking answer and a valid device wave at the same visit. Answer: on how many of the past 7 days the participant walked outside the home (PASE item 2). n: participants giving that answer. Device walkers: the share who are device walkers at that visit's device wave (as defined under Classification), with Wilson 95%% CI. Bout-days/week: that wave's days per week with a purposeful bout (median and interquartile range). Trend in bout-days/week across the four answers and its rank correlation with the answer: %s.",
  paste(trend, collapse = "; "))), sep = "\n")
```
````

Run: `uv run oai report walking_validation` (without `--run`, from the Task 3 results). Render page images with the scratchpad `pdfcheck/page.swift` and read the page with this table.
Expected: the table shows both visits with the n, share and median columns, and the legend sits directly under it.

- [ ] **Step 2: Add the cut table and the ROC-points figure**

Append inside the same section:

````markdown
```{r components-cuts}
pase_cut_names <- c(cut1 = sprintf("At least %s", answer_labels$pase_days[2]),
                    cut2 = sprintf("At least %s", answer_labels$pase_days[3]),
                    cut3 = answer_labels$pase_days[4])
item_cut_names <- c(cut1 = sprintf("Walker, at least %s", answer_labels$times[1]),
                    cut2 = sprintf("Walker, at least %s", answer_labels$times[2]),
                    cut3 = sprintf("Walker, %s", answer_labels$times[3]))
cut_row <- function(get, definition) {
  cell <- function(m) est_ci(get(m), get(m, "lo"), get(m, "hi"))
  data.frame(Definition = definition, Se = cell("se"), Sp = cell("sp"), PPV = cell("ppv"),
             NPV = cell("npv"), J = cell("j"), n = count(get("se", "n") + get("sp", "n")), check.names = FALSE)
}
cut_blocks <- list(); cut_points <- list()
for (v in comp_visits) for (k in names(pase_cut_names)) {
  get <- function(m, col = "estimate") cp_get(v, "frequency", "device_walker", k, m, col)
  cut_blocks[[paste("PASE", v)]] <- rbind(cut_blocks[[paste("PASE", v)]], cut_row(get, pase_cut_names[[k]]))
  cut_points[[length(cut_points) + 1]] <- data.frame(source = sprintf("PASE days, %s", wave(v)), cut = k,
    se = get("se"), fpr = 1 - get("sp"), current = k == "cut1")
}
for (s in c("validation", "lo_subset")) for (k in names(item_cut_names)) {
  get <- function(m, col = "estimate") ci_get(s, "times", k, m, col)
  cut_blocks[[paste("Item", s)]] <- rbind(cut_blocks[[paste("Item", s)]], cut_row(get, item_cut_names[[k]]))
  if (s == "validation") cut_points[[length(cut_points) + 1]] <- data.frame(source = "Walking item, times/month",
    cut = k, se = get("se"), fpr = 1 - get("sp"), current = k == "cut1")
}
cut_table <- do.call(rbind, cut_blocks)
block_titles <- c(sprintf("PASE walking days, %s", wave(comp_visits)),
                  sprintf("Walking item, times per month: %s", c("validation sample", "Lo 2022 subset")))
starts <- cumsum(c(1, vapply(cut_blocks, nrow, integer(1))))[seq_along(cut_blocks)]
tinytable::group_tt(oaireport::compare_table(cut_table, widths = c(2.4, 1.6, 1.6, 1.6, 1.6, 1.6, 0.7)),
                    i = as.list(stats::setNames(starts, block_titles)))
```

```{r note-components-cuts}
#| results: asis
cat(oaireport::table_note(paste(
  "Each row classifies participants as walkers by one cut of an answer and compares that with the device walker (as defined under Classification): for PASE, the device walker at the same visit's device wave; for the walking item, over the participant's valid waves.",
  "Se, Sp, PPV, NPV: as defined under Classification, with Wilson 95% CIs. J: Youden's J = Se + Sp − 1, with a person-level bootstrap 95% CI; 0 means no better than chance and 1 is perfect.",
  "The first PASE row (any walking) is the PASE walker used elsewhere in this report. The first walking-item row is the item walker, among walkers who gave a times-per-month answer; walkers without one are left out of these rows.",
  "n: participants classified.")), sep = "\n")
```

```{r components-roc}
#| fig-height: 3.4
#| results: asis
cat(oaireport::figure_group(), sep = "\n")
pts <- do.call(rbind, cut_points)
iso <- do.call(rbind, lapply(c(0, 0.1, 0.2, 0.3, 0.4), function(j) data.frame(j = j, fpr = c(0, 1 - j), se = c(j, 1))))
roc <- ggplot2::ggplot(pts, ggplot2::aes(fpr, se, colour = source, shape = current)) +
  ggplot2::geom_line(data = iso, ggplot2::aes(fpr, se, group = j), inherit.aes = FALSE,
                     linewidth = 0.25, colour = "grey75", linetype = "dashed") +
  ggplot2::geom_text(data = iso[iso$fpr == 0, ], ggplot2::aes(x = 0.02, y = se, label = paste0("J = ", j)),
                     inherit.aes = FALSE, size = 2.2, colour = "grey45", hjust = 0, vjust = -0.3) +
  ggplot2::geom_line(ggplot2::aes(group = source), linewidth = 0.4) +
  ggplot2::geom_point(size = 2.2) +
  ggplot2::scale_colour_manual(values = oaireport::oai_palette[1:3]) +
  ggplot2::scale_shape_manual(values = c(`TRUE` = 17, `FALSE` = 16), labels = c(`TRUE` = "Definition used elsewhere", `FALSE` = "Stricter cut")) +
  ggplot2::coord_equal(xlim = c(0, 1), ylim = c(0, 1)) +
  ggplot2::labs(x = "1 − specificity", y = "Sensitivity") + oaireport::theme_oai() +
  ggplot2::theme(legend.box = "vertical")
oaireport::save_figure(roc, "components_roc", "2col", height = 3.4)
print(roc)
cat(oaireport::table_note("Each point is one cut from the table above, placed by its sensitivity and 1 − specificity against the device walker; points on a line are the cuts of one answer, from least strict (top right) to strictest. Triangles mark the definitions used elsewhere in this report (any PASE walking; the walking item). Dashed lines join points of equal Youden's J; further up and to the left is better.", close_group = TRUE), sep = "\n")
```
````

Run: `uv run oai report walking_validation` and read the pages.
Expected:
- The cut table shows four blocks of three rows each, and nothing overflows the margin. Check with `pdftotext -bbox`: the xMax of the widest row must be ≤ 547.2 pt.
- The ROC figure shows three lines of three points, with J contours.

- [ ] **Step 3: Add the weekly-walking tables and figures**

Append:

````markdown
```{r components-weekly}
comparator_names <- c(purposeful_week = "Purposeful-bout minutes", mv_week = "All moderate-to-vigorous minutes",
                      light_week = "Light minutes")
weekly_table <- do.call(rbind, lapply(names(comparator_names), function(cmp) {
  cells <- unlist(lapply(comp_visits, function(v) {
    r <- function(level, stat, col = "estimate") cp_get(v, "weekly", cmp, level, stat, col)
    c(est_ci(r("all", "rho"), r("all", "rho", "lo"), r("all", "rho", "hi")),
      num(r("all", "rho_deattenuated")),
      est_ci(r("pase_walkers", "rho"), r("pase_walkers", "rho", "lo"), r("pase_walkers", "rho", "hi")),
      sprintf("%s (%s to %s)", num(r("all", "hl_diff"), 0), num(r("all", "loa", "lo"), 0), num(r("all", "loa", "hi"), 0)))
  }))
  as.data.frame(as.list(c(Comparator = comparator_names[[cmp]], cells)), check.names = FALSE)
}))
names(weekly_table) <- c("Device measure (per week)", rep(c("ρ, all (95% CI)", "Deattenuated ρ", "ρ, PASE walkers (95% CI)",
                                                           "Self-report − device, min/week (limits)"), 2))
tinytable::group_tt(oaireport::compare_table(weekly_table, widths = c(2.2, rep(c(1.6, 0.9, 1.6, 1.9), 2))),
                    j = stats::setNames(list(2:5, 6:9), wave(comp_visits)))
```

```{r note-components-weekly}
#| results: asis
cat(oaireport::table_note(sprintf(paste(
  "Estimated weekly walking: days walked in the past 7 days × hours per day, both at the PASE scoring midpoints (days %s; hours %s), in minutes per week; 0 for participants who did not walk.",
  "Each device measure is that visit's wave, per valid day × 7. Purposeful-bout minutes: moderate-to-vigorous minutes inside purposeful bouts (as defined under Classification); all moderate-to-vigorous minutes, bouted or not; light minutes, because walking outside the home includes slow walking.",
  "ρ: Spearman rank correlation with a 95%% CI, in everyone and among PASE walkers. Deattenuated ρ: ρ divided by the square root of the single-wave device reliability (the between-wave ρ of that measure).",
  "Self-report − device: the Hodges–Lehmann median difference per person, with the 2.5th and 97.5th percentiles of the differences (limits of agreement) in brackets.",
  "PASE counts walking of any intensity, the device counts activity above set intensities, so part of any difference is a difference in what is measured, not only error."),
  paste(num(unlist(assumption("pase.walking_scoring")$days), 1), collapse = "/"),
  paste(num(unlist(assumption("pase.walking_scoring")$hours), 1), collapse = "/"))), sep = "\n")
```

```{r components-guideline}
guide_minutes <- assumption("reference.min_bout_minutes_per_week")
guide_table <- do.call(rbind, lapply(comp_visits, function(v) {
  r <- function(stat, col = "estimate") cp_get(v, "weekly", "purposeful_week", "guideline", stat, col)
  data.frame(Visit = wave(v), Se = est_ci(r("se"), r("se", "lo"), r("se", "hi")),
             Sp = est_ci(r("sp"), r("sp", "lo"), r("sp", "hi")), J = est_ci(r("j"), r("j", "lo"), r("j", "hi")),
             `Cohen's κ` = est_ci(r("kappa"), r("kappa", "lo"), r("kappa", "hi")),
             n = count(r("se", "n") + r("sp", "n")), check.names = FALSE)
}))
oaireport::compare_table(guide_table, widths = c(1.2, 1.8, 1.8, 1.8, 1.8, 0.8))
```

```{r note-components-guideline}
#| results: asis
cat(oaireport::table_note(sprintf("Agreement at the guideline volume: estimated weekly walking of at least %s minutes against device purposeful-bout minutes of at least %s per week at the same visit. Se, Sp, J as in the cut table; Cohen's κ: agreement beyond chance (0 none, 1 perfect), with a person-level bootstrap 95%% CI. n: participants classified.",
  num(guide_minutes, 0), num(guide_minutes, 0))), sep = "\n")
```

```{r components-calibration}
#| fig-height: 3
#| results: asis
cat(oaireport::figure_group(), sep = "\n")
# The step writes the bins in order, so their order of appearance is the bin order
cal <- cp[cp$component == "weekly" & cp$comparator == "purposeful_week" & cp$statistic == "median", ]
bin_levels <- unique(cal$level)
cal$level <- factor(cal$level, levels = bin_levels)
cal$visit_name <- wave(cal$visit)
calib <- ggplot2::ggplot(cal, ggplot2::aes(level, estimate)) +
  ggplot2::geom_pointrange(ggplot2::aes(ymin = lo, ymax = hi), colour = oaireport::oai_palette[1], size = 0.3) +
  ggplot2::geom_text(ggplot2::aes(y = hi, label = paste0("n = ", n)), vjust = -0.6, size = 2.2, colour = "grey35") +
  ggplot2::facet_wrap(~visit_name) +
  ggplot2::labs(x = "Estimated weekly walking from PASE (hours per week)", y = "Device purposeful-bout minutes per week") +
  oaireport::theme_oai()
oaireport::save_figure(calib, "components_calibration", "2col", height = 3)
print(calib)
cat(oaireport::table_note("Device purposeful-bout minutes per week (median and interquartile range) within each band of estimated weekly walking from PASE, at each visit's device wave. n: participants in the band. A self-report that tracked the device would show medians rising steadily from left to right.", close_group = TRUE), sep = "\n")
```

```{r components-agreement}
#| fig-height: 3.2
#| results: asis
cat(oaireport::figure_group(), sep = "\n")
if (nrow(hx)) {
  offsets <- data.frame(vertex = 1:6, ox = c(1, 0, -1, -1, 0, 1), oy = c(1, 2, 1, -1, -2, -1))
  hx$cell <- seq_len(nrow(hx))
  poly <- merge(hx, offsets, by = NULL)
  poly$px <- poly$x + poly$ox * poly$dx
  poly$py <- poly$y + poly$oy * poly$dy
  poly <- poly[order(poly$cell, poly$vertex), ]
  poly$visit_name <- wave(poly$visit)
  lines <- do.call(rbind, lapply(comp_visits, function(v) data.frame(visit_name = wave(v),
    y = c(cp_get(v, "weekly", "purposeful_week", "all", "hl_diff"),
          cp_get(v, "weekly", "purposeful_week", "all", "loa", "lo"),
          cp_get(v, "weekly", "purposeful_week", "all", "loa", "hi")),
    kind = c("Median difference", "Limits of agreement", "Limits of agreement"))))
  agree <- ggplot2::ggplot(poly, ggplot2::aes(px, py, group = cell, fill = count)) +
    ggplot2::geom_polygon(colour = NA) +
    ggplot2::geom_hline(data = lines, ggplot2::aes(yintercept = y, linetype = kind), linewidth = 0.3) +
    ggplot2::scale_fill_gradient(low = "#cde2fb", high = "#0b3c8c", name = "Participants") +
    ggplot2::scale_linetype_manual(values = c(`Median difference` = "solid", `Limits of agreement` = "dashed"), name = NULL) +
    ggplot2::facet_wrap(~visit_name) +
    ggplot2::labs(x = "Mean of self-report and device (minutes per week)", y = "Self-report − device (minutes per week)") +
    oaireport::theme_oai()
  oaireport::save_figure(agree, "components_agreement", "2col", height = 3.2)
  print(agree)
}
cat(oaireport::table_note(sprintf("Each hexagon counts the participants whose mean of estimated weekly walking (PASE) and device purposeful-bout minutes per week (x) and difference between them (y) fall in it; hexagons with fewer than %s participants are not shown, so the figure shows no individual. Solid line: the median difference; dashed lines: its limits of agreement (2.5th and 97.5th percentiles).",
  num(assumption("components.min_cell_count"), 0)), close_group = TRUE), sep = "\n")
```
````

Run: `uv run oai report walking_validation` and read the pages.
Expected: the weekly table fits the page width. Check xMax ≤ 547.2 pt. If it does not fit, split it into one table per visit rather than shrinking the type. The two figures render with their legends kept on the same page.

- [ ] **Step 4: Add the item-component tables**

Append:

````markdown
```{r components-item}
item_table <- do.call(rbind, lapply(c("times", "months", "years"), function(component) {
  lv <- c("none", as.character(seq_along(answer_labels[[component]])))
  nm <- c("Non-walkers", answer_labels[[component]])
  data.frame(
    Answer = nm,
    n = count(sapply(lv, function(l) ci_get("validation", component, l, "share", "n"))),
    `Device walkers, % (95% CI)` = sapply(lv, function(l) pct_ci(ci_get("validation", component, l, "share"),
      ci_get("validation", component, l, "share", "lo"), ci_get("validation", component, l, "share", "hi"))),
    `Bout-days/week, median (IQR)` = sapply(lv, function(l) med_iqr(ci_get("validation", component, l, "median"),
      ci_get("validation", component, l, "median", "lo"), ci_get("validation", component, l, "median", "hi"))),
    check.names = FALSE)
}))
component_titles <- c("Times per month (walkers since age 50)", "Months per year", "Years walked")
sizes <- vapply(c("times", "months", "years"), function(cmp) length(answer_labels[[cmp]]) + 1L, integer(1))
tinytable::group_tt(oaireport::compare_table(item_table, widths = c(1.8, 0.7, 1.8, 1.8)),
                    i = as.list(stats::setNames(cumsum(c(1, sizes))[1:3], component_titles)))
```

```{r note-components-item}
#| results: asis
no_band <- vapply(c("times", "months", "years"), function(cmp) ci_get("validation", cmp, "no_band", "count"), numeric(1))
cat(oaireport::table_note(sprintf(
  "Validation sample. Answer: the walking item's amount answers (how many times per month, months per year and years the participant walked for exercise since age 50), with non-walkers as their own row. Device walkers and bout-days/week: as in the PASE frequency table, over the participant's valid device waves. Walkers who did not give a usable answer (left blank or don't know) are not in that block's rows: %s for times per month, %s for months per year and %s for years. Trend in bout-days/week from non-walkers through the bands (Jonckheere–Terpstra): times per month p %s; months per year p %s.",
  count(no_band[["times"]]), count(no_band[["months"]]), count(no_band[["years"]]),
  comp_p(ci_get("validation", "times", "all", "jt_p")), comp_p(ci_get("validation", "months", "all", "jt_p")))), sep = "\n")
```

```{r components-correction}
correction_table <- do.call(rbind, lapply(names(item_cut_names), function(k) {
  g <- function(stat, col = "estimate") ci_get("lo_subset", "times", k, stat, col)
  data.frame(Definition = item_cut_names[[k]], Se = est_ci(g("se"), g("se", "lo"), g("se", "hi")),
             Sp = est_ci(g("sp"), g("sp", "lo"), g("sp", "hi")), J = est_ci(g("j"), g("j", "lo"), g("j", "hi")),
             `Correction factor 1/J` = ifelse(is.na(g("correction")), "–",
               sprintf("%s (%s to %s)", num(g("correction"), 1), num(g("correction", "lo"), 1),
                       ifelse(is.na(g("correction", "hi")), "∞", num(g("correction", "hi"), 1)))),
             check.names = FALSE)
}))
oaireport::compare_table(correction_table, widths = c(2.4, 1.6, 1.6, 1.6, 1.9))
```

```{r note-components-correction}
#| results: asis
cat(oaireport::table_note("Lo 2022 subset: the participants of Lo et al. 2022 who answered the walking item and have device data. For each frequency-restricted walker definition, its Se, Sp and Youden's J against the device walker, and 1/J: how strongly a record-level misclassification correction would amplify the observed association. A larger J (smaller 1/J) gives a more stable correction. Descriptive only: the bias analysis of Lo et al. 2022 keeps the published exposure definition, and an upper limit of ∞ means the interval for J reaches 0.", close_group = FALSE), sep = "\n")
```
````

Run: `uv run oai report walking_validation`. Read every page of the new section. Check every number in two rows of each table against the CSVs printed in Task 3 Step 5.
Expected:
- the tables and legends are correct and nothing overflows;
- there is no `NA` text: missing values show "–".

- [ ] **Step 5: Egress, render check, commit**

Run: `uv run oai check-egress ~/oai-work/results/walking_validation/report`
Expected: 0 problems. The PDF and PNG figures are listed for manual review only.

```bash
git add analyses/walking_validation/report.qmd
git commit -m "feat(walking_validation): report section for the answer-level sub-analyses, with legends

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Docs and final verification

**Files:**
- Modify: `docs/superpowers/specs/2026-10-01-walking-validation-design.md` (status line; amendment 12's band-label sentence)
- Modify: `TODO.md` (the amendment-12 item)

- [ ] **Step 1: Update the spec**

In the spec:
- Change the status line (line 4) to: `**Status:** Implemented through amendment 12 (§15, §15b)`.
- In amendment 12b, replace "the codebook gives only the format name, so the band labels are confirmed from the questionnaire before the report shows them" with "labels from the release's formats.pdf (TMSMNTH): 1–3, 4–8 and 9 or more times per month; code 88 (don't know) is no band".
- In the amendment 12 **Outputs** list, add `validity_components_hex.csv` with the columns visit, x, y, count, dx, dy. These are the aggregate hexagonal cells of the agreement figure, and only cells with at least `components.min_cell_count` participants are kept.

- [ ] **Step 2: Mark the TODO item done**

In `TODO.md`, strike through the amendment-12 item's title, following the convention for completed items. Change `- **Implement spec amendment 12 (answer-level sub-analyses)** — <!-- skip -->` to `- ~~**Implement spec amendment 12 (answer-level sub-analyses)**~~ — done 2026-10-03 <!-- skip -->` and keep the rest of the line.

- [ ] **Step 3: Full verification**

```bash
uv run ruff check && uv run ruff format --check && uv run python scripts/check_no_data.py
uv run pytest -q
cd r && Rscript -e 'testthat::test_local("oaimodels", stop_on_failure = TRUE)' && RENV_PROFILE=report Rscript -e 'testthat::test_local("oaimodels", stop_on_failure = TRUE); testthat::test_local("oaireport", stop_on_failure = TRUE)'; cd ..
git diff --exit-code main -- r/renv.lock && echo "default lockfile unchanged"
git diff --name-only main | grep -E '\.(pdf|png|csv|parquet)$' || echo "no data or figure files on branch"
```

Expected: every command passes, followed by `default lockfile unchanged` and `no data or figure files on branch`.

- [ ] **Step 4: Commit the docs**

```bash
git add docs/superpowers/specs/2026-10-01-walking-validation-design.md TODO.md
git commit -m "docs: amendment 12 implemented (band labels from formats.pdf; hexagonal-cell output)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 5: Final clean-tree runs and renders**

Run these only after the final review's fixes are committed, from a clean tree (`git status` empty, `git ls-files -v | grep '^h'` empty):
- `uv run oai run lo2022_walking`, plus `--variant <name>` for each of its 7 report variants;
- `uv run oai run walking_validation`;
- `uv run pytest -m realdata -q`;
- `uv run oai report lo2022_walking && uv run oai report walking_validation`;
- egress on all four folders.

Every `run_info.json` must show `git_commit` equal to HEAD and `git_dirty: false`.
