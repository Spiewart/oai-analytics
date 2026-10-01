# Walking Validation Study Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `analyses/walking_validation`. It validates the 96-month walking-for-exercise item (the Lo 2022 exposure) against OAI accelerometry, then runs a record-level probabilistic bias analysis of Lo 2022's odds ratios and renders the results as a report.

**Architecture:**
- **Shared Python derivations** (`oai.derive.accel`, `oai.derive.walking`, `oai.derive.pase`):
  - turn the release's minute counts into device measures, in a way that reproduces the release's by-day files;
  - code the walking item for both analyses.
- **Shared R helpers** in `oaimodels`: the GEE fit, the validity statistics and the bias-analysis engine. They are used by the replication and by the new analysis.
- **A five-step analysis:** `device` → `cohort` → `validity` and `bias` → `compare`.
  - It reuses the replication's knee frame for the Lo cohort, and refits the replication's own models.
  - Its R steps run under the `report` renv profile, which gains `quantreg`.

**Tech Stack:**
- Python 3.11+ with polars and numpy (new dependency).
- R with geepack, quantreg (new, `report` profile only), parallel, jsonlite, testthat, plus `oaireport`.
- Quarto/Typst.

**Spec:** `docs/superpowers/specs/2026-10-01-walking-validation-design.md`. Read §15 Amendments: they record what planning-time prototypes changed, and they bind.

## Global Constraints

**Repository and data**
- The repository is public. Participant-level data (frames, device measures) stays under `OAI_WORK_DIR`. Results and reports under `OAI_RESULTS_DIR` are aggregate only. `oai check-egress` must report 0 problems on the analysis's results folder.
- Tests that need a participant-ID-like value build it at runtime, like `FAKE_ID = int("9" + "000123")` in `tests/test_egress.py`. The leak guard blocks such literals.
- Public text (code, docs, report) refers to "the original authors" or "the authors of Lo et al. 2015" and never describes a personal relationship.

**R environment**
- `r/renv.lock` (restored offline in the enclave) must not change. `quantreg` goes only into `r/renv/profiles/report/renv.lock`.
- `walking_validation` declares `[r] profile = "report"`. Its R steps run with `RENV_PROFILE=report`.

**Device processing**
- With the release's rules, device processing must reproduce the release's by-day files:
  - every release person-day matched;
  - wear minutes equal on ≥99.5% of matched days;
  - MV minutes and bouted MV minutes equal on 100%;
  - valid persons within ±1 of the release (1,927 at V06; 1,394 at V08).

**Bias analysis**
- It must reproduce the replication's observed odds ratios exactly (|ΔOR| ≤ 1e-8) before simulating.
- Each iteration uses `set.seed(seed + i)`, so results do not depend on the core count. Parallelism comes from `parallel::mclapply`, with cores from `OAI_R_CORES` (default: detected cores − 1).

**Code style and commits**
- ruff (line length 100); R in `oaimodels` style (namespaced calls, hand-written NAMESPACE, testthat 3e).
- Every commit ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Work on branch `feat/walking-validation`. Do not push until Task 12.

## Review Focus

1. **Persons with one valid wave, and persons whose measure is undefined at one wave.** `combine_waves` must keep them with `n_waves = 1` and the other wave's columns null. Reliability uses only persons valid at both waves. Pinned in Task 8 (`test_combine_waves_keeps_single_wave_persons`).
2. **A replication frame that is missing or was built with a different exposure coding.** The `cohort` step must stop with a message naming the `oai run lo2022_walking …` command, not silently mix codings. Pinned in Task 8 (`test_read_lo_frame_rejects_other_coding`, `test_read_lo_frame_names_the_command`).
3. **Bias-analysis draws that imply an impossible prevalence (Se + Sp ≤ 1, true prevalence outside (0, 1), PPV > 1).** They are discarded and counted, never crash. A cell with every draw discarded summarises to NA. Pinned in Task 6 (`impossible priors are discarded, not fatal`).
4. **Strata with no reference positives or negatives.** Wilson intervals return NA, priors fall back to Beta(1, 1), and the stratum test returns NA without error. Pinned in Task 5 (`classification handles empty cells`).
5. **Missing minute counts.** They count as zero for non-wear and never as wear intensity. Pinned in Task 1 (`test_missing_counts_count_as_zero_for_nonwear`, `test_missing_counts_are_not_activity`).

---

## Interfaces at a glance

| Task | Produces (exact names) | Used by |
|---|---|---|
| 1 | `oai.derive.accel`: `DeviceRules`, `nonwear_mask(counts, day_key, rules)`, `bout_mask(counts, day_key, wear, rules)`, `daily_summary(minutes, rules) -> DataFrame[ID, day, wear_min, mv_min, light_min, counts, bout_min, purposeful_min, purposeful_bouts, valid]`, `first_valid_days(daily, rules)`, `person_summary(daily, rules) -> DataFrame[ID, valid_days, wear_hr, mv_min, light_min, counts_per_day, bout_min, purposeful_min, bout_days_per_week, valid]`, `read_minutes(visit) -> DataFrame[ID, day, minute, cnt]`, `release_by_day(visit)`, `reproduction(daily, visit, rules) -> dict[str, int]`, `release_valid_persons(visit, min_valid_days=4) -> int` | 7 |
| 2 | `oai.derive.walking`: `WALKER_ITEM`, `AMOUNT_ITEMS`, `WALKER_VALUES`, `walking_answers()`, `walker_status(*, yes_without_amount_as, missing_as) -> Expr["walker"]`, `walking_sessions(midpoints) -> Expr["sessions"]`. `oai.derive.pase.score_pase(allclinical, visit, walking=DEFAULT_WALKING) -> DataFrame[ID, visit, pase_total, pase_walking]` | 8 |
| 3 | R `oaimodels::fit_knee_gee(data, rhs, outcome = "y", term = "walkerTRUE", corstr = "exchangeable", id = "ID") -> c(or, lo, hi, log_or, se)` | 10 |
| 4 | `Analysis.r_profile: str \| None`; `oai.runner.process_env(step, analysis, env) -> dict` | 7, 9, 10 |
| 5 | R `hodges_lehmann`, `rank_biserial`, `jonckheere`, `median_regression`, `spearman_ci`, `deattenuate`, `wave_reliability`, `wilson`, `classification`, `auc_ci`, `classification_by_stratum` | 9 |
| 6 | R `beta_shapes(k, n)`, `true_prevalence`, `reclass_probs`, `correct_or_2x2`, `reclassify(persons, se, sp)`, `pba(persons, knees, fit, priors, differential = FALSE, iterations, seed, cores, exposure = "walker")`, `summarise_pba(draws, direction = NA, significant = NA)` | 10 |
| 7 | Frame `device.parquet` (person × wave); results `device_reproduction.csv`, `metrics_device.csv` | 8, 10, 11 |
| 8 | Frames `frame.parquet` (persons), `lo_knees.parquet`, `lo_model.json`; results `flow.csv`, `metrics_cohort.csv`, `lo2022_t2.csv`, `lo2022_table2.csv` | 9, 10, 11 |
| 9 | Results `validity_known_groups.csv`, `validity_dose.csv`, `validity_convergent.csv`, `validity_classification.csv`, `validity_strata.csv`, `validity_pase.csv`, `metrics_validity.csv` | 11 |
| 10 | Results `bias_priors.csv`, `bias_pba.csv`, `bias_tipping.csv`, `bias_summary_level.csv`, `metrics_bias.csv`, `comparison.csv` | 11 |

---

### Task 1: Device processing (`oai.derive.accel`)

**Files:**
- Modify: `pyproject.toml` (add `numpy>=1.26`), `uv.lock`
- Rewrite: `src/oai/derive/accel.py` (currently a `NotImplementedError` stub)
- Modify: `tests/test_analyses.py` (drop the `valid_wear_days` stub case)
- Create: `tests/test_accel.py`, `tests/test_accel_realdata.py`

**Interfaces:**
- Consumes: `oai.loader.read_table`, `oai.derive.knee.find_col`.
- Produces: see the table above. `day_key` = `ID * 100_000 + day`.

- [ ] **Step 0: Branch and dependency**

```bash
git checkout -b feat/walking-validation
uv add "numpy>=1.26"
```

Expected: `pyproject.toml` lists `numpy>=1.26` and `uv.lock` is updated.

- [ ] **Step 1: Write the failing tests**

`tests/test_accel.py`:

```python
import numpy as np
import polars as pl

from oai.derive.accel import DeviceRules, bout_mask, daily_summary, nonwear_mask, person_summary

RULES = DeviceRules()
HI = 3000.0


def nonwear(counts, days=None):
    c = np.array(counts, dtype=float)
    key = np.zeros(len(c), dtype=np.int64) if days is None else np.array(days, dtype=np.int64)
    return nonwear_mask(c, key, RULES)


def bouts(counts, wear=None):
    c = np.array(counts, dtype=float)
    w = np.ones(len(c), dtype=bool) if wear is None else np.array(wear)
    return bout_mask(c, np.zeros(len(c), dtype=np.int64), w, RULES)


def test_ninety_zero_minutes_are_nonwear_and_eighty_nine_are_wear():
    assert nonwear([500] + [0] * 90 + [500]).sum() == 90
    assert nonwear([500] + [0] * 89 + [500]).sum() == 0


def test_short_low_interruptions_join_zero_runs():
    assert nonwear([0] * 45 + [50, 99] + [0] * 45).all()
    assert nonwear([0] * 45 + [50, 60, 70] + [0] * 45).sum() == 0
    assert nonwear([0] * 45 + [100] + [0] * 45).sum() == 0


def test_interruptions_do_not_start_or_end_a_period():
    m = nonwear([50] + [0] * 90 + [50])
    assert not m[0] and not m[-1] and m[1:-1].all()


def test_nonwear_does_not_cross_days():
    assert nonwear([0] * 120, days=[1] * 60 + [2] * 60).sum() == 0
    assert nonwear([0] * 120, days=[1] * 120).sum() == 120


def test_missing_counts_count_as_zero_for_nonwear():
    assert nonwear([np.nan] * 90).all()


def test_bout_needs_eight_of_ten_minutes():
    assert bouts([HI] * 10).sum() == 10
    assert bouts([HI] * 7 + [0] * 8).sum() == 0
    # the bout spans its start through its last minute at or above the cutpoint
    assert bouts([HI] * 4 + [0] + [HI] * 4 + [0] * 6).sum() == 9


def test_bout_stops_at_three_below_and_trims_trailing_minutes():
    m = bouts([HI] * 12 + [0] * 3 + [HI] * 12)
    assert m.sum() == 24 and not m[12:15].any()


def test_bout_ignores_nonwear_minutes():
    assert bouts([HI] * 10, wear=[True] * 5 + [False] * 5).sum() == 0


def minutes_frame(days, pid=1):
    rows = [(pid, day, i + 1, c) for day, counts in days.items() for i, c in enumerate(counts)]
    schema = {"ID": pl.Int64, "day": pl.Int64, "minute": pl.Int64, "cnt": pl.Float64}
    return pl.DataFrame(rows, schema=schema, orient="row")


def test_missing_counts_are_not_activity():
    daily = daily_summary(minutes_frame({1: [500.0] * 600 + [None] * 5}))
    assert daily["mv_min"].item() == 0 and daily["light_min"].item() == 600


def test_daily_and_person_summaries():
    worn = [500.0] * 600
    active = [500.0] * 580 + [HI] * 20
    days = {1: worn, 2: active, 3: [500.0] * 599, **{d: worn for d in range(4, 11)}}
    frame = pl.concat([minutes_frame(days, pid=1), minutes_frame({1: worn, 2: worn, 3: worn}, pid=2)])
    daily = daily_summary(frame)
    day2 = daily.filter((pl.col("ID") == 1) & (pl.col("day") == 2)).row(0, named=True)
    assert day2["wear_min"] == 600 and day2["valid"]
    assert (day2["mv_min"], day2["light_min"], day2["counts"]) == (20, 580, 580 * 500 + 20 * HI)
    assert (day2["bout_min"], day2["purposeful_min"], day2["purposeful_bouts"]) == (20, 20, 1)
    assert not daily.filter((pl.col("ID") == 1) & (pl.col("day") == 3))["valid"].item()
    people = person_summary(daily).sort("ID")
    one, two = people.row(0, named=True), people.row(1, named=True)
    assert one["valid_days"] == 7 and one["valid"]  # days 1, 2, 4-8: the first 7 valid days
    assert abs(one["mv_min"] - 20 / 7) < 1e-9 and abs(one["bout_days_per_week"] - 1.0) < 1e-9
    assert abs(one["wear_hr"] - 10.0) < 1e-9
    assert two["valid_days"] == 3 and not two["valid"]
```

In `tests/test_analyses.py`, delete the line `from oai.derive.accel import valid_wear_days` and the list item `lambda: valid_wear_days(pl.LazyFrame()),`.

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/test_accel.py -q`
Expected: FAIL at collection with `ImportError: cannot import name 'DeviceRules' from 'oai.derive.accel'`.

- [ ] **Step 3: Implement `src/oai/derive/accel.py`**

```python
"""ActiGraph GT1M processing from OAI minute counts (AccelData_Descrip.pdf algorithm).

Parameterised by DeviceRules:
- non-wear: runs of >= nonwear_minutes zero-count minutes, which may include interruptions of
  <= interrupt_minutes consecutive minutes with 0 < count < interrupt_ceiling, found within each
  calendar day (PAStudyDay); a missing count counts as zero for non-wear and is never activity;
- valid day: >= valid_day_hours of wear; only the first max_valid_days valid days count;
- MV bout: starts at a wear minute >= mv_cutpoint once bout_need of the bout_window minutes from
  it are >= the cutpoint; extends while each bout_window-minute window holds fewer than
  bout_stop_below minutes below it; spans its start through its last minute >= the cutpoint.
With the release's rules this reproduces the release's by-day files (tests/test_accel_realdata.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial

import numpy as np
import polars as pl

from oai.derive.knee import find_col
from oai.loader import read_table

DAY_KEY_SCALE = 100_000  # ID * scale + PAStudyDay identifies one participant-day


@dataclass(frozen=True)
class DeviceRules:
    nonwear_minutes: int = 90
    interrupt_minutes: int = 2
    interrupt_ceiling: int = 100
    valid_day_hours: float = 10.0
    max_valid_days: int = 7
    min_valid_days: int = 4
    mv_cutpoint: int = 2020
    light_floor: int = 100
    bout_window: int = 10
    bout_need: int = 8
    bout_stop_below: int = 3
    purposeful_bout_minutes: int = 10


def _runs(values: np.ndarray, key: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Start, end (exclusive) and value of each run of equal values within each key."""
    n = len(values)
    if n == 0:
        empty = np.zeros(0, dtype=np.int64)
        return empty, empty, empty
    change = np.ones(n, dtype=bool)
    change[1:] = (values[1:] != values[:-1]) | (key[1:] != key[:-1])
    starts = np.flatnonzero(change)
    ends = np.r_[starts[1:], n]
    return starts, ends, values[starts]


def nonwear_mask(
    counts: np.ndarray, day_key: np.ndarray, rules: DeviceRules = DeviceRules()
) -> np.ndarray:
    """True for non-wear minutes; rows sorted by participant-day and minute."""
    c = np.nan_to_num(np.asarray(counts, dtype=float), nan=0.0)
    kind = np.where(c == 0, 0, np.where(c < rules.interrupt_ceiling, 1, 2))
    starts, ends, kinds = _runs(kind, day_key)
    keys = day_key[starts]
    out = np.zeros(len(c), dtype=bool)
    i, n = 0, len(starts)
    while i < n:
        if kinds[i] != 0:
            i += 1
            continue
        last = i
        while (
            last + 2 < n
            and kinds[last + 1] == 1
            and ends[last + 1] - starts[last + 1] <= rules.interrupt_minutes
            and kinds[last + 2] == 0
            and keys[last + 1] == keys[i]
            and keys[last + 2] == keys[i]
        ):
            last += 2
        if ends[last] - starts[i] >= rules.nonwear_minutes:
            out[starts[i] : ends[last]] = True
        i = last + 1
    return out


def bout_mask(
    counts: np.ndarray, day_key: np.ndarray, wear: np.ndarray, rules: DeviceRules = DeviceRules()
) -> np.ndarray:
    """True for minutes inside an MV bout; only wear minutes count as >= the cutpoint."""
    c = np.nan_to_num(np.asarray(counts, dtype=float), nan=0.0)
    above = (c >= rules.mv_cutpoint) & wear
    out = np.zeros(len(c), dtype=bool)
    win, need, stop = rules.bout_window, rules.bout_need, rules.bout_stop_below
    if len(c) == 0:
        return out
    seg_starts = np.flatnonzero(np.r_[True, day_key[1:] != day_key[:-1]])
    seg_ends = np.r_[seg_starts[1:], len(c)]
    for s, e in zip(seg_starts, seg_ends, strict=True):
        a = above[s:e]
        n = e - s
        if n < win or a.sum() < need:
            continue
        cs = np.r_[0, np.cumsum(a)]
        candidates = np.flatnonzero(a[: n - win + 1] & (cs[win:] - cs[: n - win + 1] >= need))
        next_free = 0
        for i in candidates:
            if i < next_free:
                continue
            j = i
            while j + win <= n and win - (cs[j + win] - cs[j]) < stop:
                j += 1
            end = min(j + win, n) - 1
            while not a[end]:
                end -= 1
            out[s + i : s + end + 1] = True
            next_free = end + 1
    return out


def daily_summary(minutes: pl.DataFrame, rules: DeviceRules = DeviceRules()) -> pl.DataFrame:
    """One row per ID x day from `minutes` (ID, day, minute, cnt; one row per recorded minute)."""
    m = minutes.sort(["ID", "day", "minute"])
    key = m["ID"].to_numpy() * DAY_KEY_SCALE + m["day"].to_numpy()
    cnt = m["cnt"].cast(pl.Float64).to_numpy()
    wear = ~nonwear_mask(cnt, key, rules)
    bout = bout_mask(cnt, key, wear, rules)
    c = np.nan_to_num(cnt, nan=0.0)
    purposeful = np.zeros(len(c), dtype=bool)
    purposeful_start = np.zeros(len(c), dtype=bool)
    b_starts, b_ends, b_vals = _runs(bout.astype(np.int8), key)
    for s, e in zip(b_starts[b_vals == 1], b_ends[b_vals == 1], strict=True):
        if e - s >= rules.purposeful_bout_minutes:
            purposeful[s:e] = True
            purposeful_start[s] = True
    per_minute = m.select("ID", "day").with_columns(
        pl.Series("wear", wear),
        pl.Series("mv", wear & (c >= rules.mv_cutpoint)),
        pl.Series("light", wear & (c >= rules.light_floor) & (c < rules.mv_cutpoint)),
        pl.Series("wear_counts", np.where(wear, c, 0.0)),
        pl.Series("bout", bout),
        pl.Series("purposeful", purposeful),
        pl.Series("purposeful_start", purposeful_start),
    )
    return per_minute.group_by(["ID", "day"], maintain_order=True).agg(
        pl.col("wear").sum().alias("wear_min"),
        pl.col("mv").sum().alias("mv_min"),
        pl.col("light").sum().alias("light_min"),
        pl.col("wear_counts").sum().alias("counts"),
        pl.col("bout").sum().alias("bout_min"),
        pl.col("purposeful").sum().alias("purposeful_min"),
        pl.col("purposeful_start").sum().alias("purposeful_bouts"),
    ).with_columns((pl.col("wear_min") >= rules.valid_day_hours * 60).alias("valid"))


