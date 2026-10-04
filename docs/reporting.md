# Reports

`oai report NAME [--run]` renders an analysis's Quarto report to PDF.

```toml
# analyses/<name>/analysis.toml
[report]
entry = "report.qmd"            # a .qmd directly in the analysis folder
runs = ["default", "variant"]   # run labels it reads: "default" or variants in assumptions.toml
assets = ["ASSUMPTIONS.md"]     # files copied next to the entry
```

For several documents, use `documents` instead of `entry`:

```toml
[report]
documents = ["brief.qmd", "report.qmd"]          # rendered in this order
combined = "walking_validation_brief.pdf"        # optional: joins their PDFs in order
part_titles = ["Brief", "Appendix: technical report"]  # optional: one bookmark per part
runs = ["default"]
assets = ["ASSUMPTIONS.md", "references.bib"]
local_assets = ["brief.local.yml"]               # optional, untracked: copied when present
```

- `entry` and `documents` cannot be used together.
- `part_titles` default to the document names.
- Local assets are never required, and are removed from the report folder after rendering, with everything else but the PDFs and `figures/`.
- `oai report <analysis>` prints one `Report:` line per PDF.

## What happens

1. Each listed run needs a finished `run_info.json`. With `--run`, unfinished or missing runs are run first; without it, they are an error.
2. Quarto is found from `OAI_QUARTO`, then `[tools] quarto` in `config/oai.toml`, then `PATH`, then RStudio's bundled copy.
3. The entry and assets are copied to `$OAI_RESULTS_DIR/<name>/report/` and rendered there with `quarto render <entry> --to typst` (with `documents`, each document in order). Nothing is written into the repository.
4. R chunks start through `r/step-profile.R` with `RENV_PROFILE=report`, so `oaimodels::` and `oaireport::` are available. The environment carries:
   - `OAI_RESULTS_ROOT`, the analysis's results directory, `<results folder>/<analysis>`, which holds one folder per run label (the steps of `oai run` get `OAI_RESULTS_BASE`, the results folder itself, and `OAI_RESULTS_DIR`, one run's folder; see the README);
   - `OAI_REPORT_DIR`;
   - `OAI_REPORT_RUNS`, the comma-separated run labels.
5. After a successful render only `<entry>.pdf` (with `documents`, each document's PDF and the combined PDF) and `figures/` remain. Run `oai check-egress` on the folder before sharing it; PDFs and PNGs are listed for manual review. A failed render keeps its intermediates for debugging.

## Writing a report

Start from `analyses/lo2022_walking/report.qmd`. The front matter must keep:

```yaml
format:
  typst:
    papersize: us-letter
knitr:
  opts_chunk:
    dev: cairo_pdf   # embeds Arial; the default pdf device fails on system fonts
```

and the body should open with these Typst rules, so table cells are 8.5 pt, ragged and
unhyphenated (the body text is justified and hyphenated, which garbles narrow cells):

````markdown
```{=typst}
#show table: set text(size: 8.5pt, hyphenate: false)
#show table: set par(justify: false)
```
````

`oaireport` (R, `r/oaireport/`) provides:

| Function | Purpose |
|---|---|
| `load_results()` | Every listed run: its CSVs by name, `metrics`, `assumptions`, `run_info` |
| `theme_oai()`, `oai_palette`, `oai_font()` | ACR journal style: Arial 7–9 pt, Okabe–Ito colours in fixed order |
| `save_figure(plot, name, "1col"/"2col")` | `figures/<name>.pdf` + 300 dpi `.png` at 3.5 in / 7 in |
| `forest_plot(estimates, facet = , sources = )` | Odds ratios by outcome, up to four sources |
| `flow_diagram(flow, labels, published)` | Cohort flow from `flow.csv`, "ours [published]" |
| `compare_table(df, widths, labels, multipage)` | tinytable with ✓ / △ / – verdicts (columns named `verdict*`), display headers, Typst-escaped cells; breaks across pages unless `multipage = FALSE` |
| `parse_or(text)` | `"0.6 (0.4-0.8) *"` → or, lo, hi, sig |
| `table_note(text, close_group)`, `figure_group()` | A legend in small type under a table or figure, built in R from the run's assumptions and results; `figure_group()` keeps a figure and its legend on one page |
| `ledger_markdown(path)` | `ASSUMPTIONS.md` as lines for a `results: asis` chunk: title and comment dropped, keys given break points so they wrap in table cells |

Give long tables a Markdown heading, not a caption: captions do not survive page breaks in Typst.

## The `report` renv profile

The reporting packages (ggplot2, tinytable, knitr, rmarkdown, ragg, …) live in `r/renv/profiles/report/renv.lock`. That keeps the default `r/renv.lock`, which the enclave bundle restores, free of them. To restore or update the profile:

```bash
cd r && RENV_PROFILE=report Rscript -e 'renv::restore(prompt = FALSE)'
cd r && RENV_PROFILE=report Rscript -e 'testthat::test_local("oaireport")'
```

The profile also carries local-only analysis packages (e.g. `quantreg`). An analysis whose R
steps need them declares, in `analysis.toml`:

```toml
[r]
profile = "report"   # R steps run with RENV_PROFILE=report; not allowed with enclave steps
```
