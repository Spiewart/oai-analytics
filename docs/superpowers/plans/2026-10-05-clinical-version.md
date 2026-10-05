# Clinical-Reader Version of the Walking-Validation Results — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a plain-language results document for clinical readers (`clinical.qmd`). It becomes the brief's appendix in the PDF that is sent. The brief is reframed neutrally, and the new presentation features go into the shared report tooling so any analysis can use them.

**Architecture:**
- **Shared setup.** The technical report's result lookups, formatters and definitions move into `analyses/walking_validation/report_setup.R`. `report.qmd` and the new `clinical.qmd` both source it, and the technical report's text must come out identical.
- **Reusable R tooling (`oaireport`).** It gains linked technical notes (`tech_notes()`, `standard_tech_notes()`), significance bolding (`ci_excludes()`, `compare_table(bold =, groups =)`) and nothing analysis-specific.
- **Reusable Python tooling (`oai`).** It gains `[report] combined_documents`, so the sent PDF joins only the brief and the clinical version, and `oai.pdfcheck`, which provides margin and jargon checks for any rendered PDF.

**Tech Stack:** Python 3.11 (uv, pytest, pypdf as a dev dependency); R (renv "report" profile: ggplot2, tinytable 0.19, yaml); Quarto 1.9 with Typst.

**Spec:** `docs/superpowers/specs/2026-10-05-clinical-version-design.md`

## Global Constraints

- **Privacy.**
  - The repository is public.
  - Results and reports are aggregate only.
  - `oai check-egress` must report 0 problems on `~/oai-work/results/walking_validation/report/`.
- **Wording (public text).**
  - Name no individuals except as cited authors, and describe no personal relationships. Say "the original authors" or "the study team".
  - "bias" and "correction" do not appear in the brief's or the clinical version's headings or main text. The technical report keeps its formal terms.
- **Numbers.** Every number comes from the run (`oaireport::load_results()` / `report_setup.R`). Literature values are cited.
- **Pages.**
  - The brief is ≤ 6 pages (stays at 5), and page 1 ends on the appendix pointer.
  - `clinical.pdf` is ≤ 12 pages and `report.pdf` ≤ 18.
  - The combined PDF's page count equals the brief's plus the clinical version's.
  - The combined PDF's bookmarks are exactly `["Brief", "Appendix: results"]`.
- **Margins.** Right edge ≤ 550.8 pt for the brief and the clinical version (0.85in margins), and ≤ 547.2 pt for the report, each with 0.01 pt tolerance.
- **Technical report unchanged.** Its `pdftotext` output is identical before and after this plan.
- **Clinical tables.**
  - One sample per table, ≤ 5 columns, group sizes in headers.
  - Estimates are written `0.89 (0.86–0.91)` via `fmt_ci()`.
  - **Bold** when the 95% CI excludes 0 (differences, correlations, κ, J) or 1 (odds ratios), and for a test for trend when p < 0.05. Sensitivity, specificity, PPV and NPV are never bold. A limit exactly at the null is not bold, and a missing CI is not bold.
  - Legends are 2–3 plain sentences and state the bold rule.
  - Minutes per day have 1 decimal, minutes per week are whole numbers, and counts have thousands separators. *(Plan refinement of spec §5.1: whole minutes per day would hide 1–2-minute differences.)*
- **Banned in the clinical main text** (allowed only after the "Technical notes" heading), compared case-insensitively on whole words:
  - Hodges–Lehmann, rank-biserial, Jonckheere–Terpstra, permutation, bootstrap, Wilson;
  - Spearman–Brown, deattenuated, limits of agreement;
  - non-differential, differential misclassification, probabilistic bias analysis, bias analysis;
  - draws, discarded, device wave, purposeful bout, MV.
- **Technical-note markers.**
  - A superscript letter is hyperlinked to the note, and each note links back to the term's first marker.
  - Markers go **in body prose only**: never in table cells, legends, callouts or the reading guide, because those are escaped.
- **Clinical figures.** The clinical version reuses a saved figure only when its visible labels are already plain: `brief_fig1` (frequency cuts) and `tipping`. It draws its own `clinical_*` versions of the known-groups, calibration and subgroup figures, because the technical report's versions carry labels such as "purposeful-bout". *(Plan refinement of spec §5.3: images are not covered by the text-based jargon check.)*
- **Reusable tooling.** Nothing in `oaireport` or `oai` mentions walking validation.
- **Dependencies.** No new R or Python dependencies, and `r/renv.lock` and `r/renv/profiles/report/renv.lock` are unchanged.
- **Commits.**
  - Signed through 1Password. If signing fails, leave the work staged and report BLOCKED; never bypass.
  - Message trailer: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Branch.** `feat/clinical-version`. Do not push.

## Review Focus

1. **A technical-note marker placed in a table cell, legend or callout** is escaped and shows as literal `#super[...]`. Expected: markers appear only in prose, and the rendered PDF has no `#super` or `{=typst}` text. Pinned in Task 8 (realdata assertion).
2. **`combined_documents` that names a document not in `documents`, has duplicates, or comes without `combined`** gives a clear manifest error. Pinned in Task 1.
3. **`clinical.qmd` rendering before the documents whose figures it reuses** gives a clear error naming the missing figure, not a broken image. Pinned in Task 7: `figure_file()` stops with the file's name, and `test_walking_validation_clinical_renders_after_the_documents_whose_figures_it_reuses` keeps the manifest order.
4. **A CI limit exactly at the null, an NA limit, or an odds ratio (null 1)** is not bold. Bold also lands on the right cell when the table has group rows. Pinned in Task 3.
5. **A banned term in the clinical main text, including tables and legends,** fails the realdata jargon check, which names the term and page. Pinned in Task 8.

---

### Task 1: `[report] combined_documents`

**Files:**
- Modify: `src/oai/manifest.py` (`ReportSpec`, `_parse_report`), `src/oai/report.py` (the join in `render_report`)
- Test: `tests/test_manifest.py`, `tests/test_report.py`

**Interfaces:**
- Produces:
  - `ReportSpec.combined_documents: tuple[str, ...] = ()`, the last field.
  - `render_report` returns every document's PDF in document order, then the combined PDF.
  - The combined PDF joins `spec.combined_documents or spec.documents`, in that order.
  - Part titles default to the joined documents' stems.

- [ ] **Step 1: Write the failing tests.**

Append to `tests/test_manifest.py`, after `test_combined_and_titles_need_documents`:

```python
SELECT_MANIFEST = DOCS_MANIFEST.replace(
    'part_titles = ["Brief", "Appendix"]',
    'part_titles = ["Brief"]\ncombined_documents = ["brief.qmd"]',
)


def test_combined_documents_parsed(tmp_path):
    spec = load_analysis(write_docs_analysis(tmp_path, SELECT_MANIFEST)).report
    assert spec.combined_documents == ("brief.qmd",)
    assert spec.part_titles == ("Brief",)


def test_combined_documents_default_to_none_selected(tmp_path):
    assert load_analysis(write_docs_analysis(tmp_path)).report.combined_documents == ()


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ('combined_documents = ["brief.qmd"]', "combined_documents = []", "combined_documents must be a non-empty list"),
        ('combined_documents = ["brief.qmd"]', 'combined_documents = "brief.qmd"', "combined_documents must be a non-empty list"),
        ('combined_documents = ["brief.qmd"]', 'combined_documents = ["other.qmd"]', "combined_documents other.qmd are not in documents"),
        ('combined_documents = ["brief.qmd"]', 'combined_documents = ["brief.qmd", "brief.qmd"]', "combined_documents has duplicates"),
        ('part_titles = ["Brief"]', 'part_titles = ["Brief", "Appendix"]', "one title per document joined"),
    ],
)
def test_invalid_combined_documents(tmp_path, old, new, message):
    root = write_docs_analysis(tmp_path, SELECT_MANIFEST.replace(old, new))
    with pytest.raises(ManifestError, match=re.escape(message)):
        load_analysis(root)


def test_combined_documents_needs_combined(tmp_path):
    manifest = DOCS_MANIFEST.replace('combined = "together.pdf"\n', "").replace(
        'part_titles = ["Brief", "Appendix"]', 'combined_documents = ["brief.qmd"]'
    )
    with pytest.raises(ManifestError, match=re.escape("combined_documents needs combined")):
        load_analysis(write_docs_analysis(tmp_path, manifest))
```

Append to `tests/test_report.py`, after `test_part_titles_default_to_document_names`:

```python
def test_combined_documents_joins_only_the_selected_in_their_order(tmp_path, quarto_env):
    from pypdf import PdfReader

    manifest = DOCS_MANIFEST.replace(
        'part_titles = ["Brief", "Appendix"]',
        'part_titles = ["Second", "First"]\ncombined_documents = ["report.qmd", "brief.qmd"]',
    )
    env = {**quarto_env, "FAKE_QUARTO_PDF": str(blank_pdf(tmp_path / "blank.pdf", 2))}
    pdfs = render_report(
        make_docs_toy(tmp_path, manifest), make_settings(tmp_path), run_missing=True,
        base_env=env, echo=quiet,
    )
    assert [p.name for p in pdfs] == ["brief.pdf", "report.pdf", "together.pdf"]
    assert top_bookmarks(pdfs[-1]) == ["Second", "First"]
    assert len(PdfReader(pdfs[-1]).pages) == 4


def test_combined_documents_can_leave_a_document_out(tmp_path, quarto_env):
    from pypdf import PdfReader

    manifest = DOCS_MANIFEST.replace(
        'part_titles = ["Brief", "Appendix"]',
        'part_titles = ["Brief"]\ncombined_documents = ["brief.qmd"]',
    )
    env = {**quarto_env, "FAKE_QUARTO_PDF": str(blank_pdf(tmp_path / "blank.pdf", 2))}
    pdfs = render_report(
        make_docs_toy(tmp_path, manifest), make_settings(tmp_path), run_missing=True,
        base_env=env, echo=quiet,
    )
    assert top_bookmarks(pdfs[-1]) == ["Brief"]
    assert len(PdfReader(pdfs[-1]).pages) == 2
```

`DOCS_MANIFEST` in `tests/test_report.py` contains the line `part_titles = ["Brief", "Appendix"]` (followed by `\n`). The `.replace` targets the text without the newline, so it works there too.

- [ ] **Step 2: Run the tests and verify they fail.**

Run: `uv run pytest -q tests/test_manifest.py tests/test_report.py -k "combined_documents"`
Expected: FAIL. `ReportSpec` has no `combined_documents`, and the key is ignored, so the invalid cases raise nothing.

- [ ] **Step 3: Implement.**

In `src/oai/manifest.py`, add a last field to `ReportSpec`:

```python
    combined_documents: tuple[str, ...] = ()  # the documents `combined` joins, in order; () = all
```

In `_parse_report`, replace the line pair

```python
    if titles and len(titles) != len(documents):
        fail("[report] part_titles needs one title per document")
```

with

```python
    selected = raw.get("combined_documents")
    if selected is not None:
        if combined is None:
            fail("[report] combined_documents needs combined")
        if not isinstance(selected, list) or not selected or not all(isinstance(d, str) for d in selected):
            fail("[report] combined_documents must be a non-empty list of documents")
        unknown = [d for d in selected if d not in documents]
        if unknown:
            fail(f"[report] combined_documents {', '.join(unknown)} are not in documents")
        if len(set(selected)) != len(selected):
            fail("[report] combined_documents has duplicates")
    joined = selected or documents
    if titles and len(titles) != len(joined):
        fail(f"[report] part_titles needs one title per document joined ({len(joined)})")
```

Add `tuple(selected or ())` as the last argument of the `ReportSpec(...)` return.

