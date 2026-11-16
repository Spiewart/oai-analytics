# Self-Reported Walkers by Step-Walker Status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** add steps to `analyses/walking_steps` that compare "Yes, step walker" with "Yes, not a step walker" (and show "No" for context). Stage 1 screens a broad set of OAI measures with standardized differences. Stage 2 fits mixed-model trajectories for every time-varying measure.

**Architecture:**
- Python builds a person-level group frame and a long ID × visit × measure table in `OAI_FRAME_DIR`.
- A Python step writes the stage-1 screen.
- An R step fits stage 2 with `oaimodels::walker_model`.
- A separate report document `discordance.qmd` draws both.
- Self-report and device-wave construction move out of `pro_validity.py` into importable functions, so the new steps reuse them.

**Tech Stack:** Python (polars, numpy, pytest); R (`oaimodels`, nlme, geepack); Quarto/typst; the `oai` ledger and CLI.

**Spec:** `docs/superpowers/specs/2026-11-16-walking-discordance-design.md`

## Global Constraints

- **Group labels**, exactly: `"Yes, step walker"`, `"Yes, not a step walker"`, `"No"`.
- **Comparisons:**
  - **Primary:** `item96` × `steps_100:bout_days` × device `"mean"` (mean of valid waves).
  - **Replications:** `item96` × `counts_mv:bout_days` × `"mean"`; `pase06_any` × `steps_100:bout_days` × `"06"`.
- **Same coding as before.** Self-report coding is unchanged: `exposure.yes_without_amount_as = "non-walker"`, and missing answers are excluded. The primary group sizes must equal the 2×2 already sent: 341 step walkers, 910 not, 314 "No" (n = 1,565).
- **Stage 1:**
  - level at visit `06`;
  - changes `00→06` and `06→10`;
  - the nearest visit holding the measure, within one scheduled visit of each endpoint (`oai.visits` order), is used and reported; otherwise the cell is blank.
- **Stage 1 statistics:** SMD with pooled SD and a 1,000-rep bootstrap 95% CI. Reading bands: |SMD| < 0.1 negligible, 0.1–0.2 small, ≥ 0.2 lead. No p-values.
- **Stage 2:**
  - every time-varying measure, at visits `00, 01, 03, 05, 06, 08, 10` where present;
  - covariates: baseline age and sex;
  - LME (random intercept) for continuous measures, GEE (exchangeable) for binary;
  - Holm across measures within each comparison.
- **Knee replacement:**
  - main analysis: knee-level values are kept as recorded and KL is set to 4 after replacement;
  - sensitivity analysis: the replaced knee is censored from the replacement visit on.
- **KL coverage caveat:** applied when the coverage gap between "Yes" groups is more than 10 percentage points.
- **Wording.** Results text never uses "bias", "over-report", "false positive", "correction" or "misclassif".
- **Results contain aggregates only.** Person frames go to `OAI_FRAME_DIR`. No column may match `oai.export.egress.COUNT_COLUMN`, and there are no raw totals that look like IDs.
- **Names.** No collaborator names in committed files.
- **Commits** end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **A self-report or device definition that yields only two groups** (e.g. no "No" answers in a synthetic or variant sample). The screen must still run, and the "No" column is empty (Task 3, `test_screen_runs_without_no_group`).
2. **A measure absent at an anchor and at both neighbouring visits.** The cell is blank and labelled, not filled from a far visit (Task 2, `test_window_blank_beyond_one_visit`).
3. **A replaced knee that is also the only read knee at a visit.**
   - Main: worse-knee KL is 4.
   - Censored: that knee is dropped, so the worse knee comes from the other knee or is null.

   Tested in Task 2, `test_worse_knee_kl_replacement_rules`.
4. **A binary measure with no events in one group at a visit.** `walker_model` marks the visit "separated". The step must keep that row and leave it out of Holm (Task 5, `test_holm_skips_unconverged` in R `testthat` or the Python helper).
5. **Banned words** reaching `DISCORDANCE.md` or the report. A realdata-free test scans the generated markdown template (Task 4, `test_discordance_text_is_neutral`).

---

