# Walking-Validation Brief for the Northwestern Group — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce one send-ready PDF for the OAI accelerometry group at Northwestern: a 4–6 page brief that pitches a joint study, followed by the full technical report as its appendix. Generate both from the existing `walking_validation` run.

**Architecture:**
- **Manifest.** `[report]` in `analysis.toml` learns to list several documents, a combined PDF with part titles, and optional untracked "local assets" such as the author file.
- **Rendering.** `oai report` renders each document in order and joins the PDFs with `pypdf`.
- **R helpers.** A small set of helpers in `oaireport` (`R/brief.R`) emits the brief's Typst layout:
  - callouts;
  - the page-1 sidebar beside a figure;
  - the reading guide;
  - numbered labels;
  - the author line;
  - the estimate style;
  - Youden's J contours.
- **Documents.** The brief is a new `brief.qmd`. The report gets a legibility pass.

**Tech Stack:** Python 3.11 (uv, typer, pytest, pypdf as a dev dependency); R (renv "report" profile: ggplot2, tinytable, yaml); Quarto 1.9 with Typst. The bibliography uses Typst's built-in `american-medical-association` style.

**Spec:** `docs/superpowers/specs/2026-10-03-northwestern-brief-design.md`

## Global Constraints

- **Privacy and egress.**
  - The repository is public. Results and reports are aggregate only.
  - `oai check-egress` must report 0 problems on `~/oai-work/results/walking_validation/report/`.
  - Author names and contact details come only from an untracked `analyses/walking_validation/brief.local.yml`, git-ignored via `*.local.yml`. That file is never left in the report folder after rendering.
- **Wording.** Public text says "the original authors" or "the study team". It describes no personal relationships and names no individuals, except as cited authors.
- **Numbers.** Every number in the brief is read from the run (`oaireport::load_results()`), except literature values, which are cited. Every assumption value in text (bout minutes, cut-point, walker rule) comes from the run's assumptions.
- **Page limits.**
  - Brief ≤ 6 US-letter pages. Report ≤ 18 pages.
  - Nothing overflows the right margin, measured as `pdftotext -bbox` xMax:
    - ≤ 547.2 pt on report pages (0.9in margins);
    - ≤ 550.8 pt on brief pages (0.85in margins).
  - No "NA", "NaN" or "Inf" text appears in either PDF.
- **Colours.**
  - The walking item is `#0072B2`, PASE `#D55E00`, headings `#0b2e59`, in every figure of both documents.
  - Muted tints mark reference groups: `#9fb6cf` for item non-walkers, `#f0b48e` for PASE "Never".
  - Blue left-rule callouts are for points in our favour and the ask. Amber (`#E69F00`) left-rule callouts are for limitations and open questions.
- **Type.**
  - Arial, 10 pt body.
  - The page-1 lead paragraph is 11.5 pt.
  - Footers read "Brief — page n" and "Technical report — page n".
  - Brief figures are Figure 1–4; report tables and figures are A1, A2, … (counted separately).
- **Dependencies.**
  - `r/renv.lock` and `r/renv/profiles/report/renv.lock` do not change. `oaireport` gains `yaml` in Imports, which is already in the report-profile lock.
  - `pypdf` is a **dev** dependency: report rendering is local-only, like Quarto. `uv export --no-dev` for enclave bundles is unchanged.
- **Compatibility.**
  - An analysis whose `[report]` has only `entry` (lo2022_walking) renders exactly as before: one PDF, no combined file.
  - Result CSVs are untouched; this plan changes reports and tooling only.
- **Commits.**
  - Every commit is signed through 1Password. If signing fails, stop with the work staged; never bypass.
  - Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Branch.** Work on branch `feat/northwestern-brief`. Do not push.

## Review Focus

1. **Single-entry reports keep working.** An analysis with only `entry` renders one PDF, as before. It gets no combined file and has no local assets copied. Pinned in:
   - Task 1: `test_single_entry_is_one_document`;
   - Task 3: the existing `test_render_copies_inputs_sets_env_and_keeps_only_pdf_and_figures`, unchanged apart from unpacking `[pdf]`.
2. **The author file is absent or malformed.** Absent gives the neutral placeholder. Malformed gives an error naming the file and the missing key. Pinned in Task 4: `author_block reads names and contact, or gives the placeholder`.
3. **One document of several fails to render.** The error names that document, partial output is kept, and no combined PDF is written. Pinned in Task 3: `test_a_failing_document_is_named_and_nothing_is_combined`.
4. **Text holding Typst markup characters inside raw Typst blocks** (`#`, `$`, `@`, `[ ]`, `_`, `*`, `/`) renders literally. For example, an email address, "#1" or "steps/min". Pinned in Task 4: `typst_text escapes Typst markup characters`.
5. **The local author file does not survive in the report folder.** Only PDFs and `figures/` remain after rendering. Pinned in Task 3: `test_local_assets_are_copied_when_present_and_cleaned_up`.

---

### Task 1: `[report]` accepts several documents, a combined PDF, part titles and local assets

**Files:**
- Modify: `src/oai/manifest.py` (`ReportSpec`, `_parse_report`)
- Test: `tests/test_manifest.py`

**Interfaces:**
- Produces:
  ```python
  @dataclass(frozen=True)
  class ReportSpec:
      documents: tuple[str, ...]
      runs: tuple[str, ...]
      assets: tuple[str, ...] = ()
      combined: str | None = None
      part_titles: tuple[str, ...] = ()
      local_assets: tuple[str, ...] = ()
  ```
  - `documents`: .qmd files, rendered in order.
  - `runs`: unchanged.
  - `assets`: copied next to the documents.
  - `combined`: a PDF joining the documents' PDFs in order.
  - `part_titles`: one bookmark per document in `combined`.
  - `local_assets`: untracked files, copied if present.
  - A temporary property `entry` returns `documents[0]`, so `src/oai/report.py` keeps working until Task 3 removes it.

- [ ] **Step 1: Write the failing tests**

In `tests/test_manifest.py`, change the assertion in the existing `test_report_section_parsed` to:

```python
    assert analysis.report == ReportSpec(("report.qmd",), ("default", "alt"), ("notes.md",))
```

Append after `test_invalid_report_sections`:

```python
DOCS_MANIFEST = REPORT_MANIFEST.replace(
    'entry = "report.qmd"',
    'documents = ["brief.qmd", "report.qmd"]\n'
    'combined = "together.pdf"\n'
    'part_titles = ["Brief", "Appendix"]\n'
    'local_assets = ["brief.local.yml"]',
)


def write_docs_analysis(tmp_path, manifest=DOCS_MANIFEST):
    root = write_report_analysis(tmp_path, manifest)
    (root / "brief.qmd").write_text("# brief\n")
    return root


def test_single_entry_is_one_document(tmp_path):
    spec = load_analysis(write_report_analysis(tmp_path)).report
    assert spec.documents == ("report.qmd",)
    assert spec.combined is None and spec.part_titles == () and spec.local_assets == ()


def test_documents_combined_titles_and_local_assets_parsed(tmp_path):
    analysis = load_analysis(write_docs_analysis(tmp_path))
    assert analysis.report == ReportSpec(
        ("brief.qmd", "report.qmd"),
        ("default", "alt"),
        ("notes.md",),
        "together.pdf",
        ("Brief", "Appendix"),
        ("brief.local.yml",),
    )


DOCS_LINE = 'documents = ["brief.qmd", "report.qmd"]'


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        (DOCS_LINE, DOCS_LINE + '\nentry = "report.qmd"', "takes entry or documents, not both"),
        (DOCS_LINE, "documents = []", "documents must be a non-empty list"),
        (DOCS_LINE, 'documents = "brief.qmd"', "documents must be a non-empty list"),
        (DOCS_LINE, 'documents = ["brief.qmd", "brief.qmd"]', "documents has duplicates"),
        (DOCS_LINE, 'documents = ["brief.qmd", "missing.qmd"]', "documents 'missing.qmd'"),
        (DOCS_LINE, 'documents = ["brief.qmd", "notes.md"]', "must be a .qmd file"),
        ('combined = "together.pdf"', 'combined = "together.html"', "must be a .pdf file name"),
        ('combined = "together.pdf"', 'combined = "out/together.pdf"', "must be a .pdf file name"),
        ('combined = "together.pdf"', 'combined = "report.pdf"', "would overwrite"),
        ('part_titles = ["Brief", "Appendix"]', 'part_titles = ["Brief"]', "one title per document"),
        ('part_titles = ["Brief", "Appendix"]', 'part_titles = ["Brief", ""]', "list of titles"),
        ('local_assets = ["brief.local.yml"]', 'local_assets = ["../x.yml"]', "local_assets must be"),
        ('local_assets = ["brief.local.yml"]', 'local_assets = "brief.local.yml"', "local_assets must be"),
    ],
)
def test_invalid_document_sections(tmp_path, old, new, message):
    root = write_docs_analysis(tmp_path, DOCS_MANIFEST.replace(old, new))
    with pytest.raises(ManifestError, match=re.escape(message)):
        load_analysis(root)


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        ('combined = "together.pdf"', "combined needs documents"),
        ('part_titles = ["Report"]', "part_titles needs combined"),
    ],
)
def test_combined_and_titles_need_documents(tmp_path, extra, message):
    manifest = REPORT_MANIFEST.replace('assets = ["notes.md"]', f'assets = ["notes.md"]\n{extra}')
    with pytest.raises(ManifestError, match=re.escape(message)):
        load_analysis(write_report_analysis(tmp_path, manifest))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest -q tests/test_manifest.py -k "report or document or combined"`
Expected: FAIL. The parsed `ReportSpec("report.qmd", …)` differs from `ReportSpec(("report.qmd",), …)`, and the new keys are ignored, so their invalid cases raise nothing.

- [ ] **Step 3: Implement**

In `src/oai/manifest.py`, replace the `ReportSpec` class with:

```python
@dataclass(frozen=True)
class ReportSpec:
    documents: tuple[str, ...]  # .qmd files directly in the analysis folder, rendered in order
    runs: tuple[str, ...]  # run labels the report reads: "default" and/or variant names
    assets: tuple[str, ...] = ()  # files copied next to the documents before rendering
    combined: str | None = None  # a PDF joining the documents' PDFs, in order
    part_titles: tuple[str, ...] = ()  # one bookmark title per document in `combined`
    local_assets: tuple[str, ...] = ()  # untracked files (e.g. *.local.yml) copied when present

    @property
    def entry(self) -> str:  # removed in Task 3, once report.py renders every document
        return self.documents[0]
```

Below `_plain_file`, add:

```python
def _plain_name(name: object) -> bool:
    """A bare file name (no directories), which need not exist."""
    return isinstance(name, str) and bool(name) and name == Path(name).name
```

Replace `_parse_report` with:

```python
def _parse_report(raw: Any, root: Path, fail: Callable[[str], NoReturn]) -> ReportSpec:
    if not isinstance(raw, dict):
        fail("[report] must be a table")
    if "entry" in raw and "documents" in raw:
        fail("[report] takes entry or documents, not both")
    key = "documents" if "documents" in raw else "entry"
    documents = raw["documents"] if key == "documents" else [raw.get("entry")]
    if not isinstance(documents, list) or not documents:
        fail("[report] documents must be a non-empty list of .qmd files")
    for document in documents:
        if not _plain_file(root, document) or not str(document).endswith(".qmd"):
            fail(f"[report] {key} {document!r} must be a .qmd file directly in {root}")
    if len(set(documents)) != len(documents):
        fail("[report] documents has duplicates")
    runs = raw.get("runs")
    if not isinstance(runs, list) or not runs or not all(isinstance(r, str) for r in runs):
        fail("[report] runs must be a non-empty list of run labels")
    if len(set(runs)) != len(runs):
        fail("[report] runs has duplicates")
    variants = load_assumptions(root).variants
    unknown = [r for r in runs if r != DEFAULT_LABEL and r not in variants]
    if unknown:
        fail(
            f"[report] runs {', '.join(unknown)} are not 'default' or a variant in assumptions.toml"
        )
    assets = raw.get("assets", [])
    if not isinstance(assets, list):
        fail("[report] assets must be a list of file names")
    for asset in assets:
        if not _plain_file(root, asset):
            fail(f"[report] asset {asset!r} must be a file directly in {root}")
    combined = raw.get("combined")
    if combined is not None:
        if key != "documents":
            fail("[report] combined needs documents")
        if not _plain_name(combined) or not combined.endswith(".pdf"):
            fail(f"[report] combined {combined!r} must be a .pdf file name")
        if combined in {f"{Path(d).stem}.pdf" for d in documents}:
            fail(f"[report] combined {combined!r} would overwrite a document's PDF")
    titles = raw.get("part_titles", [])
    if titles and combined is None:
        fail("[report] part_titles needs combined")
    if not isinstance(titles, list) or not all(isinstance(t, str) and t for t in titles):
        fail("[report] part_titles must be a list of titles")
    if titles and len(titles) != len(documents):
        fail("[report] part_titles needs one title per document")
    local_assets = raw.get("local_assets", [])
    if not isinstance(local_assets, list) or not all(_plain_name(a) for a in local_assets):
        fail("[report] local_assets must be a list of file names")
    return ReportSpec(
        tuple(documents),
        tuple(runs),
        tuple(assets),
        combined,
        tuple(titles),
        tuple(local_assets),
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest -q tests/test_manifest.py tests/test_report.py tests/test_analyses.py`
Expected: PASS. `test_report.py` still passes through the temporary `entry` property, and the existing `entry` error cases keep their messages.