In `src/oai/report.py`, replace the body of `if spec.combined:` with:

```python
        if spec.combined:
            joined = spec.combined_documents or spec.documents
            by_document = dict(zip(spec.documents, pdfs, strict=True))
            titles = spec.part_titles or tuple(Path(d).stem for d in joined)
            echo(f"==> {analysis.name}: joining {len(joined)} PDFs into {spec.combined}")
            parts = [(title, by_document[d]) for title, d in zip(titles, joined, strict=True)]
            pdfs.append(combine_pdfs(parts, out / spec.combined))
```

The `zip(spec.documents, pdfs)` sits before the combined PDF is appended, so `pdfs` holds exactly one PDF per document.

- [ ] **Step 4: Run the tests and verify they pass.**

Run: `uv run pytest -q tests/test_manifest.py tests/test_report.py && uv run pytest -q`
Expected: PASS. The existing `test_invalid_document_sections` case that matches "one title per document" still matches.

- [ ] **Step 5: Commit.**

```bash
git add src/oai/manifest.py src/oai/report.py tests/test_manifest.py tests/test_report.py
git commit -m "feat(report): combined_documents chooses which documents the combined PDF joins

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: `oai.pdfcheck`: margin and term checks on rendered PDFs

**Files:**
- Create: `src/oai/pdfcheck.py`, `tests/test_pdfcheck.py`
- Modify: `tests/test_walking_validation_realdata.py` (use `max_right_edge`; drop `_largest_xmax`)

**Interfaces:**
- Produces:
  - `right_edge_from_bbox(bbox_html: str) -> float | None`
  - `max_right_edge(pdf: Path) -> float | None`: None when `pdftotext` is missing.
  - `find_terms_in(pages: Sequence[str], terms: Sequence[str], stop_heading: str | None = None) -> list[tuple[str, int]]`: (term, 1-based page) for each term found before the **last** occurrence of `stop_heading`.
  - `find_terms(pdf: Path, terms, stop_heading=None) -> list[tuple[str, int]]`

- [ ] **Step 1: Write the failing tests.**

Create `tests/test_pdfcheck.py`:

```python
"""Text checks on rendered PDFs."""

from oai.pdfcheck import find_terms_in, max_right_edge, right_edge_from_bbox


def test_right_edge_from_bbox():
    html = (
        '<word xMin="72.0" yMin="1" xMax="540.5" yMax="2">a</word>'
        '<word xMin="1" yMin="1" xMax="547.25" yMax="2">b</word>'
    )
    assert right_edge_from_bbox(html) == 547.25
    assert right_edge_from_bbox("<doc></doc>") is None


def test_max_right_edge_without_pdftotext(monkeypatch, tmp_path):
    monkeypatch.setattr("oai.pdfcheck.shutil.which", lambda _: None)
    assert max_right_edge(tmp_path / "x.pdf") is None


def test_find_terms_whole_words_case_insensitive():
    pages = ["A median difference, not Hodges–Lehmann.", "the bootstrapped value; BOOTSTRAP here"]
    assert find_terms_in(pages, ["Hodges–Lehmann", "bootstrap", "rank-biserial"]) == [
        ("Hodges–Lehmann", 1),
        ("bootstrap", 2),
    ]


def test_find_terms_across_a_line_break():
    pages = ["limits of\nagreement", "Hodges–\nLehmann"]
    assert find_terms_in(pages, ["limits of agreement", "Hodges–Lehmann"]) == [
        ("limits of agreement", 1),
        ("Hodges–Lehmann", 2),
    ]


def test_find_terms_stops_at_the_last_heading():
    pages = ["See Technical notes about the bootstrap.", "Results", "Technical notes\na Bootstrap: ..."]
    # page 1's mention of the heading is not the heading: the search stops at the last occurrence
    assert find_terms_in(pages, ["bootstrap"], stop_heading="Technical notes") == [("bootstrap", 1)]
    assert find_terms_in(["Results only", "Technical notes\nbootstrap"], ["bootstrap"],
                         stop_heading="Technical notes") == []
```

- [ ] **Step 2: Run the tests and verify they fail.**

Run: `uv run pytest -q tests/test_pdfcheck.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'oai.pdfcheck'`.

- [ ] **Step 3: Implement.** Create `src/oai/pdfcheck.py`:

```python
"""Checks on rendered PDFs: how far text reaches to the right, and terms that must not appear.

Used by the report tests; any analysis's documents can use them. pdftotext (poppler) and pypdf
are only needed when a check runs.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

_XMAX = re.compile(r'xMax="([0-9.]+)"')
_BROKEN_DASH = re.compile(r"([-–])\s*\n\s*")


def right_edge_from_bbox(bbox_html: str) -> float | None:
    """The largest word right edge, in points, in `pdftotext -bbox` output; None without words."""
    edges = [float(x) for x in _XMAX.findall(bbox_html)]
    return max(edges) if edges else None


def max_right_edge(pdf: Path) -> float | None:
    """The largest word right edge in a PDF, in points; None when pdftotext is unavailable."""
    if shutil.which("pdftotext") is None:
        return None
    out = subprocess.run(
        ["pdftotext", "-bbox", str(pdf), "-"], capture_output=True, text=True, check=True
    ).stdout
    return right_edge_from_bbox(out)


def _pattern(term: str) -> re.Pattern[str]:
    words = [re.escape(word) for word in term.split()]
    return re.compile(r"(?<!\w)" + r"\s+".join(words) + r"(?!\w)", re.IGNORECASE)


def find_terms_in(
    pages: Sequence[str], terms: Sequence[str], stop_heading: str | None = None
) -> list[tuple[str, int]]:
    """Each term found in the pages' text, with its 1-based page.

    Matching is case-insensitive and on whole words; a term's words may be split across lines,
    and a word broken after a hyphen or dash is rejoined. With `stop_heading`, only the text
    before its last occurrence is searched (a heading such as "Technical notes" closes a document).
    """
    texts = [_BROKEN_DASH.sub(r"\1", page) for page in pages]
    if stop_heading:
        stop = _pattern(stop_heading)
        for number in range(len(texts) - 1, -1, -1):
            matches = list(stop.finditer(texts[number]))
            if matches:
                texts = texts[:number] + [texts[number][: matches[-1].start()]]
                break
    hits = []
    for number, text in enumerate(texts, start=1):
        for term in terms:
            if _pattern(term).search(text):
                hits.append((term, number))
    return hits


def find_terms(pdf: Path, terms: Sequence[str], stop_heading: str | None = None) -> list[tuple[str, int]]:
    """`find_terms_in` over a PDF's pages (text extracted with pypdf)."""
    from pypdf import PdfReader

    return find_terms_in([page.extract_text() or "" for page in PdfReader(pdf).pages], terms, stop_heading)
```

In `tests/test_walking_validation_realdata.py`:
- Delete `_largest_xmax`.
- Add `from oai.pdfcheck import max_right_edge` to the `oai` imports.
- Replace the block `if shutil.which("pdftotext"): …` with:

```python
    for pdf in pdfs[:2]:
        edge = max_right_edge(pdf)
        if edge is not None:  # only the margin check needs poppler
            assert edge <= RIGHT_EDGE[pdf.name] + 0.01, pdf.name
```

If `re` and `subprocess` become unused, remove them. ruff will say.

- [ ] **Step 4: Run the tests and verify they pass.**

Run: `uv run pytest -q tests/test_pdfcheck.py && uv run pytest -q && uv run ruff check && uv run ruff format --check`
Expected: PASS.

Run: `uv run pytest -m realdata -q tests/test_walking_validation_realdata.py -k report_renders`
Expected: PASS.

- [ ] **Step 5: Commit.**

```bash
git add src/oai/pdfcheck.py tests/test_pdfcheck.py tests/test_walking_validation_realdata.py
git commit -m "feat: oai.pdfcheck — right-edge and term checks on rendered PDFs

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: oaireport `ci_excludes()` and `compare_table(bold =, groups =)`

**Files:**
- Create: `r/oaireport/R/significance.R`
- Modify: `r/oaireport/R/tables.R` (`compare_table`), `r/oaireport/NAMESPACE`
- Test: `r/oaireport/tests/testthat/test-tables.R`

**Interfaces:**
- Produces:
  - `ci_excludes(lo, hi, null = 0) -> logical` (recycled to a common length).
  - `compare_table(df, widths = NULL, compact = FALSE, labels = NULL, multipage = TRUE, bold = NULL, groups = NULL)`.
    - `bold` is a logical matrix with `df`'s shape.
    - `groups` is a named list like `tinytable::group_tt(i =)`: group title = the data row it goes before.
    - With `groups`, the grouping is applied inside, so bold lands on the right cells. Callers must not call `group_tt` on a table that has `bold`.

**Why `groups` moves inside.** tinytable 0.19 keys cell styles by the Typst row, where the header is row 0. It does not shift styles made before `group_tt`. Bolding must therefore come after grouping, with each data row shifted by the number of group rows at or above it. This was verified with a probe: `style_tt(i = 2)` then `group_tt(i = list(G = 1))` keeps key `"2_1"`, which now marks the first data row.

- [ ] **Step 1: Write the failing tests.** Append to `r/oaireport/tests/testthat/test-tables.R`:

```r
style_keys <- function(tab) {
  out <- tinytable::save_tt(tab, output = "typst")
  sort(regmatches(out, gregexpr('"[0-9]+_[0-9]+"(?=: )', out, perl = TRUE))[[1]])
}

test_that("ci_excludes is TRUE only when both limits sit strictly on one side of the null", {
  expect_equal(ci_excludes(c(0.1, -0.5, -0.2, 0, NA), c(0.3, -0.1, 0.4, 0.2, 0.5)),
               c(TRUE, TRUE, FALSE, FALSE, FALSE))
  expect_equal(ci_excludes(c(0.4, 0.8, 1.1), c(0.9, 1.2, 1.5), null = 1), c(TRUE, FALSE, TRUE))
  expect_equal(ci_excludes(0.2, c(0.5, NA)), c(TRUE, FALSE))
  expect_error(ci_excludes("a", 1), "numeric")
})

test_that("compare_table bolds exactly the cells marked TRUE", {
  df <- data.frame(a = c("x", "y", "z"), b = c("1", "2", "3"))
  bold <- matrix(FALSE, 3, 2); bold[2, 2] <- TRUE
  expect_equal(style_keys(compare_table(df, bold = bold)), '"2_1"')  # header is Typst row 0
  expect_equal(style_keys(compare_table(df)), character())
  expect_error(compare_table(df, bold = matrix(TRUE, 1, 2)), "bold")
  expect_error(compare_table(df, bold = matrix("x", 3, 2)), "bold")
})

test_that("bold lands on the right cell when groups add rows above it", {
  df <- data.frame(a = c("x", "y", "z"), b = c("1", "2", "3"))
  bold <- matrix(FALSE, 3, 2); bold[2, 2] <- TRUE; bold[3, 1] <- TRUE
  tab <- compare_table(df, bold = bold, groups = list(G = 1, H = 3))
  # rows: header 0, G 1, x 2, y 3, H 4, z 5
  expect_equal(style_keys(tab), c('"3_1"', '"5_0"'))
})
```

- [ ] **Step 2: Run the tests and verify they fail.**

Run: `cd r && RENV_PROFILE=report Rscript -e 'testthat::test_local("oaireport", filter = "tables")'`
Expected: FAIL with `could not find function "ci_excludes"` and `unused argument (bold = …)`.

- [ ] **Step 3: Implement.**

Create `r/oaireport/R/significance.R`:

