# Reporting Module + Lo 2022 Comparison Report — Design

**Date:** 2026-09-30
**Status:** Draft for review
**Builds on:** `2026-09-30-oai-analytics-scaffold-design.md`, `2026-09-30-assumptions-and-lo2022-replication-design.md`

## 1. Purpose

Many analyses will be run on this dataset, and each needs publication-quality figures
and a readable report. This adds a thin, reusable R reporting layer, plus an
`oai report` command that renders an analysis's Quarto report to PDF. Its first
consumer is a result-by-result comparison of Lo et al. 2022 with our replication:
a polished main body that can be shared with the authors, and an exhaustive appendix.

## 2. Scope

**In scope:**
- R package `oaireport`: ACR-style theme, figure export, forest plot, flow diagram,
  comparison tables, results loader.
- Runner provenance file `run_info.json`.
- `[report]` manifest section and the `oai report NAME [--run]` command.
- `analyses/lo2022_walking/report.qmd`.

**Out of scope (YAGNI until a second consumer needs them):**
- figure registries or plugin systems;
- Word/HTML output;
- per-run (single-label) reports;
- Kaplan–Meier, spline or trajectory plots;
- automated journal submission formatting beyond figure size and fonts.

## 3. Key decisions

| Decision | Choice | Reason |
|---|---|---|
| Layer | Thin `oaireport` R package; comparator is first consumer | Reusable pieces without guessing abstractions from n = 1 |
| Rendering | Quarto → Typst PDF (`format: typst`) | No LaTeX; Quarto 1.9 is bundled with the installed RStudio |
| Figure style | ACR journals (Arthritis & Rheumatology, Arthritis Care & Research) | Venue of Lo 2022 and of most OA work |
| Report scope | Cross-run (one report reads several run labels) | A replication comparison spans default + variants |
| Render location | A copy of `report.qmd` rendered inside `$OAI_RESULTS_DIR/<analysis>/report/` | Keeps data-derived intermediates (figures, caches) out of the repo |

## 4. `oaireport` R package (`r/oaireport/`, same renv project)

New renv dependencies: `ggplot2`, `scales`, `gt`, `ragg`, `systemfonts`, `knitr`,
`rmarkdown`. (`jsonlite` and `nanoparquet` are already locked.)

### 4.1 Style (ACR)

- `oai_font()`: `"Arial"` when installed (systemfonts), otherwise `"sans"` (e.g. CI).
- `theme_oai(base_size = 8)`: `theme_classic` base with `oai_font()`; axis text 7–8 pt,
  titles 8–9 pt; no background grid except light major gridlines on the estimate
  axis of forest plots; legend at the bottom.
- `oai_palette`: Okabe–Ito colorblind-safe colors in a fixed source order (published,
  ours, variant 1, variant 2, …). Sources are also told apart by point shape, so
  figures stay legible in grayscale.

### 4.2 Export

`save_figure(plot, name, width = c("1col", "2col"), height = NULL, dir = figure_dir())`
- **Width:** `"1col"` = 3.5 in, `"2col"` = 7 in. `height` defaults to 0.75 × width and
  is capped at 9 in.
- **Files:** `<dir>/<name>.pdf` (vector, `cairo_pdf` so fonts embed) and
  `<dir>/<name>.png` (300 dpi, `ragg`).
- **Returns:** the PDF path, invisibly.
- **Default directory:** `figure_dir()` = `$OAI_REPORT_DIR/figures`, or `tempdir()`
  when the variable is unset.

### 4.3 Figures

- **`forest_plot(estimates, ref = 1, log_scale = TRUE, facet = NULL)`**
  - `estimates` is a data.frame with columns `outcome, source, or, lo, hi` and an
    optional `sig`.
  - One row per outcome; sources are dodged vertically within an outcome.
  - Log x axis, with a dashed reference line at `ref`.
  - Optional facet column, e.g. unadjusted vs adjusted.
  - Returns a ggplot.
- **`flow_diagram(flow, labels, published = NULL)`**
  - `flow` has columns `step, persons, excluded_persons, excluded_knees` (as written by
    every analysis).
  - `labels` maps each step to text.
  - Draws vertical "remaining" boxes and side "excluded" boxes in ggplot.
  - When `published` (a named numeric vector keyed by metric, e.g.
    `flow.roa.persons`) is given, each box shows "ours [published]".
  - Returns a ggplot.

### 4.4 Tables and data

- `compare_table(df, title)`: a `gt` table of metric / published / ours / verdict
  columns, with verdict cells colored (replicated / drift / missing) and grayscale-safe
  symbols.
