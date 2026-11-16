# Steps vs Activity Counts Within a Minute (walking_steps Q1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** add a `relation` step to `analyses/walking_steps` that writes aggregate tables of per-minute steps against activity counts, and a report section that draws the Northwestern accelerometry group's three Q1 plots from them.

**Architecture:**
- `relation.py` holds pure polars/numpy functions over the analysis minutes from `share.analysis_minutes()`.
- `minute_relation.py` is the step entry. It reads both waves and writes three CSVs.
- `report.qmd` draws the hexbin, the quartile plot and the stacked bars from those CSVs. No minute data reach R.

**Tech Stack:** Python 3 (polars, numpy, pytest), R/Quarto (ggplot2, typst PDF), and the repo's `oai` CLI and ledger (`oai.assumptions.current()`).

**Spec:** `docs/superpowers/specs/2026-11-13-steps-counts-minute-relation-design.md`

## Global Constraints

- **Unit and sample.** The unit is the wear minute, pooled over participants. The minutes are exactly those `share.analysis_minutes(read_minutes(visit, steps=True), device_rules(A), int(A["sample.min_step_days"]))` returns, for visits `"06"` (48 mo) and `"08"` (72 mo), and the two are kept separate.
- **Count bins.** `relation.count_bin_edges = [0, 100, 500, 1000, 1500, 2020, 5999]`.
  - The labels are `0-99`, `100-499`, `500-999`, `1000-1499`, `1500-2019`, `2020-5998` and `5999+`.
  - The intensities are sedentary, light ×4, moderate and vigorous.
- **Step bands.** These come from the existing `walking.band_edges` (`[1, 20, 40, 60, 80, 100, 120]`), labelled as in `share.cadence_bands`: `0`, `1-19`, … , `100-119`, `120+`.
- **Hexbin.**
  - The x-axis is cut off at the per-wave quantile `relation.hex_x_quantile = 0.999` of `cnt`.
  - The y-axis runs from 0 to 200 steps.
  - The grid is `relation.hex_gridsize = 50` hexagons across x, with `ny = round(50 / sqrt(3))` rows.
  - The fill is a log scale.
- **Egress.**
  - The results carry no raw minute totals. Use shares, or minutes in thousands rounded to 0.1, as `walking_share.py` does for `cadence_bands.csv`.
  - No column may match `oai.export.egress.COUNT_COLUMN` (`n`, `count`, `n_*`, `*_n`, `*_count`).
  - The per-minute steps never enter the repo.
- **Commits.** Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Count bin edges that disagree with the device ledger.** If `relation.count_bin_edges` doesn't contain `device.light_floor` (100) and `device.mv_cutpoint` (2020), or doesn't start at 0, the step must fail rather than mislabel the intensities (Task 1, `test_count_bins_reject_edges_off_the_device_cutpoints`).
2. **Steps above 200/min.** The hexbin y range is fixed at 0–200, so a minute above 200 would fall off silently. `hex_cells` must raise instead (Task 2, `test_hex_cells_rejects_steps_above_200`).
3. **Minutes at the x cut-off or beyond it.** Minutes with `cnt > xcap` are left out of the cells but reported as `share_beyond`. The cell shares plus `share_beyond` must sum to 1 (Task 2, `test_hex_cells_shares_sum_to_one_with_beyond`).
4. **A count bin with no minutes** (possible for `5999+` in a small synthetic or variant sample). It must still appear in `band_shares` and `bin_quantiles` with null quantiles and zero shares, so that report factors don't shift (Task 1, `test_empty_count_bin_is_kept`).
5. **Large minute totals that look like participant IDs.** A raw total of 9,xxx,xxx minutes trips the egress ID regex. Outputs carry shares or thousands only (Task 3, `test_relation_outputs_pass_egress`).

---

### Task 1: Count bins, steps quartiles by bin, and step-band shares

**Files:**
- Create: `analyses/walking_steps/relation.py`
- Modify: `analyses/walking_steps/assumptions.toml` (add a `relation.*` block after `[walking.band_edges]`)
- Test: `tests/test_walking_steps.py` (add `import relation as r` beside `import share as s`; reuse its `frame()` helper)