```r
#' Whether a 95% CI excludes a null value
#'
#' TRUE when both limits sit strictly on one side of `null` (0 for differences and correlations,
#' 1 for odds ratios); FALSE when a limit equals the null or is missing. Recycled to a common
#' length.
ci_excludes <- function(lo, hi, null = 0) {
  if (!is.numeric(lo) && !all(is.na(lo)) || !is.numeric(hi) && !all(is.na(hi)) || !is.numeric(null)) {
    stop("ci_excludes(): lo, hi and null must be numeric", call. = FALSE)
  }
  n <- max(length(lo), length(hi))
  lo <- rep_len(as.numeric(lo), n); hi <- rep_len(as.numeric(hi), n)
  !is.na(lo) & !is.na(hi) & (lo > null | hi < null)
}
```

In `r/oaireport/R/tables.R`:
- Change the signature to `compare_table <- function(df, widths = NULL, compact = FALSE, labels = NULL, multipage = TRUE, bold = NULL, groups = NULL)`.
- Before `tab` is built, add:

```r
  if (!is.null(bold)) {
    bold <- as.matrix(bold)
    if (!is.logical(bold) || !identical(dim(bold), dim(df))) {
      stop("compare_table(): bold must be a logical matrix with the table's shape (",
           nrow(df), " x ", ncol(df), ")", call. = FALSE)
    }
  }
```

- After the verdict-tint loop, and before `tab` is returned, add:

```r
  if (!is.null(groups)) tab <- tinytable::group_tt(tab, i = groups)
  if (!is.null(bold)) {
    # tinytable keys styles by Typst row (header = 0) and does not shift styles made before
    # group_tt, so bold goes on after grouping, each data row moved down by the group rows above
    starts <- if (is.null(groups)) integer() else unlist(groups)
    cells <- which(bold & !is.na(bold), arr.ind = TRUE)
    for (k in seq_len(nrow(cells))) {
      row <- cells[k, 1]
      tab <- tinytable::style_tt(tab, i = row + sum(starts <= row), j = cells[k, 2], bold = TRUE)
    }
  }
```

Add `#' @param bold …` and `#' @param groups …` lines to its roxygen block, saying what the Interfaces block above says.

Append `export(ci_excludes)` to `r/oaireport/NAMESPACE`.

If the probe in Step 1's last test shows tinytable mapping `style_tt(i =)` differently, use the mapping the test proves. Write the rule you found in the code comment, and keep the test.

- [ ] **Step 4: Run the tests and verify they pass.**

Run: `cd r && RENV_PROFILE=report Rscript -e 'testthat::test_local("oaireport", stop_on_failure = TRUE)'`
Expected: PASS, with 0 failures and 0 warnings.

Run: `git diff --exit-code -- r/renv.lock r/renv/profiles/report/renv.lock`
Expected: exit 0.

- [ ] **Step 5: Commit.**

```bash
git add r/oaireport
git commit -m "feat(oaireport): ci_excludes(); compare_table() bolds cells and groups rows

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: oaireport `tech_notes()` and `standard_tech_notes()`

**Files:**
- Create: `r/oaireport/R/technical_notes.R`
- Modify: `r/oaireport/NAMESPACE`
- Test: `r/oaireport/tests/testthat/test-technical-notes.R`

**Interfaces:**
- Produces:
  - `standard_tech_notes() -> named character`. The keys are `median_difference`, `median_regression`, `wilson_ci`, `bootstrap_ci`, `trend_test`, `rank_correlation`, `sensitivity_specificity`, `predictive_values`, `youden_j`, `kappa`, `limits_of_agreement`, `misclassification_simulation`, `tipping_point` and `nondifferential`.
  - `tech_notes(entries = character(), defaults = standard_tech_notes())` returns a list with three functions:
    - `$ref(key, raw = TRUE) -> character(1)`. The marker is `#super[#link(<tn-KEY>)[LETTER]]`, plus `<tn-ref-KEY>` on the first reference. With `raw = TRUE` it is wrapped as inline raw Typst `` `…`{=typst} ``, for Markdown prose.
    - `$list(title = "Technical notes") -> character`. The notes block, as lines for a `results: asis` chunk. Write it **once**.
    - `$keys() -> character`, the keys in reference order.
  - Entries override defaults. Keys must match `^[A-Za-z][A-Za-z0-9_]*$`.
  - Internal: `note_letter(i)`, which gives a, …, z, aa, ab, ….

- [ ] **Step 1: Write the failing tests.** Create `r/oaireport/tests/testthat/test-technical-notes.R`:

```r
test_that("tech_notes letters notes in order of first reference and links both ways", {
  notes <- tech_notes(c(alpha = "First #note.", beta = "Second."), defaults = character())
  expect_equal(notes$ref("beta"), "`#super[#link(<tn-beta>)[a]]<tn-ref-beta>`{=typst}")
  expect_equal(notes$ref("alpha", raw = FALSE), "#super[#link(<tn-alpha>)[b]]<tn-ref-alpha>")
  expect_equal(notes$ref("beta", raw = FALSE), "#super[#link(<tn-beta>)[a]]")
  expect_equal(notes$keys(), c("beta", "alpha"))
  out <- paste(notes$list(), collapse = "\n")
  expect_match(out, "#heading(level: 1, numbering: none)[Technical notes]", fixed = TRUE)
  expect_match(out, '#text(weight: "bold")[a] #h(0.3em) Second. #link(<tn-ref-beta>)[↑]] <tn-beta>', fixed = TRUE)
  expect_match(out, "First \\#note.", fixed = TRUE)
  expect_lt(regexpr("<tn-beta>", out, fixed = TRUE), regexpr("<tn-alpha>", out, fixed = TRUE))
  expect_error(notes$list(), "once")
})

test_that("tech_notes rejects unknown keys and bad names, and lists only referenced notes", {
  notes <- tech_notes(c(alpha = "A."), defaults = c(beta = "B."))
  expect_error(notes$ref("gamma"), "unknown note")
  notes$ref("alpha")
  out <- paste(notes$list(), collapse = "\n")
  expect_false(grepl("<tn-beta>", out, fixed = TRUE))
  expect_error(tech_notes(c(`bad key` = "x"), defaults = character()), "key")
  expect_error(tech_notes(c("unnamed"), defaults = character()), "named")
  expect_equal(tech_notes(defaults = character())$list(), character())
})

test_that("entries override defaults, and letters continue past z", {
  expect_equal(note_letter(c(1, 26, 27, 28, 52, 53)), c("a", "z", "aa", "ab", "az", "ba"))
  notes <- tech_notes(c(kappa = "Mine."))
  notes$ref("kappa")
  expect_match(paste(notes$list(), collapse = "\n"), "Mine.", fixed = TRUE)
})

test_that("standard_tech_notes covers the common methods with plain sentences", {
  std <- standard_tech_notes()
  expect_true(all(c("median_difference", "median_regression", "wilson_ci", "bootstrap_ci", "trend_test",
                    "rank_correlation", "sensitivity_specificity", "predictive_values", "youden_j", "kappa",
                    "limits_of_agreement", "misclassification_simulation", "tipping_point",
                    "nondifferential") %in% names(std)))
  expect_true(all(nzchar(std)) && all(grepl("\\.$", std)))
})
```

- [ ] **Step 2: Run the tests and verify they fail.**

Run: `cd r && RENV_PROFILE=report Rscript -e 'testthat::test_local("oaireport", filter = "technical-notes")'`
Expected: FAIL with `could not find function "tech_notes"`.

- [ ] **Step 3: Implement.** Create `r/oaireport/R/technical_notes.R`:

```r
# Technical notes for a plain-language document: a technical term in the text carries a
# superscript letter linked to its note at the end, and each note links back to the term's first
# use. Letters are given in order of first reference; notes never referenced are left out.

#' Default note texts for common methods; a document overrides or extends them
standard_tech_notes <- function() c(
  median_difference = "Median difference: the Hodges–Lehmann estimate, the median of all differences between a member of one group and a member of the other; it is robust to skewed data.",
  median_regression = "Adjusted difference: from median (quantile) regression of the measure on the group and the listed covariates.",
  wilson_ci = "95% CI for a proportion: the Wilson score interval, which stays within 0 to 1 and behaves well for shares near either end.",
  bootstrap_ci = "Bootstrap 95% CI: participants are resampled with replacement, the estimate is recomputed each time, and the middle 95% of the results forms the interval.",
  trend_test = "Test for trend: the Jonckheere–Terpstra test of whether a measure rises across ordered groups, with a permutation p-value.",
  rank_correlation = "Rank correlation: Spearman's correlation between the ranks of two measures, from −1 to 1.",
  sensitivity_specificity = "Sensitivity: of the people the reference calls positive, the share the test also calls positive. Specificity: of the people the reference calls negative, the share the test also calls negative.",
  predictive_values = "Predictive values: of the people the test calls positive, the share the reference also calls positive (PPV); of those it calls negative, the share the reference also calls negative (NPV).",
  youden_j = "Youden's J: sensitivity + specificity − 1; 0 means the test is no better than chance and 1 means it is perfect.",
  kappa = "Agreement beyond chance: Cohen's kappa, 0 for the agreement expected by chance and 1 for perfect agreement.",
  limits_of_agreement = "Limits of agreement: the 2.5th and 97.5th percentiles of the differences between two measures (Bland–Altman).",
  misclassification_simulation = "Simulation of misclassification: a probabilistic bias analysis that repeatedly draws plausible sensitivity and specificity values, reclassifies each participant accordingly and refits the model; a simulation that implies a negative number of participants in a group is impossible and is set aside.",
  tipping_point = "Tipping-point analysis: the model is refitted over a grid of assumed sensitivity and specificity values to show where, if anywhere, the conclusion would change.",
  nondifferential = "Non-differential misclassification: misclassification that is the same in people with and without the outcome; it tends to pull an association toward no effect."
)

# a, b, …, z, aa, ab, …
note_letter <- function(i) {
  vapply(i, function(n) {
    s <- ""
    while (n > 0) {
      r <- (n - 1) %% 26
      s <- paste0(letters[r + 1], s)
      n <- (n - 1) %/% 26
    }
    s
  }, character(1))
}

#' A registry of technical notes for one document
#'
#' `entries` (named character: key = note text) override `defaults`. `$ref(key)` gives the
#' superscript marker, as inline raw Typst for Markdown prose (`raw = FALSE` for a raw Typst
#' block); use markers in body prose only, never in table cells or legends (they are escaped).
#' `$list()` writes the notes once, in order of first reference.
tech_notes <- function(entries = character(), defaults = standard_tech_notes()) {
  named_text <- function(x, what) {
    if (!is.character(x) || (length(x) && (is.null(names(x)) || any(!nzchar(names(x)))))) {
      stop("tech_notes(): ", what, " must be a named character vector", call. = FALSE)
    }
  }
  named_text(entries, "entries"); named_text(defaults, "defaults")
  notes <- defaults
  notes[names(entries)] <- entries
  bad <- names(notes)[!grepl("^[A-Za-z][A-Za-z0-9_]*$", names(notes))]
  if (length(bad)) stop("tech_notes(): key must be letters, digits and _: ", paste(bad, collapse = ", "), call. = FALSE)
  state <- new.env(parent = emptyenv())
  state$order <- character()
  state$listed <- FALSE
  ref <- function(key, raw = TRUE) {
    if (!is.character(key) || length(key) != 1 || !key %in% names(notes)) {
      stop("tech_notes(): unknown note \"", paste(key, collapse = ", "), "\"", call. = FALSE)
    }
    first <- !key %in% state$order
    if (first) state$order <- c(state$order, key)
    code <- sprintf("#super[#link(<tn-%s>)[%s]]%s", key, note_letter(match(key, state$order)),
                    if (first) sprintf("<tn-ref-%s>", key) else "")
    if (raw) sprintf("`%s`{=typst}", code) else code
  }
  list_notes <- function(title = "Technical notes") {
    if (state$listed) stop("tech_notes(): the notes are already listed; write them once", call. = FALSE)
    state$listed <- TRUE
    if (!length(state$order)) return(character())
    items <- vapply(seq_along(state$order), function(i) {
      key <- state$order[[i]]
      sprintf('#block(below: 0.6em)[#text(weight: "bold")[%s] #h(0.3em) %s #link(<tn-ref-%s>)[↑]] <tn-%s>',
              note_letter(i), typst_text(notes[[key]]), key, key)
    }, character(1))
    c("", "```{=typst}", sprintf("#heading(level: 1, numbering: none)[%s]", typst_text(title)),
      "#block[", "#set text(size: 8.5pt)", items, "]", "```", "")
  }
  list(ref = ref, list = list_notes, keys = function() state$order)
}
```

`typst_text()` escapes `/`, `-` at the start, `#` and so on. "↑" passes through. Check that the expected strings in Step 1 match what `typst_text` does to "Second." and "First #note.".