- `load_results(root, labels)`: a named list per label holding `flow`, `metrics` (named
  numeric), `table2`, `comparison`, `assumptions` (resolved JSON) and `run_info`.
  A missing label is an error naming the label and the `oai run` command that
  produces it.

## 5. Provenance: `run_info.json`

On every `oai run`, the runner writes `run_info.json` into the run's results directory:

```json
{"analysis": "...", "label": "...", "variant": null, "git_commit": "<sha or null>",
 "git_dirty": false, "started_utc": "...", "finished_utc": "...",
 "oai_version": "...", "steps": ["cohort", "models", "compare"]}
```

- Outside a git checkout (a bundle), `git_commit` is null.
- `finished_utc` is written only after all steps succeed.

## 6. Reports: manifest and command

### 6.1 `analysis.toml`

```toml
[report]
entry = "report.qmd"                 # in the analysis folder
runs = ["default", "walker_requires_amount", "missing_as_walkers"]   # labels it reads
assets = ["published.toml", "ASSUMPTIONS.md"]                         # copied next to it
```

**Validation:**
- `entry` and every asset must exist.
- `runs` must be non-empty.
- Every run other than `default` must be a variant defined in `assumptions.toml`.

### 6.2 `oai report NAME [--run]`

1. Load the manifest and require `[report]`.
2. With `--run`: run any listed label whose `run_info.json` lacks `finished_utc`.
   Without `--run`, a missing label is an error that suggests `--run`.
3. Locate Quarto in this order: `OAI_QUARTO`, then `[tools] quarto` in
   `config/oai.toml`, then `quarto` on `PATH`, then the RStudio bundle
   (`/Applications/RStudio.app/Contents/Resources/app/quarto/bin/quarto`).
   Otherwise fail with install guidance.
4. Copy `entry` and `assets` into `$OAI_RESULTS_DIR/<analysis>/report/` and render
   there with `quarto render <entry> --to typst`. The environment includes:
   - `OAI_RESULTS_ROOT` (= `$OAI_RESULTS_DIR/<analysis>`) and `OAI_REPORT_DIR`;
   - `OAI_REPORT_RUNS` (comma-separated labels);
   - the R step profile, so chunks can call `oaireport::` and `oaimodels::`.
5. The output is `report/<entry stem>.pdf` plus `report/figures/`. Print its path.

The report directory is aggregate-only and lives under the results directory, so
`oai check-egress` covers it. PDFs and PNGs are listed for manual review.

## 7. The Lo 2022 comparison report (`analyses/lo2022_walking/report.qmd`)

**Runs read:** `default`, `walker_requires_amount`, `roa_counts_replaced_knees`,
`published_counts`, `missing_as_nonwalkers`, `missing_as_walkers`,
`replacement_not_worsening`, `corstr_independence`.

### Main body (shareable)

1. **Summary.** Citation; data release; code version (from `run_info.json`). A table
   per run of replicated / drift / missing. The headline: which published conclusions
   reproduce (direction and significance of each Table 2 OR).
2. **Cohort flow.** `flow_diagram` of the default run with published counts in
   brackets, including the Supplementary Table 1 excluded groups (persons, knees,
   male, age, BMI).
3. **Table 1, side by side.** Published vs `default` vs `walker_requires_amount`, for
   walkers / non-walkers / all.
4. **Main results.** A paired `forest_plot` of the four outcomes (published, default,
   `walker_requires_amount`), faceted unadjusted / adjusted, with the numeric table
   below.
5. **What explains the gaps.** The two coding questions (yes-walkers without amount
   answers; knees replaced at baseline at the OA step): the evidence, the count each
   reproduces, the effect on results, and the question for the authors.
6. **Sensitivity analyses.** Supplementary Table 2 vs `missing_as_nonwalkers` and
   Supplementary Table 3 vs `missing_as_walkers`, as paired forest plots.

### Appendix (exhaustive)

- A. Table 3 (outcome by static alignment): published vs default.
- B. Supplementary Table 1, excluded-group characteristics.
- C. Replication grid: % replicated per results section (flow, S1, Table 1, Table 2,
  Table 3) × run as a heatmap, then the full per-metric verdict table for every run.
- D. Assumptions ledger (`ASSUMPTIONS.md`).
- E. Methods and provenance: grading tolerances (counts ±3% or ±2, means ±0.5,
  ORs ±0.1 with matching significance), `run_info.json` per run, and R and package
  versions.

**Figures** are exported with `save_figure` (flow 2-column, forests 2-column,
heatmap 2-column) for reuse in a manuscript or slides.

## 8. Testing