**Interfaces:**
- Produces:
  - `count_bin_labels(edges: list[int]) -> list[str]` returns `["0-99", …, "2020-5998", "5999+"]` for the ledger edges.
  - `intensity_of(edges: list[int], light_floor: float, mv_cutpoint: float, vigorous: int) -> dict[str, str]` maps a bin label to `"sedentary" | "light" | "moderate" | "vigorous"`. `vigorous` is the last edge, 5999.
  - `check_count_edges(edges: list[int], light_floor: float, mv_cutpoint: float) -> None` raises `ValueError` unless the edges are strictly increasing, `edges[0] == 0`, and both cutpoints are among them.
  - `with_bins(w: pl.DataFrame, count_edges: list[int], band_edges: list[int]) -> pl.DataFrame` adds String columns `count_bin` and `band`. The bands use the same cut and labels as `share.cadence_bands`, so refactor the label and break code there into a shared `band_labels(edges)` in `share.py` and call it from both places.
  - `bin_quantiles(w: pl.DataFrame, count_edges: list[int]) -> pl.DataFrame` has the columns `count_bin, minutes_thousands, share_of_minutes, steps_q1, steps_median, steps_q3`, with one row per label in label order and linear-interpolated quantiles.
  - `band_shares(w: pl.DataFrame, count_edges: list[int], band_edges: list[int]) -> pl.DataFrame` has the columns `count_bin, band, share`, with the full count_bin × band grid, where `share` is the share of the bin's minutes and is 0 for an empty bin.

- [ ] **Step 1: Write the failing tests**

```python
EDGES = [0, 100, 500, 1000, 1500, 2020, 5999]
BANDS = [1, 20, 40, 60, 80, 100, 120]

def test_count_bin_labels_and_intensity():
    assert r.count_bin_labels(EDGES) == ["0-99", "100-499", "500-999", "1000-1499",
                                         "1500-2019", "2020-5998", "5999+"]
    m = r.intensity_of(EDGES, 100, 2020, 5999)
    assert m["0-99"] == "sedentary" and m["1500-2019"] == "light"
    assert m["2020-5998"] == "moderate" and m["5999+"] == "vigorous"

@pytest.mark.parametrize("edges", [[0, 100, 500, 2000, 5999], [10, 100, 2020], [0, 500, 100, 2020]])
def test_count_bins_reject_edges_off_the_device_cutpoints(edges):
    with pytest.raises(ValueError):
        r.check_count_edges(edges, 100, 2020)

def test_bin_quantiles_by_count_bin():
    w = frame(cnt=[0.0, 50.0, 2019.0, 2020.0, 2020.0, 6000.0], steps=[0.0, 0.0, 30.0, 90.0, 110.0, 150.0])
    q = r.bin_quantiles(w, EDGES)
    assert q["count_bin"].to_list() == r.count_bin_labels(EDGES)
    row = q.filter(pl.col("count_bin") == "2020-5998")
    assert row["steps_median"].item() == 100.0 and row["share_of_minutes"].item() == pytest.approx(2 / 6)
    assert q.filter(pl.col("count_bin") == "1500-2019")["steps_median"].item() == 30.0

def test_band_shares_sum_to_one_within_bin():
    w = frame(cnt=[2500.0] * 4, steps=[0.0, 19.0, 20.0, 125.0])
    b = r.band_shares(w, EDGES, BANDS).filter(pl.col("count_bin") == "2020-5998")
    got = dict(zip(b["band"], b["share"]))
    assert got["0"] == 0.25 and got["1-19"] == 0.25 and got["20-39"] == 0.25 and got["120+"] == 0.25
    assert sum(got.values()) == pytest.approx(1.0)

def test_empty_count_bin_is_kept():
    w = frame(cnt=[0.0, 300.0], steps=[0.0, 10.0])
    q = r.bin_quantiles(w, EDGES)
    vig = q.filter(pl.col("count_bin") == "5999+")
    assert vig.height == 1 and vig["steps_median"].item() is None
    b = r.band_shares(w, EDGES, BANDS).filter(pl.col("count_bin") == "5999+")
    assert b.height == 8 and b["share"].sum() == 0
```

