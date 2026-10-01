# Reporting Module + Lo 2022 Comparison Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A reusable R reporting layer (`oaireport`) and an `oai report` command that renders an analysis's Quarto report to PDF, first used for a result-by-result comparison of Lo et al. 2022 with our replication.

**Architecture:**
- **Provenance.** The Python runner records a `run_info.json` for every run.
- **Manifest.** A `[report]` section in `analysis.toml` names a `.qmd` file and the run labels it reads.
- **Rendering.** `oai report` copies the `.qmd` into `$OAI_RESULTS_DIR/<analysis>/report/` and renders it with Quarto → Typst. R chunks start through `r/step-profile.R` under a separate renv profile (`report`), which loads `oaimodels` and the new `oaireport` package (theme, figure export, forest plot, flow diagram, verdict tables, results loader).
- **Cleanup.** After a successful render, only the PDF and `figures/` remain.

**Tech Stack:**
- Python 3.11+: typer, polars, pytest.
- R ≥ 4.4 with renv 1.3 (new profile `report`): ggplot2 4.x, tinytable 0.19, ragg, systemfonts, knitr, rmarkdown, testthat, withr.
- Quarto 1.9 (`--to typst`), bundled with RStudio.

**Spec:** `docs/superpowers/specs/2026-09-30-reporting-module-and-lo2022-comparison-design.md`. Read §12 Amendments: they record what prototyping changed, and they bind.

## Global Constraints

**Repository and data**
- The repository is public. No data, frames, results or rendered reports go in git. Reports render only under `$OAI_RESULTS_DIR/<analysis>/report/`, which is outside the repo (enforced by `oai.config`).
- Report content is aggregate only: counts, means and odds ratios already in `comparison.csv` and the metrics files. No participant-level rows.
- Report text refers to "the authors" or "the original authors". It never describes a personal relationship with them.

**R environment**
- `r/renv.lock` must not change: the enclave bundle restores it.
- Reporting packages live only in `r/renv/profiles/report/renv.lock`.
- R steps run by `oai run` keep loading only `oaimodels`. `oaireport` loads only when `RENV_PROFILE=report`.

**Figures**
- Figure widths are `"1col"` = 3.5 in and `"2col"` = 7 in. Height defaults to 0.75 × width and is capped at 9 in.
- Each figure is written twice: a PDF via `grDevices::cairo_pdf`, and a PNG at 300 dpi via `ragg::agg_png`.
- Source palette, fixed order, never cycled: `#0072B2` (published), `#D55E00` (ours), `#009E73`, `#E69F00`, with shapes 16, 17, 15, 18.
- Verdict status: replicated `#0ca30c`, drift `#fab219`, missing `#d03b3b`. Status is always shown with a symbol (✓ △ –) and a word, never by colour alone.
- Sequential (heatmap) scale: `#cde2fb` → `#1c5cab`.
- Text is set in Arial when installed (`oai_font()`), otherwise `sans`. Body text is 7–9 pt.

**Rendering and egress**
- Quarto discovery order: `OAI_QUARTO`, then `[tools] quarto` in `config/oai.toml`, then `quarto` on `PATH`, then `/Applications/RStudio.app/Contents/Resources/app/quarto/bin/quarto`.
- Every report `.qmd` uses `format: typst` with `knitr: opts_chunk: dev: cairo_pdf`. Without `cairo_pdf`, Arial fails with "invalid font type".
- Tables use tinytable with `theme_typst(multipage = TRUE)` and relative column widths. Never use gt: its HTML inlining fails inside the RStudio bundle.
- No captions on tables that may span pages; use a Markdown heading instead.
- Egress fails closed. The report directory must hold only `<stem>.pdf` and `figures/*.{pdf,png}` after a successful render.

**Code style and commits**
- Python: ruff, line length 100. Run `uv run ruff check` and `uv run ruff format --check`.
- R: match `r/oaimodels` style (namespaced calls such as `ggplot2::`, hand-written NAMESPACE, testthat edition 3).
- Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Work on branch `feat/reporting` (created in Task 1). Do not push until Task 8.

## Review Focus

1. **A commit hash that looks like a participant ID.** About 2% of git SHAs contain a 9 followed by six digits between two letters, which the egress ID pattern flags. `run_info.json` must still pass egress. Pinned in Task 1 (`test_ignored_json_keys_skip_id_like_commit_hashes`).
2. **A run that failed or was interrupted** (`run_info.json` with `finished_utc: null`, or no file) must count as missing for `oai report` and must be an error in `load_results`. Pinned in Task 1 (`test_is_finished_false_for_missing_or_unfinished`), Task 5 (`load_results names the missing or unfinished run`) and Task 6 (`test_missing_runs_counts_only_finished_runs`).
3. **Re-rendering after an earlier render** must not leave stale files or figures behind. Pinned in Task 6 (`test_render_replaces_a_previous_report`).
4. **Report entry or asset paths that leave the analysis folder** (`../x`) must be rejected, because they are copied. Pinned in Task 2 (`test_invalid_report_sections`).
5. **Edge inputs to the figure functions:** a flow step missing from `labels`, a flow with no exclusions, more than four sources, or a source missing from `sources`. Each must give a clear message or a fallback, never a cryptic ggplot error. Pinned in Task 4.

---

## Interfaces at a glance

| Produced by | Name | Consumed by |
|---|---|---|
| Task 1 | `oai.runner.RUN_INFO_FILE = "run_info.json"` | 6 |
| Task 1 | `oai.runner.run_results_dir(analysis: Analysis, settings: Settings, label: str = "default") -> Path` | 6 |
| Task 1 | `oai.runner.is_finished(results: Path) -> bool` | 6 |
| Task 1 | `oai.runner.checkout_state(repo_root: Path \| None) -> tuple[str \| None, bool]` | — |
| Task 1 | `oai.runner.r_profile_env(settings: Settings) -> dict[str, str]` | 6 |
| Task 2 | `oai.manifest.ReportSpec(entry: str, runs: tuple[str, ...], assets: tuple[str, ...] = ())`; `Analysis.report: ReportSpec \| None` | 6, 7 |
| Task 3 | R: `oai_palette`, `oai_status`, `oai_font()`, `theme_oai(base_size = 8)`, `figure_dir()`, `save_figure(plot, name, width = c("1col", "2col"), height = NULL, dir = figure_dir())` | 4, 5, 7 |
| Task 4 | R: `forest_plot(estimates, ref = 1, log_scale = TRUE, facet = NULL, sources = NULL)`, `flow_diagram(flow, labels, published = NULL)` | 7 |
| Task 5 | R: `compare_table(df, widths = NULL, compact = FALSE)`, `format_verdicts(df, compact = FALSE)`, `load_results(root, labels)`, `parse_or(text)` | 7 |
| Task 6 | `oai.report.render_report(analysis, settings, *, run_missing=False, base_env=None, echo=print, bundles=QUARTO_BUNDLES) -> Path`, `find_quarto(env, configured=None, bundles=QUARTO_BUNDLES) -> Path`, `missing_runs(analysis, settings) -> list[str]`, `ReportError`; CLI `oai report NAME [--run]` | 7 |

---

### Task 1: Run provenance (`run_info.json`) and JSON keys in the egress allow-list

**Files:**
- Modify: `src/oai/runner.py`
- Modify: `src/oai/export/egress.py`
- Modify: `config/oai.toml` (`[egress] ignore_id_pattern_columns`)
- Modify: `docs/egress.md` (lines 16 and 41)
- Test: `tests/test_runner.py`, `tests/test_egress.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `RUN_INFO_FILE = "run_info.json"`;
  - `run_results_dir(analysis, settings, label="default") -> Path` (= `settings.results_dir / analysis.name / label`);
  - `checkout_state(repo_root) -> tuple[str | None, bool]`;
  - `is_finished(results: Path) -> bool`;
  - `r_profile_env(settings) -> dict[str, str]` (keys `OAI_R_DIR`, `R_PROFILE_USER`; empty outside a checkout).
  - Every `run_analysis` call writes `<results>/run_info.json` with these keys: `analysis`, `label`, `variant`, `git_commit`, `git_dirty`, `started_utc`, `finished_utc` (null until all selected steps succeed), `oai_version` and `steps`.
  - `check_egress` drops keys named in `ignore_id_pattern_columns` from `.json` files, at any depth, before its ID scan.

- [ ] **Step 0: Create the working branch**

```bash
git checkout -b feat/reporting
```

- [ ] **Step 1: Write the failing runner tests**

Append to `tests/test_runner.py`. Merge the imports into the file's import block; `RunnerError`, `run_analysis`, `runner` and `make_settings` already exist there.

```python
import json
import re
import subprocess

import oai


def read_run_info(tmp_path, label="default"):
    return json.loads((tmp_path / "results" / "toy" / label / "run_info.json").read_text())


def test_run_info_records_a_finished_run(toy, tmp_path):
    run_analysis(toy, make_settings(tmp_path), stage="local", echo=lambda _: None)
    info = read_run_info(tmp_path)
    assert info["analysis"] == "toy"
    assert info["label"] == "default"
    assert info["variant"] is None
    assert info["steps"] == ["a"]
    assert info["git_commit"] is None and info["git_dirty"] is False  # repo_root=None
    assert info["oai_version"] == oai.__version__
    assert info["started_utc"] <= info["finished_utc"]
    assert runner.is_finished(tmp_path / "results" / "toy" / "default")


def test_run_info_has_no_finish_time_when_a_step_fails(toy, tmp_path):
    (toy.root / "a.py").write_text("raise SystemExit(3)\n")
    with pytest.raises(RunnerError, match="exit code 3"):
        run_analysis(toy, make_settings(tmp_path), stage="local", echo=lambda _: None)
    assert read_run_info(tmp_path)["finished_utc"] is None
    assert not runner.is_finished(tmp_path / "results" / "toy" / "default")


@pytest.mark.parametrize("content", [None, "not json", "[]", '{"finished_utc": null}'])
def test_is_finished_false_for_missing_or_unfinished(tmp_path, content):
    if content is not None:
        (tmp_path / "run_info.json").write_text(content)
    assert not runner.is_finished(tmp_path)


