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
- `part_titles` needs `combined`, takes one title per joined document (all documents unless `combined_documents` chooses), and defaults to the file names without `.qmd`.
- `combined_documents = [...]` chooses which documents `combined` joins, in that order (default: all); `part_titles` then has one title per joined document. It needs `combined`, and lists documents from `documents`, each once.
- `combined` must be a bare `.pdf` file name that does not collide with a document's PDF or an asset. Joining needs `pypdf`, a dev dependency (`uv sync` installs it).
- Local assets are never required, and are removed from the report folder after rendering, with everything else but the PDFs, `figures/` and `text/`.
- `oai report <analysis>` prints one `Report:` line per PDF.

## What happens

1. Each listed run needs a finished `run_info.json`. With `--run`, unfinished or missing runs are run first; without it, they are an error.
2. Quarto is found from `OAI_QUARTO`, then `[tools] quarto` in `config/oai.toml`, then `PATH`, then RStudio's bundled copy.
3. The entry and assets are copied to `$OAI_RESULTS_DIR/<name>/report/` and rendered there with `quarto render <entry> --to typst` (with `documents`, each document in order). Nothing is written into the repository.
4. R chunks start through `r/step-profile.R` with `RENV_PROFILE=report`, so `oaimodels::` and `oaireport::` are available. The environment carries:
   - `OAI_RESULTS_ROOT`, the analysis's results directory, `<results folder>/<analysis>`, which holds one folder per run label (the steps of `oai run` get `OAI_RESULTS_BASE`, the results folder itself, and `OAI_RESULTS_DIR`, one run's folder; see the README);
   - `OAI_REPORT_DIR`;
   - `OAI_REPORT_RUNS`, the comma-separated run labels.
5. After a successful render only `<entry>.pdf` (with `documents`, each document's PDF and the combined PDF), `figures/` and `text/` (plain text a document writes, such as an abstract ready to paste) remain. Run `oai check-egress` on the folder before sharing it; PDFs and PNGs are listed for manual review. A failed render keeps its intermediates for debugging.

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
| `compare_table(df, widths, labels, multipage, bold, groups, group_style)` | tinytable with ✓ / △ / – verdicts (columns named `verdict*`), display headers, Typst-escaped cells; breaks across pages unless `multipage = FALSE`. `bold`: a logical matrix of the table's shape, TRUE cells in bold. `groups`: a named list of row numbers, each name a group title set before that data row (as `tinytable::group_tt(i =)`, applied inside so bold stays on the right cells). `group_style`: `style_tt()` arguments for the group titles, bold italic by default; `NULL` leaves them plain |
| `parse_or(text)` | `"0.6 (0.4-0.8) *"` → or, lo, hi, sig |
| `table_note(text, close_group)`, `figure_group()` | A legend in small type under a table or figure, built in R from the run's assumptions and results; `figure_group()` keeps a figure and its legend on one page |
| `ledger_markdown(path)` | `ASSUMPTIONS.md` as lines for a `results: asis` chunk: title and comment dropped, keys given break points so they wrap in table cells |

Give long tables a Markdown heading, not a caption: captions do not survive page breaks in Typst.

## Plain-language documents

A document for readers outside statistics (e.g. `analyses/walking_validation/clinical.qmd`) keeps technical terms out of its text and bolds what is significant. `oaireport` and `oai` give the pieces:

- `tech_notes(entries)` makes a note registry. `$ref(key)` gives a superscript letter (a, b, …, in order of first reference; i, l and o are skipped, as they read like the digits of numbered citations) linked to the note; `$list()` writes the "Technical notes" list, each note linked back to its first marker. Use markers in prose only, never in table cells or legends, and write the list once, at the end.
- `standard_tech_notes()` gives default texts for common methods (median difference, Wilson and bootstrap CIs, test for trend, rank correlation, sensitivity and specificity, predictive values, Youden's J, kappa, limits of agreement, median regression, tipping-point analysis, misclassification simulation, non-differential misclassification). Entries passed to `tech_notes()` override or extend them; put the run's settings (resamples, iterations) in the text.
- `ci_excludes(lo, hi, null = 0)` is TRUE when a 95% CI lies strictly on one side of the null (use `null = 1` for odds ratios); a limit at the null or a missing limit is FALSE. Pass the result to `compare_table(bold =)`. With grouped rows, pass `groups` to `compare_table()` instead of calling `group_tt` yourself, so bold lands on the right cells.
- `oai.pdfcheck.find_terms(pdf, terms, stop_heading=)` lists the terms found before the last `stop_heading` (whole words, any case), and `max_right_edge(pdf)` gives the largest right edge of any word, in points (`None` without `pdftotext`). Tests use them to keep jargon out of a document's text and its text inside the margins.

## Abstracts

A conference abstract (e.g. `analyses/walking_validation/abstract.qmd`) builds each field (title, sections, figure caption) as a plain R string from the run, so the counted text is exactly the text that gets pasted:

- `char_budget(sections, images, per_image = 560, limit = 5000)` counts each named field's characters, spaces included, and a symbol such as ≥ or ρ once. It charges `per_image` for each image, tables included, since a portal charges an image up to that much. It returns a table of each part, Total, Limit and Margin, and stops the render when the total is over the limit. Set `limit` and `per_image` from the meeting's rules.
- Write the fields to `text/<name>.txt`, one block per field with its count, for pasting into the submission form; `oai report` keeps `text/` beside the PDFs, and `oai check-egress` scans it with the rest of the folder.
- Reuse a figure another document saved with that analysis's `figure_file()` (list the saving document first in `[report] documents`); `save_figure()` already writes a 300 dpi PNG for upload.

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