### Task 1: Shared self-reports and device walkers; the group frame

**Files:**
- Modify: `analyses/walking_steps/pro_validity.py`. Move the self-report list and `with_walkers`/wave dict into functions; the script calls them and its behaviour is unchanged.
- Create: `analyses/walking_steps/discordance.py`, holding the pure functions for this analysis.
- Modify: `analyses/walking_steps/assumptions.toml` (a `discordance.*` block) and `analyses/walking_steps/ASSUMPTIONS.md` (regenerated).
- Test: `tests/test_walking_steps.py`

**Interfaces:**
- Produces:
  - In `pro.py`: `self_reports(A) -> dict[str, tuple[str, str, pl.DataFrame]]`, mapping each pro id to `(label, visit, frame[ID, yes, score])`. This is the same content as today's `pros` list.
  - In `devices.py`: `device_waves(device: pl.DataFrame, definitions, measures: list[str]) -> dict[str, pl.DataFrame]`, with keys `"06"`, `"08"`, `"mean"` and `"either"`, as built today in `pro_validity.py`.
  - In `discordance.py`: `GROUPS = ("Yes, step walker", "Yes, not a step walker", "No")`.
  - In `discordance.py`: `assign_groups(answers: pl.DataFrame, walkers: pl.DataFrame, definition: str) -> pl.DataFrame[ID, group]`.
    - `answers` has `ID, yes`; `walkers` has `ID` and a Boolean column named `definition`.
    - Only IDs present in both are kept.
    - `group` is a String drawn from `GROUPS`.

- [ ] **Step 1: Write the failing tests**

```python
def test_assign_groups_three_way():
    answers = pl.DataFrame({"ID": [1, 2, 3, 4], "yes": [True, True, False, True]})
    walkers = pl.DataFrame({"ID": [1, 2, 3], "steps_100:bout_days": [True, False, True]})
    g = d.assign_groups(answers, walkers, "steps_100:bout_days").sort("ID")
    assert g["group"].to_list() == ["Yes, step walker", "Yes, not a step walker", "No"]


def test_device_waves_mean_matches_combine():
    defs = devices.walker_definitions(2.0, 150.0, [100])
    cols = ["steps", "bout_days_per_week", "purposeful_min", "step_bout100_min",
            "step_bout100_days_per_week"]
    dev = pl.DataFrame({"ID": [1, 1, 2], "wave": ["06", "08", "06"], "valid": [True, True, True],
                        "steps": [5000.0, 7000.0, 3000.0], "bout_days_per_week": [3.0, 1.0, 0.0],
                        "purposeful_min": [30.0, 10.0, 0.0], "step_bout100_min": [20.0, 0.0, 0.0],
                        "step_bout100_days_per_week": [3.0, 0.0, 0.0]})
    w = devices.device_waves(dev, defs, cols)
    mean = w["mean"].sort("ID")
    assert mean["steps"].to_list() == [6000.0, 3000.0]
    assert mean["steps_100:bout_days"].to_list() == [False, False]  # (3 + 0) / 2 = 1.5 < 2
    assert w["06"].sort("ID")["steps_100:bout_days"].to_list() == [True, False]
```

Import the modules at the top of the test file: `import discordance as d` and `import devices` (beside `import relation as r`).

- [ ] **Step 2: Run the tests and watch them fail**

Run: `uv run pytest tests/test_walking_steps.py -k "assign_groups or device_waves" -q`. Expected: FAIL (no module `discordance`).

- [ ] **Step 3: Implement the refactor and `assign_groups`, and add the ledger block**

Add the ledger entries, each with a `source`:

| Key | Value | Status |
|---|---|---|
| `discordance.comparisons` | `{primary = ["item96","steps_100:bout_days","mean"], counts_mv = ["item96","counts_mv:bout_days","mean"], pase48 = ["pase06_any","steps_100:bout_days","06"]}` | confirmed (the user's choice: primary; Claude's: replications) |
| `discordance.anchor_visit` | `"06"` | assumed |
| `discordance.change_windows` | `[["00","06"],["06","10"]]` | assumed |
| `discordance.nearest_visit_steps` | `1` | assumed |
| `discordance.smd_bands` | `{small = 0.1, lead = 0.2}` | assumed |
| `discordance.bootstrap_reps` | `1000` | assumed |
| `discordance.seed` | `20261116` | assumed |
| `discordance.trend_visits` | `["00","01","03","05","06","08","10"]` | assumed |
| `discordance.trend_covariates` | `["age0","sex"]` | assumed |
| `discordance.multiplicity` | `"holm"` | assumed |
| `discordance.replacement` | `"keep_kl4"` | confirmed (the user's choice), with choices `["keep_kl4","censor"]` and a variant `replacement_censor` |
| `discordance.kl_coverage_gap` | `0.10` | assumed |

Then run `uv run oai assumptions walking_steps --write`.

- [ ] **Step 4: Run the whole file and watch it pass**

Run: `uv run pytest tests/test_walking_steps.py tests/test_assumptions_ledgers.py -q`. Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(walking_steps): shared self-report and device-wave helpers; discordance groups and ledger"
```

### Task 2: The long measure table, knee rules and windows

**Files:**
- Modify: `analyses/walking_steps/discordance.py`
- Test: `tests/test_walking_steps.py`

**Interfaces:**
- Consumes: `oai.derive.construct.visit_measures` and `womac_pain`, `oai.derive.knee_outcomes.knee_status`, `oai.loader.read_table`.
- Produces:
  - `MEASURES: dict[str, tuple[str, str, str]]`, mapping each measure to `(area, kind, source)`.
    - `area` is one of `"demographic"`, `"health"`, `"knee"`, `"activity"`, `"item_amount"`, `"device"`.
    - `kind` is one of `"continuous"`, `"binary"`, `"categorical"`.
    - `source` is the release variable stem or the derive function.
    - The time-varying (TV) measures are:
      - BMI (`P01BMI` at 00, then `V##BMI`);
      - `V##COMORB`, `V##HSPSS`, `V##HSMSS`, `V##CESD`;
      - `V##20MPACE` and `V##400MTIM`;
      - `V##CEMPLOY`, as binary (employed);
      - worse-knee WOMAC pain, plus the `construct` measures `womac_function`, `womac_walk` and `koos_sport`;
      - PASE `total`, `total_minus_walking` and the PASE/housework/work items in `construct.MEASURES`;
      - `frequent_pain_any` and `kl_worse`;
      - `replaced_any` (binary).
    - The fixed measures are:
      - `age` (at 06), `sex`, `race` (`P02RACE`), `education` (`V00EDCV`), `income` (`V00INCOME`), `married` (`V00MARITST`), `subcohort` (`V00COHORT`) and `site`;
      - the item amounts: years, months a year and times a month;
      - the device measures: `valid_days`, `wear_hr`, `steps`, `mv_min`, plus `season` and `weekend_share` if their source exists (see Step 3).
    - Verify every variable against `*_Contents.pdf` before coding it.
  - `worse_knee_kl(status: pl.DataFrame, rule: str) -> pl.DataFrame[ID, visit, kl_worse]`.
    - `status` is knee_status-shaped (`ID, SIDE, visit, kl, replaced`).
    - With `rule` `"keep_kl4"`, a replaced knee counts as KL 4.
    - With `"censor"`, a knee is dropped from its first replaced visit on.
  - `window_values(long: pl.DataFrame, start: str, end: str, steps: int, order: list[str]) -> pl.DataFrame[ID, measure, start_used, end_used, change]`. For each measure it uses the visit holding the measure nearest to each endpoint, within `steps` positions in `order`, with ties going to the endpoint itself and then to the earlier visit. A measure with no visit within reach gets no rows.
  - `long_table(A) -> pl.DataFrame[ID, visit, measure, value, censored]`. All TV measures at `discordance.trend_visits`, with `value` as Float64 (0/1 for binary). There are two rows per knee-level measure: one for each `discordance.replacement` rule, with `censored` False or True.

- [ ] **Step 1: Write the failing tests**

```python
def test_worse_knee_kl_replacement_rules():
    st = pl.DataFrame({"ID": [1, 1, 1, 1], "SIDE": [1, 2, 1, 2], "visit": ["06", "06", "10", "10"],
                       "kl": [2, None, 3, None], "replaced": [False, False, True, False]})
    keep = d.worse_knee_kl(st, "keep_kl4").sort("visit")
    assert keep["kl_worse"].to_list() == [2, 4]
    cens = d.worse_knee_kl(st, "censor").sort("visit")
    assert cens.filter(pl.col("visit") == "10")["kl_worse"].item() is None


ORDER = ["00", "01", "03", "05", "06", "08", "10"]

def test_window_uses_nearest_visit_and_reports_it():
    long = pl.DataFrame({"ID": [1, 1], "visit": ["01", "06"], "measure": ["m", "m"],
                         "value": [10.0, 13.0]})
    w = d.window_values(long, "00", "06", 1, ORDER)
    assert w.row(0, named=True) == {"ID": 1, "measure": "m", "start_used": "01",
                                     "end_used": "06", "change": 3.0}


def test_window_blank_beyond_one_visit():
    long = pl.DataFrame({"ID": [1, 1], "visit": ["03", "06"], "measure": ["m", "m"],
                         "value": [10.0, 13.0]})
    assert d.window_values(long, "00", "06", 1, ORDER).height == 0
```

- [ ] **Step 2: Run them and watch them fail.** Run: `uv run pytest tests/test_walking_steps.py -k "worse_knee or window" -q`.
- [ ] **Step 3: Implement `worse_knee_kl`, `window_values`, `MEASURES` and `long_table`.**
  - `long_table` reads each visit's AllClinical once and calls `construct.visit_measures` and `womac_pain`.
  - KL and replacement come from `knee_status(A, visits, anchor="00")`, using `steps_oa`'s outcome ledger keys copied into this ledger. Copy the keys `knee_status` reads, with their `steps_oa` values and a source line pointing there.
  - Season and weekend share need a monitoring-date or day-of-week column. Look in `AccelDataByDay06/08_Contents.pdf`; if neither exists, leave both out of `MEASURES` and add a ledger entry `discordance.device_calendar = "unavailable"` with the source.
- [ ] **Step 4: Run the whole file and watch it pass.** Run: `uv run pytest tests/test_walking_steps.py -q`.
- [ ] **Step 5: Commit.** Message: `feat(walking_steps): discordance measure table, knee replacement rules and visit windows`.

### Task 3: Stage-1 screen functions

**Files:**
- Modify: `analyses/walking_steps/discordance.py`
- Test: `tests/test_walking_steps.py`

**Interfaces:**
- Produces:
  - `smd(a: np.ndarray, b: np.ndarray, kind: str) -> float | None`.
    - Continuous: (mean_a − mean_b) / pooled SD.
    - Binary: (p_a − p_b) / sqrt((p_a(1−p_a) + p_b(1−p_b)) / 2).
    - Categorical: the multi-level SMD of Yang & Dalton (2012).
    - Returns None if either group has fewer than 2 values. `a` is "Yes, not a step walker", `b` is "Yes, step walker".
  - `smd_ci(a, b, kind, reps: int, seed: int) -> tuple[float | None, float | None]`, a percentile bootstrap that resamples within each group.
  - `band(x: float | None, small: float, lead: float) -> str`, returning `"negligible" | "small" | "lead" | ""`.
  - `screen(groups: pl.DataFrame, values: pl.DataFrame, kinds: dict[str, str], A) -> pl.DataFrame`. Columns:
    - `measure, area, window` (`"level_06"`, `"change_00_06"`, `"change_06_10"`), `start_used, end_used`;
    - for each group G in GROUPS: `n_<g>`, `summary_<g>` (string: mean (SD), or % for binary/categorical);
    - `smd, smd_lo, smd_hi, band`.

    The `n_` columns are persons per group, so name them `persons_step`, `persons_not`, `persons_no`, avoiding the `COUNT_COLUMN` pattern.

- [ ] **Step 1: Write the failing tests**

```python
def test_smd_continuous_and_binary():
    assert d.smd(np.array([2.0, 4.0]), np.array([0.0, 2.0]), "continuous") == pytest.approx(2 / np.sqrt(2))
    assert d.smd(np.array([1.0, 1.0, 0.0, 0.0]), np.array([0.0] * 4), "binary") == pytest.approx(0.5 / np.sqrt(0.125))


def test_band_rule():
    assert [d.band(x, 0.1, 0.2) for x in (0.05, -0.15, 0.25, None)] == ["negligible", "small", "lead", ""]


def test_screen_runs_without_no_group():
    groups = pl.DataFrame({"ID": [1, 2, 3, 4], "group": ["Yes, step walker"] * 2 + ["Yes, not a step walker"] * 2})
    values = pl.DataFrame({"ID": [1, 2, 3, 4], "measure": ["bmi"] * 4, "window": ["level_06"] * 4,
                           "value": [25.0, 27.0, 30.0, 32.0], "start_used": ["06"] * 4, "end_used": ["06"] * 4})
    out = d.screen(groups, values, {"bmi": "continuous"}, A_TEST)
    assert out["persons_no"].item() == 0 and out["band"].item() == "lead"
```

`A_TEST` is a small dict fixture with the `discordance.*` keys the function reads (reps 50).

- [ ] **Step 2: Run them and watch them fail.** Run: `uv run pytest tests/test_walking_steps.py -k "smd or band or screen" -q`.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run them and watch them pass.** Same command.
- [ ] **Step 5: Commit.** Message: `feat(walking_steps): discordance stage-1 standardized differences and reading bands`.

### Task 4: Frame and screen steps on real data

**Files:**
- Create: `analyses/walking_steps/discordance_frame.py` (step `discordance_frame`, `needs = ["persons"]`).
- Create: `analyses/walking_steps/discordance_screen.py` (step `discordance_screen`, `needs = ["discordance_frame"]`).
- Modify: `analysis.toml`; add `"*.md"` if it isn't already among the outputs.
- Test: `tests/test_walking_steps.py`

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces:
  - In `OAI_FRAME_DIR`: `discordance_groups.parquet` (`comparison, ID, group`), `discordance_long.parquet` (Task 2's `long_table`) and `discordance_fixed.parquet` (`ID, measure, value`, plus device measures per comparison's device key).
  - In results:
    - `discordance_flow.csv`: comparison and group, then persons at the anchor and persons with any TV value per visit.
    - `discordance_screen.csv`: Task 3 columns plus `comparison`, `censored`.
    - `discordance_kl_coverage.csv`: comparison, group, visit and the share with a KL reading.
    - `DISCORDANCE.md`: per comparison, the leads (band "lead") in neutral wording, plus the KL-coverage caveat when the gap is more than `discordance.kl_coverage_gap`.

- [ ] **Step 1: Write the failing neutral-wording test**

```python
def test_discordance_text_is_neutral():
    text = d.render_markdown(SCREEN_FIXTURE, TRENDS_FIXTURE_EMPTY, coverage_gap=0.0, label="default")
    for word in ("bias", "over-report", "overreport", "false positive", "correction", "misclassif"):
        assert word not in text.lower()
```

- [ ] **Step 2: Implement `render_markdown(screen, trends, coverage_gap, label) -> str` in `discordance.py`, then both entry scripts.** `discordance_frame.py` asserts that the primary comparison's group sizes are `{341, 910, 314}` under the default label, and raises otherwise.
- [ ] **Step 3: Run on real data**

Run: `uv run oai run walking_steps`.

Expected:
- the steps complete;
- `discordance_flow.csv` primary shows 341 / 910 / 314;
- every `band` value is one of the four allowed strings;
- `uv run oai check-egress ~/oai-work/results/walking_steps/default` reports 0 problems.

- [ ] **Step 4: Run the tests.** Run: `uv run pytest tests/test_walking_steps.py -q`.
- [ ] **Step 5: Commit.** Message: `feat(walking_steps): discordance frame and stage-1 screen steps`.

### Task 5: Stage-2 trajectories (R)

**Files:**
- Create: `analyses/walking_steps/discordance_trends.R` (step `discordance_trends`, `lang = "r"`, `needs = ["discordance_frame"]`). Follow how `analyses/walking_validation/construct_validity.R` reads the frame and the ledger.
- Modify: `analysis.toml`, `README.md` (Part 4: outputs table and run notes).
- Test: `r/oaimodels/tests/testthat/` only if a helper is added; otherwise `tests/test_walking_steps.py` checks the Holm helper (below).

**Interfaces:**
- Consumes: `discordance_groups.parquet`, `discordance_long.parquet`, and the `age0`/`sex` covariates (from `discordance_fixed`, with age at 00 taken as `V00AGE`).
- Produces `discordance_trends.csv` with the columns:
  - `comparison, censored, measure, kind, visit`;
  - `estimate, lo, hi, scale` (difference or OR, "Yes, not a step walker" vs "Yes, step walker");
  - `p_interaction, p_interaction_holm`;
  - `persons_model` (`n_people` renamed), `converged`, `fit_note`.

Steps:
- [ ] **Step 1: Write the failing Holm test.** Holm runs in Python after R writes the raw p-values, in `discordance.py` as `holm_by(df: pl.DataFrame, by: list[str], p: str, out: str) -> pl.DataFrame`. Unconverged rows and rows with NA p are excluded from the family and keep a null.

```python
def test_holm_skips_unconverged():
    df = pl.DataFrame({"comparison": ["c"] * 3, "p": [0.01, 0.04, None], "converged": [True, True, False]})
    out = d.holm_by(df, ["comparison"], "p", "p_holm")
    assert out["p_holm"].to_list() == [pytest.approx(0.02), pytest.approx(0.04), None]
```

- [ ] **Step 2: Watch it fail, implement `holm_by`, and watch it pass.**
- [ ] **Step 3: Write `discordance_trends.R`.** For each comparison × censored × measure:
  - Keep only the two "Yes" groups, with `walker_yes = group == "Yes, not a step walker"`.
  - Call `oaimodels::walker_model(data, covariates = c("age0","sex"), structure = "visit", family = <gaussian|binomial>, corstr = "exchangeable")` for the per-visit contrasts.
  - Call it again with `structure = "period"` and `periods` = one period per visit present. Its `period_test` attribute is `p_interaction`.
  - Write the raw rows to `discordance_trends_raw.csv` in `OAI_FRAME_DIR`.
  - A small Python step, `discordance_holm.py`, adds `p_interaction_holm` via `holm_by` (one family per comparison × censored) and writes `discordance_trends.csv` to results.
- [ ] **Step 4: Run on real data.**

Run: `uv run oai run walking_steps`.

Expected:
- the steps complete;
- every TV measure has rows for each comparison;
- separated or unconverged rows carry `fit_note` or `converged = false` and a null Holm p;
- egress shows 0 problems.

- [ ] **Step 5: Commit.** Message: `feat(walking_steps): discordance stage-2 trajectories with Holm across measures`.

### Task 6: Report document

**Files:**
- Create: `analyses/walking_steps/discordance.qmd`, styled like `report.qmd`, and add it to `[report] documents`.
- Modify: `README.md`.

- [ ] **Step 1: Write the document**
  - **Flow:** group sizes per comparison.
  - **Figure, forest plot:** SMD (95% CI) per measure for the primary comparison. There is one panel per window, measures are grouped by area, and the band lines are at ±0.1 and ±0.2.
  - **Table:** leads in each replication, alongside the primary.
  - **Figure, small multiples:** adjusted per-visit differences for the TV measures with Holm p < 0.05, or the top 6 by |SMD| if none qualify, labelled so.
  - **Sensitivity:** the censored knee-level sensitivity results beside the main ones.
  - **KL caveat:** shown when it applies.
  - **Wording:** neutral throughout, with a note on how to read the two groups. The item and the device may capture different things.
- [ ] **Step 2: Render and look**

Run: `uv run oai report walking_steps`.

Expected:
- the render succeeds;
- the pages are checked as images: labels readable, no overlaps, banned words absent (`pdftotext | grep -iE "bias|over-?report|false positive|correction|misclassif"` returns nothing).
- [ ] **Step 3: Commit.** Message: `feat(walking_steps): discordance report`.