Append `export(tech_notes)` and `export(standard_tech_notes)` to `r/oaireport/NAMESPACE`.

- [ ] **Step 4: Run the tests and verify they pass.**

Run: `cd r && RENV_PROFILE=report Rscript -e 'testthat::test_local("oaireport", stop_on_failure = TRUE)'`
Expected: PASS.

Run: `git diff --exit-code -- r/renv.lock r/renv/profiles/report/renv.lock`
Expected: exit 0.

- [ ] **Step 5: Commit.**

```bash
git add r/oaireport
git commit -m "feat(oaireport): tech_notes() — superscript letters linked to technical notes and back; standard_tech_notes()

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Shared setup `report_setup.R` (the technical report's text unchanged)

**Files:**
- Create: `analyses/walking_validation/report_setup.R`
- Modify: `analyses/walking_validation/report.qmd`, `analyses/walking_validation/analysis.toml` (`assets`)

**Interfaces:**
- Produces, after `source("report_setup.R")`. Every name keeps today's definition.
  - **Results and formatters.**
    - `run`, `assumption`;
    - `num`, `count`, `pct`, `pct_range`, `named`, `or_text`, `or_interval`, `dnum`, `dnum_ci`;
    - `class_names`, `measure_names`, `outcome_names`, `model_names`, `sample_names`, `wave_names`, `wave`;
    - `cls`, `pick`, `youden`.
  - **Definitions** (from the `legends` chunk, everything before `legend <- list()`).
    - `fmt`, `cap1`, `combination`, `waves_at`, `averaged`, `cutpoint`, `purposeful_minutes`, `valid_day`;
    - `yes_without`, `item_def`, `no_amount_group`;
    - `walker_rule`, `rule_short`, `device_def`, `per_week`, `device_detail`, `measures_def`;
    - `pase_threshold`, `pase_def`, `reps_text`, `adjusted_def`.
  - **Pairing** (from `pase-pairing`): `combined_text`, `pairing`.
  - **Trend-test settings** (from `dose-table`): `jt_b`, `jt_floor`, `round_up`.
  - **Components lookups** (the whole `components-setup` chunk).
    - `cp`, `ci`, `hx`, `answer_labels`;
    - `num_na`, `count_na`, `comp_p`, `cp_get`, `ci_get`, `est_ci`, `pct_ci`, `med_iqr`;
    - `comp_visits`, `boot_text`, `comp_paired`, `comp_device`, `comp_population`, `comp_wave`, `pase_walker_rule`.
  - **Cut names** (from `components-cuts`): `component_cuts`, `cut_names`.
- `lab`, `threshold`, `flag_mark` and all bias-text variables stay in `report.qmd`.

- [ ] **Step 1: Record the baseline.**

```bash
mkdir -p /private/tmp/claude-501/-Users-spiewart-OAI/dfbe067a-077f-40ca-8e7f-4be05be5b6e7/scratchpad/clinical-plan
uv run oai report walking_validation
pdftotext ~/oai-work/results/walking_validation/report/report.pdf /private/tmp/claude-501/-Users-spiewart-OAI/dfbe067a-077f-40ca-8e7f-4be05be5b6e7/scratchpad/clinical-plan/report-before.txt
```

- [ ] **Step 2: Move the definitions.**

Create `analyses/walking_validation/report_setup.R`. It opens with this comment:

```r
# Shared by the walking-validation documents (report.qmd, clinical.qmd): the run's results, the
# assumption accessor, number formatters, name maps, result lookups and the plain definitions of
# the walker, the device walker and the PASE walker. Source it first; nothing here prints.
```

Then move the code listed under Interfaces from `report.qmd`, **cut and pasted unchanged, in this order**:
1. the `setup` chunk's lines from `run <- …` to `youden <- …`, without `lab <- …` and its comment, and without `flag_mark` and `threshold` (they stay);
2. the `legends` chunk's lines before `legend <- list()`;
3. from `pase-pairing`: `combined_text` and `pairing`. Delete the duplicate `combination <- …` there; it is now defined once, under 2;
4. from `dose-table`: `jt_b`, `jt_floor` and `round_up`;
5. the whole `components-setup` chunk body;
6. from `components-cuts`: `component_cuts` and `cut_names`.

In `report.qmd`, the `setup` chunk now starts with `source("report_setup.R")`, followed by what stays: `flag_mark`, `lab` with its comment, `threshold`, and the bias-text code. Leave every other chunk's remaining code where it is. Delete the now-empty `components-setup` chunk.

Do not change any text. In `analyses/walking_validation/analysis.toml`, add `"report_setup.R"` to `[report] assets`.

- [ ] **Step 3: Verify the report is identical.**

```bash
uv run oai report walking_validation
pdftotext ~/oai-work/results/walking_validation/report/report.pdf /private/tmp/claude-501/-Users-spiewart-OAI/dfbe067a-077f-40ca-8e7f-4be05be5b6e7/scratchpad/clinical-plan/report-after.txt
diff /private/tmp/claude-501/-Users-spiewart-OAI/dfbe067a-077f-40ca-8e7f-4be05be5b6e7/scratchpad/clinical-plan/report-before.txt /private/tmp/claude-501/-Users-spiewart-OAI/dfbe067a-077f-40ca-8e7f-4be05be5b6e7/scratchpad/clinical-plan/report-after.txt && echo identical
```

Expected: `identical`. If R reports an undefined object, a moved definition depends on something that still sits later in `report.qmd`. Move that dependency too, unchanged.

Run: `uv run pytest -q tests/test_analyses.py && uv run pytest -m realdata -q tests/test_walking_validation_realdata.py -k report_renders`
Expected: PASS.

- [ ] **Step 4: Commit.**

```bash
git add analyses/walking_validation/report_setup.R analyses/walking_validation/report.qmd analyses/walking_validation/analysis.toml
git commit -m "refactor(walking_validation): shared report_setup.R for the result lookups and definitions; technical report text unchanged

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: The brief: neutral framing and an introduction to the sensitivity analysis

**Files:**
- Modify: `analyses/walking_validation/brief.qmd`, `tests/test_walking_validation_realdata.py`

**Interfaces:**
- Consumes:
  - `run$bias_tipping` (columns `outcome`, `se`, `sp`, `or`, `excludes_1`);
  - `run$lo2022_t2` (columns `metric`, `published`);
  - `oaireport::parse_or()`;
  - `oai.pdfcheck.find_terms` (Task 2).

- [ ] **Step 1: Write the failing realdata assertion.**

In `test_walking_validation_report_renders`, after the NA checks, add:

```python
    # the brief frames the Lo et al. 2022 analysis neutrally (spec 2026-10-05 §1, §3)
    assert find_terms(pdfs[0], ["bias", "correction", "corrected"], stop_heading="References") == []
```

Add `find_terms` to the `oai.pdfcheck` import.

Run: `uv run pytest -m realdata -q tests/test_walking_validation_realdata.py -k report_renders`
Expected: FAIL. The brief contains "bias" and "correction".

- [ ] **Step 2: Edit `brief.qmd`.**

1. **Setup chunk.** Add:

   ```r
   # Lo et al. 2022's published new-pain odds ratio, and the tipping-point grid's new-pain cells
   t2 <- run$lo2022_t2
   published_or <- oaireport::parse_or(t2$published[t2$metric == "t2.new_pain.or_adj"])$or
   grid_np <- run$bias_tipping[run$bias_tipping$outcome == "new_pain" & !is.na(run$bias_tipping$or), ]
   grid_holds <- sum(grid_np$excludes_1)
   grid_feasible <- nrow(grid_np)
   grid_se_floor <- min(grid_np$se)
   ```

2. **Lead paragraph.** After its first sentence (ending `[@lo2022].`), insert:

   ```
   In that paper, walkers had about `r pct(1 - published_or)` lower odds of developing frequent knee pain; we also asked how sensitive that association is to how walkers are classified.
   ```

3. **Fourth sidebar result** (chunk `page1`, the `results` data frame). Replace the 1/J value and label with:
   - value: `sprintf("%d of %d", grid_holds, grid_feasible)`
   - label: `sprintf("plausible accuracy settings (sensitivity %s or more) in which the walking–knee-pain association in Lo et al. 2022 holds", num(grid_se_floor))`
4. **Wording.** Run `grep -n -i "bias\|correct" analyses/walking_validation/brief.qmd`. Every hit in prose, the ask, callouts, captions or the roles table gets the neutral form below. Bib keys and code identifiers stay.

   | Now | Becomes |
   |---|---|
   | sidebar ask "…and re-run the validation and the bias analysis…" | "…and re-run the validation and the classification sensitivity analysis…" |
   | page 3 paragraph starting **Why it matters for Lo et al. 2022.** | the paragraph below |
   | Figure 4 caption "…1/J is the factor by which a record-level misclassification correction scales the difference in walking prevalence between outcome groups, and its sampling error; the interval comes from J's 95% CI." | "…1/J shows how much a re-estimate that allows for misclassification would multiply the difference in walking between people with and without the outcome — how much the re-estimate depends on the walker definition; the interval comes from J's 95% CI." |
   | page 4 aim "…and redo the bias analysis of Lo et al. 2022…" | "…and revisit the associations in Lo et al. 2022…" |
   | roles table "the Lo et al. 2022 bias analysis" | "the Lo et al. 2022 sensitivity analysis" |
   | "Already built" box "…validation and bias analyses." | "…validation and sensitivity analyses." |
   | page 5 appendix line | the appendix pointer below |

   The new page 3 paragraph:

   ```
   **How sensitive is the Lo et al. 2022 association to classification?** If some participants were misclassified, a re-estimate that allows for it divides the gap in walking between people with and without the outcome by Youden's J. With the walker definition in use, that multiplies the gap by `r num(correction[[1]], 1)`; with the strictest frequency-based definition, by `r num(correction[[2]], 1)`, so a stricter definition gives a steadier re-estimate. If misclassification is the same in people with and without the outcome, the walking–knee-pain association holds in `r grid_holds` of `r grid_feasible` plausible accuracy settings (appendix).
   ```

5. **Timing paragraph** ("Timing is a second gap: …"). Append:

   ```
   The question also asks about a habit of walking for exercise since age 50, the device one week of current activity, so the two may measure different things.
   ```

6. **Appendix pointers.** Both the page-1 italic line and the page-5 line become:

   *The appendix summarises every result for clinical readers; the full technical report is available on request.*

   On page 5 keep the bold lead: **Appendix.** The appendix summarises…