- [ ] **Step 2: Run the tests to check they fail**

Run: `uv run pytest tests/test_walking_steps.py -k "count_bin or bin_quantiles or band_shares or empty_count" -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'relation'`.

- [ ] **Step 3: Add the ledger entries to `assumptions.toml`**

Add `[relation.count_bin_edges]` with:
- `value = [0, 100, 500, 1000, 1500, 2020, 5999]`
- `status = "confirmed"`
- `source = "User's choice (2026-11-13): sedentary < 100, light 100-2019 in four equal-width bins, moderate 2020-5998, vigorous >= 5999 (Troiano 2008 vigorous cutpoint)"`

Add `[relation.hex_x_quantile]` with `value = 0.999` and `status = "assumed"`. Its source: "the hexbin x-axis stops at this quantile of wear-minute counts per wave; the share beyond is reported."

Add `[relation.hex_gridsize]` with `value = 50` and `status = "assumed"`. Its source: "hexagons across the x-axis; rows = round(50 / sqrt(3))."

- [ ] **Step 4: Implement the Task 1 functions in `relation.py`, and `band_labels` in `share.py`**

Cut the counts with `pl.col("cnt").cut([e - 0.5 for e in edges[1:]], labels=...)`. Counts are integers, so the edges are exact. Build the full grid with a cross join on the label lists, so that empty bins survive.

- [ ] **Step 5: Run the whole test file to check it passes**

Run: `uv run pytest tests/test_walking_steps.py -v`
Expected: all PASS, including the 18 existing tests (they guard the `band_labels` refactor).

- [ ] **Step 6: Commit**

```bash
git add analyses/walking_steps/relation.py analyses/walking_steps/share.py analyses/walking_steps/assumptions.toml tests/test_walking_steps.py
git commit -m "feat(walking_steps): count bins, steps quartiles and band shares by count bin"
```

### Task 2: Hexagonal cells of counts × steps

**Files:**
- Modify: `analyses/walking_steps/relation.py`
- Test: `tests/test_walking_steps.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `hex_cells(cnt: np.ndarray, steps: np.ndarray, quantile: float, gridsize: int, ymax: float = 200.0) -> tuple[pl.DataFrame, dict[str, float]]`.
  - The frame has the columns `x, y, share`, with one row per non-empty hexagon. `x` and `y` are the centres. `share` is the hexagon's minutes divided by all minutes passed in.
  - The dict has `xcap` (the quantile of `cnt`), `share_beyond` (the share with `cnt > xcap`), `hex_dx` (`sx`) and `hex_dy` (`sy`), so the report can draw the hexagons.

- [ ] **Step 1: Write the failing tests**

```python
def test_hex_cells_shares_sum_to_one_with_beyond():
    rng = np.random.default_rng(1)
    cnt = rng.integers(0, 4000, 5000).astype(float); cnt[:10] = 20000.0
    steps = rng.integers(0, 201, 5000).astype(float)
    cells, meta = r.hex_cells(cnt, steps, 0.999, 50)
    assert meta["share_beyond"] > 0
    assert cells["share"].sum() + meta["share_beyond"] == pytest.approx(1.0)
    assert cells["x"].max() <= meta["xcap"] + meta["hex_dx"]

def test_hex_cells_puts_identical_points_in_one_cell():
    cells, _ = r.hex_cells(np.array([0.0] * 9 + [1000.0]), np.array([0.0] * 9 + [100.0]), 1.0, 50)
    assert cells.height == 2 and sorted(cells["share"].to_list()) == [0.1, 0.9]

def test_hex_cells_rejects_steps_above_200():
    with pytest.raises(ValueError, match="200"):
        r.hex_cells(np.array([100.0]), np.array([201.0]), 1.0, 50)