def first_valid_days(daily: pl.DataFrame, rules: DeviceRules = DeviceRules()) -> pl.DataFrame:
    """Valid days only, the first max_valid_days per participant."""
    return (
        daily.filter("valid")
        .sort(["ID", "day"])
        .with_columns(pl.int_range(pl.len()).over("ID").alias("_k"))
        .filter(pl.col("_k") < rules.max_valid_days)
        .drop("_k")
    )


def person_summary(daily: pl.DataFrame, rules: DeviceRules = DeviceRules()) -> pl.DataFrame:
    """Per participant, means per valid day over the first max_valid_days valid days."""
    return (
        first_valid_days(daily, rules)
        .group_by("ID", maintain_order=True)
        .agg(
            pl.len().alias("valid_days"),
            (pl.col("wear_min").mean() / 60).alias("wear_hr"),
            pl.col("mv_min").mean(),
            pl.col("light_min").mean(),
            pl.col("counts").mean().alias("counts_per_day"),
            pl.col("bout_min").mean(),
            pl.col("purposeful_min").mean(),
            ((pl.col("purposeful_bouts") > 0).mean() * 7).alias("bout_days_per_week"),
        )
        .with_columns((pl.col("valid_days") >= rules.min_valid_days).alias("valid"))
    )


def read_minutes(visit: str) -> pl.DataFrame:
    """ID, day, minute, cnt for one accelerometer wave ("06" or "08"), sorted."""
    lf = read_table("acceldatabymin", visit, lazy=True)
    names = {name.upper(): name for name in lf.collect_schema().names()}

    def col(name: str) -> pl.Expr:
        return pl.col(names[name.upper()])

    return (
        lf.select(
            col("ID").cast(pl.Int64).alias("ID"),
            col(f"V{visit}PAStudyDay").cast(pl.Int64).alias("day"),
            col(f"V{visit}MinSequence").cast(pl.Int64).alias("minute"),
            col(f"V{visit}MINCnt").cast(pl.Float64).alias("cnt"),
        )
        .sort(["ID", "day", "minute"])
        .collect()
    )


def release_by_day(visit: str) -> pl.DataFrame:
    """The release's by-day values: ID, day, wear_ref (minutes), mv_ref, bout_ref (Troiano)."""
    df = read_table("acceldatabyday", visit)
    col = partial(find_col, df, where=f"acceldatabyday{visit}")
    return df.select(
        pl.col(col("ID")).cast(pl.Int64).alias("ID"),
        pl.col(col(f"V{visit}PAStudyDay")).cast(pl.Int64).alias("day"),
        (pl.col(col(f"V{visit}WearHr")).cast(pl.Float64) * 60).round(0).alias("wear_ref"),
        pl.col(col(f"V{visit}DAYMVMinT")).cast(pl.Float64).alias("mv_ref"),
        pl.col(col(f"V{visit}DAYMVBoutMinT")).cast(pl.Float64).alias("bout_ref"),
    )


def reproduction(daily: pl.DataFrame, visit: str, rules: DeviceRules = DeviceRules()) -> dict[str, int]:
    """Agreement of our first valid days with the release's by-day file."""
    ref = release_by_day(visit)
    matched = ref.join(first_valid_days(daily, rules), on=["ID", "day"], how="inner")
    return {
        "release_days": ref.height,
        "matched_days": matched.height,
        "wear_mismatch_days": int(((matched["wear_min"] - matched["wear_ref"]).abs() >= 0.5).sum()),
        "mv_mismatch_days": int((matched["mv_min"] != matched["mv_ref"]).sum()),
        "bout_mismatch_days": int((matched["bout_min"] != matched["bout_ref"]).sum()),
    }


def release_valid_persons(visit: str, min_valid_days: int = 4) -> int:
    """Participants the release counts as valid (VxxANVDAYS >= min_valid_days)."""
    df = read_table("accelerometry", visit)
    return df.filter(pl.col(find_col(df, f"V{visit}ANVDAYS")) >= min_valid_days).height
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_accel.py tests/test_analyses.py -q`
Expected: PASS.

- [ ] **Step 5: Write the real-data reproduction test**

`tests/test_accel_realdata.py`:

```python
"""oai.derive.accel reproduces the release's accelerometry by-day files (real data)."""

import pytest

from oai.derive.accel import (
    DeviceRules,
    daily_summary,
    person_summary,
    read_minutes,
    release_valid_persons,
    reproduction,
)


@pytest.mark.realdata
@pytest.mark.parametrize("visit", ["06", "08"])
def test_reproduces_release_by_day_files(visit):
    rules = DeviceRules()
    daily = daily_summary(read_minutes(visit), rules)
    rep = reproduction(daily, visit, rules)
    assert rep["matched_days"] == rep["release_days"]
    assert rep["wear_mismatch_days"] <= 0.005 * rep["release_days"]
    assert rep["mv_mismatch_days"] == 0
    assert rep["bout_mismatch_days"] == 0
    ours = person_summary(daily, rules).filter("valid").height
    assert abs(ours - release_valid_persons(visit)) <= 1
```

Run: `uv run pytest tests/test_accel_realdata.py -m realdata -q`
Expected: PASS. The planning prototype gave:
- V06: 13,040/13,040 days matched; 33 wear mismatches; 0 MV; 0 bout; 1,928 persons against 1,927.
- V08: 9,399/9,399 days matched; 38 wear mismatches; 0 MV; 0 bout; 1,394 persons against 1,394.

- [ ] **Step 6: Commit**

```bash
uv run ruff check && uv run ruff format --check && uv run pytest -q
git add pyproject.toml uv.lock src/oai/derive/accel.py tests/test_accel.py tests/test_accel_realdata.py tests/test_analyses.py
git commit -m "feat: device processing that reproduces the OAI accelerometry release

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Shared walking-item and PASE derivations; the replication uses them

**Files:**
- Create: `src/oai/derive/walking.py`, `tests/test_derive_walking.py`
- Rewrite: `src/oai/derive/pase.py` (stub)
- Modify: `analyses/lo2022_walking/lo2022.py`, `tests/test_analyses.py` (drop the `score_pase` stub case)

**Interfaces:**
- Consumes: `read_table`, `find_col`.
- Produces: `walker_status`, `walking_sessions`, `walking_answers`, `AMOUNT_ITEMS`, `WALKER_VALUES`, `WALKER_ITEM` and `score_pase`.
- The replication's outputs must be identical before and after this task.

- [ ] **Step 1: Snapshot the replication outputs before refactoring**

```bash
W=.superpowers/sdd/2026-10-01-walking-validation
mkdir -p $W/pre-refactor
uv run oai run lo2022_walking > /dev/null && uv run oai run lo2022_walking --variant walker_requires_amount > /dev/null
R="$(uv run python -c 'from oai.config import get_settings; print(get_settings().results_dir / "lo2022_walking")')"
for l in default walker_requires_amount; do mkdir -p $W/pre-refactor/$l && cp "$R/$l"/*.csv $W/pre-refactor/$l/; done
ls $W/pre-refactor/default
```

Expected: both runs succeed, and the list shows `comparison.csv flow.csv metrics_cohort.csv metrics_models.csv table1.csv table2.csv table3.csv`.

- [ ] **Step 2: Write the failing tests**

`tests/test_derive_walking.py`:

```python
import polars as pl
import pytest

from oai.derive.pase import score_pase
from oai.derive.walking import walker_status, walking_sessions

MIDPOINTS = {"years": [3.0, 8.0, 15.5, 20.0], "months": [2.5, 6.5, 10.5], "times": [2.0, 6.0, 10.0]}
ANSWERS = pl.DataFrame(
    {
        "walk_item": [1, 1, 0, None],
        "amount_years": [2, None, None, None],
        "amount_months": [3, None, None, None],
        "amount_times": [3, None, None, None],
    },
    schema={c: pl.Int64 for c in ("walk_item", "amount_years", "amount_months", "amount_times")},
)


def walker(**kw):
    return ANSWERS.select(walker_status(**kw))["walker"].to_list()


def test_walker_status_codings():
    assert walker(yes_without_amount_as="walker", missing_as="non-walker") == [True, True, False, False]
    assert walker(yes_without_amount_as="non-walker", missing_as="exclude") == [True, False, False, None]
    assert walker(yes_without_amount_as="exclude", missing_as="walker") == [True, None, False, True]


def test_walking_sessions_uses_category_midpoints():
    df = pl.DataFrame({"amount_years": [4, 1, None], "amount_months": [3, 1, 2], "amount_times": [3, 1, 2]})
    assert df.select(walking_sessions(MIDPOINTS))["sessions"].to_list() == [
        20.0 * 10.5 * 10.0,
        3.0 * 2.5 * 2.0,
        None,
    ]


def test_score_pase_walking_subscore():
    ac = pl.DataFrame(
        {
            "ID": [1, 2, 3, 4],
            "V06PASE": [100.0, 50.0, None, 80.0],
            "V06PASE2": [0, 1, 3, None],
            "V06PASE2HR": [None, 2, 4, None],
        }
    )
    out = score_pase(ac, "V06")
    assert out["visit"].to_list() == ["06"] * 4
    assert out["pase_total"].to_list() == [100.0, 50.0, None, 80.0]
    assert out["pase_walking"].to_list() == [
        0.0,
        pytest.approx(20 * 1.5 / 7 * 1.5),
        pytest.approx(20 * 6 / 7 * 5),
        None,
    ]
```

In `tests/test_analyses.py`, delete `from oai.derive.pase import score_pase` and the list item `lambda: score_pase(pl.DataFrame(), "V06"),`.

Run: `uv run pytest tests/test_derive_walking.py -q`
Expected: FAIL at collection with `ModuleNotFoundError: No module named 'oai.derive.walking'`.

- [ ] **Step 3: Implement**

`src/oai/derive/walking.py`:

```python
"""The 96-month walking-for-exercise item (Historical Physical Activity Survey, AllClinical10).

Shared by lo2022_walking (its exposure) and walking_validation (the item under validation).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from functools import partial

import polars as pl

from oai.derive.knee import find_col
from oai.loader import read_table

WALKER_ITEM = "V10WLKAR4"  # walked for exercise >= 20 min a day, >= 10 times, at age >= 50
AMOUNT_ITEMS = {"years": "V10WKYRAR4", "months": "V10WKMOAR4", "times": "V10WKTMAR4"}
WALKER_VALUES = {"non-walker": False, "walker": True, "exclude": None}


def walking_answers(walker_item: str = WALKER_ITEM) -> pl.DataFrame:
    """ID, walk_item (1 yes, 0 no, null), amount_years, amount_months, amount_times (codes)."""
    ac10 = read_table("allclinical", "10")
    col = partial(find_col, ac10, where="allclinical10")
    return ac10.select(
        pl.col(col("ID")).alias("ID"),
        pl.col(col(walker_item)).alias("walk_item"),
        *[pl.col(col(item)).alias(f"amount_{name}") for name, item in AMOUNT_ITEMS.items()],
    )


def walker_status(*, yes_without_amount_as: str, missing_as: str) -> pl.Expr:
    """`walker` (Boolean; null = excluded) from walk_item and the amount_* columns."""
    no_amount = pl.all_horizontal([pl.col(f"amount_{name}").is_null() for name in AMOUNT_ITEMS])
    yes_value = (
        pl.when(no_amount)
        .then(pl.lit(WALKER_VALUES[yes_without_amount_as], dtype=pl.Boolean))
        .otherwise(True)
    )
    return (
        pl.when(pl.col("walk_item") == 1)
        .then(yes_value)
        .when(pl.col("walk_item") == 0)
        .then(False)
        .otherwise(pl.lit(WALKER_VALUES[missing_as], dtype=pl.Boolean))
        .alias("walker")
    )


def _amount(name: str, midpoints: Sequence[float]) -> pl.Expr:
    mapping = {code + 1: float(value) for code, value in enumerate(midpoints)}
    return pl.col(f"amount_{name}").replace_strict(mapping, default=None, return_dtype=pl.Float64)


def walking_sessions(midpoints: Mapping[str, Sequence[float]]) -> pl.Expr:
    """Sessions since age 50: years x months/year x times/month at category midpoints."""
    return (
        _amount("years", midpoints["years"])
        * _amount("months", midpoints["months"])
        * _amount("times", midpoints["times"])
    ).alias("sessions")
```

`src/oai/derive/pase.py`:

```python
"""PASE scoring (Washburn et al. 1993) from AllClinical items.

The total score is released as VxxPASE. The walking subscore (item 2, walking outside the home)
is weight x days/7 x hours/day from VxxPASE2 (0 never, 1 = 1-2 days, 2 = 3-4 days, 3 = 5-7 days)
and VxxPASE2HR (1 <1 h, 2 = 1-2 h, 3 = 2-4 h, 4 >4 h; skipped when never).
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import partial

import polars as pl

from oai.derive.knee import find_col

DEFAULT_WALKING = {"days": [0.0, 1.5, 3.5, 6.0], "hours": [0.5, 1.5, 3.0, 5.0], "weight": 20.0}


def score_pase(
    allclinical: pl.DataFrame, visit: str, walking: Mapping = DEFAULT_WALKING
) -> pl.DataFrame:
    """ID, visit, pase_total (released VxxPASE), pase_walking (item-2 subscore; 0 if never)."""
    v = visit.removeprefix("V")
    col = partial(find_col, allclinical, where=f"allclinical{v}")
    days = pl.col(col(f"V{v}PASE2")).replace_strict(
        dict(enumerate(walking["days"])), default=None, return_dtype=pl.Float64
    )
    hours = pl.col(col(f"V{v}PASE2HR")).replace_strict(
        {code + 1: h for code, h in enumerate(walking["hours"])}, default=None, return_dtype=pl.Float64
    )
    subscore = pl.when(days == 0).then(0.0).otherwise(walking["weight"] * days / 7 * hours)
    return allclinical.select(
        pl.col(col("ID")).alias("ID"),
        pl.lit(v).alias("visit"),
        pl.col(col(f"V{v}PASE")).cast(pl.Float64).alias("pase_total"),
        subscore.alias("pase_walking"),
    )
```

- [ ] **Step 4: Point the replication at the shared code**

In `analyses/lo2022_walking/lo2022.py`:

1. Delete the module-level `AMOUNT_ITEMS = …` and `WALKER_VALUES = …` lines, and the whole `_walk_amount` function.
2. Add to the imports:

```python
from oai.derive.walking import AMOUNT_ITEMS, WALKER_VALUES, walker_status, walking_sessions
```

3. In `build`, replace the block from `missing_as = WALKER_VALUES[A["exposure.missing_walking_as"]]` through the `respondents = current.with_columns(…)` statement with:

```python
    respondents = current.with_columns(
        walker_status(
            yes_without_amount_as=A["exposure.yes_without_amount_as"],
            missing_as=A["exposure.missing_walking_as"],
        )
    )
```

4. Replace

```python
    midpoints = A["exposure.category_midpoints"]
    walk_times = (
        _walk_amount("years", midpoints["years"])
        * _walk_amount("months", midpoints["months"])
        * _walk_amount("times", midpoints["times"])
    )
```

with

```python
    walk_times = walking_sessions(A["exposure.category_midpoints"])
```

- [ ] **Step 5: Run the tests, then prove the replication is unchanged**

Run: `uv run pytest tests/test_derive_walking.py tests/test_lo2022_build.py tests/test_analyses.py -q`
Expected: PASS.

```bash
W=.superpowers/sdd/2026-10-01-walking-validation
R="$(uv run python -c 'from oai.config import get_settings; print(get_settings().results_dir / "lo2022_walking")')"
uv run oai run lo2022_walking > /dev/null && uv run oai run lo2022_walking --variant walker_requires_amount > /dev/null
for l in default walker_requires_amount; do for f in $W/pre-refactor/$l/*.csv; do cmp "$f" "$R/$l/$(basename $f)" || echo "DIFF $l/$(basename $f)"; done; done; echo checked
```

Expected: only `checked` is printed, with no `DIFF` lines.

- [ ] **Step 6: Commit**

```bash
uv run ruff check && uv run ruff format --check && uv run pytest -q
git add src/oai/derive/walking.py src/oai/derive/pase.py analyses/lo2022_walking/lo2022.py tests/test_derive_walking.py tests/test_analyses.py
git commit -m "refactor: shared walking-item coding and PASE walking subscore (replication outputs unchanged)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `oaimodels::fit_knee_gee()`; the replication uses it

**Files:**
- Create: `r/oaimodels/R/gee.R`, `r/oaimodels/tests/testthat/test-gee.R`
- Modify: `r/oaimodels/NAMESPACE`, `analyses/lo2022_walking/models.R`

**Interfaces:**
- Produces: `fit_knee_gee(data, rhs, outcome = "y", term = "walkerTRUE", corstr = "exchangeable", id = "ID")`, returning a named numeric `c(or, lo, hi, log_or, se)`.
- The replication's outputs must be identical before and after this task (the Task 2 snapshot).

- [ ] **Step 1: Write the failing tests**

`r/oaimodels/tests/testthat/test-gee.R`:

```r
clustered <- function(seed = 1) {
  set.seed(seed)
  n <- 200
  d <- data.frame(ID = rep(seq_len(n), each = 2), walker = rep(stats::runif(n) < 0.6, each = 2),
                  age = rep(stats::rnorm(n, 60, 8), each = 2))
  d$y <- stats::rbinom(nrow(d), 1, stats::plogis(-1 + 0.5 * d$walker))
  d
}