7. **Page 1 fit.** Render. If page 1 no longer ends on the appendix pointer, lower Figure 1's height in `save_figure(fig1, "brief_fig1", "1col", height = …)` by 0.1 in at a time until it does, without going below 3.0.

- [ ] **Step 3: Verify.**

```bash
uv run oai report walking_validation
swift /private/tmp/claude-501/-Users-spiewart-OAI/dfbe067a-077f-40ca-8e7f-4be05be5b6e7/scratchpad/pdfcheck/page.swift ~/oai-work/results/walking_validation/report/brief.pdf 1 /private/tmp/claude-501/-Users-spiewart-OAI/dfbe067a-077f-40ca-8e7f-4be05be5b6e7/scratchpad/clinical-plan/brief_p1.png
```

Read pages 1 and 3 as PNG. Check:
- the new lead sentence;
- the sidebar's robustness item;
- page 1 ending on the appendix pointer;
- the brief still 5 pages.

Run: `uv run pytest -m realdata -q tests/test_walking_validation_realdata.py -k report_renders`
Expected: PASS.

- [ ] **Step 4: Commit.**

```bash
git add analyses/walking_validation/brief.qmd tests/test_walking_validation_realdata.py
git commit -m "feat(walking_validation): brief introduces the Lo et al. 2022 association and frames the classification sensitivity analysis neutrally

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: The clinical version: front page and Part 1, and the sent PDF

**Files:**
- Create: `analyses/walking_validation/clinical.qmd`
- Modify: `analyses/walking_validation/analysis.toml` (`[report]`), `tests/test_walking_validation_realdata.py`

**Interfaces:**
- Consumes:
  - `report_setup.R` (Task 5);
  - `oaireport::tech_notes`, `ci_excludes`, `compare_table(bold =, groups =)` (Tasks 3–4);
  - `fmt_ci`, `reading_guide`, `numberer`, `figure_group`, `table_note`, `theme_oai`, `save_figure`, `brief_colours`, `oai_font`;
  - `combined_documents` (Task 1).
- Produces (Task 8 appends to the same file and uses these):
  - `clinical.qmd`;
  - its `setup` objects: `lab`, `notes`, `colours`, `cnum()`, `cnum_ci()`, `plain_measures`, `figure_file()`, `bold_rule`, `class_table()`.

- [ ] **Step 1: Wire the manifest and write the failing realdata assertions.**

In `analyses/walking_validation/analysis.toml`, replace `[report]` with:

```toml
[report]
documents = ["brief.qmd", "report.qmd", "clinical.qmd"]
combined = "walking_validation_brief.pdf"
combined_documents = ["brief.qmd", "clinical.qmd"]
part_titles = ["Brief", "Appendix: results"]
runs = ["default"]
assets = ["ASSUMPTIONS.md", "references.bib", "report_setup.R"]
local_assets = ["brief.local.yml"]
```

`report.qmd` renders before `clinical.qmd`, because the clinical version reuses figures the brief and the report save.

Append to `tests/test_analyses.py`, which already imports `load_analysis` and defines `REPO`:

```python
def test_walking_validation_clinical_renders_after_the_documents_whose_figures_it_reuses():
    # clinical.qmd shows figures/brief_fig1.png (brief.qmd) and figures/tipping.png (report.qmd)
    documents = load_analysis(REPO / "analyses" / "walking_validation").report.documents
    assert documents.index("clinical.qmd") > documents.index("brief.qmd")
    assert documents.index("clinical.qmd") > documents.index("report.qmd")
```

Add `tests/test_analyses.py` to this task's commit.

In `test_walking_validation_report_renders`, change the expectations to:

```python
    pdfs = render_report(analysis, settings, echo=lambda _: None)
    names = [p.name for p in pdfs]
    assert names == ["brief.pdf", "report.pdf", "clinical.pdf", "walking_validation_brief.pdf"]
    pages = {p.name: len(PdfReader(p).pages) for p in pdfs}
    assert pages["brief.pdf"] <= 6, pages
    assert pages["report.pdf"] <= 18, pages
    assert pages["clinical.pdf"] <= 12, pages
    assert pages["walking_validation_brief.pdf"] == pages["brief.pdf"] + pages["clinical.pdf"]
```

Run the NA checks over `pdfs[:3]`, and use `_top_bookmarks(pdfs[3]) == ["Brief", "Appendix: results"]`. Add `"clinical.pdf": 550.8` to `RIGHT_EDGE`, and run the margin loop over `pdfs[:3]`. Keep the placeholder check on `pdfs[0]` and the brief `find_terms` check.

Create `clinical.qmd` with just its YAML and an empty body, then render to see the test fail.

Run: `uv run pytest -m realdata -q tests/test_walking_validation_realdata.py -k report_renders`
Expected: FAIL on the bookmark or page-count assertions until the document has content. A Quarto error is acceptable too.

- [ ] **Step 2: Write `clinical.qmd` (front page and Part 1).**

The YAML follows. Copy the line in `brief.qmd`'s `include-in-header` that fixes the reference titles' "?." punctuation **verbatim** into the marked place. Also copy the brief's raw Typst block that sets `#set par(justify: false)` at the top of the body.

````markdown
---
title: "Walking question and accelerometry in the OAI: results"
subtitle: "Appendix to the brief: every result in plain language. The full technical report is available on request."
mainfont: Arial
fontsize: 10pt
brand:
  typography:
    headings:
      color: "#0b2e59"
bibliography: references.bib
bibliographystyle: american-medical-association
format:
  typst:
    papersize: us-letter
    margin:
      x: 0.85in
      y: 0.75in
    include-in-header:
      text: |
        #set text(hyphenate: false, overhang: false)
        #set bibliography(title: [References])
        #set page(footer: context align(center, text(size: 8pt, fill: luma(90))[Appendix — page #counter(page).display()]))
        <the brief's reference-title punctuation show rule, copied verbatim>
execute:
  echo: false
  warning: false
  message: false
knitr:
  opts_chunk:
    dev: cairo_pdf
    fig-width: 7
---

```{=typst}
#set par(justify: false)
```

```{r setup}
source("report_setup.R")
lab <- oaireport::numberer("A")
colours <- oaireport::brief_colours
notes <- oaireport::tech_notes(c(
  bootstrap_ci = sprintf("Bootstrap 95%% CI: participants are resampled with replacement %s times, the estimate is recomputed each time, and the middle 95%% of the results forms the interval.", fmt(assumption("validity.bootstrap_reps"))),
  trend_test = sprintf("Test for trend: the Jonckheere–Terpstra test of whether a measure rises across ordered groups; its p-value comes from %s random permutations of the group labels.", count(jt_b))
))
# Device measures per day: counts without decimals, minutes to 1 decimal
cnum <- function(x, measure) ifelse(measure == "counts_per_day", num(x, 0), num(x, 1))
cnum_ci <- function(est, lo, hi, measure) {
  ifelse(measure == "counts_per_day", oaireport::fmt_ci(est, lo, hi, 0), oaireport::fmt_ci(est, lo, hi, 1))
}
plain_measures <- c(purposeful_min = sprintf("Minutes in bouts of %s+ minutes", purposeful_minutes),
                    counts_per_day = "Activity counts", light_min = "Light-activity minutes")
bold_rule <- "Bold: the 95% CI excludes no difference (0, or 1 for odds ratios)."
# A figure another document saved (the brief and report.qmd render before this document)
figure_file <- function(name, width = "100%") {
  path <- file.path("figures", paste0(name, ".png"))
  if (!file.exists(path)) {
    stop("clinical.qmd: ", path, " is missing; the document that saves it must render before clinical.qmd ([report] documents)", call. = FALSE)
  }
  c("", "```{=typst}", sprintf('#image("%s", width: %s)', path, width), "```", "")
}
# Sensitivity, specificity, predictive values and Youden's J in one sample (no bold: no null)
class_table <- function(sample) {
  get <- function(m, col = "estimate") pick(sample, m, col)
  rows <- c(se = "Sensitivity", sp = "Specificity", ppv = "Positive predictive value", npv = "Negative predictive value")
  data.frame(
    Measure = c(unname(rows), "Youden's J"),
    `Estimate (95% CI)` = c(vapply(names(rows), function(m) oaireport::fmt_ci(get(m), get(m, "lo"), get(m, "hi")), character(1)),
                            num(youden(sample))),
    `Based on` = c(vapply(names(rows), function(m) sprintf("%s of %s", count(get(m, "k")), count(get(m, "n"))), character(1)),
                   "sensitivity + specificity − 1"),
    check.names = FALSE)
}
flow <- stats::setNames(run$flow$persons, run$flow$step)
n_val <- run$metrics[["sample.validation.persons"]]
n_walk <- run$metrics[["sample.validation.walkers"]]
n_lo <- run$metrics[["sample.lo_subset.persons"]]
kg <- run$validity_known_groups[run$validity_known_groups$sample == "validation", ]
kg_bout <- kg[kg$measure == "purposeful_min", ]
j_strict <- ci_get("validation", "times", "cut3", "j")
grid_np <- run$bias_tipping[run$bias_tipping$outcome == "new_pain" & !is.na(run$bias_tipping$or), ]
```

## Key points

- `r count(n_val)` participants answered the 96-month question on walking for exercise and had accelerometer data at 48 or 72 months; `r pct(n_walk / n_val)` said they walk.
- People who said they walk recorded a median of `r num(kg_bout$hl, 1)` more minutes a day in bouts of `r purposeful_minutes`+ minutes (95% CI `r num(kg_bout$hl_lo, 1)`–`r num(kg_bout$hl_hi, 1)`).
- The yes/no answer separates device-defined walkers poorly (sensitivity `r num(pick("validation", "se"))`, specificity `r num(pick("validation", "sp"))`, Youden's J `r num(youden("validation"))`); asking how often helps (J `r num(j_strict)` for walking `r tolower(cut_names("times")[["cut3"]])`).
- In the Lo et al. 2022 participants, if misclassification is the same in people with and without the outcome, the association between walking and less new frequent knee pain holds in `r sum(grid_np$excludes_1)` of `r nrow(grid_np)` plausible accuracy settings.
- Activity counts are not specific to walking; a step-based device measure would show whether the question and the device measure the same thing.

```{r words}
#| results: asis
cat(oaireport::reading_guide(c(
  `Walker (by the question)` = "answered yes to the 96-month question “walked for exercise since age 50” (at least 20 minutes a day, at least 10 times).",
  `Device-defined walker` = sprintf("the accelerometer recorded %s; a bout is %s or more minutes of moderate-to-vigorous activity.", rule_short, purposeful_minutes),
  `PASE walker` = if (pase_threshold == 0) "reported walking outside the home on at least one day in the past 7 days (PASE, the Physical Activity Scale for the Elderly)." else sprintf("a PASE walking score above %s (PASE, the Physical Activity Scale for the Elderly).", fmt(pase_threshold)),
  `Sensitivity` = "of the people the device calls walkers, the share who said they walk.",
  `Specificity` = "of the people the device calls non-walkers, the share who said they don't.",
  `Predictive values` = "of the people who said they walk, the share the device calls walkers (PPV); of those who said they don't, the share it calls non-walkers (NPV).",
  `Youden's J` = "sensitivity + specificity − 1: 0 means no better than chance, 1 means perfect.",
  `95% CI` = "the 95% confidence interval, written as 0.89 (0.86–0.91)."),
  notation = paste(bold_rule, "Letters in the text (a, b, …) link to the technical notes at the end."),
  title = "Words used in this appendix"), sep = "\n")