```

- [ ] **Step 2: Run the tests to check they fail**

Run: `uv run pytest tests/test_walking_steps.py -k hex_cells -v`
Expected: FAIL with `AttributeError: module 'relation' has no attribute 'hex_cells'`.

- [ ] **Step 3: Implement `hex_cells`**

Use matplotlib's hexbin lattice, which the signature doesn't determine:

```python
xcap = float(np.quantile(cnt, quantile)); keep = cnt <= xcap
ny = round(gridsize / np.sqrt(3)); sx = xcap / gridsize; sy = ymax / ny
ix, iy = cnt[keep] / sx, steps[keep] / sy
i1, j1 = np.round(ix), np.round(iy)                    # lattice 1: (i*sx, j*sy)
i2, j2 = np.floor(ix) + 0.5, np.floor(iy) + 0.5        # lattice 2: offset by half a cell
d1 = (ix - i1) ** 2 + 3 * (iy - j1) ** 2
d2 = (ix - i2) ** 2 + 3 * (iy - j2) ** 2
cx = np.where(d1 <= d2, i1, i2) * sx; cy = np.where(d1 <= d2, j1, j2) * sy
```

Group by `(cx, cy)` and count. Divide by `len(cnt)`, the minutes passed in, not the kept ones. Raise `ValueError("steps above 200/min ...")` if `steps.max() > ymax`. If `xcap == 0`, use `sx = 1.0` so that division is safe.

- [ ] **Step 4: Run the tests to check they pass**

Run: `uv run pytest tests/test_walking_steps.py -k hex_cells -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add analyses/walking_steps/relation.py tests/test_walking_steps.py
git commit -m "feat(walking_steps): hexagonal cells of counts x steps per minute"
```

### Task 3: The `relation` step entry and its outputs

**Files:**
- Create: `analyses/walking_steps/minute_relation.py`
- Modify: `analyses/walking_steps/analysis.toml` (add a step after `share`), `analyses/walking_steps/README.md` (a "Part 3: steps against counts within a minute" section, with an outputs table)
- Test: `tests/test_walking_steps.py`

**Interfaces:**
- Consumes:
  - `relation.check_count_edges`, `with_bins`, `bin_quantiles`, `band_shares`, `hex_cells` and `intensity_of` (Tasks 1–2)
  - `share.analysis_minutes`
  - `devices.device_rules`
  - `oai.derive.accel.read_minutes`
- Produces, in `$OAI_RESULTS_DIR`:
  - `relation_hex.csv`: `visit, x, y, share`
  - `relation_hex_meta.csv`: `visit, xcap, share_beyond, hex_dx, hex_dy`
  - `relation_bins.csv`: `visit, count_bin, intensity, minutes_thousands, share_of_minutes, steps_q1, steps_median, steps_q3`
  - `relation_bands.csv`: `visit, count_bin, intensity, band, share`
  - `oai.report.load_results()` exposes all four to R as `run$relation_hex` and so on, by file stem.

- [ ] **Step 1: Write the failing egress test**

```python
def test_relation_outputs_pass_egress(tmp_path):
    from oai.export.egress import check_egress
    w = frame(cnt=[0.0, 300.0, 2500.0, 7000.0] * 50, steps=[0.0, 10.0, 105.0, 130.0] * 50)
    r.bin_quantiles(w, EDGES).write_csv(tmp_path / "relation_bins.csv")
    r.band_shares(w, EDGES, BANDS).write_csv(tmp_path / "relation_bands.csv")
    cells, _ = r.hex_cells(w["cnt"].to_numpy(), w["steps"].to_numpy(), 0.999, 50)
    cells.write_csv(tmp_path / "relation_hex.csv")
    assert check_egress(tmp_path).ok()