- [ ] **Step 5: Commit**

```bash
git add src/oai/manifest.py tests/test_manifest.py
git commit -m "feat(manifest): [report] lists documents, a combined PDF with part titles, and local assets

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Joining PDFs with a bookmark per part

**Files:**
- Modify: `pyproject.toml`, `uv.lock` (via `uv add --dev pypdf`)
- Create: `src/oai/pdfjoin.py`
- Test: `tests/test_pdfjoin.py`

**Interfaces:**
- Produces:
  - `oai.pdfjoin.combine_pdfs(parts: Sequence[tuple[str, Path]], out: Path) -> Path`;
  - `oai.pdfjoin.PdfJoinError(OAIError)`.
- Each part gets a top-level bookmark with its title. The part's own bookmarks are nested under it (verified with pypdf: `append(..., outline_item=title)` nests the imported outline).

- [ ] **Step 1: Add the dev dependency**

Run: `uv add --dev pypdf`
Expected: `[dependency-groups] dev` in `pyproject.toml` gains `"pypdf>=…"`, and `uv.lock` updates.

Run: `uv export --format requirements-txt --no-dev --no-emit-project --frozen | grep -c pypdf`
Expected: `0`.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_pdfjoin.py`:

```python
"""Joining PDFs for `oai report`'s combined document."""

from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from oai.pdfjoin import PdfJoinError, combine_pdfs


def blank_pdf(path: Path, pages: int, bookmark: str | None = None) -> Path:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    if bookmark:
        writer.add_outline_item(bookmark, 0)
    with path.open("wb") as handle:
        writer.write(handle)
    return path


def test_combine_keeps_every_page_in_order_with_a_bookmark_per_part(tmp_path):
    brief = blank_pdf(tmp_path / "brief.pdf", 2, bookmark="Inner")
    report = blank_pdf(tmp_path / "report.pdf", 3)
    out = combine_pdfs([("Brief", brief), ("Appendix", report)], tmp_path / "both.pdf")
    assert out == tmp_path / "both.pdf"
    reader = PdfReader(out)
    assert len(reader.pages) == 5
    top = [item for item in reader.outline if not isinstance(item, list)]
    assert [(i.title, reader.get_destination_page_number(i)) for i in top] == [
        ("Brief", 0),
        ("Appendix", 2),
    ]
    nested = [item for item in reader.outline if isinstance(item, list)]
    assert [[i.title for i in group] for group in nested] == [["Inner"]]


def test_combine_rejects_no_parts_and_missing_files(tmp_path):
    with pytest.raises(PdfJoinError, match="no PDFs to join"):
        combine_pdfs([], tmp_path / "x.pdf")
    with pytest.raises(PdfJoinError, match="missing PDF"):
        combine_pdfs([("A", tmp_path / "nope.pdf")], tmp_path / "x.pdf")
    assert not (tmp_path / "x.pdf").exists()
```

Run: `uv run pytest -q tests/test_pdfjoin.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'oai.pdfjoin'`.

- [ ] **Step 3: Implement**

Create `src/oai/pdfjoin.py`:

```python
"""Join PDFs into one, with a top-level bookmark per part.

`oai report` uses this for an analysis whose [report] sets `combined`. pypdf is a dev
dependency (report rendering is local-only, like Quarto), so it is imported only when a join
is asked for and enclave bundles never need it.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from oai.errors import OAIError


class PdfJoinError(OAIError):
    """PDFs could not be joined."""


def combine_pdfs(parts: Sequence[tuple[str, Path]], out: Path) -> Path:
    """Write the parts' pages in order to `out`; each part gets a bookmark with its title,
    and the part's own bookmarks are nested under it. Returns `out`."""
    if not parts:
        raise PdfJoinError("no PDFs to join")
    for _, path in parts:
        if not Path(path).is_file():
            raise PdfJoinError(f"missing PDF: {path}")
    try:
        from pypdf import PdfWriter
    except ImportError as exc:  # pragma: no cover - dev dependency
        raise PdfJoinError("joining PDFs needs pypdf: run `uv sync` (a dev dependency)") from exc
    writer = PdfWriter()
    for title, path in parts:
        writer.append(str(path), outline_item=title)
    with Path(out).open("wb") as handle:
        writer.write(handle)
    return Path(out)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest -q tests/test_pdfjoin.py`
Expected: PASS, 2 tests.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock src/oai/pdfjoin.py tests/test_pdfjoin.py
git commit -m "feat(report): join PDFs with a bookmark per part (pypdf, dev dependency)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `oai report` renders every document, copies local assets, writes the combined PDF

**Files:**
- Modify:
  - `src/oai/report.py` (`render_report`);
  - `src/oai/cli.py` (the `report` command);
  - `src/oai/manifest.py` (remove the temporary `entry` property).
- Modify callers:
  - `tests/test_report.py`;
  - `tests/test_lo2022_realdata.py:81`;
  - `tests/test_walking_validation_realdata.py:458`.