```

```{r who}
oaireport::compare_table(data.frame(
  Part = c("Part 1. Does the walking question agree with the device?", "Part 2. What the agreement means for Lo et al. 2022"),
  Who = c("Answered the walking question and have accelerometer data at 48 or 72 months",
          "Of those, members of the Lo et al. 2022 cohort"),
  Participants = count(c(n_val, n_lo)), check.names = FALSE), widths = c(2.4, 3, 1), multipage = FALSE)
```

```{=typst}
#pagebreak()
```

# Part 1. Does the walking question agree with the device?

This part uses all `r count(n_val)` participants with a walking answer and accelerometer data.

## Who was studied

```{r a-flow}
oaireport::compare_table(data.frame(
  Group = c("Answered the walking question (96 months)", "…with accelerometer data at 48 or 72 months",
            "Said they walk", "Said they don't", "Walkers by the device"),
  Participants = count(c(flow[["answered_walking_item"]], flow[["with_valid_device_wave"]], n_walk, n_val - n_walk,
                         run$metrics[["sample.validation.device_walkers"]])),
  check.names = FALSE), widths = c(4, 1.2), multipage = FALSE)
```

```{r note-a-flow}
#| results: asis
cat(oaireport::table_note(sprintf("Participants of the Osteoarthritis Initiative who answered the walking question at the 96-month visit, and of those the ones with usable accelerometer data at the 48- or 72-month visit (%s).", valid_day), label = lab("Table")), sep = "\n")
```

## Do people who say they walk move more?

People who said they walk recorded more activity than those who said they don't on `r sum(oaireport::ci_excludes(kg$hl_lo, kg$hl_hi))` of `r nrow(kg)` device measures. Table A2 gives the median difference`r notes$ref("median_difference")` with its 95% CI`r notes$ref("bootstrap_ci")`, and the difference adjusted for age, sex and body-mass index`r notes$ref("median_regression")`; Figure A1 shows the spread.

```{r a-known-groups}
kg_table <- data.frame(
  `Device measure, per day` = named(kg$measure, plain_measures),
  walk = cnum(kg$median_walkers, kg$measure),
  dont = cnum(kg$median_nonwalkers, kg$measure),
  `Difference (95% CI)` = cnum_ci(kg$hl, kg$hl_lo, kg$hl_hi, kg$measure),
  `Adjusted difference (95% CI)` = cnum_ci(kg$adj_diff, kg$adj_lo, kg$adj_hi, kg$measure),
  check.names = FALSE)
names(kg_table)[2:3] <- c(sprintf("Said they walk, median (n = %s)", count(kg$n_walkers[1])),
                          sprintf("Said they don't, median (n = %s)", count(kg$n_nonwalkers[1])))
kg_bold <- cbind(FALSE, FALSE, FALSE, oaireport::ci_excludes(kg$hl_lo, kg$hl_hi), oaireport::ci_excludes(kg$adj_lo, kg$adj_hi))
oaireport::compare_table(kg_table, widths = c(2.2, 1.5, 1.5, 1.7, 1.7), multipage = FALSE, bold = kg_bold)
```

```{r note-a-known-groups}
#| results: asis
cat(oaireport::table_note(paste("Validation sample. Medians are per day of accelerometer wear; the difference is people who said they walk minus those who said they don't, and the adjusted difference allows for age, sex and body-mass index.", bold_rule), label = lab("Table")), sep = "\n")
```

```{r a-known-groups-figure}
#| fig-height: 2.6
#| results: asis
cat(oaireport::figure_group(), sep = "\n")
kgf <- data.frame(
  measure = rep(kg$measure, 2),
  group = rep(c("Said they walk", "Said they don't"), each = nrow(kg)),
  median = c(kg$median_walkers, kg$median_nonwalkers),
  q25 = c(kg$q25_walkers, kg$q25_nonwalkers), q75 = c(kg$q75_walkers, kg$q75_nonwalkers))
kgf$measure <- factor(named(kgf$measure, plain_measures), levels = unname(plain_measures))
fig_kg <- ggplot2::ggplot(kgf, ggplot2::aes(median, group, colour = group)) +
  ggplot2::geom_pointrange(ggplot2::aes(xmin = q25, xmax = q75), size = 0.3) +
  ggplot2::facet_wrap(~measure, scales = "free_x", ncol = 3) +
  ggplot2::scale_colour_manual(values = c(`Said they walk` = colours[["item"]], `Said they don't` = colours[["muted"]]), guide = "none") +
  ggplot2::labs(x = "Median (interquartile range), per day", y = NULL) + oaireport::theme_oai()
oaireport::save_figure(fig_kg, "clinical_known_groups", "2col", height = 2.6)
print(fig_kg)
cat(oaireport::table_note("Validation sample. Point: median; bar: interquartile range (the middle half of participants).", label = lab("Figure"), close_group = TRUE), sep = "\n")
```

## Does more reported walking go with more recorded activity?

Among people who said they walk, those reporting more lifetime walking sessions recorded more activity. Table A3 gives a test for trend`r notes$ref("trend_test")` across the three groups.

```{r a-dose}
dz <- run$validity_dose[run$validity_dose$sample == "validation", ]
dose_table <- data.frame(
  `Device measure, per day` = named(dz$measure, plain_measures),
  none = cnum(dz$median_none, dz$measure), lower = cnum(dz$median_lower, dz$measure),
  upper = cnum(dz$median_upper, dz$measure), `Test for trend, p` = comp_p(dz$jt_p), check.names = FALSE)
names(dose_table)[2:4] <- c(sprintf("Said they don't (n = %s)", count(dz$n_none[1])),
                            sprintf("Fewer sessions (n = %s)", count(dz$n_lower[1])),
                            sprintf("More sessions (n = %s)", count(dz$n_upper[1])))
dose_bold <- cbind(matrix(FALSE, nrow(dz), 4), !is.na(dz$jt_p) & dz$jt_p < 0.05)
oaireport::compare_table(dose_table, widths = c(2.2, 1.4, 1.4, 1.4, 1.2), multipage = FALSE, bold = dose_bold)
```

```{r note-a-dose}
#| results: asis
cat(oaireport::table_note(sprintf("Validation sample; medians per day. Walkers are split at the %s of lifetime walking sessions (years × months a year × times a month, from their answers). Bold p: the measure rises across the three groups (p < 0.05).", assumption("exposure.amount_split")), label = lab("Table")), sep = "\n")
```

## How well does “yes” pick out walkers by the device?

Table A4 gives the sensitivity and specificity`r notes$ref("sensitivity_specificity")` of the answer against the device, with 95% CIs`r notes$ref("wilson_ci")`, the predictive values`r notes$ref("predictive_values")`, and Youden's J`r notes$ref("youden_j")`.

```{r a-class}
oaireport::compare_table(class_table("validation"), widths = c(2.6, 2, 2.2), multipage = FALSE)
```

```{r note-a-class}
#| results: asis
cat(oaireport::table_note("Validation sample, against the device-defined walker. “Based on”: the count behind each share. Sensitivity, specificity and the predictive values are never bold; Youden's J has no CI here (Table A5 gives J with CIs for each definition).", label = lab("Table")), sep = "\n")
```

## Does asking how often help?

Defining walkers by how often they walk, rather than by any walking, raises Youden's J for both the walking question and the PASE walking item (Table A5, Figure A2).

```{r a-cuts}
freq_rows <- function(get, names_k) do.call(rbind, lapply(names(names_k), function(k) data.frame(
  Definition = names_k[[k]],
  Sensitivity = oaireport::fmt_ci(get(k, "se"), get(k, "se", "lo"), get(k, "se", "hi")),
  Specificity = oaireport::fmt_ci(get(k, "sp"), get(k, "sp", "lo"), get(k, "sp", "hi")),
  `Youden's J (95% CI)` = oaireport::fmt_ci(get(k, "j"), get(k, "j", "lo"), get(k, "j", "hi")),
  bold_j = oaireport::ci_excludes(get(k, "j", "lo"), get(k, "j", "hi")), check.names = FALSE)))
item_names <- cut_names("times", prefix = "Walks at least")
pase_names <- cut_names("pase", prefix = "Walked at least")
blocks <- c(list(freq_rows(function(k, m, col = "estimate") ci_get("validation", "times", k, m, col), item_names)),
            lapply(comp_visits, function(v) freq_rows(function(k, m, col = "estimate") cp_get(v, "frequency", "device_walker", k, m, col), pase_names)))
titles <- c("Walking question: times per month", sprintf("PASE: days walked in the past week, %s", wave(comp_visits)))
freq <- do.call(rbind, blocks)
starts <- cumsum(c(1, vapply(blocks, nrow, integer(1))))[seq_along(blocks)]
freq_bold <- cbind(matrix(FALSE, nrow(freq), 3), freq$bold_j)
freq$bold_j <- NULL
oaireport::compare_table(freq, widths = c(2.4, 1.6, 1.6, 1.8), multipage = FALSE, bold = freq_bold,
                         groups = as.list(stats::setNames(starts, titles)))
```

```{r note-a-cuts}
#| results: asis
cat(oaireport::table_note(paste("Each row defines walkers by one answer cut-off and compares them with the device-defined walker: the walking question in the validation sample, PASE at each accelerometer visit (48 or 72 months).", bold_rule), label = lab("Table")), sep = "\n")
```

```{r a-cuts-figure}
#| results: asis
cat(oaireport::figure_group(), sep = "\n")
cat(figure_file("brief_fig1", width = "70%"), sep = "\n")
cat(oaireport::table_note("The definitions of Table A5, each placed by its sensitivity and 1 − specificity. Further up and to the left is better agreement; grey dashed lines join points of equal Youden's J (value above the top edge; J = 0 is chance). Triangles: the definitions in use (any walking).", label = lab("Figure"), close_group = TRUE), sep = "\n")
```

PASE also asks how many hours a day people walked. Days × hours gives an estimate of weekly walking, which Table A6 compares with the device's minutes in bouts, as a rank correlation`r notes$ref("rank_correlation")`, a median difference, and agreement beyond chance`r notes$ref("kappa")` on walking `r fmt(assumption("reference.min_bout_minutes_per_week"))`+ minutes a week.

```{r a-weekly}
guide <- assumption("reference.min_bout_minutes_per_week")
wk <- do.call(rbind, lapply(comp_visits, function(v) {
  r <- function(level, stat, col = "estimate") cp_get(v, "weekly", "purposeful_week", level, stat, col)
  data.frame(
    Visit = wave(v),
    `Rank correlation (95% CI)` = oaireport::fmt_ci(r("all", "rho"), r("all", "rho", "lo"), r("all", "rho", "hi")),
    diff = oaireport::fmt_ci(r("all", "median_diff"), r("all", "median_diff", "lo"), r("all", "median_diff", "hi"), 0),
    kappa = oaireport::fmt_ci(r("guideline", "kappa"), r("guideline", "kappa", "lo"), r("guideline", "kappa", "hi")),
    n = count_na(r("all", "median_diff", "n")),
    b_rho = oaireport::ci_excludes(r("all", "rho", "lo"), r("all", "rho", "hi")),
    b_diff = oaireport::ci_excludes(r("all", "median_diff", "lo"), r("all", "median_diff", "hi")),
    b_kappa = oaireport::ci_excludes(r("guideline", "kappa", "lo"), r("guideline", "kappa", "hi")),
    check.names = FALSE)
}))
wk_bold <- cbind(FALSE, wk$b_rho, wk$b_diff, wk$b_kappa, FALSE)
wk <- wk[c("Visit", "Rank correlation (95% CI)", "diff", "kappa", "n")]
names(wk)[3:4] <- c("Reported − device, median minutes a week (95% CI)", sprintf("Agreement on %s+ minutes a week, kappa (95% CI)", fmt(guide)))
oaireport::compare_table(wk, widths = c(1.1, 1.8, 2, 2, 0.8), multipage = FALSE, bold = wk_bold)
```

```{r note-a-weekly}
#| results: asis
cat(oaireport::table_note(paste("Participants with a PASE walking answer and accelerometer data at the same visit. Reported weekly walking: days × hours a day from PASE; device: minutes a week in bouts of", purposeful_minutes, "or more minutes.", bold_rule), label = lab("Table")), sep = "\n")
```

```{r a-calibration}
#| fig-height: 2.6
#| results: asis
cat(oaireport::figure_group(), sep = "\n")
cal <- cp[cp$component == "weekly" & cp$comparator == "purposeful_week" & cp$statistic == "median", ]
cal$level <- factor(cal$level, levels = unique(cal$level))
cal$visit_name <- wave(cal$visit)
fig_cal <- ggplot2::ggplot(cal, ggplot2::aes(level, estimate)) +
  ggplot2::geom_pointrange(ggplot2::aes(ymin = lo, ymax = hi), colour = colours[["pase"]], size = 0.3) +
  ggplot2::facet_wrap(~visit_name) +
  ggplot2::labs(x = "Weekly walking reported on PASE (hours a week)",
                y = sprintf("Device minutes a week\nin bouts of %s+ minutes", purposeful_minutes)) +
  oaireport::theme_oai()
