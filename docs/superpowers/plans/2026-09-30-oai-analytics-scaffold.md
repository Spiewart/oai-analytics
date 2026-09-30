# OAI Analytics Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold the public `Spiewart/oai-analytics` repo: packaging, data-leak guards, a working and tested Python data core (settings, catalog, loader, visit map, manifests, runner, export bundle, egress check), an R model package, analysis stubs, CI, and publish it to GitHub.

**Architecture:** A uv-managed Python package `oai` loads the pipe-delimited OAI release from an external `OAI_DATA_DIR` into typed polars frames (Parquet-cached in an external `OAI_WORK_DIR`). Each analysis in `analyses/<name>/` declares ordered Python/R steps tagged `stage = "local" | "enclave"` in `analysis.toml`; `oai run` executes them and `oai export` packages the enclave stage plus a column-restricted phenotype frame into a checksummed tarball whose `run.sh` ends with an egress check. R models live in the `oaimodels` package inside an renv project in `r/`.

**Tech Stack:** Python ≥ 3.11, uv, polars, typer, python-dotenv, pytest, ruff, pre-commit; R ≥ 4.2, renv, nanoparquet, testthat; GitHub Actions; gh CLI.

**Spec:** `docs/superpowers/specs/2026-09-30-oai-analytics-scaffold-design.md`

## Global Constraints

- Python `requires-python = ">=3.11"`; managed with uv; distribution `oai-analytics`, import package `oai`, console script `oai`.
- DataFrames are polars (`polars>=1.30`); no pandas dependency.
- R ≥ 4.2; renv project in `r/`; R package `oaimodels`; Python→R interchange is Parquet read with `nanoparquet` (never `arrow`).
- Settings resolution: process env → `.env` → `config/oai.toml` `[paths]` → error. An env var that is present but empty means "unset" and does not fall through.
- `OAI_WORK_DIR` and `OAI_RESULTS_DIR` must resolve outside the repository.
- No data in git: never commit `.parquet/.feather/.sas7bdat/.rds/.rdata/.xpt/.sav/.dta`; no file whose first line starts with `ID|` (except `tests/fixtures/`); no token matching `\b9\d{6}\b` in any file, **including this plan, tests and docs**. Tests that need such a value build it at runtime (`"9" + "000123"`).
- Synthetic fixtures use participant IDs `1000001`, `1000002`, `1000003`.
- OAI column names are preserved exactly as released (`V00XRKL`, `ID`, `SIDE`).
- Every user-facing error subclasses `oai.errors.OAIError`; the CLI prints it without a traceback and exits 1.
- Work happens on `main` of the new local repo (no remote exists until Task 15).
- Every commit message ends with the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Learning mode: two functions are **user-authored decisions** (Task 6 `resolve_missing`, Task 11 `small_cell_violations`). Implement the reference default shown, then pause and invite the user to replace it; if they change behavior, update the matching test.

## Review Focus

1. **Barcode-like columns with leading zeros** (`V00BARCDBU = 016600839603`) must stay strings, not become integers that drop the zero. → Task 6 `test_leading_zero_barcodes_stay_strings`.
2. **Free-text cells containing `": "`** (`"Note: see form"`) and **decimals written with a leading dot** (`".5"`) must not be treated as coded or missing values. → Task 6 `test_free_text_colon_and_leading_dot_decimals_are_not_misparsed`.
3. **CRLF line endings and non-UTF-8 (latin-1) bytes** in OAI text exports must load without crashing. → Task 6 `test_crlf_and_latin1_files_load`.
4. **Genomic summary statistics** (base-pair positions in the 9,000,000–9,999,999 range) must not be flagged as participant IDs when in configured position columns, while **unknown file types fail closed**. → Task 11 `test_position_columns_are_exempt_from_id_pattern`, `test_unknown_file_types_fail_closed`.
5. **`.env` paths using `~`, `$VARS` or relative paths** must resolve predictably (relative → repo root) and still be rejected when they land inside the repo. → Task 4 `test_home_and_env_vars_are_expanded`, `test_relative_work_dir_resolves_against_repo_and_is_rejected`.

## File Map

| Path | Responsibility | Task |
|---|---|---|
| `pyproject.toml`, `uv.lock`, `.gitignore`, `LICENSE`, `.env.example`, `README.md` | Packaging, ignore rules, license, config template, docs | 1, 14 |
| `src/oai/__init__.py` | Package version | 1 |
| `src/oai/cli.py` | typer app; one command per task | 1, 5, 8, 9, 11, 12 |
| `scripts/check_no_data.py`, `scripts/leak_allowlist.txt`, `.pre-commit-config.yaml` | Leak guard + hooks | 2 |
| `scripts/docx_to_md.py`, `docs/reference/*` | Reference docs + Markdown copies | 3 |
| `src/oai/errors.py` | `OAIError` base | 4 |
| `src/oai/config.py`, `config/oai.toml` | Settings resolution; project config | 4, 7, 11 |
| `tests/conftest.py` | Settings isolation, shared fixtures | 4, 5 |
| `src/oai/catalog.py`, `tests/fixtures/oai/*` | Table index; synthetic release | 5 |
| `src/oai/loader.py` | Parsing, codebook, Parquet cache | 6 |
| `src/oai/visits.py` | Visit map, `to_long`, `time_years` | 7 |
| `src/oai/manifest.py` | `analysis.toml` model + validation | 8 |
| `src/oai/runner.py` | Step execution | 9, 10 |
| `r/` (`renv.lock`, `.Rprofile`, `renv/`, `step-profile.R`, `oaimodels/`) | R project + package | 10 |
| `src/oai/export/egress.py` | Egress check | 11 |
| `src/oai/export/bundle.py`, `src/oai/export/templates/*` | Bundle builder + enclave templates | 12 |
| `src/oai/derive/*`, `analyses/*` | Stubs | 13 |
| `.github/workflows/ci.yml` | CI | 14 |

---

### Task 1: Python project skeleton

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `LICENSE`, `.env.example`, `README.md`, `src/oai/__init__.py`, `src/oai/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces: `oai.__version__: str`; `oai.cli.app: typer.Typer` with `--version`.

- [ ] **Step 1: Write packaging and repo files**

`pyproject.toml`:
```toml
[project]
name = "oai-analytics"
version = "0.1.0"
description = "Analytic suite for Osteoarthritis Initiative (OAI) data"
readme = "README.md"
license = "MIT"
requires-python = ">=3.11"
dependencies = [
    "polars>=1.30",
    "python-dotenv>=1.0",
    "typer>=0.12",
]

[project.scripts]
oai = "oai.cli:app"

[dependency-groups]
dev = [
    "pre-commit>=3.7",
    "pytest>=8",
    "ruff>=0.6",
]

[build-system]
requires = ["hatchling>=1.25"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/oai"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-m 'not realdata and not slow'"
markers = [
    "realdata: needs OAI_DATA_DIR pointing at a real OAI release (run with -m realdata)",
    "slow: builds real wheels / R packages (run with -m slow)",
]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
ignore = ["E501"]  # the formatter owns line length
```

`.gitignore`:
```gitignore
# Local configuration (may contain paths to controlled data)
.env

# Python
__pycache__/
*.py[cod]
.venv/
dist/
build/
*.egg-info/
.pytest_cache/
.ruff_cache/

# R
r/renv/library/
r/renv/staging/
r/renv/local/
.Rhistory
.Rproj.user/
*.Rcheck/
oaimodels_*.tar.gz

# Data: never commit (enforced by scripts/check_no_data.py)
*.parquet
*.feather
*.sas7bdat
*.rds
*.RData
*.rdata
*.txt
!docs/**/*.txt
!tests/fixtures/**/*.txt
!scripts/leak_allowlist.txt
work/
results/
bundles/
*.tar.gz

# OS
.DS_Store
```

`LICENSE`:
```text
MIT License

Copyright (c) 2026 oai-analytics contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

`.env.example`:
```dotenv
# Copy to .env and edit. .env is git-ignored. Environment variables override it.
# A variable set to an empty value means "unset".

# Raw OAI phenotype release (read-only). Required to load tables.
OAI_DATA_DIR="/path/to/OAI Complete Data_ASCII"

# Derived individual-level data, Parquet cache, bundles, export log.
# MUST be outside this repository.
OAI_WORK_DIR="/path/to/oai-work"

# Aggregate outputs. Defaults to $OAI_WORK_DIR/results.
# OAI_RESULTS_DIR=

# Enclave only: genotype data and every genotype-derived file.
# This is the directory destroyed at project close-out.
# OAI_GENO_DIR=

# Advanced: alternative project config / analyses directory (set by bundle run.sh).
# OAI_CONFIG=
# OAI_ANALYSES_DIR=
```

`README.md` (placeholder until Task 14):
```markdown
# oai-analytics

Analytic suite for Osteoarthritis Initiative (OAI) data. Setup and usage docs arrive with the first full scaffold.
```

`src/oai/__init__.py`:
```python
"""OAI analytics: data layer and export tooling for Osteoarthritis Initiative analyses."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("oai-analytics")
except PackageNotFoundError:  # running from a source tree without an install
    __version__ = "0.0.0"
```

- [ ] **Step 2: Write the failing test**

`tests/test_cli.py`:
```python
from typer.testing import CliRunner

from oai import __version__
from oai.cli import app

runner = CliRunner()


def test_version_flag_prints_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == __version__
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Users/spiewart/OAI && uv sync && uv run pytest tests/test_cli.py -v`
Expected: FAIL / collection error — `ModuleNotFoundError: No module named 'oai.cli'`

- [ ] **Step 4: Write minimal implementation**

`src/oai/cli.py`:
```python
"""`oai` command line."""

from __future__ import annotations

from typing import Annotated

import typer

from oai import __version__

app = typer.Typer(help="OAI analytics command line.", no_args_is_help=True)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option("--version", callback=_version_callback, is_eager=True, help="Show version."),
    ] = False,
) -> None:
    """OAI analytics."""
```

- [ ] **Step 5: Run tests and lint**

Run: `uv run pytest -v && uv run ruff check && uv run ruff format --check`
Expected: 1 passed; ruff clean (run `uv run ruff format .` first if needed).

- [ ] **Step 6: Commit** (`docs/*.docx` stay untracked until Task 3)

```bash
git add pyproject.toml uv.lock .gitignore LICENSE .env.example README.md src tests
git commit -m "feat: add Python package skeleton and oai CLI" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Data-leak guard and pre-commit hooks

**Files:**
- Create: `scripts/check_no_data.py`, `scripts/leak_allowlist.txt`, `.pre-commit-config.yaml`
- Test: `tests/test_check_no_data.py`

**Interfaces:**
- Produces: `check_file(path: Path, skip: Collection[str] = ()) -> list[str]`, `load_allowlist(path) -> list[tuple[str, str]]`, `skipped_rules(rel_path, allowlist) -> set[str]`, `main(argv: list[str] | None) -> int`. Rules: `"header"`, `"id"`, `"all"`.

- [ ] **Step 1: Write the failing tests**

`tests/test_check_no_data.py`:
```python
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_no_data.py"
_spec = importlib.util.spec_from_file_location("check_no_data", SCRIPT)
check_no_data = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_no_data)

# Built at runtime so this file never contains the participant-ID pattern itself.
FAKE_ID = "9" + "000123"


def test_clean_file_passes(tmp_path):
    p = tmp_path / "notes.md"
    p.write_text("KL grade 2, n = 1500\n")
    assert check_no_data.check_file(p) == []


def test_oai_header_is_flagged(tmp_path):
    p = tmp_path / "t.txt"
    p.write_text("ID|SIDE|V00XRKL\n")
    [problem] = check_no_data.check_file(p)
    assert "ID|" in problem


def test_participant_id_is_flagged_with_line_number(tmp_path):
    p = tmp_path / "t.csv"
    p.write_text(f"a,b\nx,{FAKE_ID}\n")
    [problem] = check_no_data.check_file(p)
    assert ":2:" in problem


def test_longer_numbers_are_not_flagged(tmp_path):
    p = tmp_path / "t.csv"
    p.write_text(f"pos\n1{FAKE_ID}\n{FAKE_ID}4\n")
    assert check_no_data.check_file(p) == []


def test_data_extensions_are_always_flagged(tmp_path):
    p = tmp_path / "frame.parquet"
    p.write_bytes(b"PAR1")
    assert check_no_data.check_file(p, skip={"header", "id"})


def test_binary_files_are_not_content_scanned(tmp_path):
    p = tmp_path / "doc.docx"
    p.write_bytes(b"PK\x03\x04\x00\x00" + FAKE_ID.encode())
    assert check_no_data.check_file(p) == []


def test_allowlist_rules(tmp_path):
    allow = tmp_path / "allow.txt"
    allow.write_text("# comment\nid uv.lock\nheader tests/fixtures/*\n")
    entries = check_no_data.load_allowlist(allow)
    assert check_no_data.skipped_rules("uv.lock", entries) == {"id"}
    assert check_no_data.skipped_rules("tests/fixtures/oai/Enrollees.txt", entries) == {"header"}
    assert check_no_data.skipped_rules("src/oai/cli.py", entries) == set()


def test_bad_allowlist_line_is_rejected(tmp_path):
    allow = tmp_path / "allow.txt"
    allow.write_text("ids uv.lock\n")
    with pytest.raises(SystemExit):
        check_no_data.load_allowlist(allow)


def test_main_exit_codes(tmp_path, capsys):
    good = tmp_path / "good.md"
    good.write_text("ok\n")
    bad = tmp_path / "bad.txt"
    bad.write_text("ID|X\n")
    assert check_no_data.main([str(good)]) == 0
    assert check_no_data.main([str(good), str(bad)]) == 1
    assert "potential data leak" in capsys.readouterr().err


def test_repository_is_clean():
    assert check_no_data.main([]) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_check_no_data.py -v`
Expected: collection error — `FileNotFoundError` for `scripts/check_no_data.py`.

- [ ] **Step 3: Write the guard**

`scripts/check_no_data.py`:
```python
#!/usr/bin/env python3
"""Fail if any given (or git-tracked) file looks like OAI participant data.

Pre-commit passes staged file names; CI runs it with no arguments to check every
tracked file. Exemptions live in scripts/leak_allowlist.txt as "<rule> <glob>".
"""

from __future__ import annotations

import fnmatch
import re
import subprocess
import sys
from collections.abc import Collection
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST_FILE = REPO_ROOT / "scripts" / "leak_allowlist.txt"
DATA_EXTENSIONS = {".parquet", ".feather", ".sas7bdat", ".rds", ".rdata", ".xpt", ".sav", ".dta"}
PARTICIPANT_ID = re.compile(rb"\b9\d{6}\b")
RULES = ("header", "id")
MAX_SCAN_BYTES = 20 * 1024 * 1024


def load_allowlist(path: Path = ALLOWLIST_FILE) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for line in path.read_text().splitlines() if path.exists() else []:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        rule, _, pattern = line.partition(" ")
        if rule not in (*RULES, "all") or not pattern.strip():
            raise SystemExit(f"{path}: bad allowlist line {line!r} (expected '<all|header|id> <glob>')")
        entries.append((rule, pattern.strip()))
    return entries


def skipped_rules(rel_path: str, allowlist: list[tuple[str, str]]) -> set[str]:
    skip: set[str] = set()
    for rule, pattern in allowlist:
        if fnmatch.fnmatch(rel_path, pattern):
            skip |= set(RULES) if rule == "all" else {rule}
    return skip


def check_file(path: Path, skip: Collection[str] = ()) -> list[str]:
    """Return problems for one file; an empty list means clean."""
    if path.suffix.lower() in DATA_EXTENSIONS:
        return [f"{path}: data file type {path.suffix!r} is never allowed in the repo"]
    try:
        with path.open("rb") as fh:
            head = fh.read(MAX_SCAN_BYTES)
    except (FileNotFoundError, IsADirectoryError):
        return []
    if b"\x00" in head[:8192]:
        return []  # binary (e.g. .docx); only the extension rule applies
    problems: list[str] = []
    if "header" not in skip and head.split(b"\n", 1)[0].startswith(b"ID|"):
        problems.append(f"{path}: first line starts with 'ID|' (OAI table header)")
    if "id" not in skip and (match := PARTICIPANT_ID.search(head)):
        line_no = head.count(b"\n", 0, match.start()) + 1
        problems.append(f"{path}:{line_no}: 7-digit number starting with 9 (OAI participant ID pattern)")
    return problems


def tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO_ROOT, check=True, capture_output=True
    ).stdout.decode()
    return [REPO_ROOT / p for p in out.split("\0") if p]


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    files = [Path(a) for a in args] if args else tracked_files()
    allowlist = load_allowlist()
    problems: list[str] = []
    for f in files:
        resolved = f.resolve()
        rel = resolved.relative_to(REPO_ROOT).as_posix() if resolved.is_relative_to(REPO_ROOT) else f.as_posix()
        problems.extend(check_file(f, skipped_rules(rel, allowlist)))
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        print(
            f"\n{len(problems)} potential data leak(s). If a hit is a false positive, "
            "add '<rule> <path>' to scripts/leak_allowlist.txt.",
            file=sys.stderr,
        )
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

`scripts/leak_allowlist.txt`:
```text
# Leak-guard exemptions: "<rule> <glob>" with repo-relative fnmatch globs.
# rule: header (skip the 'ID|' first-line check) | id (skip the participant-ID scan) | all
# uv.lock records wheel sizes in bytes, which can be 7-digit numbers starting with 9.
id uv.lock
# Synthetic fixtures mimic OAI headers; their IDs (1000001...) are still scanned.
header tests/fixtures/*
```

`.pre-commit-config.yaml`:
```yaml
# Local hooks so ruff's version comes from uv.lock (single source of truth).
repos:
  - repo: local
    hooks:
      - id: ruff
        name: ruff lint
        entry: uv run ruff check --fix
        language: system
        types: [python]
      - id: ruff-format
        name: ruff format
        entry: uv run ruff format
        language: system
        types: [python]
      - id: check-no-data
        name: block OAI data from commits
        entry: uv run python scripts/check_no_data.py
        language: system
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_check_no_data.py -v`
Expected: 10 passed.

- [ ] **Step 5: Install hooks and commit**