**Interfaces:**
- Consumes: `ReportSpec` (Task 1) and `combine_pdfs` (Task 2).
- Produces: `render_report(...) -> list[Path]`. It returns each document's PDF in order, then the combined PDF if one is set.
- The CLI prints one `Report: <path>` line per PDF, then `Before sharing: oai check-egress <folder>`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_report.py`:

1. Let `FAKE_QUARTO` fail for one named document and copy a real PDF. Replace its line

   ```
       if [ -n "$FAKE_QUARTO_FAIL" ]; then echo "boom: render failed" >&2; exit 1; fi
   ```

   with

   ```
       if [ "$FAKE_QUARTO_FAIL" = "1" ] || [ "$FAKE_QUARTO_FAIL" = "$2" ]; then echo "boom: render failed" >&2; exit 1; fi
       if [ -n "$FAKE_QUARTO_PDF" ]; then cp "$FAKE_QUARTO_PDF" "$stem.pdf"; exit 0; fi
   ```

   Keep the 4-space indentation that the dedented block uses.
2. The return value is now a list. Update these call sites:
   - `test_run_flag_runs_only_the_missing_runs`: `pdf = render_report(` → `[pdf] = render_report(`.
   - `test_render_copies_inputs_sets_env_and_keeps_only_pdf_and_figures`: `pdf = render_report(` → `[pdf] = render_report(`.
   - `test_real_quarto_renders_with_oaireport`: `pdf = render_report(` → `[pdf] = render_report(`.
3. Append:

```python
DOCS_MANIFEST = MANIFEST.replace(
    'entry = "report.qmd"',
    'documents = ["brief.qmd", "report.qmd"]\n'
    'combined = "together.pdf"\n'
    'part_titles = ["Brief", "Appendix"]\n'
    'local_assets = ["brief.local.yml", "absent.local.yml"]',
)


def make_docs_toy(tmp_path, manifest=DOCS_MANIFEST):
    # make_toy loads the analysis, so it starts from the single-entry manifest; the brief, a
    # local asset and the multi-document manifest are added before loading it again
    root = make_toy(tmp_path).root
    (root / "brief.qmd").write_text("# brief\n")
    (root / "brief.local.yml").write_text("authors: []\n")
    (root / "analysis.toml").write_text(manifest)
    return load_analysis(root)


def blank_pdf(path: Path, pages: int) -> Path:
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    with path.open("wb") as handle:
        writer.write(handle)
    return path


def top_bookmarks(path: Path) -> list[str]:
    from pypdf import PdfReader

    return [item.title for item in PdfReader(path).outline if not isinstance(item, list)]


def test_documents_render_in_order_and_combine(tmp_path, quarto_env):
    from pypdf import PdfReader

    env = {**quarto_env, "FAKE_QUARTO_PDF": str(blank_pdf(tmp_path / "blank.pdf", 2))}
    pdfs = render_report(
        make_docs_toy(tmp_path), make_settings(tmp_path), run_missing=True, base_env=env, echo=quiet
    )
    out = (tmp_path / "results" / "toy" / "report").resolve()
    assert pdfs == [out / "brief.pdf", out / "report.pdf", out / "together.pdf"]
    assert len(PdfReader(pdfs[-1]).pages) == 4
    assert top_bookmarks(pdfs[-1]) == ["Brief", "Appendix"]


def test_local_assets_are_copied_when_present_and_cleaned_up(tmp_path, quarto_env, monkeypatch):
    import oai.report as report_module

    joined = []

    def fake_join(parts, out):
        joined.append(parts)
        out.write_text("joined")
        return out

    monkeypatch.setattr(report_module, "combine_pdfs", fake_join)
    pdfs = render_report(
        make_docs_toy(tmp_path), make_settings(tmp_path), run_missing=True, base_env=quarto_env,
        echo=quiet,
    )
    # the text fake lists the folder into each PDF: the present local asset was there while
    # rendering, the absent one was skipped without error
    listing = set(pdfs[0].read_text().splitlines())
    assert "brief.local.yml" in listing and "absent.local.yml" not in listing
    assert [title for title, _ in joined[0]] == ["Brief", "Appendix"]
    out = pdfs[0].parent
    assert sorted(p.name for p in out.iterdir()) == ["brief.pdf", "figures", "report.pdf", "together.pdf"]


def test_a_failing_document_is_named_and_nothing_is_combined(tmp_path, quarto_env):
    env = {**quarto_env, "FAKE_QUARTO_FAIL": "report.qmd"}
    with pytest.raises(ReportError, match=r"report\.qmd failed"):
        render_report(
            make_docs_toy(tmp_path), make_settings(tmp_path), run_missing=True, base_env=env,
            echo=quiet,
        )
    out = tmp_path / "results" / "toy" / "report"
    assert (out / "brief.pdf").exists() and not (out / "together.pdf").exists()


def test_part_titles_default_to_document_names(tmp_path, quarto_env):
    manifest = DOCS_MANIFEST.replace('part_titles = ["Brief", "Appendix"]\n', "")
    env = {**quarto_env, "FAKE_QUARTO_PDF": str(blank_pdf(tmp_path / "blank.pdf", 1))}
    pdfs = render_report(
        make_docs_toy(tmp_path, manifest), make_settings(tmp_path), run_missing=True,
        base_env=env, echo=quiet,
    )
    assert top_bookmarks(pdfs[-1]) == ["brief", "report"]


def test_cli_report_prints_every_pdf(tmp_path, monkeypatch):
    make_docs_toy(tmp_path)
    monkeypatch.setenv("OAI_ANALYSES_DIR", str(tmp_path / "analyses"))
    monkeypatch.setenv("OAI_QUARTO", str(fake_quarto(tmp_path)))
    monkeypatch.setenv("FAKE_QUARTO_PDF", str(blank_pdf(tmp_path / "blank.pdf", 1)))
    oai_config.get_settings.cache_clear()
    result = CliRunner().invoke(app, ["report", "toy", "--run"])
    assert result.exit_code == 0, result.output
    reports = [line for line in result.output.splitlines() if line.startswith("Report: ")]
    assert [Path(line.removeprefix("Report: ")).name for line in reports] == [
        "brief.pdf", "report.pdf", "together.pdf"
    ]
```

Run: `uv run pytest -q tests/test_report.py`
Expected: FAIL. `render_report` returns one Path (so `[pdf] =` fails to unpack), renders only the first document, and copies no local assets.

- [ ] **Step 2: Implement**

In `src/oai/report.py`:
- Add `from oai.pdfjoin import combine_pdfs` to the imports.
- Change the return annotation of `render_report` to `-> list[Path]`.
- Change its docstring to `"""Render the analysis's report documents; returns their PDFs, then the combined PDF."""`.
- Replace everything from `for name in (spec.entry, *spec.assets):` to the end of the function with:

```python
    for name in (*spec.documents, *spec.assets):
        shutil.copy2(analysis.root / name, out / name)
    for name in spec.local_assets:  # untracked (e.g. the brief's author file): copied if present
        if (analysis.root / name).is_file():
            shutil.copy2(analysis.root / name, out / name)
    env.update(
        OAI_ANALYSIS=analysis.name,
        OAI_RESULTS_ROOT=str(results_root),
        OAI_REPORT_DIR=str(out),
        OAI_REPORT_RUNS=",".join(spec.runs),
        RENV_PROFILE=RENV_PROFILE,
    )
    for key, value in r_profile_env(settings).items():
        env.setdefault(key, value)
    pdfs: list[Path] = []
    for document in spec.documents:
        echo(f"==> {analysis.name}: rendering {document} with {quarto}")
        proc = subprocess.run(
            [str(quarto), "render", document, "--to", "typst"],
            cwd=out,
            env=env,
            capture_output=True,
            text=True,
        )
        pdf = out / f"{Path(document).stem}.pdf"
        if proc.returncode != 0 or not pdf.is_file():
            raise ReportError(
                f"quarto render of {document} failed (exit {proc.returncode}); "
                f"partial output kept in {out}\n" + _tail(proc.stderr or proc.stdout)
            )
        pdfs.append(pdf)
    if spec.combined:
        titles = spec.part_titles or tuple(Path(d).stem for d in spec.documents)
        echo(f"==> {analysis.name}: joining {len(pdfs)} PDFs into {spec.combined}")
        pdfs.append(combine_pdfs(list(zip(titles, pdfs, strict=True)), out / spec.combined))
    keep = set(pdfs)
    for child in out.iterdir():
        if child in keep or child.name == FIGURES_DIR:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    return pdfs
```

In `src/oai/cli.py`, change the body of the `report` command to:

```python
    with user_errors():
        settings = get_settings()
        analysis = find_analysis(name, settings.analyses_dir)
        pdfs = render_report(analysis, settings, run_missing=run_, echo=typer.echo)
    for pdf in pdfs:
        typer.echo(f"Report: {pdf}")
    typer.echo(f"Before sharing: oai check-egress {pdfs[0].parent}")
```

Remove the temporary `entry` property from `ReportSpec`. Then run `git grep -n "spec\.entry\|report\.entry" src tests`; it must print nothing. A step's `entry` is a different attribute and stays.

In `tests/test_lo2022_realdata.py:81` and `tests/test_walking_validation_realdata.py:458`, change `pdf = render_report(` to `[pdf] = render_report(`. Task 5 rewrites the walking-validation one.

- [ ] **Step 3: Run the tests to verify they pass**

Run: `uv run pytest -q tests/test_report.py tests/test_manifest.py tests/test_pdfjoin.py && uv run pytest -q`
Expected: PASS. The existing `test_failed_render_keeps_partial_output_and_shows_stderr` still matches, since the message keeps "exit 1", "partial output kept" and the stderr tail.

- [ ] **Step 4: Commit**

```bash
git add src/oai/report.py src/oai/cli.py src/oai/manifest.py tests/
git commit -m "feat(report): render every [report] document, copy local assets, write the combined PDF

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: `oaireport` brief helpers

**Files:**
- Create: `r/oaireport/R/brief.R`, `r/oaireport/tests/testthat/test-brief.R`
- Modify:
  - `r/oaireport/R/notes.R` (`table_note` gains `label`);
  - `r/oaireport/NAMESPACE`;
  - `r/oaireport/DESCRIPTION` (Imports gains `yaml`);
  - `r/oaireport/tests/testthat/test-notes.R`.

**Interfaces:**
- Produces (all exported):
  - `brief_colours`: a named character vector with `item`, `pase`, `navy`, `tint`, `muted`, `pase_muted`, `note_fill`, `warn`, `warn_fill`, `warn_text`, `label`.
  - `typst_text(x)`: escapes Typst markup characters (`\ # $ * _ \` < > @ ~ [ ] /`) and squeezes whitespace.
  - `fmt_ci(est, lo, hi, digits = 2)`: "0.89 (0.86–0.91)"; "a (b to c)" when a limit is negative; the estimate alone when a limit is NA; "–" when the estimate is NA. Vectorised over `est`, `lo` and `hi`.
  - Lines for a `results: asis` chunk, each wrapped in a raw Typst block:
    - `callout(text, kind = c("note", "warn"), title = NULL, cite = NULL, size = 9.5)`;
    - `sidebar_figure(results, ask, image, caption, caption_title = "Figure 1.", heading = "Key results", sidebar = 0.31)`, where `results` is a data frame with `value` and `label`;
    - `reading_guide(definitions, notation, title = "How to read this report")`.
  - `numberer(prefix = "")`: returns `function(kind = c("Table", "Figure"))`, which yields "Table A1.", "Figure A1.", "Table A2.", ….
  - `author_block(path, placeholder = "Authors and contact to be added")`: one string.
  - `youden_contours(j = c(0, 0.1, 0.2, 0.3, 0.4))`: a list of two ggplot layers: dashed grey lines of equal Youden's J on a sensitivity against (1 − specificity) plot, and their values printed just above the top edge, off every line. The J = 0 line is the chance diagonal. Use it with `coord_equal(xlim = c(0, 1), ylim = c(0, 1), clip = "off")` and a top plot margin of at least 14 pt.
  - `table_note(text, size = 8, close_group = FALSE, label = NULL)`: a non-NULL `label` is placed, unescaped, before the escaped text as bold Markdown.

- [ ] **Step 1: Write the failing tests**

Create `r/oaireport/tests/testthat/test-brief.R`:

```r
test_that("typst_text escapes Typst markup characters", {
  expect_equal(typst_text("a #b $c *d* _e_ [f] <g> @h ~i `j` \\k l/m"),
               "a \\#b \\$c \\*d\\* \\_e\\_ \\[f\\] \\<g\\> \\@h \\~i \\`j\\` \\\\k l\\/m")
  expect_equal(typst_text("  two   spaces \n newline "), "two spaces newline")
  expect_error(typst_text(1), "character")
})

test_that("fmt_ci joins limits with an en dash, or 'to' when a limit is negative", {
  expect_equal(fmt_ci(0.891, 0.862, 0.913), "0.89 (0.86–0.91)")
  expect_equal(fmt_ci(105, -153, 1080, digits = 0), "105 (-153 to 1,080)")
  expect_equal(fmt_ci(NA, 1, 2), "–")
  expect_equal(fmt_ci(0.5, NA, 0.6), "0.50")
  expect_equal(fmt_ci(c(0.1, 0.2), c(0.05, -0.1), c(0.2, 0.3)),
               c("0.10 (0.05–0.20)", "0.20 (-0.10 to 0.30)"))
})

test_that("callout emits one raw Typst block with escaped text, a title and citations", {
  note <- callout("Counts can't tell #walking from cycling", kind = "warn", title = "The weak link.",
                  cite = c("abel2008", "storti2008"))
  body <- paste(note, collapse = "\n")
  expect_equal(sum(grepl("^```", note)), 2)
  expect_match(body, "```{=typst}", fixed = TRUE)
  expect_match(body, "rgb(\"#E69F00\")", fixed = TRUE)
  expect_match(body, "The weak link.", fixed = TRUE)
  expect_match(body, "\\#walking", fixed = TRUE)
  expect_match(body, "@abel2008 @storti2008", fixed = TRUE)
  expect_match(paste(callout("ok"), collapse = "\n"), "rgb(\"#0072B2\")", fixed = TRUE)
  expect_error(callout("x", kind = "other"))
  expect_error(callout("x", cite = "bad key"), "cite")
})

test_that("sidebar_figure lays out key results and the ask beside the figure", {
  side <- sidebar_figure(data.frame(value = c("0.88 / 0.25", "7.7 → 3.9"), label = c("Se / Sp", "factor")),
                         ask = "A joint study.", image = "figures/f.png", caption = "Caption.")
  text <- paste(side, collapse = "\n")
  expect_match(text, "#grid(columns: (31%, 1fr)", fixed = TRUE)
  expect_match(text, "#image(\"figures/f.png\", width: 100%)", fixed = TRUE)
  expect_match(text, "7.7 → 3.9", fixed = TRUE)
  expect_match(text, "0.88 \\/ 0.25", fixed = TRUE)
  expect_match(text, "The ask.", fixed = TRUE)
  expect_match(text, "KEY RESULTS", fixed = TRUE)
  expect_error(sidebar_figure(data.frame(x = 1), "a", "i", "c"), "value and label")
})

test_that("reading_guide lists each term in bold, then the notation line", {
  guide <- reading_guide(c(`Item walker` = "answered yes.", `Device walker` = "2 days a week."),
                         "Notation: 0.89 (0.86–0.91).")
  text <- paste(guide, collapse = "\n")
  expect_match(text, "#text(weight: \"bold\")[Item walker:] answered yes.", fixed = TRUE)
  expect_match(text, "Notation: 0.89", fixed = TRUE)
  expect_match(text, "How to read this report", fixed = TRUE)
  expect_error(reading_guide(c("no names"), "n"), "named")
})

test_that("numberer counts tables and figures separately", {
  lab <- numberer("A")
  expect_equal(c(lab("Table"), lab("Figure"), lab("Table")), c("Table A1.", "Figure A1.", "Table A2."))
  expect_equal(numberer()("Figure"), "Figure 1.")
  expect_error(lab("Chart"))
})

test_that("author_block reads names and contact, or gives the placeholder", {
  expect_equal(author_block(tempfile(fileext = ".yml")), "Authors and contact to be added")
  path <- withr::local_tempfile(fileext = ".yml")
  writeLines(c("authors:", "  - name: A. Person", "    affiliation: Somewhere", "  - name: B. Person",
               "contact:", "  name: A. Person", "  email: a@example.org"), path)
  expect_equal(author_block(path),
               "A. Person (Somewhere), B. Person · Contact: A. Person, a@example.org")
  writeLines("authors: []", path)
  expect_error(author_block(path), "needs `authors`")
  writeLines(c("authors:", "  - name: A", "contact:", "  name: A"), path)
  expect_error(author_block(path), "without an `email`")
})

test_that("youden_contours draws a dashed line per J and labels each above the top edge", {
  layers <- youden_contours(c(0, 0.2))
  expect_length(layers, 2)
  expect_equal(layers[[1]]$data$se, c(0, 1, 0.2, 1))
  expect_equal(layers[[2]]$data$fpr, c(1, 0.8))
  expect_equal(layers[[2]]$data$label, c("0", "J = 0.2"))
  expect_error(youden_contours(1), "j must")
})
```

Append to `r/oaireport/tests/testthat/test-notes.R`:

```r
test_that("table_note puts an unescaped bold label before the escaped text", {
  lines <- table_note("Some *text*.", label = "Table A1.")
  expect_true("**Table A1.** Some \\*text\\*." %in% lines)
  expect_false(any(grepl("\\*\\*", table_note("Plain."))))
  expect_error(table_note("x", label = c("a", "b")), "label")
})
```

Run: `cd r && RENV_PROFILE=report Rscript -e 'testthat::test_local("oaireport", filter = "brief|notes")'`
Expected: FAIL with `could not find function "typst_text"`, and the label test fails with `unused argument (label = …)`.

- [ ] **Step 2: Implement**

Create `r/oaireport/R/brief.R`:

```r
# Building blocks for a document that pitches results to another group (the walking-validation
# brief), shared with the technical report: colours, the estimate style, callout boxes, a
# sidebar beside a figure, a reading-guide box, numbered labels, the author line and Youden's J
# contours. Layout helpers return lines for a `results: asis` chunk; write them with
# cat(x, sep = "\n").

#' Colours shared by the brief and the report: the walking item, PASE, headings, tints for
#' reference groups, and the fills and rules of the callout boxes
brief_colours <- c(
  item = "#0072B2", pase = "#D55E00", navy = "#0b2e59", tint = "#eef4fb", muted = "#9fb6cf",
  pase_muted = "#f0b48e", note_fill = "#f5f9fd", warn = "#E69F00", warn_fill = "#fffaf0",
  warn_text = "#a86a00", label = "#34567a"
)

#' Escape text for Typst markup inside raw Typst blocks (Markdown is not processed there)
#'
#' "/" is escaped too, because "//" starts a Typst comment.
typst_text <- function(x) {
  if (!is.character(x)) stop("typst_text(): x must be character", call. = FALSE)
  x <- gsub("\\s+", " ", trimws(x))
  gsub("([\\\\#$*_`<>@~/\\[\\]])", "\\\\\\1", x, perl = TRUE)
}

#' An estimate with its 95% interval: "0.89 (0.86–0.91)"; " to " when a limit is negative
fmt_ci <- function(est, lo, hi, digits = 2) {
  f <- function(x) formatC(x, format = "f", digits = digits, big.mark = ",")
  sep <- ifelse(!is.na(lo) & !is.na(hi) & (lo < 0 | hi < 0), " to ", "–")
  ifelse(is.na(est), "–",
         ifelse(is.na(lo) | is.na(hi), f(est), paste0(f(est), " (", f(lo), sep, f(hi), ")")))
}

#' A callout box: "note" (blue rule: points in our favour, the ask) or "warn" (amber rule:
#' limitations and open questions). `cite` takes bibliography keys, cited Typst-natively.
callout <- function(text, kind = c("note", "warn"), title = NULL, cite = NULL, size = 9.5) {
  kind <- match.arg(kind)
  if (!is.null(cite) && (!is.character(cite) || any(!grepl("^[A-Za-z0-9_:-]+$", cite)))) {
    stop("callout(): cite must be bibliography keys (letters, digits, _ : -)", call. = FALSE)
  }
  rule <- brief_colours[[if (kind == "note") "item" else "warn"]]
  fill <- brief_colours[[if (kind == "note") "note_fill" else "warn_fill"]]
  ink <- brief_colours[[if (kind == "note") "item" else "warn_text"]]
  head <- if (is.null(title)) "" else
    sprintf('#text(weight: "bold", fill: rgb("%s"))[%s] ', ink, typst_text(title))
  cites <- if (is.null(cite)) "" else paste0(" ", paste0("@", cite, collapse = " "))
  c("", "```{=typst}",
    sprintf('#block(width: 100%%, inset: (x: 8pt, y: 6pt), fill: rgb("%s"), stroke: (left: 3pt + rgb("%s")), breakable: false)[',
            fill, rule),
    sprintf("#set text(size: %spt)", format(size)),
    paste0(head, typst_text(text), cites),
    "]", "```", "")
}

#' Page-1 layout: a shaded sidebar of key results and the ask, beside a figure and its caption
#'
#' `results` is a data frame with columns `value` (short: it is set at 15 pt in a narrow column)
#' and `label`; `image` is the figure's path relative to the document.
sidebar_figure <- function(results, ask, image, caption, caption_title = "Figure 1.",
                           heading = "Key results", sidebar = 0.31) {
  if (!is.data.frame(results) || !all(c("value", "label") %in% names(results))) {
    stop("sidebar_figure(): results needs columns value and label", call. = FALSE)
  }
  keys <- sprintf('#text(size: 15pt, weight: "bold", fill: rgb("%s"))[%s] \\ #text(size: 8pt)[%s] #v(6pt)',
                  brief_colours[["navy"]], typst_text(as.character(results$value)),
                  typst_text(as.character(results$label)))
  c("", "```{=typst}",
    sprintf("#grid(columns: (%s%%, 1fr), gutter: 12pt,", format(round(100 * sidebar))),
    sprintf('  block(fill: rgb("%s"), inset: 9pt, radius: 4pt, width: 100%%)[', brief_colours[["tint"]]),
    sprintf('    #text(size: 7pt, fill: rgb("%s"))[%s] #v(4pt)', brief_colours[["label"]],
            typst_text(toupper(heading))),
    paste0("    ", keys),
    sprintf('    #block(width: 100%%, stroke: (left: 3pt + rgb("%s")), fill: white, inset: 6pt)[#text(size: 8.5pt)[#text(weight: "bold", fill: rgb("%s"))[The ask.] %s]]',
            brief_colours[["item"]], brief_colours[["item"]], typst_text(ask)),
    "  ],",
    sprintf('  [#image("%s", width: 100%%) #text(size: 8pt)[#text(weight: "bold")[%s] %s]]',
            image, typst_text(caption_title), typst_text(caption)),
    ")", "```", "")
}

#' A reading-guide box: bold terms with their definitions, then a notation line
reading_guide <- function(definitions, notation, title = "How to read this report") {
  if (!is.character(definitions) || is.null(names(definitions)) || any(!nzchar(names(definitions)))) {
    stop("reading_guide(): definitions must be a named character vector", call. = FALSE)
  }
  items <- sprintf('#text(weight: "bold")[%s:] %s #v(3pt)', typst_text(names(definitions)),
                   typst_text(unname(definitions)))
  c("", "```{=typst}",
    sprintf('#block(width: 100%%, inset: 10pt, radius: 4pt, fill: rgb("%s"), breakable: false)[',
            brief_colours[["tint"]]),
    "#set text(size: 8.5pt)",
    sprintf('#text(size: 10pt, weight: "bold", fill: rgb("%s"))[%s] #v(4pt)', brief_colours[["navy"]],
            typst_text(title)),
    items, typst_text(notation), "]", "```", "")
}

#' Numbered labels: lab <- numberer("A"); lab("Table") gives "Table A1.", then "Table A2."
numberer <- function(prefix = "") {
  counts <- c(Table = 0L, Figure = 0L)
  function(kind = c("Table", "Figure")) {
    kind <- match.arg(kind)
    counts[[kind]] <<- counts[[kind]] + 1L
    sprintf("%s %s%d.", kind, prefix, counts[[kind]])
  }
}

#' The author and contact line from an untracked YAML file, or a neutral placeholder
#'
#' The file holds `authors` (entries with `name` and optional `affiliation`) and an optional
#' `contact` (`name`, `email`). It is never committed: *.local.yml is git-ignored.
author_block <- function(path, placeholder = "Authors and contact to be added") {
  if (!file.exists(path)) return(placeholder)
  info <- yaml::read_yaml(path)
  authors <- info$authors
  named <- function(a) is.list(a) && is.character(a$name) && length(a$name) == 1 && nzchar(a$name)
  if (!is.list(authors) || !length(authors) || !all(vapply(authors, named, logical(1)))) {
    stop("author_block(): ", path, " needs `authors`, a list of entries with a `name`", call. = FALSE)
  }
  who <- vapply(authors, function(a) {
    if (is.null(a$affiliation)) a$name else sprintf("%s (%s)", a$name, a$affiliation)
  }, character(1))
  line <- paste(who, collapse = ", ")
  contact <- info$contact
  if (!is.null(contact)) {
    if (!is.list(contact) || !is.character(contact$email) || !nzchar(contact$email)) {
      stop("author_block(): ", path, " has a `contact` without an `email`", call. = FALSE)
    }
    who_contact <- if (is.null(contact$name)) contact$email else sprintf("%s, %s", contact$name, contact$email)
    line <- sprintf("%s · Contact: %s", line, who_contact)
  }
  line
}

#' Lines of equal Youden's J on a sensitivity / (1 − specificity) plot
#'
#' Each line runs from (0, J) to (1 − J, 1); J = 0 is the chance diagonal. Its value is printed
#' just above the top edge where the line ends, so no label sits on a line or a point. Add to a
#' plot with `+`, together with coord_equal(xlim = c(0, 1), ylim = c(0, 1), clip = "off") and a
#' top margin of 14 pt or more.
youden_contours <- function(j = c(0, 0.1, 0.2, 0.3, 0.4)) {
  if (!is.numeric(j) || !length(j) || anyNA(j) || any(j < 0 | j >= 1)) {
    stop("youden_contours(): j must be numbers in [0, 1)", call. = FALSE)
  }
  lines <- do.call(rbind, lapply(j, function(x) data.frame(j = x, fpr = c(0, 1 - x), se = c(x, 1))))
  ends <- data.frame(j = j, fpr = 1 - j, se = 1,
                     label = ifelse(j == max(j), paste0("J = ", as.character(j)), as.character(j)))
  list(
    ggplot2::geom_line(data = lines, ggplot2::aes(fpr, se, group = j), inherit.aes = FALSE,
                       linewidth = 0.25, colour = "grey75", linetype = "dashed"),
    ggplot2::geom_text(data = ends, ggplot2::aes(fpr, se, label = label), inherit.aes = FALSE,
                       size = 2.2, colour = "grey45", vjust = -0.6, family = oai_font())
  )
}
```

In `r/oaireport/R/notes.R`:
- Change the signature to `table_note <- function(text, size = 8, close_group = FALSE, label = NULL)`.
- After the `size` check, add:

  ```r
    if (!is.null(label) && (!is.character(label) || length(label) != 1 || is.na(label) || !nzchar(label))) {
      stop("table_note(): label must be one string or NULL", call. = FALSE)
    }
  ```

- After the line that escapes `text` (it starts `text <- gsub("([\\\\*_`), add:

  ```r
    if (!is.null(label)) text <- paste0("**", label, "** ", text)
  ```

- Add `#' @param label A bold label put before the text (e.g. "Table A1."), or NULL.` to its roxygen block.

Append to `r/oaireport/NAMESPACE`:

```
export(brief_colours)
export(typst_text)
export(fmt_ci)
export(callout)
export(sidebar_figure)
export(reading_guide)
export(numberer)
export(author_block)
export(youden_contours)
```

In `r/oaireport/DESCRIPTION`, add `yaml` to the end of Imports, so it reads `ggplot2, grDevices, grid, jsonlite, ragg, stats, systemfonts, tinytable, utils, yaml`. Keep the field's existing line-wrapping style.

- [ ] **Step 3: Run the tests to verify they pass**

Run: `cd r && RENV_PROFILE=report Rscript -e 'testthat::test_local("oaireport", stop_on_failure = TRUE)'`
Expected: PASS, with 0 failures and 0 warnings.

Run: `git diff --exit-code -- r/renv.lock r/renv/profiles/report/renv.lock`
Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add r/oaireport
git commit -m "feat(oaireport): brief helpers — colours, estimate style, callouts, sidebar figure, reading guide, numbered labels, author line, Youden's J contours

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The brief

**Files:**
- Create:
  - `analyses/walking_validation/references.bib`;
  - `analyses/walking_validation/brief.qmd`;
  - `analyses/walking_validation/brief.local.example.yml`.
- Modify:
  - `analyses/walking_validation/analysis.toml` (`[report]`);
  - `.gitignore`;
  - `tests/test_walking_validation_realdata.py` (`test_walking_validation_report_renders`).

**Interfaces:**
- Consumes:
  - Task 1's `[report]` keys and Task 3's `render_report -> list[Path]`.
  - Task 4's helpers.
  - Run results:
    - `validity_classification` (sample, measure, estimate, lo, hi);
    - `validity_components_pase` (visit, component, comparator, level, statistic, estimate, lo, hi, n);
    - `validity_components_item` (sample, component, level, statistic, estimate, lo, hi, n);
    - `device_reproduction` (wave, release_days, matched_days, mv_mismatch_days, bout_mismatch_days);
    - the metric `sample.validation.persons`.
  - Run assumptions:
    - `components.answer_labels` (`pase_days`, `times`, …);
    - `device.purposeful_bout_minutes`, `device.mv_cutpoint`;
    - `reference.walker_rule`, `reference.min_bout_days_per_week`, `reference.min_bout_minutes_per_week`;
    - `pase.device_pairing`, `pase.walker_threshold`.
- Vocabulary actually present in the run:
  - PASE frequency `share` levels are `0`–`3`, and `se/sp/j` levels are `cut1`–`cut3`.
  - Weekly `rho` levels are `all` and `pase_walkers`; `median_diff` is `all`; `kappa/ppv/npv` are `guideline`. `median` levels are `0`, `<2`, `2–5`, `5–10`, `10+`.
  - Item `share` levels are `none`, `1`–`3`. `correction` exists for `lo_subset`/`times` only.
- Produces:
  - `brief.pdf` (≤ 6 pages) and `walking_validation_brief.pdf` (brief + report) in `<results>/walking_validation/report/`;
  - figures `brief_fig1`–`brief_fig4` in `figures/`.

- [ ] **Step 1: Write the failing realdata test**

In `tests/test_walking_validation_realdata.py`, replace the body of `test_walking_validation_report_renders`, from the `[pdf] = render_report(...)` line to the end, with:

```python
    pdfs = render_report(analysis, settings, echo=lambda _: None)
    assert [p.name for p in pdfs] == ["brief.pdf", "report.pdf", "walking_validation_brief.pdf"]
    pages = [len(PdfReader(p).pages) for p in pdfs]
    assert pages[0] <= 6, f"brief has {pages[0]} pages"
    assert pages[1] <= 18, f"report has {pages[1]} pages"
    assert pages[2] == pages[0] + pages[1]
    for pdf in pdfs[:2]:
        text = "\n".join(page.extract_text() for page in PdfReader(pdf).pages)
        for bad in (r"\bNA\b", r"\bNaN\b", r"\bInf\b", r"`r "):
            assert not re.search(bad, text), f"{bad!r} in {pdf.name}"
    if not (analysis.root / "brief.local.yml").exists():
        assert "Authors and contact to be added" in PdfReader(pdfs[0]).pages[0].extract_text()
    figures = {p.name for p in (pdfs[0].parent / "figures").iterdir()}
    for name in ("known_groups", "strata", "tipping", "forest_bias", "brief_fig1", "brief_fig4"):
        assert {f"{name}.pdf", f"{name}.png"} <= figures, name
    egress = settings.project["egress"]
    report = check_egress(
        pdfs[0].parent,
        min_cell=egress["min_cell"],
        small_cell=egress["small_cell"],
        ignore_id_pattern_columns=egress["ignore_id_pattern_columns"],
    )
    assert report.ok, report.problems
```

Add `import re` and `from pypdf import PdfReader` to the module's imports if they are not already there.

Run: `uv run pytest -m realdata -q tests/test_walking_validation_realdata.py -k report_renders`
Expected: FAIL. The returned names are `["report.pdf"]`.

- [ ] **Step 2: Write `references.bib`**

Create `analyses/walking_validation/references.bib`:

```bibtex
@article{lo2022,
  author = {Lo, Grace H. and Vinod, Surabhi and Richard, Michael J. and Harkey, Matthew S. and McAlindon, Timothy E. and Kriska, Andrea M. and Rockette-Wagner, Bonny and Eaton, Charles B. and Hochberg, Marc C. and Jackson, Rebecca D. and Kwoh, C. Kent and Nevitt, Michael C. and Driban, Jeffrey B.},
  title = {Association Between Walking for Exercise and Symptomatic and Structural Progression in Individuals With Knee Osteoarthritis: Data From the Osteoarthritis Initiative Cohort},
  journal = {Arthritis Rheumatol}, year = {2022}, volume = {74}, number = {10}, pages = {1660--1667},
  doi = {10.1002/art.42241}
}
@article{lo2015,
  author = {Lo, Grace H. and McAlindon, Timothy E. and Hawker, Gillian A. and Driban, Jeffrey B. and Price, Lori Lyn and Song, Jing and Eaton, Charles B. and Hochberg, Marc C. and Jackson, Rebecca D. and Kwoh, C. Kent and Nevitt, Michael C. and Dunlop, Dorothy D.},
  title = {Symptom Assessment in Knee Osteoarthritis Needs to Account for Physical Activity Level},
  journal = {Arthritis Rheumatol}, year = {2015}, volume = {67}, number = {11}, pages = {2897--2904},
  doi = {10.1002/art.39271}
}
@article{fenton2018,
  author = {Fenton, S. A. M. and Neogi, T. and Dunlop, D. and Nevitt, M. and Doherty, M. and Duda, J. L. and Klocke, R. and Abhishek, A. and Rushton, A. and Zhang, W. and Lewis, C. E. and Torner, J. and Kitas, G. and White, D. K.},
  title = {Does the Intensity of Daily Walking Matter for Protecting Against the Development of a Slow Gait Speed in People With or at High Risk of Knee Osteoarthritis? {An} Observational Study},
  journal = {Osteoarthritis Cartilage}, year = {2018}, volume = {26}, number = {9}, pages = {1181--1189},
  doi = {10.1016/j.joca.2018.04.015}
}
@article{master2021,
  author = {Master, Hiral and Thoma, Louise M. and Neogi, Tuhina and Dunlop, Dorothy D. and LaValley, Michael and Christiansen, Meredith B. and Voinier, Dana and White, Daniel K.},
  title = {Daily Walking and the Risk of Knee Replacement Over 5 Years Among Adults With Advanced Knee Osteoarthritis in the {United States}},
  journal = {Arch Phys Med Rehabil}, year = {2021}, volume = {102}, number = {10}, pages = {1888--1894},
  doi = {10.1016/j.apmr.2021.05.014}
}
@article{song2010,
  author = {Song, Jing and Semanik, Pamela and Sharma, Leena and Chang, Rowland W. and Hochberg, Marc C. and Mysiw, W. Jerry and Bathon, Joan M. and Eaton, Charles B. and Jackson, Rebecca and Kwoh, C. Kent and Nevitt, Michael and Dunlop, Dorothy D.},
  title = {Assessing Physical Activity in Persons With Knee Osteoarthritis Using Accelerometers: Data From the Osteoarthritis Initiative},
  journal = {Arthritis Care Res (Hoboken)}, year = {2010}, volume = {62}, number = {12}, pages = {1724--1732},
  doi = {10.1002/acr.20305}
}
@article{abel2008,
  author = {Abel, Mark G. and Hannon, James C. and Sell, Katie and Lillie, Tia and Conlin, Geri and Anderson, David},
  title = {Validation of the {Kenz Lifecorder EX} and {ActiGraph GT1M} Accelerometers for Walking and Running in Adults},
  journal = {Appl Physiol Nutr Metab}, year = {2008}, volume = {33}, number = {6}, pages = {1155--1164},
  doi = {10.1139/h08-103}
}
@article{storti2008,
  author = {Storti, Kristi L. and Pettee, Kelley K. and Brach, Jennifer S. and Talkowski, Jaime Berlin and Richardson, Caroline R. and Kriska, Andrea M.},
  title = {Gait Speed and Step-Count Monitor Accuracy in Community-Dwelling Older Adults},
  journal = {Med Sci Sports Exerc}, year = {2008}, volume = {40}, number = {1}, pages = {59--64},
  doi = {10.1249/mss.0b013e318158b504}
}
@article{tudorlocke2021,
  author = {Tudor-Locke, Catrine and Mora-Gonzalez, Jose and Ducharme, Scott W. and Aguiar, Elroy J. and Schuna, John M. and Barreira, Tiago V. and Moore, Christopher C. and Chase, Colleen J. and Gould, Zachary R. and Amalbert-Birriel, Marcos A. and Chipkin, Stuart R. and Staudenmayer, John},
  title = {Walking Cadence (Steps/Min) and Intensity in 61--85-Year-Old Adults: The {CADENCE-Adults} Study},
  journal = {Int J Behav Nutr Phys Act}, year = {2021}, volume = {18}, number = {1}, pages = {129},
  doi = {10.1186/s12966-021-01199-4}
}
@article{hagiwara2008,
  author = {Hagiwara, Akiko and Ito, Naomi and Sawai, Kazuhiko and Kazuma, Keiko},
  title = {Validity and Reliability of the {Physical Activity Scale for the Elderly (PASE)} in {Japanese} Elderly People},
  journal = {Geriatr Gerontol Int}, year = {2008}, volume = {8}, number = {3}, pages = {143--151},
  doi = {10.1111/j.1447-0594.2008.00463.x}
}
@article{heesch2011,
  author = {Heesch, Kristiann C. and Hill, Robert L. and van Uffelen, Jannique G. Z. and Brown, Wendy J.},
  title = {Are {Active Australia} Physical Activity Questions Valid for Older Adults?},
  journal = {J Sci Med Sport}, year = {2011}, volume = {14}, number = {3}, pages = {233--237},
  doi = {10.1016/j.jsams.2010.11.004}
}
@article{giles2009,
  author = {Giles, Kate and Marshall, Alison L.},
  title = {Repeatability and Accuracy of {CHAMPS} as a Measure of Physical Activity in a Community Sample of Older {Australian} Adults},
  journal = {J Phys Act Health}, year = {2009}, volume = {6}, number = {2}, pages = {221--229},
  doi = {10.1123/jpah.6.2.221}
}
@article{harris2009,
  author = {Harris, Tess J. and Owen, Christopher G. and Victor, Christina R. and Adams, Rika and Ekelund, Ulf and Cook, Derek G.},
  title = {A Comparison of Questionnaire, Accelerometer, and Pedometer: Measures in Older People},
  journal = {Med Sci Sports Exerc}, year = {2009}, volume = {41}, number = {7}, pages = {1392--1402},
  doi = {10.1249/MSS.0b013e31819b3533}
}
```

- [ ] **Step 3: Write `brief.qmd`**

Create `analyses/walking_validation/brief.qmd` with the content below. Every number comes from the run or from the cited literature.

````markdown
---
title: "Is reported walking really walking?"
subtitle: "Validating self-reported walking in the OAI against accelerometry — a proposal for joint work"
mainfont: Arial
fontsize: 10pt
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
        #set text(hyphenate: false)
        #set par(justify: false)
        #set bibliography(title: [References])
        #set page(footer: context align(center, text(size: 8pt, fill: luma(90))[Brief — page #counter(page).display()]))
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
assumption <- function(key) run$assumptions$assumptions[[key]]$value
num <- function(x, digits = 2) formatC(x, format = "f", digits = digits, big.mark = ",")
count <- function(x) formatC(x, format = "d", big.mark = ",")
fmt <- function(x) format(x, trim = TRUE, big.mark = ",")
pct <- function(x) paste0(num(100 * x, 0), "%")
range_text <- function(x, digits = 2) {
  lo <- num(min(x), digits); hi <- num(max(x), digits)
  if (lo == hi) lo else paste0(lo, "–", hi)
}
colours <- oaireport::brief_colours
# The one row matching every condition; stops when there is none or several (a changed schema)
one <- function(df, ...) {
  cond <- list(...)
  keep <- Reduce(`&`, Map(function(col, value) !is.na(df[[col]]) & df[[col]] == value, names(cond), cond))
  row <- df[keep, , drop = FALSE]
  if (nrow(row) != 1) {
    stop("expected one row for ", paste(names(cond), unlist(cond), sep = " = ", collapse = ", "),
         ", found ", nrow(row), call. = FALSE)
  }
  row
}
cls <- run$validity_classification
cp <- run$validity_components_pase
cp$visit <- sprintf("%02d", as.integer(cp$visit))
ci <- run$validity_components_item
pase <- function(v, component, comparator, level, statistic) {
  one(cp, visit = v, component = component, comparator = comparator, level = level, statistic = statistic)
}
item <- function(sample, component, level, statistic) {
  one(ci, sample = sample, component = component, level = level, statistic = statistic)
}
labels <- lapply(assumption("components.answer_labels"), unlist)
visits <- c("06", "08")
wave_names <- c(`06` = "48 months", `08` = "72 months")
paired <- assumption("pase.device_pairing") == "adjacent_wave"
device_wave_text <- if (paired) "that visit's own device wave" else "the participant's combined device waves"
pase_any_is_walker <- assumption("pase.walker_threshold") == 0
walker_rule <- assumption("reference.walker_rule")
rule_short <- switch(walker_rule,
  bout_days = sprintf("on average at least %s days a week with a purposeful bout", fmt(assumption("reference.min_bout_days_per_week"))),
  any_bout = "at least one purposeful bout",
  bout_minutes = sprintf("on average at least %s minutes a week in purposeful bouts", fmt(assumption("reference.min_bout_minutes_per_week"))),
  stop("unknown reference.walker_rule: ", walker_rule))

n_validation <- run$metrics[["sample.validation.persons"]]
se <- one(cls, sample = "validation", measure = "se")$estimate
sp <- one(cls, sample = "validation", measure = "sp")$estimate
j_item <- vapply(c("cut1", "cut3"), function(k) item("validation", "times", k, "j")$estimate, numeric(1))
j_pase_any <- vapply(visits, function(v) pase(v, "frequency", "device_walker", "cut1", "j")$estimate, numeric(1))
j_pase_mid <- vapply(visits, function(v) pase(v, "frequency", "device_walker", "cut2", "j")$estimate, numeric(1))
correction <- vapply(c("cut1", "cut3"), function(k) item("lo_subset", "times", k, "correction")$estimate, numeric(1))
strict <- labels$times[length(labels$times)]
bout_minutes <- assumption("device.purposeful_bout_minutes")
cutpoint <- assumption("device.mv_cutpoint")
guide <- assumption("reference.min_bout_minutes_per_week")
rho_week <- vapply(visits, function(v) pase(v, "weekly", "purposeful_week", "all", "rho")$estimate, numeric(1))
diff_week <- vapply(visits, function(v) pase(v, "weekly", "purposeful_week", "all", "median_diff")$estimate, numeric(1))
kappa_week <- vapply(visits, function(v) pase(v, "weekly", "purposeful_week", "guideline", "kappa")$estimate, numeric(1))
repro <- run$device_reproduction
repro$wave_name <- wave_names[sprintf("%02d", as.integer(repro$wave))]
```

```{r authors}
#| results: asis
cat("```{=typst}",
    sprintf("#text(size: 9.5pt, fill: luma(70))[%s] #v(4pt)",
            oaireport::typst_text(oaireport::author_block("brief.local.yml"))),
    "```", sep = "\n")
```

```{=typst}
#set text(size: 11.5pt)
```

The Osteoarthritis Initiative (OAI) asked participants whether they had walked for exercise since age 50, and the answer predicts knee outcomes [@lo2022]. We checked that answer, and the walking question of the Physical Activity Scale for the Elderly (PASE), against what the ActiGraph GT1M recorded at 48 and 72 months in `r count(n_validation)` participants. Almost everyone says yes, so the question alone separates walkers poorly; *how often* people say they walk carries most of the signal. Our device reference is built from activity counts, which cannot tell walking from other moderate activity, and that is where your step and cadence data come in.

```{=typst}
#set text(size: 10pt)
```

```{r fig1}
#| include: false
cuts <- c("cut1", "cut2", "cut3")
item_pts <- do.call(rbind, lapply(cuts, function(k) data.frame(
  source = "Walking item (times per month)", cut = k,
  se = item("validation", "times", k, "se")$estimate,
  fpr = 1 - item("validation", "times", k, "sp")$estimate,
  current = k == "cut1")))
pase_pts <- do.call(rbind, lapply(visits, function(v) do.call(rbind, lapply(cuts, function(k) data.frame(
  source = sprintf("PASE days per week, %s", wave_names[[v]]), cut = k,
  se = pase(v, "frequency", "device_walker", k, "se")$estimate,
  fpr = 1 - pase(v, "frequency", "device_walker", k, "sp")$estimate,
  current = k == "cut1" && pase_any_is_walker)))))
pts <- rbind(item_pts, pase_pts)
pts$source <- factor(pts$source, levels = unique(pts$source))
fig1 <- ggplot2::ggplot(pts, ggplot2::aes(fpr, se, colour = source, linetype = source)) +
  oaireport::youden_contours() +
  ggplot2::geom_line(linewidth = 0.6) +
  ggplot2::geom_point(ggplot2::aes(shape = current), size = 2.6) +
  ggplot2::scale_colour_manual(values = c(colours[["item"]], colours[["pase"]], colours[["pase"]]), name = NULL) +
  ggplot2::scale_linetype_manual(values = c("solid", "solid", "dashed"), name = NULL) +
  ggplot2::scale_shape_manual(values = c(`TRUE` = 17, `FALSE` = 16), name = NULL,
                              labels = c(`TRUE` = "Definition in use", `FALSE` = "Stricter, frequency-based")) +
  ggplot2::coord_equal(xlim = c(0, 1), ylim = c(0, 1), clip = "off") +
  ggplot2::labs(x = "1 − specificity", y = "Sensitivity") +
  oaireport::theme_oai(base_size = 8) +
  ggplot2::theme(legend.position = "bottom", legend.box = "vertical",
                 plot.margin = ggplot2::margin(14, 8, 4, 4))
oaireport::save_figure(fig1, "brief_fig1", "1col", height = 3.9)
```

```{r page1}
#| results: asis
# Sidebar values stay short (15 pt in a narrow column): PASE gives the 48-month value and puts
# the 72-month one in its label
results <- data.frame(
  value = c(sprintf("%s / %s", num(se), num(sp)),
            sprintf("%s → %s", num(j_item[[1]]), num(j_item[[2]])),
            sprintf("%s → %s", num(j_pase_any[["06"]]), num(j_pase_mid[["06"]])),
            sprintf("%s → %s", num(correction[[1]], 1), num(correction[[2]], 1))),
  label = c("sensitivity / specificity of “walked for exercise” against the device",
            sprintf("Youden's J: any walker → walks %s", strict),
            sprintf("Youden's J for PASE at 48 months: any walking → at least %s a week (72 months: %s → %s)",
                    labels$pase_days[3], num(j_pase_any[["08"]]), num(j_pase_mid[["08"]])),
            sprintf("how much a bias correction for Lo et al. 2022 would scale the result: any walker → %s", strict)))
cat(oaireport::sidebar_figure(
  results,
  ask = "A joint study: rebuild the reference from your step and cadence data (for example, minutes at 100 steps/min or more) and re-run the validation and the bias analysis, pre-specified and jointly authored.",
  image = "figures/brief_fig1.png",
  caption = "Each point is a walker definition, placed by its sensitivity and 1 − specificity against the device-defined walker. Triangles: the definitions in use (any walking). Stricter, frequency-based definitions (circles) move both questions up and to the left, toward better agreement. Grey dashed lines join points of equal Youden's J, with each value above the top edge; J = 0 is chance."),
  sep = "\n")
```

*The appendix (the full technical report) gives the methods and every result, from the same analysis run.*

```{=typst}
#pagebreak()
```

## What the counts already show

Reported walking frequency tracks the device in a clear gradient, which a yes/no question discards.

```{r fig2}
#| fig-height: 2.6
#| results: asis
cat(oaireport::figure_group(), sep = "\n")
level_rows <- function(get, levels, names, question, fill) {
  do.call(rbind, lapply(seq_along(levels), function(i) {
    r <- get(levels[[i]])
    data.frame(question = question, answer = names[[i]], estimate = r$estimate, lo = r$lo, hi = r$hi,
               fill = if (i == 1) paste0(fill, "_ref") else fill)
  }))
}
bars <- rbind(
  level_rows(function(l) item("validation", "times", l, "share"),
             c("none", as.character(seq_along(labels$times))), c("Non-walkers", labels$times),
             "Walking item: times per month", "item"),
  level_rows(function(l) pase("06", "frequency", "device_walker", l, "share"),
             as.character(0:3), labels$pase_days, "PASE: days walked last week (48 months)", "pase"))
bars$answer <- factor(bars$answer, levels = rev(unique(bars$answer)))
bars$question <- factor(bars$question, levels = unique(bars$question))
x_top <- min(1, max(bars$hi, na.rm = TRUE) + 0.15)
fig2 <- ggplot2::ggplot(bars, ggplot2::aes(estimate, answer, fill = fill)) +
  ggplot2::geom_col(width = 0.65) +
  ggplot2::geom_errorbar(ggplot2::aes(xmin = lo, xmax = hi), width = 0.25, linewidth = 0.3, orientation = "y") +
  ggplot2::geom_text(ggplot2::aes(x = hi, label = pct(estimate)), hjust = -0.25, size = 2.6,
                     family = oaireport::oai_font()) +
  ggplot2::scale_fill_manual(values = c(item_ref = colours[["muted"]], item = colours[["item"]],
                                        pase_ref = colours[["pase_muted"]], pase = colours[["pase"]]),
                             guide = "none") +
  ggplot2::scale_x_continuous(labels = function(x) paste0(100 * x, "%"), limits = c(0, x_top), expand = c(0, 0)) +
  ggplot2::facet_wrap(~question, scales = "free_y") +
  ggplot2::labs(x = "Share who are device-defined walkers (95% CI)", y = NULL) +
  oaireport::theme_oai(base_size = 8)
oaireport::save_figure(fig2, "brief_fig2", "2col", height = 2.6)
print(fig2)
pase72 <- vapply(as.character(0:3), function(l) pase("08", "frequency", "device_walker", l, "share")$estimate, numeric(1))
cat(oaireport::table_note(sprintf(
  "Share of participants who are device-defined walkers (%s, where a purposeful bout is at least %s minutes at %s counts/min or more), by reported walking frequency, with Wilson 95%% CIs. Walking item: validation sample, non-walkers and the walkers who answered how many times a month they walked. PASE: participants with a 48-month PASE answer, against %s. At 72 months the PASE shares run from %s (never) to %s (5–7 days).",
  rule_short, fmt(bout_minutes), fmt(cutpoint), device_wave_text, pct(pase72[[1]]), pct(pase72[[4]])),
  label = "Figure 2.", close_group = TRUE), sep = "\n")
```

Combining PASE's two walking answers (days × hours a day) gives an estimate of weekly walking. It ranks people only modestly against the device's purposeful-bout minutes (Spearman ρ `r range_text(rho_week)`), sits a median of about `r range_text(diff_week, 0)` minutes a week above the device, and agrees weakly on who walks at least `r fmt(guide)` minutes a week (Cohen's κ `r range_text(kappa_week)`). That is in line with studies of self-reported walking against device steps in older adults, which found ρ of 0.17 to 0.42 [@hagiwara2008; @heesch2011; @giles2009; @harris2009].

```{r fig3}
#| fig-height: 2.6
#| results: asis
cat(oaireport::figure_group(), sep = "\n")
cal <- cp[cp$component == "weekly" & cp$comparator == "purposeful_week" & cp$statistic == "median", ]
cal$level <- factor(cal$level, levels = unique(cal$level))  # the step writes the bins in order
cal$visit_name <- wave_names[cal$visit]
fig3 <- ggplot2::ggplot(cal, ggplot2::aes(level, estimate)) +
  ggplot2::geom_pointrange(ggplot2::aes(ymin = lo, ymax = hi), colour = colours[["pase"]], size = 0.3) +
  ggplot2::geom_text(ggplot2::aes(y = hi, label = paste0("n = ", count(n))), vjust = -0.6, size = 2.2,
                     colour = "grey35", family = oaireport::oai_font()) +
  ggplot2::scale_y_continuous(expand = ggplot2::expansion(mult = c(0.05, 0.15))) +
  ggplot2::facet_wrap(~visit_name) +
  ggplot2::labs(x = "Estimated weekly walking from PASE (hours per week)",
                y = "Device purposeful-bout\nminutes per week") +
  oaireport::theme_oai(base_size = 8)
oaireport::save_figure(fig3, "brief_fig3", "2col", height = 2.6)
print(fig3)
cat(oaireport::table_note(sprintf(
  "Device purposeful-bout minutes per week (point: median; bar: interquartile range) within each band of estimated weekly walking from PASE (days × hours a day at the PASE scoring midpoints), against %s. n: participants in the band. A self-report that tracked the device would show medians rising steadily from left to right.",
  device_wave_text), label = "Figure 3.", close_group = TRUE), sep = "\n")
```

```{=typst}
#pagebreak()
```

## Why counts aren't enough, and what steps would add

```{r weak-link}
#| results: asis
cat(oaireport::callout(sprintf(
  "A purposeful bout is any run of at least %s minutes at %s counts/min or more. Cycling, yard work or stairs count; slow walking may not. The device-defined walker is therefore a proxy, so part of the low specificity may belong to the reference rather than to the question.",
  fmt(bout_minutes), fmt(cutpoint)), kind = "warn", title = "The weak link."), sep = "\n")
```

**Why it matters for Lo et al. 2022.** A record-level correction for misclassification divides by Youden's J, so a weak J makes the correction unstable. With the walker definition in use, a correction would scale the difference in walking prevalence between outcome groups by `r num(correction[[1]], 1)`; with the strictest frequency-based definition, by `r num(correction[[2]], 1)`.

```{r fig4}
#| fig-height: 2.1
#| results: asis
cat(oaireport::figure_group(), sep = "\n")
cut_names <- c(cut1 = "Any walker (in use)", cut2 = sprintf("At least %s", labels$times[2]), cut3 = labels$times[3])
cf <- do.call(rbind, lapply(names(cut_names), function(k) {
  r <- item("lo_subset", "times", k, "correction")
  data.frame(definition = cut_names[[k]], estimate = r$estimate, lo = r$lo, hi = r$hi)
}))
cf$definition <- factor(cf$definition, levels = rev(cut_names))
top <- max(c(cf$hi, cf$estimate), na.rm = TRUE) * 1.15
cf$hi_draw <- ifelse(is.na(cf$hi), top, cf$hi)
fig4 <- ggplot2::ggplot(cf, ggplot2::aes(estimate, definition)) +
  ggplot2::geom_col(fill = colours[["item"]], width = 0.6) +
  ggplot2::geom_errorbar(data = cf[!is.na(cf$hi), , drop = FALSE], ggplot2::aes(xmin = lo, xmax = hi),
                         width = 0.25, linewidth = 0.3, orientation = "y") +
  ggplot2::geom_segment(data = cf[is.na(cf$hi), , drop = FALSE],
                        ggplot2::aes(x = lo, xend = hi_draw, yend = definition), linewidth = 0.4,
                        arrow = ggplot2::arrow(length = ggplot2::unit(0.08, "in"))) +
  ggplot2::geom_text(ggplot2::aes(x = 0, label = paste0(num(estimate, 1), "×")), hjust = -0.2,
                     colour = "white", size = 2.8, fontface = "bold", family = oaireport::oai_font()) +
  ggplot2::scale_x_continuous(limits = c(0, top), expand = c(0, 0)) +
  ggplot2::labs(x = "Correction factor 1/J (95% CI)", y = NULL) +
  oaireport::theme_oai(base_size = 8)
oaireport::save_figure(fig4, "brief_fig4", "2col", height = 2.1)
print(fig4)
cat(oaireport::table_note(sprintf(
  "Lo et al. 2022 participants who answered the walking item and have device data (%s classified). For each walker definition by the times-per-month answer, 1/J is the factor by which a record-level misclassification correction scales the difference in walking prevalence between outcome groups, and its sampling error; the interval comes from J's 95%% CI.%s",
  count(item("lo_subset", "times", "cut1", "correction")$n),
  if (any(is.na(cf$hi))) " An arrow marks an interval with no upper limit (J's interval reaches 0)." else ""),
  label = "Figure 4.", close_group = TRUE), sep = "\n")
```

```{r steps-add}
#| results: asis
cat(oaireport::callout(
  "Walking-specific references: steps per day, minutes at 100 steps/min or more (about 3 METs in adults aged 61 to 85, without knee OA) and step-based bouts. OAI cadence bands at this threshold have already been used.",
  kind = "note", title = "What steps and cadence add.", cite = c("tudorlocke2021", "fenton2018", "master2021")), sep = "\n")
cat(oaireport::callout(
  "GT1M step counts come from the device's step-detection algorithm, which undercounts slow walking: 64% of steps were counted at 54 m/min, and 19% were missed below 0.8 m/s in adults around 79 years old. How should slow walkers with knee OA be handled?",
  kind = "warn", title = "An open question for your expertise.", cite = c("abel2008", "storti2008")), sep = "\n")
```

```{=typst}
#pagebreak()
```

## The proposed joint study

**Aim.** Revalidate the 96-month walking item and PASE walking, and redo the bias analysis of Lo et al. 2022, against walking-specific references (steps per day, minutes at 100 steps/min or more, step-based bouts) defined together and pre-specified.

```{r roles}
roles <- data.frame(
  `You bring` = c("Step and cadence data, and how they were derived",
                  "Step-algorithm expertise; handling of slow gait",
                  "Co-design of the reference definitions"),
  `We bring` = c("Coding of the walking item and PASE; an open, reproducible pipeline",
                 "Validation statistics; the Lo et al. 2022 bias analysis",
                 "Drafting; shared code; aggregate-only outputs"),
  check.names = FALSE)
oaireport::compare_table(roles, widths = c(1, 1), multipage = FALSE)
```

**What we would need.** The existing daily step and cadence-band summaries at 48 and 72 months [@lo2015; @fenton2018; @master2021]; per-minute steps, if available; and a short description of how the steps were derived. The public release holds activity counts only: which files hold the steps?

```{r built}
#| results: asis
matched <- sprintf("%s of %s release person-days at %s", count(repro$matched_days), count(repro$release_days),
                   repro$wave_name)
differ_text <- if (all(repro$mv_mismatch_days == 0 & repro$bout_mismatch_days == 0)) {
  "with the same moderate-to-vigorous and bout minutes on every matched day"
} else sprintf("with moderate-to-vigorous minutes differing on %s and bout minutes on %s matched days",
               count(sum(repro$mv_mismatch_days)), count(sum(repro$bout_mismatch_days)))
cat(oaireport::callout(sprintf(
  "Our pipeline rebuilds the OAI release's day-level accelerometry files from the minute counts, following the OAI processing standard: it matches %s, %s. A step-based reference therefore drops into the same validation and bias analyses.",
  paste(matched, collapse = " and "), differ_text), kind = "note", title = "Already built.", cite = "song2010"),
  sep = "\n")
```

**Outputs.** A joint paper (or papers) and shared, open code.

```{=typst}
#pagebreak()
```

**Appendix.** The technical report that follows gives the methods and every result of the validation and the bias analysis, generated from the same analysis run as this brief.
````

The bibliography renders after this line on page 5.

- [ ] **Step 4: Wire the manifest and ignore local files**

In `analyses/walking_validation/analysis.toml`, replace the `[report]` table with:

```toml
[report]
documents = ["brief.qmd", "report.qmd"]
combined = "walking_validation_brief.pdf"
part_titles = ["Brief", "Appendix: technical report"]
runs = ["default"]
assets = ["ASSUMPTIONS.md", "references.bib"]
local_assets = ["brief.local.yml"]
```

Append to `.gitignore`:

```
# Untracked per-user settings, e.g. the brief's author and contact block
*.local.yml
```

Create `analyses/walking_validation/brief.local.example.yml`. It is committed, and holds placeholders only:

```yaml
# Copy to brief.local.yml (git-ignored) and fill in; the brief prints these on page 1.
authors:
  - name: First Author
    affiliation: Institution
  - name: Second Author
    affiliation: Institution
contact:
  name: First Author
  email: first.author@example.org
```

Run: `uv run pytest -q tests/test_analyses.py tests/test_manifest.py`
Expected: PASS. The walking_validation manifest loads with its documents.

- [ ] **Step 5: Render and look**

Run: `uv run oai report walking_validation`. The default run already exists, so no `--run` is needed.
Expected: three `Report:` lines, for `brief.pdf`, `report.pdf` and `walking_validation_brief.pdf`.

Render every brief page to PNG and read each one. The page renderer is `swift /private/tmp/claude-501/-Users-spiewart-OAI/dfbe067a-077f-40ca-8e7f-4be05be5b6e7/scratchpad/pdfcheck/page.swift <pdf> <page> <png>`. If that path is gone, use `pdftoppm -r 110 -png <pdf> <prefix>`.

Check each page:
- **Page 1:**
  - the title, subtitle and author placeholder;
  - the 11.5-pt lead paragraph;
  - the sidebar (four key results, none wrapping mid-number, and the ask) beside Figure 1, with its J labels above the panel's top edge;
  - the appendix pointer;
  - the footer "Brief — page 1".
- **Page 2:** Figure 2's bars, with muted reference bars and direct labels; the weekly paragraph; Figure 3 in orange.
- **Page 3:** the amber "weak link" box, the "why it matters" paragraph, Figure 4, and the blue and amber boxes with superscript citations.
- **Page 4:** the aim, the roles table, the data request, the "Already built" box and the outputs.
- **Page 5:** the appendix line, then "References" with 12 entries.
- Every number matches the CSVs, and nothing reads "NA".

**Fixes to apply if needed:**
- **Page 1 overflows onto page 2.** Reduce `brief_fig1` to height 3.6, and the lead paragraph to 11 pt. Re-render.
- **The footer is missing** because Quarto's template resets the page. Move the `#set page(footer: …)` line out of `include-in-header` and into a raw `{=typst}` block at the top of the body (before the `authors` chunk). Do the same in Task 6.

Measure the right margin:

```bash
pdftotext -bbox ~/oai-work/results/walking_validation/report/brief.pdf - | grep -o 'xMax="[0-9.]*"' | sed 's/[^0-9.]//g' | sort -n | tail -1
```

Expected: ≤ 550.8.

Run: `uv run pytest -m realdata -q tests/test_walking_validation_realdata.py -k report_renders`
Expected: PASS.

Run: `uv run oai check-egress ~/oai-work/results/walking_validation/report`
Expected: 0 problems.

- [ ] **Step 6: Commit**

```bash
git add analyses/walking_validation/brief.qmd analyses/walking_validation/references.bib analyses/walking_validation/brief.local.example.yml analyses/walking_validation/analysis.toml .gitignore tests/test_walking_validation_realdata.py
git commit -m "feat(walking_validation): brief to the Northwestern accelerometry group, combined with the report as its appendix

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Appendix pass, report-wide (reading guide, estimate style, numbering, footer, colours, page budget)

**Files:**
- Modify: `analyses/walking_validation/report.qmd`

**Interfaces:**
- Consumes: Task 4's `fmt_ci`, `reading_guide`, `numberer`, `table_note(label =)` and `brief_colours`.
- Produces:
  - the setup-chunk helpers `lab` (a `numberer("A")`) and `dnum_ci`;
  - every table and figure legend labelled A1, A2, …;
  - the footer "Technical report — page n".
- Task 7 adds legends with `label = lab("Table")` and `label = lab("Figure")`.

- [ ] **Step 1: Footer, numbering and estimate helpers**

In the YAML `include-in-header: text: |` block, add a line after `#set text(hyphenate: false)`:

```
        #set page(footer: context align(center, text(size: 8pt, fill: luma(90))[Technical report — page #counter(page).display()]))
```

In the `setup` chunk, after the `dnum` line, add:

```r
# An estimate with its 95% interval, in the device measure's digits (counts/day without decimals)
dnum_ci <- function(est, lo, hi, measure) {
  ifelse(measure == "counts_per_day", oaireport::fmt_ci(est, lo, hi, 0), oaireport::fmt_ci(est, lo, hi, 2))
}
# Tables and figures are numbered A1, A2, ... (the report is the brief's appendix)
lab <- oaireport::numberer("A")
```

- [ ] **Step 2: Number every legend**

Run: `grep -n "table_note(" analyses/walking_validation/report.qmd`
It lists 25 calls. Add a `label =` argument to every call except the one in chunk `ledger-legend`:
- **Figures:** `label = lab("Figure")` for the calls in chunks `known-groups-figure`, `strata-figure`, `components-roc`, `components-calibration`, `components-agreement`, `tipping` and `forest-bias`. These are the calls with `close_group = TRUE`.
- **Tables:** `label = lab("Table")` for all the others:
  - `note-flow`, `note-reproduction`, `note-known-groups`, `note-dose`, `note-convergent`, `note-classification`;
  - `note-pase`, `note-components-frequency`, `note-components-duration`, `note-components-cuts`;
  - `note-components-weekly`, `note-components-guideline`, `note-components-item`, `note-components-correction`;
  - `note-pba`, `note-summary-level`, `note-priors`.

Leave the legend text unchanged. The labels are assigned in document order, because knitr runs the chunks in order.

- [ ] **Step 3: Contents and reading guide**

Insert immediately before the line `# Summary`, after the raw Typst block that sets `hyphenate: auto`:

````markdown
```{=typst}
#outline(title: [Contents], depth: 1, indent: auto)
#v(8pt)
```

```{r reading-guide}
#| results: asis
cat(oaireport::reading_guide(
  c(`Item walker` = item_def,
    `Device walker` = paste(device_def, device_detail),
    `PASE walker` = pase_def),
  notation = "Estimates are shown with their 95% confidence interval as 0.89 (0.86–0.91); “to” joins the limits when one is negative; “–” marks a value that cannot be computed. Tables and figures are numbered A1, A2, …; each legend defines its own labels and population."),
  sep = "\n")
```

```{=typst}
#pagebreak()
```
````

`item_def`, `device_def`, `device_detail` and `pase_def` are defined in the `legends` chunk, which runs before `# Summary`.

- [ ] **Step 4: One estimate style**

Make these replacements in `report.qmd`:
- **Chunk `known-groups-table`.**
  - `sprintf("%s (%s to %s)", dnum(all_kg$hl, m), dnum(all_kg$hl_lo, m), dnum(all_kg$hl_hi, m))` → `dnum_ci(all_kg$hl, all_kg$hl_lo, all_kg$hl_hi, m)`
  - `sprintf("%s (%s to %s)", dnum(all_kg$adj_diff, m), dnum(all_kg$adj_lo, m), dnum(all_kg$adj_hi, m))` → `dnum_ci(all_kg$adj_diff, all_kg$adj_lo, all_kg$adj_hi, m)`
- **Chunk `dose-table`.**
  - `sprintf("%s (%s to %s)", dnum(dz$adj_upper, m), dnum(dz$adj_upper_lo, m), dnum(dz$adj_upper_hi, m))` → `dnum_ci(dz$adj_upper, dz$adj_upper_lo, dz$adj_upper_hi, m)`
- **Chunk `convergent`.**
  - `sprintf("%s (%s to %s)", num(cv$rho), num(cv$lo), num(cv$hi))` → `oaireport::fmt_ci(cv$rho, cv$lo, cv$hi)`
- **Chunk `classification`.** Merge the `Estimate` and `95% CI` columns into one column:

  ```r
    `Estimate (95% CI)` = oaireport::fmt_ci(cls$estimate, cls$lo, cls$hi),
  ```

  Change `widths = c(1.4, 1, 1, 1.4, 1.4)` to `widths = c(1.4, 1, 2, 1.4)`.
- **Chunk `pase`.** Delete the `pase_estimate <- …` and `pase_ci <- …` statements. Replace `pz$cell <- …` with:

  ```r
  pz$cell <- ifelse(pz$statistic %in% c("hl", "adj_diff"), dnum_ci(pz$estimate, pz$lo, pz$hi, pz$measure),
                    oaireport::fmt_ci(pz$estimate, pz$lo, pz$hi))
  ```

- **Chunk `components-setup`.** Replace the body of `est_ci` so the function reads:

  ```r
  est_ci <- function(est, lo, hi, digits = 2) oaireport::fmt_ci(est, lo, hi, digits)
  ```

- **Chunk `components-correction`.** Change the format string `"%s (%s to %s)"` to `"%s (%s–%s)"`. The lower limit of 1/J is always positive.

Leave these unchanged, because they are ranges, not intervals:
- limits of agreement;
- `n_prior_text`;
- `reliability_n_text`;
- the IQR (`med_iqr`) and percent (`pct_ci`) cells;
- the odds-ratio intervals (`or_interval`, which keep "<0.01").

- [ ] **Step 5: Shared colours and page budget**

- **Chunk `components-calibration`.** Change `colour = oaireport::oai_palette[1]` to `colour = oaireport::brief_colours[["pase"]]`. This is PASE data.
- **Chunk `components-agreement`.** Change `scale_fill_gradient(low = "#cde2fb", high = "#0b3c8c", …)` to `scale_fill_gradient(low = oaireport::brief_colours[["tint"]], high = oaireport::brief_colours[["navy"]], …)`.
- **Chunk `tipping`.** Change `#| fig-height: 5.6` and `save_figure(tip, "tipping", "2col", height = 5.6)` to 4.6. After rendering, the page before the grid must not be more than about a quarter blank. If it is, try 4.2.

Task 7 handles the ROC colours.

- [ ] **Step 6: Render, measure, commit**

Run: `uv run oai report walking_validation`

```bash
uv run python -c "from pypdf import PdfReader; print(len(PdfReader('$HOME/oai-work/results/walking_validation/report/report.pdf').pages))"
pdftotext -bbox ~/oai-work/results/walking_validation/report/report.pdf - | grep -o 'xMax="[0-9.]*"' | sed 's/[^0-9.]//g' | sort -n | tail -1
```

Expected:
- ≤ 18 pages;
- largest xMax ≤ 547.2.

Read every report page as a PNG and confirm:
- page 1 holds the title, the contents and the reading guide;
- every legend starts with "Table A…" or "Figure A…", numbered in order;
- the footer reads "Technical report — page n";
- the merged estimate columns read "0.89 (0.86–0.91)".

```bash
git add analyses/walking_validation/report.qmd
git commit -m "feat(walking_validation): report reads as the brief's appendix — contents and reading guide, one estimate style, A-numbered legends, footer, shared colours, smaller tipping grid

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Appendix pass, the answer-level section (deferred fixes and the three missing results)

**Files:**
- Modify: `analyses/walking_validation/report.qmd`, section `# Answer-level sub-analyses`

**Interfaces:**
- Consumes:
  - Task 6's `lab`, `est_ci` (now `fmt_ci`) and the labels already added to this section's legends;
  - Task 4's `youden_contours` and `brief_colours`;
  - the components helpers `cp_get`, `ci_get`, `comp_p`, `count_na`, `pct_ci`, `med_iqr`, `comp_visits`, `answer_labels`, `boot_text`, `comp_paired`, `combined_text`, `pase_threshold`.

- [ ] **Step 1: The disclosure**

In the paragraph after `# Answer-level sub-analyses`, replace

```
These analyses are secondary. They were pre-specified on 2026-10-02 after an exploratory look at the PASE frequency answer, and they are reported for every pre-listed cut, without choosing an optimal one.
```

with

```
These secondary analyses were pre-specified on 2026-10-02, prompted by an exploratory look at the PASE frequency answer, so the PASE days-per-week rows repeat that look and are not confirmatory. Every pre-listed cut is reported; no optimal cut is chosen.
```

- [ ] **Step 2: Generated visit text**

In chunk `note-components-frequency`, replace the `freq_population <- …` statement with:

```r
visits_text <- paste(wave(comp_visits), collapse = " or ")
freq_population <- if (comp_paired) {
  sprintf("Validation-sample participants with a PASE walking answer and a valid device wave at the same visit (%s).", visits_text)
} else sprintf("Validation-sample participants with a PASE walking answer at %s. Every device value in these tables is %s, as for the walking item.", visits_text, combined_text)
```

- [ ] **Step 3: Split the cut table**

In chunk `components-cuts`:
- Keep everything up to and including `item_sample_names <- …`.
- Delete `cut_table`, its `rownames`, `block_titles`, `starts` and the final `tinytable::group_tt(...)` call.
- Append:

```r
pase_blocks <- cut_blocks[startsWith(names(cut_blocks), "PASE")]
item_blocks <- cut_blocks[!startsWith(names(cut_blocks), "PASE")]
# One table per answer source, each kept on its page
block_table <- function(blocks, titles) {
  table <- do.call(rbind, blocks)
  rownames(table) <- NULL
  starts <- cumsum(c(1, vapply(blocks, nrow, integer(1))))[seq_along(blocks)]
  tinytable::group_tt(
    oaireport::compare_table(table, widths = c(2.4, 1.6, 1.6, 1.6, 1.6, 1.6, 0.7), multipage = FALSE),
    i = as.list(stats::setNames(starts, titles)))
}
block_table(pase_blocks, sprintf("PASE walking days, %s", wave(comp_visits)))
```

Replace chunk `note-components-cuts` with these three chunks:

````markdown
```{r note-components-cuts}
#| results: asis
cut_pase_device <- if (comp_paired) "by the same visit's device wave alone" else sprintf("by %s", combined_text)
cut_pase_first <- if (pase_threshold == 0) "The first row (any walking) is the PASE walker used elsewhere in this report." else
  sprintf("The first row (any walking) is not the PASE walker used elsewhere in this report, a walking subscore above %s, which also depends on the hours answer.", fmt(pase_threshold))
cut_stats <- sprintf("Se, Sp, PPV, NPV: as defined under Classification, with Wilson 95%% CIs. J: Youden's J = Se + Sp − 1, with a %s; 0 means no better than chance and 1 is perfect. n: participants classified.", boot_text)
cat(oaireport::table_note(sprintf(
  "Each row classifies participants as walkers by one cut of the PASE days answer and compares that with the device walker (as defined under Classification) %s, in the population of the PASE frequency table. %s %s",
  cut_pase_device, cut_pase_first, cut_stats), label = lab("Table")), sep = "\n")
```

```{r components-cuts-item}
block_table(item_blocks, c(sprintf("Walking item, times per month: %s", item_sample_names),
                           sprintf("Walking item, months per year: %s", item_sample_names)))
```

```{r note-components-cuts-item}
#| results: asis
cat(oaireport::table_note(sprintf(paste(
  "Each row classifies participants as walkers by one cut of a walking-item amount answer and compares that with the device walker (as defined under Classification) over the participant's valid waves, in the validation sample or the Lo 2022 subset (as in the sample flow table).",
  "A cut is a frequency-restricted walker: a walker whose amount answer is in that band or a higher one; non-walkers fall below every cut, and walkers without an answer to that amount are left out of its rows. The first row of each block is the item walker, among walkers who answered that amount. %s"),
  cut_stats), label = lab("Table")), sep = "\n")
```
````

The order of `cut_blocks` (`PASE 06`, `PASE 08`, then times and months, each for the validation sample and then the Lo subset) matches these titles. Leave the `#show figure: set block(sticky: false)` block before the cuts, and the `sticky: true` block after them, where they are, so they enclose all three new chunks.

- [ ] **Step 4: ROC colours and contour labels off their lines**

In chunk `components-roc`:
- Delete the `iso <- …` line, the `geom_line(data = iso, …)` layer and the `geom_text(data = iso[…], …)` layer.
- Rebuild the plot so it reads:

```r
src <- levels(pts$source)
is_pase <- startsWith(src, "PASE")
roc <- ggplot2::ggplot(pts, ggplot2::aes(fpr, se, colour = source, shape = current)) +
  oaireport::youden_contours() +
  ggplot2::geom_line(ggplot2::aes(group = source, linetype = source), linewidth = 0.4) +
  ggplot2::geom_point(size = 2.2) +
  ggplot2::scale_colour_manual(values = stats::setNames(
    ifelse(is_pase, oaireport::brief_colours[["pase"]], oaireport::brief_colours[["item"]]), src), name = NULL) +
  ggplot2::scale_linetype_manual(values = stats::setNames(ifelse(is_pase & cumsum(is_pase) > 1, "dashed", "solid"), src),
                                 name = NULL) +
  ggplot2::scale_shape_manual(values = c(`TRUE` = 17, `FALSE` = 16), name = NULL,
                              labels = c(`TRUE` = "Definition used elsewhere", `FALSE` = if (pase_threshold == 0) "Stricter cut" else "Other cut")) +
  ggplot2::coord_equal(xlim = c(0, 1), ylim = c(0, 1), clip = "off") +
  ggplot2::labs(x = "1 − specificity", y = "Sensitivity") + oaireport::theme_oai() +
  ggplot2::theme(legend.position = "right", legend.box = "vertical", plot.margin = ggplot2::margin(14, 6, 4, 4))
```

In its legend, replace `Dashed lines join points of equal Youden's J; further up and to the left is better.` with `Blue: the walking item; orange: PASE (solid at the first visit, dashed at the second). Thin grey dashed lines join points of equal Youden's J, with each value printed above the top edge (J = 0 is chance); further up and to the left is better.`

- [ ] **Step 5: Legend fixes**

1. **Item table.** In chunk `components-item`, change `"Times per month (walkers since age 50)"` to `"Times per month"`. In `note-components-item`, after `with non-walkers as their own row.`, insert ` n: participants giving that answer (for non-walkers, all non-walkers in the sample).`
2. **Weekly legend.** In chunk `note-components-weekly`, add after `weekly_population <- …`:

   ```r
   walker_n <- vapply(comp_visits, function(v) sprintf("%s at %s",
     count_na(cp_get(v, "weekly", "purposeful_week", "pase_walkers", "rho", "n")), wave(v)), character(1))
   ```

   In the third `paste` part, change `"ρ: Spearman rank correlation (95%% CI), in everyone and among PASE walkers."` to `"ρ: Spearman rank correlation (95%% CI), in everyone and among PASE walkers (%s)."`. Add `paste(walker_n, collapse = " and ")` to the `sprintf` arguments, between `fmt(cutpoint)` and `reliability_text`.
3. **Agreement figure.** Restructure chunk `components-agreement` so the figure group opens only when there are hexagons:
   - Move `cat(oaireport::figure_group(), sep = "\n")` to the first line inside `if (nrow(hx)) {`.
   - Move the `shown <- …` statement and the `cat(oaireport::table_note(…, close_group = TRUE, label = lab("Figure")), sep = "\n")` call inside the same `if`, after `print(agree)`.
   - Add an `else` branch:

   ```r
   } else {
     cat(oaireport::table_note(sprintf("No hexagon held at least %s participants, so the agreement figure is not shown; the median difference and limits of agreement are in the weekly table.",
       fmt(assumption("components.min_cell_count")))), sep = "\n")
   }
   ```

- [ ] **Step 6: The three pre-specified results not yet shown**

1. **Trend across weekly bands (12a).** In chunk `components-calibration`, add before the `cat(oaireport::table_note(` call:

   ```r
   weekly_trend <- paste(vapply(comp_visits, function(v) sprintf("%s at %s",
     comp_p(cp_get(v, "weekly", "purposeful_week", "all", "jt_p")), wave(v)), character(1)), collapse = " and ")
   ```

   Append to its legend's format string ` Trend across the bands (Jonckheere–Terpstra, permutation test as in the dose–response table): p %s.`, and add `weekly_trend` as the last `sprintf` argument.
2. **Guideline PPV and NPV (12a).** In chunk `components-guideline`, add after the `Sp = …` column:

   ```r
                PPV = est_ci(r("ppv"), r("ppv", "lo"), r("ppv", "hi")),
                NPV = est_ci(r("npv"), r("npv", "lo"), r("npv", "hi")),
   ```

   Change `widths = c(1.2, 1.8, 1.8, 1.8, 1.8, 0.8)` to `widths = c(1.1, 1.6, 1.6, 1.6, 1.6, 1.6, 1.6, 0.7)`. In `note-components-guideline`, after the Sp sentence (`… (Wilson 95%% CIs);`), insert ` PPV and NPV: the share meeting it by self-report who meet it by the device, and the share not meeting it by self-report who do not meet it by the device (Wilson 95%% CIs);`.
3. **Lo-subset item shares and trend (12b).** After chunk `note-components-item`, add:

````markdown
```{r components-item-lo}
item_table_lo <- do.call(rbind, lapply(c("times", "months", "years"), function(component) {
  lv <- c("none", as.character(seq_along(answer_labels[[component]])))
  data.frame(
    Answer = c("Non-walkers", answer_labels[[component]]),
    n = count_na(sapply(lv, function(l) ci_get("lo_subset", component, l, "share", "n"))),
    `Device walkers, % (95% CI)` = sapply(lv, function(l) pct_ci(ci_get("lo_subset", component, l, "share"),
      ci_get("lo_subset", component, l, "share", "lo"), ci_get("lo_subset", component, l, "share", "hi"))),
    `Bout-days/week, median (IQR)` = sapply(lv, function(l) med_iqr(ci_get("lo_subset", component, l, "median"),
      ci_get("lo_subset", component, l, "median", "lo"), ci_get("lo_subset", component, l, "median", "hi"))),
    check.names = FALSE)
}))
rownames(item_table_lo) <- NULL
tinytable::group_tt(oaireport::compare_table(item_table_lo, widths = c(1.8, 0.7, 1.8, 1.8), multipage = FALSE),
                    i = as.list(stats::setNames(cumsum(c(1, sizes))[1:3], component_titles)))
```

```{r note-components-item-lo}
#| results: asis
no_band_lo <- vapply(c("times", "months", "years"), function(cmp) ci_get("lo_subset", cmp, "no_band", "count"), numeric(1))
cat(oaireport::table_note(sprintf(
  "Lo 2022 subset: the participants of Lo et al. 2022 who answered the walking item and have device data. Answer, n, device walkers and bout-days/week: as in the table above. Walkers who did not give a usable answer are not in that block's rows: %s for times per month, %s for months per year and %s for years. Trend in bout-days/week from non-walkers through the bands (Jonckheere–Terpstra): times per month p %s; months per year p %s.",
  count_na(no_band_lo[["times"]]), count_na(no_band_lo[["months"]]), count_na(no_band_lo[["years"]]),
  comp_p(ci_get("lo_subset", "times", "all", "jt_p")), comp_p(ci_get("lo_subset", "months", "all", "jt_p")))),
  label = lab("Table")), sep = "\n")
```
````

`sizes` and `component_titles` come from chunk `components-item`.

- [ ] **Step 7: Render, check, commit**

Run: `uv run oai report walking_validation`

Read every page of the answer-level section as PNGs, and check:
- the PASE and item cut tables are separate, and neither splits across pages;
- the ROC's J labels sit above the panel, off every line;
- the ROC colours are blue for the item and orange for PASE;
- the guideline table's PPV and NPV, the trend sentences and the Lo-subset table read correctly, and their numbers match `validity_components_pase.csv` and `validity_components_item.csv`.

Repeat the page count and xMax check from Task 6. Expected: ≤ 18 pages and xMax ≤ 547.2.

Run: `uv run pytest -m realdata -q tests/test_walking_validation_realdata.py -k report_renders`
Expected: PASS.

```bash
git add analyses/walking_validation/report.qmd
git commit -m "feat(walking_validation): answer-level section — split cut tables, ROC in item/PASE colours with J labels off the lines, legend fixes, trend across weekly bands, guideline PPV/NPV, Lo-subset item shares

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Docs, spec status, full verification

**Files:**
- Modify:
  - `docs/reporting.md`;
  - `analyses/walking_validation/README.md`;
  - `docs/superpowers/specs/2026-10-03-northwestern-brief-design.md`.

- [ ] **Step 1: Docs**

In `docs/reporting.md`, keep the fenced single-entry `[report]` example near the top, and add after it:

````markdown
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
````

In `analyses/walking_validation/README.md`, add a section at the end:

```markdown
## Sending the brief

`uv run oai report walking_validation` writes three PDFs to `<results>/walking_validation/report/`:

- `brief.pdf`: the 4–6 page brief to the accelerometry group;
- `report.pdf`: the technical report;
- `walking_validation_brief.pdf`: both joined, the brief first and the report as its appendix, with a bookmark for each part. **This is the file to send.**

The brief's author and contact line comes from `brief.local.yml`, which is git-ignored. Copy `brief.local.example.yml` to `brief.local.yml` and fill it in. Without the file, the brief prints a placeholder.

Run `uv run oai check-egress <results>/walking_validation/report` before sending.
```

In the spec:
- change `**Status:** Draft for review` to `**Status:** Implemented`;
- in §6.4, replace `The CSL file is committed in the analysis folder, in AMA style.` with `Typst's built-in american-medical-association style is used, so no CSL file is committed.`;
- in §5.6, after `The footer reads "Technical report — page n".`, add ` The brief's reads "Brief — page n".`

- [ ] **Step 2: Full verification**

```bash
uv run ruff check && uv run ruff format --check && uv run python scripts/check_no_data.py
uv run pytest -q
uv run pytest -m realdata -q
```

```bash
cd r && Rscript -e 'testthat::test_local("oaimodels", stop_on_failure = TRUE)' && RENV_PROFILE=report Rscript -e 'testthat::test_local("oaireport", stop_on_failure = TRUE); testthat::test_local("oaimodels", stop_on_failure = TRUE)'
```

```bash
git diff --exit-code main -- r/renv.lock r/renv/profiles/report/renv.lock && echo "lockfiles unchanged"
uv export --format requirements-txt --no-dev --no-emit-project --frozen | grep -c pypdf
git diff --name-only main | grep -E '\.(pdf|png|csv|parquet)$' || echo "no data or figure files on branch"
git ls-files | grep -c '\.local\.yml$'
```

Expected:
- every command passes;
- `lockfiles unchanged`;
- the pypdf count is `0`;
- `no data or figure files on branch`;
- the local-yml count is `0`.

- [ ] **Step 3: Commit**

```bash
git add docs/reporting.md analyses/walking_validation/README.md docs/superpowers/specs/2026-10-03-northwestern-brief-design.md
git commit -m "docs: multi-document reports; sending the walking-validation brief; spec implemented

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 4: Final clean-tree renders**

Run these after the final review's fixes are committed:
1. Check the tree is clean: `git status --porcelain` and `git ls-files -v | grep '^[a-z]'` must both print nothing.
2. Run `uv run oai run walking_validation`. This refreshes `run_info` to HEAD; the CSVs stay identical.
3. Run `uv run oai report walking_validation && uv run oai report lo2022_walking`.
4. Read every page of `walking_validation_brief.pdf` as PNGs.
5. Run `oai check-egress` on both report folders. Expected: 0 problems each.