oaireport::save_figure(fig_cal, "clinical_calibration", "2col", height = 2.6)
print(fig_cal)
cat(oaireport::table_note("Point: median; bar: interquartile range of the device's minutes a week, within each band of reported weekly walking. A report that tracked the device would show medians rising from left to right.", label = lab("Figure"), close_group = TRUE), sep = "\n")
```

## How does PASE compare?

```{r a-pase}
pz <- run$validity_pase
pz$visit <- sprintf("%02d", as.integer(pz$visit))
pv <- function(v, measure, stat, col = "estimate") {
  x <- pz[pz$visit == v & pz$measure == measure & pz$statistic == stat, col]
  if (length(x) == 1) x else NA
}
pase_visits <- unique(pz$visit)
pt <- do.call(rbind, lapply(pase_visits, function(v) data.frame(
  Visit = wave(v),
  Sensitivity = oaireport::fmt_ci(pv(v, "device_walker", "se"), pv(v, "device_walker", "se", "lo"), pv(v, "device_walker", "se", "hi")),
  Specificity = oaireport::fmt_ci(pv(v, "device_walker", "sp"), pv(v, "device_walker", "sp", "lo"), pv(v, "device_walker", "sp", "hi")),
  `Youden's J` = num(pv(v, "device_walker", "se") + pv(v, "device_walker", "sp") - 1),
  rho = oaireport::fmt_ci(pv(v, "purposeful_min", "rho"), pv(v, "purposeful_min", "rho", "lo"), pv(v, "purposeful_min", "rho", "hi")),
  b_rho = oaireport::ci_excludes(pv(v, "purposeful_min", "rho", "lo"), pv(v, "purposeful_min", "rho", "hi")),
  check.names = FALSE)))
pt_bold <- cbind(matrix(FALSE, nrow(pt), 4), pt$b_rho)
pt$b_rho <- NULL
names(pt)[5] <- "Rank correlation with device bout minutes (95% CI)"
oaireport::compare_table(pt, widths = c(1.1, 1.7, 1.7, 1, 2.2), multipage = FALSE, bold = pt_bold)
```

```{r note-a-pase}
#| results: asis
cat(oaireport::table_note(paste("The PASE walker against the device-defined walker at each PASE visit. The 96-month visit has no accelerometer data of its own and is compared with the participant's accelerometer visits.", bold_rule), label = lab("Table")), sep = "\n")
```

```{r notes-list}
#| results: asis
cat(notes$list(), sep = "\n")
```
````

Three notes on this markdown:
- **Cross-references.** The prose names tables and figures in the order the legends number them: Tables A1–A7 and Figures A1–A3 in Part 1. After rendering, check that every "Table A…" or "Figure A…" in the prose matches the label on its legend, and fix any that do not.
- **The notes list.** The `notes-list` chunk is the document's last chunk. Its labels are the targets of the superscript links, and Typst fails on a link to a missing label. Task 8 inserts Part 2 and Methods in brief **before** this chunk.
- **Sharing.** `class_table()` is used again in Part 2 (Task 8).

- [ ] **Step 3: Render and look.**

```bash
uv run oai report walking_validation
```

Render every `clinical.pdf` page to PNG with `swift …/pdfcheck/page.swift` into `…/scratchpad/clinical-plan/` and read each page. Check:
- every table has ≤ 5 columns;
- bold is on the right cells (spot-check two cells against the CSVs);
- legends start "Table A…" or "Figure A…" in order;
- no "NA" anywhere;
- the Technical notes list at the end holds the notes referenced so far.

Run: `uv run pytest -m realdata -q tests/test_walking_validation_realdata.py -k report_renders`
Expected: PASS.

Run: `uv run oai check-egress ~/oai-work/results/walking_validation/report`
Expected: 0 problems.

- [ ] **Step 4: Commit.**

```bash
git add analyses/walking_validation/clinical.qmd analyses/walking_validation/analysis.toml tests/test_walking_validation_realdata.py tests/test_analyses.py
git commit -m "feat(walking_validation): clinical-reader version, front page and Part 1; the sent PDF joins the brief and the clinical version

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: The clinical version: Part 2, Methods in brief, Technical notes; jargon gate; docs

**Files:**
- Modify:
  - `analyses/walking_validation/clinical.qmd` (append);
  - `tests/test_walking_validation_realdata.py`;
  - `docs/reporting.md`;
  - `analyses/walking_validation/README.md`;
  - `docs/superpowers/specs/2026-10-05-clinical-version-design.md` (status).

**Interfaces:**
- Consumes Task 7's setup objects (`lab`, `notes`, `colours`, `class_table`, `figure_file`, `bold_rule`, `n_lo`, `grid_np`).
- Also consumes `run$validity_strata`, `run$lo2022_t2`, `run$bias_tipping`, `run$bias_pba` and `oaireport::parse_or`.

- [ ] **Step 1: Write the failing jargon and markup assertions.**

In `tests/test_walking_validation_realdata.py`, add near `RIGHT_EDGE`:

```python
# spec 2026-10-05 §5.2: allowed only after the "Technical notes" heading
CLINICAL_BANNED = [
    "Hodges–Lehmann", "rank-biserial", "Jonckheere–Terpstra", "permutation", "bootstrap", "Wilson",
    "Spearman–Brown", "deattenuated", "limits of agreement", "non-differential",
    "differential misclassification", "probabilistic bias analysis", "bias analysis", "draws",
    "discarded", "device wave", "purposeful bout", "MV",
]
```

In `test_walking_validation_report_renders`, add:

```python
    clinical = pdfs[2]
    assert find_terms(clinical, CLINICAL_BANNED, stop_heading="Technical notes") == []
    clinical_text = "\n".join(page.extract_text() for page in PdfReader(clinical).pages)
    for leftover in ("#super", "{=typst}", "<tn-"):
        assert leftover not in clinical_text, leftover
    assert "Technical notes" in clinical_text
```

Run: `uv run pytest -m realdata -q tests/test_walking_validation_realdata.py -k report_renders`
Expected: FAIL. There is no "Technical notes" heading yet, or Part 2 is missing.

- [ ] **Step 2: Insert Part 2 and Methods in brief into `clinical.qmd`, before its last chunk (`notes-list`).**

The `notes-list` chunk (Task 7) stays the document's last chunk. The markdown below goes immediately before it. Do not repeat the `notes-list` chunk that closes the block below; it shows where the existing chunk sits.

````markdown
```{=typst}
#pagebreak()
```

# Part 2. What the agreement means for Lo et al. 2022

This part uses the `r count(n_lo)` participants of Lo et al. 2022 [@lo2022] who answered the walking question and have accelerometer data, a subset of Part 1's sample.

## Agreement in the Lo et al. 2022 participants

Agreement is as weak here as in Part 1 (Table A8), and similar across subgroups (Figure A4). Sensitivity, specificity`r notes$ref("sensitivity_specificity")` and Youden's J`r notes$ref("youden_j")` are as defined on the first page.

```{r b-class}
oaireport::compare_table(class_table("lo_subset"), widths = c(2.6, 2, 2.2), multipage = FALSE)
```

```{r note-b-class}
#| results: asis
cat(oaireport::table_note("Lo et al. 2022 participants with accelerometer data, against the device-defined walker. Sensitivity, specificity and the predictive values are never bold; Youden's J has no CI here.", label = lab("Table")), sep = "\n")
```

```{r b-strata}
#| fig-height: 4
#| results: asis
cat(oaireport::figure_group(), sep = "\n")
st <- run$validity_strata[run$validity_strata$sample == "lo_subset" & run$validity_strata$measure %in% c("se", "sp"), ]
var_names <- c(kl = "KL grade (worse knee)", pain = "Frequent knee pain", outcome_names)
st$group <- factor(named(st$variable, var_names), levels = unique(named(st$variable, var_names)))
st$stratum <- gsub("-", "–", st$stratum)
st$measure_name <- factor(ifelse(st$measure == "se", "Sensitivity", "Specificity"), levels = c("Sensitivity", "Specificity"))
fig_st <- ggplot2::ggplot(st, ggplot2::aes(estimate, stratum, colour = measure_name)) +
  ggplot2::geom_pointrange(ggplot2::aes(xmin = lo, xmax = hi), position = ggplot2::position_dodge(width = 0.5), size = 0.25) +
  ggplot2::facet_grid(group ~ ., scales = "free_y", space = "free_y") +
  ggplot2::scale_colour_manual(values = c(Sensitivity = colours[["item"]], Specificity = colours[["navy"]]), name = NULL) +
  ggplot2::scale_x_continuous(limits = c(0, 1)) +
  ggplot2::labs(x = "Estimate (95% CI)", y = NULL) + oaireport::theme_oai() +
  ggplot2::theme(legend.position = "bottom", strip.text.y = ggplot2::element_text(angle = 0, hjust = 0))
oaireport::save_figure(fig_st, "clinical_strata", "2col", height = 4)
print(fig_st)
cat(oaireport::table_note("Lo et al. 2022 participants with accelerometer data. Sensitivity and specificity of the walking answer against the device-defined walker, within subgroups: Kellgren–Lawrence (KL) grade of the worse knee and frequent knee pain at baseline; for each outcome, people in whom it did or did not occur during follow-up.", label = lab("Figure"), close_group = TRUE), sep = "\n")
```

## Two ways to read low agreement

Low agreement between the question and the accelerometer has two readings, and the data here cannot tell them apart.

- **Reporting.** Some people may misremember or misreport their walking, so the question misclassifies them.
- **Different constructs.** The question asks about a long-standing habit of walking for exercise since age 50, at the 96-month visit. The accelerometer recorded one week of current activity of any kind, years earlier. And activity counts do not single out walking. The two may simply measure different things.

A walking-specific accelerometer measure, such as steps and step rate, would separate these readings: it measures walking itself, at the visits the device was worn.

## Lo et al. 2022's results, replicated

```{r b-lo}
t2 <- run$lo2022_t2
rows <- t2[match(sprintf("t2.%s.or_adj", names(outcome_names)), t2$metric), ]
pub <- oaireport::parse_or(rows$published)
ours <- oaireport::parse_or(rows$ours)
lo_table <- data.frame(
  Outcome = unname(outcome_names),
  `Published odds ratio (95% CI)` = sub(" \\*$", "", gsub("-", "–", rows$published)),
  `This analysis (95% CI)` = oaireport::fmt_ci(ours$or, ours$lo, ours$hi),
  check.names = FALSE)
lo_bold <- cbind(FALSE, oaireport::ci_excludes(pub$lo, pub$hi, 1), oaireport::ci_excludes(ours$lo, ours$hi, 1))
oaireport::compare_table(lo_table, widths = c(2.6, 2, 2), multipage = FALSE, bold = lo_bold)
```