def test_checkout_state_reports_commit_and_uncommitted_changes(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)

    git("init", "-q")
    (repo / "f.txt").write_text("x")
    git("add", "f.txt")
    git("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "init")
    commit, dirty = runner.checkout_state(repo)
    assert re.fullmatch(r"[0-9a-f]{40}", commit) and dirty is False
    (repo / "f.txt").write_text("y")
    assert runner.checkout_state(repo) == (commit, True)
    assert runner.checkout_state(None) == (None, False)
    outside = tmp_path / "plain"
    outside.mkdir()
    assert runner.checkout_state(outside) == (None, False)


def test_r_profile_env_only_inside_a_checkout(tmp_path):
    assert runner.r_profile_env(make_settings(tmp_path)) == {}
```

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/test_runner.py -q -k "run_info or is_finished or checkout_state or r_profile_env"`
Expected: FAIL. `read_run_info` raises FileNotFoundError, and the others fail with `AttributeError: module 'oai.runner' has no attribute 'is_finished'` (or `checkout_state` / `r_profile_env`).

- [ ] **Step 3: Implement provenance in the runner**

In `src/oai/runner.py`:

1. Add `run_info.json` to the module docstring after the `OAI_ASSUMPTIONS` line:

```python
Each run also writes OAI_RESULTS_DIR/run_info.json (analysis, label, variant, git commit,
start/finish times, oai version, steps); finished_utc stays null unless every step succeeds.
```

2. Replace the import block with:

```python
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from oai import __version__
from oai.assumptions import DEFAULT_LABEL, Resolved, load_assumptions
from oai.config import Settings
from oai.errors import OAIError
from oai.manifest import STAGES, Analysis, Step

RUN_INFO_FILE = "run_info.json"
```

3. Add these functions after `frame_dir`:

```python
def run_results_dir(analysis: Analysis, settings: Settings, label: str = DEFAULT_LABEL) -> Path:
    """Aggregate outputs of one run: <results_dir>/<analysis>/<label>."""
    return settings.results_dir / analysis.name / label


def checkout_state(repo_root: Path | None) -> tuple[str | None, bool]:
    """(HEAD commit, has uncommitted changes) of a git checkout; (None, False) outside one."""
    if repo_root is None or shutil.which("git") is None:
        return None, False
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True
    )
    if head.returncode != 0:
        return None, False
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo_root, capture_output=True, text=True
    )
    return head.stdout.strip(), bool(status.stdout.strip())


def is_finished(results: Path) -> bool:
    """True when results/run_info.json records a run whose steps all succeeded."""
    try:
        info = json.loads((results / RUN_INFO_FILE).read_text())
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(info, dict) and bool(info.get("finished_utc"))


def r_profile_env(settings: Settings) -> dict[str, str]:
    """OAI_R_DIR and R_PROFILE_USER, so R starts through r/step-profile.R (checkouts only)."""
    r_profile = settings.repo_root / "r" / "step-profile.R" if settings.repo_root else None
    if r_profile is None or not r_profile.is_file():
        return {}
    return {"OAI_R_DIR": str(r_profile.parent), "R_PROFILE_USER": str(r_profile)}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
```

4. In `step_env`, replace `results = settings.results_dir / analysis.name / resolved.label` with:

```python
    results = run_results_dir(analysis, settings, resolved.label)
```

5. In `step_env`, replace the four `r_profile` lines at the end (before `return env`) with:

```python
    for key, value in r_profile_env(settings).items():
        env.setdefault(key, value)
```

6. In `run_analysis`, replace everything from `env = step_env(...)` to the end of the function with:

```python
    env = step_env(analysis, settings, base_env, resolved=resolved)
    commit, dirty = checkout_state(settings.repo_root)
    info: dict[str, object] = {
        "analysis": analysis.name,
        "label": resolved.label,
        "variant": resolved.variant,
        "git_commit": commit,
        "git_dirty": dirty,
        "started_utc": _utc_now(),
        "finished_utc": None,
        "oai_version": __version__,
        "steps": [s.id for s in steps],
    }
    info_path = Path(env["OAI_RESULTS_DIR"]) / RUN_INFO_FILE
    info_path.write_text(json.dumps(info, indent=2))
    results: list[StepResult] = []
    for step, cmd in commands:
        echo(f"==> {analysis.name}:{step.id} [{resolved.label}] ({step.lang}, {step.stage})")
        proc = subprocess.run(cmd, cwd=analysis.root, env=env)
        results.append(StepResult(step.id, proc.returncode))
        if proc.returncode != 0:
            raise RunnerError(f"step {step.id!r} failed with exit code {proc.returncode}")
    info["finished_utc"] = _utc_now()
    info_path.write_text(json.dumps(info, indent=2))
    return results
```

- [ ] **Step 4: Run the runner tests**

Run: `uv run pytest tests/test_runner.py -q`
Expected: PASS (all tests, old and new).

- [ ] **Step 5: Write the failing egress tests**

Append to `tests/test_egress.py`. Merge the imports into the file's import block; `check_egress` is already imported there.

```python
import json
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
# A hex commit with FAKE_ID (already defined in this file) between letters: the ID pattern
# matches it. Built at runtime, like FAKE_ID, so the leak guard never sees the literal.
SHA_LIKE_ID = f"ab{FAKE_ID}cd" + "0" * 29


def test_ignored_json_keys_skip_id_like_commit_hashes(tmp_path):
    (tmp_path / "run_info.json").write_text(
        json.dumps({"git_commit": SHA_LIKE_ID, "label": "default"})
    )
    assert not check_egress(tmp_path, min_cell=5).ok  # scanned unless the key is ignored
    assert check_egress(tmp_path, min_cell=5, ignore_id_pattern_columns=["git_commit"]).ok


def test_ignored_json_keys_do_not_hide_other_values(tmp_path):
    (tmp_path / "run_info.json").write_text(
        json.dumps({"git_commit": "abc", "nested": {"note": f"x{FAKE_ID}y"}})
    )
    report = check_egress(tmp_path, min_cell=5, ignore_id_pattern_columns=["git_commit"])
    assert not report.ok


def test_unparseable_json_is_scanned_whole(tmp_path):
    (tmp_path / "broken.json").write_text(f'{{"git_commit": "ab{FAKE_ID}cd"')
    assert not check_egress(tmp_path, min_cell=5, ignore_id_pattern_columns=["git_commit"]).ok


def test_project_config_ignores_git_commit():
    project = tomllib.loads((REPO_ROOT / "config" / "oai.toml").read_text())
    assert "git_commit" in project["egress"]["ignore_id_pattern_columns"]
```

- [ ] **Step 6: Run them and watch them fail**

Run: `uv run pytest tests/test_egress.py -q -k "json or git_commit"`
Expected: FAIL. `test_ignored_json_keys_skip_id_like_commit_hashes` fails on its second assert, and `test_project_config_ignores_git_commit` fails. `test_unparseable_json_is_scanned_whole` and `test_ignored_json_keys_do_not_hide_other_values` already pass; they pin the fail-closed behavior.

- [ ] **Step 7: Implement the JSON key allow-list**

In `src/oai/export/egress.py`, add `import json` to the stdlib imports and `from typing import Any` to the typing imports. Then add this function above `check_egress`:

```python
def _without_keys(text: str, keys: set[str]) -> str:
    """JSON text minus the values of `keys` at any depth; unparseable text is returned whole."""

    def strip(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: strip(v) for k, v in value.items() if k not in keys}
        if isinstance(value, list):
            return [strip(v) for v in value]
        return value

    try:
        return json.dumps(strip(json.loads(text)))
    except json.JSONDecodeError:
        return text
```

In `check_egress`, replace

```python
            elif suffix in TEXT_SUFFIXES or suffix in SCANNED_REVIEW_SUFFIXES:
                if PARTICIPANT_ID.search(path.read_text(errors="replace")):
```

with

```python
            elif suffix in TEXT_SUFFIXES or suffix in SCANNED_REVIEW_SUFFIXES:
                text = path.read_text(errors="replace")
                if suffix == ".json" and ignore:
                    text = _without_keys(text, ignore)
                if PARTICIPANT_ID.search(text):
```

In `config/oai.toml`, replace the last two lines of `[egress]` with:

```toml
# Columns (and JSON keys, e.g. run_info.json's git_commit) whose values legitimately look
# like 7-digit numbers: GWAS base-pair positions, git commit hashes.
ignore_id_pattern_columns = ["POS", "BP", "position", "git_commit"]
```

In `docs/egress.md`:
- Replace the line-16 fragment `and columns listed in \`ignore_id_pattern_columns\` (e.g. GWAS base-pair \`POS\`) are skipped;` with `and columns or JSON keys listed in \`ignore_id_pattern_columns\` (e.g. GWAS base-pair \`POS\`, \`run_info.json\`'s \`git_commit\`) are skipped;`.
- Replace line 41 with `ignore_id_pattern_columns = ["POS", "BP", "position", "git_commit"]`.

- [ ] **Step 8: Run the egress tests and the whole suite**

Run: `uv run pytest tests/test_egress.py -q && uv run pytest -q`
Expected: PASS everywhere, with no new skips beyond the usual R and real-data skips.

- [ ] **Step 9: Commit**

```bash
uv run ruff check && uv run ruff format --check
git add src/oai/runner.py src/oai/export/egress.py config/oai.toml docs/egress.md tests/test_runner.py tests/test_egress.py
git commit -m "feat: record run_info.json provenance; egress may ignore JSON keys such as git_commit

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: `[report]` manifest section

**Files:**
- Modify: `src/oai/manifest.py`
- Test: `tests/test_manifest.py`

**Interfaces:**
- Consumes: `oai.assumptions.load_assumptions(root).variants` and `DEFAULT_LABEL`.
- Produces: `ReportSpec(entry, runs, assets)`, a frozen dataclass, and `Analysis.report: ReportSpec | None = None` (a new last field, so existing constructors keep working).
- Validation rules:
  - `entry` is a `.qmd` file directly in the analysis folder.
  - `runs` is a non-empty, duplicate-free list of strings; each run is `"default"` or a variant in `assumptions.toml`.
  - Each asset is a file directly in the analysis folder: no directories and no `..`, since all of these files are copied.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_manifest.py`. Add `import re` and `ReportSpec` to its imports.

```python
REPORT_MANIFEST = textwrap.dedent(
    """
    name = "demo"

    [[steps]]
    id = "frame"
    lang = "python"
    entry = "frame.py"

    [report]
    entry = "report.qmd"
    runs = ["default", "alt"]
    assets = ["notes.md"]
    """
)
REPORT_ASSUMPTIONS = textwrap.dedent(
    """
    [cohort.min_age]
    value = 50
    status = "confirmed"
    source = "test"

    [variants.alt]
    description = "older"
    set = { "cohort.min_age" = 60 }
    """
)


def write_report_analysis(tmp_path, manifest=REPORT_MANIFEST):
    root = write_analysis(tmp_path, manifest, files=("frame.py", "report.qmd", "notes.md"))
    (root / "assumptions.toml").write_text(REPORT_ASSUMPTIONS)
    return root


def test_report_section_parsed(tmp_path):
    analysis = load_analysis(write_report_analysis(tmp_path))
    assert analysis.report == ReportSpec("report.qmd", ("default", "alt"), ("notes.md",))


def test_report_section_is_optional(tmp_path):
    assert load_analysis(write_analysis(tmp_path, VALID)).report is None


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ('entry = "report.qmd"', 'entry = "missing.qmd"', "entry 'missing.qmd'"),
        ('entry = "report.qmd"', 'entry = "notes.md"', "must be a .qmd file"),
        ('entry = "report.qmd"', 'entry = "../demo/report.qmd"', "directly in"),
        ('runs = ["default", "alt"]', "runs = []", "non-empty list"),
        ('runs = ["default", "alt"]', 'runs = ["default", "default"]', "duplicates"),
        ('runs = ["default", "alt"]', 'runs = ["default", "nope"]', "runs nope are not"),
        ('assets = ["notes.md"]', 'assets = ["missing.md"]', "asset 'missing.md'"),
        ('assets = ["notes.md"]', 'assets = ["../demo/notes.md"]', "asset '../demo/notes.md'"),
        ('assets = ["notes.md"]', 'assets = "notes.md"', "assets must be a list"),
    ],
)
def test_invalid_report_sections(tmp_path, old, new, message):
    root = write_report_analysis(tmp_path, REPORT_MANIFEST.replace(old, new))
    with pytest.raises(ManifestError, match=re.escape(message)):
        load_analysis(root)
```

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/test_manifest.py -q -k report`
Expected: FAIL with `ImportError: cannot import name 'ReportSpec' from 'oai.manifest'`.

- [ ] **Step 3: Implement**

In `src/oai/manifest.py`:

1. Extend the imports:

```python
from collections.abc import Callable

from oai.assumptions import DEFAULT_LABEL, load_assumptions
```

2. Add after `ExportSpec`:

```python
@dataclass(frozen=True)
class ReportSpec:
    entry: str  # a .qmd file directly in the analysis folder
    runs: tuple[str, ...]  # run labels the report reads: "default" and/or variant names
    assets: tuple[str, ...] = ()  # files copied next to the entry before rendering
```

3. Add `report: ReportSpec | None = None` as the last field of `Analysis`, after `aggregate_outputs`.

4. Replace the last two lines of `_parse` with:

```python
    outputs = tuple(data.get("outputs", {}).get("aggregate", []))
    report = _parse_report(data["report"], root, fail) if "report" in data else None
    return Analysis(
        name, data.get("description", ""), root, inputs, tuple(steps), export, outputs, report
    )
```

5. Add below `_parse`:

```python
def _plain_file(root: Path, name: object) -> bool:
    """A bare file name (no directories) that exists directly in root."""
    return isinstance(name, str) and name == Path(name).name and (root / name).is_file()


def _parse_report(raw: Any, root: Path, fail: Callable[[str], NoReturn]) -> ReportSpec:
    if not isinstance(raw, dict):
        fail("[report] must be a table")
    entry = raw.get("entry")
    if not _plain_file(root, entry) or not str(entry).endswith(".qmd"):
        fail(f"[report] entry {entry!r} must be a .qmd file directly in {root}")
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
    return ReportSpec(str(entry), tuple(runs), tuple(assets))
```

- [ ] **Step 4: Run the tests, then the whole suite**

Run: `uv run pytest tests/test_manifest.py -q && uv run pytest -q`
Expected: PASS everywhere. `tests/test_analyses.py` still validates `lo2022_walking`, which has no `[report]` yet.

- [ ] **Step 5: Commit**

```bash
uv run ruff check && uv run ruff format --check
git add src/oai/manifest.py tests/test_manifest.py
git commit -m "feat: [report] manifest section (entry, runs, assets)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The `report` renv profile, the `oaireport` skeleton (style and export), the step profile, and CI

**Files:**
- Create: `r/renv/profiles/report/renv.lock`, `r/renv/profiles/report/renv/settings.json` and `r/renv/profiles/report/renv/.gitignore` (all generated by renv)
- Create: `r/oaireport/DESCRIPTION`, `r/oaireport/LICENSE`, `r/oaireport/NAMESPACE`
- Create: `r/oaireport/R/style.R`, `r/oaireport/R/export.R`
- Create: `r/oaireport/tests/testthat.R`, `r/oaireport/tests/testthat/helper-png.R`, `r/oaireport/tests/testthat/test-style.R`, `r/oaireport/tests/testthat/test-export.R`
- Modify: `r/step-profile.R`
- Modify: `.github/workflows/ci.yml`
- Test: `tests/test_r_interop.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `oai_palette` (4 hex values) and `oai_status` (named: replicated, drift, missing);
  - `oai_font()`: `"Arial"` or `"sans"`;
  - `theme_oai(base_size = 8)`;
  - `figure_dir()`: `$OAI_REPORT_DIR/figures`, or `tempdir()`;
  - `save_figure(plot, name, width = c("1col", "2col"), height = NULL, dir = figure_dir())`: writes `<dir>/<name>.pdf` and `.png` and returns the PDF path invisibly;
  - the R test command for this package: `cd r && RENV_PROFILE=report Rscript -e 'testthat::test_local("oaireport", stop_on_failure = TRUE)'`.

- [ ] **Step 1: Create the `report` profile without touching the default lockfile**

`r/.Rprofile` activates renv, and renv honors `RENV_PROFILE`. Prototyping this exact command against a copy of `r/` produced a 130-package profile lockfile and left `renv.lock` byte-identical.

```bash
cd r && RENV_PROFILE=report Rscript -e 'source("renv/activate.R"); renv::settings$snapshot.type("all"); renv::restore(lockfile = "renv.lock", prompt = FALSE); renv::install(c("ggplot2", "scales", "tinytable", "ragg", "systemfonts", "knitr", "rmarkdown", "withr"), prompt = FALSE); renv::snapshot(prompt = FALSE)' && cd ..
```

Expected: the output ends with `Lockfile written to ".../r/renv/profiles/report/renv.lock"`.

Then verify:

```bash
git diff --exit-code r/renv.lock && echo "default lockfile unchanged"
git status --short r/
git check-ignore -q r/renv/profiles/report/renv/library && echo "profile library ignored"
grep -c '"Package"' r/renv/profiles/report/renv.lock
```

Expected:
- `default lockfile unchanged`;
- `?? r/renv/profiles/`;
- `profile library ignored`;
- a package count above 100. The default lockfile has 82; the profile is a superset.

- [ ] **Step 2: Write the package metadata and the failing tests**

`r/oaireport/DESCRIPTION`:

```
Package: oaireport
Title: Publication Figures and Reports for OAI Analytics
Version: 0.1.0
Author: oai-analytics contributors
Maintainer: oai-analytics contributors <oai-analytics@users.noreply.github.com>
Description: ACR-style ggplot2 theme, figure export at journal column widths, forest
    plots, cohort flow diagrams, verdict tables and a results loader for analysis
    reports rendered with `oai report` (renv profile "report").
License: MIT + file LICENSE
Encoding: UTF-8
Depends: R (>= 4.4)
Imports: ggplot2, grDevices, grid, jsonlite, ragg, stats, systemfonts, tinytable, utils
Suggests: testthat (>= 3.0.0), withr
Config/testthat/edition: 3
```

`r/oaireport/LICENSE`:

```
YEAR: 2026
COPYRIGHT HOLDER: oai-analytics contributors
```

`r/oaireport/NAMESPACE` (empty for now, so the tests fail on missing functions rather than undefined exports):

```
# Exports are added as functions land.
```

`r/oaireport/tests/testthat.R`:

```r
library(testthat)
library(oaireport)

test_check("oaireport")
```

`r/oaireport/tests/testthat/helper-png.R`:

```r
# Width and height in pixels from a PNG's IHDR chunk.
png_size <- function(path) {
  con <- file(path, "rb")
  on.exit(close(con))
  bytes <- readBin(con, "raw", 24)
  to_int <- function(b) sum(as.integer(b) * 256^(3:0))
  c(width = to_int(bytes[17:20]), height = to_int(bytes[21:24]))
}
```

`r/oaireport/tests/testthat/test-style.R`:

```r
test_that("theme_oai is a bottom-legend classic theme in the report font", {
  theme <- theme_oai()
  expect_s3_class(theme, "theme")
  expect_equal(theme$legend.position, "bottom")
  expect_equal(theme$text$family, oai_font())
  expect_equal(theme$text$size, 8)
  expect_equal(theme_oai(9)$text$size, 9)
})

test_that("palette and status colours are fixed", {
  expect_equal(oai_palette, c("#0072B2", "#D55E00", "#009E73", "#E69F00"))
  expect_equal(oai_status, c(replicated = "#0ca30c", drift = "#fab219", missing = "#d03b3b"))
  expect_true(oai_font() %in% c("Arial", "sans"))
})
```

`r/oaireport/tests/testthat/test-export.R`:

```r
point_plot <- function() {
  ggplot2::ggplot(data.frame(x = 1, y = 1), ggplot2::aes(x, y)) + ggplot2::geom_point()
}

test_that("save_figure writes a vector PDF and a 300 dpi PNG at ACR widths", {
  dir <- withr::local_tempdir()
  path <- save_figure(point_plot(), "two", "2col", dir = dir)
  expect_equal(path, file.path(dir, "two.pdf"))
  expect_gt(file.size(path), 0)
  expect_equal(png_size(file.path(dir, "two.png")), c(width = 2100, height = 1575))
  save_figure(point_plot(), "one", "1col", dir = dir)
  one <- png_size(file.path(dir, "one.png"))
  expect_equal(one[["width"]], 1050)
  expect_lte(abs(one[["height"]] - 787.5), 1)
})

test_that("save_figure caps the height at 9 inches", {
  dir <- withr::local_tempdir()
  save_figure(point_plot(), "tall", "1col", height = 20, dir = dir)
  expect_equal(png_size(file.path(dir, "tall.png"))[["height"]], 2700)
})

test_that("save_figure rejects names that are not plain file stems", {
  expect_error(save_figure(point_plot(), "../x", dir = withr::local_tempdir()), "figure name")
})

test_that("figure_dir follows OAI_REPORT_DIR", {
  withr::local_envvar(OAI_REPORT_DIR = file.path("tmp", "rep"))
  expect_equal(figure_dir(), file.path("tmp", "rep", "figures"))
  withr::local_envvar(OAI_REPORT_DIR = "")
  expect_equal(figure_dir(), tempdir())
})
```

- [ ] **Step 3: Run them and watch them fail**

Run: `cd r && RENV_PROFILE=report Rscript -e 'testthat::test_local("oaireport", stop_on_failure = TRUE)'; cd ..`
Expected: FAIL with `could not find function "theme_oai"` (and `save_figure`, `figure_dir`) and `object 'oai_palette' not found`.

- [ ] **Step 4: Implement style and export**

`r/oaireport/R/style.R`:

```r
# ACR journal style (Arthritis & Rheumatology, Arthritis Care & Research): Arial or a
# sans fallback at 7-9 pt, classic axes, legend at the bottom.

# Okabe-Ito colours in fixed source order: published, ours, variant 1, variant 2.
# Never cycled: a fifth source is a facet or a separate figure.
oai_palette <- c("#0072B2", "#D55E00", "#009E73", "#E69F00")

# Verdict colours. Always shown with a symbol and a word, never colour alone.
oai_status <- c(replicated = "#0ca30c", drift = "#fab219", missing = "#d03b3b")

oai_font <- function() {
  if ("Arial" %in% systemfonts::system_fonts()$family) "Arial" else "sans"
}

theme_oai <- function(base_size = 8) {
  ggplot2::theme_classic(base_size = base_size, base_family = oai_font()) +
    ggplot2::theme(
      axis.text = ggplot2::element_text(size = base_size - 1, colour = "grey15"),
      axis.title = ggplot2::element_text(size = base_size),
      strip.background = ggplot2::element_blank(),
      strip.text = ggplot2::element_text(size = base_size, face = "bold"),
      legend.position = "bottom",
      legend.title = ggplot2::element_blank(),
      legend.text = ggplot2::element_text(size = base_size - 1),
      legend.key.size = ggplot2::unit(0.8, "lines"),
      plot.margin = ggplot2::margin(4, 6, 4, 4)
    )
}
```

`r/oaireport/R/export.R`:

```r
# Figures at journal column widths: a vector PDF (cairo, so fonts embed) and a 300 dpi PNG.

figure_widths <- c("1col" = 3.5, "2col" = 7)
max_figure_height <- 9

# `oai report` sets OAI_REPORT_DIR; outside a report, figures go to a temporary directory.
figure_dir <- function() {
  report_dir <- Sys.getenv("OAI_REPORT_DIR")
  if (nzchar(report_dir)) file.path(report_dir, "figures") else tempdir()
}

save_figure <- function(plot, name, width = c("1col", "2col"), height = NULL, dir = figure_dir()) {
  if (!grepl("^[A-Za-z0-9_-]+$", name)) {
    stop("figure name must use only letters, digits, '_' or '-': ", name, call. = FALSE)
  }
  width <- match.arg(width)
  w <- figure_widths[[width]]
  h <- min(if (is.null(height)) 0.75 * w else height, max_figure_height)
  dir.create(dir, recursive = TRUE, showWarnings = FALSE)
  pdf_path <- file.path(dir, paste0(name, ".pdf"))
  ggplot2::ggsave(pdf_path, plot, width = w, height = h, units = "in",
                  device = grDevices::cairo_pdf)
  ggplot2::ggsave(file.path(dir, paste0(name, ".png")), plot, width = w, height = h,
                  units = "in", dpi = 300, device = ragg::agg_png)
  invisible(pdf_path)
}
```

Replace `r/oaireport/NAMESPACE` with:

```
export(oai_palette)
export(oai_status)
export(oai_font)
export(theme_oai)
export(figure_dir)
export(save_figure)
```

- [ ] **Step 5: Run the R tests**

Run: `cd r && RENV_PROFILE=report Rscript -e 'testthat::test_local("oaireport", stop_on_failure = TRUE)'; cd ..`
Expected: `[ FAIL 0 | WARN 0 | SKIP 0 | PASS 14 ]`. The count may differ by a few if testthat counts compound expectations differently; any FAIL is a failure.

- [ ] **Step 6: Write the failing step-profile test**

Append to `tests/test_r_interop.py` (add `import os` to its imports):

```python
def _report_profile_ready() -> bool:
    if shutil.which("Rscript") is None:
        return False
    probe = subprocess.run(
        ["Rscript", "-e", "library(ggplot2); library(tinytable); library(knitr)"],
        cwd=R_DIR,
        capture_output=True,
        env={**os.environ, "RENV_PROFILE": "report"},
    )
    return probe.returncode == 0


@pytest.mark.skipif(not _report_profile_ready(), reason="the r/ report profile is not restored")
@pytest.mark.parametrize(("profile", "loaded"), [("report", "TRUE"), ("", "FALSE")])
def test_step_profile_loads_oaireport_only_in_report_profile(tmp_path, profile, loaded):
    env = {
        **os.environ,
        "OAI_R_DIR": str(R_DIR),
        "R_PROFILE_USER": str(R_DIR / "step-profile.R"),
        "RENV_PROFILE": profile,
    }
    out = subprocess.run(
        ["Rscript", "-e", 'cat("oaireport" %in% loadedNamespaces())'],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip().endswith(loaded)
```

Run: `uv run pytest tests/test_r_interop.py -q -k oaireport`
Expected: FAIL for `profile="report"` (the output ends with `FALSE`); PASS for `profile=""`.

- [ ] **Step 7: Load `oaireport` in the report profile**

Replace `r/step-profile.R` with:

```r
# Loaded via R_PROFILE_USER for every R step `oai run` launches from a checkout:
# activates the r/ renv library, then loads oaimodels from source so step scripts
# call oaimodels::fn() exactly as they will against the installed package in the enclave.
# `oai report` renders with RENV_PROFILE=report (r/renv/profiles/report), whose library adds
# the reporting packages; only then is oaireport loaded too.
local({
  owd <- setwd(Sys.getenv("OAI_R_DIR"))
  on.exit(setwd(owd))
  source("renv/activate.R")
})
pkgload::load_all(file.path(Sys.getenv("OAI_R_DIR"), "oaimodels"), quiet = TRUE, export_all = FALSE)
if (identical(Sys.getenv("RENV_PROFILE"), "report")) {
  pkgload::load_all(file.path(Sys.getenv("OAI_R_DIR"), "oaireport"), quiet = TRUE, export_all = FALSE)
}
```

Run: `uv run pytest tests/test_r_interop.py tests/test_lo2022_models.py -q`
Expected: PASS. The existing R steps still load under the default profile.

- [ ] **Step 8: Add the CI job**

Append this job to `.github/workflows/ci.yml` (under `jobs:`, after `r:`):

```yaml
  r-report:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: r
    steps:
      - uses: actions/checkout@v4
      - name: System libraries for ragg/systemfonts/textshaping
        run: sudo apt-get update && sudo apt-get install -y libfontconfig1-dev libfreetype-dev libharfbuzz-dev libfribidi-dev libpng-dev libjpeg-dev libtiff-dev libwebp-dev
      - uses: r-lib/actions/setup-r@v2
        with:
          r-version: "4.5.2"
          use-public-rspm: true
      - uses: r-lib/actions/setup-renv@v2
        with:
          working-directory: r
          profile: '"report"'
          cache-version: report-1
      - run: Rscript -e 'testthat::test_local("oaireport", stop_on_failure = TRUE)'
```

`setup-renv`'s `profile` input is forwarded to `renv::activate(profile = ...)` (verified in r-lib/actions@v2 `setup-renv/action.yaml`). The separate `cache-version` keeps this job's package cache apart from the `r` job's.

- [ ] **Step 9: Commit**

```bash
uv run pytest -q
git add r/renv/profiles r/oaireport r/step-profile.R .github/workflows/ci.yml tests/test_r_interop.py
git status --short   # nothing under r/renv/profiles/report/renv/library may be staged
git commit -m "feat: oaireport R package (ACR theme, figure export) in a separate renv 'report' profile

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: `forest_plot` and `flow_diagram`

**Files:**
- Create: `r/oaireport/R/figures.R`
- Modify: `r/oaireport/NAMESPACE`
- Test: `r/oaireport/tests/testthat/test-figures.R`

**Interfaces:**
- Consumes: `oai_palette`, `theme_oai()`, `oai_font()` (Task 3).
- Produces:
  - `forest_plot(estimates, ref = 1, log_scale = TRUE, facet = NULL, sources = NULL)` returns a ggplot. Layer 1 is the reference line and layer 2 the point ranges.
  - `flow_diagram(flow, labels, published = NULL)` returns a ggplot. Layer 4 holds the step-box text and layer 5 the exclusion-box text.
  - Count text uses `formatC(x, format = "d", big.mark = ",")`; plain `format` switches to scientific notation at 100,000.

- [ ] **Step 1: Write the failing tests**

`r/oaireport/tests/testthat/test-figures.R`:

```r
estimates <- data.frame(
  outcome = rep(c("New pain", "KL worse"), each = 2),
  source = rep(c("Published", "Ours"), 2),
  or = c(0.6, 0.66, 0.8, 0.82),
  lo = c(0.4, 0.47, 0.6, 0.62),
  hi = c(0.8, 0.94, 1.1, 1.10)
)

# Point colours keyed by odds ratio ("0.60", "0.66", ...); x is log10(or) on a log axis.
point_colours <- function(p, log_scale = TRUE) {
  points <- ggplot2::layer_data(p, 2)
  or <- if (log_scale) 10^points$x else points$x
  stats::setNames(points$colour, format(round(or, 2)))
}

test_that("forest_plot maps sources to fixed colours and shapes on a log axis", {
  p <- forest_plot(estimates)
  points <- ggplot2::layer_data(p, 2)
  expect_equal(sort(points$x), sort(log10(estimates$or)))
  colours <- point_colours(p)
  expect_equal(unname(colours[c("0.60", "0.66")]), oai_palette[1:2])
  expect_setequal(points$shape, c(16, 17))
  expect_equal(ggplot2::layer_data(p, 1)$xintercept, 0)
})

test_that("forest_plot puts the first outcome at the top", {
  points <- ggplot2::layer_data(forest_plot(estimates), 2)
  first <- round(10^points$x, 2) %in% c(0.6, 0.66)
  expect_gt(mean(points$y[first]), mean(points$y[!first]))
})

test_that("forest_plot honours a linear scale, facets in order and a given source order", {
  est <- rbind(transform(estimates, model = "Unadjusted"), transform(estimates, model = "Adjusted"))
  p <- forest_plot(est, log_scale = FALSE, facet = "model", sources = c("Ours", "Published"))
  expect_equal(ggplot2::layer_data(p, 1)$xintercept[1], 1)
  expect_s3_class(p$facet, "FacetWrap")
  expect_equal(levels(p$data$model), c("Unadjusted", "Adjusted"))
  expect_equal(levels(p$data$source), c("Ours", "Published"))
  expect_equal(unname(point_colours(p, log_scale = FALSE)[c("0.66", "0.60")]), oai_palette[1:2])
})

test_that("forest_plot rejects missing columns, unlisted sources and more than four sources", {
  expect_error(forest_plot(estimates[, -3]), "missing column\\(s\\): or")
  expect_error(forest_plot(estimates, sources = "Published"), "sources does not list: Ours")
  five <- data.frame(outcome = "x", source = letters[1:5], or = 1, lo = 0.5, hi = 2)
  expect_error(forest_plot(five), "at most 4 sources")
})

flow <- data.frame(
  step = c("all", "age50", "roa"),
  persons = c(4796, 4247, 2336),
  excluded_persons = c(0, 549, 1911),
  excluded_knees = c(0, 299, 0)
)

test_that("flow_diagram draws a box per step and side boxes for exclusions", {
  p <- flow_diagram(flow, labels = c(all = "Enrolled", age50 = "Age >= 50"))
  main <- ggplot2::layer_data(p, 4)$label
  side <- ggplot2::layer_data(p, 5)$label
  expect_equal(main, c("Enrolled\nn = 4,796", "Age >= 50\nn = 4,247", "roa\nn = 2,336"))
  expect_equal(side, c("Excluded: 549\n(299 knees)", "Excluded: 1,911"))
})

test_that("flow_diagram shows published counts in brackets", {
  p <- flow_diagram(
    flow,
    labels = c(roa = "Knee OA"),
    published = c(flow.roa.persons = 2356, flow.age50.excluded_knees = 300)
  )
  labels <- c(ggplot2::layer_data(p, 4)$label, ggplot2::layer_data(p, 5)$label)
  expect_true("Knee OA\nn = 2,336 [2,356]" %in% labels)
  expect_true("Excluded: 549\n(299 [300] knees)" %in% labels)
  expect_true("all\nn = 4,796" %in% labels)
})

test_that("counts keep thousands separators without scientific notation", {
  expect_equal(count_text(c(100000, 4796, 549)), c("100,000", "4,796", "549"))
})

test_that("flow_diagram handles a flow without exclusions and rejects bad input", {
  p <- flow_diagram(flow[1, ], labels = character())
  expect_length(ggplot2::layer_data(p, 4)$label, 1)
  expect_length(ggplot2::layer_data(p, 5)$label, 0)
  expect_error(flow_diagram(flow[, 1:2], labels = character()), "missing column")
  expect_error(flow_diagram(flow[0, ], labels = character()), "no steps")
})
```

- [ ] **Step 2: Run them and watch them fail**

Run: `cd r && RENV_PROFILE=report Rscript -e 'testthat::test_local("oaireport", stop_on_failure = TRUE)'; cd ..`
Expected: FAIL with `could not find function "forest_plot"` and `could not find function "flow_diagram"`.

- [ ] **Step 3: Implement**

`r/oaireport/R/figures.R`:

```r
# Figures for analysis reports, styled by theme_oai(): forest plots and cohort flow diagrams.

check_columns <- function(df, required, what) {
  missing <- setdiff(required, names(df))
  if (length(missing)) {
    stop(what, " is missing column(s): ", paste(missing, collapse = ", "), call. = FALSE)
  }
}

count_text <- function(x) formatC(x, format = "d", big.mark = ",")

# Odds ratios with 95% CIs, one row per outcome, sources dodged within a row.
# `estimates`: outcome, source, or, lo, hi (plus the `facet` column when given). Outcomes
# run top to bottom and facets left to right in order of first appearance; `sources` fixes
# the colour and shape order (default: order of first appearance). At most four sources.
forest_plot <- function(estimates, ref = 1, log_scale = TRUE, facet = NULL, sources = NULL) {
  check_columns(estimates, c("outcome", "source", "or", "lo", "hi", facet), "estimates")
  present <- unique(as.character(estimates$source))
  sources <- sources %||% present
  unlisted <- setdiff(present, sources)
  if (length(unlisted)) {
    stop("sources does not list: ", paste(unlisted, collapse = ", "), call. = FALSE)
  }
  if (length(sources) > length(oai_palette)) {
    stop("forest_plot shows at most ", length(oai_palette),
         " sources; split or facet the rest", call. = FALSE)
  }
  estimates$source <- factor(estimates$source, levels = sources)
  estimates$outcome <- factor(estimates$outcome, levels = rev(unique(estimates$outcome)))
  if (!is.null(facet)) {
    estimates[[facet]] <- factor(estimates[[facet]], levels = unique(estimates[[facet]]))
  }
  colours <- stats::setNames(oai_palette[seq_along(sources)], sources)
  shapes <- stats::setNames(c(16, 17, 15, 18)[seq_along(sources)], sources)
  p <- ggplot2::ggplot(estimates,
                       ggplot2::aes(x = or, y = outcome, colour = source, shape = source)) +
    ggplot2::geom_vline(xintercept = ref, linetype = "dashed", linewidth = 0.3, colour = "grey40") +
    ggplot2::geom_pointrange(ggplot2::aes(xmin = lo, xmax = hi),
                             position = ggplot2::position_dodge(width = 0.6, reverse = TRUE),
                             size = 0.3, linewidth = 0.5) +
    ggplot2::scale_colour_manual(values = colours, breaks = sources) +
    ggplot2::scale_shape_manual(values = shapes, breaks = sources) +
    ggplot2::labs(x = "Odds ratio (95% CI)", y = NULL) +
    theme_oai() +
    ggplot2::theme(panel.grid.major.x = ggplot2::element_line(colour = "grey90", linewidth = 0.25))
  if (log_scale) p <- p + ggplot2::scale_x_log10()
  if (!is.null(facet)) p <- p + ggplot2::facet_wrap(stats::as.formula(paste("~", facet)))
  p
}

# Cohort flow: a box per step with the participants remaining, and a side box for each
# later step that excluded anyone. `flow`: step, persons, excluded_persons, excluded_knees
# (as analyses write flow.csv). `labels` maps steps to text; unlisted steps show their name.
# `published` (named numeric, e.g. c(flow.roa.persons = 2356)) adds "[published]" after
# our count wherever a key flow.<step>.<column> exists. Save at about 0.8 in per step.
flow_diagram <- function(flow, labels, published = NULL) {
  check_columns(flow, c("step", "persons", "excluded_persons", "excluded_knees"), "flow")
  n <- nrow(flow)
  if (n == 0) stop("flow has no steps", call. = FALSE)
  count <- function(ours, step, column) {
    text <- count_text(ours)
    key <- paste("flow", step, column, sep = ".")
    if (key %in% names(published)) text <- sprintf("%s [%s]", text, count_text(published[[key]]))
    text
  }
  box_w <- 0.9
  side_w <- 0.8
  box_h <- 0.3
  y <- rev(seq_len(n)) - 1
  side_x <- box_w / 2 + 0.35 + side_w / 2
  main <- data.frame(x = 0, y = y, label = vapply(seq_len(n), function(i) {
    step <- flow$step[[i]]
    name <- if (step %in% names(labels)) labels[[step]] else step
    paste0(name, "\nn = ", count(flow$persons[[i]], step, "persons"))
  }, character(1)))
  ex <- which(flow$excluded_persons > 0 & seq_len(n) > 1)
  side <- data.frame(x = rep(side_x, length(ex)), y = y[ex] + 0.5, label = vapply(ex, function(i) {
    step <- flow$step[[i]]
    text <- paste("Excluded:", count(flow$excluded_persons[[i]], step, "excluded_persons"))
    if (flow$excluded_knees[[i]] > 0) {
      text <- sprintf("%s\n(%s knees)", text, count(flow$excluded_knees[[i]], step, "excluded_knees"))
    }
    text
  }, character(1)))
  boxes <- rbind(
    data.frame(xmin = -box_w / 2, xmax = box_w / 2, ymin = y - box_h, ymax = y + box_h),
    data.frame(xmin = rep(side_x - side_w / 2, nrow(side)), xmax = rep(side_x + side_w / 2, nrow(side)),
               ymin = side$y - 0.8 * box_h, ymax = side$y + 0.8 * box_h)
  )
  down <- data.frame(x = rep(0, n - 1), xend = rep(0, n - 1), y = y[-n] - box_h, yend = y[-1] + box_h)
  across <- data.frame(x = rep(0, nrow(side)), xend = rep(side_x - side_w / 2, nrow(side)),
                       y = side$y, yend = side$y)
  arrow <- grid::arrow(length = grid::unit(0.05, "in"), type = "closed")
  ink <- "grey20"
  ggplot2::ggplot() +
    ggplot2::geom_rect(data = boxes, ggplot2::aes(xmin = xmin, xmax = xmax, ymin = ymin, ymax = ymax),
                       fill = "white", colour = ink, linewidth = 0.3) +
    ggplot2::geom_segment(data = down, ggplot2::aes(x = x, y = y, xend = xend, yend = yend),
                          arrow = arrow, linewidth = 0.3, colour = ink) +
    ggplot2::geom_segment(data = across, ggplot2::aes(x = x, y = y, xend = xend, yend = yend),
                          arrow = arrow, linewidth = 0.3, colour = ink) +
    ggplot2::geom_text(data = main, ggplot2::aes(x = x, y = y, label = label),
                       size = 2.6, family = oai_font(), lineheight = 0.95) +
    ggplot2::geom_text(data = side, ggplot2::aes(x = x, y = y, label = label),
                       size = 2.5, family = oai_font(), lineheight = 0.95) +
    ggplot2::coord_cartesian(xlim = c(-box_w / 2 - 0.05, side_x + side_w / 2 + 0.05),
                             ylim = c(-box_h - 0.05, n - 1 + box_h + 0.05), expand = FALSE) +
    ggplot2::theme_void(base_family = oai_font())
}
```

Append to `r/oaireport/NAMESPACE`:

```
export(forest_plot)
export(flow_diagram)
```

- [ ] **Step 4: Run the R tests**

Run: `cd r && RENV_PROFILE=report Rscript -e 'testthat::test_local("oaireport", stop_on_failure = TRUE)'; cd ..`
Expected: `FAIL 0`.

- [ ] **Step 5: Look at both figures**

```bash
cd r && RENV_PROFILE=report Rscript -e '
pkgload::load_all("oaireport", quiet = TRUE)
flow <- read.csv(file.path(Sys.getenv("HOME"), "oai-work/results/lo2022_walking/default/flow.csv"))
save_figure(flow_diagram(flow, c(age50 = "Age ≥ 50 years"), c(flow.roa.persons = 2356)), "flow_check", "2col", height = 0.8 * nrow(flow), dir = tempdir())
est <- data.frame(outcome = rep(c("New pain", "KL worse"), each = 2), source = rep(c("Published", "Ours"), 2), or = c(0.6, 0.66, 0.8, 0.82), lo = c(0.4, 0.47, 0.6, 0.62), hi = c(0.8, 0.94, 1.1, 1.1))
save_figure(forest_plot(est), "forest_check", "1col", dir = tempdir())
cat(tempdir(), "\n")'; cd ..
```

Read `<tempdir>/flow_check.png` and `<tempdir>/forest_check.png` with the Read tool. Expected:
- **Flow:** compact boxes with no overlapping text, and side boxes level with the arrows.
- **Forest:** one row per outcome, with published values in blue circles and ours in orange triangles. The x axis is logarithmic, with a dashed line at 1 and the legend at the bottom.

If the flow results file is absent, use the `flow` data frame from the tests instead.

- [ ] **Step 6: Commit**

```bash
git add r/oaireport
git commit -m "feat(oaireport): forest_plot and flow_diagram

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Verdict tables and the results loader

**Files:**
- Create: `r/oaireport/R/tables.R`, `r/oaireport/R/results.R`
- Modify: `r/oaireport/NAMESPACE`
- Test: `r/oaireport/tests/testthat/test-tables.R`, `r/oaireport/tests/testthat/test-results.R`

**Interfaces:**
- Consumes: the `comparison.csv` format (`metric, kind, published, ours, diff, verdict, related`) and the odds-ratio text `"0.6 (0.4-0.8) *"`, both from `oai.replication`; and `run_info.json` (Task 1).
- Produces:
  - **`format_verdicts(df, compact = FALSE)`.** Every column whose name starts with `verdict` becomes `"✓ replicated"`, `"△ drift"`, `"– missing"` or `""` (only the symbol when `compact = TRUE`).
  - **`compare_table(df, widths = NULL, compact = FALSE)`.** Returns a tinytable with `theme_typst(multipage = TRUE)`, verdict cells tinted (replicated `#e2f4e2`, drift `#fdf0d0`, missing `#f8e0e0`), and a notes line holding the legend and grading tolerances.
  - **`load_results(root = Sys.getenv("OAI_RESULTS_ROOT"), labels = <OAI_REPORT_RUNS split on ",">)`.** Returns a named list by label. Each element holds every `*.csv` by file stem (`flow`, `comparison`, `table2`, …), plus `metrics` (named numeric merged from `metrics_*.csv`), `assumptions` (the resolved JSON) and `run_info`.
  - **`parse_or(text)`.** Returns a data.frame with columns `or`, `lo`, `hi` and `sig` (NA where the text does not parse).

- [ ] **Step 1: Write the failing tests**

`r/oaireport/tests/testthat/test-tables.R`:

```r
comparison <- data.frame(
  metric = c("a", "b", "c", "d"),
  published = c("1", "2", "3", "4"),
  ours = c("1", "3", NA, "4"),
  verdict = c("replicated", "drift", "missing", NA)
)

test_that("format_verdicts turns verdicts into symbols and words", {
  out <- format_verdicts(comparison)
  expect_equal(out$verdict, c("✓ replicated", "△ drift", "– missing", ""))
  expect_equal(out$metric, comparison$metric)
  expect_equal(format_verdicts(comparison, compact = TRUE)$verdict,
               c("✓", "△", "–", ""))
})

test_that("format_verdicts formats every verdict* column and rejects unknown verdicts", {
  two <- transform(comparison, verdict_alt = rev(comparison$verdict))
  expect_equal(format_verdicts(two)$verdict_alt, c("", "– missing", "△ drift", "✓ replicated"))
  expect_error(format_verdicts(data.frame(verdict = "maybe")), "unknown verdict\\(s\\): maybe")
})

test_that("compare_table returns a tinytable and checks widths", {
  expect_s4_class(compare_table(comparison), "tinytable")
  expect_s4_class(compare_table(comparison, widths = c(2, 1, 1, 1.5), compact = TRUE), "tinytable")
  expect_s4_class(compare_table(data.frame(x = 1)), "tinytable")
  expect_error(compare_table(comparison, widths = c(1, 1)), "one value per column")
})
```

`r/oaireport/tests/testthat/test-results.R`:

```r
write_run <- function(root, label, finished = '"2026-09-30T12:00:00+00:00"') {
  dir <- file.path(root, label)
  dir.create(dir, recursive = TRUE)
  writeLines(sprintf('{"label": "%s", "finished_utc": %s}', label, finished),
             file.path(dir, "run_info.json"))
  utils::write.csv(data.frame(step = "all", persons = 10), file.path(dir, "flow.csv"),
                   row.names = FALSE)
  utils::write.csv(data.frame(metric = c("a", "b"), value = c(1, NA)),
                   file.path(dir, "metrics_one.csv"), row.names = FALSE)
  utils::write.csv(data.frame(metric = "c", value = 3), file.path(dir, "metrics_two.csv"),
                   row.names = FALSE)
  writeLines('{"label": "x", "assumptions": {"k": {"value": 1, "origin": "default"}}}',
             file.path(dir, "assumptions.resolved.json"))
  dir
}

test_that("load_results reads every CSV, merged metrics, assumptions and run info", {
  root <- withr::local_tempdir()
  write_run(root, "default")
  write_run(root, "alt")
  runs <- load_results(root, c("default", "alt"))
  expect_named(runs, c("default", "alt"))
  expect_equal(runs$alt$flow$persons, 10)
  expect_equal(runs$default$metrics, c(a = 1, b = NA, c = 3))
  expect_equal(runs$default$assumptions$assumptions$k$value, 1)
  expect_equal(runs$alt$run_info$label, "alt")
})

test_that("load_results takes its defaults from the oai report environment", {
  root <- withr::local_tempdir()
  write_run(root, "default")
  write_run(root, "alt")
  withr::local_envvar(OAI_RESULTS_ROOT = root, OAI_REPORT_RUNS = "default,alt")
  expect_named(load_results(), c("default", "alt"))
  withr::local_envvar(OAI_RESULTS_ROOT = "")
  expect_error(load_results(), "no results root")
})

test_that("load_results names the missing or unfinished run and how to produce it", {
  root <- withr::local_tempdir()
  write_run(root, "default", finished = "null")
  expect_error(load_results(root, "default"), "run 'default' did not finish.*oai report")
  expect_error(load_results(root, "alt"), "no run 'alt'.*--variant alt")
})

test_that("load_results refuses CSVs that shadow its own parts", {
  root <- withr::local_tempdir()
  dir <- write_run(root, "default")
  utils::write.csv(data.frame(x = 1), file.path(dir, "metrics.csv"), row.names = FALSE)
  expect_error(load_results(root, "default"), "metrics.csv")
})

test_that("parse_or reads graded odds-ratio text", {
  out <- parse_or(c("0.6 (0.4-0.8) *", "0.82 (0.62-1.10)", NA, "n/a"))
  expect_equal(out$or, c(0.6, 0.82, NA, NA))
  expect_equal(out$lo, c(0.4, 0.62, NA, NA))
  expect_equal(out$hi, c(0.8, 1.10, NA, NA))
  expect_equal(out$sig, c(TRUE, FALSE, NA, NA))
  expect_equal(nrow(parse_or(character())), 0)
})
```

- [ ] **Step 2: Run them and watch them fail**

Run: `cd r && RENV_PROFILE=report Rscript -e 'testthat::test_local("oaireport", stop_on_failure = TRUE)'; cd ..`
Expected: FAIL with `could not find function "format_verdicts"` (and `compare_table`, `load_results`, `parse_or`).

- [ ] **Step 3: Implement**

`r/oaireport/R/tables.R`:

```r
# Verdict tables (tinytable, Typst-ready). Verdicts come from oai.replication:
# replicated / drift / missing. Each shows a symbol and a word on a light status tint, so
# the table reads in greyscale. Long tables break across pages (theme_typst multipage); put
# their title in a heading, not a caption.

verdict_words <- c(replicated = "✓ replicated", drift = "△ drift", missing = "– missing")
verdict_symbols <- c(replicated = "✓", drift = "△", missing = "–")
verdict_tints <- c(replicated = "#e2f4e2", drift = "#fdf0d0", missing = "#f8e0e0")
verdict_note <- paste(
  "✓ replicated · △ drift · – missing.",
  "Counts replicate within 3% or 2, means within 0.5, odds ratios within 0.1 with the same significance."
)

format_verdicts <- function(df, compact = FALSE) {
  text <- if (compact) verdict_symbols else verdict_words
  for (j in grep("^verdict", names(df))) {
    v <- as.character(df[[j]])
    given <- !is.na(v) & nzchar(v)
    unknown <- setdiff(unique(v[given]), names(text))
    if (length(unknown)) {
      stop("unknown verdict(s): ", paste(unknown, collapse = ", "), call. = FALSE)
    }
    df[[j]] <- ifelse(given, unname(text[v]), "")
  }
  df
}

compare_table <- function(df, widths = NULL, compact = FALSE) {
  df <- as.data.frame(df)
  if (!is.null(widths) && length(widths) != ncol(df)) {
    stop("widths needs one value per column (", ncol(df), ")", call. = FALSE)
  }
  verdict_cols <- grep("^verdict", names(df))
  args <- list(format_verdicts(df, compact))
  if (length(verdict_cols)) args$notes <- verdict_note
  if (!is.null(widths)) args$width <- widths
  tab <- tinytable::theme_typst(do.call(tinytable::tt, args), multipage = TRUE)
  for (j in verdict_cols) {
    for (verdict in names(verdict_tints)) {
      i <- which(df[[j]] == verdict)
      if (length(i)) tab <- tinytable::style_tt(tab, i = i, j = j, background = verdict_tints[[verdict]])
    }
  }
  tab
}
```

`r/oaireport/R/results.R`:

```r
# Run results for reports. `oai report` sets OAI_RESULTS_ROOT (<results_dir>/<analysis>)
# and OAI_REPORT_RUNS (the [report] runs, comma-separated).

reserved_parts <- c("metrics", "assumptions", "run_info")

load_results <- function(root = Sys.getenv("OAI_RESULTS_ROOT"),
                         labels = strsplit(Sys.getenv("OAI_REPORT_RUNS"), ",", fixed = TRUE)[[1]]) {
  if (!nzchar(root)) stop("no results root: pass `root` or render with `oai report`", call. = FALSE)
  if (!length(labels)) stop("no run labels: pass `labels` or render with `oai report`", call. = FALSE)
  stats::setNames(lapply(labels, function(label) load_run(file.path(root, label), label)), labels)
}

load_run <- function(dir, label) {
  how <- sprintf("run `oai report <analysis> --run` (or `oai run <analysis>%s`)",
                 if (identical(label, "default")) "" else paste(" --variant", label))
  info_path <- file.path(dir, "run_info.json")
  if (!file.exists(info_path)) {
    stop(sprintf("no run '%s' in %s; %s", label, dirname(dir), how), call. = FALSE)
  }
  run_info <- jsonlite::read_json(info_path)
  if (is.null(run_info$finished_utc)) {
    stop(sprintf("run '%s' did not finish; %s", label, how), call. = FALSE)
  }
  csvs <- list.files(dir, pattern = "\\.csv$", full.names = TRUE)
  stems <- sub("\\.csv$", "", basename(csvs))
  shadowed <- stems %in% reserved_parts
  if (any(shadowed)) {
    stop("run '", label, "' has ", paste0(stems[shadowed], ".csv", collapse = ", "),
         ", which would shadow load_results() parts", call. = FALSE)
  }
  run <- stats::setNames(lapply(csvs, utils::read.csv, na.strings = c("", "NA")), stems)
  metrics <- do.call(rbind, run[startsWith(stems, "metrics_")])
  run$metrics <- if (is.null(metrics)) numeric() else stats::setNames(as.numeric(metrics$value), metrics$metric)
  assumptions_path <- file.path(dir, "assumptions.resolved.json")
  run$assumptions <- if (file.exists(assumptions_path)) jsonlite::read_json(assumptions_path)
  run$run_info <- run_info
  run
}

# "0.6 (0.4-0.8) *" (oai.replication's odds-ratio text; * = significant) -> or, lo, hi, sig.
parse_or <- function(text) {
  pattern <- "^\\s*([0-9.]+) \\(([0-9.]+)-([0-9.]+)\\)( \\*)?\\s*$"
  text <- as.character(text)
  n <- length(text)
  out <- data.frame(or = rep(NA_real_, n), lo = rep(NA_real_, n), hi = rep(NA_real_, n),
                    sig = rep(NA, n))
  ok <- !is.na(text) & grepl(pattern, text)
  if (any(ok)) {
    parts <- do.call(rbind, regmatches(text[ok], regexec(pattern, text[ok])))
    out$or[ok] <- as.numeric(parts[, 2])
    out$lo[ok] <- as.numeric(parts[, 3])
    out$hi[ok] <- as.numeric(parts[, 4])
    out$sig[ok] <- nzchar(parts[, 5])
  }
  out
}
```

Append to `r/oaireport/NAMESPACE`:

```
export(format_verdicts)
export(compare_table)
export(load_results)
export(parse_or)
```

- [ ] **Step 4: Run the R tests**

Run: `cd r && RENV_PROFILE=report Rscript -e 'testthat::test_local("oaireport", stop_on_failure = TRUE)'; cd ..`
Expected: `FAIL 0`.

- [ ] **Step 5: Commit**

```bash
git add r/oaireport
git commit -m "feat(oaireport): verdict tables, results loader and odds-ratio parser

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: `oai report`

**Files:**
- Create: `src/oai/report.py`
- Modify: `src/oai/cli.py`
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes:
  - from Task 1: `run_results_dir`, `is_finished`, `r_profile_env`, `run_analysis`;
  - from Task 2: `Analysis.report: ReportSpec | None`;
  - from Task 3: `r/step-profile.R`, which loads `oaireport` when `RENV_PROFILE=report`.
- Produces:
  - `ReportError(OAIError)`;
  - `find_quarto(env: Mapping[str, str], configured: str | None = None, bundles: Sequence[Path] = QUARTO_BUNDLES) -> Path`;
  - `missing_runs(analysis, settings) -> list[str]`;
  - `render_report(analysis, settings, *, run_missing=False, base_env=None, echo=print, bundles=QUARTO_BUNDLES) -> Path` (the PDF path);
  - CLI `oai report NAME [--run]`.
- Render environment:
  - `OAI_ANALYSIS`;
  - `OAI_RESULTS_ROOT` (= `<results_dir>/<analysis>`);
  - `OAI_REPORT_DIR` (= `<results_dir>/<analysis>/report`);
  - `OAI_REPORT_RUNS`;
  - `RENV_PROFILE=report`;
  - `OAI_R_DIR` and `R_PROFILE_USER`, set by `setdefault` only.

- [ ] **Step 1: Write the failing tests**

`tests/test_report.py`:

```python
"""`oai report`: render an analysis's Quarto report (fake quarto; one real render if available)."""

import json
import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from oai import config as oai_config
from oai.cli import app
from oai.config import load_settings
from oai.manifest import load_analysis
from oai.report import ReportError, find_quarto, missing_runs, render_report
from oai.runner import run_analysis

REPO = Path(__file__).resolve().parents[1]

MANIFEST = textwrap.dedent(
    """
    name = "toy"

    [[steps]]
    id = "a"
    lang = "python"
    entry = "a.py"

    [report]
    entry = "report.qmd"
    runs = ["default", "alt"]
    assets = ["notes.md"]
    """
)
ASSUMPTIONS = textwrap.dedent(
    """
    [cohort.min_age]
    value = 50
    status = "confirmed"
    source = "test"

    [variants.alt]
    description = "older"
    set = { "cohort.min_age" = 60 }
    """
)
STEP = 'import os, pathlib\npathlib.Path(os.environ["OAI_RESULTS_DIR"], "out.csv").write_text("metric,value\\nm,1\\n")\n'
# Stands in for `quarto render <entry> --to typst`, run in the report directory.
FAKE_QUARTO = textwrap.dedent(
    """\
    #!/bin/sh
    stem="${2%.qmd}"
    mkdir -p figures .quarto
    echo fig > figures/f.png
    echo scratch > .quarto/x
    echo typ > "$stem.typ"
    if [ -n "$FAKE_QUARTO_FAIL" ]; then echo "boom: render failed" >&2; exit 1; fi
    {
      echo "args=$*"
      echo "root=$OAI_RESULTS_ROOT"
      echo "report=$OAI_REPORT_DIR"
      echo "runs=$OAI_REPORT_RUNS"
      echo "profile=$RENV_PROFILE"
      ls
    } > "$stem.pdf"
    """
)


def make_toy(tmp_path, manifest=MANIFEST, qmd="# toy\n"):
    root = tmp_path / "analyses" / "toy"
    root.mkdir(parents=True)
    (root / "analysis.toml").write_text(manifest)
    (root / "assumptions.toml").write_text(ASSUMPTIONS)
    (root / "a.py").write_text(STEP)
    (root / "report.qmd").write_text(qmd)
    (root / "notes.md").write_text("notes\n")
    return load_analysis(root)


def make_settings(tmp_path, repo_root=None):
    env = {"OAI_WORK_DIR": str(tmp_path / "work"), "OAI_RESULTS_DIR": str(tmp_path / "results")}
    return load_settings(env=env, repo_root=repo_root)


def fake_quarto(tmp_path) -> Path:
    path = tmp_path / "bin" / "quarto"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(FAKE_QUARTO)
    path.chmod(0o755)
    return path


@pytest.fixture
def toy(tmp_path):
    return make_toy(tmp_path)


@pytest.fixture
def quarto_env(tmp_path):
    return {**os.environ, "OAI_QUARTO": str(fake_quarto(tmp_path))}


def quiet(_):
    pass


def test_render_needs_a_report_section(tmp_path, quarto_env):
    analysis = make_toy(tmp_path, MANIFEST.split("[report]")[0])
    with pytest.raises(ReportError, match="no \\[report\\] section"):
        render_report(analysis, make_settings(tmp_path), base_env=quarto_env, echo=quiet)


def test_missing_runs_counts_only_finished_runs(toy, tmp_path):
    settings = make_settings(tmp_path)
    assert missing_runs(toy, settings) == ["default", "alt"]
    run_analysis(toy, settings, echo=quiet)
    assert missing_runs(toy, settings) == ["alt"]
    info = tmp_path / "results" / "toy" / "default" / "run_info.json"
    info.write_text(json.dumps({**json.loads(info.read_text()), "finished_utc": None}))
    assert missing_runs(toy, settings) == ["default", "alt"]


def test_report_without_run_flag_names_missing_runs(toy, tmp_path, quarto_env):
    with pytest.raises(ReportError, match="default, alt.*oai report toy --run"):
        render_report(toy, make_settings(tmp_path), base_env=quarto_env, echo=quiet)


def test_run_flag_runs_only_the_missing_runs(toy, tmp_path, quarto_env):
    settings = make_settings(tmp_path)
    run_analysis(toy, settings, echo=quiet)
    default_info = (tmp_path / "results" / "toy" / "default" / "run_info.json").read_text()
    pdf = render_report(toy, settings, run_missing=True, base_env=quarto_env, echo=quiet)
    assert pdf.is_file()
    assert missing_runs(toy, settings) == []
    assert (tmp_path / "results" / "toy" / "default" / "run_info.json").read_text() == default_info


def test_render_copies_inputs_sets_env_and_keeps_only_pdf_and_figures(toy, tmp_path, quarto_env):
    pdf = render_report(
        toy, make_settings(tmp_path), run_missing=True, base_env=quarto_env, echo=quiet
    )
    out = (tmp_path / "results" / "toy" / "report").resolve()  # settings resolve paths
    assert pdf == out / "report.pdf"
    lines = pdf.read_text().splitlines()
    assert "args=render report.qmd --to typst" in lines
    assert f"root={(tmp_path / 'results' / 'toy').resolve()}" in lines
    assert f"report={out.resolve()}" in lines
    assert "runs=default,alt" in lines
    assert "profile=report" in lines
    assert {"report.qmd", "notes.md"} <= set(lines)  # copied before rendering
    assert sorted(p.name for p in out.iterdir()) == ["figures", "report.pdf"]
    assert (out / "figures" / "f.png").is_file()


def test_render_replaces_a_previous_report(toy, tmp_path, quarto_env):
    settings = make_settings(tmp_path)
    stale = tmp_path / "results" / "toy" / "report" / "figures" / "stale.png"
    stale.parent.mkdir(parents=True)
    stale.write_text("old")
    render_report(toy, settings, run_missing=True, base_env=quarto_env, echo=quiet)
    assert not stale.exists()


def test_failed_render_keeps_partial_output_and_shows_stderr(toy, tmp_path, quarto_env):
    with pytest.raises(ReportError, match="(?s)exit 1.*partial output kept.*boom: render failed"):
        render_report(
            toy,
            make_settings(tmp_path),
            run_missing=True,
            base_env={**quarto_env, "FAKE_QUARTO_FAIL": "1"},
            echo=quiet,
        )
    out = tmp_path / "results" / "toy" / "report"
    assert (out / "report.typ").is_file() and (out / "report.qmd").is_file()


def test_find_quarto_order(tmp_path):
    def exe(name):
        path = tmp_path / name / "quarto"
        path.parent.mkdir()
        path.write_text("#!/bin/sh\n")
        path.chmod(0o755)
        return path

    explicit, configured, on_path, bundle = exe("e"), exe("c"), exe("p"), exe("b")
    env = {"OAI_QUARTO": str(explicit), "PATH": str(on_path.parent)}
    assert find_quarto(env, str(configured), [bundle]) == explicit
    del env["OAI_QUARTO"]
    assert find_quarto(env, str(configured), [bundle]) == configured
    assert find_quarto(env, None, [bundle]) == on_path
    assert find_quarto({"PATH": str(tmp_path)}, None, [bundle]) == bundle
    with pytest.raises(ReportError, match="install it.*OAI_QUARTO"):
        find_quarto({"PATH": str(tmp_path)}, None, [tmp_path / "nope"])


def test_find_quarto_rejects_a_bad_explicit_path(tmp_path):
    with pytest.raises(ReportError, match="OAI_QUARTO=.*not an executable"):
        find_quarto({"OAI_QUARTO": str(tmp_path / "missing")}, None, [])
    with pytest.raises(ReportError, match="\\[tools\\] quarto=.*not an executable"):
        find_quarto({"PATH": ""}, str(tmp_path / "missing"), [])


def test_cli_report(tmp_path, monkeypatch):
    make_toy(tmp_path)
    monkeypatch.setenv("OAI_ANALYSES_DIR", str(tmp_path / "analyses"))
    monkeypatch.setenv("OAI_QUARTO", str(fake_quarto(tmp_path)))
    oai_config.get_settings.cache_clear()
    missing = CliRunner().invoke(app, ["report", "toy"])
    assert missing.exit_code == 1 and "--run" in missing.output
    result = CliRunner().invoke(app, ["report", "toy", "--run"])
    assert result.exit_code == 0, result.output
    assert "Report:" in result.output and "report.pdf" in result.output
    assert "oai check-egress" in result.output


def _report_tools_ready() -> bool:
    try:
        find_quarto(os.environ)
    except ReportError:
        return False
    if shutil.which("Rscript") is None:
        return False
    probe = subprocess.run(
        ["Rscript", "-e", "library(knitr); library(ggplot2); library(tinytable)"],
        cwd=REPO / "r",
        capture_output=True,
        env={**os.environ, "RENV_PROFILE": "report"},
    )
    return probe.returncode == 0


SMOKE_QMD = textwrap.dedent(
    """\
    ---
    format:
      typst:
        papersize: us-letter
    execute:
      echo: false
    knitr:
      opts_chunk:
        dev: cairo_pdf
    ---

    ```{r}
    p <- ggplot2::ggplot(data.frame(x = 1:3, y = 1:3), ggplot2::aes(x, y)) +
      ggplot2::geom_point() + oaireport::theme_oai()
    oaireport::save_figure(p, "smoke", "1col")
    p
    ```

    ```{r}
    oaireport::compare_table(data.frame(metric = "m", verdict = "replicated"))
    ```
    """
)


@pytest.mark.skipif(not _report_tools_ready(), reason="Quarto or the r/ report profile is unavailable")
def test_real_quarto_renders_with_oaireport(tmp_path):
    analysis = make_toy(tmp_path, MANIFEST.replace('runs = ["default", "alt"]', 'runs = ["default"]'), SMOKE_QMD)
    settings = make_settings(tmp_path, repo_root=REPO)
    pdf = render_report(
        analysis, settings, run_missing=True, base_env=dict(os.environ), echo=quiet
    )
    assert pdf.stat().st_size > 5_000
    assert sorted(p.name for p in pdf.parent.iterdir()) == ["figures", "report.pdf"]
    assert {p.name for p in (pdf.parent / "figures").iterdir()} == {"smoke.pdf", "smoke.png"}
```

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run pytest tests/test_report.py -q`
Expected: FAIL at collection with `ModuleNotFoundError: No module named 'oai.report'`.

- [ ] **Step 3: Implement `src/oai/report.py`**

```python
"""`oai report`: render an analysis's Quarto report ([report] in analysis.toml) to PDF.

The entry and its assets are copied into <results_dir>/<analysis>/report/ and rendered
there with `quarto render <entry> --to typst`, so nothing is written into the repository.
R chunks start through r/step-profile.R under the `report` renv profile, which loads
oaimodels and oaireport. After a successful render only the PDF and figures/ remain, so
`oai check-egress` sees nothing but reviewable outputs; a failed render is left in place.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from oai.assumptions import DEFAULT_LABEL
from oai.config import Settings
from oai.errors import OAIError
from oai.manifest import Analysis, ReportSpec
from oai.runner import is_finished, r_profile_env, run_analysis, run_results_dir

REPORT_DIR = "report"
FIGURES_DIR = "figures"
RENV_PROFILE = "report"
QUARTO_BUNDLES = (Path("/Applications/RStudio.app/Contents/Resources/app/quarto/bin/quarto"),)
STDERR_TAIL_LINES = 40


class ReportError(OAIError):
    """A report could not be prepared or rendered."""


def _executable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def find_quarto(
    env: Mapping[str, str],
    configured: str | None = None,
    bundles: Sequence[Path] = QUARTO_BUNDLES,
) -> Path:
    """OAI_QUARTO, then [tools] quarto in config/oai.toml, then PATH, then RStudio's bundle."""
    for source, raw in (("OAI_QUARTO", env.get("OAI_QUARTO")), ("[tools] quarto", configured)):
        if raw:
            path = Path(raw).expanduser()
            if not _executable(path):
                raise ReportError(f"{source}={raw} is not an executable Quarto")
            return path
    on_path = shutil.which("quarto", path=env.get("PATH"))
    if on_path:
        return Path(on_path)
    for bundle in bundles:
        if _executable(bundle):
            return bundle
    raise ReportError(
        "Quarto not found: install it (https://quarto.org) or set OAI_QUARTO to its path"
    )


def _spec(analysis: Analysis) -> ReportSpec:
    if analysis.report is None:
        raise ReportError(f"{analysis.name} has no [report] section in analysis.toml")
    return analysis.report


def missing_runs(analysis: Analysis, settings: Settings) -> list[str]:
    """The [report] runs without a finished run_info.json."""
    return [
        label
        for label in _spec(analysis).runs
        if not is_finished(run_results_dir(analysis, settings, label))
    ]


def _tail(text: str) -> str:
    return "\n".join(text.strip().splitlines()[-STDERR_TAIL_LINES:])


def render_report(
    analysis: Analysis,
    settings: Settings,
    *,
    run_missing: bool = False,
    base_env: Mapping[str, str] | None = None,
    echo: Callable[[str], None] = print,
    bundles: Sequence[Path] = QUARTO_BUNDLES,
) -> Path:
    """Render the analysis's report; returns the PDF path."""
    spec = _spec(analysis)
    env = dict(os.environ if base_env is None else base_env)
    missing = missing_runs(analysis, settings)
    if missing and not run_missing:
        raise ReportError(
            f"{analysis.name}: no finished run for {', '.join(missing)}; "
            f"run `oai report {analysis.name} --run` to run them first"
        )
    for label in missing:
        variant = None if label == DEFAULT_LABEL else label
        run_analysis(analysis, settings, variant=variant, base_env=env, echo=echo)
    quarto = find_quarto(env, settings.project.get("tools", {}).get("quarto"), bundles)
    results_root = settings.results_dir / analysis.name
    out = results_root / REPORT_DIR
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for name in (spec.entry, *spec.assets):
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
    echo(f"==> {analysis.name}: rendering {spec.entry} with {quarto}")
    proc = subprocess.run(
        [str(quarto), "render", spec.entry, "--to", "typst"],
        cwd=out,
        env=env,
        capture_output=True,
        text=True,
    )
    pdf = out / f"{Path(spec.entry).stem}.pdf"
    if proc.returncode != 0 or not pdf.is_file():
        raise ReportError(
            f"quarto render failed (exit {proc.returncode}); partial output kept in {out}\n"
            + _tail(proc.stderr or proc.stdout)
        )
    for child in out.iterdir():
        if child == pdf or child.name == FIGURES_DIR:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    return pdf
```

- [ ] **Step 4: Add the CLI command**

In `src/oai/cli.py`, add `from oai.report import render_report` to the imports. Then add this command after `run`:

```python
@app.command()
def report(
    name: Annotated[str, typer.Argument(help="Analysis folder name under analyses/.")],
    run_: Annotated[
        bool,
        typer.Option("--run", help="First run any [report] runs that have not finished."),
    ] = False,
) -> None:
    """Render an analysis's [report] (Quarto -> PDF) under OAI_RESULTS_DIR."""
    with user_errors():
        settings = get_settings()
        analysis = find_analysis(name, settings.analyses_dir)
        pdf = render_report(analysis, settings, run_missing=run_, echo=typer.echo)
    typer.echo(f"Report: {pdf}")
    typer.echo(f"Before sharing: oai check-egress {pdf.parent}")
```

- [ ] **Step 5: Run the tests, then the whole suite**

Run: `uv run pytest tests/test_report.py -q && uv run pytest -q`
Expected: PASS. `test_real_quarto_renders_with_oaireport` runs locally, where RStudio's Quarto and the report profile exist, and passes; in CI it is skipped.

- [ ] **Step 6: Commit**

```bash
uv run ruff check && uv run ruff format --check
git add src/oai/report.py src/oai/cli.py tests/test_report.py
git commit -m "feat: oai report renders an analysis's Quarto report to PDF

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: The Lo 2022 comparison report

**Files:**
- Create: `analyses/lo2022_walking/report.qmd`
- Modify: `analyses/lo2022_walking/analysis.toml` (add `[report]`)
- Modify: `analyses/lo2022_walking/README.md` (one paragraph)
- Test: `tests/test_lo2022_realdata.py`

**Interfaces:**
- Consumes:
  - `oaireport::load_results`, `parse_or`, `forest_plot`, `flow_diagram`, `compare_table`, `save_figure`, `oai_font`;
  - `oai report`;
  - result files `comparison.csv`, `flow.csv` and `metrics_*.csv`, with metric names as written by `lo2022.py` and `models.R`: `t2.<outcome>.or_adj[.lo|.hi]`, `t1.<characteristic>.<group>`, `t3.<outcome>.<alignment>.<group>.<events|n>`, `s1.<step>.<measure>`, `flow.<step>.<persons|excluded_persons|excluded_knees>`.
- Produces: `report.pdf` and the figures `flow`, `forest_table2`, `forest_supp2`, `forest_supp3`, `replication_grid` (each `.pdf` and `.png`).

- [ ] **Step 1: Write the failing real-data test**

Append to `tests/test_lo2022_realdata.py`. Add `import os` and these imports: `from oai.report import ReportError, find_quarto, render_report`.

```python
def _report_tools_ready() -> bool:
    try:
        find_quarto(os.environ)
    except ReportError:
        return False
    if shutil.which("Rscript") is None:
        return False
    probe = subprocess.run(
        ["Rscript", "-e", "library(knitr); library(ggplot2); library(tinytable); library(geepack)"],
        cwd=REPO / "r",
        capture_output=True,
        env={**os.environ, "RENV_PROFILE": "report"},
    )
    return probe.returncode == 0


@pytest.mark.realdata
@pytest.mark.skipif(not _report_tools_ready(), reason="Quarto or the r/ report profile is unavailable")
def test_lo2022_report_renders():
    settings = get_settings()
    analysis = find_analysis("lo2022_walking", settings.analyses_dir)
    pdf = render_report(analysis, settings, run_missing=True, echo=lambda _: None)
    assert pdf.stat().st_size > 50_000
    figures = {p.name for p in (pdf.parent / "figures").iterdir()}
    for name in ("flow", "forest_table2", "forest_supp2", "forest_supp3", "replication_grid"):
        assert {f"{name}.pdf", f"{name}.png"} <= figures, name
    egress = settings.project["egress"]
    report = check_egress(
        pdf.parent,
        min_cell=egress["min_cell"],
        small_cell=egress["small_cell"],
        ignore_id_pattern_columns=egress["ignore_id_pattern_columns"],
    )
    assert report.ok, report.problems
```

Run: `uv run pytest tests/test_lo2022_realdata.py -m realdata -q -k report`
Expected: FAIL with `ReportError: lo2022_walking has no [report] section in analysis.toml`.

- [ ] **Step 2: Add the `[report]` section**

Append to `analyses/lo2022_walking/analysis.toml`:

```toml
[report]
entry = "report.qmd"
runs = [
    "default", "walker_requires_amount", "roa_counts_replaced_knees", "published_counts",
    "missing_as_nonwalkers", "missing_as_walkers", "replacement_not_worsening",
    "corstr_independence",
]
assets = ["ASSUMPTIONS.md"]
```

- [ ] **Step 3: Write `analyses/lo2022_walking/report.qmd`**

````markdown
---
title: "Lo et al. 2022 replication: result-by-result comparison"
subtitle: "Walking for exercise and knee osteoarthritis progression in the OAI"
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
runs <- oaireport::load_results()
d <- runs$default
wra <- runs$walker_requires_amount
roa <- runs$roa_counts_replaced_knees

run_names <- c(
  default = "Primary analysis (every assumption at its default)",
  walker_requires_amount = "'Yes' walkers with no amount answers coded as non-walkers",
  roa_counts_replaced_knees = "Knees replaced at baseline count toward radiographic OA",
  published_counts = "Both count-reproducing choices together",
  missing_as_nonwalkers = "Survey non-respondents as non-walkers",
  missing_as_walkers = "Survey non-respondents as walkers",
  replacement_not_worsening = "Interval replacement not counted as structural worsening",
  corstr_independence = "Independence working correlation"
)
graded_against <- c(
  missing_as_nonwalkers = "Supplementary Table 2",
  missing_as_walkers = "Supplementary Table 3"
)
run_name <- function(label) if (label %in% names(run_names)) run_names[[label]] else label
outcome_names <- c(
  new_pain = "New frequent knee pain",
  kl_worse = "KL grade worsening",
  jsn_worse = "Medial JSN worsening",
  improved_pain = "Resolution of frequent knee pain"
)
model_names <- c(or_unadj = "Unadjusted", or_adj = "Adjusted")
group_names <- c(walkers = "Walkers", nonwalkers = "Non-walkers", all = "All")
fmt <- function(x, digits = 0) formatC(x, format = "f", digits = digits, big.mark = ",")
named <- function(key, map) ifelse(key %in% names(map), map[key], key)
verdict_counts <- function(cmp) {
  table(factor(cmp$verdict, levels = c("replicated", "drift", "missing")))
}
published_value <- function(run, metric) {
  as.numeric(run$comparison$published[run$comparison$metric == metric])
}

# Our odds ratios for one run, from its metrics (full precision).
or_estimates <- function(run, source) {
  grid <- expand.grid(outcome = names(outcome_names), model = names(model_names),
                      stringsAsFactors = FALSE)
  key <- sprintf("t2.%s.%s", grid$outcome, grid$model)
  m <- run$metrics
  data.frame(outcome = unname(outcome_names[grid$outcome]), model = unname(model_names[grid$model]),
             source = source, or = unname(m[key]), lo = unname(m[paste0(key, ".lo")]),
             hi = unname(m[paste0(key, ".hi")]))
}

# The published odds ratios this run was graded against, from its comparison.csv.
published_estimates <- function(run, source = "Published") {
  cmp <- run$comparison[run$comparison$kind == "or", ]
  parts <- do.call(rbind, strsplit(sub("^t2\\.", "", cmp$metric), ".", fixed = TRUE))
  ors <- oaireport::parse_or(cmp$published)
  data.frame(outcome = unname(outcome_names[parts[, 1]]), model = unname(model_names[parts[, 2]]),
             source = source, or = ors$or, lo = ors$lo, hi = ors$hi)
}

in_display_order <- function(est) {
  est[order(match(est$model, model_names), match(est$outcome, outcome_names)), ]
}

# One row per metric matching `pattern`: published, then ours and the verdict for each run.
compare_runs <- function(pattern, labels, run_titles = labels) {
  base <- runs[[labels[1]]]$comparison
  rows <- base[grepl(pattern, base$metric), c("metric", "published")]
  for (i in seq_along(labels)) {
    cmp <- runs[[labels[i]]]$comparison
    hit <- match(rows$metric, cmp$metric)
    rows[[run_titles[i]]] <- cmp$ours[hit]
    rows[[paste("verdict", run_titles[i])]] <- cmp$verdict[hit]
  }
  rownames(rows) <- NULL
  rows
}

commit <- d$run_info$git_commit
code_version <- paste0(
  "oai-analytics ", d$run_info$oai_version,
  if (is.null(commit)) "" else paste0(", commit ", substr(commit, 1, 7)),
  if (isTRUE(d$run_info$git_dirty)) " (with uncommitted changes)" else ""
)
```

# Summary

We re-ran every published analysis of Lo et al.^[Lo GH, et al. Association Between Walking for Exercise and Symptomatic and Structural Progression in Individuals With Knee Osteoarthritis. *Arthritis Rheumatol* 2022;74:1660–7. doi:10.1002/art.42241.] on the public OAI release with the oai-analytics suite. Every published number was then graded against our value. A count replicates within 3% (or 2), a mean within 0.5, and an odds ratio within 0.1 with the same statistical significance. Code: `r code_version`. The primary run finished `r d$run_info$finished_utc` UTC.

```{r headline}
t2 <- d$comparison[d$comparison$kind == "or", ]
pub <- oaireport::parse_or(t2$published)
ours <- oaireport::parse_or(t2$ours)
agree <- (pub$or < 1) == (ours$or < 1) & pub$sig == ours$sig
```

**Headline.** `r sum(agree)` of `r nrow(t2)` published Table 2 odds ratios reproduce in direction and statistical significance. `r sum(t2$verdict == "replicated")` of them also lie within 0.1 of the published estimate. Across all `r nrow(d$comparison)` graded results, the primary analysis replicates `r verdict_counts(d$comparison)[["replicated"]]`.

```{r summary-table}
summary_rows <- do.call(rbind, lapply(names(runs), function(label) {
  counts <- verdict_counts(runs[[label]]$comparison)
  data.frame(
    Run = label,
    Description = run_name(label),
    `Graded against` = if (label %in% names(graded_against)) graded_against[[label]] else "Main paper",
    Replicated = counts[["replicated"]], Drift = counts[["drift"]], Missing = counts[["missing"]],
    check.names = FALSE
  )
}))
oaireport::compare_table(summary_rows, widths = c(2.3, 3.6, 1.7, 1, 0.8, 0.8))
```

# Cohort flow

Our counts, with the published count in brackets where the paper reports one.

```{r flow}
#| fig-height: 6.4
flow_labels <- c(
  all = "OAI participants",
  age50 = "Age ≥ 50 years",
  baseline_xray = "Baseline x-ray read in Project 15",
  roa = "Radiographic knee OA",
  before_survey = "96-month visit on or after survey start",
  no_visit96 = "Attended the 96-month visit",
  no_survey = "Answered the walking survey",
  no_followup = "48- or 36-month follow-up x-ray"
)
counts <- d$comparison[d$comparison$kind == "count", ]
flow_plot <- oaireport::flow_diagram(
  d$flow, flow_labels, stats::setNames(as.numeric(counts$published), counts$metric)
)
oaireport::save_figure(flow_plot, "flow", "2col", height = 0.8 * nrow(d$flow))
flow_plot
```

Analysed knees: `r fmt(d$metrics[["flow.knees"]])` (published `r fmt(published_value(d, "flow.knees"))`). Characteristics of each excluded group (Supplementary Table 1) are in Appendix B.

# Table 1: baseline characteristics

```{r table1}
t1 <- compare_runs("^t1\\.", c("default", "walker_requires_amount"), c("primary", "amount"))
t1_names <- c(
  persons = "Participants", age_mean = "Age, mean (years)", male = "Men",
  bmi_mean = "BMI, mean (kg/m²)",
  walk_days_min = "Times walked, minimum", walk_days_p25 = "Times walked, 25th centile",
  walk_days_median = "Times walked, median", walk_days_p75 = "Times walked, 75th centile",
  walk_days_max = "Times walked, maximum",
  knees = "Knees", kl2 = "KL grade 2", kl3 = "KL grade 3", kl4 = "KL grade 4",
  jsm0 = "Medial JSN grade 0", jsm1 = "Medial JSN grade 1", jsm2 = "Medial JSN grade 2",
  jsm3 = "Medial JSN grade 3", pain0 = "Frequent knee pain at baseline",
  align_knees = "Knees with a long-limb film", varus = "Varus", neutral = "Neutral",
  valgus = "Valgus", pain48 = "Frequent knee pain at 48 months",
  replaced48 = "Knee replaced by 48 months"
)
parts <- do.call(rbind, strsplit(sub("^t1\\.", "", t1$metric), ".", fixed = TRUE))
t1_table <- data.frame(
  Characteristic = named(parts[, 1], t1_names), Group = named(parts[, 2], group_names),
  Published = t1$published, Primary = t1$primary, `verdict primary` = t1$`verdict primary`,
  `Walker requires amount` = t1$amount, `verdict amount` = t1$`verdict amount`,
  check.names = FALSE
)
oaireport::compare_table(t1_table, widths = c(3, 1.4, 1.1, 1.1, 1.5, 1.4, 1.5))
```

"Times walked" is years × months per year × times per month among walkers, using category midpoints (an open assumption; see Appendix D).

# Table 2: walking and knee outcomes

```{r forest-main}
#| fig-height: 4.2
sources <- c("Published", "Replication: primary", "Replication: walker requires amount")
main_est <- in_display_order(rbind(
  published_estimates(d), or_estimates(d, sources[2]), or_estimates(wra, sources[3])
))
main_plot <- oaireport::forest_plot(main_est, facet = "model", sources = sources)
oaireport::save_figure(main_plot, "forest_table2", "2col", height = 4.2)
main_plot
```

```{r table2}
t2_rows <- compare_runs("^t2\\.[a-z_]+\\.or_", c("default", "walker_requires_amount"),
                        c("primary", "amount"))
parts <- do.call(rbind, strsplit(sub("^t2\\.", "", t2_rows$metric), ".", fixed = TRUE))
oaireport::compare_table(data.frame(
  Outcome = named(parts[, 1], outcome_names), Model = named(parts[, 2], model_names),
  Published = t2_rows$published, Primary = t2_rows$primary,
  `verdict primary` = t2_rows$`verdict primary`, `Walker requires amount` = t2_rows$amount,
  `verdict amount` = t2_rows$`verdict amount`, check.names = FALSE
), widths = c(2.6, 1.3, 1.6, 1.6, 1.4, 1.6, 1.4))
```

Odds ratios (95% CI) for walkers versus non-walkers, from GEE logistic models with knees clustered within participants; \* marks significance.

# What explains the gaps

```{r gaps}
walkers <- function(run) run$metrics[["t1.persons.walkers"]]
roa_persons <- function(run) run$metrics[["flow.roa.persons"]]
replicated <- function(label) verdict_counts(runs[[label]]$comparison)[["replicated"]]
gap_runs <- c("default", "walker_requires_amount", "roa_counts_replaced_knees", "published_counts")
gap_table <- rbind(
  data.frame(Source = "Published", Walkers = fmt(published_value(d, "t1.persons.walkers")),
             `Radiographic OA step` = fmt(published_value(d, "flow.roa.persons")),
             Replicated = "", check.names = FALSE),
  do.call(rbind, lapply(gap_runs, function(label) data.frame(
    Source = run_name(label), Walkers = fmt(walkers(runs[[label]])),
    `Radiographic OA step` = fmt(roa_persons(runs[[label]])),
    Replicated = sprintf("%d of %d", replicated(label), nrow(runs[[label]]$comparison)),
    check.names = FALSE
  )))
)
oaireport::compare_table(gap_table, widths = c(4, 1.2, 1.8, 1.4))
```

Two coding choices that the paper does not state explain most of the count differences.

**1. Walkers who answered "yes" but gave no amount.** `r fmt(walkers(d) - walkers(wra))` participants answered yes to walking for exercise (V10WLKAR4) but left years, months per year and times per month blank. The primary analysis counts them as walkers: `r fmt(walkers(d))` walkers against `r fmt(published_value(d, "t1.persons.walkers"))` published. Coding them as non-walkers gives `r fmt(walkers(wra))` walkers, and the number of replicated results changes from `r replicated("default")` to `r replicated("walker_requires_amount")`. *Question for the authors:* were these respondents coded as non-walkers?

**2. Knees replaced before baseline, at the radiographic-OA step.** Counting participants whose only OA knee had been replaced at baseline gives `r fmt(roa_persons(roa))` participants at that step (published `r fmt(published_value(d, "flow.roa.persons"))`, primary `r fmt(roa_persons(d))`). The number of replicated results changes from `r replicated("default")` to `r replicated("roa_counts_replaced_knees")`. The Methods describe a native knee. *Question for the authors:* did a knee replaced at baseline count toward eligibility?

# Sensitivity analyses

Each panel compares a supplementary table with the run that reproduces its imputation of survey non-respondents.

```{r sensitivity-helper}
sensitivity_plot <- function(label) {
  est <- in_display_order(rbind(
    published_estimates(runs[[label]]), or_estimates(runs[[label]], "Replication")
  ))
  oaireport::forest_plot(est, facet = "model", sources = c("Published", "Replication"))
}
```

## Supplementary Table 2: non-respondents as non-walkers

```{r forest-supp2}
#| fig-height: 4.2
supp2 <- sensitivity_plot("missing_as_nonwalkers")
oaireport::save_figure(supp2, "forest_supp2", "2col", height = 4.2)
supp2
```

## Supplementary Table 3: non-respondents as walkers

```{r forest-supp3}
#| fig-height: 4.2
supp3 <- sensitivity_plot("missing_as_walkers")
oaireport::save_figure(supp3, "forest_supp3", "2col", height = 4.2)
supp3
```

```{=typst}
#pagebreak()
```

# Appendix A. Table 3: outcomes by static alignment (primary analysis)

```{r appendix-a}
t3 <- compare_runs("^t3\\.", "default", "primary")
parts <- do.call(rbind, strsplit(sub("^t3\\.", "", t3$metric), ".", fixed = TRUE))
oaireport::compare_table(data.frame(
  Outcome = named(parts[, 1], outcome_names), Alignment = tools::toTitleCase(parts[, 2]),
  Group = named(parts[, 3], group_names), Measure = ifelse(parts[, 4] == "n", "Knees", "Events"),
  Published = t3$published, Primary = t3$primary, verdict = t3$`verdict primary`,
  check.names = FALSE
), widths = c(2.6, 1.2, 1.3, 1, 1, 1, 1.4))
```

# Appendix B. Supplementary Table 1: excluded groups (primary analysis)

```{r appendix-b}
excluded_names <- c(
  before_survey = "96-month visit before survey start", no_visit96 = "No 96-month visit",
  no_survey = "No walking survey answers", no_followup = "No 48- or 36-month follow-up"
)
measure_names <- c(
  excluded_persons = "Participants", excluded_knees = "Knees", male = "Men",
  age_mean = "Age, mean (years)", bmi_mean = "BMI, mean (kg/m²)"
)
s1 <- compare_runs("^(s1\\.|flow\\.[a-z0-9_]+\\.excluded_)", "default", "primary")
parts <- do.call(rbind, strsplit(sub("^(s1|flow)\\.", "", s1$metric), ".", fixed = TRUE))
s1 <- s1[order(match(parts[, 1], names(excluded_names)), match(parts[, 2], names(measure_names))), ]
parts <- do.call(rbind, strsplit(sub("^(s1|flow)\\.", "", s1$metric), ".", fixed = TRUE))
oaireport::compare_table(data.frame(
  `Excluded group` = named(parts[, 1], excluded_names), Measure = named(parts[, 2], measure_names),
  Published = s1$published, Primary = s1$primary, verdict = s1$`verdict primary`,
  check.names = FALSE
), widths = c(3.2, 2, 1.1, 1.1, 1.4))
```

# Appendix C. Replication grid

Percentage of published results replicated, by results section and run (n = results graded). The two missing-data runs are graded only against their own supplementary tables.

```{r appendix-c-grid}
#| fig-height: 4
section_names <- c(flow = "Cohort flow", s1 = "Supp. Table 1", t1 = "Table 1", t2 = "Table 2", t3 = "Table 3")
grid <- do.call(rbind, lapply(names(runs), function(label) {
  cmp <- runs[[label]]$comparison
  section <- sub("\\..*$", "", cmp$metric)
  share <- tapply(cmp$verdict == "replicated", section, mean)
  data.frame(run = label, section = names(share), pct = 100 * as.numeric(share),
             n = as.integer(table(section)[names(share)]))
}))
grid$section <- factor(named(grid$section, section_names), levels = section_names)
grid$run <- factor(grid$run, levels = rev(names(runs)))
grid_plot <- ggplot2::ggplot(grid, ggplot2::aes(section, run, fill = pct)) +
  ggplot2::geom_tile(colour = "white", linewidth = 0.8) +
  ggplot2::geom_text(ggplot2::aes(label = sprintf("%.0f%%\n(n = %d)", pct, n), colour = pct > 60),
                     size = 2.4, family = oaireport::oai_font(), lineheight = 0.9) +
  ggplot2::scale_fill_gradient(low = "#cde2fb", high = "#1c5cab", limits = c(0, 100),
                               name = "% replicated") +
  ggplot2::scale_colour_manual(values = c(`FALSE` = "grey10", `TRUE` = "white"), guide = "none") +
  ggplot2::scale_x_discrete(position = "top") +
  ggplot2::labs(x = NULL, y = NULL) +
  oaireport::theme_oai() +
  ggplot2::theme(axis.line = ggplot2::element_blank(), axis.ticks = ggplot2::element_blank(),
                 legend.title = ggplot2::element_text(size = 7))
oaireport::save_figure(grid_plot, "replication_grid", "2col", height = 4)
grid_plot
```

## Every graded result, by run

The published column shows the main paper's value. Runs R5 and R6 are graded against Supplementary Tables 2 and 3 (see Sensitivity analyses).

```{r appendix-c-key}
oaireport::compare_table(data.frame(
  Key = sprintf("R%d", seq_along(runs)), Run = names(runs),
  Description = vapply(names(runs), run_name, character(1)), check.names = FALSE
), widths = c(0.6, 2.6, 4.6))
```

```{r appendix-c-table}
all_metrics <- unique(unlist(lapply(runs, function(r) r$comparison$metric)))
wide <- data.frame(Metric = all_metrics,
                   Published = d$comparison$published[match(all_metrics, d$comparison$metric)])
for (i in seq_along(runs)) {
  cmp <- runs[[i]]$comparison
  wide[[sprintf("verdict R%d", i)]] <- cmp$verdict[match(all_metrics, cmp$metric)]
}
oaireport::compare_table(wide, widths = c(3.6, 1.7, rep(0.6, length(runs))), compact = TRUE)
```

# Appendix D. Assumptions ledger

Every analytic choice, its status (confirmed from the paper, assumed, or open) and its source. Generated from `assumptions.toml`.

```{r appendix-d-ledger}
#| results: asis
ledger <- readLines("ASSUMPTIONS.md", warn = FALSE)
cat(ledger[!grepl("^# |^<!--", ledger)], sep = "\n")
```

## Settings that differ from the primary run

```{r appendix-d-diffs}
diffs <- do.call(rbind, lapply(names(runs), function(label) {
  items <- runs[[label]]$assumptions$assumptions
  changed <- Filter(function(x) !identical(x$origin, "default"), items)
  if (!length(changed)) return(NULL)
  data.frame(Run = label, Assumption = names(changed),
             Value = vapply(changed, function(x) paste(format(unlist(x$value)), collapse = ", "), ""),
             check.names = FALSE)
}))
oaireport::compare_table(diffs, widths = c(2.4, 3.4, 2))
```

# Appendix E. Methods and provenance

Grading (oai.replication):
- A count replicates when it is within the larger of 3% and 2.
- A mean replicates when it is within 0.5.
- An odds ratio replicates when it is within 0.1 and has the same statistical significance. The published significance flag is used, because rounded bounds such as 0.6–1.0 can hide an upper bound below 1.
- Otherwise a result is "drift", or "missing" when we could not compute it.

```{r appendix-e-runs}
oaireport::compare_table(do.call(rbind, lapply(names(runs), function(label) {
  info <- runs[[label]]$run_info
  data.frame(Run = label,
             Commit = if (is.null(info$git_commit)) "–" else substr(info$git_commit, 1, 7),
             `Uncommitted changes` = if (isTRUE(info$git_dirty)) "yes" else "no",
             `Finished (UTC)` = info$finished_utc, oai = info$oai_version, check.names = FALSE)
})), widths = c(2.6, 1, 1.5, 2.4, 0.8))
```

```{r appendix-e-software}
packages <- c("oaireport", "oaimodels", "geepack", "ggplot2", "tinytable", "knitr")
oaireport::compare_table(data.frame(
  Software = c("R", packages),
  Version = c(paste(R.version$major, R.version$minor, sep = "."),
              vapply(packages, function(p) as.character(utils::packageVersion(p)), character(1)))
), widths = c(2, 2))
```
````

- [ ] **Step 4: Render it and run the real-data test**

Run: `uv run oai report lo2022_walking --run`
Expected:
- `==> lo2022_walking:cohort [...]` lines for each run that lacks a finished `run_info.json`. All eight lack one on first use, because their results predate `run_info.json`, so this takes several minutes.
- Then `==> lo2022_walking: rendering report.qmd with /Applications/RStudio.app/...`, then `Report: …/lo2022_walking/report/report.pdf`.

If rendering fails, read the stderr tail in the error. The directory `report/` keeps `report.typ` and the copied `.qmd`. Fix the `.qmd` and rerun.

Then: `uv run pytest tests/test_lo2022_realdata.py -m realdata -q -k report`
Expected: PASS (a second render, with no reruns).

- [ ] **Step 5: Look at the PDF**

Render pages to PNG with PDFKit, a stock macOS framework. Do not use `pdftotext` or a third-party PDF server; they are unavailable or restricted here.

```bash
cat > "$TMPDIR/pdfpage.swift" <<'EOF'
import PDFKit
import AppKit
let doc = PDFDocument(url: URL(fileURLWithPath: CommandLine.arguments[1]))!
if CommandLine.arguments.count == 2 { print("pages", doc.pageCount); exit(0) }
let page = doc.page(at: Int(CommandLine.arguments[2])! - 1)!
let image = page.thumbnail(of: NSSize(width: 900, height: 1160), for: .mediaBox)
let rep = NSBitmapImageRep(data: image.tiffRepresentation!)!
try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: CommandLine.arguments[3]))
EOF
PDF="$(uv run python -c 'from oai.config import get_settings; print(get_settings().results_dir / "lo2022_walking/report/report.pdf")')"
swift "$TMPDIR/pdfpage.swift" "$PDF"
for p in 1 2 3 4 5 6; do swift "$TMPDIR/pdfpage.swift" "$PDF" $p "$TMPDIR/report-p$p.png"; done
```

Read each PNG with the Read tool, plus at least one appendix page near the end. Check:
- **Text:** body text is Arial, headings are in order, and no R error text or `NA` appears where a number belongs.
- **Summary:** the run table shows 8 rows with tinted verdict counts.
- **Flow:** the figure is legible, and bracketed published counts appear (for example `2,336 [2,356]`).
- **Tables:** Table 1 and the long appendix tables continue across pages with a repeated header row; none overprints at the page foot.
- **Forest plots:** three sources in fixed colour order, facets Unadjusted then Adjusted, and a dashed line at 1.
- **Heatmap:** white text on dark tiles and dark text on light tiles. Each label reads `NN%` and `(n = N)`.
- **Appendix D:** the ledger tables appear under "Assumptions ledger" without the ledger's own H1 title.

Fix anything wrong in `report.qmd`, or in `oaireport` with a test first, and rerender with `uv run oai report lo2022_walking`.

- [ ] **Step 6: Run egress on the report directory**

Run: `uv run oai check-egress "$(dirname "$PDF")"`
Expected:
- `REVIEW` lines for `report.pdf` and each `figures/*.pdf|png`;
- `0 problem(s)`;
- exit code 0.

- [ ] **Step 7: Document and commit**

Append to `analyses/lo2022_walking/README.md`:

```markdown
## Comparison report

`oai report lo2022_walking --run` runs the eight labels listed under `[report]` in
[analysis.toml](analysis.toml) (as needed) and renders [report.qmd](report.qmd) to
`$OAI_RESULTS_DIR/lo2022_walking/report/report.pdf`. The report's main body compares each
published result with ours and explains the gaps; its appendix holds every graded number,
the assumptions ledger and run provenance. Figures are in `report/figures/` as PDF and
300 dpi PNG at journal column widths.
```

```bash
uv run pytest -q
git add analyses/lo2022_walking/report.qmd analyses/lo2022_walking/analysis.toml analyses/lo2022_walking/README.md tests/test_lo2022_realdata.py
git commit -m "feat(lo2022_walking): result-by-result comparison report

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Documentation, final verification, push

**Files:**
- Create: `docs/reporting.md`
- Modify: `README.md` (command list), `docs/superpowers/specs/2026-09-30-reporting-module-and-lo2022-comparison-design.md` (status line)

**Interfaces:**
- Consumes: everything above.
- Produces: user-facing documentation.

- [ ] **Step 1: Write `docs/reporting.md`**

````markdown
# Reports

`oai report NAME [--run]` renders an analysis's Quarto report to PDF.

```toml
# analyses/<name>/analysis.toml
[report]
entry = "report.qmd"            # a .qmd directly in the analysis folder
runs = ["default", "variant"]   # run labels it reads: "default" or variants in assumptions.toml
assets = ["ASSUMPTIONS.md"]     # files copied next to the entry
```

## What happens

1. Each listed run needs a finished `run_info.json`. With `--run`, unfinished or missing runs are run first; without it, they are an error.
2. Quarto is found from `OAI_QUARTO`, then `[tools] quarto` in `config/oai.toml`, then `PATH`, then RStudio's bundled copy.
3. The entry and assets are copied to `$OAI_RESULTS_DIR/<name>/report/` and rendered there with `quarto render <entry> --to typst`. Nothing is written into the repository.
4. R chunks start through `r/step-profile.R` with `RENV_PROFILE=report`, so `oaimodels::` and `oaireport::` are available. The environment carries:
   - `OAI_RESULTS_ROOT`, the analysis's results directory;
   - `OAI_REPORT_DIR`;
   - `OAI_REPORT_RUNS`, the comma-separated run labels.
5. After a successful render only `<entry>.pdf` and `figures/` remain. Run `oai check-egress` on the folder before sharing it; PDFs and PNGs are listed for manual review. A failed render keeps its intermediates for debugging.

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

`oaireport` (R, `r/oaireport/`) provides:

| Function | Purpose |
|---|---|
| `load_results()` | Every listed run: its CSVs by name, `metrics`, `assumptions`, `run_info` |
| `theme_oai()`, `oai_palette`, `oai_font()` | ACR journal style: Arial 7–9 pt, Okabe–Ito colours in fixed order |
| `save_figure(plot, name, "1col"/"2col")` | `figures/<name>.pdf` + 300 dpi `.png` at 3.5 in / 7 in |
| `forest_plot(estimates, facet = , sources = )` | Odds ratios by outcome, up to four sources |
| `flow_diagram(flow, labels, published)` | Cohort flow from `flow.csv`, "ours [published]" |
| `compare_table(df, widths)` | tinytable with ✓ / △ / – verdicts; breaks across pages |
| `parse_or(text)` | `"0.6 (0.4-0.8) *"` → or, lo, hi, sig |

Give long tables a Markdown heading, not a caption: captions do not survive page breaks in Typst.

## The `report` renv profile

The reporting packages (ggplot2, tinytable, knitr, rmarkdown, ragg, …) live in `r/renv/profiles/report/renv.lock`. That keeps the default `r/renv.lock`, which the enclave bundle restores, free of them. To restore or update the profile:

```bash
cd r && RENV_PROFILE=report Rscript -e 'renv::restore(prompt = FALSE)'
cd r && RENV_PROFILE=report Rscript -e 'testthat::test_local("oaireport")'
```
````

- [ ] **Step 2: Add the command to `README.md`**

Find the block that lists `oai` commands (`grep -n "oai run\|check-egress" README.md`). Add these two lines next to `oai run`:

```
oai report lo2022_walking --run   # render the analysis's report (PDF) under OAI_RESULTS_DIR
```

and, in the documentation links, `- [docs/reporting.md](docs/reporting.md): reports, figures and the oaireport package`. Match the README's existing formatting for both.

- [ ] **Step 3: Mark the spec implemented**

In the spec, change `**Status:** Draft for review` to `**Status:** Implemented (see §12 Amendments)`.

- [ ] **Step 4: Full verification**

```bash
uv run ruff check && uv run ruff format --check
uv run python scripts/check_no_data.py
uv run pytest -q
uv run pytest -m realdata -q
cd r && Rscript -e 'testthat::test_local("oaimodels", stop_on_failure = TRUE)' && RENV_PROFILE=report Rscript -e 'testthat::test_local("oaireport", stop_on_failure = TRUE)'; cd ..
git diff --exit-code main -- r/renv.lock && echo "default lockfile unchanged"
git status --short
```

Expected:
- every command passes;
- `default lockfile unchanged`;
- a clean tree after the commit below;
- `git ls-files | grep -E '\.(pdf|png|csv|parquet)$'` shows no new files.

- [ ] **Step 5: Commit, then hand off**

```bash
git add docs/reporting.md README.md docs/superpowers/specs/2026-09-30-reporting-module-and-lo2022-comparison-design.md
git commit -m "docs: reporting guide (oai report, oaireport, report renv profile)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Use superpowers:finishing-a-development-branch to decide merge, push and PR. If the branch is merged to `main` and pushed, check the new `r-report` CI job once: a failing apt or renv step is a Task 3 fix.