```bash
uv run pre-commit install
git add scripts .pre-commit-config.yaml tests/test_check_no_data.py
git commit -m "feat: add data-leak guard and pre-commit hooks" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
Expected: pre-commit runs ruff + check-no-data and passes.

---

### Task 3: Reference docs with Markdown copies

**Files:**
- Move: `docs/*.docx` → `docs/reference/`
- Create: `scripts/docx_to_md.py`, `docs/reference/README.md`, generated `docs/reference/*.md`

- [ ] **Step 1: Move the source documents**

```bash
mkdir -p docs/reference && mv docs/*.docx docs/reference/ && ls docs/reference
```
Expected: the four `oai-*.docx` files.

- [ ] **Step 2: Write the converter**

`scripts/docx_to_md.py`:
```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["pypandoc_binary>=1.13"]
# ///
"""Convert docs/reference/*.docx to GitHub-flavored Markdown next to the originals.

Run with `uv run scripts/docx_to_md.py` (pandoc ships inside pypandoc_binary).
"""

from pathlib import Path

import pypandoc

REFERENCE = Path(__file__).resolve().parents[1] / "docs" / "reference"


def main() -> None:
    for docx in sorted(REFERENCE.glob("*.docx")):
        md = docx.with_suffix(".md")
        pypandoc.convert_file(str(docx), "gfm", outputfile=str(md), extra_args=["--wrap=none"])
        print(f"wrote {md.name}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Convert and verify**

Run: `uv run scripts/docx_to_md.py && wc -w docs/reference/*.md && uv run python scripts/check_no_data.py docs/reference/*`
Expected: four `wrote …` lines; each `.md` has > 1,000 words; leak guard exits 0. If the guard flags a line, inspect it — a citation number is a false positive (add `id docs/reference/<file>.md` to the allowlist), anything else is a stop-and-ask.

- [ ] **Step 4: Write the index**

`docs/reference/README.md`:
```markdown
# Reference documents

Literature syntheses that define the analyses in this repo. The `.docx` files are the originals; the `.md` copies are generated with `uv run scripts/docx_to_md.py` for reading and diffing on GitHub. Regenerate after editing a `.docx`.

| Document | What it covers |
|---|---|
| [Dataset table structure](oai-dataset-table-structure.md) | Table families, visit-code mapping, keys (`ID`, `SIDE`) and record grain of the public OAI release |
| [Progression definitions review](oai-progression-definitions-review.md) | Radiographic, MRI, symptomatic, functional and hard-endpoint progression definitions used with OAI |
| [Progression definition crosswalk](oai-progression-definition-crosswalk.md) | Each progression definition mapped to its OAI table stem and variables |
| [Activity agreement analysis plan](oai-activity-agreement-analysis-plan.md) | PASE vs. accelerometer agreement (Aims 1–3) and the per-genotype progression arm (§10–12) |

Variable names in these documents are representative; verify them against the release's `*_Contents.pdf` files in `OAI_DATA_DIR`.
```

- [ ] **Step 5: Commit**

```bash
git add docs/reference scripts/docx_to_md.py
git commit -m "docs: add reference documents with Markdown copies" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Settings resolution

**Files:**
- Create: `src/oai/errors.py`, `src/oai/config.py`, `config/oai.toml`, `tests/conftest.py`, local `.env` (not committed)
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `OAIError`; `ConfigError(OAIError)`; `Settings` with `repo_root: Path | None`, `config_path: Path | None`, `project: Mapping[str, Any]`, `paths: Mapping[str, Path]` and properties `data_dir`, `work_dir`, `results_dir`, `geno_dir: Path | None`, `analyses_dir`; `load_settings(*, env: Mapping[str, str] | None = None, repo_root: Path | None = <auto>) -> Settings`; `get_settings() -> Settings` (cached); `find_repo_root(start: Path | None = None) -> Path | None`.
- Test fixtures: `isolated_settings` (autouse), `fake_repo`.

- [ ] **Step 1: Create the project config and shared fixtures**

`config/oai.toml`:
```toml
# Project configuration for oai-analytics. Non-secret, committed.
# Machine-specific paths belong in .env (see .env.example); [paths] below is a
# last-resort fallback and is normally left commented out.

# [paths]
# data_dir = "/path/to/OAI Complete Data_ASCII"
# work_dir = "/path/to/oai-work"
```

`tests/conftest.py`:
```python
"""Shared pytest fixtures.

Every test runs with OAI_* settings pointed at throwaway locations so a developer's
real .env never leaks into the suite. Tests marked `realdata` keep the developer's
OAI_DATA_DIR and are skipped when it is not configured.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from oai import config as oai_config

FIXTURES = Path(__file__).parent / "fixtures"
OAI_FIXTURE_DATA = FIXTURES / "oai"
REPO_ROOT = Path(__file__).resolve().parents[1]


def _clear_caches() -> None:
    oai_config.get_settings.cache_clear()


@pytest.fixture(autouse=True)
def isolated_settings(request, tmp_path, monkeypatch):
    if request.node.get_closest_marker("realdata"):
        try:
            data_dir = oai_config.load_settings().data_dir
        except oai_config.ConfigError:
            pytest.skip("OAI_DATA_DIR is not configured (env or .env)")
    else:
        data_dir = OAI_FIXTURE_DATA
    monkeypatch.setenv("OAI_DATA_DIR", str(data_dir))
    monkeypatch.setenv("OAI_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setenv("OAI_RESULTS_DIR", str(tmp_path / "results"))
    for key in ("OAI_GENO_DIR", "OAI_ANALYSES_DIR", "OAI_CONFIG", "OAI_FRAME_DIR"):
        monkeypatch.setenv(key, "")
    _clear_caches()
    yield
    _clear_caches()


@pytest.fixture
def fake_repo(tmp_path) -> Path:
    """A minimal checkout: pyproject.toml plus a copy of the real config/oai.toml."""
    root = tmp_path / "repo"
    (root / "config").mkdir(parents=True)
    (root / "pyproject.toml").write_text('[project]\nname = "fake"\n')
    (root / "config" / "oai.toml").write_text((REPO_ROOT / "config" / "oai.toml").read_text())
    return root
```

- [ ] **Step 2: Write the failing tests**

`tests/test_config.py`:
```python
from pathlib import Path

import pytest

from oai.config import ConfigError, find_repo_root, load_settings


def test_env_beats_dotenv_beats_toml(fake_repo, tmp_path):
    (fake_repo / ".env").write_text(
        f'OAI_DATA_DIR="{tmp_path / "from_dotenv"}"\nOAI_WORK_DIR="{tmp_path / "work_dotenv"}"\n'
    )
    cfg = fake_repo / "config" / "oai.toml"
    cfg.write_text(
        cfg.read_text()
        + f'\n[paths]\ndata_dir = "{tmp_path / "from_toml"}"\n'
        + f'work_dir = "{tmp_path / "work_toml"}"\ngeno_dir = "{tmp_path / "geno_toml"}"\n'
    )
    s = load_settings(env={"OAI_DATA_DIR": str(tmp_path / "from_env")}, repo_root=fake_repo)
    assert s.data_dir == (tmp_path / "from_env").resolve()
    assert s.work_dir == (tmp_path / "work_dotenv").resolve()
    assert s.geno_dir == (tmp_path / "geno_toml").resolve()


def test_missing_data_dir_raises_on_access(fake_repo):
    s = load_settings(env={}, repo_root=fake_repo)
    with pytest.raises(ConfigError, match="OAI_DATA_DIR is not set"):
        _ = s.data_dir


def test_empty_env_value_means_unset_and_blocks_dotenv(fake_repo, tmp_path):
    (fake_repo / ".env").write_text(f'OAI_GENO_DIR="{tmp_path / "geno"}"\n')
    s = load_settings(env={"OAI_GENO_DIR": ""}, repo_root=fake_repo)
    assert s.geno_dir is None


def test_work_dir_inside_repo_is_rejected(fake_repo):
    with pytest.raises(ConfigError, match="inside the repository"):
        load_settings(env={"OAI_WORK_DIR": str(fake_repo / "work")}, repo_root=fake_repo)


def test_relative_work_dir_resolves_against_repo_and_is_rejected(fake_repo):
    with pytest.raises(ConfigError, match="inside the repository"):
        load_settings(env={"OAI_WORK_DIR": "work"}, repo_root=fake_repo)


def test_results_dir_defaults_under_work_dir(fake_repo, tmp_path):
    s = load_settings(env={"OAI_WORK_DIR": str(tmp_path / "w")}, repo_root=fake_repo)
    assert s.results_dir == (tmp_path / "w" / "results").resolve()


def test_home_and_env_vars_are_expanded(fake_repo, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("OAI_TEST_BASE", str(tmp_path / "base"))
    s = load_settings(
        env={"OAI_DATA_DIR": "~/oai-data", "OAI_WORK_DIR": "$OAI_TEST_BASE/work"},
        repo_root=fake_repo,
    )
    assert s.data_dir == (tmp_path / "home" / "oai-data").resolve()
    assert s.work_dir == (tmp_path / "base" / "work").resolve()


def test_oai_config_override(fake_repo, tmp_path):
    other = tmp_path / "other.toml"
    other.write_text(f'[paths]\ndata_dir = "{tmp_path / "x"}"\n')
    s = load_settings(env={"OAI_CONFIG": str(other)}, repo_root=fake_repo)
    assert s.config_path == other.resolve()
    assert s.data_dir == (tmp_path / "x").resolve()


def test_missing_oai_config_file_raises(fake_repo, tmp_path):
    with pytest.raises(ConfigError, match="does not exist"):
        load_settings(env={"OAI_CONFIG": str(tmp_path / "nope.toml")}, repo_root=fake_repo)


def test_analyses_dir_defaults_to_repo(fake_repo):
    s = load_settings(env={}, repo_root=fake_repo)
    assert s.analyses_dir == fake_repo.resolve() / "analyses"


def test_analyses_dir_without_repo_requires_env():
    s = load_settings(env={}, repo_root=None)
    with pytest.raises(ConfigError, match="OAI_ANALYSES_DIR"):
        _ = s.analyses_dir


def test_find_repo_root_locates_this_checkout():
    root = find_repo_root()
    assert root is not None
    assert (root / "config" / "oai.toml").is_file()
    assert Path(__file__).resolve().is_relative_to(root)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py -v`
Expected: collection error — `ModuleNotFoundError: No module named 'oai.config'`

- [ ] **Step 4: Write the implementation**

`src/oai/errors.py`:
```python
"""Base class for errors the CLI shows as plain messages (no traceback)."""


class OAIError(Exception):
    """A user-facing error: bad configuration, unknown table, invalid manifest, ..."""
```

`src/oai/config.py`:
```python
"""Settings resolution: process env -> .env -> config/oai.toml [paths] -> error.

An environment variable that is present but empty means "unset" and does not fall
through to .env, which lets tests and scripts switch a setting off explicitly.
"""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

from oai.errors import OAIError

PATH_KEYS = ("OAI_DATA_DIR", "OAI_WORK_DIR", "OAI_RESULTS_DIR", "OAI_GENO_DIR", "OAI_ANALYSES_DIR")
MUST_BE_OUTSIDE_REPO = ("OAI_WORK_DIR", "OAI_RESULTS_DIR")
_AUTO: Any = object()


class ConfigError(OAIError):
    """A required setting is missing or unsafe."""


def find_repo_root(start: Path | None = None) -> Path | None:
    """Return the checkout root (has pyproject.toml and config/oai.toml), or None."""
    here = (start or Path(__file__)).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "config" / "oai.toml").is_file():
            return candidate
    return None


@dataclass(frozen=True)
class Settings:
    repo_root: Path | None
    config_path: Path | None
    project: Mapping[str, Any]
    paths: Mapping[str, Path] = field(default_factory=dict)

    def _require(self, key: str) -> Path:
        try:
            return self.paths[key]
        except KeyError:
            raise ConfigError(
                f"{key} is not set. Set it in the environment, in .env (see .env.example), "
                "or under [paths] in config/oai.toml."
            ) from None

    @property
    def data_dir(self) -> Path:
        return self._require("OAI_DATA_DIR")

    @property
    def work_dir(self) -> Path:
        return self._require("OAI_WORK_DIR")

    @property
    def results_dir(self) -> Path:
        return self.paths.get("OAI_RESULTS_DIR") or self.work_dir / "results"

    @property
    def geno_dir(self) -> Path | None:
        return self.paths.get("OAI_GENO_DIR")

    @property
    def analyses_dir(self) -> Path:
        if "OAI_ANALYSES_DIR" in self.paths:
            return self.paths["OAI_ANALYSES_DIR"]
        if self.repo_root is not None:
            return self.repo_root / "analyses"
        raise ConfigError("OAI_ANALYSES_DIR is not set and no repository checkout was found.")


def _lookup(key: str, sources: tuple[Mapping[str, str | None], ...], toml_paths: Mapping) -> str | None:
    for source in sources:
        if key in source:
            return source[key] or None
    return toml_paths.get(key.removeprefix("OAI_").lower()) or None


def _normalize(raw: str, *, base: Path | None) -> Path:
    path = Path(os.path.expandvars(raw)).expanduser()
    if not path.is_absolute():
        path = (base or Path.cwd()) / path
    return path.resolve()


def _config_path(sources: tuple[Mapping[str, str | None], ...], root: Path | None) -> Path | None:
    for source in sources:
        if "OAI_CONFIG" in source:
            raw = source["OAI_CONFIG"]
            if raw:
                path = Path(raw).expanduser()
                if not path.is_file():
                    raise ConfigError(f"OAI_CONFIG={raw} does not exist")
                return path.resolve()
            break
    if root is not None and (root / "config" / "oai.toml").is_file():
        return root / "config" / "oai.toml"
    return None


def load_settings(
    *, env: Mapping[str, str] | None = None, repo_root: Path | None = _AUTO
) -> Settings:
    env = dict(os.environ if env is None else env)
    root = find_repo_root() if repo_root is _AUTO else repo_root
    root = root.resolve() if root is not None else None
    dotenv: dict[str, str | None] = {}
    if root is not None and (root / ".env").is_file():
        dotenv = dict(dotenv_values(root / ".env"))
    sources = (env, dotenv)
    config_path = _config_path(sources, root)
    project = tomllib.loads(config_path.read_text()) if config_path else {}
    toml_paths = project.get("paths", {})
    paths: dict[str, Path] = {}
    for key in PATH_KEYS:
        raw = _lookup(key, sources, toml_paths)
        if raw:
            paths[key] = _normalize(raw, base=root)
    if root is not None:
        for key in MUST_BE_OUTSIDE_REPO:
            if key in paths and paths[key].is_relative_to(root):
                raise ConfigError(
                    f"{key}={paths[key]} is inside the repository ({root}). "
                    "Derived data must live outside the repo."
                )
    return Settings(repo_root=root, config_path=config_path, project=project, paths=paths)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings (cached; tests clear the cache)."""
    return load_settings()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest -v`
Expected: all pass (12 in `test_config.py` plus earlier tests).

- [ ] **Step 6: Create the developer's local `.env` (never committed)**

```bash
cat > .env <<'EOF'
OAI_DATA_DIR="/Users/spiewart/OAI Complete Data_ASCII"
OAI_WORK_DIR="/Users/spiewart/oai-work"
EOF
git check-ignore .env
```
Expected: `git check-ignore` prints `.env`.

- [ ] **Step 7: Commit**

```bash
git add src/oai/errors.py src/oai/config.py config/oai.toml tests/conftest.py tests/test_config.py
git commit -m "feat: add settings resolution with repo-safety checks" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Table catalog and `oai catalog`

**Files:**
- Create: `src/oai/catalog.py`, `tests/fixtures/oai/*.txt`
- Modify: `src/oai/cli.py`, `tests/conftest.py`
- Test: `tests/test_catalog.py`

**Interfaces:**
- Consumes: `get_settings()`, `Settings.data_dir`, `OAIError`.
- Produces: `CatalogError(OAIError)`; `TableFile(table: str, visit: str | None, kind: Literal["visit","cumulative","static"], path: Path)` with `.key -> str` (`"allclinical_00"`, `"enrollees"`); `parse_filename(path) -> TableFile | None`; `Catalog` with `scan(data_dir)`, `tables() -> list[str]`, `visits(table) -> list[str]`, `get(table, visit: str | int | None = None) -> TableFile`, `resolve_input(spec) -> list[TableFile]`, `__len__`; `catalog_for(data_dir: Path) -> Catalog` (lru-cached); `INPUT_SPEC: re.Pattern`; `cli.user_errors()` context manager.

- [ ] **Step 1: Create the synthetic release**

`tests/fixtures/oai/Enrollees.txt`:
```text
ID|VERSION|P02SEX|P02RACE|V00COHORT|V00SITE
1000001|2.1|2: Female|1: White or Caucasian|1: Progression|A
1000002|2.1|1: Male|2: Black or African American|2: Incidence|B
1000003|2.1|2: Female|1: White or Caucasian|2: Incidence|C
```

`tests/fixtures/oai/AllClinical00.txt`:
```text
ID|VERSION|P01BMI|V00AGE|V00WOMKPR|V00PASE|V00KPACT30
1000001|2.1|27.4|61|3|180|1: Yes
1000002|2.1|.: Missing Form/Incomplete Workbook|55|0|95|0: No
1000003|2.1|31.2|70|.A: Not Expected|210|1: Yes
```

`tests/fixtures/oai/AllClinical01.txt`:
```text
ID|VERSION|V01BMI|V01WOMKPR|V01PASE
1000001|2.1|27.9|4|170
1000002|2.1|.: Missing Form/Incomplete Workbook|1|100
1000003|2.1|30.8|2|.: Missing Form/Incomplete Workbook
```

`tests/fixtures/oai/kxr_sq_bu00.txt`:
```text
ID|SIDE|READPRJ|VERSION|V00BARCDBU|V00XRKL|V00XRJSM
1000001|1: Right|15|0.9|016600000001|2|1: 1
1000001|2: Left|15|0.9|016600000002|1|0: 0
1000002|1: Right|15|0.9|016600000003|3|2: 2
```

`tests/fixtures/oai/kXR_SQ_BU01.txt` (mixed case on purpose):
```text
ID|SIDE|READPRJ|VERSION|V01BARCDBU|V01XRKL|V01XRJSM
1000001|1: Right|15|0.9|016600000004|3|1: 1
1000002|1: Right|15|0.9|016600000005|3|2: 2
```

`tests/fixtures/oai/OUTCOMES99.txt`:
```text
ID|VERSION|V99ERKDAYS|V99ERKRPCF
1000001|3.1|2410|1: Yes
1000002|3.1|.: Missing Form/Incomplete Workbook|0: No
1000003|3.1|.: Missing Form/Incomplete Workbook|0: No
```

`tests/fixtures/oai/kMRI_SQ_WORMS_Link_Formats.txt`:
```text
FORMAT|VALUE
WORMS|1
```

- [ ] **Step 2: Write the failing tests**

`tests/test_catalog.py`:
```python
from pathlib import Path

import pytest
from typer.testing import CliRunner

from oai.catalog import Catalog, CatalogError, TableFile, parse_filename
from oai.cli import app

OAI_FIXTURE_DATA = Path(__file__).parent / "fixtures" / "oai"


@pytest.mark.parametrize(
    "name, table, visit, kind",
    [
        ("AllClinical00.txt", "allclinical", "00", "visit"),
        ("ALLCLINICAL13.txt", "allclinical", "13", "visit"),
        ("kXR_SQ_BU01.txt", "kxr_sq_bu", "01", "visit"),
        ("Enrollees.txt", "enrollees", None, "static"),
        ("OUTCOMES99.txt", "outcomes", "99", "cumulative"),
        ("COVIDQ97.txt", "covidq", "97", "cumulative"),
        ("Something2010.txt", "something2010", None, "static"),
    ],
)
def test_parse_filename(name, table, visit, kind):
    tf = parse_filename(Path(name))
    assert (tf.table, tf.visit, tf.kind) == (table, visit, kind)


def test_formats_files_are_excluded():
    assert parse_filename(Path("sAGEAncillaryStudy_Formats.txt")) is None


def test_scan_fixture_release():
    cat = Catalog.scan(OAI_FIXTURE_DATA)
    assert cat.tables() == ["allclinical", "enrollees", "kxr_sq_bu", "outcomes"]
    assert cat.visits("kxr_sq_bu") == ["00", "01"]
    assert cat.get("outcomes", "99").kind == "cumulative"
    assert cat.get("enrollees").key == "enrollees"
    assert cat.get("AllClinical", "V01").key == "allclinical_01"
    assert len(cat) == 6


def test_duplicate_keys_raise():
    a = TableFile("kxr_sq_bu", "00", "visit", Path("kxr_sq_bu00.txt"))
    b = TableFile("kxr_sq_bu", "00", "visit", Path("KXR_SQ_BU00.txt"))
    with pytest.raises(CatalogError, match="Two files"):
        Catalog([a, b])


def test_unknown_table_and_visit_messages():
    cat = Catalog.scan(OAI_FIXTURE_DATA)
    with pytest.raises(CatalogError, match="Unknown table 'nope'"):
        cat.get("nope")
    with pytest.raises(CatalogError, match="available: 00, 01"):
        cat.get("kxr_sq_bu", "06")


@pytest.mark.parametrize(
    "spec, keys",
    [
        ("enrollees", ["enrollees"]),
        ("allclinical:01", ["allclinical_01"]),
        ("kxr_sq_bu:*", ["kxr_sq_bu_00", "kxr_sq_bu_01"]),
    ],
)
def test_resolve_input(spec, keys):
    assert [tf.key for tf in Catalog.scan(OAI_FIXTURE_DATA).resolve_input(spec)] == keys


def test_resolve_input_rejects_bad_spec():
    with pytest.raises(CatalogError, match="Bad input spec"):
        Catalog.scan(OAI_FIXTURE_DATA).resolve_input("AllClinical:0")


def test_missing_data_dir(tmp_path):
    with pytest.raises(CatalogError, match="not found"):
        Catalog.scan(tmp_path / "absent")


def test_cli_catalog_lists_tables():
    result = CliRunner().invoke(app, ["catalog"])
    assert result.exit_code == 0, result.output
    assert "kxr_sq_bu" in result.stdout and "00 01" in result.stdout
    assert "6 files, 4 tables" in result.stdout


def test_cli_reports_config_errors_without_traceback(monkeypatch):
    monkeypatch.setenv("OAI_DATA_DIR", "")
    result = CliRunner().invoke(app, ["catalog"])
    assert result.exit_code == 1
    assert "OAI_DATA_DIR is not set" in result.output
    assert "Traceback" not in result.output


@pytest.mark.realdata
def test_real_release_catalogs_cleanly():
    from oai.config import get_settings

    data_dir = get_settings().data_dir
    cat = Catalog.scan(data_dir)
    expected = [p for p in data_dir.glob("*.txt") if not p.stem.lower().endswith("_formats")]
    assert len(cat) == len(expected)
    assert "allclinical" in cat.tables() and "00" in cat.visits("allclinical")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_catalog.py -v`
Expected: collection error — `No module named 'oai.catalog'`

- [ ] **Step 4: Write the implementation**

`src/oai/catalog.py`:
```python
"""Index of the OAI tables present in a data directory.

File stems end in a two-digit visit code (AllClinical00, kxr_sq_bu06), a cumulative
code (OUTCOMES99, COVIDQ97) or nothing (Enrollees). Names are case-folded, so
kXR_SQ_BU01 and kxr_sq_bu00 are two visits of one table.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from oai.errors import OAIError

CUMULATIVE_CODES = frozenset({"97", "99"})
INPUT_SPEC = re.compile(r"^(?P<table>[a-z0-9_]+)(?::(?P<visit>\d{2}|\*))?$")
_VISIT_SUFFIX = re.compile(r"^(?P<table>.*[^\d])(?P<visit>\d{2})$")

Kind = Literal["visit", "cumulative", "static"]


class CatalogError(OAIError):
    """Unknown table/visit, ambiguous files, or a bad input spec."""


@dataclass(frozen=True)
class TableFile:
    table: str
    visit: str | None
    kind: Kind
    path: Path

    @property
    def key(self) -> str:
        """Stable identifier such as 'allclinical_00' or 'enrollees'."""
        return self.table if self.visit is None else f"{self.table}_{self.visit}"


def parse_filename(path: Path) -> TableFile | None:
    stem = path.stem
    if stem.lower().endswith("_formats"):
        return None
    match = _VISIT_SUFFIX.match(stem)
    if match is None:
        return TableFile(stem.lower(), None, "static", path)
    visit = match["visit"]
    kind: Kind = "cumulative" if visit in CUMULATIVE_CODES else "visit"
    return TableFile(match["table"].lower().rstrip("_"), visit, kind, path)


def _normalize_visit(visit: str | int | None) -> str | None:
    if visit is None:
        return None
    text = str(visit).strip().upper().removeprefix("V")
    if not text.isdigit():
        raise CatalogError(f"Bad visit code {visit!r}")
    return text.zfill(2)


class Catalog:
    def __init__(self, files: Iterable[TableFile]) -> None:
        self._files: dict[tuple[str, str | None], TableFile] = {}
        for tf in files:
            key = (tf.table, tf.visit)
            if key in self._files:
                raise CatalogError(
                    f"Two files map to table {tf.table!r} visit {tf.visit!r}: "
                    f"{self._files[key].path.name} and {tf.path.name}"
                )
            self._files[key] = tf

    @classmethod
    def scan(cls, data_dir: Path) -> Catalog:
        if not data_dir.is_dir():
            raise CatalogError(f"OAI data directory not found: {data_dir}")
        parsed = (parse_filename(p) for p in sorted(data_dir.glob("*.txt")))
        return cls(tf for tf in parsed if tf is not None)

    def __len__(self) -> int:
        return len(self._files)

    def tables(self) -> list[str]:
        return sorted({table for table, _ in self._files})

    def visits(self, table: str) -> list[str]:
        t = table.lower()
        return sorted(v for (name, v) in self._files if name == t and v is not None)

    def get(self, table: str, visit: str | int | None = None) -> TableFile:
        t, v = table.lower(), _normalize_visit(visit)
        try:
            return self._files[(t, v)]
        except KeyError:
            if t not in self.tables():
                raise CatalogError(
                    f"Unknown table {table!r}. Run `oai catalog` to list tables."
                ) from None
            available = ", ".join(self.visits(t)) or "(no visit suffix)"
            raise CatalogError(f"Table {t!r} has no visit {visit!r}; available: {available}") from None

    def resolve_input(self, spec: str) -> list[TableFile]:
        match = INPUT_SPEC.match(spec)
        if match is None:
            raise CatalogError(f"Bad input spec {spec!r}; use 'table', 'table:VV' or 'table:*'")
        table, visit = match["table"], match["visit"]
        if visit == "*":
            files = [self._files[(table, v)] for v in self.visits(table)]
            if not files:
                raise CatalogError(f"No visits found for table {table!r}")
            return files
        return [self.get(table, visit)]


@lru_cache(maxsize=4)
def catalog_for(data_dir: Path) -> Catalog:
    """Cached catalog per data directory."""
    return Catalog.scan(data_dir)
```

Modify `src/oai/cli.py` — add imports and the error helper + command (keep existing `main` and `_version_callback`):
```python
from collections.abc import Iterator
from contextlib import contextmanager

from oai.catalog import catalog_for
from oai.config import get_settings
from oai.errors import OAIError


@contextmanager
def user_errors() -> Iterator[None]:
    """Show OAIError messages without a traceback and exit 1."""
    try:
        yield
    except OAIError as exc:
        typer.secho(f"error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1) from None


@app.command()
def catalog() -> None:
    """List the OAI tables found in OAI_DATA_DIR."""
    with user_errors():
        settings = get_settings()
        cat = catalog_for(settings.data_dir)
        for table in cat.tables():
            visits = cat.visits(table)
            typer.echo(f"{table:<32} {' '.join(visits) if visits else '(no visit)'}")
        typer.echo(f"\n{len(cat)} files, {len(cat.tables())} tables in {settings.data_dir}")
```

Modify `tests/conftest.py` — clear the catalog cache too:
```python
from oai import catalog as oai_catalog
from oai import config as oai_config


def _clear_caches() -> None:
    oai_config.get_settings.cache_clear()
    oai_catalog.catalog_for.cache_clear()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest -v && uv run pytest -m realdata tests/test_catalog.py -v && uv run oai catalog | tail -3`
Expected: all default tests pass; realdata test passes; CLI ends with `156 files, 43 tables in /Users/spiewart/OAI Complete Data_ASCII`.

- [ ] **Step 6: Commit**

```bash
git add src/oai/catalog.py src/oai/cli.py tests
git commit -m "feat: add OAI table catalog and oai catalog command" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Table loader with codebook and Parquet cache

**Files:**
- Create: `src/oai/loader.py`
- Test: `tests/test_loader.py`

**Interfaces:**
- Consumes: `catalog_for`, `TableFile`, `Settings.work_dir`, `get_settings`.
- Produces: `resolve_missing(raw: str) -> str | None` (**user-authored**); `Codebook(labels: dict[str, dict[str, str]], missing: dict[str, dict[str, str]])` with `to_json()` / `from_json()`; `policy_fingerprint() -> str`; `parse_table(path: Path) -> tuple[pl.LazyFrame, Codebook]`; `ensure_cached(tf: TableFile, settings: Settings) -> tuple[Path, Codebook]`; `read_table(name, visit=None, *, columns=None, lazy=False, settings=None) -> pl.DataFrame | pl.LazyFrame`; `codebook(name, visit=None, *, settings=None) -> Codebook`; constants `STREAMING_MAX_COLUMNS = 64`, `PARSER_VERSION = 1`.

- [ ] **Step 1: Write the failing tests**

`tests/test_loader.py`:
```python
import os

import polars as pl
import pytest

from oai import loader
from oai.catalog import CatalogError, catalog_for
from oai.config import get_settings
from oai.loader import codebook, parse_table, read_table


def _write(directory, name, text, *, encoding="utf-8", newline="\n"):
    path = directory / name
    path.write_bytes(text.replace("\n", newline).encode(encoding))
    return path


def test_types_and_coded_split():
    df = read_table("kxr_sq_bu", "00")
    assert df.schema["ID"] == pl.Int64
    assert df.schema["SIDE"] == pl.Int64
    assert df["SIDE"].to_list() == [1, 2, 1]
    assert df.schema["VERSION"] == pl.Float64
    assert df["V00XRJSM"].to_list() == [1, 0, 2]


def test_codebook_records_labels_and_missing_codes():
    cb = codebook("allclinical", "00")
    assert cb.labels["V00KPACT30"] == {"0": "No", "1": "Yes"}
    assert cb.missing["P01BMI"] == {".": "Missing Form/Incomplete Workbook"}
    assert cb.missing["V00WOMKPR"] == {".A": "Not Expected"}


def test_missing_codes_become_null_under_reference_policy():
    # Assumes the reference resolve_missing (every missing code -> null).
    # Update if the user-authored policy differs.
    df = read_table("allclinical", "00")
    assert df["P01BMI"].to_list() == [27.4, None, 31.2]
    assert df.schema["P01BMI"] == pl.Float64


def test_leading_zero_barcodes_stay_strings():
    df = read_table("kxr_sq_bu", "00")
    assert df.schema["V00BARCDBU"] == pl.String
    assert df["V00BARCDBU"][0] == "016600000001"


def test_free_text_colon_and_leading_dot_decimals_are_not_misparsed(tmp_path):
    path = _write(tmp_path, "t00.txt", "ID|NOTE|FRAC\n1000001|Note: see form|.5\n1000002|plain|0.25\n")
    lf, cb = parse_table(path)
    df = lf.collect()
    assert df["NOTE"].to_list() == ["Note: see form", "plain"]
    assert df["FRAC"].to_list() == [0.5, 0.25]
    assert "NOTE" not in cb.labels
    assert "FRAC" not in cb.missing


def test_crlf_and_latin1_files_load(tmp_path):
    text = "ID|NAME|V00AGE\n1000001|caf\xe9|61\n1000002|plain|55\n"
    path = _write(tmp_path, "t00.txt", text, encoding="latin-1", newline="\r\n")
    df = parse_table(path)[0].collect()
    assert df["V00AGE"].to_list() == [61, 55]
    assert df["NAME"].to_list()[1] == "plain"
    assert df["NAME"].to_list()[0].startswith("caf")


def test_columns_and_lazy():
    lf = read_table("allclinical", "00", columns=["ID", "V00AGE"], lazy=True)
    assert isinstance(lf, pl.LazyFrame)
    assert lf.collect().columns == ["ID", "V00AGE"]


def test_cache_is_reused(monkeypatch):
    read_table("enrollees")
    monkeypatch.setattr(loader, "parse_table", lambda path: pytest.fail("cache was not used"))
    assert read_table("enrollees").height == 3


def test_cache_rebuilt_when_source_changes(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    src = _write(data, "Enrollees.txt", "ID|P02SEX\n1000001|1: Male\n")
    monkeypatch.setenv("OAI_DATA_DIR", str(data))
    get_settings.cache_clear()
    catalog_for.cache_clear()
    assert read_table("enrollees")["P02SEX"].to_list() == [1]
    src.write_text("ID|P02SEX\n1000001|2: Female\n1000002|1: Male\n")
    st = src.stat()
    os.utime(src, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
    assert read_table("enrollees")["P02SEX"].to_list() == [2, 1]


def test_cache_rebuilt_when_missing_policy_changes(monkeypatch):
    read_table("enrollees")
    calls = []
    real_parse = loader.parse_table
    monkeypatch.setattr(loader, "policy_fingerprint", lambda: "a-different-policy")
    monkeypatch.setattr(loader, "parse_table", lambda path: calls.append(path) or real_parse(path))
    read_table("enrollees")
    assert len(calls) == 1


@pytest.mark.parametrize("max_columns", [0, 1000])
def test_streaming_and_in_memory_paths_agree(monkeypatch, max_columns):
    monkeypatch.setattr(loader, "STREAMING_MAX_COLUMNS", max_columns)
    df = read_table("allclinical", "01")
    assert df["V01PASE"].to_list() == [170, 100, None]
    assert df.schema["V01BMI"] == pl.Float64


def test_unknown_table_is_a_user_error():
    with pytest.raises(CatalogError, match="Unknown table"):
        read_table("nope")


@pytest.mark.realdata
def test_real_core_tables_load():
    enrollees = read_table("enrollees")
    assert enrollees.height > 4000
    assert enrollees.schema["ID"] == pl.Int64
    kxr = read_table("kxr_sq_bu", "00", columns=["ID", "SIDE", "V00XRKL"])
    assert set(kxr["SIDE"].drop_nulls().unique().to_list()) <= {1, 2}
    allclinical = read_table("allclinical", "00", lazy=True)
    assert {"V00AGE", "P01BMI", "V00WOMKPR"} <= set(allclinical.collect_schema().names())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_loader.py -v`
Expected: collection error — `No module named 'oai.loader'`

- [ ] **Step 3: Write the implementation (with the reference missing-value policy)**

`src/oai/loader.py`:
```python
"""Load OAI pipe-delimited tables as typed polars frames, via a Parquet cache.

Raw OAI cells look like "1: Right" (code + label), "2" (plain value) or
".: Missing Form/Incomplete Workbook" (missing-value code). Parsing keeps the code as
the cell value, moves labels into a per-table Codebook, resolves missing codes with
resolve_missing(), and casts a column to Int64/Float64 when every value allows it.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import dataclass, field
from pathlib import Path

import polars as pl

from oai.catalog import TableFile, catalog_for
from oai.config import Settings, get_settings

CODED = r"^(-?\d+(?:\.\d+)?): (.*)$"
MISSING = r"^\.[A-Z]?(?:: .*)?$"
MISSING_CODE = r"^(\.[A-Z]?)"
MISSING_LABEL = r"^\.[A-Z]?: (.*)$"
LEADING_ZERO = r"^-?0\d"
# sink_parquet streams tall/narrow tables (accelerometer minutes) efficiently but is
# pathologically slow on wide ones (AllClinical: ~1,200 columns), so pick by width.
STREAMING_MAX_COLUMNS = 64
# Bump when parsing rules change so existing caches are rebuilt.
PARSER_VERSION = 1


def resolve_missing(raw: str) -> str | None:
    """Decide what a missing-value cell becomes. USER-AUTHORED POLICY.

    `raw` is the whole cell, e.g. ".: Missing Form/Incomplete Workbook" or
    ".A: Not Expected". The return value replaces the cell before type inference;
    the code and label are always kept in Codebook.missing for that column.

    - Return None for everything: clean numeric columns; the per-cell reason is lost
      (the codebook still lists which reasons occur in each column).
    - Return a sentinel for some codes (e.g. keep ".A" distinct): any non-numeric
      sentinel turns that entire column into strings.

    Editing this function invalidates every cached table (see policy_fingerprint).
    """
    return None


@dataclass
class Codebook:
    labels: dict[str, dict[str, str]] = field(default_factory=dict)
    missing: dict[str, dict[str, str]] = field(default_factory=dict)

    def to_json(self) -> dict[str, dict[str, dict[str, str]]]:
        return {"labels": self.labels, "missing": self.missing}

    @classmethod
    def from_json(cls, data: dict) -> Codebook:
        return cls(labels=data["labels"], missing=data["missing"])


def policy_fingerprint() -> str:
    """Changes whenever the parser version or the resolve_missing source changes."""
    source = inspect.getsource(resolve_missing)
    return hashlib.sha256(f"{PARSER_VERSION}\n{source}".encode()).hexdigest()[:16]


def _scan_text(path: Path) -> pl.LazyFrame:
    return pl.scan_csv(
        path, separator="|", infer_schema=False, quote_char=None, encoding="utf8-lossy"
    )


def parse_table(path: Path) -> tuple[pl.LazyFrame, Codebook]:
    """Lazy frame with coded cells split, missing codes resolved and numerics cast."""
    lf = _scan_text(path)
    columns = lf.collect_schema().names()

    raw_missing = (
        lf.select([pl.col(c).filter(pl.col(c).str.contains(MISSING)).unique().implode() for c in columns])
        .collect()
        .row(0)
    )
    replacements = {raw: resolve_missing(raw) for values in raw_missing for raw in values}

    def cleaned(c: str) -> pl.Expr:
        col = pl.col(c)
        if not replacements:
            return col
        return (
            pl.when(col.str.contains(MISSING))
            .then(col.replace_strict(replacements, default=None, return_dtype=pl.String))
            .otherwise(col)
        )

    def value(c: str) -> pl.Expr:
        col = cleaned(c)
        return pl.coalesce(col.str.extract(CODED, 1), col)

    stats_exprs: list[pl.Expr] = []
    for c in columns:
        v, raw = value(c), pl.col(c)
        present = v.is_not_null()
        stats_exprs += [
            (present & v.str.to_integer(strict=False).is_null()).sum().alias(f"{c}::notint"),
            (present & v.cast(pl.Float64, strict=False).is_null()).sum().alias(f"{c}::notfloat"),
            (present & v.str.contains(LEADING_ZERO)).sum().alias(f"{c}::lead0"),
            pl.struct(code=raw.str.extract(CODED, 1), label=raw.str.extract(CODED, 2))
            .filter(raw.str.contains(CODED))
            .unique()
            .implode()
            .alias(f"{c}::labels"),
            pl.struct(code=raw.str.extract(MISSING_CODE, 1), label=raw.str.extract(MISSING_LABEL, 1))
            .filter(raw.str.contains(MISSING))
            .unique()
            .implode()
            .alias(f"{c}::missing"),
        ]
    stats = lf.select(stats_exprs).collect().row(0, named=True)

    book = Codebook()
    typed: list[pl.Expr] = []
    for c in columns:
        v = value(c)
        if stats[f"{c}::lead0"] == 0:
            if stats[f"{c}::notint"] == 0:
                v = v.cast(pl.Int64)
            elif stats[f"{c}::notfloat"] == 0:
                v = v.cast(pl.Float64)
        typed.append(v.alias(c))
        if labels := stats[f"{c}::labels"]:
            ordered = sorted(labels, key=lambda d: float(d["code"]))
            book.labels[c] = {d["code"]: d["label"] for d in ordered}
        if missing := stats[f"{c}::missing"]:
            book.missing[c] = {d["code"]: d["label"] or "" for d in missing}
    return lf.select(typed), book


def _source_meta(path: Path) -> dict[str, object]:
    st = path.stat()
    return {
        "source": str(path),
        "size": st.st_size,
        "mtime_ns": st.st_mtime_ns,
        "policy": policy_fingerprint(),
    }


def ensure_cached(tf: TableFile, settings: Settings) -> tuple[Path, Codebook]:
    """Return (parquet path, codebook), rebuilding the cache when it is stale."""
    base = settings.work_dir / "cache" / tf.key
    parquet, sidecar = base.with_suffix(".parquet"), base.with_suffix(".json")
    meta = _source_meta(tf.path)
    if parquet.exists() and sidecar.exists():
        stored = json.loads(sidecar.read_text())
        if stored.get("meta") == meta:
            return parquet, Codebook.from_json(stored["codebook"])
    parquet.parent.mkdir(parents=True, exist_ok=True)
    lf, book = parse_table(tf.path)
    tmp = parquet.parent / f"{parquet.name}.tmp"
    if len(lf.collect_schema()) <= STREAMING_MAX_COLUMNS:
        lf.sink_parquet(tmp)
    else:
        lf.collect().write_parquet(tmp)
    tmp.replace(parquet)
    sidecar.write_text(json.dumps({"meta": meta, "codebook": book.to_json()}, indent=1))
    return parquet, book


def _table_file(name: str, visit: str | int | None, settings: Settings) -> TableFile:
    return catalog_for(settings.data_dir).get(name, visit)


def read_table(
    name: str,
    visit: str | int | None = None,
    *,
    columns: list[str] | None = None,
    lazy: bool = False,
    settings: Settings | None = None,
) -> pl.DataFrame | pl.LazyFrame:
    """Load an OAI table, e.g. read_table("kxr_sq_bu", "00", columns=["ID", "SIDE"])."""
    settings = settings or get_settings()
    parquet, _ = ensure_cached(_table_file(name, visit, settings), settings)
    if lazy:
        lf = pl.scan_parquet(parquet)
        return lf.select(columns) if columns else lf
    return pl.read_parquet(parquet, columns=columns)


def codebook(name: str, visit: str | int | None = None, *, settings: Settings | None = None) -> Codebook:
    """Value labels and missing-value codes for a table."""
    settings = settings or get_settings()
    return ensure_cached(_table_file(name, visit, settings), settings)[1]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -v && uv run pytest -m realdata tests/test_loader.py -v`
Expected: all pass. The realdata run takes ~10–20 s (first parse of AllClinical00).

- [ ] **Step 5: USER CONTRIBUTION — missing-value policy**

Pause and invite the user to replace the body of `resolve_missing` in `src/oai/loader.py` (5–10 lines). Show them `uv run python -c "from oai.loader import codebook; print(codebook('allclinical','00').missing)" | head` output from their real data first, so the decision is grounded in the codes that actually occur. If their policy differs from "all → null", update `test_missing_codes_become_null_under_reference_policy` to match, then rerun `uv run pytest tests/test_loader.py -v`.

- [ ] **Step 6: Commit**

```bash
git add src/oai/loader.py tests/test_loader.py
git commit -m "feat: add OAI table loader with codebook and Parquet cache" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Visit map, long format and time

**Files:**
- Create: `src/oai/visits.py`
- Modify: `config/oai.toml`
- Test: `tests/test_visits.py`

**Interfaces:**
- Consumes: `get_settings().project`, `ConfigError`, `OAIError`.
- Produces: `Visit(code: str, month: int | None, contact: str | None, verified: bool)`; `UnknownVisitError(OAIError, ValueError)`; `UnverifiedVisitError(OAIError, ValueError)`; `normalize_code(code: str | int) -> str` (`"V06"`); `load_visit_map(project=None) -> dict[str, Visit]`; `nominal_month(code, *, visit_map=None) -> int`; `to_long(df, id_cols=("ID",)) -> pl.DataFrame` (columns: id cols, `visit`, stems); `time_years(df, *, visit_map=None) -> pl.DataFrame` (adds `time_years: Float64`, `time_source: "visdys" | "nominal"`).

- [ ] **Step 1: Add the visit map to `config/oai.toml`** (append)

```toml

# Visit-code map (docs/reference/oai-dataset-table-structure.md). V02/V04/V07/V09 are
# telephone contacts. V11-V14 exist in this release (extended follow-up) but their
# nominal months are unconfirmed: check AllClinical13_ReleaseComments_Yr14.pdf and
# AllClinical14_ReleaseComments_Y16.pdf in OAI_DATA_DIR, then add month/contact and
# set verified = true. Until then time comes from V##VISDYS (present from V03 on).
[visits]
V00 = { month = 0, contact = "clinic", verified = true }
V01 = { month = 12, contact = "clinic", verified = true }
V02 = { month = 18, contact = "phone", verified = true }
V03 = { month = 24, contact = "clinic", verified = true }
V04 = { month = 30, contact = "phone", verified = true }
V05 = { month = 36, contact = "clinic", verified = true }
V06 = { month = 48, contact = "clinic", verified = true }
V07 = { month = 60, contact = "phone", verified = true }
V08 = { month = 72, contact = "clinic", verified = true }
V09 = { month = 84, contact = "phone", verified = true }
V10 = { month = 96, contact = "clinic", verified = true }
V11 = { verified = false }
V12 = { verified = false }
V13 = { verified = false }
V14 = { verified = false }
```

- [ ] **Step 2: Write the failing tests**

`tests/test_visits.py`:
```python
import polars as pl
import pytest

from oai.config import ConfigError
from oai.visits import (
    UnknownVisitError,
    UnverifiedVisitError,
    load_visit_map,
    nominal_month,
    normalize_code,
    time_years,
    to_long,
)


@pytest.mark.parametrize("raw", ["V06", "v06", "06", "6", 6])
def test_normalize_code(raw):
    assert normalize_code(raw) == "V06"


def test_normalize_code_rejects_non_visits():
    with pytest.raises(UnknownVisitError):
        normalize_code("P01")


def test_repo_visit_map_matches_docs():
    vm = load_visit_map()
    assert [vm[c].month for c in ("V00", "V01", "V03", "V05", "V06", "V08", "V10")] == [
        0, 12, 24, 36, 48, 72, 96,
    ]
    assert vm["V02"].contact == "phone"
    assert not vm["V13"].verified


def test_nominal_month_refuses_unverified_visits():
    with pytest.raises(UnverifiedVisitError, match="V13"):
        nominal_month("13")


def test_nominal_month_unknown_visit():
    with pytest.raises(UnknownVisitError, match="V20"):
        nominal_month("V20")


def test_verified_visit_without_month_is_a_config_error():
    with pytest.raises(ConfigError, match="V05"):
        load_visit_map({"visits": {"V05": {"verified": True}}})


def test_to_long_melts_visit_prefixed_columns():
    wide = pl.DataFrame(
        {
            "ID": [1000001, 1000001],
            "SIDE": [1, 2],
            "READPRJ": [15, 15],
            "V00XRKL": [1, 2],
            "V01XRKL": [2, 2],
            "V01XRJSM": [0, 1],
        }
    )
    long = to_long(wide, id_cols=("ID", "SIDE"))
    assert long.columns == ["ID", "SIDE", "visit", "XRKL", "XRJSM"]
    assert long.sort(["visit", "SIDE"]).rows() == [
        (1000001, 1, "V00", 1, None),
        (1000001, 2, "V00", 2, None),
        (1000001, 1, "V01", 2, 0),
        (1000001, 2, "V01", 2, 1),
    ]


def test_to_long_requires_id_columns():
    with pytest.raises(ValueError, match="SIDE"):
        to_long(pl.DataFrame({"ID": [1000001], "V00XRKL": [1]}), id_cols=("ID", "SIDE"))


def test_time_years_prefers_visdys_and_falls_back_to_nominal():
    long = pl.DataFrame(
        {"ID": [1000001] * 3, "visit": ["V00", "V01", "V03"], "VISDYS": [None, None, 740]}
    )
    out = time_years(long)
    assert out["time_years"].to_list() == pytest.approx([0.0, 1.0, 740 / 365.25])
    assert out["time_source"].to_list() == ["nominal", "nominal", "visdys"]


def test_time_years_without_visdys_column_uses_nominal():
    out = time_years(pl.DataFrame({"ID": [1000001, 1000001], "visit": ["V00", "V06"]}))
    assert out["time_years"].to_list() == [0.0, 4.0]


def test_unverified_visit_needs_visdys():
    long = pl.DataFrame({"ID": [1000001], "visit": ["V13"], "VISDYS": [None]})
    with pytest.raises(UnverifiedVisitError):
        time_years(long)


def test_unverified_visit_with_visdys_is_fine():
    long = pl.DataFrame({"ID": [1000001], "visit": ["V13"], "VISDYS": [4383]})
    assert time_years(long)["time_years"].to_list() == pytest.approx([4383 / 365.25])
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_visits.py -v`
Expected: collection error — `No module named 'oai.visits'`

- [ ] **Step 4: Write the implementation**

`src/oai/visits.py`:
```python
"""OAI visit codes (V00..V14): nominal month, contact type, wide->long reshaping and time.

The numeric part of V## is NOT elapsed months (V06 = 48 months). Always go through
this module; prefer V##VISDYS (days since enrollment) over nominal months.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import polars as pl

from oai.config import ConfigError, get_settings
from oai.errors import OAIError

VISIT_COLUMN = re.compile(r"^V(\d{2})(.+)$")
DAYS_PER_YEAR = 365.25


class UnknownVisitError(OAIError, ValueError):
    """Not a visit code, or not in the visit map."""


class UnverifiedVisitError(OAIError, ValueError):
    """The visit's nominal month has not been confirmed from release documentation."""


@dataclass(frozen=True)
class Visit:
    code: str
    month: int | None
    contact: str | None
    verified: bool


def normalize_code(code: str | int) -> str:
    text = str(code).strip().upper().removeprefix("V")
    if not text.isdigit() or len(text) > 2:
        raise UnknownVisitError(f"Not a visit code: {code!r}")
    return f"V{int(text):02d}"


def load_visit_map(project: Mapping[str, Any] | None = None) -> dict[str, Visit]:
    project = get_settings().project if project is None else project
    raw = project.get("visits")
    if not raw:
        raise ConfigError("No [visits] table in config/oai.toml")
    visits: dict[str, Visit] = {}
    for code, entry in raw.items():
        c = normalize_code(code)
        verified = bool(entry.get("verified", False))
        month = entry.get("month")
        if verified and month is None:
            raise ConfigError(f"Visit {c} is marked verified but has no month")
        visits[c] = Visit(c, month, entry.get("contact"), verified)
    return visits


def nominal_month(code: str | int, *, visit_map: Mapping[str, Visit] | None = None) -> int:
    vm = load_visit_map() if visit_map is None else visit_map
    c = normalize_code(code)
    if c not in vm:
        raise UnknownVisitError(f"Visit {c} is not in the visit map")
    visit = vm[c]
    if not visit.verified or visit.month is None:
        raise UnverifiedVisitError(
            f"Nominal month for {c} is unverified; confirm it from the release documentation "
            "and update [visits] in config/oai.toml (or use V##VISDYS)."
        )
    return visit.month


def to_long(df: pl.DataFrame, id_cols: Sequence[str] = ("ID",)) -> pl.DataFrame:
    """Melt V##<STEM> columns into rows keyed on id_cols + visit.

    Columns that are neither id columns nor V##-prefixed (e.g. P01BMI, READPRJ) are
    dropped; join person-level fields separately.
    """
    missing = [c for c in id_cols if c not in df.columns]
    if missing:
        raise ValueError(f"id columns not in frame: {missing}")
    by_visit: dict[str, dict[str, str]] = {}
    for col in df.columns:
        match = VISIT_COLUMN.match(col)
        if match and col not in id_cols:
            by_visit.setdefault(f"V{match[1]}", {})[col] = match[2]
    if not by_visit:
        raise ValueError("No V##-prefixed columns found")
    parts = [
        df.select([*id_cols, *[pl.col(src).alias(stem) for src, stem in cols.items()]]).with_columns(
            pl.lit(code).alias("visit")
        )
        for code, cols in sorted(by_visit.items())
    ]
    out = pl.concat(parts, how="diagonal_relaxed")
    rest = [c for c in out.columns if c not in (*id_cols, "visit")]
    return out.select([*id_cols, "visit", *rest])


def time_years(df: pl.DataFrame, *, visit_map: Mapping[str, Visit] | None = None) -> pl.DataFrame:
    """Add time_years (VISDYS / 365.25, else nominal month / 12) and time_source."""
    if "visit" not in df.columns:
        raise ValueError("time_years expects a long frame with a 'visit' column (see to_long)")
    vm = load_visit_map() if visit_map is None else visit_map
    has_days = "VISDYS" in df.columns
    days = pl.col("VISDYS").cast(pl.Float64) if has_days else pl.lit(None, dtype=pl.Float64)
    fallback_rows = df.filter(days.is_null()) if has_days else df
    months = {code: nominal_month(code, visit_map=vm) for code in fallback_rows["visit"].unique().to_list()}
    nominal = pl.col("visit").replace_strict(months, default=None, return_dtype=pl.Float64)
    return df.with_columns(
        pl.coalesce(days / DAYS_PER_YEAR, nominal / 12).alias("time_years"),
        pl.when(days.is_not_null()).then(pl.lit("visdys")).otherwise(pl.lit("nominal")).alias("time_source"),
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/oai/visits.py config/oai.toml tests/test_visits.py
git commit -m "feat: add visit map, long-format reshaping and time derivation" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Analysis manifests and `oai analyses`

**Files:**
- Create: `src/oai/manifest.py`
- Modify: `src/oai/cli.py`
- Test: `tests/test_manifest.py`

**Interfaces:**
- Consumes: `INPUT_SPEC` from `oai.catalog`, `OAIError`, `get_settings().analyses_dir`.
- Produces: `ManifestError(OAIError)`; `Step(id, lang: "python"|"r", stage: "local"|"enclave", entry: str, needs: tuple[str, ...])`; `ExportSpec(frame: str, columns: tuple[str, ...])`; `Analysis(name, description, root: Path, inputs: tuple[str, ...], steps: tuple[Step, ...], export: ExportSpec | None, aggregate_outputs: tuple[str, ...])` with properties `languages: set[str]`, `stages: set[str]`; `load_analysis(path: Path) -> Analysis`; `find_analysis(name, analyses_dir) -> Analysis`; `list_analyses(analyses_dir) -> list[Analysis]`; `MANIFEST_NAME = "analysis.toml"`.

- [ ] **Step 1: Write the failing tests**

`tests/test_manifest.py`:
```python
import textwrap

import pytest
from typer.testing import CliRunner

from oai.cli import app
from oai.manifest import ManifestError, find_analysis, list_analyses, load_analysis

VALID = textwrap.dedent(
    """
    name = "demo"
    description = "Demo analysis"

    [inputs]
    tables = ["enrollees", "allclinical:00", "kxr_sq_bu:*"]

    [[steps]]
    id = "frame"
    lang = "python"
    stage = "local"
    entry = "frame.py"

    [[steps]]
    id = "models"
    lang = "r"
    stage = "enclave"
    entry = "models.R"
    needs = ["frame"]

    [export]
    frame = "frame.parquet"
    columns = ["ID", "SIDE"]

    [outputs]
    aggregate = ["results/*.csv"]
    """
)


def write_analysis(parent, text, name="demo", files=("frame.py", "models.R")):
    root = parent / name
    root.mkdir(parents=True)
    (root / "analysis.toml").write_text(text)
    for f in files:
        (root / f).write_text("# stub\n")
    return root


def test_valid_manifest(tmp_path):
    a = load_analysis(write_analysis(tmp_path, VALID))
    assert a.name == "demo" and a.description == "Demo analysis"
    assert a.inputs == ("enrollees", "allclinical:00", "kxr_sq_bu:*")
    assert [s.id for s in a.steps] == ["frame", "models"]
    assert a.steps[1].needs == ("frame",) and a.steps[1].stage == "enclave"
    assert a.export.columns == ("ID", "SIDE")
    assert a.aggregate_outputs == ("results/*.csv",)
    assert a.languages == {"python", "r"} and a.stages == {"local", "enclave"}


@pytest.mark.parametrize(
    "old, new, message",
    [
        ('name = "demo"', 'name = "other"', "must match its directory"),
        ('"allclinical:00"', '"AllClinical:0"', "bad input spec"),
        ('lang = "r"', 'lang = "julia"', "lang must be one of"),
        ('stage = "enclave"', 'stage = "cloud"', "stage must be one of"),
        ('needs = ["frame"]', 'needs = ["later"]', "not an earlier step"),
        ('entry = "models.R"', 'entry = "missing.R"', "not found"),
        ('id = "models"', 'id = "frame"', "duplicate step id"),
        ('columns = ["ID", "SIDE"]', "columns = []", "non-empty 'columns'"),
    ],
)
def test_invalid_manifests(tmp_path, old, new, message):
    assert old in VALID
    with pytest.raises(ManifestError, match=message):
        load_analysis(write_analysis(tmp_path, VALID.replace(old, new)))


def test_enclave_steps_require_export(tmp_path):
    text = VALID.split("[export]")[0]
    with pytest.raises(ManifestError, match=r"must declare \[export\]"):
        load_analysis(write_analysis(tmp_path, text))


def test_invalid_toml(tmp_path):
    with pytest.raises(ManifestError, match="invalid TOML"):
        load_analysis(write_analysis(tmp_path, "name = "))


def test_find_analysis_lists_available(tmp_path):
    write_analysis(tmp_path, VALID)
    with pytest.raises(ManifestError, match="available: demo"):
        find_analysis("nope", tmp_path)


def test_list_analyses(tmp_path):
    write_analysis(tmp_path, VALID)
    assert [a.name for a in list_analyses(tmp_path)] == ["demo"]


def test_cli_analyses(tmp_path, monkeypatch):
    write_analysis(tmp_path, VALID)
    monkeypatch.setenv("OAI_ANALYSES_DIR", str(tmp_path))
    result = CliRunner().invoke(app, ["analyses"])
    assert result.exit_code == 0, result.output
    assert "demo" in result.stdout and "[enclave,local]" in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_manifest.py -v`
Expected: collection error — `No module named 'oai.manifest'`

- [ ] **Step 3: Write the implementation**

`src/oai/manifest.py`:
```python
"""analysis.toml: the contract between an analysis folder and the runner/exporter."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, NoReturn

from oai.catalog import INPUT_SPEC
from oai.errors import OAIError

MANIFEST_NAME = "analysis.toml"
LANGS = ("python", "r")
STAGES = ("local", "enclave")
_IDENT = re.compile(r"^[a-z][a-z0-9_]*$")


class ManifestError(OAIError):
    """An analysis.toml is missing or invalid."""


@dataclass(frozen=True)
class Step:
    id: str
    lang: Literal["python", "r"]
    stage: Literal["local", "enclave"]
    entry: str
    needs: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExportSpec:
    frame: str
    columns: tuple[str, ...]


@dataclass(frozen=True)
class Analysis:
    name: str
    description: str
    root: Path
    inputs: tuple[str, ...]
    steps: tuple[Step, ...]
    export: ExportSpec | None
    aggregate_outputs: tuple[str, ...]

    @property
    def languages(self) -> set[str]:
        return {s.lang for s in self.steps}

    @property
    def stages(self) -> set[str]:
        return {s.stage for s in self.steps}


def load_analysis(path: Path) -> Analysis:
    root = path if path.is_dir() else path.parent
    toml_path = root / MANIFEST_NAME
    if not toml_path.is_file():
        raise ManifestError(f"No {MANIFEST_NAME} in {root}")
    try:
        data = tomllib.loads(toml_path.read_text())
    except tomllib.TOMLDecodeError as exc:
        raise ManifestError(f"{toml_path}: invalid TOML: {exc}") from None
    return _parse(data, root, toml_path)


def _parse(data: dict[str, Any], root: Path, where: Path) -> Analysis:
    def fail(message: str) -> NoReturn:
        raise ManifestError(f"{where}: {message}")

    name = data.get("name")
    if not isinstance(name, str) or not _IDENT.match(name):
        fail("'name' must be a lowercase identifier")
    if name != root.name:
        fail(f"name {name!r} must match its directory name {root.name!r}")

    inputs = tuple(data.get("inputs", {}).get("tables", []))
    for spec in inputs:
        if not INPUT_SPEC.match(spec):
            fail(f"bad input spec {spec!r} (use 'table', 'table:VV' or 'table:*')")

    raw_steps = data.get("steps", [])
    if not raw_steps:
        fail("at least one [[steps]] entry is required")
    steps: list[Step] = []
    seen: set[str] = set()
    for i, raw in enumerate(raw_steps):
        sid = raw.get("id")
        if not isinstance(sid, str) or not _IDENT.match(sid):
            fail(f"steps[{i}].id must be a lowercase identifier")
        if sid in seen:
            fail(f"duplicate step id {sid!r}")
        lang, stage, entry = raw.get("lang"), raw.get("stage", "local"), raw.get("entry")
        if lang not in LANGS:
            fail(f"step {sid!r}: lang must be one of {', '.join(LANGS)}")
        if stage not in STAGES:
            fail(f"step {sid!r}: stage must be one of {', '.join(STAGES)}")
        if not isinstance(entry, str) or not (root / entry).is_file():
            fail(f"step {sid!r}: entry {entry!r} not found in {root}")
        needs = tuple(raw.get("needs", []))
        for need in needs:
            if need not in seen:
                fail(f"step {sid!r} needs {need!r}, which is not an earlier step")
        steps.append(Step(sid, lang, stage, entry, needs))
        seen.add(sid)

    export = None
    if "export" in data:
        frame, columns = data["export"].get("frame"), tuple(data["export"].get("columns", []))
        if not isinstance(frame, str) or not columns:
            fail("[export] needs 'frame' and a non-empty 'columns' list")
        export = ExportSpec(frame, columns)
    if export is None and any(s.stage == "enclave" for s in steps):
        fail("has stage='enclave' steps and must declare [export]")

    outputs = tuple(data.get("outputs", {}).get("aggregate", []))
    return Analysis(name, data.get("description", ""), root, inputs, tuple(steps), export, outputs)


def list_analyses(analyses_dir: Path) -> list[Analysis]:
    return [load_analysis(p.parent) for p in sorted(analyses_dir.glob(f"*/{MANIFEST_NAME}"))]