test_that("fit_knee_gee matches a direct geeglm fit", {
  skip_if_not_installed("geepack")
  d <- clustered()
  est <- fit_knee_gee(d, "walker + age")
  direct <- geepack::geeglm(y ~ walker + age, id = ID, data = d, family = stats::binomial,
                            corstr = "exchangeable")
  co <- summary(direct)$coefficients["walkerTRUE", ]
  expect_equal(est[["log_or"]], co[["Estimate"]])
  expect_equal(est[["se"]], co[["Std.err"]])
  expect_equal(est[["or"]], exp(co[["Estimate"]]))
  expect_equal(est[["lo"]], exp(co[["Estimate"]] - 1.96 * co[["Std.err"]]))
  expect_equal(est[["hi"]], exp(co[["Estimate"]] + 1.96 * co[["Std.err"]]))
})

test_that("fit_knee_gee orders clusters itself and names a missing term", {
  skip_if_not_installed("geepack")
  d <- clustered()
  shuffled <- d[sample(nrow(d)), ]
  expect_equal(fit_knee_gee(shuffled, "walker"), fit_knee_gee(d, "walker"))
  expect_error(fit_knee_gee(d, "age"), "walkerTRUE")
})
```

Run: `cd r && Rscript -e 'testthat::test_local("oaimodels", stop_on_failure = TRUE)'; cd ..`
Expected: FAIL with `could not find function "fit_knee_gee"`.

- [ ] **Step 2: Implement**

`r/oaimodels/R/gee.R`:

```r
#' Knee-level logistic GEE clustered on participant (the Lo 2022 Table 2 model)
#'
#' @param data Knee rows with the outcome, `id` and the right-hand-side variables.
#' @param rhs Right-hand side, e.g. "walker + age + sex + factor(kl0)".
#' @param outcome Binary (0/1) outcome column.
#' @param term Coefficient whose odds ratio is returned.
#' @param corstr Working correlation (geepack).
#' @param id Cluster column; rows are ordered by it before fitting.
#' @return Named numeric: or, lo, hi (95% Wald), log_or, se.
fit_knee_gee <- function(data, rhs, outcome = "y", term = "walkerTRUE",
                         corstr = "exchangeable", id = "ID") {
  if (!requireNamespace("geepack", quietly = TRUE)) {
    stop("fit_knee_gee() needs the geepack package", call. = FALSE)
  }
  data <- data[order(data[[id]]), , drop = FALSE]
  data$.cluster <- data[[id]]
  model <- geepack::geeglm(stats::as.formula(paste(outcome, "~", rhs)), id = .cluster,
                           data = data, family = stats::binomial, corstr = corstr)
  coefs <- summary(model)$coefficients
  if (!term %in% rownames(coefs)) {
    stop("term ", term, " is not in the model (", paste(rownames(coefs), collapse = ", "), ")",
         call. = FALSE)
  }
  b <- coefs[term, "Estimate"]
  se <- coefs[term, "Std.err"]
  c(or = exp(b), lo = exp(b - 1.96 * se), hi = exp(b + 1.96 * se), log_or = b, se = se)
}
```

Append `export(fit_knee_gee)` to `r/oaimodels/NAMESPACE`.

In `analyses/lo2022_walking/models.R`, replace the whole `fit_or <- function(d, rhs) { … }` definition with:

```r
fit_or <- function(d, rhs) {
  oaimodels::fit_knee_gee(d, rhs, corstr = A[["model.corstr"]])[c("or", "lo", "hi")]
}
```

- [ ] **Step 3: Run the tests and prove the replication is unchanged**

```bash
W=.superpowers/sdd/2026-10-01-walking-validation
R="$(uv run python -c 'from oai.config import get_settings; print(get_settings().results_dir / "lo2022_walking")')"
cd r && Rscript -e 'testthat::test_local("oaimodels", stop_on_failure = TRUE)' && cd ..
uv run oai run lo2022_walking > /dev/null && uv run oai run lo2022_walking --variant walker_requires_amount > /dev/null
for l in default walker_requires_amount; do for f in $W/pre-refactor/$l/*.csv; do cmp "$f" "$R/$l/$(basename $f)" || echo "DIFF $l/$(basename $f)"; done; done; echo checked
```

Expected: `FAIL 0`, then only `checked`.

- [ ] **Step 4: Commit**

```bash
uv run pytest -q
git add r/oaimodels analyses/lo2022_walking/models.R
git commit -m "refactor: oaimodels::fit_knee_gee() shared by the replication (outputs unchanged)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Per-analysis R profile (`[r] profile`), `quantreg`, and CI

**Files:**
- Modify: `src/oai/manifest.py`, `src/oai/runner.py`, `r/renv/profiles/report/renv.lock`, `r/oaimodels/DESCRIPTION`, `.github/workflows/ci.yml`, `docs/reporting.md`
- Test: `tests/test_manifest.py`, `tests/test_runner.py`, `tests/test_r_interop.py`

**Interfaces:**
- Produces:
  - `Analysis.r_profile: str | None = None` (from `[r] profile`). It must be a lowercase identifier, and analyses with enclave steps may not set it.
  - `oai.runner.process_env(step, analysis, env) -> dict[str, str]`, which adds `RENV_PROFILE` for R steps when `r_profile` is set.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_manifest.py`:

```python
R_PROFILE = REPORT_MANIFEST + '\n[r]\nprofile = "report"\n'


def test_r_profile_parsed(tmp_path):
    assert load_analysis(write_report_analysis(tmp_path, R_PROFILE)).r_profile == "report"
    assert load_analysis(write_analysis(tmp_path / "other", VALID.replace('stage = "enclave"', 'stage = "local"'))).r_profile is None


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (REPORT_MANIFEST + '\n[r]\nprofile = "Bad Name"\n', "[r] profile"),
        (VALID + '\n[r]\nprofile = "report"\n', "enclave"),
    ],
)
def test_invalid_r_profile(tmp_path, text, message):
    root = write_analysis(tmp_path, text, files=("frame.py", "models.R", "report.qmd", "notes.md"))
    (root / "assumptions.toml").write_text(REPORT_ASSUMPTIONS)
    with pytest.raises(ManifestError, match=re.escape(message)):
        load_analysis(root)
```

Append to `tests/test_runner.py`:

```python
def test_process_env_sets_renv_profile_for_r_steps_only(tmp_path):
    root = tmp_path / "analyses" / "prof"
    root.mkdir(parents=True)
    (root / "analysis.toml").write_text(
        'name = "prof"\n\n[r]\nprofile = "report"\n\n'
        '[[steps]]\nid = "a"\nlang = "python"\nentry = "a.py"\n\n'
        '[[steps]]\nid = "b"\nlang = "r"\nentry = "b.R"\n'
    )
    (root / "a.py").write_text("")
    (root / "b.R").write_text("")
    analysis = load_analysis(root)
    py, r = analysis.steps
    assert "RENV_PROFILE" not in runner.process_env(py, analysis, {"X": "1"})
    assert runner.process_env(r, analysis, {"X": "1"}) == {"X": "1", "RENV_PROFILE": "report"}
```

Append to `tests/test_r_interop.py`:

```python
@pytest.mark.skipif(not _report_profile_ready(), reason="the r/ report profile is not restored")
def test_r_steps_run_under_the_analysis_r_profile(tmp_path):
    root = tmp_path / "analyses" / "profiled"
    root.mkdir(parents=True)
    (root / "analysis.toml").write_text(
        'name = "profiled"\n\n[r]\nprofile = "report"\n\n'
        '[[steps]]\nid = "probe"\nlang = "r"\nentry = "probe.R"\n'
    )
    (root / "probe.R").write_text(
        'writeLines(as.character(requireNamespace("quantreg", quietly = TRUE)), '
        'file.path(Sys.getenv("OAI_RESULTS_DIR"), "probe.txt"))\n'
    )
    settings = load_settings(
        env={"OAI_WORK_DIR": str(tmp_path / "w"), "OAI_RESULTS_DIR": str(tmp_path / "r")},
        repo_root=REPO,
    )
    run_analysis(load_analysis(root), settings, echo=lambda _: None)
    assert (tmp_path / "r" / "profiled" / "default" / "probe.txt").read_text().strip() == "TRUE"
```

Run: `uv run pytest tests/test_manifest.py tests/test_runner.py -q -k "r_profile or process_env"`
Expected: FAIL. `r_profile` and `process_env` are unknown (AttributeError / TypeError).

- [ ] **Step 2: Implement manifest and runner support**

In `src/oai/manifest.py`:

1. Add `r_profile: str | None = None` as the last field of `Analysis`, after `report`.
2. In `_parse`, replace the `return Analysis(…)` statement with:

```python
    r_profile = _parse_r(data["r"], steps, fail) if "r" in data else None
    return Analysis(
        name,
        data.get("description", ""),
        root,
        inputs,
        tuple(steps),
        export,
        outputs,
        report,
        r_profile,
    )
```

3. Add this function below `_parse_report`:

```python
def _parse_r(raw: Any, steps: list[Step], fail: Callable[[str], NoReturn]) -> str:
    profile = raw.get("profile") if isinstance(raw, dict) else None
    if not isinstance(profile, str) or not re.match(r"^[a-z][a-z0-9_-]*$", profile):
        fail("[r] profile must be a lowercase renv profile name, e.g. \"report\"")
    if any(s.stage == "enclave" for s in steps):
        fail("[r] profile is local-only: enclave bundles restore only the default R library")
    return profile
```

In `src/oai/runner.py`, add after `r_profile_env`:

```python
def process_env(step: Step, analysis: Analysis, env: Mapping[str, str]) -> dict[str, str]:
    """One step's environment: R steps get the analysis's renv profile ([r] profile)."""
    out = dict(env)
    if step.lang == "r" and analysis.r_profile:
        out["RENV_PROFILE"] = analysis.r_profile
    return out
```

and in `run_analysis` replace `proc = subprocess.run(cmd, cwd=analysis.root, env=env)` with:

```python
        proc = subprocess.run(cmd, cwd=analysis.root, env=process_env(step, analysis, env))
```

Run: `uv run pytest tests/test_manifest.py tests/test_runner.py -q`
Expected: PASS.

- [ ] **Step 3: Add `quantreg` to the report profile only**

```bash
cd r && RENV_PROFILE=report Rscript -e 'renv::install("quantreg", prompt = FALSE); renv::snapshot(prompt = FALSE)' && cd ..
git diff --exit-code r/renv.lock && echo "default lockfile unchanged"
grep -c '"Package": "quantreg"' r/renv/profiles/report/renv.lock
```

Expected: `default lockfile unchanged`, then `1`.

In `r/oaimodels/DESCRIPTION`:
- change the `Suggests:` line to `Suggests: testthat (>= 3.0.0), lme4, ordinal, geepack, survival, quantreg`;
- change `Imports: nanoparquet, jsonlite` to `Imports: nanoparquet, jsonlite, parallel, stats`.

Run: `uv run pytest tests/test_r_interop.py -q`
Expected: PASS, including `test_r_steps_run_under_the_analysis_r_profile`.

- [ ] **Step 4: CI and docs**

In `.github/workflows/ci.yml`, replace the `r-report` job's last step with:

```yaml
      - run: Rscript -e 'testthat::test_local("oaireport", stop_on_failure = TRUE); testthat::test_local("oaimodels", stop_on_failure = TRUE)'
```

In `docs/reporting.md`, under "## The `report` renv profile", append:

```markdown
The profile also carries local-only analysis packages (e.g. `quantreg`). An analysis whose R
steps need them declares, in `analysis.toml`:

```toml
[r]
profile = "report"   # R steps run with RENV_PROFILE=report; not allowed with enclave steps
```
```

- [ ] **Step 5: Commit**

```bash
uv run ruff check && uv run ruff format --check && uv run pytest -q
git add src/oai/manifest.py src/oai/runner.py r/renv/profiles/report/renv.lock r/oaimodels/DESCRIPTION .github/workflows/ci.yml docs/reporting.md tests/test_manifest.py tests/test_runner.py tests/test_r_interop.py
git commit -m "feat: per-analysis renv profile for R steps; quantreg in the report profile

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: `oaimodels` validity helpers

**Files:**
- Create: `r/oaimodels/R/validity.R`, `r/oaimodels/tests/testthat/test-validity.R`
- Modify: `r/oaimodels/NAMESPACE`

**Interfaces:**
- Produces:
  - `hodges_lehmann(x, y) -> c(estimate, lo, hi)`;
  - `rank_biserial(x, y) -> numeric`;
  - `jonckheere(x, group, permutations = 2000, seed = 1) -> c(statistic, p)` (one-sided, increasing);
  - `median_regression(formula, data, term) -> c(estimate, lo, hi)` (needs quantreg);
  - `spearman_ci(x, y) -> c(rho, lo, hi, n)`;
  - `deattenuate(rho, reliability_x = 1, reliability_y = 1)`;
  - `wave_reliability(r, share_two_waves)`;
  - `wilson(k, n) -> c(estimate, lo, hi)`;
  - `classification(test, reference) -> data.frame(measure, estimate, lo, hi, k, n)`, with measures `se`, `sp`, `ppv` and `npv`;
  - `auc_ci(score, reference, reps = 1000, seed = 1) -> c(estimate, lo, hi)`;
  - `classification_by_stratum(test, reference, stratum) -> data.frame(measure, estimate, lo, hi, k, n, stratum, p_differs)`.

- [ ] **Step 1: Write the failing tests**

`r/oaimodels/tests/testthat/test-validity.R`:

```r
test_that("hodges_lehmann and rank_biserial measure a shift", {
  hl <- hodges_lehmann(1:10 + 5, 1:10)
  expect_equal(hl[["estimate"]], 5, tolerance = 1e-6)
  expect_true(hl[["lo"]] < 5 && hl[["hi"]] > 5)
  expect_equal(rank_biserial(11:20, 1:10), 1)
  expect_equal(rank_biserial(1:10, 1:10), 0)
})

test_that("jonckheere detects an increasing trend and not a decreasing one", {
  g <- factor(rep(c("none", "lower", "upper"), each = 3), levels = c("none", "lower", "upper"))
  up <- jonckheere(1:9, g, permutations = 999, seed = 1)
  down <- jonckheere(9:1, g, permutations = 999, seed = 1)
  expect_equal(up[["statistic"]], 27)
  expect_lt(up[["p"]], 0.05)
  expect_gt(down[["p"]], 0.9)
})

test_that("median_regression returns the median difference", {
  skip_if_not_installed("quantreg")
  d <- data.frame(y = c(rep(c(1, 2, 3), 10), rep(c(4, 5, 6), 10)), group = rep(c(0, 1), each = 30))
  est <- median_regression(y ~ group, d, "group")
  expect_equal(est[["estimate"]], 3, tolerance = 1e-6)
  expect_error(median_regression(y ~ group, d, "other"), "other")
})

test_that("spearman_ci, deattenuate and wave_reliability", {
  s <- spearman_ci(c(1, 2, 3, 4, 5, 6), c(2, 1, 4, 3, 6, 5))
  expect_equal(s[["rho"]], stats::cor(c(1, 2, 3, 4, 5, 6), c(2, 1, 4, 3, 6, 5), method = "spearman"))
  expect_equal(s[["n"]], 6)
  expect_true(s[["lo"]] < s[["rho"]] && s[["hi"]] > s[["rho"]])
  expect_equal(deattenuate(0.3, reliability_y = 0.36), 0.5)
  expect_equal(deattenuate(0.9, reliability_y = 0.25), 1)
  expect_equal(wave_reliability(0.6, 1), 2 * 0.6 / 1.6)
  expect_equal(wave_reliability(0.6, 0), 0.6)
})

test_that("wilson and classification", {
  w <- wilson(5, 10)
  expect_equal(unname(w), c(0.5, 0.2366, 0.7634), tolerance = 1e-4)
  test <- c(TRUE, TRUE, TRUE, FALSE, TRUE, FALSE, FALSE, FALSE)
  ref <- c(TRUE, TRUE, TRUE, TRUE, FALSE, FALSE, FALSE, FALSE)
  cl <- classification(test, ref)
  expect_equal(cl$measure, c("se", "sp", "ppv", "npv"))
  expect_equal(cl$estimate, c(3 / 4, 3 / 4, 3 / 4, 3 / 4))
  expect_equal(cl$k, c(3, 3, 3, 3))
  expect_equal(cl$n, c(4, 4, 4, 4))
})

test_that("classification handles empty cells", {
  cl <- classification(c(TRUE, TRUE), c(TRUE, TRUE))
  expect_true(is.na(cl$estimate[cl$measure == "sp"]))
  expect_equal(cl$n[cl$measure == "sp"], 0)
  s <- classification_by_stratum(c(TRUE, TRUE, FALSE), c(TRUE, TRUE, TRUE), c("a", "b", "b"))
  expect_true(all(is.na(s$estimate[s$measure == "sp"])))
})

test_that("auc_ci and classification_by_stratum", {
  a <- auc_ci(c(1, 2, 3, 4), c(FALSE, FALSE, TRUE, TRUE), reps = 200, seed = 1)
  expect_equal(a[["estimate"]], 1)
  set.seed(2)
  ref <- rep(c(TRUE, FALSE), 100)
  stratum <- rep(c("a", "b"), each = 100)
  test <- ifelse(stratum == "a", ref, stats::runif(200) < 0.5)
  s <- classification_by_stratum(test, ref, stratum)
  expect_setequal(unique(s$stratum), c("a", "b"))
  expect_equal(s$estimate[s$measure == "se" & s$stratum == "a"], 1)
  expect_lt(s$p_differs[s$measure == "se"][1], 0.001)
})
```

Run: `cd r && RENV_PROFILE=report Rscript -e 'testthat::test_local("oaimodels", stop_on_failure = TRUE)'; cd ..`
Expected: FAIL with `could not find function "hodges_lehmann"` (and the others).

- [ ] **Step 2: Implement `r/oaimodels/R/validity.R`**

```r
# Measurement-validity statistics for comparing a self-report with a device reference.

#' Hodges-Lehmann shift (x minus y) with its 95% CI (Wilcoxon rank-sum inversion)
hodges_lehmann <- function(x, y) {
  x <- x[!is.na(x)]
  y <- y[!is.na(y)]
  w <- suppressWarnings(stats::wilcox.test(x, y, conf.int = TRUE, exact = FALSE))
  c(estimate = unname(w$estimate), lo = w$conf.int[1], hi = w$conf.int[2])
}

#' Rank-biserial correlation: P(x > y) - P(x < y), ties counting one half
rank_biserial <- function(x, y) {
  x <- x[!is.na(x)]
  y <- y[!is.na(y)]
  r <- rank(c(x, y))
  n1 <- length(x)
  u <- sum(r[seq_len(n1)]) - n1 * (n1 + 1) / 2
  2 * u / (n1 * length(y)) - 1
}

jt_statistic <- function(x, g) {
  levels <- sort(unique(g))
  s <- 0
  for (a in seq_along(levels)) for (b in seq_along(levels)) if (a < b) {
    xa <- x[g == levels[a]]
    xb <- x[g == levels[b]]
    r <- rank(c(xa, xb))
    nb <- length(xb)
    s <- s + sum(r[length(xa) + seq_len(nb)]) - nb * (nb + 1) / 2
  }
  s
}

#' Jonckheere-Terpstra statistic for an increasing trend across ordered groups, with a
#' one-sided permutation p-value
jonckheere <- function(x, group, permutations = 2000, seed = 1) {
  ok <- !is.na(x) & !is.na(group)
  x <- x[ok]
  g <- as.integer(group[ok])
  observed <- jt_statistic(x, g)
  set.seed(seed)
  perm <- replicate(permutations, jt_statistic(sample(x), g))
  c(statistic = observed, p = (1 + sum(perm >= observed)) / (permutations + 1))
}

#' Median (quantile 0.5) regression coefficient for one term, with a 95% CI
median_regression <- function(formula, data, term) {
  if (!requireNamespace("quantreg", quietly = TRUE)) {
    stop("median_regression() needs the quantreg package", call. = FALSE)
  }
  fit <- quantreg::rq(formula, tau = 0.5, data = data)
  s <- summary(fit, se = "nid")$coefficients
  if (!term %in% rownames(s)) {
    stop("term ", term, " is not in the model (", paste(rownames(s), collapse = ", "), ")",
         call. = FALSE)
  }
  est <- s[term, "Value"]
  se <- s[term, "Std. Error"]
  c(estimate = est, lo = est - 1.96 * se, hi = est + 1.96 * se)
}

#' Spearman rho with a Bonett-Wright 95% CI
spearman_ci <- function(x, y) {
  ok <- stats::complete.cases(x, y)
  x <- x[ok]
  y <- y[ok]
  n <- length(x)
  rho <- stats::cor(x, y, method = "spearman")
  se <- sqrt((1 + rho^2 / 2) / (n - 3))
  z <- atanh(rho)
  c(rho = rho, lo = tanh(z - 1.96 * se), hi = tanh(z + 1.96 * se), n = n)
}

#' A correlation corrected for unreliability, capped at +/-1
deattenuate <- function(rho, reliability_x = 1, reliability_y = 1) {
  pmax(pmin(rho / sqrt(reliability_x * reliability_y), 1), -1)
}

#' Reliability of a person's mean over one or two waves from the between-wave correlation
#' (Spearman-Brown for two waves), weighted by the share with two waves
wave_reliability <- function(r, share_two_waves) {
  share_two_waves * (2 * r / (1 + r)) + (1 - share_two_waves) * r
}

#' Wilson 95% interval for k successes of n (NA when n is 0)
wilson <- function(k, n) {
  if (n == 0) return(c(estimate = NA_real_, lo = NA_real_, hi = NA_real_))
  p <- k / n
  z <- 1.96
  d <- 1 + z^2 / n
  centre <- (p + z^2 / (2 * n)) / d
  half <- z * sqrt(p * (1 - p) / n + z^2 / (4 * n^2)) / d
  c(estimate = p, lo = centre - half, hi = centre + half)
}

#' Sensitivity, specificity, PPV and NPV of a binary test against a binary reference
classification <- function(test, reference) {
  ok <- !is.na(test) & !is.na(reference)
  t <- as.logical(test[ok])
  r <- as.logical(reference[ok])
  tp <- sum(t & r)
  fn <- sum(!t & r)
  fp <- sum(t & !r)
  tn <- sum(!t & !r)
  counts <- list(se = c(tp, tp + fn), sp = c(tn, tn + fp), ppv = c(tp, tp + fp), npv = c(tn, tn + fn))
  do.call(rbind, lapply(names(counts), function(m) {
    k <- counts[[m]][1]
    n <- counts[[m]][2]
    w <- wilson(k, n)
    data.frame(measure = m, estimate = w[["estimate"]], lo = w[["lo"]], hi = w[["hi"]], k = k, n = n)
  }))
}

#' AUC of a score for a binary reference (Mann-Whitney), percentile bootstrap 95% CI
auc_ci <- function(score, reference, reps = 1000, seed = 1) {
  ok <- !is.na(score) & !is.na(reference)
  s <- score[ok]
  r <- as.logical(reference[ok])
  auc <- function(s, r) {
    n1 <- sum(r)
    n0 <- sum(!r)
    if (n1 == 0 || n0 == 0) return(NA_real_)
    (sum(rank(s)[r]) - n1 * (n1 + 1) / 2) / (n1 * n0)
  }
  set.seed(seed)
  boots <- replicate(reps, {
    i <- sample.int(length(s), replace = TRUE)
    auc(s[i], r[i])
  })
  q <- stats::quantile(boots, c(0.025, 0.975), na.rm = TRUE, names = FALSE)
  c(estimate = auc(s, r), lo = q[1], hi = q[2])
}

#' Sensitivity and specificity per stratum, with a likelihood-ratio p-value for whether each
#' differs across strata (NA when it cannot be tested)
classification_by_stratum <- function(test, reference, stratum) {
  ok <- !is.na(test) & !is.na(reference) & !is.na(stratum)
  t <- as.logical(test[ok])
  r <- as.logical(reference[ok])
  s <- as.character(stratum[ok])
  rows <- lapply(sort(unique(s)), function(level) {
    cl <- classification(t[s == level], r[s == level])
    cl$stratum <- level
    cl[cl$measure %in% c("se", "sp"), ]
  })
  out <- do.call(rbind, rows)
  lr_p <- function(subset) {
    correct <- (t == r)[subset]
    st <- factor(s[subset])
    if (nlevels(st) < 2 || length(unique(correct)) < 2) return(NA_real_)
    full <- stats::glm(correct ~ st, family = stats::binomial)
    null <- stats::glm(correct ~ 1, family = stats::binomial)
    stats::anova(null, full, test = "LRT")[2, "Pr(>Chi)"]
  }
  out$p_differs <- ifelse(out$measure == "se", lr_p(r), lr_p(!r))
  rownames(out) <- NULL
  out
}
```

Append to `r/oaimodels/NAMESPACE`:

```
export(hodges_lehmann)
export(rank_biserial)
export(jonckheere)
export(median_regression)
export(spearman_ci)
export(deattenuate)
export(wave_reliability)
export(wilson)
export(classification)
export(auc_ci)
export(classification_by_stratum)
```

- [ ] **Step 3: Run the tests in both profiles**

Run: `cd r && RENV_PROFILE=report Rscript -e 'testthat::test_local("oaimodels", stop_on_failure = TRUE)' && Rscript -e 'testthat::test_local("oaimodels", stop_on_failure = TRUE)'; cd ..`
Expected: `FAIL 0` both times. In the default profile, the quantreg test is skipped.

- [ ] **Step 4: Commit**

```bash
git add r/oaimodels
git commit -m "feat(oaimodels): validity statistics (HL, rank-biserial, JT, median regression, Se/Sp, AUC)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: `oaimodels` bias-analysis engine

**Files:**
- Create: `r/oaimodels/R/bias.R`, `r/oaimodels/tests/testthat/test-bias.R`
- Modify: `r/oaimodels/NAMESPACE`

**Interfaces:**
- Produces:
  - `beta_shapes(k, n) -> c(shape1, shape2)`;
  - `true_prevalence(p_obs, se, sp)`;
  - `reclass_probs(p_obs, se, sp) -> list(p_true, ppv, fom)`, where `fom` = P(truly exposed | classified unexposed);
  - `correct_or_2x2(a, b, c, d, se_case, sp_case, se_ctrl = se_case, sp_ctrl = sp_case)`;
  - `reclassify(persons, se, sp)`, which returns NULL when the draw is impossible;
  - `pba(...)`, returning `data.frame(iter, log_or, se, log_or_total, discarded)`;
  - `summarise_pba(...)`, returning `data.frame(or, lo_sys, hi_sys, lo_total, hi_total, conclusion_share, discarded, n)`.
- `persons` has columns `ID`, `observed` (logical) and `stratum` (outcome status, e.g. "case" / "noncase"). Reclassification always happens within these strata. Non-differential means one Se/Sp draw shared by all strata; differential means one draw per stratum.
- `priors` has columns `stratum`, `se1`, `se2`, `sp1`, `sp2` (Beta shapes), or `stratum`, `se`, `sp` for fixed values.

- [ ] **Step 1: Write the failing tests**

`r/oaimodels/tests/testthat/test-bias.R`:

```r
person_data <- function(n = 400, seed = 1) {
  set.seed(seed)
  persons <- data.frame(ID = seq_len(n), observed = stats::runif(n) < 0.5)
  y <- stats::rbinom(n, 1, stats::plogis(-0.5 + 0.4 * persons$observed))
  persons$stratum <- ifelse(y == 1, "case", "noncase")
  knees <- data.frame(ID = persons$ID, y = y, walker = persons$observed)
  list(persons = persons, knees = knees)
}
glm_fit <- function(k) {
  co <- summary(stats::glm(y ~ walker, data = k, family = stats::binomial))$coefficients
  c(log_or = co["walkerTRUE", "Estimate"], se = co["walkerTRUE", "Std. Error"])
}

test_that("prevalence and reclassification algebra", {
  expect_equal(beta_shapes(8, 10), c(shape1 = 9, shape2 = 3))
  expect_equal(true_prevalence(0.5, 1, 1), 0.5)
  p <- reclass_probs(0.5, 1, 1)
  expect_equal(c(p$ppv, p$fom), c(1, 0))
  expect_equal(correct_or_2x2(10, 20, 30, 40, 1, 1), (10 * 40) / (20 * 30))
  expect_equal(correct_or_2x2(100, 100, 100, 300, 0.8, 0.9), 44 / 9, tolerance = 1e-6)
})

test_that("reclassify is the identity at perfect sensitivity and specificity", {
  d <- person_data()
  set.seed(3)
  out <- reclassify(d$persons, c(case = 1, noncase = 1), c(case = 1, noncase = 1))
  expect_equal(out, d$persons$observed)
})

test_that("pba with fixed perfect classification returns the observed OR", {
  d <- person_data()
  observed <- glm_fit(d$knees)
  draws <- pba(d$persons, d$knees, glm_fit, data.frame(stratum = "all", se = 1, sp = 1),
               iterations = 20, seed = 1)
  expect_false(any(draws$discarded))
  expect_equal(draws$log_or, rep(observed[["log_or"]], 20))
  s <- summarise_pba(draws, direction = sign(observed[["log_or"]]), significant = FALSE)
  expect_equal(s$or, exp(observed[["log_or"]]))
  expect_equal(s$conclusion_share, 1)
})

test_that("impossible priors are discarded, not fatal", {
  d <- person_data()
  # worse than chance (Se + Sp <= 1), and a negative true prevalence (observed < 1 - Sp)
  for (fixed in list(c(0.3, 0.3), c(0.9, 0.3))) {
    draws <- pba(d$persons, d$knees, glm_fit, data.frame(stratum = "all", se = fixed[1], sp = fixed[2]),
                 iterations = 5, seed = 1)
    expect_true(all(draws$discarded))
    s <- summarise_pba(draws)
    expect_true(is.na(s$or))
    expect_equal(s$discarded, 1)
  }
})

test_that("differential priors must cover every stratum", {
  d <- person_data()
  bad <- data.frame(stratum = "case", se1 = 9, se2 = 2, sp1 = 9, sp2 = 2)
  expect_error(pba(d$persons, d$knees, glm_fit, bad, differential = TRUE, iterations = 2), "noncase")
})

test_that("pba is identical across core counts", {
  skip_on_os("windows")
  d <- person_data()
  priors <- data.frame(stratum = "all", se1 = 90, se2 = 10, sp1 = 80, sp2 = 20)
  one <- pba(d$persons, d$knees, glm_fit, priors, iterations = 8, seed = 4, cores = 1)
  two <- pba(d$persons, d$knees, glm_fit, priors, iterations = 8, seed = 4, cores = 2)
  expect_equal(one, two)
})

test_that("pba recovers a true OR under known non-differential misclassification", {
  skip_if(Sys.getenv("OAI_SLOW") == "", "set OAI_SLOW=1 to run the simulation test")
  set.seed(11)
  n <- 4000
  truth <- stats::runif(n) < 0.5
  y <- stats::rbinom(n, 1, stats::plogis(-0.5 + log(0.6) * truth))
  observed <- ifelse(truth, stats::runif(n) < 0.85, stats::runif(n) < 0.25)  # Se 0.85, Sp 0.75
  persons <- data.frame(ID = seq_len(n), observed = observed, stratum = ifelse(y == 1, "case", "noncase"))
  knees <- data.frame(ID = seq_len(n), y = y, walker = observed)
  true_or <- exp(glm_fit(data.frame(y = y, walker = truth))[["log_or"]])
  priors <- data.frame(stratum = "all", se1 = 851, se2 = 151, sp1 = 751, sp2 = 251)
  s <- summarise_pba(pba(persons, knees, glm_fit, priors, iterations = 300, seed = 2))
  expect_lt(abs(s$or - true_or), 0.05)
})
```

Run: `cd r && RENV_PROFILE=report Rscript -e 'testthat::test_local("oaimodels", stop_on_failure = TRUE)'; cd ..`
Expected: FAIL with `could not find function "beta_shapes"` (and the others).

- [ ] **Step 2: Implement `r/oaimodels/R/bias.R`**

```r
# Probabilistic bias analysis for a misclassified binary person-level exposure
# (Lash, Fox & MacLehose, record-level method). Reclassification always happens within outcome
# strata; "non-differential" shares one Se/Sp draw across strata, "differential" draws per stratum.

#' Beta(k + 1, n - k + 1) shapes for a proportion observed as k of n (uniform prior)
beta_shapes <- function(k, n) c(shape1 = k + 1, shape2 = n - k + 1)

#' True exposure prevalence implied by the observed prevalence, sensitivity and specificity
true_prevalence <- function(p_obs, se, sp) (p_obs + sp - 1) / (se + sp - 1)

#' P(truly exposed | classified exposed) and P(truly exposed | classified unexposed)
reclass_probs <- function(p_obs, se, sp) {
  p <- true_prevalence(p_obs, se, sp)
  list(p_true = p, ppv = se * p / p_obs, fom = (1 - se) * p / (1 - p_obs))
}

#' Corrected odds ratio from a 2x2 table with outcome-specific classification
#' a = exposed cases, b = unexposed cases, c = exposed non-cases, d = unexposed non-cases
correct_or_2x2 <- function(a, b, c, d, se_case, sp_case, se_ctrl = se_case, sp_ctrl = sp_case) {
  n1 <- a + b
  n0 <- c + d
  A <- (a - (1 - sp_case) * n1) / (se_case + sp_case - 1)
  C <- (c - (1 - sp_ctrl) * n0) / (se_ctrl + sp_ctrl - 1)
  B <- n1 - A
  D <- n0 - C
  if (!all(is.finite(c(A, B, C, D))) || any(c(A, B, C, D) <= 0)) return(NA_real_)
  (A * D) / (B * C)
}

#' One reclassification of persons$observed within persons$stratum; NULL if impossible
reclassify <- function(persons, se, sp) {
  out <- logical(nrow(persons))
  for (s in unique(persons$stratum)) {
    i <- persons$stratum == s
    p_obs <- mean(persons$observed[i])
    pr <- reclass_probs(p_obs, se[[s]], sp[[s]])
    probs <- c(pr$p_true, pr$ppv, pr$fom)
    if (se[[s]] + sp[[s]] <= 1 || !all(is.finite(probs)) || pr$p_true <= 0 || pr$p_true >= 1 ||
        any(probs[2:3] < 0 | probs[2:3] > 1)) {
      return(NULL)
    }
    u <- stats::runif(sum(i))
    out[i] <- ifelse(persons$observed[i], u < pr$ppv, u < pr$fom)
  }
  out
}

#' Record-level probabilistic bias analysis
#' @param persons data.frame(ID, observed, stratum)
#' @param knees rows passed to `fit` after `exposure` is replaced by each draw (matched by ID)
#' @param fit function(knees) -> c(log_or, se)
#' @param priors Beta shapes (stratum, se1, se2, sp1, sp2) or fixed values (stratum, se, sp)
#' @param differential One draw per stratum (TRUE) or one shared draw (FALSE; one prior row)
pba <- function(persons, knees, fit, priors, differential = FALSE, iterations = 1000, seed = 1,
                cores = 1, exposure = "walker") {
  strata <- unique(persons$stratum)
  fixed <- all(c("se", "sp") %in% names(priors))
  if (differential) {
    missing <- setdiff(strata, priors$stratum)
    if (length(missing)) stop("priors lack strata: ", paste(missing, collapse = ", "), call. = FALSE)
  } else if (nrow(priors) != 1) {
    stop("non-differential pba() takes one prior row", call. = FALSE)
  }
  draw <- function(rows) {
    if (fixed) return(list(se = rows$se, sp = rows$sp))
    list(se = stats::rbeta(nrow(rows), rows$se1, rows$se2),
         sp = stats::rbeta(nrow(rows), rows$sp1, rows$sp2))
  }
  one <- function(i) {
    set.seed(seed + i)
    if (differential) {
      rows <- priors[match(strata, priors$stratum), ]
      d <- draw(rows)
      se <- stats::setNames(d$se, strata)
      sp <- stats::setNames(d$sp, strata)
    } else {
      d <- draw(priors)
      se <- stats::setNames(rep(d$se, length(strata)), strata)
      sp <- stats::setNames(rep(d$sp, length(strata)), strata)
    }
    truth <- reclassify(persons, se, sp)
    if (is.null(truth)) {
      return(data.frame(iter = i, log_or = NA_real_, se = NA_real_, log_or_total = NA_real_,
                        discarded = TRUE))
    }
    knees[[exposure]] <- truth[match(knees$ID, persons$ID)]
    est <- fit(knees)
    data.frame(iter = i, log_or = est[["log_or"]], se = est[["se"]],
               log_or_total = stats::rnorm(1, est[["log_or"]], est[["se"]]), discarded = FALSE)
  }
  runs <- if (cores > 1) {
    parallel::mclapply(seq_len(iterations), one, mc.cores = cores)
  } else {
    lapply(seq_len(iterations), one)
  }
  failed <- vapply(runs, inherits, logical(1), what = "try-error")
  if (any(failed)) stop("pba() iteration failed: ", runs[[which(failed)[1]]], call. = FALSE)
  do.call(rbind, runs)
}

#' Median bias-adjusted OR with 95% simulation intervals, the share of iterations keeping the
#' published conclusion (same direction; CI excluding 1 when `significant`), and discards
summarise_pba <- function(draws, direction = NA, significant = NA) {
  kept <- draws[!draws$discarded, ]
  q <- function(x) {
    if (!length(x)) return(c(NA_real_, NA_real_, NA_real_))
    exp(stats::quantile(x, c(0.5, 0.025, 0.975), names = FALSE))
  }
  s <- q(kept$log_or)
  t <- q(kept$log_or_total)
  holds <- if (is.na(direction) || !nrow(kept)) NA_real_ else {
    same <- sign(kept$log_or) == direction
    sig <- if (isTRUE(significant)) abs(kept$log_or / kept$se) > 1.96 else TRUE
    mean(same & sig)
  }
  data.frame(or = s[1], lo_sys = s[2], hi_sys = s[3], lo_total = t[2], hi_total = t[3],
             conclusion_share = holds, discarded = mean(draws$discarded), n = nrow(draws))
}
```

Append to `r/oaimodels/NAMESPACE`:

```
export(beta_shapes)
export(true_prevalence)
export(reclass_probs)
export(correct_or_2x2)
export(reclassify)
export(pba)
export(summarise_pba)
```

- [ ] **Step 3: Run the tests, including the simulation**

Run: `cd r && OAI_SLOW=1 RENV_PROFILE=report Rscript -e 'testthat::test_local("oaimodels", stop_on_failure = TRUE)'; cd ..`
Expected: `FAIL 0`, with the simulation test passing.

If the simulation fails on tolerance alone, record the observed |median − truth| in the ledger before ruling. Widen to 0.08 only if the bias is in no particular direction; a systematic bias is a code defect.

- [ ] **Step 4: Commit**

```bash
git add r/oaimodels
git commit -m "feat(oaimodels): record-level probabilistic bias analysis engine

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: `walking_validation` scaffold, assumptions ledger, and the `device` step

**Files:**
- Create in `analyses/walking_validation/`: `analysis.toml`, `assumptions.toml`, `ASSUMPTIONS.md` (generated), `README.md`, `device.py`, `expected.toml`
- Modify: `tests/test_analyses.py` (add `"walking_validation"` to the expected list), `analyses/activity_agreement/README.md` (one line)

**Interfaces:**
- Consumes: Task 1 (`oai.derive.accel`) and Task 4 (`[r] profile`).
- Produces:
  - frame `device.parquet` with columns `ID, valid_days, wear_hr, mv_min, light_min, counts_per_day, bout_min, purposeful_min, bout_days_per_week, valid, wave`;
  - `device_reproduction.csv`;
  - `metrics_device.csv`, with metrics `device.<06|08>.<release_days|matched_days|wear_mismatch_days|mv_mismatch_days|bout_mismatch_days|valid_persons|release_valid_persons>`.

- [ ] **Step 1: Write the manifest and ledger**

`analyses/walking_validation/analysis.toml`:

```toml
name = "walking_validation"
description = "Validity of the 96-month walking-for-exercise item (Lo 2022 exposure) against OAI accelerometry, with a probabilistic bias analysis of Lo 2022."

[inputs]
tables = [
    "enrollees", "allclinical:00", "allclinical:06", "allclinical:08", "allclinical:10",
    "kxr_sq_bu:00", "accelerometry:06", "accelerometry:08",
    "acceldatabymin:06", "acceldatabymin:08", "acceldatabyday:06", "acceldatabyday:08",
]

[r]
profile = "report"

[[steps]]
id = "device"
lang = "python"
stage = "local"
entry = "device.py"

[[steps]]
id = "cohort"
lang = "python"
stage = "local"
entry = "build_cohort.py"
needs = ["device"]

[[steps]]
id = "validity"
lang = "r"
stage = "local"
entry = "validity.R"
needs = ["cohort"]

[[steps]]
id = "bias"
lang = "r"
stage = "local"
entry = "bias.R"
needs = ["cohort"]

[[steps]]
id = "compare"
lang = "python"
stage = "local"
entry = "compare.py"
needs = ["validity", "bias"]

[outputs]
aggregate = [
    "flow.csv", "device_reproduction.csv", "validity_*.csv", "bias_*.csv", "lo2022_*.csv",
    "comparison.csv", "metrics_*.csv", "assumptions.resolved.json",
]
```

`build_cohort.py`, `validity.R`, `bias.R` and `compare.py` don't exist yet, but the manifest requires every entry to exist. Create placeholder files that exit with an error, so `load_analysis` passes now:

```bash
cd analyses/walking_validation
printf 'raise SystemExit("cohort step: implemented in Task 8")\n' > build_cohort.py
printf 'stop("validity step: implemented in Task 9")\n' > validity.R
printf 'stop("bias step: implemented in Task 10")\n' > bias.R
printf 'raise SystemExit("compare step: implemented in Task 10")\n' > compare.py
cd ../..
```

`analyses/walking_validation/assumptions.toml`:

```toml
# Assumptions for the walking validation study.
# Spec: docs/superpowers/specs/2026-10-01-walking-validation-design.md

[device.nonwear_minutes]
value = 90
status = "confirmed"
source = "AccelData_Descrip.pdf (non-wear >90 zero minutes); >= 90 within each calendar day reproduces the release's by-day files"
rationale = "Validated for knee-OA wear patterns; 60 is the NHANES rule"
alternatives = [60]

[device.interrupt_minutes]
value = 2
status = "confirmed"
source = "AccelData_Descrip.pdf: interruptions of up to 2 consecutive minutes"

[device.interrupt_ceiling]
value = 100
status = "confirmed"
source = "AccelData_Descrip.pdf: interruptions have counts < 100"

[device.valid_day_hours]
value = 10.0
status = "confirmed"
source = "AccelData_Descrip.pdf: valid day = >= 10 wear hours"

[device.max_valid_days]
value = 7
status = "confirmed"
source = "AccelData_Descrip.pdf: only the first 7 valid days are used"

[device.min_valid_days]
value = 4
status = "confirmed"
source = "Accelerometry_Descrip.pdf: 4-7 valid days"

[device.mv_cutpoint]
value = 2020
status = "confirmed"
source = "Troiano 2008 cutpoint, as in the release"

[device.purposeful_bout_minutes]
value = 10
status = "assumed"
source = "Spec 5: purposeful walking proxy = minutes in >= 10-minute MV bouts"

[device.wave_combination]
value = "mean"
status = "assumed"
source = "Spec 4: habitual activity = mean over a person's valid waves"
choices = ["mean", "06", "08"]

[reference.walker_rule]
value = "bout_days"
status = "assumed"
source = "Spec 5: device habitual walker = >= 2 bout-days per valid week"
choices = ["bout_days", "any_bout", "bout_minutes"]

[reference.min_bout_days_per_week]
value = 2.0
status = "assumed"
source = "Spec 5"

[reference.min_bout_minutes_per_week]
value = 150.0
status = "assumed"
source = "Spec 5 variant: DHHS 2008 aerobic guideline volume"

[exposure.yes_without_amount_as]
value = "non-walker"
status = "open"
source = "Reproduces the published 887 walkers (lo2022_walking walker_requires_amount); question for the original authors in TODO.md"
choices = ["walker", "non-walker", "exclude"]

[exposure.category_midpoints]
value = { years = [3.0, 8.0, 15.5, 20.0], months = [2.5, 6.5, 10.5], times = [2.0, 6.0, 10.0] }
status = "open"
source = "As lo2022_walking exposure.category_midpoints"

[strata.reading_project]
value = 15
status = "assumed"
source = "As lo2022_walking cohort.reading_project (baseline KL for strata)"

[strata.pain_baseline_item]
value = "P01KP{side}12CV"
status = "assumed"
source = "As lo2022_walking outcomes.pain_baseline_items"

[pase.walking_scoring]
value = { days = [0.0, 1.5, 3.5, 6.0], hours = [0.5, 1.5, 3.0, 5.0], weight = 20.0 }
status = "assumed"
source = "Washburn et al. 1993 PASE scoring for item 2 (walking outside the home)"

[validity.bootstrap_reps]
value = 1000
status = "assumed"
source = "AUC percentile bootstrap"

[validity.jt_permutations]
value = 2000
status = "assumed"
source = "Jonckheere-Terpstra permutation p-value"

[bias.lo2022_label]
value = "walker_requires_amount"
status = "assumed"
source = "The lo2022_walking run whose exposure coding matches exposure.yes_without_amount_as"
choices = ["walker_requires_amount", "default"]

[bias.iterations]
value = 2000
status = "assumed"
source = "Spec 7"

[bias.tipping_iterations]
value = 200
status = "assumed"
source = "Spec 7"

[bias.tipping_step]
value = 0.05
status = "assumed"
source = "Spec 7: sensitivity 0.60-1.00 x specificity 0.40-1.00"

[bias.seed]
value = 20261001
status = "assumed"
source = "Fixed seed; iteration i uses seed + i, so results do not depend on core count"

[bias.max_discard_share]
value = 0.10
status = "assumed"
source = "Spec 12: cells discarding more than this share of draws are flagged"

[variants.wave48]
description = "Device = 48-month wave only"
set = { "device.wave_combination" = "06" }

[variants.wave72]
description = "Device = 72-month wave only"
set = { "device.wave_combination" = "08" }

[variants.walker_any_bout]
description = "Device walker = any purposeful bout"
set = { "reference.walker_rule" = "any_bout" }

[variants.walker_150min]
description = "Device walker = >= 150 purposeful-bout minutes a week"
set = { "reference.walker_rule" = "bout_minutes" }

[variants.nonwear60]
description = "NHANES 60-minute non-wear rule"
set = { "device.nonwear_minutes" = 60 }

[variants.exposure_replication_coding]
description = "'Yes' with no amount answers coded as a walker (the replication's default coding)"
set = { "exposure.yes_without_amount_as" = "walker", "bias.lo2022_label" = "default" }
```

`analyses/walking_validation/expected.toml`:

```toml
# Reference values for the compare step: the release's own accelerometry counts and the
# spec's sample sizes (spec 3). Graded by oai.replication (counts within 3% or 2).

[related]
"device" = ["device.nonwear_minutes", "device.interrupt_minutes", "device.valid_day_hours", "device.mv_cutpoint"]
"sample" = ["exposure.yes_without_amount_as", "device.wave_combination", "bias.lo2022_label"]

[default]
"device.06.valid_persons" = 1927
"device.08.valid_persons" = 1394
"device.06.matched_days" = 13040
"device.08.matched_days" = 9399
"device.06.mv_mismatch_days" = 0
"device.08.mv_mismatch_days" = 0
"device.06.bout_mismatch_days" = 0
"device.08.bout_mismatch_days" = 0
"sample.validation.persons" = 1566
"sample.lo_subset.persons" = 784
```

- [ ] **Step 2: Write `device.py`**

```python
"""Step `device`: person-wave device measures from the minute files (spec 5).

Participant-level measures go to OAI_FRAME_DIR/device.parquet, never to results. The aggregate
agreement with the release's own by-day files goes to device_reproduction.csv and
metrics_device.csv.
"""

import os
from pathlib import Path

import polars as pl

from oai.assumptions import current
from oai.derive.accel import (
    DeviceRules,
    daily_summary,
    person_summary,
    read_minutes,
    release_valid_persons,
    reproduction,
)

A = current()
rules = DeviceRules(
    nonwear_minutes=A["device.nonwear_minutes"],
    interrupt_minutes=A["device.interrupt_minutes"],
    interrupt_ceiling=A["device.interrupt_ceiling"],
    valid_day_hours=A["device.valid_day_hours"],
    max_valid_days=A["device.max_valid_days"],
    min_valid_days=A["device.min_valid_days"],
    mv_cutpoint=A["device.mv_cutpoint"],
    purposeful_bout_minutes=A["device.purposeful_bout_minutes"],
)
frames, results = Path(os.environ["OAI_FRAME_DIR"]), Path(os.environ["OAI_RESULTS_DIR"])
waves, rows, metrics = [], [], []
for visit in ("06", "08"):
    daily = daily_summary(read_minutes(visit), rules)
    persons = person_summary(daily, rules).with_columns(pl.lit(visit).alias("wave"))
    waves.append(persons)
    check = reproduction(daily, visit, rules)
    check["valid_persons"] = persons.filter("valid").height
    check["release_valid_persons"] = release_valid_persons(visit, rules.min_valid_days)
    rows.append({"wave": visit, **check})
    metrics += [(f"device.{visit}.{key}", float(value)) for key, value in check.items()]
    print(f"wave {visit}: {check}")
pl.concat(waves).write_parquet(frames / "device.parquet")
pl.DataFrame(rows).write_csv(results / "device_reproduction.csv")
pl.DataFrame(metrics, schema=["metric", "value"], orient="row").write_csv(results / "metrics_device.csv")
```

- [ ] **Step 3: README, ledger and analysis list**

`analyses/walking_validation/README.md`:

```markdown
# walking_validation

Validity of the 96-month walking-for-exercise item, the exposure in Lo et al. 2022 (Arthritis
Rheumatol 74:1660-7), against the OAI accelerometer waves at 48 and 72 months. Includes a
record-level probabilistic bias analysis of the paper's odds ratios.
Spec: [docs/superpowers/specs/2026-10-01-walking-validation-design.md](../../docs/superpowers/specs/2026-10-01-walking-validation-design.md).

| Step | Lang | Output |
|---|---|---|
| `device` | Python | device measures per person and wave (frame); agreement with the release (`device_reproduction.csv`) |
| `cohort` | Python | validation frame, Lo 2022 subset and knee frame (frames); `flow.csv`; Lo Table 2 copies |
| `validity` | R | known groups, dose-response, convergent ranking, Se/Sp, strata, PASE benchmark |
| `bias` | R | probabilistic bias analysis, tipping-point grid, summary-level correction |
| `compare` | Python | `comparison.csv`: device reproduction and sample sizes against `expected.toml` |

Needs the replication's frame for the matching exposure coding:
`oai run lo2022_walking --variant walker_requires_amount` (primary) or `oai run lo2022_walking`
(variant `exposure_replication_coding`). R steps run under the `report` renv profile (`[r]`).
```

Then:

```bash
uv run oai assumptions walking_validation --write
```

In `tests/test_analyses.py`, add `"walking_validation",` as the last item of the list in `test_expected_analyses_exist`. In `analyses/activity_agreement/README.md`, append the line `The walking-item validation (the Lo 2022 exposure) lives in [walking_validation](../walking_validation/README.md).`

- [ ] **Step 4: Run the tests and the device step**

Run: `uv run pytest tests/test_analyses.py tests/test_assumptions_ledgers.py tests/test_manifest.py -q`
Expected: PASS.

Run: `uv run oai run walking_validation --step device`
Expected:
- `wave 06: {'release_days': 13040, 'matched_days': 13040, 'wear_mismatch_days': 33, 'mv_mismatch_days': 0, 'bout_mismatch_days': 0, 'valid_persons': 1928, 'release_valid_persons': 1927}`;
- a matching line for 08 (9,399 days matched; 1,394 against 1,394);
- then `1 step(s) completed: device`.

- [ ] **Step 5: Commit**

```bash
uv run ruff check && uv run ruff format --check
git add analyses/walking_validation analyses/activity_agreement/README.md tests/test_analyses.py
git commit -m "feat(walking_validation): scaffold, assumptions ledger and device step

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: The `cohort` step

**Files:**
- Create: `analyses/walking_validation/wv.py`, `tests/test_walking_validation.py`
- Replace the placeholder: `analyses/walking_validation/build_cohort.py`

**Interfaces:**
- Consumes:
  - `device.parquet` (Task 7);
  - `walker_status`, `walking_answers`, `walking_sessions` and `score_pase` (Task 2);
  - the replication's `frame.parquet` and `assumptions.resolved.json` under `OAI_WORK_DIR/lo2022_walking/<label>/`, and its `comparison.csv` and `table2.csv` under `OAI_RESULTS_DIR/lo2022_walking/<label>/`.
- Produces:
  - **Frame `frame.parquet`, one row per person:**
    - identity and covariates: `ID, walk_item, walker, sessions, amount_level, age, sex, bmi, kl_max0, pain0_any`;
    - device: `n_waves`; the combined `purposeful_min, counts_per_day, light_min, bout_days_per_week`; their `_06` and `_08` versions; `device_walker`;
    - PASE: `pase_walking_06, pase_walking_08, pase_walking_10`;
    - Lo link: `in_lo, lo_walker, new_pain_any, kl_worse_any, jsn_worse_any, improved_pain_any`.
  - **Frame `lo_knees.parquet`:** `ID, SIDE, walker, age, sex, bmi, kl0, new_pain, kl_worse, jsn_worse, improved_pain`.
  - **Frame `lo_model.json`:** `or_unadj, or_adj, corstr, covariates`.
  - **Results:** `flow.csv`, `metrics_cohort.csv`, `lo2022_t2.csv`, `lo2022_table2.csv`.

- [ ] **Step 1: Write the failing tests**

`tests/test_walking_validation.py`:

```python
import json
import sys
from pathlib import Path

import polars as pl
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "analyses" / "walking_validation"))

import wv  # noqa: E402
from wv import CohortError, combine_waves, lo_model, person_outcomes, read_lo_frame  # noqa: E402
from wv import with_amount_level, with_device_walker  # noqa: E402

MEASURE = {"purposeful_min": 0.0, "counts_per_day": 0.0, "light_min": 0.0, "bout_days_per_week": 0.0}


def device_rows(rows):
    return pl.DataFrame([{**MEASURE, **r} for r in rows])


def test_combine_waves_keeps_single_wave_persons():
    device = device_rows(
        [
            {"ID": 1, "wave": "06", "valid": True, "purposeful_min": 10.0},
            {"ID": 1, "wave": "08", "valid": True, "purposeful_min": 20.0},
            {"ID": 2, "wave": "06", "valid": True, "purposeful_min": 5.0},
            {"ID": 3, "wave": "06", "valid": False, "purposeful_min": 99.0},
        ]
    )
    out = combine_waves(device, "mean").sort("ID")
    assert out["ID"].to_list() == [1, 2]
    assert out["n_waves"].to_list() == [2, 1]
    assert out["purposeful_min"].to_list() == [15.0, 5.0]
    assert out["purposeful_min_08"].to_list() == [20.0, None]
    one_wave = combine_waves(device, "08")
    assert one_wave["ID"].to_list() == [1] and one_wave["purposeful_min"].to_list() == [20.0]
    assert "purposeful_min_06" in one_wave.columns
    with pytest.raises(ValueError, match="combination"):
        combine_waves(device, "both")


def test_device_walker_rules():
    df = pl.DataFrame({"bout_days_per_week": [0.0, 1.0, 2.0], "purposeful_min": [0.0, 10.0, 25.0]})
    rule = lambda r: with_device_walker(df, r, 2.0, 150.0)["device_walker"].to_list()  # noqa: E731
    assert rule("bout_days") == [False, False, True]
    assert rule("any_bout") == [False, True, True]
    assert rule("bout_minutes") == [False, False, True]
    with pytest.raises(ValueError, match="walker_rule"):
        rule("steps")


def test_amount_level_median_split():
    df = pl.DataFrame({"walker": [False, True, True, True, True], "sessions": [None, 10.0, 20.0, 30.0, None]})
    assert with_amount_level(df)["amount_level"].to_list() == ["none", "lower", "lower", "upper", None]


def test_person_outcomes_any_knee():
    knees = pl.DataFrame(
        {
            "ID": [1, 1, 2, 3],
            "walker": [True, True, False, True],
            "new_pain": [False, True, None, None],
            "kl_worse": [False, False, True, None],
            "jsn_worse": [None, None, None, None],
            "improved_pain": [None, False, None, True],
        },
        schema_overrides={"jsn_worse": pl.Boolean},
    )
    out = person_outcomes(knees).sort("ID")
    assert out["new_pain_any"].to_list() == [True, None, None]
    assert out["kl_worse_any"].to_list() == [False, True, None]
    assert out["jsn_worse_any"].to_list() == [None, None, None]
    assert out["lo_walker"].to_list() == [True, False, True]


def write_lo(tmp_path, label, coding):
    d = tmp_path / "lo2022_walking" / label
    d.mkdir(parents=True)
    pl.DataFrame({"ID": [1], "walker": [True]}).write_parquet(d / "frame.parquet")
    values = {"exposure.yes_without_amount_as": coding, "model.covariates": ["age", "sex", "kl0"],
              "model.kl_covariate": "factor", "model.corstr": "exchangeable"}
    (d / "assumptions.resolved.json").write_text(
        json.dumps({"assumptions": {k: {"value": v} for k, v in values.items()}})
    )


def test_read_lo_frame_rejects_other_coding(tmp_path):
    write_lo(tmp_path, "default", "walker")
    with pytest.raises(CohortError, match="codes yes-without-amount as 'walker'"):
        read_lo_frame(tmp_path, "default", "non-walker")
    frame, values = read_lo_frame(tmp_path, "default", "walker")
    assert frame.height == 1 and values["model.corstr"] == "exchangeable"


def test_read_lo_frame_names_the_command(tmp_path):
    with pytest.raises(CohortError, match="oai run lo2022_walking --variant walker_requires_amount"):
        read_lo_frame(tmp_path, "walker_requires_amount", "non-walker")


def test_lo_model_mirrors_models_r():
    values = {"model.covariates": ["age", "sex", "kl0"], "model.kl_covariate": "factor", "model.corstr": "exchangeable"}
    assert lo_model(values) == {
        "or_unadj": "walker",
        "or_adj": "walker + age + sex + factor(kl0)",
        "corstr": "exchangeable",
        "covariates": "age,sex,kl0",
    }
```

Run: `uv run pytest tests/test_walking_validation.py -q`
Expected: FAIL at collection with `ModuleNotFoundError: No module named 'wv'`.

- [ ] **Step 2: Implement `analyses/walking_validation/wv.py`**

```python
"""Walking-validation helpers: combine device waves, the device reference, amount levels and the
link to the Lo 2022 replication's knee frame."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from oai.errors import OAIError

MEASURES = ("purposeful_min", "counts_per_day", "light_min", "bout_days_per_week")
OUTCOMES = ("new_pain", "kl_worse", "jsn_worse", "improved_pain")
LO2022 = "lo2022_walking"


class CohortError(OAIError):
    """The Lo 2022 frame needed here is missing or was built with another exposure coding."""


def combine_waves(device: pl.DataFrame, combination: str) -> pl.DataFrame:
    """One row per person over their valid waves: the mean ("mean") or one wave ("06"/"08").

    Also returns each wave's measures as <measure>_06 / <measure>_08 and n_waves.
    """
    if combination not in ("mean", "06", "08"):
        raise ValueError(f"combination must be 'mean', '06' or '08', not {combination!r}")
    valid = device.filter("valid")
    per_wave = valid.select("ID")
    for wave in ("06", "08"):
        one = valid.filter(pl.col("wave") == wave).select(
            "ID", *[pl.col(m).alias(f"{m}_{wave}") for m in MEASURES]
        )
        per_wave = per_wave.join(one, on="ID", how="left")
    per_wave = per_wave.unique("ID")
    used = valid if combination == "mean" else valid.filter(pl.col("wave") == combination)
    combined = used.group_by("ID").agg(
        pl.len().alias("n_waves"), *[pl.col(m).mean() for m in MEASURES]
    )
    return combined.join(per_wave, on="ID", how="left").sort("ID")


def with_device_walker(
    persons: pl.DataFrame, rule: str, min_bout_days: float, min_bout_minutes: float
) -> pl.DataFrame:
    """Add device_walker, the reference standard."""
    rules = {
        "bout_days": pl.col("bout_days_per_week") >= min_bout_days,
        "any_bout": pl.col("bout_days_per_week") > 0,
        "bout_minutes": pl.col("purposeful_min") * 7 >= min_bout_minutes,
    }
    if rule not in rules:
        raise ValueError(f"reference.walker_rule must be one of {', '.join(rules)}, not {rule!r}")
    return persons.with_columns(rules[rule].alias("device_walker"))


def with_amount_level(persons: pl.DataFrame) -> pl.DataFrame:
    """amount_level: 'none' (non-walker), 'lower'/'upper' half of sessions among walkers."""
    median = persons.filter(pl.col("walker") & pl.col("sessions").is_not_null())["sessions"].median()
    level = (
        pl.when(pl.col("walker").is_null())
        .then(pl.lit(None, dtype=pl.String))
        .when(~pl.col("walker"))
        .then(pl.lit("none"))
        .when(pl.col("sessions").is_null())
        .then(pl.lit(None, dtype=pl.String))
        .when(pl.col("sessions") <= median)
        .then(pl.lit("lower"))
        .otherwise(pl.lit("upper"))
    )
    return persons.with_columns(level.alias("amount_level"))


def person_outcomes(knees: pl.DataFrame) -> pl.DataFrame:
    """Per person: lo_walker and <outcome>_any (any knee with the event; null if none observed)."""
    return knees.group_by("ID").agg(
        pl.col("walker").first().alias("lo_walker"),
        *[
            pl.when(pl.col(o).is_not_null().any())
            .then(pl.col(o).fill_null(False).any())
            .alias(f"{o}_any")
            for o in OUTCOMES
        ],
    )


def read_lo_frame(work_dir: Path, label: str, yes_without_amount_as: str) -> tuple[pl.DataFrame, dict]:
    """The replication's knee frame and resolved assumptions for `label`, checked for coding."""
    d = work_dir / LO2022 / label
    frame, resolved = d / "frame.parquet", d / "assumptions.resolved.json"
    if not frame.is_file() or not resolved.is_file():
        command = f"oai run {LO2022}" + ("" if label == "default" else f" --variant {label}")
        raise CohortError(f"no {LO2022} frame for {label!r} in {d}; run `{command}` first")
    values = {k: v["value"] for k, v in json.loads(resolved.read_text())["assumptions"].items()}
    coding = values["exposure.yes_without_amount_as"]
    if coding != yes_without_amount_as:
        raise CohortError(
            f"{LO2022} {label!r} codes yes-without-amount as {coding!r}, but this run uses "
            f"{yes_without_amount_as!r}; set bias.lo2022_label to the matching run"
        )
    return pl.read_parquet(frame), values


def lo_model(values: dict) -> dict[str, str]:
    """The replication's Table 2 model, as models.R builds it."""
    kl_term = "factor(kl0)" if values["model.kl_covariate"] == "factor" else "kl0"
    covariates = [kl_term if c == "kl0" else c for c in values["model.covariates"]]
    return {
        "or_unadj": "walker",
        "or_adj": " + ".join(["walker", *covariates]),
        "corstr": values["model.corstr"],
        "covariates": ",".join(values["model.covariates"]),
    }
```

Run: `uv run pytest tests/test_walking_validation.py -q`
Expected: PASS.

- [ ] **Step 3: Implement `build_cohort.py`**

```python
"""Step `cohort`: the person-level validation frame, the Lo 2022 subset, and its knee frame."""

import json
import os
import shutil
from functools import partial
from pathlib import Path

import polars as pl
from wv import (
    LO2022,
    MEASURES,
    OUTCOMES,
    CohortError,
    combine_waves,
    lo_model,
    person_outcomes,
    read_lo_frame,
    with_amount_level,
    with_device_walker,
)

from oai.assumptions import current
from oai.config import get_settings
from oai.derive.knee import find_col, frequent_knee_pain, xray_readings
from oai.derive.pase import score_pase
from oai.derive.walking import walker_status, walking_answers, walking_sessions
from oai.loader import read_table

A = current()
settings = get_settings()
frames, results = Path(os.environ["OAI_FRAME_DIR"]), Path(os.environ["OAI_RESULTS_DIR"])


def select(df: pl.DataFrame, **columns: str) -> pl.DataFrame:
    col = partial(find_col, df)
    return df.select([pl.col(col(src)).alias(dst) for dst, src in columns.items()])


answered = (
    walking_answers()
    .with_columns(
        walker_status(yes_without_amount_as=A["exposure.yes_without_amount_as"], missing_as="exclude"),
        walking_sessions(A["exposure.category_midpoints"]),
    )
    .filter(pl.col("walker").is_not_null())
)
pase = None
for visit in ("06", "08", "10"):
    scored = score_pase(read_table("allclinical", visit), visit, A["pase.walking_scoring"]).select(
        "ID", pl.col("pase_walking").alias(f"pase_walking_{visit}")
    )
    pase = scored if pase is None else pase.join(scored, on="ID", how="full", coalesce=True)

people = select(read_table("enrollees"), ID="ID", sex="P02SEX").join(
    select(read_table("allclinical", "00"), ID="ID", age="V00AGE", bmi="P01BMI"), on="ID", how="left"
)
kl = (
    xray_readings(["00"], project=A["strata.reading_project"])
    .group_by("ID")
    .agg(pl.col("KL").max().alias("kl_max0"))
)
pain = (
    frequent_knee_pain("00", A["strata.pain_baseline_item"])
    .group_by("ID")
    .agg(
        pl.when(pl.col("frequent_pain").is_not_null().any())
        .then(pl.col("frequent_pain").fill_null(False).any())
        .alias("pain0_any")
    )
)
combined = with_device_walker(
    combine_waves(pl.read_parquet(frames / "device.parquet"), A["device.wave_combination"]),
    A["reference.walker_rule"],
    A["reference.min_bout_days_per_week"],
    A["reference.min_bout_minutes_per_week"],
)

label = A["bias.lo2022_label"]
lo_knees, lo_values = read_lo_frame(settings.work_dir, label, A["exposure.yes_without_amount_as"])
lo_people = person_outcomes(lo_knees).with_columns(pl.lit(True).alias("in_lo"))

persons = (
    answered.join(combined, on="ID", how="inner")
    .join(people, on="ID", how="left")
    .join(kl, on="ID", how="left")
    .join(pain, on="ID", how="left")
    .join(pase, on="ID", how="left")
    .join(lo_people, on="ID", how="left")
    .with_columns(
        pl.col("in_lo").fill_null(False), pl.col("age").cast(pl.Float64), pl.col("bmi").cast(pl.Float64)
    )
)
persons = with_amount_level(persons).sort("ID")
mismatch = persons.filter(pl.col("in_lo") & (pl.col("walker") != pl.col("lo_walker"))).height
if mismatch:
    raise CohortError(f"{mismatch} Lo 2022 participants are coded differently here; check the coding")
persons.write_parquet(frames / "frame.parquet")

covariates = list(lo_values["model.covariates"])
keep = ["ID", "SIDE", "walker", *dict.fromkeys(["age", "sex", "bmi", *covariates]), *OUTCOMES]
lo_knees.select([c for c in keep if c in lo_knees.columns]).write_parquet(frames / "lo_knees.parquet")
(frames / "lo_model.json").write_text(json.dumps(lo_model(lo_values), indent=2))

lo_results = settings.results_dir / LO2022 / label
for name, target in (("comparison.csv", "lo2022_t2.csv"), ("table2.csv", "lo2022_table2.csv")):
    source = lo_results / name
    if not source.is_file():
        raise CohortError(f"{source} is missing; run `oai run {LO2022} --variant {label}` first")
    if name == "comparison.csv":
        pl.read_csv(source).filter(pl.col("metric").str.starts_with("t2.")).write_csv(results / target)
    else:
        shutil.copyfile(source, results / target)

lo_subset = persons.filter("in_lo")
flow = pl.DataFrame(
    [
        {"step": "answered_walking_item", "persons": answered.height},
        {"step": "with_valid_device_wave", "persons": persons.height},
        {"step": "lo2022_cohort", "persons": lo_people.height},
        {"step": "lo2022_with_device", "persons": lo_subset.height},
    ]
)
flow.write_csv(results / "flow.csv")
metrics = [
    ("sample.validation.persons", persons.height),
    ("sample.validation.walkers", persons["walker"].sum()),
    ("sample.validation.device_walkers", persons["device_walker"].sum()),
    ("sample.validation.two_waves", (persons["n_waves"] == 2).sum()),
    ("sample.lo_subset.persons", lo_subset.height),
    ("sample.lo_subset.walkers", lo_subset["walker"].sum()),
    ("sample.lo_subset.device_walkers", lo_subset["device_walker"].sum()),
]
pl.DataFrame([(m, float(v)) for m, v in metrics], schema=["metric", "value"], orient="row").write_csv(
    results / "metrics_cohort.csv"
)
print(flow)
print(f"measures: {', '.join(MEASURES)}; outcomes: {', '.join(OUTCOMES)}")
```

- [ ] **Step 4: Run it**

```bash
uv run oai run lo2022_walking --variant walker_requires_amount > /dev/null
uv run oai run walking_validation --step cohort
```

Expected: the flow table prints `lo2022_with_device` = 784 and `with_valid_device_wave` ≈ 1,566 (±2), then `1 step(s) completed: cohort`.

- [ ] **Step 5: Commit**

```bash
uv run ruff check && uv run ruff format --check && uv run pytest -q
git add analyses/walking_validation/wv.py analyses/walking_validation/build_cohort.py tests/test_walking_validation.py
git commit -m "feat(walking_validation): cohort step (validation frame, Lo 2022 subset and knee frame)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: The `validity` step

**Files:**
- Replace the placeholder: `analyses/walking_validation/validity.R`

**Interfaces:**
- Consumes: `frame.parquet` (Task 8) and the Task 5 helpers.
- Produces:
  - `validity_known_groups.csv` (`sample, measure, n_walkers, n_nonwalkers, median_walkers, q25_walkers, q75_walkers, median_nonwalkers, q25_nonwalkers, q75_nonwalkers, hl, hl_lo, hl_hi, rank_biserial, adj_diff, adj_lo, adj_hi`);
  - `validity_dose.csv`;
  - `validity_convergent.csv`;
  - `validity_classification.csv` (`sample, measure, estimate, lo, hi, k, n`; the measures include `auc`);
  - `validity_strata.csv` (`sample, variable, stratum, measure, estimate, lo, hi, k, n, p_differs`);
  - `validity_pase.csv`;
  - `metrics_validity.csv`.

- [ ] **Step 1: Write `validity.R`**

```r
# Step `validity`: does the walking item rank and classify people like the device? (spec 6)
A <- oaimodels::assumptions()
persons <- oaimodels::read_frame(required = c(
  "ID", "walker", "amount_level", "sessions", "device_walker", "in_lo", "n_waves", "age", "sex",
  "bmi", "kl_max0", "pain0_any", "purposeful_min", "counts_per_day", "light_min"
))
out_dir <- Sys.getenv("OAI_RESULTS_DIR")
measures <- c("purposeful_min", "counts_per_day", "light_min")
outcomes <- c("new_pain", "kl_worse", "jsn_worse", "improved_pain")
reps <- A[["validity.bootstrap_reps"]]
perms <- A[["validity.jt_permutations"]]
seed <- A[["bias.seed"]]
adjust <- "age + sex + bmi"
levels_amount <- c("none", "lower", "upper")
samples <- list(validation = rep(TRUE, nrow(persons)), lo_subset = persons$in_lo)
q <- function(x, p) unname(stats::quantile(x, p, na.rm = TRUE))
bind <- function(rows) do.call(rbind, rows)

known <- list(); dose <- list(); convergent <- list(); classes <- list(); strata <- list()
for (sample in names(samples)) {
  d <- persons[samples[[sample]], ]
  for (m in measures) {
    w <- d[[m]][d$walker]
    nw <- d[[m]][!d$walker]
    hl <- oaimodels::hodges_lehmann(w, nw)
    adj <- oaimodels::median_regression(stats::as.formula(paste(m, "~ walker +", adjust)), d, "walkerTRUE")
    known[[length(known) + 1]] <- data.frame(
      sample = sample, measure = m, n_walkers = sum(!is.na(w)), n_nonwalkers = sum(!is.na(nw)),
      median_walkers = q(w, 0.5), q25_walkers = q(w, 0.25), q75_walkers = q(w, 0.75),
      median_nonwalkers = q(nw, 0.5), q25_nonwalkers = q(nw, 0.25), q75_nonwalkers = q(nw, 0.75),
      hl = hl[["estimate"]], hl_lo = hl[["lo"]], hl_hi = hl[["hi"]],
      rank_biserial = oaimodels::rank_biserial(w, nw),
      adj_diff = adj[["estimate"]], adj_lo = adj[["lo"]], adj_hi = adj[["hi"]]
    )
    level <- factor(d$amount_level, levels = levels_amount)
    jt <- oaimodels::jonckheere(d[[m]], level, permutations = perms, seed = seed)
    dd <- d[!is.na(level), ]
    dd$amount_level <- factor(dd$amount_level, levels = levels_amount)
    form <- stats::as.formula(paste(m, "~ amount_level +", adjust))
    lower <- oaimodels::median_regression(form, dd, "amount_levellower")
    upper <- oaimodels::median_regression(form, dd, "amount_levelupper")
    dose[[length(dose) + 1]] <- data.frame(
      sample = sample, measure = m,
      median_none = q(d[[m]][level %in% "none"], 0.5), median_lower = q(d[[m]][level %in% "lower"], 0.5),
      median_upper = q(d[[m]][level %in% "upper"], 0.5), jt = jt[["statistic"]], jt_p = jt[["p"]],
      adj_lower = lower[["estimate"]], adj_lower_lo = lower[["lo"]], adj_lower_hi = lower[["hi"]],
      adj_upper = upper[["estimate"]], adj_upper_lo = upper[["lo"]], adj_upper_hi = upper[["hi"]]
    )
    walkers <- d[d$walker & !is.na(d$sessions), ]
    rho <- oaimodels::spearman_ci(walkers$sessions, walkers[[m]])
    a <- persons[[paste0(m, "_06")]]
    b <- persons[[paste0(m, "_08")]]
    both <- !is.na(a) & !is.na(b)
    r_waves <- stats::cor(a[both], b[both], method = "spearman")
    reliability <- oaimodels::wave_reliability(r_waves, mean(walkers$n_waves == 2))
    convergent[[length(convergent) + 1]] <- data.frame(
      sample = sample, measure = m, n = rho[["n"]], rho = rho[["rho"]], lo = rho[["lo"]], hi = rho[["hi"]],
      between_wave_rho = r_waves, n_both_waves = sum(both), reliability = reliability,
      rho_deattenuated = oaimodels::deattenuate(rho[["rho"]], reliability_y = reliability)
    )
  }
  cl <- oaimodels::classification(d$walker, d$device_walker)
  auc <- oaimodels::auc_ci(ifelse(d$walker, d$sessions, 0), d$device_walker, reps = reps, seed = seed)
  cl <- rbind(cl, data.frame(measure = "auc", estimate = auc[["estimate"]], lo = auc[["lo"]],
                             hi = auc[["hi"]], k = NA, n = sum(!is.na(d$device_walker))))
  cl$sample <- sample
  classes[[length(classes) + 1]] <- cl
  by <- list(
    kl = as.character(cut(d$kl_max0, c(-Inf, 1, 2, Inf), labels = c("KL 0-1", "KL 2", "KL 3-4"))),
    pain = ifelse(d$pain0_any, "frequent pain", "no frequent pain")
  )
  if (sample == "lo_subset") {
    for (o in outcomes) by[[o]] <- ifelse(d[[paste0(o, "_any")]], "event", "no event")
  }
  for (v in names(by)) {
    s <- oaimodels::classification_by_stratum(d$walker, d$device_walker, by[[v]])
    s$sample <- sample
    s$variable <- v
    strata[[length(strata) + 1]] <- s
  }
}

pase <- list()
for (visit in c("06", "08", "10")) {
  p <- persons[[paste0("pase_walking_", visit)]]
  for (m in measures) {
    rho <- oaimodels::spearman_ci(p, persons[[m]])
    pase[[length(pase) + 1]] <- data.frame(visit = visit, measure = m, statistic = "rho",
                                           estimate = rho[["rho"]], lo = rho[["lo"]], hi = rho[["hi"]], n = rho[["n"]])
  }
  cl <- oaimodels::classification(p > 0, persons$device_walker)
  cl <- cl[cl$measure %in% c("se", "sp"), ]
  pase[[length(pase) + 1]] <- data.frame(visit = visit, measure = "device_walker", statistic = cl$measure,
                                         estimate = cl$estimate, lo = cl$lo, hi = cl$hi, n = cl$n)
}

classification_all <- bind(classes)
validation <- classification_all[classification_all$sample == "validation", ]
lo_subset <- classification_all[classification_all$sample == "lo_subset", ]
metrics <- data.frame(
  metric = c("validity.validation.se", "validity.validation.sp", "validity.validation.auc",
             "validity.lo_subset.se", "validity.lo_subset.sp"),
  value = c(validation$estimate[validation$measure == "se"], validation$estimate[validation$measure == "sp"],
            validation$estimate[validation$measure == "auc"], lo_subset$estimate[lo_subset$measure == "se"],
            lo_subset$estimate[lo_subset$measure == "sp"])
)
write <- function(df, name) utils::write.csv(df, file.path(out_dir, name), row.names = FALSE)
write(bind(known), "validity_known_groups.csv")
write(bind(dose), "validity_dose.csv")
write(bind(convergent), "validity_convergent.csv")
write(classification_all, "validity_classification.csv")
write(bind(strata), "validity_strata.csv")
write(bind(pase), "validity_pase.csv")
write(metrics, "metrics_validity.csv")
print(metrics)
```

- [ ] **Step 2: Run it**

Run: `uv run oai run walking_validation --step validity`
Expected:
- it prints `metrics`, with Se and Sp between 0 and 1 and an AUC between 0.5 and 1;
- `1 step(s) completed: validity`;
- all seven CSVs exist in the run's results folder.

Then check that each file has rows and no numeric column is entirely NA:

```bash
RES="$(uv run python -c 'from oai.config import get_settings; print(get_settings().results_dir / "walking_validation/default")')"
for f in $RES/validity_*.csv; do echo "$(basename $f): $(($(wc -l < $f) - 1)) rows"; done
```

Expected row counts:
- `validity_known_groups.csv` and `validity_dose.csv`: 6 each;
- `validity_convergent.csv`: 6;
- `validity_classification.csv`: 10;
- `validity_pase.csv`: 15 (3 visits × (3 ρ + 2 Se/Sp)).

- [ ] **Step 3: Commit**

```bash
git add analyses/walking_validation/validity.R
git commit -m "feat(walking_validation): validity step (known groups, dose, ranking, Se/Sp, strata, PASE)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: The `bias` and `compare` steps, and an end-to-end real-data test

**Files:**
- Replace the placeholders: `analyses/walking_validation/bias.R`, `analyses/walking_validation/compare.py`
- Create: `tests/test_walking_validation_realdata.py`

**Interfaces:**
- Consumes: `frame.parquet`, `lo_knees.parquet`, `lo_model.json`, `lo2022_t2.csv`, `lo2022_table2.csv` (Task 8); the Task 3 and Task 6 R functions; `oaireport::parse_or`.
- Produces:
  - `bias_priors.csv`;
  - `bias_pba.csv` (`outcome, model, scenario, observed_or, published_or, or, lo_sys, hi_sys, lo_total, hi_total, conclusion_share, discarded, n, flagged`);
  - `bias_tipping.csv` (`outcome, se, sp, or, lo, hi, excludes_1, discarded`);
  - `bias_summary_level.csv`;
  - `metrics_bias.csv`;
  - `comparison.csv`.

- [ ] **Step 1: Write the real-data test first**

`tests/test_walking_validation_realdata.py`:

```python
"""End-to-end walking_validation on the real release (short bias-analysis settings)."""

import os
import shutil
import subprocess
from pathlib import Path

import polars as pl
import pytest

from oai.config import get_settings
from oai.export.egress import check_egress
from oai.manifest import find_analysis
from oai.runner import run_analysis

REPO = Path(__file__).resolve().parents[1]


def _ready() -> bool:
    if shutil.which("Rscript") is None:
        return False
    probe = subprocess.run(
        ["Rscript", "-e", "library(quantreg); library(geepack); library(ggplot2)"],
        cwd=REPO / "r",
        capture_output=True,
        env={**os.environ, "RENV_PROFILE": "report"},
    )
    return probe.returncode == 0


@pytest.mark.realdata
@pytest.mark.skipif(not _ready(), reason="R report profile with quantreg/geepack is unavailable")
def test_walking_validation_end_to_end():
    settings = get_settings()
    quiet = lambda _: None  # noqa: E731
    run_analysis(find_analysis("lo2022_walking", settings.analyses_dir), settings,
                 variant="walker_requires_amount", echo=quiet)
    analysis = find_analysis("walking_validation", settings.analyses_dir)
    fast = {"bias.iterations": 40, "bias.tipping_iterations": 4, "bias.tipping_step": 0.2,
            "validity.bootstrap_reps": 50, "validity.jt_permutations": 99}
    run_analysis(analysis, settings, overrides=fast, echo=quiet)
    out = next((settings.results_dir / "walking_validation").glob("default+custom-*"))
    comparison = pl.read_csv(out / "comparison.csv")
    device = comparison.filter(pl.col("metric").str.starts_with("device."))
    assert (device["verdict"] == "replicated").all(), device
    pba = pl.read_csv(out / "bias_pba.csv")
    assert pba.height == 4 * 2 * 2
    assert pba["or"].is_not_null().all()
    egress = settings.project["egress"]
    report = check_egress(out, min_cell=egress["min_cell"], small_cell=egress["small_cell"],
                          ignore_id_pattern_columns=egress["ignore_id_pattern_columns"])
    assert report.ok, report.problems
```

Run: `uv run pytest tests/test_walking_validation_realdata.py -m realdata -q`
Expected: FAIL with `RunnerError: step 'bias' failed with exit code 1`; the placeholder prints `bias step: implemented in Task 10`.

- [ ] **Step 2: Write `bias.R`**

```r
# Step `bias`: how far could misclassification of the walking item move Lo 2022's odds ratios?
# (spec 7). Refits the replication's own models on reclassified exposure.
A <- oaimodels::assumptions()
frames <- Sys.getenv("OAI_FRAME_DIR")
out_dir <- Sys.getenv("OAI_RESULTS_DIR")
persons <- oaimodels::read_frame(required = c("ID", "walker", "device_walker", "in_lo"))
knees_all <- oaimodels::read_frame(file.path(frames, "lo_knees.parquet"), required = c("ID", "walker"))
model <- jsonlite::fromJSON(file.path(frames, "lo_model.json"))
published <- utils::read.csv(file.path(out_dir, "lo2022_t2.csv"), na.strings = c("", "NA"))
replicated <- utils::read.csv(file.path(out_dir, "lo2022_table2.csv"))
outcomes <- c("new_pain", "kl_worse", "jsn_worse", "improved_pain")
models <- c(or_unadj = model$or_unadj, or_adj = model$or_adj)
base_covariates <- strsplit(model$covariates, ",")[[1]]
cores <- as.integer(Sys.getenv("OAI_R_CORES", max(1L, parallel::detectCores() - 1L)))
iterations <- A[["bias.iterations"]]
seed <- A[["bias.seed"]]
validated <- persons[persons$in_lo & !is.na(persons$device_walker), ]

prior_row <- function(d, stratum) {
  se_k <- sum(d$walker & d$device_walker)
  se_n <- sum(d$device_walker)
  sp_k <- sum(!d$walker & !d$device_walker)
  sp_n <- sum(!d$device_walker)
  se <- oaimodels::beta_shapes(se_k, se_n)
  sp <- oaimodels::beta_shapes(sp_k, sp_n)
  data.frame(stratum = stratum, se1 = se[["shape1"]], se2 = se[["shape2"]], sp1 = sp[["shape1"]],
             sp2 = sp[["shape2"]], se_k = se_k, se_n = se_n, sp_k = sp_k, sp_n = sp_n)
}

knee_data <- function(o) {  # exactly as lo2022_walking/models.R prepares it
  d <- knees_all[!is.na(knees_all[[o]]), unique(c("ID", "walker", base_covariates, o))]
  names(d)[names(d) == o] <- "y"
  d$y <- as.integer(d$y)
  d <- d[stats::complete.cases(d), ]
  d[order(d$ID), ]
}

pba_rows <- list(); prior_rows <- list(); tipping_rows <- list(); summary_rows <- list()
for (o in outcomes) {
  k <- knee_data(o)
  first <- !duplicated(k$ID)
  person <- data.frame(ID = k$ID[first], observed = k$walker[first])
  person$stratum <- ifelse(person$ID %in% k$ID[k$y == 1], "case", "noncase")
  v <- validated[!is.na(validated[[paste0(o, "_any")]]), ]
  nondiff <- prior_row(v, "all")
  diff <- rbind(prior_row(v[v[[paste0(o, "_any")]], ], "case"),
                prior_row(v[!v[[paste0(o, "_any")]], ], "noncase"))
  prior_rows[[length(prior_rows) + 1]] <- rbind(
    cbind(outcome = o, scenario = "non-differential", nondiff),
    cbind(outcome = o, scenario = "differential", diff)
  )
  for (m in names(models)) {
    fit <- function(kn) oaimodels::fit_knee_gee(kn, models[[m]], corstr = model$corstr)[c("log_or", "se")]
    observed <- oaimodels::fit_knee_gee(k, models[[m]], corstr = model$corstr)
    rep_or <- replicated$or[replicated$outcome == o & replicated$model == m]
    if (length(rep_or) != 1 || abs(observed[["or"]] - rep_or) > 1e-8) {
      stop("bias step does not reproduce the replication's ", o, " ", m, " odds ratio", call. = FALSE)
    }
    pub <- oaireport::parse_or(published$published[published$metric == paste0("t2.", o, ".", m)])
    for (scenario in c("non-differential", "differential")) {
      priors <- if (scenario == "differential") diff else nondiff
      draws <- oaimodels::pba(person, k, fit, priors, differential = scenario == "differential",
                              iterations = iterations, seed = seed, cores = cores)
      s <- oaimodels::summarise_pba(draws, direction = sign(log(pub$or)), significant = pub$sig)
      pba_rows[[length(pba_rows) + 1]] <- data.frame(
        outcome = o, model = m, scenario = scenario, observed_or = observed[["or"]],
        published_or = pub$or, s, flagged = s$discarded > A[["bias.max_discard_share"]]
      )
    }
  }
  fit_adj <- function(kn) oaimodels::fit_knee_gee(kn, models[["or_adj"]], corstr = model$corstr)[c("log_or", "se")]
  step <- A[["bias.tipping_step"]]
  grid <- expand.grid(se = round(seq(0.6, 1, by = step), 6), sp = round(seq(0.4, 1, by = step), 6))
  for (g in seq_len(nrow(grid))) {
    draws <- oaimodels::pba(person, k, fit_adj, data.frame(stratum = "all", se = grid$se[g], sp = grid$sp[g]),
                            iterations = A[["bias.tipping_iterations"]], seed = seed, cores = cores)
    s <- oaimodels::summarise_pba(draws)
    tipping_rows[[length(tipping_rows) + 1]] <- data.frame(
      outcome = o, se = grid$se[g], sp = grid$sp[g], or = s$or, lo = s$lo_total, hi = s$hi_total,
      excludes_1 = !is.na(s$or) & (s$hi_total < 1 | s$lo_total > 1), discarded = s$discarded
    )
  }
  count <- function(group, what) {
    as.numeric(published$published[published$metric == sprintf("t2.%s.%s.%s", o, group, what)])
  }
  a <- count("walkers", "events")
  b <- count("nonwalkers", "events")
  c0 <- count("walkers", "n") - a
  d0 <- count("nonwalkers", "n") - b
  for (scenario in c("non-differential", "differential")) {
    set.seed(seed)
    ors <- replicate(iterations, {
      if (scenario == "non-differential") {
        se <- stats::rbeta(1, nondiff$se1, nondiff$se2)
        sp <- stats::rbeta(1, nondiff$sp1, nondiff$sp2)
        oaimodels::correct_or_2x2(a, b, c0, d0, se, sp)
      } else {
        oaimodels::correct_or_2x2(
          a, b, c0, d0,
          se_case = stats::rbeta(1, diff$se1[1], diff$se2[1]), sp_case = stats::rbeta(1, diff$sp1[1], diff$sp2[1]),
          se_ctrl = stats::rbeta(1, diff$se1[2], diff$se2[2]), sp_ctrl = stats::rbeta(1, diff$sp1[2], diff$sp2[2])
        )
      }
    })
    kept <- ors[!is.na(ors)]
    summary_rows[[length(summary_rows) + 1]] <- data.frame(
      outcome = o, scenario = scenario, crude_or = (a * d0) / (b * c0),
      or = if (length(kept)) stats::median(kept) else NA_real_,
      lo = if (length(kept)) unname(stats::quantile(kept, 0.025)) else NA_real_,
      hi = if (length(kept)) unname(stats::quantile(kept, 0.975)) else NA_real_,
      discarded = mean(is.na(ors))
    )
  }
}

pba_all <- do.call(rbind, pba_rows)
write <- function(df, name) utils::write.csv(df, file.path(out_dir, name), row.names = FALSE)
write(do.call(rbind, prior_rows), "bias_priors.csv")
write(pba_all, "bias_pba.csv")
write(do.call(rbind, tipping_rows), "bias_tipping.csv")
write(do.call(rbind, summary_rows), "bias_summary_level.csv")
write(data.frame(metric = sprintf("bias.%s.%s.%s.or", pba_all$outcome, pba_all$model,
                                  ifelse(pba_all$scenario == "differential", "diff", "nondiff")),
                 value = pba_all$or), "metrics_bias.csv")
print(pba_all[, c("outcome", "model", "scenario", "observed_or", "or", "lo_total", "hi_total", "conclusion_share")])
```

- [ ] **Step 3: Write `compare.py`**

```python
"""Step `compare`: grade device reproduction and sample sizes against expected.toml."""

import os
import tomllib
from pathlib import Path

import polars as pl

from oai.assumptions import current, load_assumptions
from oai.replication import grade, select_section, summarize

A = current()
results = Path(os.environ["OAI_RESULTS_DIR"])
expected = tomllib.loads(Path("expected.toml").read_text())
variant_sets = {name: v.set for name, v in load_assumptions(Path.cwd()).variants.items()}
section = select_section(expected, A.variant, A.values, variant_sets)
ours: dict[str, float] = {}
for path in sorted(results.glob("metrics_*.csv")):
    for metric, value in pl.read_csv(path, null_values=["NA"]).iter_rows():
        if value is not None:
            ours[metric] = float(value)
statuses = {key: item.status for key, item in A.items.items()}
table = grade(expected[section], ours, expected.get("related", {}), statuses)
table.write_csv(results / "comparison.csv")
print(summarize(table, section=section, label=A.label))
```

- [ ] **Step 4: Run the real-data test, then the full analysis**

Run: `uv run pytest tests/test_walking_validation_realdata.py -m realdata -q`
Expected: PASS, in a few minutes with the short settings.

Run (full settings; about 15 minutes on 10 cores): `time uv run oai run walking_validation`
Expected:
- all 5 steps complete;
- the bias step prints 16 rows. With perfect-classification sanity in mind, each `observed_or` matches the replication's `walker_requires_amount` `table2.csv` ORs;
- `compare` prints `10 replicated · 0 drift · 0 missing`, or within tolerance on the two sample sizes.

- [ ] **Step 5: Commit**

```bash
uv run ruff check && uv run ruff format --check && uv run pytest -q
git add analyses/walking_validation/bias.R analyses/walking_validation/compare.py tests/test_walking_validation_realdata.py
git commit -m "feat(walking_validation): probabilistic bias analysis of Lo 2022 and comparison step

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: The report

**Files:**
- Create: `analyses/walking_validation/report.qmd`
- Modify: `analyses/walking_validation/analysis.toml` (add `[report]`)

**Interfaces:**
- Consumes:
  - every results CSV from Tasks 7–10, through `oaireport::load_results()`, where CSVs are keyed by file stem;
  - `oaireport` figures and tables.
- Produces:
  - `report.pdf`;
  - figures `known_groups`, `strata`, `forest_bias`, `tipping` (PDF and PNG).

- [ ] **Step 1: Add the `[report]` section**

Append to `analyses/walking_validation/analysis.toml`:

```toml
[report]
entry = "report.qmd"
runs = ["default"]
assets = ["ASSUMPTIONS.md"]
```

- [ ] **Step 2: Write `report.qmd`**

````markdown
---
title: "Walking for exercise: validity of the OAI item against accelerometry"
subtitle: "The Lo et al. 2022 exposure, with a probabilistic bias analysis"
date: today
mainfont: Arial
fontsize: 10pt
format:
  typst:
    papersize: us-letter
    margin:
      x: 0.9in
      y: 0.9in
execute:
  echo: false
  warning: false
  message: false
knitr:
  opts_chunk:
    dev: cairo_pdf
    fig-width: 7
---

```{r setup}
run <- oaireport::load_results()$default
num <- function(x, digits = 2) formatC(x, format = "f", digits = digits, big.mark = ",")
count <- function(x) formatC(x, format = "d", big.mark = ",")
named <- function(key, map) ifelse(key %in% names(map), map[key], key)
measure_names <- c(purposeful_min = "Purposeful-bout min/day", counts_per_day = "Counts/day",
                   light_min = "Light min/day")
outcome_names <- c(new_pain = "New frequent knee pain", kl_worse = "KL grade worsening",
                   jsn_worse = "Medial JSN worsening", improved_pain = "Resolution of frequent knee pain")
model_names <- c(or_unadj = "Unadjusted", or_adj = "Adjusted")
cls <- run$validity_classification
pick <- function(sample, measure, col = "estimate") cls[[col]][cls$sample == sample & cls$measure == measure]
pba <- run$bias_pba
headline <- pba[pba$outcome == "new_pain" & pba$model == "or_adj" & pba$scenario == "differential", ]
info <- run$run_info
code_version <- paste0("oai-analytics ", info$oai_version,
                       if (is.null(info$git_commit)) "" else paste0(", commit ", substr(info$git_commit, 1, 7)))
versions <- unlist(info$data_versions)
data_release <- if (length(versions)) paste(sprintf("%s %s", names(versions), versions), collapse = ", ") else "not recorded"
```

```{=typst}
#show table: set text(size: 8.5pt, hyphenate: false)
#show table: set par(justify: false)
```

# Summary

The exposure in Lo et al. 2022 is the 96-month survey item "walked for exercise since age 50". We compared it with OAI accelerometry from the 48- and 72-month waves in `r count(run$metrics[["sample.validation.persons"]])` participants, `r count(run$metrics[["sample.lo_subset.persons"]])` of them from the paper's cohort. The device is an imperfect reference: it measures current activity, while the item asks about walking since age 50. Sensitivity and specificity are therefore convergent-validity estimates. Data: the OAI public release; input table versions `r data_release`. Code: `r code_version`.

**Headline.** Against the device-defined habitual walker, the item's sensitivity is `r num(pick("validation", "se"))` (95% CI `r num(pick("validation", "se", "lo"))`–`r num(pick("validation", "se", "hi"))`) and its specificity is `r num(pick("validation", "sp"))` (`r num(pick("validation", "sp", "lo"))`–`r num(pick("validation", "sp", "hi"))`). Allowing for differential misclassification, the adjusted odds ratio for new frequent knee pain moves from `r num(headline$observed_or)` to `r num(headline$or)` (95% simulation interval `r num(headline$lo_total)`–`r num(headline$hi_total)`). The published conclusion holds in `r num(100 * headline$conclusion_share, 0)`% of iterations.

# Samples and device processing

```{r samples}
oaireport::compare_table(data.frame(Step = run$flow$step, Participants = count(run$flow$persons)),
                         widths = c(4, 1.5))
```

Our processing of the minute data reproduces the release's own day-level files:

```{r reproduction}
r <- run$device_reproduction
oaireport::compare_table(data.frame(
  Wave = ifelse(r$wave == "06", "48 months", "72 months"), `Release days` = count(r$release_days),
  Matched = count(r$matched_days), `Wear differs` = count(r$wear_mismatch_days),
  `MV differs` = count(r$mv_mismatch_days), `Bout differs` = count(r$bout_mismatch_days),
  `Valid persons (ours / release)` = sprintf("%s / %s", count(r$valid_persons), count(r$release_valid_persons)),
  check.names = FALSE), widths = c(1.4, 1.2, 1, 1.1, 1, 1, 2))
```

# Known groups and dose–response

```{r known-groups-figure}
#| fig-height: 3.2
kg <- run$validity_known_groups
kg <- kg[kg$sample == "validation", ]
long <- rbind(
  data.frame(measure = kg$measure, group = "Walkers", median = kg$median_walkers, q25 = kg$q25_walkers, q75 = kg$q75_walkers),
  data.frame(measure = kg$measure, group = "Non-walkers", median = kg$median_nonwalkers, q25 = kg$q25_nonwalkers, q75 = kg$q75_nonwalkers)
)
long$measure <- named(long$measure, measure_names)
kg_plot <- ggplot2::ggplot(long, ggplot2::aes(x = median, y = group, colour = group)) +
  ggplot2::geom_pointrange(ggplot2::aes(xmin = q25, xmax = q75), size = 0.3, linewidth = 0.6) +
  ggplot2::facet_wrap(~measure, scales = "free_x") +
  ggplot2::scale_colour_manual(values = oaireport::oai_palette[1:2], guide = "none") +
  ggplot2::labs(x = "Median (interquartile range)", y = NULL) + oaireport::theme_oai()
oaireport::save_figure(kg_plot, "known_groups", "2col", height = 3.2)
kg_plot
```

```{r known-groups-table}
all_kg <- run$validity_known_groups
oaireport::compare_table(data.frame(
  Sample = all_kg$sample, Measure = named(all_kg$measure, measure_names),
  `Walkers, median` = num(all_kg$median_walkers), `Non-walkers, median` = num(all_kg$median_nonwalkers),
  `Hodges–Lehmann (95% CI)` = sprintf("%s (%s to %s)", num(all_kg$hl), num(all_kg$hl_lo), num(all_kg$hl_hi)),
  `Rank-biserial` = num(all_kg$rank_biserial),
  `Adjusted median difference` = sprintf("%s (%s to %s)", num(all_kg$adj_diff), num(all_kg$adj_lo), num(all_kg$adj_hi)),
  check.names = FALSE), widths = c(1.4, 2, 1.1, 1.1, 2, 1, 2))
```

```{r dose-table}
dz <- run$validity_dose
oaireport::compare_table(data.frame(
  Sample = dz$sample, Measure = named(dz$measure, measure_names), None = num(dz$median_none),
  Lower = num(dz$median_lower), Upper = num(dz$median_upper),
  `Trend p (JT)` = formatC(dz$jt_p, format = "g", digits = 2),
  `Upper vs none, adjusted` = sprintf("%s (%s to %s)", num(dz$adj_upper), num(dz$adj_upper_lo), num(dz$adj_upper_hi)),
  check.names = FALSE), widths = c(1.4, 2, 1, 1, 1, 1.1, 2.2))
```

# Convergent ranking

```{r convergent}
cv <- run$validity_convergent
oaireport::compare_table(data.frame(
  Sample = cv$sample, Measure = named(cv$measure, measure_names), n = count(cv$n),
  `Spearman ρ (95% CI)` = sprintf("%s (%s to %s)", num(cv$rho), num(cv$lo), num(cv$hi)),
  `Between-wave ρ` = num(cv$between_wave_rho), `Deattenuated ρ` = num(cv$rho_deattenuated),
  check.names = FALSE), widths = c(1.4, 2, 0.8, 2, 1.2, 1.2))
```

# Classification and differential misclassification

```{r classification}
oaireport::compare_table(data.frame(
  Sample = cls$sample, Measure = toupper(cls$measure), Estimate = num(cls$estimate),
  `95% CI` = sprintf("%s–%s", num(cls$lo), num(cls$hi)),
  `k / n` = ifelse(is.na(cls$k), count(cls$n), sprintf("%s / %s", count(cls$k), count(cls$n))),
  check.names = FALSE), widths = c(1.4, 1, 1, 1.4, 1.4))
```

```{r strata-figure}
#| fig-height: 4.6
st <- run$validity_strata
st$label <- sprintf("%s: %s", st$variable, st$stratum)
st$measure <- ifelse(st$measure == "se", "Sensitivity", "Specificity")
st_plot <- ggplot2::ggplot(st, ggplot2::aes(x = estimate, y = label, colour = sample, shape = sample)) +
  ggplot2::geom_pointrange(ggplot2::aes(xmin = lo, xmax = hi), size = 0.25, linewidth = 0.5,
                           position = ggplot2::position_dodge(width = 0.5)) +
  ggplot2::facet_wrap(~measure) + ggplot2::scale_x_continuous(limits = c(0, 1)) +
  ggplot2::scale_colour_manual(values = oaireport::oai_palette[1:2]) +
  ggplot2::labs(x = "Estimate (95% CI)", y = NULL) + oaireport::theme_oai()
oaireport::save_figure(st_plot, "strata", "2col", height = 4.6)
st_plot
```

# PASE walking subscore (benchmark)

```{r pase}
pz <- run$validity_pase
oaireport::compare_table(data.frame(
  Visit = pz$visit, Against = named(pz$measure, c(measure_names, device_walker = "Device walker")),
  Statistic = toupper(pz$statistic), Estimate = num(pz$estimate),
  `95% CI` = sprintf("%s–%s", num(pz$lo), num(pz$hi)), n = count(pz$n), check.names = FALSE),
  widths = c(0.8, 2, 1, 1, 1.4, 0.9))
```

# Bias analysis of Lo 2022

Each panel shows the published odds ratio, our replication, and the median bias-adjusted odds ratio with its 95% simulation interval (systematic plus random error).

```{r forest-bias}
#| fig-height: 4.4
lo_or <- run$lo2022_t2[run$lo2022_t2$kind == "or", ]
parts <- do.call(rbind, strsplit(sub("^t2\\.", "", lo_or$metric), ".", fixed = TRUE))
pub <- oaireport::parse_or(lo_or$published)
ours <- oaireport::parse_or(lo_or$ours)
base <- data.frame(outcome = unname(outcome_names[parts[, 1]]), model = unname(model_names[parts[, 2]]))
est <- rbind(
  cbind(base, source = "Published", or = pub$or, lo = pub$lo, hi = pub$hi),
  cbind(base, source = "Replication", or = ours$or, lo = ours$lo, hi = ours$hi),
  data.frame(outcome = unname(outcome_names[pba$outcome]), model = unname(model_names[pba$model]),
             source = ifelse(pba$scenario == "differential", "Bias-adjusted (differential)",
                             "Bias-adjusted (non-differential)"),
             or = pba$or, lo = pba$lo_total, hi = pba$hi_total)
)
est <- est[order(match(est$model, model_names), match(est$outcome, outcome_names)), ]
sources <- c("Published", "Replication", "Bias-adjusted (non-differential)", "Bias-adjusted (differential)")
forest <- oaireport::forest_plot(est, facet = "model", sources = sources)
oaireport::save_figure(forest, "forest_bias", "2col", height = 4.4)
forest
```

```{r bias-table}
oaireport::compare_table(data.frame(
  Outcome = named(pba$outcome, outcome_names), Model = named(pba$model, model_names), Scenario = pba$scenario,
  Observed = num(pba$observed_or), `Bias-adjusted (95% SI)` = sprintf("%s (%s–%s)", num(pba$or), num(pba$lo_total), num(pba$hi_total)),
  `Conclusion holds` = sprintf("%s%%", num(100 * pba$conclusion_share, 0)), Discarded = sprintf("%s%%", num(100 * pba$discarded, 1)),
  check.names = FALSE), widths = c(2.4, 1.1, 1.6, 1, 2, 1.2, 1.1))
```

The tipping-point grid shows each adjusted odds ratio under fixed, non-differential sensitivity and specificity. Shaded cells keep an interval that excludes 1.

```{r tipping}
#| fig-height: 5.6
tp <- run$bias_tipping
tp$outcome <- factor(named(tp$outcome, outcome_names), levels = outcome_names)
tp$label <- ifelse(is.na(tp$or), "–", num(tp$or))
tip <- ggplot2::ggplot(tp, ggplot2::aes(x = factor(sp), y = factor(se), fill = excludes_1)) +
  ggplot2::geom_tile(colour = "white", linewidth = 0.4) +
  ggplot2::geom_text(ggplot2::aes(label = label), size = 1.9, family = oaireport::oai_font(), colour = "grey10") +
  ggplot2::scale_fill_manual(values = c(`TRUE` = "#cde2fb", `FALSE` = "grey92"),
                             labels = c(`TRUE` = "Interval excludes 1", `FALSE` = "Includes 1")) +
  ggplot2::facet_wrap(~outcome, ncol = 2) +
  ggplot2::labs(x = "Specificity", y = "Sensitivity") + oaireport::theme_oai() +
  ggplot2::theme(axis.text.x = ggplot2::element_text(angle = 90, vjust = 0.5))
oaireport::save_figure(tip, "tipping", "2col", height = 5.6)
tip
```

```{r summary-level}
sl <- run$bias_summary_level
oaireport::compare_table(data.frame(
  Outcome = named(sl$outcome, outcome_names), Scenario = sl$scenario, `Crude OR` = num(sl$crude_or),
  `Corrected (95% SI)` = sprintf("%s (%s–%s)", num(sl$or), num(sl$lo), num(sl$hi)),
  Discarded = sprintf("%s%%", num(100 * sl$discarded, 1)), check.names = FALSE),
  widths = c(2.6, 1.8, 1, 2.2, 1.1))
```

The summary-level correction above uses the published Table 2 counts and ignores knee clustering. It is the transparent, reproducible-from-the-paper check.

# Methods and provenance

```{r priors}
pr <- run$bias_priors
oaireport::compare_table(data.frame(
  Outcome = named(pr$outcome, outcome_names), Scenario = pr$scenario, Stratum = pr$stratum,
  Sensitivity = sprintf("%s / %s", count(pr$se_k), count(pr$se_n)),
  Specificity = sprintf("%s / %s", count(pr$sp_k), count(pr$sp_n)), check.names = FALSE),
  widths = c(2.6, 1.8, 1.2, 1.4, 1.4))
```

Priors are Beta(k + 1, n − k + 1) from the 2×2 counts above, taken in the Lo 2022 participants with device data. Reclassification is done within outcome strata, and each iteration refits the replication's own GEE models.

```{r ledger}
#| results: asis
ledger <- readLines("ASSUMPTIONS.md", warn = FALSE)
ledger <- ledger[!grepl("^# |^<!--", ledger)]
spans <- gregexpr("`[A-Za-z][A-Za-z0-9_.{}]*`", ledger)
regmatches(ledger, spans) <- lapply(regmatches(ledger, spans), function(x) {
  gsub("([._])", "\\1\u200b", gsub("`", "", x))
})
cat(ledger, sep = "\n")
```
````

- [ ] **Step 3: Render and look**

Run: `uv run oai report walking_validation --run`
Expected:
- `Report: …/walking_validation/report/report.pdf`;
- `uv run oai check-egress <that folder>` reports 0 problems.

Render the pages to PNG with the PDFKit script from the reporting plan (`swift pdfpage.swift <pdf> <page> <png>`) and read each with the Read tool. Check:
- no R error text or `NA` where a number belongs;
- tables continue across pages;
- the forest plot shows four sources in fixed colours;
- the tipping-point grid is legible;
- the strata figure's labels are readable.

Fix the `.qmd` and re-render until clean.

- [ ] **Step 4: Commit**

```bash
git add analyses/walking_validation/report.qmd analyses/walking_validation/analysis.toml
git commit -m "feat(walking_validation): report

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Docs, follow-ups, final verification

**Files:**
- Modify: `README.md` (analyses table), `TODO.md` (a step-data request item), `docs/superpowers/specs/2026-10-01-walking-validation-design.md` (status)

- [ ] **Step 1: README and TODO**

In `README.md`'s analyses table, add the row:

```
| `walking_validation` | local | [spec](docs/superpowers/specs/2026-10-01-walking-validation-design.md) |
```

In `TODO.md`, under `### Lo 2022 replication`, add:

```markdown
- **Request OAI GT1M step data for walking_validation** — <!-- skip --> Steps are not in the public release or in NDA's accelerometry structures (counts only). Lo et al. 2015 (Arthritis Rheumatol 67:2897-904) used OAI step counts with the OAI accelerometry investigators at Northwestern; ask for per-minute steps (for cadence) at 48 and 72 months. When received, place them under the data root's `external/` folder and add a steps criterion to `oai.derive.accel` and a ledger variant.
```

In the spec, change `**Status:** Draft for review` to `**Status:** Implemented (see §15 Amendments)`.

- [ ] **Step 2: Full verification**

```bash
uv run ruff check && uv run ruff format --check && uv run python scripts/check_no_data.py
uv run pytest -q
uv run pytest -m realdata -q
cd r && Rscript -e 'testthat::test_local("oaimodels", stop_on_failure = TRUE)' && RENV_PROFILE=report Rscript -e 'testthat::test_local("oaimodels", stop_on_failure = TRUE); testthat::test_local("oaireport", stop_on_failure = TRUE)'; cd ..
git diff --exit-code main -- r/renv.lock && echo "default lockfile unchanged"
git diff --name-only main | grep -E '\.(pdf|png|csv|parquet)$' || echo "no data or figure files on branch"
```

Expected: every command passes, plus `default lockfile unchanged` and `no data or figure files on branch`.

- [ ] **Step 3: Commit and hand off**

```bash
git add README.md TODO.md docs/superpowers/specs/2026-10-01-walking-validation-design.md
git commit -m "docs: walking_validation in README; step-data request in TODO

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Use superpowers:finishing-a-development-branch.