- **testthat (`oaireport`):**
  - `theme_oai` returns a theme;
  - `forest_plot` maps sources to colour and shape, puts outcomes on the y axis, uses
    a log x axis and draws the reference line;
  - `flow_diagram` has one box per step and shows "ours [published]" labels when
    `published` is given;
  - `save_figure` writes PDF and PNG at 3.5 in / 7 in (checked via PNG pixel size);
  - `load_results` errors on a missing label;
  - `compare_table` returns a `gt_tbl`.
- **pytest:**
  - `[report]` validation;
  - `run_info.json` contents, including `finished_utc` only on success;
  - Quarto discovery order;
  - `oai report` without `--run` reports missing labels;
  - `--run` runs only the missing ones (synthetic analysis with a Python step);
  - render smoke test of a tiny `.qmd` to PDF (skipped unless Quarto, R and knitr
    are available).
- **Real data:** `oai report lo2022_walking --run` produces a PDF (> 50 KB) with all
  figures, and `oai check-egress` passes (warnings allowed).

## 9. Success criteria

- `oai report lo2022_walking --run` renders `report.pdf` with every section in §7.
- Figures appear as PDF + PNG at ACR widths in `report/figures/`.
- No repository file changes during rendering.
- All tests green, and CI green (render tests skip in CI if Quarto is absent).

## 10. Error handling

- A missing Quarto, run, asset or `[report]` section produces an `OAIError` with the
  fix, e.g. "run `oai report NAME --run`" or "install Quarto or set OAI_QUARTO".
- A failed render produces an error with Quarto's stderr tail; partial outputs are
  left in place for inspection.

## 11. Open questions

- Whether to install standalone Quarto (Homebrew) rather than rely on RStudio's bundle.
  Not blocking; discovery supports both.

## 12. Amendments (2026-09-30, from prototyping while planning)

These supersede the sections they name.

1. **Tables use tinytable, not gt (§4, §4.4, §8).**
   - gt's Typst path runs Quarto's `juice` CSS inliner, which fails inside the RStudio-bundled Quarto. tinytable writes native Typst.
   - `compare_table(df, widths = NULL, compact = FALSE)` replaces `compare_table(df, title)`:
     - **No `title`:** a tinytable caption is lost when its table breaks across pages, so tables are titled by Markdown headings instead.
     - **`widths`:** relative column widths. Typst's default narrow, equal columns hyphenate words.
     - **`compact`:** verdict symbols only, for wide grids.
   - Tables are built with `theme_typst(multipage = TRUE)`, so long tables continue onto later pages with a repeated header. The default overprinted at the page foot after 17 rows.
   - `compare_table` returns a `tinytable`. `format_verdicts()` and `parse_or()` are added.
   - Verdict cells use a light status tint behind black text plus a symbol: the drift yellow is unreadable as text colour.
2. **Reporting packages live in a renv profile (§4).**
   - `r/renv/profiles/report/renv.lock`, activated by `RENV_PROFILE=report`, adds ggplot2, scales, tinytable, ragg, systemfonts, knitr, rmarkdown and withr on top of the default lockfile.
   - The default `r/renv.lock`, which enclave bundles restore offline, is unchanged. The enclave therefore never needs font or graphics system libraries, or rmarkdown's dependency tree.
   - `oai report` sets `RENV_PROFILE=report`, and `r/step-profile.R` loads `oaireport` only then.
   - CI tests `oaireport` in a separate `r-report` job.
3. **`run_info.json` and egress (§5).** About 2% of git commit hashes contain a run of digits that the participant-ID pattern matches. `[egress] ignore_id_pattern_columns` now also names JSON keys, and the project config lists `git_commit`.
4. **Report directory and manifest (§6.1, §6.2).**
   - `report/` is emptied before rendering.
   - After a successful render, everything except `<stem>.pdf` and `figures/` is removed: the copied entry and assets, `.quarto/` and the Typst intermediates. Without this, egress (which fails closed on `.qmd` and `.toml`) would fail.
   - `entry` and each asset must be a bare file name in the analysis folder.
   - The Lo report's assets are `["ASSUMPTIONS.md"]`. Published values come from each run's `comparison.csv`, so `published.toml` is not needed.
5. **Quarto discovery (§6.2).** An `OAI_QUARTO` or `[tools] quarto` value that is not executable is an error, not a fallthrough.
6. **Lo report, cohort flow (§7, main body item 2).** The flow diagram's side boxes show excluded participants and knees, as "ours [published]". The Supplementary Table 1 characteristics (men, age, BMI) are a table in Appendix B rather than box text, so the figure stays legible at two-column width.