```{r note-b-lo}
#| results: asis
cat(oaireport::table_note("Adjusted odds ratios for walkers against non-walkers, by knee, from Lo et al. 2022 and from this analysis's replication with the published methods. Bold: the 95% CI excludes 1.", label = lab("Table")), sep = "\n")
```

## How sensitive is the association to classification?

```{r b-example}
t2v <- function(metric) as.numeric(t2$published[t2$metric == metric])
w_e <- t2v("t2.new_pain.walkers.events"); w_n <- t2v("t2.new_pain.walkers.n")
nw_e <- t2v("t2.new_pain.nonwalkers.events"); nw_n <- t2v("t2.new_pain.nonwalkers.n")
case_share <- w_e / (w_e + nw_e)
non_share <- (w_n - w_e) / ((w_n - w_e) + (nw_n - nw_e))
gap <- abs(case_share - non_share)
ex_se <- 0.9; ex_sp <- 0.6; ex_j <- ex_se + ex_sp - 1
stopifnot(any(abs(grid_np$se - ex_se) < 1e-9 & abs(grid_np$sp - ex_sp) < 1e-9))  # a feasible grid cell
dev_se <- pick("lo_subset", "se"); dev_sp <- pick("lo_subset", "sp"); dev_j <- dev_se + dev_sp - 1
case_dev <- (case_share - (1 - dev_sp)) / dev_j
```

If the walking question misclassifies some people, how would Lo et al. 2022's association change? In the paper's published table, `r pct(case_share)` of the knees that developed new frequent knee pain belonged to people who said they walk, against `r pct(non_share)` of the knees that did not: a gap of `r num(100 * gap, 0)` percentage points. Allowing for misclassification divides that gap by Youden's J. If the question's sensitivity were `r num(ex_se)` and its specificity `r num(ex_sp)` (J `r num(ex_j)`), the gap would grow to `r num(100 * gap / ex_j, 0)` points, so the association looks stronger, not weaker. Against the accelerometer, sensitivity is `r num(dev_se)` and specificity `r num(dev_sp)` (J `r num(dev_j)`): the gap would be multiplied by `r num(1 / dev_j, 1)`, and the share among knees with new pain would become `r num(case_dev)`, below zero, which is impossible.

The tipping-point analysis`r notes$ref("tipping_point")` repeats this over a grid of plausible accuracy values, assuming the misclassification is the same in people with and without the outcome`r notes$ref("nondifferential")` (Figure A5).

```{r b-tipping}
#| results: asis
tp <- run$bias_tipping
tip <- do.call(rbind, lapply(names(outcome_names), function(o) {
  g <- tp[tp$outcome == o & !is.na(tp$or), ]
  data.frame(outcome = outcome_names[[o]], holds = sum(g$excludes_1, na.rm = TRUE), feasible = nrow(g))
}))
cat(oaireport::figure_group(), sep = "\n")
cat(figure_file("tipping"), sep = "\n")
cat(oaireport::table_note(sprintf("Each cell: the adjusted odds ratio if the walking question had that sensitivity (rows) and specificity (columns), the same in people with and without the outcome; shaded cells keep a 95%% interval that excludes 1, and blank cells are impossible combinations. Settings in which the association holds: %s.",
  paste(sprintf("%s, %d of %d", tolower(tip$outcome), tip$holds, tip$feasible), collapse = "; ")), label = lab("Figure"), close_group = TRUE), sep = "\n")
```

A simulation of misclassification`r notes$ref("misclassification_simulation")` that takes the question's accuracy from the accelerometer cannot give a reliable single re-estimate: most of its simulations imply impossible values (Table A10). That is a limit of the activity-count reference, which is not specific to walking, as much as of the question.

```{r b-simulation}
pba <- run$bias_pba
adj <- pba[pba$model == "or_adj", ]
share <- function(o, scenario) pct(adj$discarded[adj$outcome == o & adj$scenario == scenario])
sim <- data.frame(
  Outcome = unname(outcome_names),
  `Misclassification the same in both groups` = vapply(names(outcome_names), share, character(1), scenario = "non-differential"),
  `Misclassification differs between groups` = vapply(names(outcome_names), share, character(1), scenario = "differential"),
  check.names = FALSE)
oaireport::compare_table(sim, widths = c(2.6, 2, 2), multipage = FALSE)
```

```{r note-b-simulation}
#| results: asis
cat(oaireport::table_note("Share of simulations, with the walking question's accuracy taken from the accelerometer in the Lo et al. 2022 participants, that imply an impossible (negative) number of walkers or non-walkers in a group, by outcome and adjusted model. The full results are in the technical report.", label = lab("Table")), sep = "\n")
```

A stricter definition makes a re-estimate steadier, because it raises J: the multiplier 1/J falls (Table A11).

```{r b-stricter}
times_names <- cut_names("times", prefix = "Walks at least")
defs <- c(cut1 = "Any walker (in use)", cut2 = times_names[["cut2"]], cut3 = times_names[["cut3"]])
st_rows <- do.call(rbind, lapply(names(defs), function(k) {
  g <- function(stat, col = "estimate") ci_get("lo_subset", "times", k, stat, col)
  data.frame(
    Definition = defs[[k]],
    Sensitivity = oaireport::fmt_ci(g("se"), g("se", "lo"), g("se", "hi")),
    Specificity = oaireport::fmt_ci(g("sp"), g("sp", "lo"), g("sp", "hi")),
    `Youden's J (95% CI)` = oaireport::fmt_ci(g("j"), g("j", "lo"), g("j", "hi")),
    `Multiplier 1/J (95% CI)` = ifelse(is.na(g("correction")), "–",
      sprintf("%s (%s–%s)", num(g("correction"), 1), num_na(g("correction", "lo"), 1),
              ifelse(is.na(g("correction", "hi")), "∞", num(g("correction", "hi"), 1)))),
    b_j = oaireport::ci_excludes(g("j", "lo"), g("j", "hi")),
    check.names = FALSE)
}))
st_bold <- cbind(matrix(FALSE, nrow(st_rows), 3), st_rows$b_j, FALSE)
st_rows$b_j <- NULL
oaireport::compare_table(st_rows, widths = c(2.2, 1.6, 1.6, 1.6, 1.6), multipage = FALSE, bold = st_bold)
```

```{r note-b-stricter}
#| results: asis
cat(oaireport::table_note(paste("Lo et al. 2022 participants with accelerometer data, walkers defined by the times-per-month answer. The multiplier shows how much a re-estimate that allows for misclassification would multiply the gap in walking between people with and without the outcome; its interval comes from J's.", bold_rule), label = lab("Table")), sep = "\n")
```

## An accelerometry-based alternative

The accelerometry group's step and step-rate data make a walking-specific exposure possible:
- steps per day;
- minutes a day at 100 or more steps per minute (about moderate intensity in adults aged 61 to 85 [@tudorlocke2021]);
- bouts of continuous stepping.

Defined together and pre-specified, such an exposure could be put into Lo et al. 2022's models in place of the walking question, and the results compared with the question's. That would test directly whether the question and the accelerometer measure the same thing, and how much the association depends on how walking is measured.

```{=typst}
#pagebreak()
```

# Methods in brief

- **Participants.** Osteoarthritis Initiative participants who answered the walking question at the 96-month visit and had usable accelerometer data at the 48- or 72-month visit (`r valid_day`).
- **Accelerometer.** An ActiGraph GT1M worn at the hip for a week. `r device_detail` A device-defined walker shows `r rule_short`.
- **Statistics.** Medians and median differences with 95% CIs, and differences adjusted for age, sex and body-mass index. Shares (sensitivity, specificity, predictive values) carry 95% CIs. Rank correlations, agreement beyond chance (kappa), and tests for trend across ordered groups. For Lo et al. 2022: the published models replicated, then refitted under assumed accuracy values (tipping-point grid) and under simulated misclassification.
- **Source.** Every number comes from the same analysis run as the brief. The full technical report gives every analysis, setting and assumption, and is available on request.

```{r notes-list}
#| results: asis
cat(notes$list(), sep = "\n")
```
````

Two notes:
- `device_detail` may contain banned terms (e.g. "counts/min" is fine, but check against the list). If the jargon check flags anything in Methods, rephrase there in plain words. Do not weaken the list.
- The bibliography follows Technical notes automatically. The jargon check stops at the last "Technical notes" heading, so the references are not checked.

- [ ] **Step 3: Render, read every page, and gate.**

```bash
uv run oai report walking_validation
```

Read every `clinical.pdf` page as PNG. Check:
- **Parts.** Part 1 and Part 2 each start on a new page.
- **Links.** Superscript letters link to the notes, and the notes' ↑ links back. Spot-check one in a PDF viewer, or check that `pdftotext` shows the letters.
- **Legends.** Each legend states its population.
- **Bold.** Bold is on the right cells. Spot-check Table A9 against `lo2022_t2.csv`.
- **Page count.** ≤ 12 pages. If it is over, reduce figure heights first (Figure A4 to 3.4, Figure A1 to 2.2), then join the Part 1 → Part 2 page break into the flow.

Run: `uv run pytest -m realdata -q tests/test_walking_validation_realdata.py -k report_renders`
Expected: PASS.

Run: `uv run pytest -q`, then `uv run oai check-egress ~/oai-work/results/walking_validation/report`
Expected: 0 problems.

- [ ] **Step 4: Docs.**

- **`docs/reporting.md`.** In the multi-document section, add a bullet: "`combined_documents = [...]` chooses which documents `combined` joins, in that order (default: all); `part_titles` then has one title per joined document."

  Add a short section "Plain-language documents", stating:
  - `oaireport::tech_notes()` gives superscript-letter markers linked to a Technical notes list. Use them in prose only, and write the list once at the end.
  - `standard_tech_notes()` gives default texts.
  - `ci_excludes()` and `compare_table(bold =, groups =)` handle significance bolding; pass `groups` instead of calling `group_tt` yourself.
  - `oai.pdfcheck.find_terms()` and `max_right_edge()` gate jargon and margins in tests.
- **`analyses/walking_validation/README.md`, "Sending the brief".** It now writes four PDFs:
  - `brief.pdf`;
  - `report.pdf` (the technical report, kept as the full record and available on request);
  - `clinical.pdf` (results for clinical readers);
  - `walking_validation_brief.pdf` = brief + clinical version, the file to send.
- **The spec.** Set `**Status:** Implemented`.

- [ ] **Step 5: Full verification and commit.**

```bash
uv run ruff check && uv run ruff format --check && uv run python scripts/check_no_data.py
uv run pytest -q
uv run pytest -m realdata -q
cd r && Rscript -e 'testthat::test_local("oaimodels", stop_on_failure = TRUE)' && RENV_PROFILE=report Rscript -e 'testthat::test_local("oaireport", stop_on_failure = TRUE); testthat::test_local("oaimodels", stop_on_failure = TRUE)'; cd ..
git diff --exit-code main -- r/renv.lock r/renv/profiles/report/renv.lock && echo "lockfiles unchanged"
```

```bash
git add analyses/walking_validation/clinical.qmd tests/test_walking_validation_realdata.py docs/reporting.md analyses/walking_validation/README.md docs/superpowers/specs/2026-10-05-clinical-version-design.md
git commit -m "feat(walking_validation): clinical version Part 2, methods and linked technical notes; jargon gate; docs

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