```

(Check `check_egress`'s signature in `src/oai/export/egress.py:150` and pass any required `min_cell` the way existing egress tests do.)

- [ ] **Step 2: Run it to check it passes, or fix the column names until it does**

Run: `uv run pytest tests/test_walking_steps.py::test_relation_outputs_pass_egress -v`
Expected: PASS. A failure names the offending column; rename it so it doesn't match `COUNT_COLUMN`.

- [ ] **Step 3: Write `minute_relation.py`**

Follow `walking_share.py`:
- Read `A = current()`.
- Call `check_count_edges(edges, rules.light_floor, rules.mv_cutpoint)` before reading any data.
- Loop over visits `"06"` and `"08"`.
- Add `visit` and `intensity` columns, then concatenate and write the four CSVs.

Add to `analysis.toml`:

```toml
[[steps]]
id = "relation"
lang = "python"
stage = "local"
entry = "minute_relation.py"
```

- [ ] **Step 4: Run the step on real data**

Run: `uv run oai run walking_steps`
Expected:
- The four `relation_*.csv` files appear in `~/oai-work/results/walking_steps/default/`.
- The egress check that `oai run` performs passes.
- In `relation_bins.csv`, `share_of_minutes` sums to 1 per visit, and `steps_median` rises across the count bins.
- `share_beyond` is about 0.001 per visit.

- [ ] **Step 5: Run the whole test file**

Run: `uv run pytest tests/test_walking_steps.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add analyses/walking_steps/minute_relation.py analyses/walking_steps/analysis.toml analyses/walking_steps/README.md tests/test_walking_steps.py
git commit -m "feat(walking_steps): relation step writes steps-vs-counts aggregates for Q1"
```

### Task 4: Report section with the three Q1 figures

**Files:**
- Modify: `analyses/walking_steps/report.qmd`. Add a section, "Steps and activity counts within a minute", after "How much of the activity counts is walking" and before "Device walkers".

**Interfaces:**
- Consumes: `run$relation_hex`, `run$relation_hex_meta`, `run$relation_bins` and `run$relation_bands` (Task 3), plus the setup chunk's `wave()`, `num()`, `pct()`, `colours` and `assumption()`.

- [ ] **Step 1: Add the three figure chunks**

Draw each figure with `facet_wrap(~ wave)`, using the panel labels "48 months" and "72 months" as in `fig-bands`.

- **`fig-hex`: the hexbin.**
  - Draw each hexagon with `geom_polygon`, from its centre plus the vertex offsets `(±0.5·dx, ±dy/6)` and `(0, ±dy/3)` (matplotlib's hexagon).
  - Map fill to `share` with `scale_fill_viridis_c(trans = "log10")`.
  - Add `geom_vline` at `device.light_floor` and `device.mv_cutpoint`, and a dotted line at the vigorous edge.
  - The caption gives the cut-off and `pct(share_beyond)` per wave: "Each hexagon's colour is the share of wear minutes it holds (log scale). Minutes above X counts/min (the top 0.1%) are not shown."
- **`fig-bin-quartiles`: steps by count bin.**
  - Plot a point at `steps_median` with a `geom_linerange` from `steps_q1` to `steps_q3`.
  - The x-axis is the count bins in ledger order. Label each with its intensity and range, for example "Light\n100–499".
- **`fig-bin-bands`: a 100% stacked bar of `share` by `band` within each count bin.**
  - The fill is sequential (0 steps lightest to 120+ darkest).
  - Put labels only on segments of 10% or more.

- [ ] **Step 2: Render the report and look at it**

The worktree needs the report renv library: symlink `r/renv/profiles/report/renv/library` to the main checkout's library, and add the link to `.git/info/exclude`.

Run: `uv run oai report walking_steps`
Expected:
- The render succeeds and `report.pdf` grows by about two pages.
- Read the new pages as images (`pdftoppm -r 80`) and check:
  - the hexbin shows a dense band of 0 steps across the low counts;
  - the cutpoint lines line up with the x ticks;
  - the stacked bars sum to 100%, and no label collides with another.

- [ ] **Step 3: Commit**

```bash
git add analyses/walking_steps/report.qmd
git commit -m "feat(walking_steps): report section with the Q1 steps-vs-counts figures"
```