def find_analysis(name: str, analyses_dir: Path) -> Analysis:
    root = analyses_dir / name
    if not (root / MANIFEST_NAME).is_file():
        available = sorted(p.parent.name for p in analyses_dir.glob(f"*/{MANIFEST_NAME}"))
        raise ManifestError(
            f"Unknown analysis {name!r}; available: {', '.join(available) or '(none)'}"
        )
    return load_analysis(root)
```

Modify `src/oai/cli.py` — add import and command:
```python
from oai.manifest import list_analyses


@app.command()
def analyses() -> None:
    """List analyses and validate their manifests."""
    with user_errors():
        for a in list_analyses(get_settings().analyses_dir):
            typer.echo(f"{a.name:<28} [{','.join(sorted(a.stages))}] {a.description}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/oai/manifest.py src/oai/cli.py tests/test_manifest.py
git commit -m "feat: add analysis manifests and oai analyses command" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Step runner and `oai run`

**Files:**
- Create: `src/oai/runner.py`
- Modify: `src/oai/cli.py`
- Test: `tests/test_runner.py`

**Interfaces:**
- Consumes: `Analysis`, `Step`, `find_analysis`, `Settings` (`work_dir`, `results_dir`, `geno_dir`, `repo_root`).
- Produces: `RunnerError(OAIError)`; `StepResult(step_id: str, returncode: int)`; `select_steps(analysis, *, stage=None, step_id=None) -> list[Step]`; `frame_dir(analysis, settings, env: Mapping[str, str]) -> Path`; `step_env(analysis, settings, base_env=None) -> dict[str, str]` (sets `OAI_ANALYSIS`, `OAI_FRAME_DIR`, `OAI_RESULTS_DIR`); `step_command(step, analysis) -> list[str]`; `run_analysis(analysis, settings, *, stage=None, step_id=None, base_env=None, echo=print) -> list[StepResult]`.

- [ ] **Step 1: Write the failing tests**

`tests/test_runner.py`:
```python
import textwrap

import pytest
from typer.testing import CliRunner

from oai import runner
from oai.cli import app
from oai.config import load_settings
from oai.manifest import load_analysis
from oai.runner import RunnerError, run_analysis, select_steps

MANIFEST = textwrap.dedent(
    """
    name = "toy"

    [[steps]]
    id = "a"
    lang = "python"
    stage = "local"
    entry = "a.py"

    [[steps]]
    id = "b"
    lang = "python"
    stage = "enclave"
    entry = "b.py"
    needs = ["a"]

    [export]
    frame = "frame.parquet"
    columns = ["ID"]
    """
)

MARKER = textwrap.dedent(
    """
    import os, pathlib
    frame = pathlib.Path(os.environ["OAI_FRAME_DIR"])
    (frame / "{step}.done").write_text(os.environ["OAI_RESULTS_DIR"] + "|" + os.environ["OAI_ANALYSIS"])
    """
)


@pytest.fixture
def toy(tmp_path):
    root = tmp_path / "analyses" / "toy"
    root.mkdir(parents=True)
    (root / "analysis.toml").write_text(MANIFEST)
    for step in ("a", "b"):
        (root / f"{step}.py").write_text(MARKER.replace("{step}", step))
    return load_analysis(root)


def make_settings(tmp_path, **extra):
    env = {"OAI_WORK_DIR": str(tmp_path / "work"), "OAI_RESULTS_DIR": str(tmp_path / "results"), **extra}
    return load_settings(env=env, repo_root=None)


def test_runs_local_steps_with_step_env(toy, tmp_path):
    results = run_analysis(toy, make_settings(tmp_path), stage="local", echo=lambda _: None)
    assert [(r.step_id, r.returncode) for r in results] == [("a", 0)]
    marker = tmp_path / "work" / "toy" / "a.done"
    assert marker.read_text() == f"{(tmp_path / 'results' / 'toy').resolve()}|toy"
    assert not (tmp_path / "work" / "toy" / "b.done").exists()


def test_enclave_steps_need_geno_dir_and_nothing_runs_without_it(toy, tmp_path):
    with pytest.raises(RunnerError, match="OAI_GENO_DIR"):
        run_analysis(toy, make_settings(tmp_path), echo=lambda _: None)
    assert not (tmp_path / "work" / "toy" / "a.done").exists()


def test_enclave_steps_run_when_geno_dir_set(toy, tmp_path):
    settings = make_settings(tmp_path, OAI_GENO_DIR=str(tmp_path / "geno"))
    run_analysis(toy, settings, stage="enclave", echo=lambda _: None)
    assert (tmp_path / "work" / "toy" / "b.done").exists()


def test_frame_dir_override(toy, tmp_path):
    frame = tmp_path / "bundle-data"
    env = {"OAI_FRAME_DIR": str(frame), "PATH": ""}
    run_analysis(toy, make_settings(tmp_path), stage="local", base_env=env, echo=lambda _: None)
    assert (frame / "a.done").exists()


def test_failing_step_stops_the_run(toy, tmp_path):
    (toy.root / "a.py").write_text("raise SystemExit(3)\n")
    settings = make_settings(tmp_path, OAI_GENO_DIR=str(tmp_path / "geno"))
    with pytest.raises(RunnerError, match="step 'a' failed with exit code 3"):
        run_analysis(toy, settings, echo=lambda _: None)
    assert not (tmp_path / "work" / "toy" / "b.done").exists()


def test_missing_rscript_fails_before_anything_runs(toy, tmp_path, monkeypatch):
    (toy.root / "m.R").write_text("cat('hi')\n")
    (toy.root / "analysis.toml").write_text(
        MANIFEST + '\n[[steps]]\nid = "m"\nlang = "r"\nstage = "local"\nentry = "m.R"\n'
    )
    analysis = load_analysis(toy.root)
    monkeypatch.setattr(runner.shutil, "which", lambda name: None)
    with pytest.raises(RunnerError, match="Rscript not found"):
        run_analysis(analysis, make_settings(tmp_path), stage="local", echo=lambda _: None)
    assert not (tmp_path / "work" / "toy" / "a.done").exists()


def test_select_steps_errors(toy):
    with pytest.raises(RunnerError, match="no step 'zz'"):
        select_steps(toy, step_id="zz")
    with pytest.raises(RunnerError, match="stage must be"):
        select_steps(toy, stage="cloud")


def test_cli_run(toy, tmp_path, monkeypatch):
    monkeypatch.setenv("OAI_ANALYSES_DIR", str(toy.root.parent))
    result = CliRunner().invoke(app, ["run", "toy", "--stage", "local"])
    assert result.exit_code == 0, result.output
    assert "a" in result.stdout
    assert (tmp_path / "work" / "toy" / "a.done").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_runner.py -v`
Expected: collection error — `No module named 'oai.runner'`

- [ ] **Step 3: Write the implementation**

`src/oai/runner.py`:
```python
"""Execute an analysis's steps in declared order.

Each step runs as a subprocess in its analysis folder with:
  OAI_ANALYSIS     analysis name
  OAI_FRAME_DIR    where frames are read/written (default OAI_WORK_DIR/<analysis>;
                   a bundle's run.sh points it at the bundle's data/)
  OAI_RESULTS_DIR  aggregate outputs for this analysis (<results_dir>/<analysis>)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from oai.config import Settings
from oai.errors import OAIError
from oai.manifest import STAGES, Analysis, Step


class RunnerError(OAIError):
    """A step could not be selected, started or completed."""


@dataclass(frozen=True)
class StepResult:
    step_id: str
    returncode: int


def select_steps(analysis: Analysis, *, stage: str | None = None, step_id: str | None = None) -> list[Step]:
    if stage is not None and stage not in STAGES:
        raise RunnerError(f"stage must be one of {', '.join(STAGES)}, not {stage!r}")
    steps = list(analysis.steps)
    if step_id is not None:
        steps = [s for s in steps if s.id == step_id]
        if not steps:
            raise RunnerError(f"{analysis.name} has no step {step_id!r}")
    if stage is not None:
        steps = [s for s in steps if s.stage == stage]
    if not steps:
        raise RunnerError(f"No steps of {analysis.name} match stage={stage!r} step={step_id!r}")
    return steps


def frame_dir(analysis: Analysis, settings: Settings, env: Mapping[str, str]) -> Path:
    override = env.get("OAI_FRAME_DIR")
    return Path(override) if override else settings.work_dir / analysis.name


def step_env(analysis: Analysis, settings: Settings, base_env: Mapping[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if base_env is None else base_env)
    frames = frame_dir(analysis, settings, env)
    results = settings.results_dir / analysis.name
    frames.mkdir(parents=True, exist_ok=True)
    results.mkdir(parents=True, exist_ok=True)
    env.update(OAI_ANALYSIS=analysis.name, OAI_FRAME_DIR=str(frames), OAI_RESULTS_DIR=str(results))
    return env


def step_command(step: Step, analysis: Analysis) -> list[str]:
    entry = str(analysis.root / step.entry)
    if step.lang == "python":
        return [sys.executable, entry]
    rscript = shutil.which("Rscript")
    if rscript is None:
        raise RunnerError("Rscript not found on PATH; install R to run R steps")
    return [rscript, entry]


def run_analysis(
    analysis: Analysis,
    settings: Settings,
    *,
    stage: str | None = None,
    step_id: str | None = None,
    base_env: Mapping[str, str] | None = None,
    echo: Callable[[str], None] = print,
) -> list[StepResult]:
    steps = select_steps(analysis, stage=stage, step_id=step_id)
    if any(s.stage == "enclave" for s in steps) and settings.geno_dir is None:
        raise RunnerError("Enclave steps require OAI_GENO_DIR; they only run inside the secure enclave.")
    commands = [(step, step_command(step, analysis)) for step in steps]  # fail before running anything
    env = step_env(analysis, settings, base_env)
    results: list[StepResult] = []
    for step, cmd in commands:
        echo(f"==> {analysis.name}:{step.id} ({step.lang}, {step.stage})")
        proc = subprocess.run(cmd, cwd=analysis.root, env=env)
        results.append(StepResult(step.id, proc.returncode))
        if proc.returncode != 0:
            raise RunnerError(f"step {step.id!r} failed with exit code {proc.returncode}")
    return results
```

Modify `src/oai/cli.py` — add imports and command:
```python
from oai.manifest import find_analysis, list_analyses
from oai.runner import run_analysis


@app.command()
def run(
    name: Annotated[str, typer.Argument(help="Analysis folder name under analyses/.")],
    stage: Annotated[str | None, typer.Option(help="Only run steps of this stage (local|enclave).")] = None,
    step: Annotated[str | None, typer.Option(help="Only run this step id.")] = None,
) -> None:
    """Run an analysis's steps in declared order."""
    with user_errors():
        settings = get_settings()
        analysis = find_analysis(name, settings.analyses_dir)
        results = run_analysis(analysis, settings, stage=stage, step_id=step, echo=typer.echo)
        typer.echo(f"{len(results)} step(s) completed: {', '.join(r.step_id for r in results)}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/oai/runner.py src/oai/cli.py tests/test_runner.py
git commit -m "feat: add step runner and oai run command" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: R project and `oaimodels` package

**Files:**
- Create: `r/oaimodels/{DESCRIPTION,NAMESPACE,LICENSE}`, `r/oaimodels/R/read_frame.R`, `r/oaimodels/R/models.R`, `r/oaimodels/tests/testthat.R`, `r/oaimodels/tests/testthat/test-read_frame.R`, `r/oaimodels/tests/testthat/test-models.R`, `r/step-profile.R`; generated `r/.Rprofile`, `r/renv.lock`, `r/renv/{activate.R,settings.json,.gitignore}`
- Modify: `src/oai/runner.py` (`step_env`)
- Test: `tests/test_r_interop.py`

**Interfaces:**
- Consumes: `step_env`, `Settings.repo_root`.
- Produces (R): `read_frame(path = file.path(Sys.getenv("OAI_FRAME_DIR"), "frame.parquet"), required = character())`, `default_covariates(n_pcs = 10)`, stubs `fit_progression_lmm`, `fit_kl_clmm`, `fit_progressor_gee`, `fit_tkr_cox`. Runner adds `OAI_R_DIR` and `R_PROFILE_USER` for R steps run from a checkout so `oaimodels::fn()` works locally exactly as it does against the installed package in the enclave.

- [ ] **Step 1: Write the R package**

`r/oaimodels/DESCRIPTION`:
```text
Package: oaimodels
Title: Shared Model Helpers for OAI Analytics
Version: 0.1.0
Author: oai-analytics contributors
Maintainer: oai-analytics contributors <oai-analytics@users.noreply.github.com>
Description: Loads analysis frames written by the Python side and wraps the
    mixed, cumulative-link, GEE and Cox models specified in the OAI analysis plan.
License: MIT + file LICENSE
Encoding: UTF-8
Depends: R (>= 4.2)
Imports: nanoparquet
Suggests: testthat (>= 3.0.0), lme4, ordinal, geepack, survival
Config/testthat/edition: 3
```

`r/oaimodels/LICENSE`:
```text
YEAR: 2026
COPYRIGHT HOLDER: oai-analytics contributors
```

`r/oaimodels/NAMESPACE`:
```text
export(read_frame)
export(default_covariates)
export(fit_progression_lmm)
export(fit_kl_clmm)
export(fit_progressor_gee)
export(fit_tkr_cox)
```

`r/oaimodels/R/read_frame.R`:
```r
#' Read an analysis frame written by the Python side
#'
#' @param path Parquet file. Defaults to `frame.parquet` in `OAI_FRAME_DIR`,
#'   which `oai run` sets for every step.
#' @param required Columns that must be present.
#' @return A data.frame.
read_frame <- function(path = file.path(Sys.getenv("OAI_FRAME_DIR"), "frame.parquet"),
                       required = character()) {
  if (!file.exists(path)) stop("Frame not found: ", path, call. = FALSE)
  frame <- as.data.frame(nanoparquet::read_parquet(path))
  missing <- setdiff(required, names(frame))
  if (length(missing)) {
    stop("Frame is missing required columns: ", paste(missing, collapse = ", "), call. = FALSE)
  }
  frame
}
```

`r/oaimodels/R/models.R`:
```r
#' Confounder block shared by every model in the analysis plan (section 11)
#' @param n_pcs Number of ancestry principal components.
default_covariates <- function(n_pcs = 10) {
  c("age0", "sex", "bmi0", if (n_pcs > 0) paste0("PC", seq_len(n_pcs)))
}

not_implemented <- function(section) {
  stop("Not implemented yet: see docs/reference/oai-activity-agreement-analysis-plan.md, section ",
       section, call. = FALSE)
}

#' Continuous progression: lmer(outcome ~ time * exposure + covariates + (time | ID/SIDE)) (11.1)
fit_progression_lmm <- function(frame, outcome, exposure = "geno_add",
                                covariates = default_covariates()) {
  not_implemented("11.1")
}

#' KL-grade transition: clmm(kl ~ time * exposure + covariates + (1 | ID/SIDE)) (11.2)
fit_kl_clmm <- function(frame, outcome = "kl_grade", exposure = "geno_add",
                        covariates = default_covariates()) {
  not_implemented("11.2")
}

#' Binary progressor: geeglm(progressor ~ exposure + covariates, id = ID, exchangeable) (11.3)
fit_progressor_gee <- function(frame, outcome = "progressor", exposure = "geno_add",
                               covariates = default_covariates()) {
  not_implemented("11.3")
}

#' KL4/TKR: coxph(Surv(time, event) ~ exposure + covariates + frailty(ID)) (11.4)
fit_tkr_cox <- function(frame, time = "time_to_event", event = "event", exposure = "geno_add",
                        covariates = default_covariates()) {
  not_implemented("11.4")
}
```

`r/oaimodels/tests/testthat.R`:
```r
library(testthat)
library(oaimodels)

test_check("oaimodels")
```

`r/oaimodels/tests/testthat/test-read_frame.R`:
```r
test_that("read_frame round-trips Parquet and checks required columns", {
  path <- tempfile(fileext = ".parquet")
  nanoparquet::write_parquet(data.frame(ID = 1000001:1000003, time_years = c(0, 1, 2)), path)
  frame <- read_frame(path, required = c("ID", "time_years"))
  expect_equal(nrow(frame), 3)
  expect_error(read_frame(path, required = "age0"), "missing required columns: age0")
})

test_that("read_frame explains a missing file", {
  expect_error(read_frame(tempfile()), "Frame not found")
})
```

`r/oaimodels/tests/testthat/test-models.R`:
```r
test_that("default_covariates matches the plan's confounder block", {
  expect_equal(default_covariates(2), c("age0", "sex", "bmi0", "PC1", "PC2"))
  expect_equal(default_covariates(0), c("age0", "sex", "bmi0"))
})

test_that("model stubs point at the analysis plan", {
  expect_error(fit_progression_lmm(data.frame(), "y"), "section 11.1")
  expect_error(fit_tkr_cox(data.frame()), "section 11.4")
})
```

`r/step-profile.R`:
```r
# Loaded via R_PROFILE_USER for every R step `oai run` launches from a checkout:
# activates the r/ renv library, then loads oaimodels from source so step scripts
# call oaimodels::fn() exactly as they will against the installed package in the enclave.
local({
  owd <- setwd(Sys.getenv("OAI_R_DIR"))
  on.exit(setwd(owd))
  source("renv/activate.R")
})
pkgload::load_all(file.path(Sys.getenv("OAI_R_DIR"), "oaimodels"), quiet = TRUE, export_all = FALSE)
```

- [ ] **Step 2: Initialize renv and install dependencies**

```bash
Rscript -e 'if (!requireNamespace("renv", quietly = TRUE)) install.packages("renv", repos = "https://cloud.r-project.org")'
cd r && Rscript -e 'renv::init(bare = TRUE, restart = FALSE)'
cd r && Rscript -e 'renv::settings$snapshot.type("all"); renv::install(c("nanoparquet", "lme4", "ordinal", "geepack", "survival", "testthat")); renv::snapshot(prompt = FALSE)'
ls -a r r/renv
```
Expected: `r/.Rprofile`, `r/renv.lock`, `r/renv/activate.R`, `r/renv/settings.json`, `r/renv/.gitignore`; `renv.lock` lists `nanoparquet`, `lme4`, `ordinal`, `geepack`, `survival`, `testthat`, `pkgload`.

- [ ] **Step 3: Run the R tests**

Run: `cd r && Rscript -e 'testthat::test_local("oaimodels", stop_on_failure = TRUE)'`
Expected: `[ FAIL 0 | WARN 0 | SKIP 0 | PASS 7 ]`

- [ ] **Step 4: Write the failing interop tests**

`tests/test_r_interop.py`:
```python
"""Python -> Parquet -> R round trips through oaimodels (skipped when r/ isn't restored)."""

import shutil
import subprocess
import textwrap
from pathlib import Path

import polars as pl
import pytest

from oai.config import load_settings
from oai.manifest import load_analysis
from oai.runner import run_analysis

REPO = Path(__file__).resolve().parents[1]
R_DIR = REPO / "r"


def _r_ready() -> bool:
    if shutil.which("Rscript") is None:
        return False
    probe = subprocess.run(
        ["Rscript", "-e", "library(nanoparquet); library(pkgload)"], cwd=R_DIR, capture_output=True
    )
    return probe.returncode == 0


pytestmark = pytest.mark.skipif(not _r_ready(), reason="R with the restored r/ renv library is unavailable")


def test_polars_frame_reads_in_r(tmp_path):
    path = tmp_path / "frame.parquet"
    pl.DataFrame(
        {"ID": [1000001, 1000002], "time_years": [0.0, 1.02], "sex": ["F", "M"], "age0": [61, None]}
    ).write_parquet(path)
    code = (
        'pkgload::load_all("oaimodels", quiet = TRUE); '
        'f <- read_frame(commandArgs(TRUE)[1], required = c("ID", "time_years")); '
        'cat(nrow(f), sum(f$ID), f$sex[2], is.na(f$age0[2]), sep = "|")'
    )
    out = subprocess.run(["Rscript", "-e", code, str(path)], cwd=R_DIR, capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "2|2000003|M|TRUE"


def test_runner_r_step_sees_oaimodels(tmp_path):
    root = tmp_path / "analyses" / "rstep"
    root.mkdir(parents=True)
    (root / "analysis.toml").write_text(
        'name = "rstep"\n[[steps]]\nid = "m"\nlang = "r"\nstage = "local"\nentry = "m.R"\n'
    )
    (root / "m.R").write_text(
        textwrap.dedent(
            """
            covs <- oaimodels::default_covariates(1)
            writeLines(paste(covs, collapse = ","), file.path(Sys.getenv("OAI_RESULTS_DIR"), "covs.txt"))
            """
        )
    )
    settings = load_settings(
        env={"OAI_WORK_DIR": str(tmp_path / "work"), "OAI_RESULTS_DIR": str(tmp_path / "results")},
        repo_root=REPO,
    )
    run_analysis(load_analysis(root), settings, echo=lambda _: None)
    assert (tmp_path / "results" / "rstep" / "covs.txt").read_text().strip() == "age0,sex,bmi0,PC1"
```

- [ ] **Step 5: Run to verify the runner test fails**

Run: `uv run pytest tests/test_r_interop.py -v`
Expected: `test_polars_frame_reads_in_r` PASS; `test_runner_r_step_sees_oaimodels` FAIL (`there is no package called 'oaimodels'`, non-zero exit → `RunnerError`).

- [ ] **Step 6: Teach the runner about the R step profile**

Modify `step_env` in `src/oai/runner.py` — insert before `return env`:
```python
    r_profile = settings.repo_root / "r" / "step-profile.R" if settings.repo_root else None
    if r_profile is not None and r_profile.is_file():
        env.setdefault("OAI_R_DIR", str(r_profile.parent))
        env.setdefault("R_PROFILE_USER", str(r_profile))
```

- [ ] **Step 7: Run all tests**

Run: `uv run pytest -v`
Expected: all pass, including both interop tests.

- [ ] **Step 8: Commit**

```bash
git add r src/oai/runner.py tests/test_r_interop.py
git status --short r   # confirm r/renv/library is NOT staged
git commit -m "feat: add oaimodels R package with renv and runner integration" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Egress check and `oai check-egress`

**Files:**
- Create: `src/oai/export/__init__.py`, `src/oai/export/egress.py`
- Modify: `config/oai.toml`, `src/oai/cli.py`
- Test: `tests/test_egress.py`

**Interfaces:**
- Produces: `EgressError(OAIError)`; `EgressReport(problems: list[str], manual_review: list[Path], checked: list[Path])` with `.ok`; `small_cell_violations(df: pl.DataFrame, min_cell: int) -> list[str]` (**user-authored**); `check_egress(results_dir: Path, *, min_cell: int, ignore_id_pattern_columns: Sequence[str] = ()) -> EgressReport`.

- [ ] **Step 1: Add egress settings to `config/oai.toml`** (append)

```toml

# Rules applied by `oai check-egress` before anything leaves the enclave.
[egress]
# Smallest non-zero count allowed in outgoing results (small-cell suppression).
min_cell = 11
# Columns whose values legitimately look like 7-digit numbers (e.g. GWAS base-pair positions).
ignore_id_pattern_columns = ["POS", "BP", "position"]
```

- [ ] **Step 2: Write the failing tests**

`tests/test_egress.py`:
```python
import polars as pl
from typer.testing import CliRunner

from oai.cli import app
from oai.export.egress import check_egress, small_cell_violations

FAKE_ID = int("9" + "000123")  # built at runtime; never type the pattern literally


def test_clean_aggregate_results_pass(tmp_path):
    pl.DataFrame({"term": ["time:geno_add"], "estimate": [0.12], "n": [1500]}).write_csv(tmp_path / "coef.csv")
    report = check_egress(tmp_path, min_cell=11)
    assert report.ok, report.problems
    assert len(report.checked) == 1


def test_identifier_columns_fail(tmp_path):
    pl.DataFrame({"src_subject_id": ["x"], "value": [1.0]}).write_csv(tmp_path / "rows.csv")
    assert "identifier column" in check_egress(tmp_path, min_cell=11).problems[0]


def test_participant_id_values_fail_in_nested_parquet(tmp_path):
    (tmp_path / "sub").mkdir()
    pl.DataFrame({"who": [FAKE_ID]}).write_parquet(tmp_path / "sub" / "x.parquet")
    [problem] = check_egress(tmp_path, min_cell=11).problems
    assert "sub/x.parquet" in problem and "participant-ID-like" in problem
    assert str(FAKE_ID) not in problem  # never echo the value itself


def test_position_columns_are_exempt_from_id_pattern(tmp_path):
    pl.DataFrame({"SNP": ["rs1"], "POS": [FAKE_ID], "beta": [0.1]}).write_csv(tmp_path / "gwas.tsv", separator="\t")
    assert check_egress(tmp_path, min_cell=11, ignore_id_pattern_columns=["POS"]).ok
    assert not check_egress(tmp_path, min_cell=11).ok


def test_small_cells_fail(tmp_path):
    pl.DataFrame({"group": ["a", "b", "c"], "n": [0, 4, 40]}).write_csv(tmp_path / "counts.csv")
    [problem] = check_egress(tmp_path, min_cell=11).problems
    assert "'n'" in problem


def test_small_cell_rule_reference_behavior():
    # Reference rule; update if the user-authored rule differs.
    df = pl.DataFrame({"n_cases": [3, 20], "count": [0, 12], "estimate": [1.0, 2.0]})
    assert len(small_cell_violations(df, 11)) == 1


def test_unknown_file_types_fail_closed(tmp_path):
    (tmp_path / "model.rds").write_bytes(b"\x00binary")
    assert "fails closed" in check_egress(tmp_path, min_cell=11).problems[0]


def test_figures_go_to_manual_review(tmp_path):
    (tmp_path / "plot.png").write_bytes(b"\x89PNG")
    report = check_egress(tmp_path, min_cell=11)
    assert report.ok and report.manual_review == [tmp_path / "plot.png"]


def test_text_files_are_scanned(tmp_path):
    (tmp_path / "log.txt").write_text(f"subject {FAKE_ID} dropped\n")
    assert not check_egress(tmp_path, min_cell=11).ok


def test_missing_directory_fails(tmp_path):
    assert not check_egress(tmp_path / "absent", min_cell=11).ok


def test_cli_exit_codes(tmp_path):
    pl.DataFrame({"n": [100]}).write_csv(tmp_path / "ok.csv")
    ok = CliRunner().invoke(app, ["check-egress", str(tmp_path)])
    assert ok.exit_code == 0, ok.output
    pl.DataFrame({"ID": [1]}).write_csv(tmp_path / "bad.csv")
    bad = CliRunner().invoke(app, ["check-egress", str(tmp_path)])
    assert bad.exit_code == 1
    assert "identifier column" in bad.output
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_egress.py -v`
Expected: collection error — `No module named 'oai.export'`

- [ ] **Step 4: Write the implementation (with the reference small-cell rule)**

`src/oai/export/__init__.py`:
```python
"""Moving analyses into, and results out of, the secure enclave."""
```

`src/oai/export/egress.py`:
```python
"""Check that a results directory holds only aggregate outputs before it leaves the enclave.

Fails closed: any file that cannot be positively checked is a problem, except figure
formats, which are listed for manual review.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import polars as pl

from oai.errors import OAIError

ID_COLUMN_NAMES = frozenset({"id", "src_subject_id", "subjid", "subject_id", "sample_id"})
PARTICIPANT_ID = re.compile(r"\b9\d{6}\b")
COUNT_COLUMN = re.compile(r"^(n|count|n_.+|.+_n|.+_count)$", re.IGNORECASE)
TABULAR_SEPARATORS = {".csv": ",", ".tsv": "\t"}
TEXT_SUFFIXES = {".json", ".txt", ".md", ".log"}
MANUAL_REVIEW_SUFFIXES = {".png", ".pdf", ".svg", ".jpg", ".jpeg", ".html"}


class EgressError(OAIError):
    """Egress could not be configured or run."""


@dataclass
class EgressReport:
    problems: list[str] = field(default_factory=list)
    manual_review: list[Path] = field(default_factory=list)
    checked: list[Path] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def small_cell_violations(df: pl.DataFrame, min_cell: int) -> list[str]:
    """Return one message per column that breaks small-cell suppression. USER-AUTHORED RULE.

    Decide which columns are counts and which values are disclosive. Trade-offs:
    - Matching only count-named columns (n, count, n_*, *_n, *_count) misses counts
      hidden in columns like 'cases'; checking every integer column flags years and IDs.
    - Zero is usually safe to release; 1..min_cell-1 usually is not. Some policies
      also suppress complementary cells so a small cell can't be recovered from totals.
    """
    problems = []
    for col in df.columns:
        if not COUNT_COLUMN.match(col) or not df.schema[col].is_numeric():
            continue
        small = df.filter((pl.col(col) > 0) & (pl.col(col) < min_cell)).height
        if small:
            problems.append(f"column {col!r} has {small} cell(s) with 0 < n < {min_cell}")
    return problems


def _frame_problems(df: pl.DataFrame, name: str, *, min_cell: int, ignore: set[str]) -> list[str]:
    problems = []
    for col in df.columns:
        if col.lower() in ID_COLUMN_NAMES:
            problems.append(f"{name}: identifier column {col!r}")
        if col in ignore:
            continue
        values = df.get_column(col).cast(pl.String, strict=False).drop_nulls()
        hits = values.str.contains(PARTICIPANT_ID.pattern).sum()
        if hits:
            problems.append(f"{name}: column {col!r} has {hits} participant-ID-like value(s)")
    problems.extend(f"{name}: {message}" for message in small_cell_violations(df, min_cell))
    return problems


def check_egress(
    results_dir: Path, *, min_cell: int, ignore_id_pattern_columns: Sequence[str] = ()
) -> EgressReport:
    report = EgressReport()
    if not results_dir.is_dir():
        report.problems.append(f"{results_dir}: not a directory")
        return report
    ignore = set(ignore_id_pattern_columns)
    for path in sorted(p for p in results_dir.rglob("*") if p.is_file()):
        rel = path.relative_to(results_dir).as_posix()
        suffix = path.suffix.lower()
        report.checked.append(path)
        try:
            if suffix in TABULAR_SEPARATORS:
                df = pl.read_csv(path, separator=TABULAR_SEPARATORS[suffix], infer_schema_length=10_000)
                report.problems += _frame_problems(df, rel, min_cell=min_cell, ignore=ignore)
            elif suffix == ".parquet":
                report.problems += _frame_problems(pl.read_parquet(path), rel, min_cell=min_cell, ignore=ignore)
            elif suffix in TEXT_SUFFIXES:
                if PARTICIPANT_ID.search(path.read_text(errors="replace")):
                    report.problems.append(f"{rel}: contains participant-ID-like values")
            elif suffix in MANUAL_REVIEW_SUFFIXES:
                report.manual_review.append(path)
            else:
                report.problems.append(f"{rel}: unrecognized file type {suffix or '(none)'}; egress fails closed")
        except (pl.exceptions.PolarsError, OSError) as exc:
            report.problems.append(f"{rel}: could not be read ({type(exc).__name__}); egress fails closed")
    return report
```

Modify `src/oai/cli.py` — add imports and command:
```python
from pathlib import Path

from oai.export.egress import EgressError, check_egress


@app.command("check-egress")
def check_egress_cmd(
    results_dir: Annotated[Path, typer.Argument(help="Directory of results to be released.")],
    min_cell: Annotated[int | None, typer.Option(help="Override [egress] min_cell.")] = None,
) -> None:
    """Verify a results directory holds only aggregate, non-identifying outputs."""
    with user_errors():
        cfg = get_settings().project.get("egress", {})
        threshold = min_cell if min_cell is not None else cfg.get("min_cell")
        if threshold is None:
            raise EgressError("No [egress] min_cell in config/oai.toml and no --min-cell given")
        report = check_egress(
            results_dir,
            min_cell=int(threshold),
            ignore_id_pattern_columns=cfg.get("ignore_id_pattern_columns", []),
        )
    for problem in report.problems:
        typer.secho(f"FAIL   {problem}", err=True, fg=typer.colors.RED)
    for path in report.manual_review:
        typer.echo(f"REVIEW {path}")
    typer.echo(
        f"{len(report.checked)} file(s) checked; {len(report.problems)} problem(s); "
        f"{len(report.manual_review)} need manual review"
    )
    if not report.ok:
        raise typer.Exit(1)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest -v`
Expected: all pass.

- [ ] **Step 6: USER CONTRIBUTION — small-cell rule and threshold**

Pause and invite the user to replace the body of `small_cell_violations` in `src/oai/export/egress.py` (5–10 lines) and to confirm `[egress] min_cell` in `config/oai.toml` against their institution's disclosure policy (11 is a common default, e.g. CMS). If behavior changes, update `test_small_cell_rule_reference_behavior` and `test_small_cells_fail`, then rerun `uv run pytest tests/test_egress.py -v`.

- [ ] **Step 7: Commit**

```bash
git add src/oai/export config/oai.toml src/oai/cli.py tests/test_egress.py
git commit -m "feat: add fail-closed egress check for enclave results" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Export bundle and `oai export`

**Files:**
- Create: `src/oai/export/bundle.py`, `src/oai/export/templates/run.sh`, `src/oai/export/templates/README_ENCLAVE.md`
- Modify: `src/oai/cli.py`
- Test: `tests/test_bundle.py`

**Interfaces:**
- Consumes: `Analysis` (`export`, `languages`, `root`, `name`, `steps`), `Settings` (`repo_root`, `config_path`, `work_dir`), `run_analysis`, `frame_dir`.
- Produces: `ExportError(OAIError)`; `Builders(python_wheel, r_package, python_requirements)` — each `Callable[[Path], None]` writing into the given dir; `default_builders(repo_root) -> Builders`; `git_state(repo_root) -> tuple[str, bool]`; `sha256_file(path) -> str`; `BundleResult(path: Path, manifest: dict)`; `export_analysis(analysis, settings, *, out_dir=None, allow_dirty=False, run_local=True, vendor=False, builders=None, now=None) -> BundleResult`; `VENDOR_HELP: str`.

- [ ] **Step 1: Write the templates**

`src/oai/export/templates/run.sh`:
```bash
#!/usr/bin/env bash
# Run the enclave stage of analysis "@@ANALYSIS@@" from this bundle.
# Needs: python3 >= 3.11, R >= 4.2 with renv (if env/renv.lock exists), sha256sum,
# and OAI_GENO_DIR pointing at the controlled-access genotype directory.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANALYSIS="@@ANALYSIS@@"
cd "$HERE"

: "${OAI_GENO_DIR:?Set OAI_GENO_DIR to the controlled-access genotype directory}"

echo "==> Verifying bundle checksums"
sha256sum --quiet -c SHA256SUMS

echo "==> Python environment"
PIP_OPTS=()
if [ -d vendor/wheels ]; then PIP_OPTS=(--no-index --find-links vendor/wheels); fi
python3 -m venv .venv
.venv/bin/pip install --quiet ${PIP_OPTS[@]+"${PIP_OPTS[@]}"} -r env/requirements.txt
.venv/bin/pip install --quiet ${PIP_OPTS[@]+"${PIP_OPTS[@]}"} --no-deps code/*.whl

if [ -f env/renv.lock ]; then
  echo "==> R packages"
  mkdir -p .rlib
  if [ -d vendor/r ]; then export RENV_CONFIG_REPOS_OVERRIDE="file://$HERE/vendor/r"; fi
  Rscript -e 'renv::restore(project = ".", lockfile = "env/renv.lock", library = ".rlib", prompt = FALSE)'
  R CMD INSTALL --no-test-load --library=.rlib code/oaimodels_*.tar.gz
  export R_LIBS="$HERE/.rlib"
fi

export OAI_CONFIG="$HERE/config/oai.toml"
export OAI_ANALYSES_DIR="$HERE/code/analyses"
export OAI_FRAME_DIR="$HERE/data"
export OAI_WORK_DIR="${OAI_WORK_DIR:-$OAI_GENO_DIR/work}"
export OAI_RESULTS_DIR="${OAI_RESULTS_DIR:-$OAI_GENO_DIR/results}"

echo "==> Running enclave steps"
.venv/bin/oai run "$ANALYSIS" --stage enclave

echo "==> Egress check"
.venv/bin/oai check-egress "$OAI_RESULTS_DIR/$ANALYSIS"
echo "Done. Only files that passed the egress check may leave the enclave."
```

`src/oai/export/templates/README_ENCLAVE.md`:
````markdown
# Enclave bundle: @@ANALYSIS@@

This bundle runs the `enclave` stage of the `@@ANALYSIS@@` analysis next to
controlled-access dbGaP genotype data (GeCKO, phs000955). It contains no genotype data.

## Contents

| Path | What |
|---|---|
| `code/` | `oai` wheel, `oaimodels` R source package, the analysis folder |
| `env/` | `requirements.txt` (hash-pinned), `renv.lock` |
| `data/` | phenotype frame, restricted to the columns declared in `analysis.toml` |
| `config/oai.toml` | project config (visit map, egress rules) |
| `SHA256SUMS`, `MANIFEST.json` | checksums; git commit, row/column counts, timestamp |

## Run

1. Transfer the `.tar.gz` using your institution's approved method.
2. Extract it **inside** `$OAI_GENO_DIR`, so every intermediate lives in the directory destroyed at close-out.
3. `export OAI_GENO_DIR=/secure/path/to/geno` then `bash run.sh`.
4. Only the results directory, and only after `oai check-egress` passes, may leave the enclave. Review figures listed as `REVIEW` by eye.

## Offline enclaves

If the enclave has no internet access, populate `vendor/` on a connected Linux x86_64 machine before transfer:

```bash
# Python wheels
pip download -r env/requirements.txt --platform manylinux2014_x86_64 \
  --python-version 3.11 --only-binary=:all: -d vendor/wheels
# R sources as a local CRAN-like repo (renv honors RENV_CONFIG_REPOS_OVERRIDE)
Rscript -e 'pkgs <- c("renv", names(renv::lockfile_read("env/renv.lock")$Packages));
  dir.create("vendor/r/src/contrib", recursive = TRUE);
  download.packages(pkgs, destdir = "vendor/r/src/contrib", type = "source",
                    repos = "https://cloud.r-project.org");
  tools::write_PACKAGES("vendor/r/src/contrib", type = "source")'
```
`SHA256SUMS` does not need regenerating: it covers only the original bundle files, not `vendor/`.

## Containers (alternative)

Where Apptainer is available, build a `linux/amd64` image on a connected machine
(`docker buildx build --platform linux/amd64 ...` from a `rocker/r-ver` base with Python ≥ 3.11),
convert it with `apptainer build image.sif docker-archive://image.tar`, and run `run.sh` inside it.

## Close-out

At project termination, destroy `$OAI_GENO_DIR` (including this bundle, `.venv`, `.rlib`,
work and results) following your institution's media-sanitization procedure, per the NIH
Security Best Practices for Controlled-Access Data.
````

- [ ] **Step 2: Write the failing tests**

`tests/test_bundle.py`:
```python
import dataclasses
import json
import subprocess
import tarfile
import textwrap
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest
from typer.testing import CliRunner

from oai.cli import app
from oai.config import load_settings
from oai.export.bundle import Builders, ExportError, default_builders, export_analysis, sha256_file
from oai.manifest import ExportSpec, Step, load_analysis

REPO = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)

MANIFEST = textwrap.dedent(
    """
    name = "toy"

    [[steps]]
    id = "frame"
    lang = "python"
    stage = "local"
    entry = "build_frame.py"

    [[steps]]
    id = "models"
    lang = "r"
    stage = "enclave"
    entry = "models.R"
    needs = ["frame"]

    [export]
    frame = "frame.parquet"
    columns = ["ID", "SIDE", "age0"]
    """
)

BUILD_FRAME = textwrap.dedent(
    """
    import os, pathlib
    import polars as pl
    out = pathlib.Path(os.environ["OAI_FRAME_DIR"]) / "frame.parquet"
    pl.DataFrame(
        {"ID": [1000001, 1000002], "SIDE": [1, 2], "age0": [61, 55], "not_exported": ["x", "y"]}
    ).write_parquet(out)
    """
)


def _git(repo, *args):
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=repo, check=True, capture_output=True,
    )


@pytest.fixture
def export_repo(fake_repo):
    root = fake_repo / "analyses" / "toy"
    root.mkdir(parents=True)
    (root / "analysis.toml").write_text(MANIFEST)
    (root / "build_frame.py").write_text(BUILD_FRAME)
    (root / "models.R").write_text('stop("enclave only")\n')
    (fake_repo / "r").mkdir()
    (fake_repo / "r" / "renv.lock").write_text('{"R": {"Version": "4.5.2"}}\n')
    _git(fake_repo, "init", "-q", "-b", "main")
    _git(fake_repo, "add", "-A")
    _git(fake_repo, "commit", "-q", "-m", "init")
    return fake_repo


@pytest.fixture
def settings(export_repo, tmp_path):
    return load_settings(env={"OAI_WORK_DIR": str(tmp_path / "work")}, repo_root=export_repo)


@pytest.fixture
def toy(export_repo):
    return load_analysis(export_repo / "analyses" / "toy")


def fake_builders(calls):
    def wheel(dest):
        calls.append("wheel")
        (dest / "oai_analytics-0.1.0-py3-none-any.whl").write_bytes(b"wheel")

    def rpkg(dest):
        calls.append("r")
        (dest / "oaimodels_0.1.0.tar.gz").write_bytes(b"rpkg")

    def reqs(dest):
        calls.append("reqs")
        (dest / "requirements.txt").write_text("polars==1.30.0\n")

    return Builders(python_wheel=wheel, r_package=rpkg, python_requirements=reqs)


def _extract(tar_path, dest):
    with tarfile.open(tar_path) as tar:
        tar.extractall(dest, filter="data")
    return dest / tar_path.name.removesuffix(".tar.gz")


def test_bundle_contents_and_checksums(toy, settings, tmp_path):
    calls = []
    result = export_analysis(toy, settings, builders=fake_builders(calls), now=NOW)
    assert result.path.name == "toy-20260930T120000Z.tar.gz"
    assert calls == ["wheel", "r", "reqs"]
    root = _extract(result.path, tmp_path / "x")
    for rel in [
        "run.sh", "README_ENCLAVE.md", "MANIFEST.json", "SHA256SUMS", "env/renv.lock",
        "env/requirements.txt", "config/oai.toml", "code/analyses/toy/analysis.toml",
        "code/oai_analytics-0.1.0-py3-none-any.whl", "code/oaimodels_0.1.0.tar.gz", "data/frame.parquet",
    ]:
        assert (root / rel).is_file(), rel
    manifest = json.loads((root / "MANIFEST.json").read_text())
    for rel, digest in manifest["files"].items():
        assert sha256_file(root / rel) == digest
    assert manifest["frame"] == {"file": "data/frame.parquet", "rows": 2, "columns": ["ID", "SIDE", "age0"]}
    assert pl.read_parquet(root / "data" / "frame.parquet").columns == ["ID", "SIDE", "age0"]
    assert manifest["git_dirty"] is False and len(manifest["git_commit"]) == 40


def test_run_script_is_rendered_and_valid_bash(toy, settings, tmp_path):
    result = export_analysis(toy, settings, builders=fake_builders([]), now=NOW)
    run_sh = _extract(result.path, tmp_path / "x") / "run.sh"
    text = run_sh.read_text()
    assert 'ANALYSIS="toy"' in text and "@@" not in text
    assert run_sh.stat().st_mode & 0o111
    subprocess.run(["bash", "-n", str(run_sh)], check=True)


def test_export_is_logged(toy, settings):
    result = export_analysis(toy, settings, builders=fake_builders([]), now=NOW)
    record = json.loads((settings.work_dir / "export_log.jsonl").read_text().splitlines()[-1])
    assert record["analysis"] == "toy"
    assert record["sha256"] == sha256_file(result.path)
    assert record["frame_rows"] == 2


def test_dirty_tree_is_refused(toy, settings, export_repo):
    (export_repo / "notes.md").write_text("uncommitted\n")
    with pytest.raises(ExportError, match="uncommitted"):
        export_analysis(toy, settings, builders=fake_builders([]))


def test_allow_dirty_is_recorded(toy, settings, export_repo):
    (export_repo / "notes.md").write_text("uncommitted\n")
    result = export_analysis(toy, settings, builders=fake_builders([]), allow_dirty=True)
    assert result.manifest["git_dirty"] is True


def test_missing_export_column(toy, settings):
    broken = dataclasses.replace(toy, export=ExportSpec("frame.parquet", ("ID", "nope")))
    with pytest.raises(ExportError, match="nope"):
        export_analysis(broken, settings, builders=fake_builders([]))


def test_analysis_without_export(toy, settings):
    with pytest.raises(ExportError, match=r"no \[export\]"):
        export_analysis(dataclasses.replace(toy, export=None), settings, builders=fake_builders([]))


def test_vendor_flag_explains_offline_procedure(toy, settings):
    with pytest.raises(ExportError, match="pip download"):
        export_analysis(toy, settings, builders=fake_builders([]), vendor=True)


def test_python_only_analysis_skips_r(toy, settings, tmp_path):
    python_only = dataclasses.replace(toy, steps=(Step("frame", "python", "local", "build_frame.py"),))
    calls = []
    result = export_analysis(python_only, settings, builders=fake_builders(calls), now=NOW)
    assert calls == ["wheel", "reqs"]
    assert not (_extract(result.path, tmp_path / "x") / "env" / "renv.lock").exists()


def test_cli_export_unknown_analysis():
    result = CliRunner().invoke(app, ["export", "nope"])
    assert result.exit_code == 1
    assert "Unknown analysis" in result.output


@pytest.mark.slow
def test_real_wheel_ships_templates(tmp_path):
    default_builders(REPO).python_wheel(tmp_path)
    with zipfile.ZipFile(next(tmp_path.glob("*.whl"))) as zf:
        names = zf.namelist()
    assert "oai/export/templates/run.sh" in names
    assert "oai/export/templates/README_ENCLAVE.md" in names
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_bundle.py -v`
Expected: collection error — `No module named 'oai.export.bundle'`

- [ ] **Step 4: Write the implementation**

`src/oai/export/bundle.py`:
```python
"""Build a self-contained, checksummed bundle that runs an analysis's enclave stage.

Only the phenotype columns declared in [export] leave the laptop. Every export is
appended to OAI_WORK_DIR/export_log.jsonl (NIH: "track all copies or extracts").
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any

import polars as pl

from oai import __version__
from oai.config import Settings
from oai.errors import OAIError
from oai.manifest import Analysis
from oai.runner import frame_dir, run_analysis

VENDOR_HELP = (
    "--vendor is not implemented yet. For an offline enclave, populate vendor/ inside the "
    "extracted bundle on a connected Linux x86_64 machine: `pip download -r env/requirements.txt "
    "--platform manylinux2014_x86_64 --python-version 3.11 --only-binary=:all: -d vendor/wheels`, "
    "and see README_ENCLAVE.md ('Offline enclaves') for the R packages."
)


class ExportError(OAIError):
    """The bundle could not be built."""


Builder = Callable[[Path], None]


@dataclass(frozen=True)
class Builders:
    python_wheel: Builder
    r_package: Builder
    python_requirements: Builder


@dataclass(frozen=True)
class BundleResult:
    path: Path
    manifest: dict[str, Any]


def _run(cmd: list[str], cwd: Path) -> None:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise ExportError(f"`{' '.join(cmd)}` failed:\n{proc.stderr.strip()}")


def default_builders(repo_root: Path) -> Builders:
    def python_wheel(dest: Path) -> None:
        _run(["uv", "build", "--wheel", "--out-dir", str(dest)], cwd=repo_root)

    def r_package(dest: Path) -> None:
        _run(["R", "CMD", "build", "--no-build-vignettes", str(repo_root / "r" / "oaimodels")], cwd=dest)

    def python_requirements(dest: Path) -> None:
        _run(
            ["uv", "export", "--format", "requirements-txt", "--no-dev", "--no-emit-project",
             "--frozen", "--output-file", str(dest / "requirements.txt")],
            cwd=repo_root,
        )

    return Builders(python_wheel, r_package, python_requirements)


def git_state(repo_root: Path) -> tuple[str, bool]:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True)
    if head.returncode != 0:
        raise ExportError("Export needs a git checkout with at least one commit")
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo_root, capture_output=True, text=True, check=True
    )
    return head.stdout.strip(), bool(status.stdout.strip())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _render(template: str, analysis: str) -> str:
    text = resources.files("oai.export").joinpath("templates", template).read_text()
    return text.replace("@@ANALYSIS@@", analysis)


def _append_export_log(settings: Settings, tar_path: Path, manifest: dict[str, Any]) -> None:
    record = {
        "bundle": str(tar_path),
        "sha256": sha256_file(tar_path),
        "analysis": manifest["analysis"],
        "created_utc": manifest["created_utc"],
        "git_commit": manifest["git_commit"],
        "frame_rows": manifest["frame"]["rows"],
    }
    settings.work_dir.mkdir(parents=True, exist_ok=True)
    with (settings.work_dir / "export_log.jsonl").open("a") as fh:
        fh.write(json.dumps(record) + "\n")


def export_analysis(
    analysis: Analysis,
    settings: Settings,
    *,
    out_dir: Path | None = None,
    allow_dirty: bool = False,
    run_local: bool = True,
    vendor: bool = False,
    builders: Builders | None = None,
    now: datetime | None = None,
) -> BundleResult:
    if analysis.export is None:
        raise ExportError(f"{analysis.name} has no [export] section; nothing to export")
    if vendor:
        raise ExportError(VENDOR_HELP)
    if settings.repo_root is None or settings.config_path is None:
        raise ExportError("Export must run from a repository checkout with config/oai.toml")
    repo = settings.repo_root
    commit, dirty = git_state(repo)
    if dirty and not allow_dirty:
        raise ExportError("Working tree has uncommitted changes; commit first or pass --allow-dirty")
    builders = builders or default_builders(repo)

    if run_local and "local" in analysis.stages:
        run_analysis(analysis, settings, stage="local")
    frame_path = frame_dir(analysis, settings, os.environ) / analysis.export.frame
    if not frame_path.is_file():
        raise ExportError(f"Frame {frame_path} not found; run the local steps first")
    frame = pl.read_parquet(frame_path)
    missing = [c for c in analysis.export.columns if c not in frame.columns]
    if missing:
        raise ExportError(f"Frame is missing declared export columns: {missing}")
    frame = frame.select(analysis.export.columns)

    stamp = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    bundle_name = f"{analysis.name}-{stamp}"
    out_dir = out_dir or settings.work_dir / "bundles"
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp) / bundle_name
        for sub in ("code", "env", "data", "config"):
            (stage / sub).mkdir(parents=True)
        builders.python_wheel(stage / "code")
        if "r" in analysis.languages:
            builders.r_package(stage / "code")
            shutil.copy2(repo / "r" / "renv.lock", stage / "env" / "renv.lock")
        builders.python_requirements(stage / "env")
        shutil.copytree(
            analysis.root,
            stage / "code" / "analyses" / analysis.name,
            ignore=shutil.ignore_patterns("__pycache__", "*.parquet"),
        )
        shutil.copy2(settings.config_path, stage / "config" / "oai.toml")
        frame.write_parquet(stage / "data" / analysis.export.frame)
        for template, mode in (("run.sh", 0o755), ("README_ENCLAVE.md", 0o644)):
            target = stage / template
            target.write_text(_render(template, analysis.name))
            target.chmod(mode)

        files = sorted(p for p in stage.rglob("*") if p.is_file())
        checksums = {p.relative_to(stage).as_posix(): sha256_file(p) for p in files}
        (stage / "SHA256SUMS").write_text("".join(f"{h}  {rel}\n" for rel, h in checksums.items()))
        manifest: dict[str, Any] = {
            "analysis": analysis.name,
            "created_utc": stamp,
            "git_commit": commit,
            "git_dirty": dirty,
            "oai_version": __version__,
            "frame": {
                "file": f"data/{analysis.export.frame}",
                "rows": frame.height,
                "columns": list(frame.columns),
            },
            "files": checksums,
        }
        (stage / "MANIFEST.json").write_text(json.dumps(manifest, indent=2))
        tar_path = out_dir / f"{bundle_name}.tar.gz"
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(stage, arcname=bundle_name)
    _append_export_log(settings, tar_path, manifest)
    return BundleResult(tar_path, manifest)
```

Modify `src/oai/cli.py` — add import and command:
```python
from oai.export.bundle import export_analysis


@app.command()
def export(
    name: Annotated[str, typer.Argument(help="Analysis with an [export] section.")],
    out: Annotated[Path | None, typer.Option(help="Output directory (default OAI_WORK_DIR/bundles).")] = None,
    allow_dirty: Annotated[bool, typer.Option(help="Export from a tree with uncommitted changes.")] = False,
    skip_local: Annotated[bool, typer.Option(help="Reuse the existing frame; don't rerun local steps.")] = False,
    vendor: Annotated[bool, typer.Option(help="Vendor offline dependencies (not implemented yet).")] = False,
) -> None:
    """Bundle an analysis's enclave stage with its phenotype frame."""
    with user_errors():
        settings = get_settings()
        analysis = find_analysis(name, settings.analyses_dir)
        result = export_analysis(
            analysis, settings, out_dir=out, allow_dirty=allow_dirty, run_local=not skip_local, vendor=vendor
        )
        frame = result.manifest["frame"]
        typer.echo(f"Bundle: {result.path}")
        typer.echo(f"Frame: {frame['rows']} rows x {len(frame['columns'])} columns")
        typer.echo(f"Logged to {settings.work_dir / 'export_log.jsonl'}")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest -v && uv run pytest -m slow -v`
Expected: all pass; the slow test builds a real wheel containing both templates.

- [ ] **Step 6: Commit**

```bash
git add src/oai/export src/oai/cli.py tests/test_bundle.py
git commit -m "feat: add checksummed enclave export bundles" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: Analysis and derivation stubs

**Files:**
- Create: `src/oai/derive/__init__.py`, `src/oai/derive/pase.py`, `src/oai/derive/accel.py`, `src/oai/derive/progression.py`; `analyses/activity_agreement/{analysis.toml,README.md,build_frame.py,agreement.R}`; `analyses/progression_definitions/{analysis.toml,README.md,derive_endpoints.py}`; `analyses/genetics_progression/{analysis.toml,README.md,build_frame.py,models.R}`
- Test: `tests/test_analyses.py`

**Interfaces:**
- Consumes: `load_analysis`, `catalog_for`, `get_settings`.
- Produces: `score_pase(allclinical: pl.DataFrame, visit: str) -> pl.DataFrame`, `valid_wear_days(by_minute: pl.LazyFrame, *, nonwear_minutes: int = 90, min_wear_hours: float = 10.0) -> pl.DataFrame`, `kl_progression(kl_long: pl.DataFrame, *, baseline: str = "V00", followup: str = "V06", exclude_0_to_1: bool = True) -> pl.DataFrame`, `fnih_jsw_progressor(jsw_long: pl.DataFrame, *, threshold_mm: float = 0.7) -> pl.DataFrame` — all raise `NotImplementedError` naming their reference section.

- [ ] **Step 1: Write the failing tests**

`tests/test_analyses.py`:
```python
from pathlib import Path

import polars as pl
import pytest

from oai.catalog import catalog_for
from oai.config import get_settings
from oai.derive.accel import valid_wear_days
from oai.derive.pase import score_pase
from oai.derive.progression import fnih_jsw_progressor, kl_progression
from oai.manifest import load_analysis

REPO = Path(__file__).resolve().parents[1]
ANALYSES = sorted(p.parent.name for p in (REPO / "analyses").glob("*/analysis.toml"))


def test_expected_analyses_exist():
    assert ANALYSES == ["activity_agreement", "genetics_progression", "progression_definitions"]


@pytest.mark.parametrize("name", ANALYSES)
def test_manifest_is_valid(name):
    assert load_analysis(REPO / "analyses" / name).name == name


def test_genetics_exports_an_id_keyed_frame_to_the_enclave():
    a = load_analysis(REPO / "analyses" / "genetics_progression")
    assert a.stages == {"local", "enclave"}
    assert a.export is not None and a.export.columns[0] == "ID"


@pytest.mark.parametrize(
    "call",
    [
        lambda: score_pase(pl.DataFrame(), "V06"),
        lambda: valid_wear_days(pl.LazyFrame()),
        lambda: kl_progression(pl.DataFrame()),
        lambda: fnih_jsw_progressor(pl.DataFrame()),
    ],
)
def test_derive_stubs_point_to_reference_docs(call):
    with pytest.raises(NotImplementedError, match="docs/reference"):
        call()


@pytest.mark.realdata
@pytest.mark.parametrize("name", ANALYSES)
def test_inputs_resolve_against_real_release(name):
    catalog = catalog_for(get_settings().data_dir)
    for spec in load_analysis(REPO / "analyses" / name).inputs:
        assert catalog.resolve_input(spec), spec
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_analyses.py -v`
Expected: collection error — `No module named 'oai.derive'`

- [ ] **Step 3: Write the derivation stubs**

`src/oai/derive/__init__.py`:
```python
"""Derived variables (PASE scores, accelerometer summaries, progression endpoints)."""
```

`src/oai/derive/pase.py`:
```python
"""PASE scoring (activity-agreement plan §3, 'PASE (index self-report)')."""

import polars as pl

REFERENCE = "docs/reference/oai-activity-agreement-analysis-plan.md §3"


def score_pase(allclinical: pl.DataFrame, visit: str) -> pl.DataFrame:
    """Return ID, visit, pase_total, pase_walking from one visit's AllClinical PASE items."""
    raise NotImplementedError(f"score_pase: see {REFERENCE}")
```

`src/oai/derive/accel.py`:
```python
"""ActiGraph GT1M processing (activity-agreement plan §3, 'Accelerometer')."""

import polars as pl

REFERENCE = "docs/reference/oai-activity-agreement-analysis-plan.md §3"


def valid_wear_days(
    by_minute: pl.LazyFrame, *, nonwear_minutes: int = 90, min_wear_hours: float = 10.0
) -> pl.DataFrame:
    """Per-participant valid days: >= min_wear_hours of wear after removing >= nonwear_minutes zero-count runs."""
    raise NotImplementedError(f"valid_wear_days: see {REFERENCE}")
```

`src/oai/derive/progression.py`:
```python
"""Progression endpoints (docs/reference/oai-progression-definition-crosswalk.md)."""

import polars as pl

REFERENCE = "docs/reference/oai-progression-definition-crosswalk.md §1"


def kl_progression(
    kl_long: pl.DataFrame, *, baseline: str = "V00", followup: str = "V06", exclude_0_to_1: bool = True
) -> pl.DataFrame:
    """Knee-level KL progression (>= 1 grade, optionally excluding 0 -> 1) between two visits."""
    raise NotImplementedError(f"kl_progression: see {REFERENCE}")


def fnih_jsw_progressor(jsw_long: pl.DataFrame, *, threshold_mm: float = 0.7) -> pl.DataFrame:
    """FNIH structural progressor: medial minimum JSW loss >= threshold_mm at 24/36/48 months."""
    raise NotImplementedError(f"fnih_jsw_progressor: see {REFERENCE}")
```

- [ ] **Step 4: Write the analysis folders**

`analyses/activity_agreement/analysis.toml`:
```toml
name = "activity_agreement"
description = "Self-reported activity (PASE, 96-mo walking) vs. ActiGraph accelerometry: agreement/validation (Aims 1-3)."

[inputs]
tables = [
    "enrollees",
    "allclinical:00", "allclinical:01", "allclinical:03", "allclinical:05",
    "allclinical:06", "allclinical:10",
    "accelerometry:06", "acceldatabyday:06",
]

[[steps]]
id = "frame"
lang = "python"
stage = "local"
entry = "build_frame.py"

[[steps]]
id = "agreement"
lang = "r"
stage = "local"
entry = "agreement.R"
needs = ["frame"]

[outputs]
aggregate = ["*.csv", "*.png"]
```

`analyses/activity_agreement/build_frame.py`:
```python
"""Build the activity-agreement frame (Samples A-C). Stub."""

import sys

sys.exit(
    "activity_agreement/build_frame.py is a stub: see "
    "docs/reference/oai-activity-agreement-analysis-plan.md §2-4"
)
```

`analyses/activity_agreement/agreement.R`:
```r
# Agreement layers 1-5 (Spearman, Bland-Altman, kappa, ROC, bias predictors). Stub.
stop("activity_agreement/agreement.R is a stub: see docs/reference/oai-activity-agreement-analysis-plan.md section 5")
```

`analyses/activity_agreement/README.md`:
```markdown
# activity_agreement

Agreement between OAI self-reported activity (PASE; 96-month walking-for-exercise item) and the 48-month ActiGraph accelerometer substudy. Plan: [`docs/reference/oai-activity-agreement-analysis-plan.md`](../../docs/reference/oai-activity-agreement-analysis-plan.md) §1–9.

| Step | Stage | Does |
|---|---|---|
| `frame` (`build_frame.py`) | local | Samples A–C; device endpoints (90-min non-wear, ≥10 h valid day); PASE total + walking subscore |
| `agreement` (`agreement.R`) | local | Spearman + deattenuation, Bland–Altman, κ, ROC cutpoint, bias regression |

Status: stub.
```

`analyses/progression_definitions/analysis.toml`:
```toml
name = "progression_definitions"
description = "Derive radiographic, symptomatic and hard-endpoint progression definitions per the crosswalk."

[inputs]
tables = ["enrollees", "kxr_sq_bu:*", "kxr_qjsw_duryea:*", "allclinical:*", "outcomes:99"]

[[steps]]
id = "endpoints"
lang = "python"
stage = "local"
entry = "derive_endpoints.py"

[outputs]
aggregate = ["*.csv"]
```

`analyses/progression_definitions/derive_endpoints.py`:
```python
"""Derive knee-level progression endpoints (KL, OARSI JSN, FNIH JSW, WOMAC, TKR). Stub."""

import sys

sys.exit(
    "progression_definitions/derive_endpoints.py is a stub: see "
    "docs/reference/oai-progression-definition-crosswalk.md"
)
```

`analyses/progression_definitions/README.md`:
```markdown
# progression_definitions

Knee-level progression endpoints from the [crosswalk](../../docs/reference/oai-progression-definition-crosswalk.md): KL ≥ 1 grade, incident ROA, OARSI JSN, FNIH medial minimum-JSW loss ≥ 0.7 mm, AKOA, WOMAC-based and TKR (Outcomes99). Outputs feed `genetics_progression` and future analyses; only per-definition prevalence tables are aggregate outputs.

Status: stub.
```

`analyses/genetics_progression/analysis.toml`:
```toml
name = "genetics_progression"
description = "Per-genotype progression models (dbGaP GeCKO phs000955): candidate loci, PRS, LSKAT."

[inputs]
tables = ["enrollees", "allclinical:00", "kxr_sq_bu:*", "kxr_qjsw_duryea:*", "outcomes:99"]

[[steps]]
id = "frame"
lang = "python"
stage = "local"
entry = "build_frame.py"

[[steps]]
id = "models"
lang = "r"
stage = "enclave"
entry = "models.R"
needs = ["frame"]

[export]
frame = "frame.parquet"
columns = ["ID", "SIDE", "visit", "time_years", "age0", "sex", "bmi0"]

[outputs]
aggregate = ["*.csv", "*.png"]
```

`analyses/genetics_progression/build_frame.py`:
```python
"""Build the knee x visit phenotype frame exported to the enclave. Stub."""

import sys

sys.exit(
    "genetics_progression/build_frame.py is a stub: see "
    "docs/reference/oai-activity-agreement-analysis-plan.md §10-12"
)
```

`analyses/genetics_progression/models.R`:
```r
# Enclave stage: join genotype dosages (OAI_GENO_DIR) via the dbGaP bridge file, then
# fit oaimodels::fit_progression_lmm / fit_kl_clmm / fit_progressor_gee / fit_tkr_cox. Stub.
stop("genetics_progression/models.R is a stub: see docs/reference/oai-activity-agreement-analysis-plan.md section 11")
```

`analyses/genetics_progression/README.md`:
```markdown
# genetics_progression

Per-genotype progression analysis (plan §10–12). Genotypes are controlled-access (dbGaP GeCKO, phs000955) and never leave the enclave.

| Step | Stage | Does |
|---|---|---|
| `frame` (`build_frame.py`) | local | Knee × visit phenotype frame: `ID, SIDE, visit, time_years, age0, sex, bmi0` (+ outcomes as they are implemented) |
| `models` (`models.R`) | enclave | Bridge-file join to genotype dosages; §11 models; egress-checked aggregate tables |

```bash
oai export genetics_progression   # on the laptop -> OAI_WORK_DIR/bundles/*.tar.gz
bash run.sh                       # in the enclave, inside $OAI_GENO_DIR
```

Open question: dbGaP lists the genotypes as hg37; the plan assumed hg18 + liftover. Confirm on receipt.

Status: stub.
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest -v && uv run pytest -m realdata tests/test_analyses.py -v && uv run oai analyses`
Expected: all pass; `oai analyses` prints the three analyses with `[local]`, `[local]`, `[enclave,local]`.

- [ ] **Step 6: Commit**

```bash
git add src/oai/derive analyses tests/test_analyses.py
git commit -m "feat: add analysis manifests and derivation stubs" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: README and CI

**Files:**
- Modify: `README.md`
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Write the README**

`README.md`:
````markdown
# oai-analytics

An analysis suite for [Osteoarthritis Initiative](https://nda.nih.gov/oai) (OAI) data. Python loads and derives; R fits models. Analyses that need controlled-access genotypes (dbGaP GeCKO, [phs000955](https://www.ncbi.nlm.nih.gov/projects/gap/cgi-bin/study.cgi?study_id=phs000955.v1.p1)) are exported as self-contained bundles that run inside a NIST SP 800-171–compliant enclave. Only egress-checked aggregate results come back out.

> **No data lives in this repository.** OAI phenotype data (NDA) and genotype data (dbGaP) are covered by data-use agreements. Source data, derived frames, caches and bundles all live outside the repo. A pre-commit hook and CI block anything that looks like participant data.

## Setup

Requirements: [uv](https://docs.astral.sh/uv/), git, and R ≥ 4.2 for model steps.

```bash
uv sync
uv run pre-commit install
cp .env.example .env                  # set OAI_DATA_DIR and OAI_WORK_DIR
(cd r && Rscript -e 'renv::restore()')
uv run oai catalog                    # sanity check: lists the tables in your release
```

## Configuration

Settings resolve in this order: environment → `.env` → `[paths]` in `config/oai.toml` → error.

| Variable | Meaning |
|---|---|
| `OAI_DATA_DIR` | Raw OAI release (pipe-delimited `.txt`), read-only |
| `OAI_WORK_DIR` | Parquet cache, derived frames, bundles, export log. **Must be outside the repo.** |
| `OAI_RESULTS_DIR` | Aggregate outputs (default `$OAI_WORK_DIR/results`) |
| `OAI_GENO_DIR` | Enclave only. Genotypes and everything derived from them. Destroyed at close-out. |

`config/oai.toml` holds the visit-code map and the egress rules.

## Commands

| Command | Does |
|---|---|
| `oai catalog` | List tables × visits found in `OAI_DATA_DIR` |
| `oai analyses` | List analyses and validate their `analysis.toml` |
| `oai run NAME [--stage local\|enclave] [--step ID]` | Run an analysis's steps in order |
| `oai export NAME` | Build an enclave bundle (`OAI_WORK_DIR/bundles/NAME-<utc>.tar.gz`) |
| `oai check-egress DIR` | Fail unless `DIR` holds only aggregate, non-identifying outputs |

## Python API

```python
from oai.loader import read_table, codebook
from oai.visits import to_long, time_years

kxr = read_table("kxr_sq_bu", "00", columns=["ID", "SIDE", "V00XRKL"])  # typed polars frame
codebook("kxr_sq_bu", "00").labels["SIDE"]                               # {'1': 'Right', '2': 'Left'}
long = time_years(to_long(read_table("allclinical", "03")))              # ID, visit, ..., time_years
```

Coded cells (`1: Right`) load as their code, with labels in the codebook. Missing codes (`.: Missing Form/…`) are resolved by `oai.loader.resolve_missing`. `V##` is **not** elapsed months (V06 = 48 mo), so always use `oai.visits`.

## Analyses

| Analysis | Runs | Reference |
|---|---|---|
| `activity_agreement` | local | [analysis plan §1–9](docs/reference/oai-activity-agreement-analysis-plan.md) |
| `progression_definitions` | local | [crosswalk](docs/reference/oai-progression-definition-crosswalk.md) |
| `genetics_progression` | local → enclave | [analysis plan §10–12](docs/reference/oai-activity-agreement-analysis-plan.md) |

Each folder's `analysis.toml` declares its input tables, ordered steps (`lang = python|r`, `stage = local|enclave`), the columns it exports and its aggregate outputs.

## Enclave workflow

1. `oai export genetics_progression` runs the local steps and packages code, lockfiles, the column-restricted frame, `run.sh` and checksums. The export is appended to `OAI_WORK_DIR/export_log.jsonl`.
2. Move the tarball with your institution's approved transfer method and extract it **inside** `$OAI_GENO_DIR`.
3. `bash run.sh` verifies checksums, installs, runs the `enclave` steps, then runs `oai check-egress`.
4. Only results that pass the egress check leave the enclave.
5. At close-out, destroy `$OAI_GENO_DIR`.

Each bundle's `README_ENCLAVE.md` covers offline installation and containers.

## Development

```bash
uv run pytest                    # unit tests on synthetic fixtures
uv run pytest -m realdata        # smoke tests against your OAI_DATA_DIR
uv run pytest -m slow            # builds a real wheel
(cd r && Rscript -e 'testthat::test_local("oaimodels")')
uv run python scripts/check_no_data.py
```

## Repository layout

```
config/oai.toml      visit map, egress rules
src/oai/             Python package (catalog, loader, visits, manifest, runner, export/)
r/                   renv project + oaimodels R package
analyses/<name>/     analysis.toml + step scripts
docs/reference/      source documents (.docx) with Markdown copies
scripts/             leak guard, docx→md converter
tests/               pytest (synthetic fixtures only)
```

## Data use

You need your own approved access to OAI (NIMH Data Archive) and, for the genetic arm, dbGaP phs000955. Follow the acknowledgment and publication requirements in your data use certifications, and cite the accession numbers.

## License

MIT. See [LICENSE](LICENSE).
````

- [ ] **Step 2: Write CI**

`.github/workflows/ci.yml`:
```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  python:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.11", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
          python-version: ${{ matrix.python-version }}
      - run: uv sync --locked
      - run: uv run ruff check
      - run: uv run ruff format --check
      - run: uv run python scripts/check_no_data.py
      - run: uv run pytest

  r:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: r
    steps:
      - uses: actions/checkout@v4
      - uses: r-lib/actions/setup-r@v2
        with:
          r-version: "4.5.2"
          use-public-rspm: true
      - uses: r-lib/actions/setup-renv@v2
        with:
          working-directory: r
      - run: Rscript -e 'testthat::test_local("oaimodels", stop_on_failure = TRUE)'
```

- [ ] **Step 3: Verify locally**

Run: `uv run ruff check && uv run ruff format --check && uv run python scripts/check_no_data.py && uv run pytest && (cd r && Rscript -e 'testthat::test_local("oaimodels", stop_on_failure = TRUE)')`
Expected: every command exits 0.

- [ ] **Step 4: Commit**

```bash
git add README.md .github/workflows/ci.yml
git commit -m "docs: add README and CI workflow" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 15: Final verification and publish to GitHub

- [ ] **Step 1: Full verification**

Run:
```bash
uv run pytest && uv run pytest -m realdata && uv run pytest -m slow
(cd r && Rscript -e 'testthat::test_local("oaimodels", stop_on_failure = TRUE)')
uv run python scripts/check_no_data.py
git status --short
```
Expected: all pass; `git status` shows only untracked `.env`-free output (`.env` is ignored).

- [ ] **Step 2: Audit history for data**

Run:
```bash
git log --all --name-only --pretty=format: | sort -u | grep -Ei '\.(parquet|feather|sas7bdat|rds|rdata|xpt|sav|dta|txt|csv)$'
```
Expected: only `scripts/leak_allowlist.txt` and `tests/fixtures/oai/*.txt`. Anything else: stop and ask the user.

- [ ] **Step 3: Create the public repo and push**

```bash
gh repo create Spiewart/oai-analytics --public --source=. --remote=origin \
  --description "Analytic suite for Osteoarthritis Initiative (OAI) data: local phenotype analyses + exportable enclave bundles for dbGaP genotypes" \
  --push
gh repo view Spiewart/oai-analytics --json url,visibility
```
Expected: URL printed; `"visibility": "PUBLIC"`.

- [ ] **Step 4: Check the first CI run once**

Run: `gh run list --repo Spiewart/oai-analytics --limit 2`
Expected: CI run listed (queued, in progress or completed). Report its URL/status to the user; do not poll.
