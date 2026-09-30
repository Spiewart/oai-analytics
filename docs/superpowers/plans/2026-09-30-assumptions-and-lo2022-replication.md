# Assumptions Framework + Lo 2022 Replication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-analysis assumptions framework (TOML ledger, variants, `--set` overrides, resolved values saved with every run) and use it to replicate Lo et al. 2022 (walking for exercise and knee OA progression) end to end, graded against the paper's published numbers.

**Architecture:** `oai.assumptions` parses `analyses/<name>/assumptions.toml` and resolves a variant plus overrides into `assumptions.resolved.json`, which the runner writes into per-label frame and results folders and exposes to Python (`current()`) and R (`oaimodels::assumptions()`). Reusable knee-level derivations live in `oai.derive.knee`; generic grading lives in `oai.replication`. The analysis `analyses/lo2022_walking/` has three steps: Python cohort + descriptives, R GEE models, Python comparison. Each step emits `metrics_*.csv`, which `compare.py` grades against `published.toml`.

**Tech Stack:** Python ≥ 3.11 (uv, polars, typer, pytest), R (renv, geepack, jsonlite, nanoparquet, testthat).

**Spec:** `docs/superpowers/specs/2026-09-30-assumptions-and-lo2022-replication-design.md`

## Global Constraints

- Everything in `docs/superpowers/plans/2026-09-30-oai-analytics-scaffold.md` Global Constraints still applies (no data in git; fixture IDs 1000001–1000010; `OAIError` subclasses for user errors; commit trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; work on `main`).
- Knee frames are keyed on `ID` (Int64) and `SIDE` (`"R"`/`"L"`; release codes 1 = Right, 2 = Left).
- Release column names are looked up case-insensitively (`find_col`): the release mixes `READPRJ`/`readprj` and `ID`/`id`.
- Assumption values are TOML scalars, arrays or inline tables. Dates are strings (`"2012-09-12"`), never TOML dates, because JSON can't serialize those.
- Run labels: `default`, `<variant>`, or `<base>+custom-<8 hex>`. Frames go to `OAI_WORK_DIR/<analysis>/<label>/` and results to `<results_dir>/<analysis>/<label>/`. An explicitly set `OAI_FRAME_DIR` is used as-is.
- Replication results (flow counts, tables, comparison) are aggregate but come from DUA data. They stay in `OAI_RESULTS_DIR`, outside the repo, and are reported in chat, not committed.
- The new synthetic release lives in `tests/fixtures/oai_knee/`. The existing `tests/fixtures/oai/` must not change (its tests assert its exact contents).
- Published targets are copied verbatim from the paper and Supplementary Tables 1–3 (bold = significant).

## Review Focus

1. **A knee replaced during follow-up with no follow-up X-ray reading** must stay in the cohort and count as structurally worsened when `outcomes.replacement_is_structural_worsening` is true. Otherwise the paper's 77 replaced knees vanish. → Task 8 `test_replaced_knee_without_reading_is_included`.
2. **A blank baseline frequent-pain answer** must exclude that knee from both pain-outcome denominators, not count it as "no pain". → Task 8 `test_blank_baseline_pain_is_excluded_from_pain_outcomes`.
3. **Running two variants in succession** must not overwrite each other's frames or results. → Task 2 `test_variants_write_to_separate_label_directories`.
4. **An unknown or mistyped `--set` key or variant** must fail before any step runs. → Task 2 `test_bad_override_fails_before_any_step_runs`.
5. **A published OR whose CI touches 1.0 after rounding (e.g. "0.6–1.0", significant)** must be graded by the stored `sig` flag, not by re-deriving significance from the rounded bounds. → Task 11 `test_or_significance_uses_published_flag`.

## File Map

| Path | Responsibility | Task |
|---|---|---|
| `src/oai/assumptions.py` | Parse, validate, resolve, ledger render, `current()` | 1, 3 |
| `src/oai/runner.py`, `src/oai/cli.py`, `src/oai/export/bundle.py` | Labels, env, `--variant`/`--set`, `oai assumptions` | 2, 3 |
| `docs/assumptions.md` | Framework guide | 3 |
| `r/oaimodels/{DESCRIPTION,NAMESPACE,R/assumptions.R,tests/testthat/test-assumptions.R}` | R access to resolved assumptions | 4 |
| `tests/fixtures/oai_knee/*.txt` | Synthetic release for knee derivations and the replication | 5 |
| `src/oai/derive/knee.py` | `find_col`, `xray_readings`, `with_fallback`, `frequent_knee_pain`, `visit_days`, `knee_replacement`, `knee_alignment` | 5, 6 |
| `analyses/lo2022_walking/{analysis.toml,assumptions.toml,ASSUMPTIONS.md,published.toml,README.md}` | Analysis definition and targets | 7 |
| `analyses/lo2022_walking/lo2022.py`, `build_frame.py` | Cohort, exposure, outcomes, Table 1/3, metrics | 8, 9 |
| `analyses/lo2022_walking/models.R` | GEE Table 2 | 10 |
| `src/oai/replication.py`, `analyses/lo2022_walking/compare.py` | Graded comparison | 11 |
| `README.md` | Command docs | 3, 12 |

---

### Task 1: Assumptions core

**Files:**
- Create: `src/oai/assumptions.py`
- Test: `tests/test_assumptions.py`

**Interfaces:**
- Produces:
  - `AssumptionsError(OAIError)`; `ASSUMPTIONS_FILE = "assumptions.toml"`, `RESOLVED_FILE = "assumptions.resolved.json"`, `LEDGER_FILE = "ASSUMPTIONS.md"`, `STATUSES = ("confirmed", "assumed", "open")`, `DEFAULT_LABEL = "default"`.
  - `Assumption(key, value, status, source, rationale="", alternatives=())`; `Variant(name, description, set)`.
  - `Assumptions(path, items, variants)` with `.resolve(analysis, variant=None, overrides=None) -> Resolved`.
  - `Resolved(analysis, label, variant, overrides, values, origins, items)`: `[key]`, `.to_json()`, `.write(dir) -> Path`, `Resolved.read(path)`.
  - `load_assumptions(analysis_root) -> Assumptions` (empty `Assumptions(path=None)` when the file is absent); `parse_override("k=v") -> (key, value)`; `current() -> Resolved`.

- [ ] **Step 1: Write the failing tests**

`tests/test_assumptions.py`:
```python
import json
import textwrap

import pytest

from oai.assumptions import (
    AssumptionsError,
    Resolved,
    current,
    load_assumptions,
    parse_override,
)

TOML = textwrap.dedent(
    """
    [cohort.min_age]
    value = 50
    status = "confirmed"
    source = "p.1661"

    [cohort.survey_start]
    value = "2012-09-12"
    status = "assumed"
    source = "p.1662"
    rationale = "visit date cutoff"
    alternatives = ["none"]

    [model.corstr]
    value = "exchangeable"
    status = "open"
    source = "not stated"

    [alignment.varus_max]
    value = -2.0
    status = "confirmed"
    source = "p.1662"

    [variants.indep]
    description = "independence working correlation"
    set = { "model.corstr" = "independence" }
    """
)


def write(tmp_path, text=TOML):
    root = tmp_path / "demo"
    root.mkdir(exist_ok=True)
    (root / "assumptions.toml").write_text(text)
    return root


def test_parses_dotted_keys_and_variants(tmp_path):
    a = load_assumptions(write(tmp_path))
    assert sorted(a.items) == ["alignment.varus_max", "cohort.min_age", "cohort.survey_start", "model.corstr"]
    assert a.items["cohort.survey_start"].rationale == "visit date cutoff"
    assert a.items["cohort.survey_start"].alternatives == ("none",)
    assert a.variants["indep"].set == {"model.corstr": "independence"}


def test_missing_file_gives_empty_assumptions(tmp_path):
    a = load_assumptions(tmp_path)
    assert a.path is None and not a.items
    assert a.resolve("demo").label == "default"


def test_resolve_default_variant_and_overrides(tmp_path):
    a = load_assumptions(write(tmp_path))
    r = a.resolve("demo")
    assert r.label == "default" and r["model.corstr"] == "exchangeable"
    r = a.resolve("demo", "indep")
    assert r.label == "indep" and r["model.corstr"] == "independence"
    assert r.origins["model.corstr"] == "variant"
    r = a.resolve("demo", None, {"cohort.min_age": 45})
    assert r.label.startswith("default+custom-") and len(r.label) == len("default+custom-") + 8
    assert r["cohort.min_age"] == 45 and r.origins["cohort.min_age"] == "override"


def test_int_is_accepted_for_float_but_not_the_reverse(tmp_path):
    a = load_assumptions(write(tmp_path))
    assert a.resolve("demo", None, {"alignment.varus_max": -3})["alignment.varus_max"] == -3
    with pytest.raises(AssumptionsError, match="expects int"):
        a.resolve("demo", None, {"cohort.min_age": 45.5})


@pytest.mark.parametrize(
    "overrides, variant, message",
    [
        ({"nope.key": 1}, None, "unknown assumption"),
        ({"cohort.min_age": "fifty"}, None, "expects int"),
        ({}, "missing", "unknown variant"),
    ],
)
def test_bad_resolutions(tmp_path, overrides, variant, message):
    with pytest.raises(AssumptionsError, match=message):
        load_assumptions(write(tmp_path)).resolve("demo", variant, overrides)


@pytest.mark.parametrize(
    "old, new, message",
    [
        ('status = "open"', 'status = "maybe"', "status must be one of"),
        ('source = "not stated"', 'source = ""', "'source' is required"),
        ('source = "not stated"', 'source = "x"\nnotes = "y"', "unknown field"),
        ('"model.corstr" = "independence"', '"model.nope" = 1', "unknown assumption"),
        ('"model.corstr" = "independence"', '"model.corstr" = 3', "expects str"),
    ],
)
def test_invalid_files(tmp_path, old, new, message):
    assert old in TOML
    with pytest.raises(AssumptionsError, match=message):
        load_assumptions(write(tmp_path, TOML.replace(old, new)))


def test_invalid_toml(tmp_path):
    with pytest.raises(AssumptionsError, match="invalid TOML"):
        load_assumptions(write(tmp_path, "[x"))


@pytest.mark.parametrize(
    "text, expected",
    [
        ("model.corstr=independence", ("model.corstr", "independence")),
        ('model.corstr="independence"', ("model.corstr", "independence")),
        ("cohort.min_age=45", ("cohort.min_age", 45)),
        ("flag=true", ("flag", True)),
        ('visits=["06", "05"]', ("visits", ["06", "05"])),
    ],
)
def test_parse_override(text, expected):
    assert parse_override(text) == expected


def test_parse_override_requires_equals():
    with pytest.raises(AssumptionsError, match="key=value"):
        parse_override("model.corstr")


def test_resolved_round_trips_through_json_and_current(tmp_path, monkeypatch):
    r = load_assumptions(write(tmp_path)).resolve("demo", "indep")
    path = r.write(tmp_path / "out")
    data = json.loads(path.read_text())
    assert data["label"] == "indep"
    assert data["assumptions"]["model.corstr"] == {
        "value": "independence",
        "status": "open",
        "source": "not stated",
        "origin": "variant",
    }
    monkeypatch.setenv("OAI_ASSUMPTIONS", str(path))
    again = current()
    assert isinstance(again, Resolved) and again["model.corstr"] == "independence"


def test_current_requires_env(monkeypatch):
    monkeypatch.delenv("OAI_ASSUMPTIONS", raising=False)
    with pytest.raises(AssumptionsError, match="oai run"):
        current()


def test_unknown_key_lookup_is_a_user_error(tmp_path):
    with pytest.raises(AssumptionsError, match="no assumption"):
        load_assumptions(write(tmp_path)).resolve("demo")["nope"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_assumptions.py -q`
Expected: collection error — `No module named 'oai.assumptions'`

- [ ] **Step 3: Write the implementation**

`src/oai/assumptions.py`:
```python
"""Per-analysis assumptions: a documented, configurable ledger of analytic choices.

Each analysis may keep `assumptions.toml` next to its `analysis.toml`. An assumption is
any table with a `value`; its key is the dotted table path (e.g. "cohort.min_age").
`[variants.<name>]` tables name override sets for sensitivity analyses. The runner
resolves a variant plus `--set` overrides into `assumptions.resolved.json`, which steps
read with `current()` (Python) or `oaimodels::assumptions()` (R). See docs/assumptions.md.
"""

from __future__ import annotations

import hashlib
import json
import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from oai.errors import OAIError

ASSUMPTIONS_FILE = "assumptions.toml"
RESOLVED_FILE = "assumptions.resolved.json"
LEDGER_FILE = "ASSUMPTIONS.md"
STATUSES = ("confirmed", "assumed", "open")
DEFAULT_LABEL = "default"
_FIELDS = {"value", "status", "source", "rationale", "alternatives"}


class AssumptionsError(OAIError):
    """assumptions.toml is invalid, or a variant/override does not fit it."""


@dataclass(frozen=True)
class Assumption:
    key: str
    value: Any
    status: str
    source: str
    rationale: str = ""
    alternatives: tuple[Any, ...] = ()


@dataclass(frozen=True)
class Variant:
    name: str
    description: str
    set: Mapping[str, Any]


@dataclass(frozen=True)
class Resolved:
    analysis: str
    label: str
    variant: str | None
    overrides: Mapping[str, Any]
    values: Mapping[str, Any]
    origins: Mapping[str, str]
    items: Mapping[str, Assumption]

    def __getitem__(self, key: str) -> Any:
        try:
            return self.values[key]
        except KeyError:
            raise AssumptionsError(f"{self.analysis}: no assumption {key!r}") from None

    def to_json(self) -> dict[str, Any]:
        return {
            "analysis": self.analysis,
            "label": self.label,
            "variant": self.variant,
            "overrides": dict(self.overrides),
            "assumptions": {
                key: {
                    "value": self.values[key],
                    "status": item.status,
                    "source": item.source,
                    "origin": self.origins[key],
                }
                for key, item in self.items.items()
            },
        }

    def write(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / RESOLVED_FILE
        path.write_text(json.dumps(self.to_json(), indent=2))
        return path

    @classmethod
    def read(cls, path: Path) -> Resolved:
        data = json.loads(path.read_text())
        entries = data["assumptions"]
        return cls(
            analysis=data["analysis"],
            label=data["label"],
            variant=data["variant"],
            overrides=data["overrides"],
            values={key: e["value"] for key, e in entries.items()},
            origins={key: e["origin"] for key, e in entries.items()},
            items={key: Assumption(key, e["value"], e["status"], e["source"]) for key, e in entries.items()},
        )


def _same_type(default: Any, value: Any) -> bool:
    if isinstance(default, bool) or isinstance(value, bool):
        return isinstance(default, bool) and isinstance(value, bool)
    if isinstance(default, float):
        return isinstance(value, (int, float))
    return type(default) is type(value)


@dataclass(frozen=True)
class Assumptions:
    path: Path | None
    items: Mapping[str, Assumption] = field(default_factory=dict)
    variants: Mapping[str, Variant] = field(default_factory=dict)

    def check(self, key: str, value: Any, where: str) -> None:
        if key not in self.items:
            raise AssumptionsError(f"{where}: unknown assumption {key!r}")
        default = self.items[key].value
        if not _same_type(default, value):
            raise AssumptionsError(
                f"{where}: {key} expects {type(default).__name__}, got {type(value).__name__} ({value!r})"
            )

    def resolve(
        self, analysis: str, variant: str | None = None, overrides: Mapping[str, Any] | None = None
    ) -> Resolved:
        overrides = dict(overrides or {})
        values = {key: item.value for key, item in self.items.items()}
        origins = dict.fromkeys(values, "default")
        if variant is not None:
            if variant not in self.variants:
                available = ", ".join(sorted(self.variants)) or "(none)"
                raise AssumptionsError(f"{analysis}: unknown variant {variant!r}; available: {available}")
            for key, value in self.variants[variant].set.items():
                values[key], origins[key] = value, "variant"
        for key, value in overrides.items():
            self.check(key, value, f"--set {key}")
            values[key], origins[key] = value, "override"
        label = variant or DEFAULT_LABEL
        if overrides:
            digest = hashlib.sha256(json.dumps(overrides, sort_keys=True).encode()).hexdigest()[:8]
            label = f"{label}+custom-{digest}"
        return Resolved(analysis, label, variant, overrides, values, origins, self.items)


def _parse_item(key: str, entry: dict[str, Any], where: Path) -> Assumption:
    unknown = set(entry) - _FIELDS
    if unknown:
        raise AssumptionsError(f"{where}: {key}: unknown field(s) {sorted(unknown)}")
    if entry.get("status") not in STATUSES:
        raise AssumptionsError(f"{where}: {key}: status must be one of {', '.join(STATUSES)}")
    source = entry.get("source")
    if not isinstance(source, str) or not source.strip():
        raise AssumptionsError(f"{where}: {key}: 'source' is required")
    return Assumption(
        key,
        entry["value"],
        entry["status"],
        source,
        entry.get("rationale", ""),
        tuple(entry.get("alternatives", [])),
    )


def _walk(table: dict[str, Any], prefix: str, where: Path, out: dict[str, Assumption]) -> None:
    for name, entry in table.items():
        key = f"{prefix}.{name}" if prefix else name
        if not isinstance(entry, dict):
            raise AssumptionsError(f"{where}: {key!r} must be a table with value, status and source")
        if "value" in entry:
            out[key] = _parse_item(key, entry, where)
        else:
            _walk(entry, key, where, out)


def load_assumptions(analysis_root: Path) -> Assumptions:
    path = analysis_root / ASSUMPTIONS_FILE
    if not path.is_file():
        return Assumptions(path=None)
    try:
        data = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as exc:
        raise AssumptionsError(f"{path}: invalid TOML: {exc}") from None
    raw_variants = data.pop("variants", {})
    items: dict[str, Assumption] = {}
    _walk(data, "", path, items)
    base = Assumptions(path=path, items=items)
    variants: dict[str, Variant] = {}
    for name, spec in raw_variants.items():
        if not isinstance(spec, dict) or not isinstance(spec.get("set"), dict):
            raise AssumptionsError(f"{path}: variant {name!r} needs a 'set' table")
        for key, value in spec["set"].items():
            base.check(key, value, f"{path}: variant {name!r}")
        variants[name] = Variant(name, spec.get("description", ""), spec["set"])
    return Assumptions(path=path, items=items, variants=variants)


def parse_override(text: str) -> tuple[str, Any]:
    """Parse `key=value`; the value is a TOML literal (7, true, "x", [1, 2]) or a bare string."""
    key, sep, raw = text.partition("=")
    if not sep or not key.strip():
        raise AssumptionsError(f"--set expects key=value, got {text!r}")
    try:
        value = tomllib.loads(f"v = {raw.strip()}")["v"]
    except tomllib.TOMLDecodeError:
        value = raw.strip()
    return key.strip(), value


def current() -> Resolved:
    """The resolved assumptions of the running step (set by `oai run`)."""
    path = os.environ.get("OAI_ASSUMPTIONS")
    if not path:
        raise AssumptionsError("OAI_ASSUMPTIONS is not set; run this step via `oai run`")
    return Resolved.read(Path(path))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run ruff format -q . && uv run ruff check --fix -q; uv run pytest tests/test_assumptions.py -q`
Expected: all pass (22 tests).

- [ ] **Step 5: Commit**

```bash
git add src/oai/assumptions.py tests/test_assumptions.py
git commit -m "feat: add per-analysis assumptions (parse, validate, resolve)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Runner, CLI and export integration

**Files:**
- Modify: `src/oai/runner.py`, `src/oai/cli.py`, `src/oai/export/bundle.py`
- Test: modify `tests/test_runner.py` and `tests/test_r_interop.py`; add tests to `tests/test_runner.py`

**Interfaces:**
- Consumes: `load_assumptions`, `Resolved`, `DEFAULT_LABEL`, `parse_override` (Task 1).
- Produces:
  - `frame_dir(analysis, settings, env, label=DEFAULT_LABEL) -> Path`
  - `resolve_assumptions(analysis, variant=None, overrides=None) -> Resolved`
  - `step_env(analysis, settings, base_env=None, *, resolved=None) -> dict[str, str]`, which adds `OAI_ASSUMPTIONS` and `OAI_RUN_LABEL`
  - `run_analysis(..., variant=None, overrides=None, ...)`
  - CLI `oai run NAME [--variant V] [--set k=v ...]`

- [ ] **Step 1: Update existing runner tests for label directories and add new failing tests**

In `tests/test_runner.py`, change the expected paths:
- `test_runs_local_steps_with_step_env`:
  ```python
      marker = tmp_path / "work" / "toy" / "default" / "a.done"
      assert marker.read_text() == f"{(tmp_path / 'results' / 'toy' / 'default').resolve()}|toy"
      assert not (tmp_path / "work" / "toy" / "default" / "b.done").exists()
  ```
- Every other `tmp_path / "work" / "toy" / "<x>.done"` in the file becomes `tmp_path / "work" / "toy" / "default" / "<x>.done"`. The exception is `test_frame_dir_override`, which keeps its explicit frame directory.

Append:
```python
LABEL_STEP = textwrap.dedent(
    """
    import json, os, pathlib
    data = json.loads(pathlib.Path(os.environ["OAI_ASSUMPTIONS"]).read_text())
    out = pathlib.Path(os.environ["OAI_RESULTS_DIR"]) / "seen.txt"
    out.write_text(os.environ["OAI_RUN_LABEL"] + "|" + str(data["assumptions"]["model.corstr"]["value"]))
    """
)

TOY_ASSUMPTIONS = textwrap.dedent(
    """
    [model.corstr]
    value = "exchangeable"
    status = "open"
    source = "test"

    [variants.indep]
    description = "independence"
    set = { "model.corstr" = "independence" }
    """
)


@pytest.fixture
def labelled(toy):
    (toy.root / "a.py").write_text(LABEL_STEP)
    (toy.root / "assumptions.toml").write_text(TOY_ASSUMPTIONS)
    return load_analysis(toy.root)


def test_variants_write_to_separate_label_directories(labelled, tmp_path):
    settings = make_settings(tmp_path)
    run_analysis(labelled, settings, stage="local", echo=lambda _: None)
    run_analysis(labelled, settings, stage="local", variant="indep", echo=lambda _: None)
    results = tmp_path / "results" / "toy"
    assert (results / "default" / "seen.txt").read_text() == "default|exchangeable"
    assert (results / "indep" / "seen.txt").read_text() == "indep|independence"
    assert (tmp_path / "work" / "toy" / "indep" / "assumptions.resolved.json").is_file()
    assert (results / "indep" / "assumptions.resolved.json").is_file()


def test_override_creates_custom_label(labelled, tmp_path):
    run_analysis(
        labelled, make_settings(tmp_path), stage="local",
        overrides={"model.corstr": "ar1"}, echo=lambda _: None,
    )
    [label_dir] = [p for p in (tmp_path / "results" / "toy").iterdir() if p.name.startswith("default+custom-")]
    assert (label_dir / "seen.txt").read_text().endswith("|ar1")


def test_bad_override_fails_before_any_step_runs(labelled, tmp_path):
    with pytest.raises(AssumptionsError, match="unknown assumption"):
        run_analysis(labelled, make_settings(tmp_path), overrides={"nope": 1}, echo=lambda _: None)
    with pytest.raises(AssumptionsError, match="unknown variant"):
        run_analysis(labelled, make_settings(tmp_path), variant="nope", echo=lambda _: None)
    assert not (tmp_path / "results" / "toy").exists()


def test_cli_run_with_variant_and_set(labelled, tmp_path, monkeypatch):
    monkeypatch.setenv("OAI_ANALYSES_DIR", str(labelled.root.parent))
    result = CliRunner().invoke(app, ["run", "toy", "--stage", "local", "--variant", "indep"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "results" / "toy" / "indep" / "seen.txt").is_file()
    bad = CliRunner().invoke(app, ["run", "toy", "--stage", "local", "--set", "model.corstr=3"])
    assert bad.exit_code == 1 and "expects str" in bad.output
```
Also add `from oai.assumptions import AssumptionsError` to the imports.

In `tests/test_r_interop.py`, `test_runner_r_step_sees_oaimodels`: change the expected path to `tmp_path / "results" / "rstep" / "default" / "covs.txt"`.

- [ ] **Step 2: Run tests to verify the right ones fail**

Run: `uv run pytest tests/test_runner.py tests/test_r_interop.py -q`
Expected: the label-path tests fail (markers not under `default/`), the new tests fail (`unexpected keyword argument 'variant'` / `'overrides'`), and the CLI test fails with "No such option: --variant".

- [ ] **Step 3: Implement**

In `src/oai/runner.py`:
- add `from oai.assumptions import DEFAULT_LABEL, Resolved, load_assumptions`
- replace `frame_dir` and `step_env`, and add `resolve_assumptions`:

```python
def frame_dir(
    analysis: Analysis, settings: Settings, env: Mapping[str, str], label: str = DEFAULT_LABEL
) -> Path:
    """Where a run's frames live; an explicit OAI_FRAME_DIR (a bundle) is used as-is."""
    override = env.get("OAI_FRAME_DIR")
    return Path(override) if override else settings.work_dir / analysis.name / label


def resolve_assumptions(
    analysis: Analysis, variant: str | None = None, overrides: Mapping[str, object] | None = None
) -> Resolved:
    return load_assumptions(analysis.root).resolve(analysis.name, variant, overrides)


def step_env(
    analysis: Analysis,
    settings: Settings,
    base_env: Mapping[str, str] | None = None,
    *,
    resolved: Resolved | None = None,
) -> dict[str, str]:
    env = dict(os.environ if base_env is None else base_env)
    resolved = resolved or resolve_assumptions(analysis)
    frames = frame_dir(analysis, settings, env, resolved.label)
    results = settings.results_dir / analysis.name / resolved.label
    frames.mkdir(parents=True, exist_ok=True)
    results.mkdir(parents=True, exist_ok=True)
    resolved.write(results)
    env.update(
        OAI_ANALYSIS=analysis.name,
        OAI_FRAME_DIR=str(frames),
        OAI_RESULTS_DIR=str(results),
        OAI_ASSUMPTIONS=str(resolved.write(frames)),
        OAI_RUN_LABEL=resolved.label,
    )
    r_profile = settings.repo_root / "r" / "step-profile.R" if settings.repo_root else None
    if r_profile is not None and r_profile.is_file():
        env.setdefault("OAI_R_DIR", str(r_profile.parent))
        env.setdefault("R_PROFILE_USER", str(r_profile))
    return env
```
- change `run_analysis`:

```python
def run_analysis(
    analysis: Analysis,
    settings: Settings,
    *,
    stage: str | None = None,
    step_id: str | None = None,
    variant: str | None = None,
    overrides: Mapping[str, object] | None = None,
    base_env: Mapping[str, str] | None = None,
    echo: Callable[[str], None] = print,
) -> list[StepResult]:
    steps = select_steps(analysis, stage=stage, step_id=step_id)
    resolved = resolve_assumptions(analysis, variant, overrides)  # fail before running anything
    if any(s.stage == "enclave" for s in steps) and settings.geno_dir is None:
        raise RunnerError("Enclave steps require OAI_GENO_DIR; they only run inside the secure enclave.")
    commands = [(step, step_command(step, analysis)) for step in steps]
    env = step_env(analysis, settings, base_env, resolved=resolved)
    results: list[StepResult] = []
    for step, cmd in commands:
        echo(f"==> {analysis.name}:{step.id} [{resolved.label}] ({step.lang}, {step.stage})")
        proc = subprocess.run(cmd, cwd=analysis.root, env=env)
        results.append(StepResult(step.id, proc.returncode))
        if proc.returncode != 0:
            raise RunnerError(f"step {step.id!r} failed with exit code {proc.returncode}")
    return results
```

In `src/oai/export/bundle.py`, the frame lookup reads the `default` label explicitly:
```python
from oai.assumptions import DEFAULT_LABEL
...
    frame_path = frame_dir(analysis, settings, os.environ, DEFAULT_LABEL) / analysis.export.frame
```

In `src/oai/cli.py`, add `from oai.assumptions import parse_override` and replace the `run` command:
```python
@app.command()
def run(
    name: Annotated[str, typer.Argument(help="Analysis folder name under analyses/.")],
    stage: Annotated[
        str | None, typer.Option(help="Only run steps of this stage (local|enclave).")
    ] = None,
    step: Annotated[str | None, typer.Option(help="Only run this step id.")] = None,
    variant: Annotated[
        str | None, typer.Option(help="Named variant from the analysis's assumptions.toml.")
    ] = None,
    set_: Annotated[
        list[str] | None,
        typer.Option("--set", help="Override an assumption, key=value (repeatable)."),
    ] = None,
) -> None:
    """Run an analysis's steps in declared order."""
    with user_errors():
        overrides = dict(parse_override(text) for text in set_ or [])
        settings = get_settings()
        analysis = find_analysis(name, settings.analyses_dir)
        results = run_analysis(
            analysis, settings, stage=stage, step_id=step, variant=variant,
            overrides=overrides, echo=typer.echo,
        )
        typer.echo(f"{len(results)} step(s) completed: {', '.join(r.step_id for r in results)}")
```

- [ ] **Step 4: Run the whole suite**

Run: `uv run ruff format -q . && uv run ruff check --fix -q; uv run pytest -q`
Expected: all pass, including `tests/test_bundle.py` unchanged (its frame is written by the step to `OAI_FRAME_DIR` = `work/toy/default` and read back from there).

- [ ] **Step 5: Commit**

```bash
git add src/oai/runner.py src/oai/cli.py src/oai/export/bundle.py tests/test_runner.py tests/test_r_interop.py
git commit -m "feat: resolve assumptions per run with variant/--set labels" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Ledger rendering, `oai assumptions`, docs

**Files:**
- Modify: `src/oai/assumptions.py`, `src/oai/cli.py`, `README.md`
- Create: `docs/assumptions.md`, `tests/test_assumptions_ledgers.py`
- Test: add to `tests/test_assumptions.py`

**Interfaces:**
- Produces: `render_ledger(name: str, assumptions: Assumptions) -> str`; CLI `oai assumptions NAME [--write]`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_assumptions.py`:
```python
from typer.testing import CliRunner

from oai.assumptions import render_ledger
from oai.cli import app


def test_render_ledger_groups_by_status(tmp_path):
    text = render_ledger("demo", load_assumptions(write(tmp_path)))
    assert text.startswith("# Assumptions: demo\n")
    assert "2 confirmed · 1 assumed · 1 open" in text
    assert "## Confirmed (2)" in text and "## Open (1)" in text
    assert "| `cohort.survey_start` | `2012-09-12` | p.1662 | visit date cutoff |" in text
    assert "| `alignment.varus_max` | `-2.0` | p.1662 |  |" in text
    assert "## Variants" in text and "`model.corstr = independence`" in text


def test_render_ledger_escapes_pipes(tmp_path):
    text = TOML.replace('source = "p.1661"', 'source = "a | b"')
    assert "a \\| b" in render_ledger("demo", load_assumptions(write(tmp_path, text)))


def test_cli_assumptions_prints_and_writes(tmp_path, monkeypatch):
    root = write(tmp_path)
    (root / "analysis.toml").write_text('name = "demo"\n[[steps]]\nid = "a"\nlang = "python"\nentry = "a.py"\n')
    (root / "a.py").write_text("")
    monkeypatch.setenv("OAI_ANALYSES_DIR", str(tmp_path))
    shown = CliRunner().invoke(app, ["assumptions", "demo"])
    assert shown.exit_code == 0 and "## Open (1)" in shown.stdout
    written = CliRunner().invoke(app, ["assumptions", "demo", "--write"])
    assert written.exit_code == 0
    assert (root / "ASSUMPTIONS.md").read_text() == render_ledger("demo", load_assumptions(root))


def test_cli_assumptions_without_file(tmp_path, monkeypatch):
    root = tmp_path / "bare"
    root.mkdir()
    (root / "analysis.toml").write_text('name = "bare"\n[[steps]]\nid = "a"\nlang = "python"\nentry = "a.py"\n')
    (root / "a.py").write_text("")
    monkeypatch.setenv("OAI_ANALYSES_DIR", str(tmp_path))
    result = CliRunner().invoke(app, ["assumptions", "bare"])
    assert result.exit_code == 1 and "has no assumptions.toml" in result.output
```

`tests/test_assumptions_ledgers.py`:
```python
"""Every committed ASSUMPTIONS.md must match what `oai assumptions NAME --write` produces."""

from pathlib import Path

import pytest

from oai.assumptions import LEDGER_FILE, load_assumptions, render_ledger

REPO = Path(__file__).resolve().parents[1]
WITH_ASSUMPTIONS = sorted(p.parent for p in (REPO / "analyses").glob("*/assumptions.toml"))


@pytest.mark.parametrize("root", WITH_ASSUMPTIONS, ids=lambda p: p.name)
def test_ledger_is_in_sync(root):
    ledger = root / LEDGER_FILE
    assert ledger.is_file(), f"run `oai assumptions {root.name} --write`"
    assert ledger.read_text() == render_ledger(root.name, load_assumptions(root)), (
        f"{ledger} is stale: run `oai assumptions {root.name} --write`"
    )
```
(With no analyses using assumptions yet, this parametrizes to zero cases, and pytest reports it as skipped. Task 7 gives it a case.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_assumptions.py -q`
Expected: `ImportError: cannot import name 'render_ledger'`.

- [ ] **Step 3: Implement**

Append to `src/oai/assumptions.py`:
```python
def _fmt(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value)


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def render_ledger(name: str, assumptions: Assumptions) -> str:
    """Markdown ledger grouped by status; written to ASSUMPTIONS.md by `oai assumptions --write`."""
    items = list(assumptions.items.values())
    counts = {status: sum(1 for a in items if a.status == status) for status in STATUSES}
    lines = [
        f"# Assumptions: {name}",
        "",
        f"<!-- Generated by `oai assumptions {name} --write` from assumptions.toml. Do not edit. -->",
        "",
        " · ".join(f"{counts[status]} {status}" for status in STATUSES),
    ]
    for status in STATUSES:
        rows = sorted((a for a in items if a.status == status), key=lambda a: a.key)
        if not rows:
            continue
        lines += [
            "",
            f"## {status.capitalize()} ({len(rows)})",
            "",
            "| Key | Value | Source | Rationale |",
            "|---|---|---|---|",
        ]
        lines += [
            f"| `{a.key}` | `{_cell(_fmt(a.value))}` | {_cell(a.source)} | {_cell(a.rationale)} |"
            for a in rows
        ]
    if assumptions.variants:
        lines += ["", "## Variants", "", "| Variant | Sets | Description |", "|---|---|---|"]
        for v in sorted(assumptions.variants.values(), key=lambda v: v.name):
            sets = "<br>".join(f"`{k} = {_cell(_fmt(val))}`" for k, val in v.set.items())
            lines.append(f"| `{v.name}` | {sets} | {_cell(v.description)} |")
    return "\n".join(lines) + "\n"
```

In `src/oai/cli.py`, extend the assumptions import to `from oai.assumptions import LEDGER_FILE, AssumptionsError, load_assumptions, parse_override, render_ledger` and add:
```python
@app.command("assumptions")
def assumptions_cmd(
    name: Annotated[str, typer.Argument(help="Analysis folder name under analyses/.")],
    write: Annotated[bool, typer.Option(help="Write ASSUMPTIONS.md next to assumptions.toml.")] = False,
) -> None:
    """Show (or write) an analysis's assumptions ledger."""
    with user_errors():
        analysis = find_analysis(name, get_settings().analyses_dir)
        loaded = load_assumptions(analysis.root)
        if loaded.path is None:
            raise AssumptionsError(f"{name} has no assumptions.toml")
        text = render_ledger(name, loaded)
        if write:
            out = analysis.root / LEDGER_FILE
            out.write_text(text)
            typer.echo(f"Wrote {out}")
        else:
            typer.echo(text)
```

`docs/assumptions.md`:
````markdown
# Assumptions

Every analysis records its analytic choices in `analyses/<name>/assumptions.toml`, so
results are transparent and sensitivity analyses are a flag away.

## The file

```toml
[cohort.survey_start]              # key: cohort.survey_start
value = "2012-09-12"               # scalar, array or inline table (dates as strings)
status = "assumed"                 # confirmed | assumed | open
source = "Lo 2022 p.1662"          # where the choice comes from (required)
rationale = "Visit-date cutoff"    # optional
alternatives = ["none"]            # optional, documentation only

[variants.missing_as_walkers]      # named override set for a sensitivity analysis
description = "Supplementary Table 3"
set = { "cohort.impute_missing_walking" = "walker" }
```

- **confirmed:** stated by the source (paper, protocol, data documentation).
- **assumed:** our reading, ideally checked against a published number.
- **open:** not stated anywhere; a sensitivity variant should cover it.

## Running with variants and overrides

```bash
oai run lo2022_walking                                    # label: default
oai run lo2022_walking --variant missing_as_walkers       # label: missing_as_walkers
oai run lo2022_walking --set model.corstr=independence    # label: default+custom-<hash>
```

- **Where outputs go:** each label has its own folders, `$OAI_WORK_DIR/<analysis>/<label>/`
  and `$OAI_RESULTS_DIR/<analysis>/<label>/`, so runs never overwrite each other.
- **Provenance:** both folders get `assumptions.resolved.json`, recording every value used
  and whether it came from the default, the variant or an override.
- **Validation:** unknown keys, unknown variants and type mismatches fail before any step
  runs.
- **Reading values in steps:**
  - Python: `from oai.assumptions import current; A = current(); A["model.corstr"]`
  - R: `A <- oaimodels::assumptions(); A[["model.corstr"]]`

## The ledger

`oai assumptions NAME` prints the ledger grouped by status, and `--write` saves it as
`ASSUMPTIONS.md` next to the TOML. A test fails if a committed ledger is stale.
````

In `README.md`, add two rows to the Commands table after the `oai run` row:
```markdown
| `oai run NAME --variant V` / `--set key=value` | Run with a named sensitivity variant or ad-hoc overrides ([docs/assumptions.md](docs/assumptions.md)) |
| `oai assumptions NAME [--write]` | Show or write an analysis's assumptions ledger |
```

- [ ] **Step 4: Run tests**

Run: `uv run ruff format -q . && uv run ruff check --fix -q; uv run pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/oai/assumptions.py src/oai/cli.py tests/test_assumptions.py tests/test_assumptions_ledgers.py docs/assumptions.md README.md
git commit -m "feat: render assumptions ledgers with oai assumptions" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: R access to resolved assumptions

**Files:**
- Modify: `r/oaimodels/DESCRIPTION` (`Imports: nanoparquet, jsonlite`), `r/oaimodels/NAMESPACE`
- Create: `r/oaimodels/R/assumptions.R`, `r/oaimodels/tests/testthat/test-assumptions.R`
- Test: add to `tests/test_r_interop.py`

**Interfaces:**
- Produces: `oaimodels::assumptions(path = Sys.getenv("OAI_ASSUMPTIONS"))`, a named list mapping each key to its value. `jsonlite` is already in `r/renv.lock` (version 2.0.0), so no lockfile change is needed.

- [ ] **Step 1: Write the failing R test**

`r/oaimodels/tests/testthat/test-assumptions.R`:
```r
test_that("assumptions() returns key -> value from the resolved JSON", {
  path <- tempfile(fileext = ".json")
  writeLines('{"analysis": "demo", "label": "default", "variant": null, "overrides": {},
    "assumptions": {
      "model.corstr": {"value": "exchangeable", "status": "open", "source": "x", "origin": "default"},
      "model.covariates": {"value": ["age", "sex", "kl0"], "status": "confirmed", "source": "x", "origin": "default"},
      "alignment.varus_max": {"value": -2.0, "status": "confirmed", "source": "x", "origin": "default"}}}', path)
  a <- assumptions(path)
  expect_equal(a[["model.corstr"]], "exchangeable")
  expect_equal(a[["model.covariates"]], c("age", "sex", "kl0"))
  expect_equal(a[["alignment.varus_max"]], -2)
})

test_that("assumptions() explains how to get a resolved file", {
  expect_error(assumptions(""), "oai run")
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd r && Rscript -e 'testthat::test_local("oaimodels")' 2>&1 | tail -3`
Expected: FAIL (`could not find function "assumptions"`).

- [ ] **Step 3: Implement**

`r/oaimodels/R/assumptions.R`:
```r
#' Resolved assumptions for the current run
#'
#' `oai run` writes `assumptions.resolved.json` and points `OAI_ASSUMPTIONS` at it.
#' @param path Resolved JSON file.
#' @return Named list: assumption key -> value.
assumptions <- function(path = Sys.getenv("OAI_ASSUMPTIONS")) {
  if (!nzchar(path) || !file.exists(path)) {
    stop("No resolved assumptions found: run this step via `oai run`", call. = FALSE)
  }
  resolved <- jsonlite::fromJSON(path, simplifyVector = TRUE)
  lapply(resolved$assumptions, function(entry) entry$value)
}
```
Add `export(assumptions)` to `NAMESPACE`, and change the `DESCRIPTION` line `Imports: nanoparquet` to `Imports: nanoparquet, jsonlite`.

Append to `tests/test_r_interop.py`:
```python
def test_runner_r_step_reads_assumptions(tmp_path):
    root = tmp_path / "analyses" / "rassume"
    root.mkdir(parents=True)
    (root / "analysis.toml").write_text(
        'name = "rassume"\n[[steps]]\nid = "m"\nlang = "r"\nstage = "local"\nentry = "m.R"\n'
    )
    (root / "assumptions.toml").write_text(
        '[model.corstr]\nvalue = "exchangeable"\nstatus = "open"\nsource = "t"\n'
    )
    (root / "m.R").write_text(
        'writeLines(oaimodels::assumptions()[["model.corstr"]], '
        'file.path(Sys.getenv("OAI_RESULTS_DIR"), "corstr.txt"))\n'
    )
    settings = load_settings(
        env={"OAI_WORK_DIR": str(tmp_path / "work"), "OAI_RESULTS_DIR": str(tmp_path / "results")},
        repo_root=REPO,
    )
    run_analysis(load_analysis(root), settings, overrides={"model.corstr": "ar1"}, echo=lambda _: None)
    [out] = (tmp_path / "results" / "rassume").glob("*/corstr.txt")
    assert out.read_text().strip() == "ar1"
```

- [ ] **Step 4: Run tests**

Run: `(cd r && Rscript -e 'testthat::test_local("oaimodels", stop_on_failure = TRUE)' 2>&1 | tail -1) && uv run pytest tests/test_r_interop.py -q`
Expected: `[ FAIL 0 | WARN 0 | SKIP 0 | PASS 11 ]`; interop tests pass.

- [ ] **Step 5: Commit**

```bash
git add r/oaimodels tests/test_r_interop.py
git commit -m "feat: expose resolved assumptions to R steps" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Knee-level synthetic release + readings and fallback

**Files:**
- Create: `tests/fixtures/oai_knee/*.txt` (all files below), `src/oai/derive/knee.py`, `tests/test_derive_knee.py`

**Interfaces:**
- Produces:
  - `SIDE_CODES = {1: "R", 2: "L"}`, `KNEE_KEYS = ("ID", "SIDE")`
  - `find_col(df, name) -> str` (raises `KeyError`)
  - `xray_readings(visits, *, project=15) -> DataFrame[ID, SIDE, visit, KL: f64, JSM: f64]`
  - `with_fallback(*frames, value_cols, on=KNEE_KEYS) -> DataFrame`: the first frame whose row has any non-null value wins; `visit` is renamed to `source_visit`.

- [ ] **Step 1: Create the synthetic knee release**

It has 10 participants, one per flow step, plus included cases. All file bodies below are exact.

`tests/fixtures/oai_knee/Enrollees.txt`:
```text
ID|VERSION|P02SEX
1000001|2.1|1: Male
1000002|2.1|2: Female
1000003|2.1|2: Female
1000004|2.1|2: Female
1000005|2.1|2: Female
1000006|2.1|1: Male
1000007|2.1|2: Female
1000008|2.1|2: Female
1000009|2.1|1: Male
1000010|2.1|2: Female
```

`tests/fixtures/oai_knee/AllClinical00.txt` (1000010's right-knee pain is a single-space blank):
```text
ID|V00AGE|P01BMI|P01KPR12CV|P01KPL12CV
1000001|61|27.5|0: No|0: No
1000002|45|24.0|0: No|0: No
1000003|70|31.0|1: Yes|0: No
1000004|66|29.0|0: No|0: No
1000005|58|28.0|1: Yes|0: No
1000006|72|33.0|0: No|0: No
1000007|55|26.0|0: No|1: Yes
1000008|63|30.0|0: No|0: No
1000009|68|32.5|1: Yes|0: No
1000010|59|25.5| |0: No
```

`tests/fixtures/oai_knee/AllClinical05.txt`:
```text
ID|V05VISDYS|V05KPR12CV|V05KPL12CV
1000001|1100|0: No|0: No
1000009|1100|0: No|1: Yes
1000010|1090|0: No|0: No
```

`tests/fixtures/oai_knee/AllClinical06.txt`:
```text
ID|V06VISDYS|V06KPR12CV|V06KPL12CV
1000001|1470|1: Yes|0: No
1000006|1480|0: No|0: No
1000009| | | 
1000010|1455|0: No|0: No
```

`tests/fixtures/oai_knee/AllClinical10.txt`:
```text
ID|V10FVDATE|V10WLKAR1|V10WLKAR2|V10WLKAR3|V10WLKAR4|V10WKYRAR4|V10WKMOAR4|V10WKTMAR4
1000001|01/15/2013|1|1|1|1|4|3|3
1000002|02/01/2013|0|0|0|0| | | 
1000003|02/01/2013|1|1|1|1|1|1|1
1000004|02/01/2013|0|0|0|0| | | 
1000005|05/01/2012| | | | | | | 
1000006| | | | | | | | 
1000007|03/01/2013| | | | | | | 
1000008|02/01/2013|0|0|0|0| | | 
1000009|04/01/2013|0|1|0|0| | | 
1000010|06/01/2013|1| | | | | | 
```

`tests/fixtures/oai_knee/kxr_sq_bu00.txt` (1000003 has only a Project-37 reading):
```text
ID|SIDE|READPRJ|VERSION|V00XRKL|V00XRJSM
1000001|1: Right|15|0.9|2|1
1000001|2: Left|15|0.9|1|0
1000002|1: Right|15|0.9|2|1
1000003|1: Right|37|0.9|3|2
1000004|1: Right|15|0.9|1|0
1000004|2: Left|15|0.9|1|1
1000005|1: Right|15|0.9|2|1
1000006|1: Right|15|0.9|3|2
1000007|1: Right|15|0.9|2|0
1000008|1: Right|15|0.9|2|1
1000009|1: Right|15|0.9|3|2
1000009|2: Left|15|0.9|4|3
1000010|1: Right|15|0.9|2|0
1000010|2: Left|15|0.9|0|0
```

`tests/fixtures/oai_knee/kxr_sq_bu05.txt` (lowercase `readprj`, as in the release):
```text
ID|SIDE|readprj|VERSION|V05XRKL|V05XRJSM
1000001|1: Right|15|0.9|2|1
1000009|1: Right|15|0.9|3|2.2
```

`tests/fixtures/oai_knee/kxr_sq_bu06.txt` (1000009's right knee is read only in Project 37 at 48 months):
```text
ID|SIDE|READPRJ|VERSION|V06XRKL|V06XRJSM
1000001|1: Right|15|0.9|3|1.4
1000001|2: Left|15|0.9|1|0
1000006|1: Right|15|0.9|3|2
1000009|1: Right|37|0.9|4|3
1000010|1: Right|15|0.9|2|0
1000010|2: Left|15|0.9|0|0
```

`tests/fixtures/oai_knee/OUTCOMES99.txt` (lowercase `id`, as in the release):
```text
id|V99ERKBLRP|V99ELKBLRP|V99ERKRPCF|V99ELKRPCF|V99ERKRPSN|V99ELKRPSN|V99ERKDAYS|V99ELKDAYS
1000001|0: No|0: No| | | | | | 
1000002|0: No|0: No| | | | | | 
1000003|0: No|0: No| | | | | | 
1000004|0: No|1: Yes| | | | | | 
1000005|0: No|0: No| | | | | | 
1000006|0: No|0: No| | | | | | 
1000007|0: No|0: No| | | | | | 
1000008|0: No|0: No|0: Replacement adjudcated,failed to confirm| | | |900| 
1000009|0: No|0: No| |3: Replacement adjudicated, confirmed| | | |900
1000010|0: No|0: No| | |1: Yes, replacement seen on FU xray| |2000| 
```

`tests/fixtures/oai_knee/flxr_kneealign_cooke01.txt`:
```text
ID|SIDE|READPRJ|V01HKANGLE
1000001|1: Right|60|-3.5
1000009|1: Right|60|2.5
```

`tests/fixtures/oai_knee/flxr_kneealign_cooke03.txt`:
```text
ID|SIDE|READPRJ|V03HKANGLE
1000001|1: Right|60|-1.0
1000010|1: Right|60|0.5
```

`tests/fixtures/oai_knee/flxr_kneealign_cooke05.txt`:
```text
ID|SIDE|READPRJ|V05HKANGLE
1000009|2: Left|60| 
```

`tests/fixtures/oai_knee/flxr_kneealign_cooke06.txt`:
```text
ID|SIDE|READPRJ|V06HKANGLE
1000006|1: Right|60|-4.0
```

- [ ] **Step 2: Write the failing tests**

`tests/test_derive_knee.py`:
```python
from pathlib import Path

import polars as pl
import pytest

from oai.catalog import catalog_for
from oai.config import get_settings
from oai.derive.knee import find_col, with_fallback, xray_readings

KNEE_DATA = Path(__file__).parent / "fixtures" / "oai_knee"


@pytest.fixture(autouse=True)
def knee_release(isolated_settings, monkeypatch):
    monkeypatch.setenv("OAI_DATA_DIR", str(KNEE_DATA))
    get_settings.cache_clear()
    catalog_for.cache_clear()


def knee(df, id_, side):
    return df.filter((pl.col("ID") == id_) & (pl.col("SIDE") == side)).row(0, named=True)


def test_find_col_is_case_insensitive():
    df = pl.DataFrame({"readprj": [15], "ID": [1]})
    assert find_col(df, "READPRJ") == "readprj"
    with pytest.raises(KeyError):
        find_col(df, "SIDE")


def test_xray_readings_filters_project_and_maps_side():
    base = xray_readings(["00"], project=15)
    assert base.columns == ["ID", "SIDE", "visit", "KL", "JSM"]
    assert 1000003 not in base["ID"].to_list()  # only read in Project 37
    assert knee(base, 1000009, "L") == {"ID": 1000009, "SIDE": "L", "visit": "00", "KL": 4.0, "JSM": 3.0}


def test_xray_readings_handles_lowercase_readprj_and_decimal_jsn():
    assert knee(xray_readings(["05"]), 1000009, "R")["JSM"] == 2.2


def test_with_fallback_prefers_first_frame_and_records_source():
    fu = with_fallback(xray_readings(["06"]), xray_readings(["05"]), value_cols=["KL", "JSM"])
    assert knee(fu, 1000001, "R")["source_visit"] == "06"
    row = knee(fu, 1000009, "R")  # 48-month reading is Project 37 only -> 36-month fallback
    assert (row["source_visit"], row["JSM"]) == ("05", 2.2)
    assert fu.filter((pl.col("ID") == 1000009) & (pl.col("SIDE") == "L")).is_empty()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_derive_knee.py -q`
Expected: collection error — `No module named 'oai.derive.knee'`.

- [ ] **Step 4: Implement**

`src/oai/derive/knee.py`:
```python
"""Knee-level building blocks shared by progression analyses.

Every frame is keyed on ID (Int64) and SIDE ("R"/"L"; the release codes 1 = Right,
2 = Left). Column lookups are case-insensitive because the release mixes spellings
(READPRJ/readprj, ID/id).
"""

from __future__ import annotations

from collections.abc import Sequence

import polars as pl

from oai.loader import read_table

SIDE_CODES = {1: "R", 2: "L"}
KNEE_KEYS = ("ID", "SIDE")


def find_col(df: pl.DataFrame, name: str) -> str:
    """The frame's column matching `name` case-insensitively."""
    for col in df.columns:
        if col.upper() == name.upper():
            return col
    raise KeyError(f"column {name!r} not found")


def _side(df: pl.DataFrame) -> pl.Expr:
    return pl.col(find_col(df, "SIDE")).replace_strict(SIDE_CODES, return_dtype=pl.String).alias("SIDE")


def xray_readings(visits: Sequence[str], *, project: int = 15) -> pl.DataFrame:
    """ID, SIDE, visit, KL, JSM from kxr_sq_bu, one reading project only.

    Follow-up medial JSN (JSM) keeps within-grade decimals such as 1.2, so
    "JSM follow-up > JSM baseline" captures within-grade worsening.
    """
    frames = []
    for visit in visits:
        df = read_table("kxr_sq_bu", visit)
        frames.append(
            df.filter(pl.col(find_col(df, "READPRJ")) == project)
            .select(
                pl.col(find_col(df, "ID")).alias("ID"),
                _side(df),
                pl.lit(visit).alias("visit"),
                pl.col(find_col(df, f"V{visit}XRKL")).cast(pl.Float64).alias("KL"),
                pl.col(find_col(df, f"V{visit}XRJSM")).cast(pl.Float64).alias("JSM"),
            )
            .unique(["ID", "SIDE", "visit"], keep="first", maintain_order=True)
        )
    return pl.concat(frames)


def _nonempty(df: pl.DataFrame, cols: Sequence[str]) -> pl.DataFrame:
    return df.filter(pl.any_horizontal([pl.col(c).is_not_null() for c in cols]))


def with_fallback(
    *frames: pl.DataFrame, value_cols: Sequence[str], on: Sequence[str] = KNEE_KEYS
) -> pl.DataFrame:
    """Per key, the row from the first frame with any non-null value_cols; adds source_visit.

    Frames must carry a `visit` column (renamed to `source_visit` in the result).
    """
    keys = list(on)
    picked: list[pl.DataFrame] = []
    seen: pl.DataFrame | None = None
    for df in frames:
        rows = _nonempty(df, value_cols)
        if seen is not None:
            rows = rows.join(seen, on=keys, how="anti")
        picked.append(rows)
        seen = rows.select(keys) if seen is None else pl.concat([seen, rows.select(keys)])
    return pl.concat(picked, how="diagonal_relaxed").rename({"visit": "source_visit"})
```

- [ ] **Step 5: Run tests**

Run: `uv run ruff format -q . && uv run ruff check --fix -q; uv run pytest -q && uv run python scripts/check_no_data.py`
Expected: all pass; guard clean (fixtures are allow-listed for headers and names, and IDs start with 1).

- [ ] **Step 6: Commit**

```bash
git add tests/fixtures/oai_knee src/oai/derive/knee.py tests/test_derive_knee.py
git commit -m "feat: add knee-level reading and fallback derivations" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Pain, visit days, knee replacement, alignment

**Files:**
- Modify: `src/oai/derive/knee.py`, `tests/test_derive_knee.py`

**Interfaces:**
- Produces:
  - `frequent_knee_pain(visit, item) -> DataFrame[ID, SIDE, visit, frequent_pain: bool]`; `item` is a template with `{visit}`/`{side}`.
  - `visit_days(visit) -> DataFrame[ID, days: f64]`
  - `REPLACEMENT_STATUS_COUNTS = (1, 3)`
  - `knee_replacement(by_days=None) -> DataFrame[ID, SIDE, replaced_at_baseline, replaced_days, replaced]`
  - `knee_alignment(*, source="cooke", visits=("01","03","05","06"), pick="earliest") -> DataFrame[ID, SIDE, visit, hka]`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_derive_knee.py`:
```python
from oai.derive.knee import frequent_knee_pain, knee_alignment, knee_replacement, visit_days


def test_frequent_knee_pain_baseline_and_blank():
    pain = frequent_knee_pain("00", "P01KP{side}12CV")
    assert knee(pain, 1000009, "R")["frequent_pain"] is True
    assert knee(pain, 1000001, "L")["frequent_pain"] is False
    assert knee(pain, 1000010, "R")["frequent_pain"] is None  # blank cell


def test_frequent_knee_pain_followup_template():
    pain = frequent_knee_pain("05", "V{visit}KP{side}12CV")
    assert knee(pain, 1000009, "L")["frequent_pain"] is True


def test_visit_days():
    days = dict(visit_days("06").iter_rows())
    assert days[1000001] == 1470.0 and days[1000009] is None


def test_knee_replacement_counts_and_baseline_flag():
    rep = knee_replacement()
    assert knee(rep, 1000004, "L")["replaced_at_baseline"] is True
    assert knee(rep, 1000008, "R")["replaced"] is False  # adjudicated, failed to confirm
    assert knee(rep, 1000009, "L")["replaced"] is True  # adjudicated, confirmed
    assert knee(rep, 1000010, "R")["replaced"] is True  # seen on follow-up x-ray


def test_knee_replacement_by_days_window():
    by = pl.DataFrame({"ID": [1000009, 1000010], "days": [1100.0, 1455.0]})
    rep = knee_replacement(by)
    assert knee(rep, 1000009, "L")["replaced"] is True  # day 900 <= 1100
    assert knee(rep, 1000010, "R")["replaced"] is False  # day 2000 > 1455
    assert knee(rep, 1000001, "R")["replaced"] is False  # no days for this ID -> not replaced


def test_knee_alignment_pick_and_blank_films():
    earliest = knee_alignment()
    assert knee(earliest, 1000001, "R") == {"ID": 1000001, "SIDE": "R", "visit": "01", "hka": -3.5}
    assert knee(knee_alignment(pick="latest"), 1000001, "R")["hka"] == -1.0
    assert earliest.filter((pl.col("ID") == 1000009) & (pl.col("SIDE") == "L")).is_empty()


def test_knee_alignment_rejects_unknown_pick():
    with pytest.raises(ValueError, match="pick"):
        knee_alignment(pick="middle")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_derive_knee.py -q`
Expected: `ImportError: cannot import name 'frequent_knee_pain'`.

- [ ] **Step 3: Implement**

Append to `src/oai/derive/knee.py`:
```python
# Lo 2022 p.1661: a follow-up replacement counts when adjudicated-confirmed (3) or
# self-reported (1), or when seen on a follow-up x-ray; "adjudicated, failed to confirm"
# (0) does not count unless it was seen on an x-ray.
REPLACEMENT_STATUS_COUNTS = (1, 3)
ALIGNMENT_COLUMNS = {"cooke": "V{visit}HKANGLE", "duryea": "V{visit}HKANGJD"}


def frequent_knee_pain(visit: str, item: str) -> pl.DataFrame:
    """ID, SIDE, visit, frequent_pain from a per-side item template.

    `item` may use {visit} and {side}, e.g. "V{visit}KP{side}12CV" or "P01KP{side}12CV".
    Blank answers stay null (neither pain nor no pain).
    """
    df = read_table("allclinical", visit)
    return pl.concat(
        [
            df.select(
                pl.col(find_col(df, "ID")).alias("ID"),
                pl.lit(side).alias("SIDE"),
                pl.lit(visit).alias("visit"),
                (pl.col(find_col(df, item.format(visit=visit, side=side))) == 1).alias("frequent_pain"),
            )
            for side in ("R", "L")
        ]
    )


def visit_days(visit: str) -> pl.DataFrame:
    """ID, days: days from enrollment to the visit (V##VISDYS)."""
    df = read_table("allclinical", visit)
    return df.select(
        pl.col(find_col(df, "ID")).alias("ID"),
        pl.col(find_col(df, f"V{visit}VISDYS")).cast(pl.Float64).alias("days"),
    )


def _outcome(df: pl.DataFrame, knee_code: str, suffix: str) -> pl.Expr:
    return pl.col(find_col(df, f"V99E{knee_code}{suffix}"))


def knee_replacement(by_days: pl.DataFrame | None = None) -> pl.DataFrame:
    """ID, SIDE, replaced_at_baseline, replaced_days, replaced (from OUTCOMES99).

    `replaced` is True for a counted follow-up replacement (see REPLACEMENT_STATUS_COUNTS)
    on or before the participant's `by_days` (a frame of ID, days). Without `by_days`, any
    counted replacement is True. A counted replacement with no day, or an ID absent from
    `by_days`, is False.
    """
    df = read_table("outcomes", "99")
    parts = []
    for side, code in (("R", "RK"), ("L", "LK")):
        counted = (
            _outcome(df, code, "RPCF").is_in(REPLACEMENT_STATUS_COUNTS)
            | (_outcome(df, code, "RPSN") == 1)
        ).fill_null(False)
        parts.append(
            df.select(
                pl.col(find_col(df, "ID")).alias("ID"),
                pl.lit(side).alias("SIDE"),
                (_outcome(df, code, "BLRP") == 1).fill_null(False).alias("replaced_at_baseline"),
                pl.when(counted).then(_outcome(df, code, "DAYS").cast(pl.Float64)).alias("replaced_days"),
                counted.alias("counted"),
            )
        )
    out = pl.concat(parts)
    if by_days is None:
        return out.rename({"counted": "replaced"})
    out = out.join(by_days.select("ID", pl.col("days").alias("by_days")), on="ID", how="left")
    in_window = pl.col("counted") & (pl.col("replaced_days") <= pl.col("by_days"))
    return out.with_columns(in_window.fill_null(False).alias("replaced")).drop("counted", "by_days")


def knee_alignment(
    *,
    source: str = "cooke",
    visits: Sequence[str] = ("01", "03", "05", "06"),
    pick: str = "earliest",
) -> pl.DataFrame:
    """ID, SIDE, visit, hka: one long-limb film per knee (degrees; negative = varus)."""
    if pick not in ("earliest", "latest"):
        raise ValueError(f"pick must be 'earliest' or 'latest', not {pick!r}")
    column = ALIGNMENT_COLUMNS[source]
    frames = []
    for visit in visits:
        df = read_table(f"flxr_kneealign_{source}", visit)
        frames.append(
            df.select(
                pl.col(find_col(df, "ID")).alias("ID"),
                _side(df),
                pl.lit(visit).alias("visit"),
                pl.col(find_col(df, column.format(visit=visit))).cast(pl.Float64).alias("hka"),
            ).drop_nulls("hka")
        )
    films = pl.concat(frames).sort("visit", descending=pick == "latest", maintain_order=True)
    return films.unique(["ID", "SIDE"], keep="first", maintain_order=True)
```

- [ ] **Step 4: Run tests**

Run: `uv run ruff format -q . && uv run ruff check --fix -q; uv run pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/oai/derive/knee.py tests/test_derive_knee.py
git commit -m "feat: add knee pain, replacement and alignment derivations" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: `lo2022_walking` definition, assumptions and published targets

**Files:**
- Create: `analyses/lo2022_walking/{analysis.toml,assumptions.toml,published.toml,README.md,ASSUMPTIONS.md}`, plus placeholder `build_frame.py`, `models.R`, `compare.py` (replaced in Tasks 8, 10, 11)
- Modify: `tests/test_analyses.py`
- Test: `tests/test_lo2022_definition.py`

- [ ] **Step 1: Write the failing tests**

In `tests/test_analyses.py`, change the expected list:
```python
    assert ANALYSES == ["activity_agreement", "genetics_progression", "lo2022_walking", "progression_definitions"]
```

`tests/test_lo2022_definition.py`:
```python
import tomllib
from pathlib import Path

from oai.assumptions import load_assumptions
from oai.manifest import load_analysis

ANALYSIS = Path(__file__).resolve().parents[1] / "analyses" / "lo2022_walking"


def test_manifest_and_assumptions_load():
    a = load_analysis(ANALYSIS)
    assert [s.id for s in a.steps] == ["cohort", "models", "compare"]
    loaded = load_assumptions(ANALYSIS)
    assert set(loaded.variants) == {
        "missing_as_nonwalkers", "missing_as_walkers", "replacement_not_worsening", "corstr_independence",
    }
    assert loaded.items["model.corstr"].status == "open"


def test_published_targets_are_well_formed():
    published = tomllib.loads((ANALYSIS / "published.toml").read_text())
    assert set(published) == {"related", "default", "missing_as_nonwalkers", "missing_as_walkers"}
    default = published["default"]
    assert default["flow.no_followup.persons"] == 1212 and default["flow.knees"] == 1808
    assert default["t2.jsn_worse.or_adj"] == {"or": 0.8, "lo": 0.6, "hi": 1.0, "sig": True}
    assert published["missing_as_walkers"]["t2.kl_worse.walkers.n"] == 2711
    known = set(load_assumptions(ANALYSIS).items)
    for prefix, keys in published["related"].items():
        assert set(keys) <= known, prefix
    for section in ("default", "missing_as_nonwalkers", "missing_as_walkers"):
        for metric, value in published[section].items():
            assert isinstance(value, (int, float)) or set(value) == {"or", "lo", "hi", "sig"}, metric
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_lo2022_definition.py tests/test_analyses.py -q`
Expected: failures (`No analysis.toml in …/lo2022_walking`, list mismatch).

- [ ] **Step 3: Create the analysis files**

`analyses/lo2022_walking/analysis.toml`:
```toml
name = "lo2022_walking"
description = "Replication of Lo et al. 2022: walking for exercise and knee OA progression (OAI)."

[inputs]
tables = [
    "enrollees", "allclinical:00", "allclinical:05", "allclinical:06", "allclinical:10",
    "kxr_sq_bu:00", "kxr_sq_bu:05", "kxr_sq_bu:06", "outcomes:99",
    "flxr_kneealign_cooke:01", "flxr_kneealign_cooke:03",
    "flxr_kneealign_cooke:05", "flxr_kneealign_cooke:06",
]

[[steps]]
id = "cohort"
lang = "python"
stage = "local"
entry = "build_frame.py"

[[steps]]
id = "models"
lang = "r"
stage = "local"
entry = "models.R"
needs = ["cohort"]

[[steps]]
id = "compare"
lang = "python"
stage = "local"
entry = "compare.py"
needs = ["models"]

[outputs]
aggregate = [
    "flow.csv", "table1.csv", "table2.csv", "table3.csv", "comparison.csv",
    "metrics_*.csv", "assumptions.resolved.json",
]
```

`analyses/lo2022_walking/assumptions.toml`:
```toml
# Assumptions for the Lo et al. 2022 replication (Arthritis Rheumatol 74:1660-7).
# confirmed = stated in the paper/supplement; assumed = our reading, checked against a
# published count where possible; open = not stated. Regenerate the ledger with
# `oai assumptions lo2022_walking --write`.

[cohort.min_age]
value = 50
status = "confirmed"
source = "Lo 2022 p.1661 (inclusion criteria)"

[cohort.reading_project]
value = 15
status = "assumed"
source = "Lo 2022 ref 11 (Project 15 reliability); reproduces the 3,980 baseline x-rays exactly"
rationale = "Project 15 is the central BU reading covering baseline to 48 months for nearly all knees"
alternatives = [37, 43]

[cohort.survey_start]
value = "2012-09-12"
status = "assumed"
source = "Lo 2022 p.1662: survey data acquired Sept 12, 2012 to Oct 31, 2014"
rationale = "Participants whose 96-month visit (V10FVDATE) came earlier were never offered the survey; check against S1 (417 persons, 644 knees)"

[cohort.survey_completed_items]
value = ["V10WLKAR1", "V10WLKAR2", "V10WLKAR3", "V10WLKAR4"]
status = "assumed"
source = "AllClinical10 Q39-Q48 walking screeners, asked of every respondent"
rationale = "Answering any walking screener means the survey was completed; check against S1 (337 persons, 513 knees)"

[cohort.impute_missing_walking]
value = "none"
status = "confirmed"
source = "Lo 2022 p.1663: the primary analysis excludes survey non-respondents"
alternatives = ["non-walker", "walker"]

[knees.min_kl]
value = 2
status = "confirmed"
source = "Lo 2022 p.1661; Table 1 (KL 2-4 only)"

[exposure.walker_item]
value = "V10WLKAR4"
status = "assumed"
source = "AllClinical10 Q48; Lo 2022 p.1662 describes the screener as 'walk for exercise at least 10 times'"
rationale = "Only age-50+ walking item in the release; its wording adds 'for at least 20 minutes within a given day'"

[exposure.missing_walking_as]
value = "non-walker"
status = "confirmed"
source = "Lo 2022 p.1662 (n = 17 respondents with missing walking data coded as non-walkers)"
alternatives = ["walker", "exclude"]

[exposure.category_midpoints]
value = { years = [3.0, 8.0, 15.5, 20.0], months = [2.5, 6.5, 10.5], times = [2.0, 6.0, 10.0] }
status = "open"
source = "Lo 2022 p.1662: 'using the median value for the answers'"
rationale = "Codes 1-4 (years 1-5, 6-10, 11-20, >20), 1-3 (months 1-4, 5-8, 9-12), 1-3 (times 1-3, 4-8, 9+); 20 x 10.5 x 10 reproduces the published max of 2,100, but the published min of 13 is unexplained"

[outcomes.followup_visits]
value = ["06", "05"]
status = "confirmed"
source = "Lo 2022 p.1662: 48-month data, with 36-month data carried forward when missing"

[outcomes.pain_baseline_items]
value = "P01KP{side}12CV"
status = "assumed"
source = "Lo 2022 p.1661 question wording matches screening-visit Q15a/Q18a"
rationale = "Check against 676 of 1,808 knees with baseline frequent pain"
alternatives = ["P02KPN{side}CV"]

[outcomes.pain_followup_items]
value = "V{visit}KP{side}12CV"
status = "assumed"
source = "Lo 2022 p.1661; AllClinical follow-up interview Q6a/Q8a"
rationale = "Check against 729 of 1,808 knees with frequent pain at 48 months"

[outcomes.replacement_is_structural_worsening]
value = true
status = "assumed"
source = "Lo 2022 p.1663: KL4 and JSN3 knees were kept because an interval replacement would count as worsening"

[outcomes.replaced_knee_pain]
value = "keep"
status = "open"
source = "Not stated"
alternatives = ["exclude"]

[outcomes.replacement_window]
value = "followup_visit_days"
status = "assumed"
source = "Lo 2022 Table 1: replacements over the 48-month follow-up (77 of 1,808 knees)"
rationale = "A replacement counts if its day is on or before the participant's follow-up visit day (V06VISDYS, else V05VISDYS, else nominal 48 months)"

[alignment.source]
value = "cooke"
status = "assumed"
source = "Lo 2022 refs 13-14 (Sled, Cooke); film counts by visit match p.1662"
alternatives = ["duryea"]

[alignment.visits]
value = ["01", "03", "05", "06"]
status = "confirmed"
source = "Lo 2022 p.1662: long-limb films obtained at months 12, 24, 36 and 48"

[alignment.pick]
value = "earliest"
status = "assumed"
source = "Lo 2022 p.1662 (one film per knee; timing varied)"
rationale = "Check against 1,484 knees with films"
alternatives = ["latest"]

[alignment.varus_max]
value = -2.0
status = "confirmed"
source = "Lo 2022 p.1662"

[alignment.valgus_min]
value = 2.0
status = "confirmed"
source = "Lo 2022 p.1662"

[model.covariates]
value = ["age", "sex", "kl0"]
status = "confirmed"
source = "Lo 2022 Table 2 footnote"

[model.corstr]
value = "exchangeable"
status = "open"
source = "Not stated (GEE, Lo 2022 p.1662)"
alternatives = ["independence"]

[model.kl_covariate]
value = "factor"
status = "open"
source = "Not stated"
alternatives = ["numeric"]

[variants.missing_as_nonwalkers]
description = "Supplementary Table 2: survey non-respondents imputed as non-walkers"
set = { "cohort.impute_missing_walking" = "non-walker" }

[variants.missing_as_walkers]
description = "Supplementary Table 3: survey non-respondents imputed as walkers"
set = { "cohort.impute_missing_walking" = "walker" }

[variants.replacement_not_worsening]
description = "Sensitivity: an interval replacement does not count as structural worsening"
set = { "outcomes.replacement_is_structural_worsening" = false }

[variants.corstr_independence]
description = "Sensitivity: independence working correlation"
set = { "model.corstr" = "independence" }
```

`analyses/lo2022_walking/published.toml`:
```toml
# Published values: Lo et al. 2022 (Arthritis Rheumatol 74:1660-7) and Supplementary
# Tables 1-3. Integers are counts, floats are means, inline tables are odds ratios
# {or, lo, hi, sig} (sig = bold/footnoted as significant). Graded by oai.replication.

[related]  # metric prefix -> assumptions that bear on it (longest prefix wins)
"flow.age50" = ["cohort.min_age"]
"flow.baseline_xray" = ["cohort.reading_project"]
"flow.roa" = ["cohort.reading_project", "knees.min_kl"]
"flow.before_survey" = ["cohort.survey_start"]
"flow.no_visit96" = ["cohort.survey_start"]
"flow.no_survey" = ["cohort.survey_completed_items"]
"flow.no_followup" = ["cohort.reading_project", "outcomes.followup_visits"]
"flow.knees" = ["cohort.reading_project", "outcomes.followup_visits", "knees.min_kl"]
"flow.fallback36" = ["outcomes.followup_visits"]
"s1.before_survey" = ["cohort.survey_start"]
"s1.no_visit96" = ["cohort.survey_start"]
"s1.no_survey" = ["cohort.survey_completed_items"]
"s1.no_followup" = ["cohort.reading_project", "outcomes.followup_visits"]
"t1" = ["exposure.walker_item", "exposure.missing_walking_as"]
"t1.walk_days_min" = ["exposure.category_midpoints"]
"t1.walk_days_p25" = ["exposure.category_midpoints"]
"t1.walk_days_median" = ["exposure.category_midpoints"]
"t1.walk_days_p75" = ["exposure.category_midpoints"]
"t1.walk_days_max" = ["exposure.category_midpoints"]
"t1.pain0" = ["outcomes.pain_baseline_items", "exposure.walker_item"]
"t1.pain48" = ["outcomes.pain_followup_items", "outcomes.followup_visits", "exposure.walker_item"]
"t1.replaced48" = ["outcomes.replacement_window", "exposure.walker_item"]
"t1.align_knees" = ["alignment.source", "alignment.pick"]
"t1.varus" = ["alignment.source", "alignment.pick"]
"t1.neutral" = ["alignment.source", "alignment.pick"]
"t1.valgus" = ["alignment.source", "alignment.pick"]
"t2.new_pain" = ["outcomes.pain_baseline_items", "outcomes.pain_followup_items", "exposure.walker_item", "model.corstr"]
"t2.improved_pain" = ["outcomes.pain_baseline_items", "outcomes.pain_followup_items", "exposure.walker_item", "model.corstr"]
"t2.kl_worse" = ["outcomes.replacement_is_structural_worsening", "exposure.walker_item", "model.corstr", "model.kl_covariate"]
"t2.jsn_worse" = ["outcomes.replacement_is_structural_worsening", "exposure.walker_item", "model.corstr", "model.kl_covariate"]
"t3" = ["alignment.source", "alignment.pick", "exposure.walker_item"]

[default]
"flow.all.persons" = 4796
"flow.age50.persons" = 4247
"flow.baseline_xray.persons" = 3980
"flow.roa.persons" = 2356
"flow.before_survey.excluded_persons" = 417
"flow.before_survey.excluded_knees" = 644
"flow.before_survey.persons" = 1939
"flow.no_visit96.excluded_persons" = 346
"flow.no_visit96.excluded_knees" = 553
"flow.no_visit96.persons" = 1593
"flow.no_survey.excluded_persons" = 337
"flow.no_survey.excluded_knees" = 513
"flow.no_survey.persons" = 1256
"flow.no_followup.excluded_persons" = 44
"flow.no_followup.excluded_knees" = 73
"flow.no_followup.persons" = 1212
"flow.knees" = 1808
"flow.fallback36.persons" = 151
"s1.before_survey.male" = 130
"s1.before_survey.age_mean" = 63.5
"s1.before_survey.bmi_mean" = 29.4
"s1.no_visit96.male" = 148
"s1.no_visit96.age_mean" = 65.5
"s1.no_visit96.bmi_mean" = 30.0
"s1.no_survey.male" = 137
"s1.no_survey.age_mean" = 65.5
"s1.no_survey.bmi_mean" = 29.6
"s1.no_followup.male" = 14
"s1.no_followup.age_mean" = 63.7
"s1.no_followup.bmi_mean" = 30.4
"t1.persons.nonwalkers" = 325
"t1.persons.walkers" = 887
"t1.persons.all" = 1212
"t1.age_mean.nonwalkers" = 64.5
"t1.age_mean.walkers" = 62.7
"t1.age_mean.all" = 63.2
"t1.male.nonwalkers" = 167
"t1.male.walkers" = 381
"t1.male.all" = 548
"t1.bmi_mean.nonwalkers" = 30.2
"t1.bmi_mean.walkers" = 29.2
"t1.bmi_mean.all" = 29.4
"t1.walk_days_min.walkers" = 13
"t1.walk_days_p25.walkers" = 337
"t1.walk_days_median.walkers" = 845
"t1.walk_days_p75.walkers" = 1417
"t1.walk_days_max.walkers" = 2100
"t1.knees.nonwalkers" = 503
"t1.knees.walkers" = 1305
"t1.knees.all" = 1808
"t1.kl2.nonwalkers" = 284
"t1.kl2.walkers" = 869
"t1.kl2.all" = 1153
"t1.kl3.nonwalkers" = 175
"t1.kl3.walkers" = 354
"t1.kl3.all" = 529
"t1.kl4.nonwalkers" = 44
"t1.kl4.walkers" = 82
"t1.kl4.all" = 126
"t1.jsm0.nonwalkers" = 151
"t1.jsm0.walkers" = 487
"t1.jsm0.all" = 638
"t1.jsm1.nonwalkers" = 173
"t1.jsm1.walkers" = 475
"t1.jsm1.all" = 648
"t1.jsm2.nonwalkers" = 144
"t1.jsm2.walkers" = 293
"t1.jsm2.all" = 437
"t1.jsm3.nonwalkers" = 35
"t1.jsm3.walkers" = 50
"t1.jsm3.all" = 85
"t1.pain0.nonwalkers" = 223
"t1.pain0.walkers" = 453
"t1.pain0.all" = 676
"t1.align_knees.nonwalkers" = 418
"t1.align_knees.walkers" = 1066
"t1.align_knees.all" = 1484
"t1.varus.nonwalkers" = 227
"t1.varus.walkers" = 480
"t1.varus.all" = 707
"t1.neutral.nonwalkers" = 129
"t1.neutral.walkers" = 407
"t1.neutral.all" = 536
"t1.valgus.nonwalkers" = 62
"t1.valgus.walkers" = 179
"t1.valgus.all" = 241
"t1.pain48.nonwalkers" = 233
"t1.pain48.walkers" = 496
"t1.pain48.all" = 729
"t1.replaced48.nonwalkers" = 27
"t1.replaced48.walkers" = 50
"t1.replaced48.all" = 77
"t2.new_pain.nonwalkers.events" = 103
"t2.new_pain.nonwalkers.n" = 280
"t2.new_pain.walkers.events" = 223
"t2.new_pain.walkers.n" = 852
"t2.new_pain.or_unadj" = { or = 0.6, lo = 0.4, hi = 0.8, sig = true }
"t2.new_pain.or_adj" = { or = 0.6, lo = 0.4, hi = 0.8, sig = true }
"t2.kl_worse.nonwalkers.events" = 105
"t2.kl_worse.nonwalkers.n" = 503
"t2.kl_worse.walkers.events" = 234
"t2.kl_worse.walkers.n" = 1305
"t2.kl_worse.or_unadj" = { or = 0.8, lo = 0.6, hi = 1.1, sig = false }
"t2.kl_worse.or_adj" = { or = 0.8, lo = 0.6, hi = 1.1, sig = false }
"t2.jsn_worse.nonwalkers.events" = 137
"t2.jsn_worse.nonwalkers.n" = 503
"t2.jsn_worse.walkers.events" = 281
"t2.jsn_worse.walkers.n" = 1305
"t2.jsn_worse.or_unadj" = { or = 0.7, lo = 0.6, hi = 1.0, sig = true }
"t2.jsn_worse.or_adj" = { or = 0.8, lo = 0.6, hi = 1.0, sig = true }
"t2.improved_pain.nonwalkers.events" = 93
"t2.improved_pain.nonwalkers.n" = 223
"t2.improved_pain.walkers.events" = 180
"t2.improved_pain.walkers.n" = 453
"t2.improved_pain.or_unadj" = { or = 0.9, lo = 0.7, hi = 1.3, sig = false }
"t2.improved_pain.or_adj" = { or = 0.8, lo = 0.6, hi = 1.2, sig = false }
"t3.new_pain.varus.nonwalkers.events" = 47
"t3.new_pain.varus.nonwalkers.n" = 120
"t3.new_pain.varus.walkers.events" = 82
"t3.new_pain.varus.walkers.n" = 290
"t3.new_pain.neutral.nonwalkers.events" = 28
"t3.new_pain.neutral.nonwalkers.n" = 77
"t3.new_pain.neutral.walkers.events" = 60
"t3.new_pain.neutral.walkers.n" = 266
"t3.new_pain.valgus.nonwalkers.events" = 9
"t3.new_pain.valgus.nonwalkers.n" = 31
"t3.new_pain.valgus.walkers.events" = 40
"t3.new_pain.valgus.walkers.n" = 122
"t3.kl_worse.varus.nonwalkers.events" = 59
"t3.kl_worse.varus.nonwalkers.n" = 227
"t3.kl_worse.varus.walkers.events" = 97
"t3.kl_worse.varus.walkers.n" = 480
"t3.kl_worse.neutral.nonwalkers.events" = 13
"t3.kl_worse.neutral.nonwalkers.n" = 129
"t3.kl_worse.neutral.walkers.events" = 58
"t3.kl_worse.neutral.walkers.n" = 407
"t3.kl_worse.valgus.nonwalkers.events" = 9
"t3.kl_worse.valgus.nonwalkers.n" = 62
"t3.kl_worse.valgus.walkers.events" = 35
"t3.kl_worse.valgus.walkers.n" = 179
"t3.jsn_worse.varus.nonwalkers.events" = 88
"t3.jsn_worse.varus.nonwalkers.n" = 227
"t3.jsn_worse.varus.walkers.events" = 149
"t3.jsn_worse.varus.walkers.n" = 480
"t3.jsn_worse.neutral.nonwalkers.events" = 14
"t3.jsn_worse.neutral.nonwalkers.n" = 129
"t3.jsn_worse.neutral.walkers.events" = 69
"t3.jsn_worse.neutral.walkers.n" = 407
"t3.jsn_worse.valgus.nonwalkers.events" = 3
"t3.jsn_worse.valgus.nonwalkers.n" = 62
"t3.jsn_worse.valgus.walkers.events" = 16
"t3.jsn_worse.valgus.walkers.n" = 179
"t3.improved_pain.varus.nonwalkers.events" = 43
"t3.improved_pain.varus.nonwalkers.n" = 107
"t3.improved_pain.varus.walkers.events" = 74
"t3.improved_pain.varus.walkers.n" = 190
"t3.improved_pain.neutral.nonwalkers.events" = 20
"t3.improved_pain.neutral.nonwalkers.n" = 52
"t3.improved_pain.neutral.walkers.events" = 66
"t3.improved_pain.neutral.walkers.n" = 141
"t3.improved_pain.valgus.nonwalkers.events" = 15
"t3.improved_pain.valgus.nonwalkers.n" = 31
"t3.improved_pain.valgus.walkers.events" = 20
"t3.improved_pain.valgus.walkers.n" = 57

[missing_as_nonwalkers]
"t2.new_pain.nonwalkers.events" = 324
"t2.new_pain.nonwalkers.n" = 1004
"t2.new_pain.walkers.events" = 223
"t2.new_pain.walkers.n" = 852
"t2.new_pain.or_unadj" = { or = 0.7, lo = 0.6, hi = 0.9, sig = true }
"t2.new_pain.or_adj" = { or = 0.8, lo = 0.6, hi = 0.9, sig = true }
"t2.kl_worse.nonwalkers.events" = 427
"t2.kl_worse.nonwalkers.n" = 1909
"t2.kl_worse.walkers.events" = 234
"t2.kl_worse.walkers.n" = 1305
"t2.kl_worse.or_unadj" = { or = 0.8, lo = 0.6, hi = 0.9, sig = true }
"t2.kl_worse.or_adj" = { or = 0.8, lo = 0.7, hi = 1.0, sig = true }
"t2.jsn_worse.nonwalkers.events" = 522
"t2.jsn_worse.nonwalkers.n" = 1909
"t2.jsn_worse.walkers.events" = 281
"t2.jsn_worse.walkers.n" = 1305
"t2.jsn_worse.or_unadj" = { or = 0.7, lo = 0.6, hi = 0.9, sig = true }
"t2.jsn_worse.or_adj" = { or = 0.8, lo = 0.7, hi = 1.0, sig = true }
"t2.improved_pain.nonwalkers.events" = 338
"t2.improved_pain.nonwalkers.n" = 896
"t2.improved_pain.walkers.events" = 180
"t2.improved_pain.walkers.n" = 453
"t2.improved_pain.or_unadj" = { or = 1.1, lo = 0.8, hi = 1.4, sig = false }
"t2.improved_pain.or_adj" = { or = 1.0, lo = 0.8, hi = 1.3, sig = false }

[missing_as_walkers]
"t2.new_pain.nonwalkers.events" = 103
"t2.new_pain.nonwalkers.n" = 280
"t2.new_pain.walkers.events" = 444
"t2.new_pain.walkers.n" = 1576
"t2.new_pain.or_unadj" = { or = 0.7, lo = 0.5, hi = 0.9, sig = true }
"t2.new_pain.or_adj" = { or = 0.7, lo = 0.5, hi = 0.9, sig = true }
"t2.kl_worse.nonwalkers.events" = 105
"t2.kl_worse.nonwalkers.n" = 503
"t2.kl_worse.walkers.events" = 556
"t2.kl_worse.walkers.n" = 2711
"t2.kl_worse.or_unadj" = { or = 1.0, lo = 0.8, hi = 1.3, sig = false }
"t2.kl_worse.or_adj" = { or = 1.0, lo = 0.8, hi = 1.2, sig = false }
"t2.jsn_worse.nonwalkers.events" = 137
"t2.jsn_worse.nonwalkers.n" = 503
"t2.jsn_worse.walkers.events" = 666
"t2.jsn_worse.walkers.n" = 2711
"t2.jsn_worse.or_unadj" = { or = 0.9, lo = 0.7, hi = 1.1, sig = false }
"t2.jsn_worse.or_adj" = { or = 0.9, lo = 0.7, hi = 1.1, sig = false }
"t2.improved_pain.nonwalkers.events" = 93
"t2.improved_pain.nonwalkers.n" = 223
"t2.improved_pain.walkers.events" = 425
"t2.improved_pain.walkers.n" = 1126
"t2.improved_pain.or_unadj" = { or = 0.9, lo = 0.6, hi = 1.2, sig = false }
"t2.improved_pain.or_adj" = { or = 0.9, lo = 0.6, hi = 1.2, sig = false }
```

`analyses/lo2022_walking/README.md`:
```markdown
# lo2022_walking

Replication of Lo GH et al. *Association Between Walking for Exercise and Symptomatic
and Structural Progression in Individuals With Knee Osteoarthritis.* Arthritis Rheumatol
2022;74:1660–7 (doi:10.1002/art.42241). It tests whether the suite reproduces a
published OAI analysis.

| Step | Lang | Output |
|---|---|---|
| `cohort` (`build_frame.py`) | Python | knee frame, `flow.csv`, `table1.csv`, `table3.csv`, `metrics_cohort.csv` |
| `models` (`models.R`) | R | `table2.csv`, `metrics_models.csv` (GEE logistic, knees clustered on participant) |
| `compare` (`compare.py`) | Python | `comparison.csv`, a graded verdict against `published.toml` |

```bash
oai run lo2022_walking                                  # the paper's primary analysis
oai run lo2022_walking --variant missing_as_nonwalkers  # Supplementary Table 2
oai run lo2022_walking --variant missing_as_walkers     # Supplementary Table 3
oai assumptions lo2022_walking                          # what was assumed, and why
```

Every analytic choice is in [assumptions.toml](assumptions.toml) (rendered as
[ASSUMPTIONS.md](ASSUMPTIONS.md)). Results stay in `$OAI_RESULTS_DIR` and are not committed.
```

Placeholder entry scripts (replaced in Tasks 8, 10 and 11):

`analyses/lo2022_walking/build_frame.py`:
```python
import sys

sys.exit("lo2022_walking/build_frame.py: implemented in plan Task 8")
```

`analyses/lo2022_walking/models.R`:
```r
stop("lo2022_walking/models.R: implemented in plan Task 10")
```

`analyses/lo2022_walking/compare.py`:
```python
import sys

sys.exit("lo2022_walking/compare.py: implemented in plan Task 11")
```

- [ ] **Step 4: Generate the ledger and run tests**

Run: `uv run oai assumptions lo2022_walking --write && uv run pytest -q && uv run pytest -m realdata -q tests/test_analyses.py`
Expected: `Wrote …/ASSUMPTIONS.md`; all tests pass, including `test_ledger_is_in_sync[lo2022_walking]`; the realdata input-resolution test passes for `lo2022_walking`.

- [ ] **Step 5: Commit**

```bash
git add analyses/lo2022_walking tests/test_analyses.py tests/test_lo2022_definition.py
git commit -m "feat: define lo2022_walking replication with assumptions and published targets" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Cohort, exposure and outcomes (`lo2022.build`)

**Files:**
- Create: `analyses/lo2022_walking/lo2022.py`, `tests/test_lo2022_build.py`
- Modify: `analyses/lo2022_walking/build_frame.py` (replace the placeholder)

**Interfaces:**
- Consumes: `oai.derive.knee` (Tasks 5–6), `Resolved` (Task 1), `oai.visits.nominal_month`.
- Produces:
  - `Built(knees, flow, fallback_visit)`, where `knees` columns include `ID, SIDE, walker, age, sex, bmi, kl0, jsm0, klf, jsmf, source_visit, replaced, pain0, painf, hka, alignment, walk_times, kl_worse, jsn_worse, new_pain, improved_pain`, and `flow` columns are `step, persons, excluded_persons, excluded_knees, male, age_mean, bmi_mean`.
  - `build(A: Resolved) -> Built`
  - Constants `FLOW_STEPS`, `SURVEY_STEPS`, `S1_STEPS`, `OUTCOMES`, `GROUPS`.

- [ ] **Step 1: Write the failing tests**

`tests/test_lo2022_build.py`:
```python
import sys
from pathlib import Path

import polars as pl
import pytest

from oai.assumptions import load_assumptions
from oai.catalog import catalog_for
from oai.config import get_settings

REPO = Path(__file__).resolve().parents[1]
ANALYSIS = REPO / "analyses" / "lo2022_walking"
KNEE_DATA = Path(__file__).parent / "fixtures" / "oai_knee"
sys.path.insert(0, str(ANALYSIS))
import lo2022  # noqa: E402


@pytest.fixture(autouse=True)
def knee_release(isolated_settings, monkeypatch):
    monkeypatch.setenv("OAI_DATA_DIR", str(KNEE_DATA))
    get_settings.cache_clear()
    catalog_for.cache_clear()


def built(variant=None, **overrides):
    resolved = load_assumptions(ANALYSIS).resolve("lo2022_walking", variant, overrides)
    return lo2022.build(resolved)


def knee(df, id_, side):
    return df.filter((pl.col("ID") == id_) & (pl.col("SIDE") == side)).row(0, named=True)


def test_flow_matches_synthetic_design():
    b = built()
    flow = {r["step"]: r for r in b.flow.iter_rows(named=True)}
    assert [s for s in flow] == list(lo2022.FLOW_STEPS)
    assert {s: flow[s]["persons"] for s in flow} == {
        "all": 10, "age50": 9, "baseline_xray": 8, "roa": 7,
        "before_survey": 6, "no_visit96": 5, "no_survey": 4, "no_followup": 3,
    }
    assert flow["before_survey"]["excluded_knees"] == 1
    assert flow["no_visit96"]["male"] == 1  # 1000006
    assert sorted(b.knees.select("ID", "SIDE").rows()) == [
        (1000001, "R"), (1000009, "L"), (1000009, "R"), (1000010, "R"),
    ]


def test_exposure_coding():
    walkers = dict(built().knees.unique("ID").select("ID", "walker").iter_rows())
    assert walkers == {1000001: True, 1000009: False, 1000010: False}  # 1000010: missing -> non-walker


def test_missing_walking_can_be_excluded():
    ids = built(None, **{"exposure.missing_walking_as": "exclude"}).knees["ID"].unique().to_list()
    assert 1000010 not in ids


def test_structural_outcomes_and_fallback():
    k = built().knees
    assert (knee(k, 1000001, "R")["kl_worse"], knee(k, 1000001, "R")["jsn_worse"]) == (True, True)
    row = knee(k, 1000009, "R")
    assert (row["source_visit"], row["kl_worse"], row["jsn_worse"]) == ("05", False, True)
    assert (knee(k, 1000010, "R")["kl_worse"], knee(k, 1000010, "R")["jsn_worse"]) == (False, False)


def test_replaced_knee_without_reading_is_included():
    row = knee(built().knees, 1000009, "L")
    assert (row["replaced"], row["klf"], row["kl_worse"], row["jsn_worse"]) == (True, None, True, True)
    off = knee(built("replacement_not_worsening").knees, 1000009, "L")
    assert (off["kl_worse"], off["jsn_worse"]) == (None, None)


def test_pain_outcomes():
    k = built().knees
    assert (knee(k, 1000001, "R")["new_pain"], knee(k, 1000001, "R")["improved_pain"]) == (True, None)
    assert (knee(k, 1000009, "R")["new_pain"], knee(k, 1000009, "R")["improved_pain"]) == (None, True)
    assert knee(k, 1000009, "L")["new_pain"] is True  # replaced knee, pain kept
    excluded = built(None, **{"outcomes.replaced_knee_pain": "exclude"}).knees
    assert knee(excluded, 1000009, "L")["new_pain"] is None


def test_blank_baseline_pain_is_excluded_from_pain_outcomes():
    row = knee(built().knees, 1000010, "R")
    assert (row["pain0"], row["new_pain"], row["improved_pain"]) == (None, None, None)


def test_alignment_and_walking_amount():
    k = built().knees
    assert knee(k, 1000001, "R")["alignment"] == "varus"
    assert knee(k, 1000009, "R")["alignment"] == "valgus"
    assert knee(k, 1000010, "R")["alignment"] == "neutral"
    assert knee(k, 1000009, "L")["alignment"] is None
    assert knee(k, 1000001, "R")["walk_times"] == 2100.0  # >20 y x 9-12 mo x 9+ times
    assert knee(k, 1000009, "R")["walk_times"] == 0.0


def test_imputation_variants_add_survey_nonrespondents_with_followup():
    for variant, expected in (("missing_as_nonwalkers", False), ("missing_as_walkers", True)):
        k = built(variant).knees
        assert knee(k, 1000006, "R")["walker"] is expected
        assert k["ID"].n_unique() == 4
    assert 1000006 not in built().knees["ID"].to_list()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_lo2022_build.py -q`
Expected: collection error — `No module named 'lo2022'`.

- [ ] **Step 3: Implement**

`analyses/lo2022_walking/lo2022.py`:
```python
"""Lo et al. 2022 (Arthritis Rheumatol 74:1660): cohort, exposure, outcomes, descriptives.

Every analytic choice comes from assumptions.toml through `A[...]`; see ASSUMPTIONS.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import polars as pl

from oai.assumptions import Resolved
from oai.derive.knee import (
    KNEE_KEYS,
    find_col,
    frequent_knee_pain,
    knee_alignment,
    knee_replacement,
    visit_days,
    with_fallback,
    xray_readings,
)
from oai.loader import read_table
from oai.visits import nominal_month

FLOW_STEPS = (
    "all", "age50", "baseline_xray", "roa", "before_survey", "no_visit96", "no_survey", "no_followup",
)
SURVEY_STEPS = ("before_survey", "no_visit96", "no_survey")
S1_STEPS = (*SURVEY_STEPS, "no_followup")
OUTCOMES = ("new_pain", "kl_worse", "jsn_worse", "improved_pain")
GROUPS = ("walkers", "nonwalkers", "all")
ALIGNMENTS = ("varus", "neutral", "valgus")
AMOUNT_ITEMS = {"years": "V10WKYRAR4", "months": "V10WKMOAR4", "times": "V10WKTMAR4"}
DAYS_PER_MONTH = 365.25 / 12
WALKER_VALUES = {"non-walker": False, "walker": True, "exclude": None}


@dataclass
class Built:
    knees: pl.DataFrame
    flow: pl.DataFrame
    fallback_visit: str | None


def _select(df: pl.DataFrame, **columns: str) -> pl.DataFrame:
    return df.select([pl.col(find_col(df, src)).alias(dst) for dst, src in columns.items()])


def _people(A: Resolved) -> pl.DataFrame:
    enrollees = _select(read_table("enrollees"), ID="ID", sex="P02SEX")
    baseline = _select(read_table("allclinical", "00"), ID="ID", age="V00AGE", bmi="P01BMI")
    ac10 = read_table("allclinical", "10")
    answered = pl.any_horizontal(
        [pl.col(find_col(ac10, item)).is_not_null() for item in A["cohort.survey_completed_items"]]
    )
    survey = ac10.select(
        pl.col(find_col(ac10, "ID")).alias("ID"),
        pl.col(find_col(ac10, "V10FVDATE")).cast(pl.String).str.to_date("%m/%d/%Y", strict=False).alias("visit96"),
        answered.alias("answered"),
        pl.col(find_col(ac10, A["exposure.walker_item"])).alias("walk_item"),
        *[pl.col(find_col(ac10, item)).alias(f"walk_{name}") for name, item in AMOUNT_ITEMS.items()],
    )
    return (
        enrollees.join(baseline, on="ID", how="left")
        .join(survey, on="ID", how="left")
        .with_columns(
            pl.col("age").cast(pl.Float64),
            pl.col("bmi").cast(pl.Float64),
            pl.col("answered").fill_null(False),
        )
    )


def _followup_days(ids: pl.DataFrame, visits: list[str]) -> pl.DataFrame:
    out = ids
    for visit in visits:
        out = out.join(visit_days(visit).rename({"days": f"d{visit}"}), on="ID", how="left")
    nominal = nominal_month(visits[0]) * DAYS_PER_MONTH
    return out.select("ID", pl.coalesce([pl.col(f"d{v}") for v in visits] + [pl.lit(nominal)]).alias("days"))


def _flow_row(step: str, remaining: pl.DataFrame, excluded: pl.DataFrame, oa: pl.DataFrame) -> dict:
    ids = excluded["ID"].implode()
    return {
        "step": step,
        "persons": remaining.height,
        "excluded_persons": excluded.height,
        "excluded_knees": oa.filter(pl.col("ID").is_in(ids)).height,
        "male": int((excluded["sex"] == 1).sum()),
        "age_mean": excluded["age"].mean(),
        "bmi_mean": excluded["bmi"].mean(),
    }


def _walk_amount(name: str, midpoints: list[float]) -> pl.Expr:
    mapping = {code + 1: float(value) for code, value in enumerate(midpoints)}
    return pl.col(f"walk_{name}").replace_strict(mapping, default=None, return_dtype=pl.Float64)


def build(A: Resolved) -> Built:
    project, min_kl = A["cohort.reading_project"], A["knees.min_kl"]
    fu_visits = list(A["outcomes.followup_visits"])
    people = _people(A)

    baseline = xray_readings(["00"], project=project).filter(pl.col("KL").is_not_null())
    at_baseline = knee_replacement().select(*KNEE_KEYS, "replaced_at_baseline")
    oa = (
        baseline.join(at_baseline, on=list(KNEE_KEYS), how="left")
        .filter(~pl.col("replaced_at_baseline").fill_null(False) & (pl.col("KL") >= min_kl))
        .select(*KNEE_KEYS, pl.col("KL").alias("kl0"), pl.col("JSM").alias("jsm0"))
    )
    followup = with_fallback(
        *[xray_readings([v], project=project) for v in fu_visits], value_cols=["KL", "JSM"]
    ).select(*KNEE_KEYS, pl.col("KL").alias("klf"), pl.col("JSM").alias("jsmf"), "source_visit")
    replaced = knee_replacement(_followup_days(people.select("ID"), fu_visits)).select(*KNEE_KEYS, "replaced")
    knees = (
        oa.join(followup, on=list(KNEE_KEYS), how="left")
        .join(replaced, on=list(KNEE_KEYS), how="left")
        .with_columns(pl.col("replaced").fill_null(False))
        .with_columns((pl.col("source_visit").is_not_null() | pl.col("replaced")).alias("has_followup"))
    )

    # Person-level flow (Figure 1 and Supplementary Table 1).
    survey_start = date.fromisoformat(A["cohort.survey_start"])
    rules = {
        "age50": pl.col("age") >= A["cohort.min_age"],
        "baseline_xray": pl.col("ID").is_in(baseline["ID"].unique().implode()),
        "roa": pl.col("ID").is_in(oa["ID"].unique().implode()),
        "before_survey": ~(pl.col("visit96") < survey_start).fill_null(False),
        "no_visit96": pl.col("visit96").is_not_null(),
        "no_survey": pl.col("answered"),
        "no_followup": pl.col("ID").is_in(knees.filter("has_followup")["ID"].unique().implode()),
    }
    current = people
    flow = [_flow_row("all", people, people.clear(), oa)]
    survey_excluded = []
    for step, keep in rules.items():
        excluded = current.filter(~keep.fill_null(False))
        current = current.filter(keep.fill_null(False))
        flow.append(_flow_row(step, current, excluded, oa))
        if step in SURVEY_STEPS:
            survey_excluded.append(excluded)

    missing_as = WALKER_VALUES[A["exposure.missing_walking_as"]]
    respondents = current.with_columns(
        pl.when(pl.col("walk_item") == 1).then(True)
        .when(pl.col("walk_item") == 0).then(False)
        .otherwise(pl.lit(missing_as, dtype=pl.Boolean))
        .alias("walker")
    )
    cohort = [respondents]
    impute = A["cohort.impute_missing_walking"]
    if impute != "none":
        imputed = pl.concat(survey_excluded).filter(rules["no_followup"])
        cohort.append(imputed.with_columns(pl.lit(WALKER_VALUES[impute], dtype=pl.Boolean).alias("walker")))
    persons = pl.concat(cohort).filter(pl.col("walker").is_not_null())

    # Pain, alignment and outcomes (knee level).
    pain0 = frequent_knee_pain("00", A["outcomes.pain_baseline_items"]).select(
        *KNEE_KEYS, pl.col("frequent_pain").alias("pain0")
    )
    painf = with_fallback(
        *[frequent_knee_pain(v, A["outcomes.pain_followup_items"]) for v in fu_visits],
        value_cols=["frequent_pain"],
    ).select(*KNEE_KEYS, pl.col("frequent_pain").alias("painf"))
    films = knee_alignment(
        source=A["alignment.source"], visits=A["alignment.visits"], pick=A["alignment.pick"]
    ).select(*KNEE_KEYS, "hka")
    alignment = (
        pl.when(pl.col("hka") <= A["alignment.varus_max"]).then(pl.lit("varus"))
        .when(pl.col("hka") >= A["alignment.valgus_min"]).then(pl.lit("valgus"))
        .when(pl.col("hka").is_not_null()).then(pl.lit("neutral"))
        .alias("alignment")
    )
    structural = pl.col("replaced") & pl.lit(A["outcomes.replacement_is_structural_worsening"])
    pain_counts = (
        pl.lit(True) if A["outcomes.replaced_knee_pain"] == "keep" else ~pl.col("replaced")
    )
    midpoints = A["exposure.category_midpoints"]
    walk_times = _walk_amount("years", midpoints["years"]) * _walk_amount("months", midpoints["months"]) * _walk_amount("times", midpoints["times"])

    frame = (
        knees.filter("has_followup")
        .join(persons.select("ID", "walker", "age", "sex", "bmi", *[f"walk_{n}" for n in AMOUNT_ITEMS]), on="ID", how="inner")
        .join(pain0, on=list(KNEE_KEYS), how="left")
        .join(painf, on=list(KNEE_KEYS), how="left")
        .join(films, on=list(KNEE_KEYS), how="left")
        .with_columns(
            alignment,
            pl.when(pl.col("walker")).then(walk_times).otherwise(0.0).alias("walk_times"),
            pl.when(structural).then(True).otherwise(pl.col("klf") > pl.col("kl0")).alias("kl_worse"),
            pl.when(structural).then(True).otherwise(pl.col("jsmf") > pl.col("jsm0")).alias("jsn_worse"),
            pl.when(pl.col("pain0").not_() & pain_counts).then(pl.col("painf")).alias("new_pain"),
            pl.when(pl.col("pain0") & pain_counts).then(pl.col("painf").not_()).alias("improved_pain"),
        )
        .drop("has_followup", *[f"walk_{n}" for n in AMOUNT_ITEMS])
        .sort(["ID", "SIDE"])
    )
    fallback_visit = fu_visits[-1] if len(fu_visits) > 1 else None
    return Built(knees=frame, flow=pl.DataFrame(flow), fallback_visit=fallback_visit)
```

`analyses/lo2022_walking/build_frame.py` (replace the placeholder):
```python
"""Step `cohort`: build the Lo 2022 knee frame and flow (Table 1/3 are added in Task 9)."""

import os
from pathlib import Path

from lo2022 import build

from oai.assumptions import current

A = current()
built = build(A)
frames, results = Path(os.environ["OAI_FRAME_DIR"]), Path(os.environ["OAI_RESULTS_DIR"])
built.knees.write_parquet(frames / "frame.parquet")
built.flow.write_csv(results / "flow.csv")
print(built.flow)
```

- [ ] **Step 4: Run tests**

Run: `uv run ruff format -q . && uv run ruff check --fix -q; uv run pytest -q`
Expected: all pass (the 11 new tests plus existing ones).

- [ ] **Step 5: Commit**

```bash
git add analyses/lo2022_walking/lo2022.py analyses/lo2022_walking/build_frame.py tests/test_lo2022_build.py
git commit -m "feat: build Lo 2022 cohort, exposure and knee outcomes" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Table 1, Table 3 and cohort metrics

**Files:**
- Modify: `analyses/lo2022_walking/lo2022.py`, `analyses/lo2022_walking/build_frame.py`, `tests/test_lo2022_build.py`

**Interfaces:**
- Produces: `flow_metrics(built) -> DataFrame[metric, value]`, `table1(built) -> DataFrame[metric, value]`, `table3(built) -> DataFrame[metric, value]`. The metric keys follow `published.toml` (`flow.*`, `s1.*`, `t1.*`, `t3.*`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_lo2022_build.py`:
```python
def metrics(df):
    return dict(df.iter_rows())


def test_flow_metrics_keys_and_values():
    m = metrics(lo2022.flow_metrics(built()))
    assert m["flow.no_followup.persons"] == 3
    assert m["flow.before_survey.excluded_persons"] == 1
    assert m["s1.no_visit96.male"] == 1
    assert m["flow.knees"] == 4
    assert m["flow.fallback36.persons"] == 1


def test_table1_metrics():
    m = metrics(lo2022.table1(built()))
    assert (m["t1.persons.walkers"], m["t1.persons.nonwalkers"], m["t1.persons.all"]) == (1, 2, 3)
    assert m["t1.age_mean.all"] == pytest.approx((61 + 68 + 59) / 3)
    assert (m["t1.male.walkers"], m["t1.male.all"]) == (1, 2)
    assert (m["t1.knees.nonwalkers"], m["t1.knees.all"]) == (3, 4)
    assert (m["t1.kl2.all"], m["t1.kl3.all"], m["t1.kl4.all"]) == (2, 1, 1)
    assert (m["t1.jsm1.walkers"], m["t1.jsm3.nonwalkers"]) == (1, 1)
    assert (m["t1.pain0.all"], m["t1.pain48.all"], m["t1.replaced48.nonwalkers"]) == (1, 2, 1)
    assert (m["t1.align_knees.all"], m["t1.varus.walkers"], m["t1.valgus.nonwalkers"]) == (3, 1, 1)
    assert m["t1.walk_days_max.walkers"] == 2100.0


def test_table3_metrics():
    m = metrics(lo2022.table3(built()))
    assert (m["t3.kl_worse.varus.walkers.events"], m["t3.kl_worse.varus.walkers.n"]) == (1, 1)
    assert (m["t3.kl_worse.valgus.nonwalkers.events"], m["t3.kl_worse.valgus.nonwalkers.n"]) == (0, 1)
    assert m["t3.new_pain.neutral.nonwalkers.n"] == 0  # 1000010 R has blank baseline pain
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_lo2022_build.py -q`
Expected: 3 failures — `module 'lo2022' has no attribute 'flow_metrics'`.

- [ ] **Step 3: Implement**

Append to `analyses/lo2022_walking/lo2022.py`:
```python
def _metrics(rows: list[tuple[str, float | int | None]]) -> pl.DataFrame:
    return pl.DataFrame(
        [{"metric": key, "value": None if value is None else float(value)} for key, value in rows],
        schema={"metric": pl.String, "value": pl.Float64},
    )


def _by_group(df: pl.DataFrame) -> dict[str, pl.DataFrame]:
    return {"walkers": df.filter(pl.col("walker")), "nonwalkers": df.filter(~pl.col("walker")), "all": df}


def flow_metrics(built: Built) -> pl.DataFrame:
    rows: list[tuple[str, float | int | None]] = []
    for r in built.flow.iter_rows(named=True):
        step = r["step"]
        rows.append((f"flow.{step}.persons", r["persons"]))
        if step != "all":
            rows += [
                (f"flow.{step}.excluded_persons", r["excluded_persons"]),
                (f"flow.{step}.excluded_knees", r["excluded_knees"]),
            ]
        if step in S1_STEPS:
            rows += [(f"s1.{step}.male", r["male"]), (f"s1.{step}.age_mean", r["age_mean"]), (f"s1.{step}.bmi_mean", r["bmi_mean"])]
    fallback = built.knees.filter(pl.col("source_visit") == built.fallback_visit)
    rows += [("flow.knees", built.knees.height), ("flow.fallback36.persons", fallback["ID"].n_unique())]
    return _metrics(rows)


def table1(built: Built) -> pl.DataFrame:
    rows: list[tuple[str, float | int | None]] = []
    persons = built.knees.unique("ID", keep="first", maintain_order=True)
    for group, p in _by_group(persons).items():
        rows += [
            (f"t1.persons.{group}", p.height),
            (f"t1.age_mean.{group}", p["age"].mean()),
            (f"t1.male.{group}", (p["sex"] == 1).sum()),
            (f"t1.bmi_mean.{group}", p["bmi"].mean()),
        ]
    days = persons.filter(pl.col("walker"))["walk_times"].drop_nulls()
    for stat, q in (("min", 0.0), ("p25", 0.25), ("median", 0.5), ("p75", 0.75), ("max", 1.0)):
        rows.append((f"t1.walk_days_{stat}.walkers", days.quantile(q, "linear") if len(days) else None))
    for group, k in _by_group(built.knees).items():
        rows.append((f"t1.knees.{group}", k.height))
        rows += [(f"t1.kl{v}.{group}", (k["kl0"] == v).sum()) for v in (2, 3, 4)]
        rows += [(f"t1.jsm{v}.{group}", (k["jsm0"] == v).sum()) for v in (0, 1, 2, 3)]
        rows += [
            (f"t1.pain0.{group}", k["pain0"].sum()),
            (f"t1.align_knees.{group}", k["alignment"].is_not_null().sum()),
            (f"t1.pain48.{group}", k["painf"].sum()),
            (f"t1.replaced48.{group}", k["replaced"].sum()),
        ]
        rows += [(f"t1.{cat}.{group}", (k["alignment"] == cat).sum()) for cat in ALIGNMENTS]
    return _metrics(rows)


def table3(built: Built) -> pl.DataFrame:
    rows: list[tuple[str, float | int | None]] = []
    for outcome in OUTCOMES:
        for cat in ALIGNMENTS:
            for group, k in _by_group(built.knees).items():
                if group == "all":
                    continue
                cell = k.filter((pl.col("alignment") == cat) & pl.col(outcome).is_not_null())
                rows += [
                    (f"t3.{outcome}.{cat}.{group}.events", cell[outcome].sum()),
                    (f"t3.{outcome}.{cat}.{group}.n", cell.height),
                ]
    return _metrics(rows)
```

Replace `analyses/lo2022_walking/build_frame.py`:
```python
"""Step `cohort`: Lo 2022 knee frame, flow, Table 1 and Table 3 (with metrics for grading)."""

import os
from pathlib import Path

import polars as pl
from lo2022 import build, flow_metrics, table1, table3

from oai.assumptions import current

A = current()
built = build(A)
frames, results = Path(os.environ["OAI_FRAME_DIR"]), Path(os.environ["OAI_RESULTS_DIR"])
built.knees.write_parquet(frames / "frame.parquet")
built.flow.write_csv(results / "flow.csv")
t1, t3 = table1(built), table3(built)
t1.write_csv(results / "table1.csv")
t3.write_csv(results / "table3.csv")
pl.concat([flow_metrics(built), t1, t3]).write_csv(results / "metrics_cohort.csv")
print(built.flow)
print(f"{built.knees.height} knees, {built.knees['ID'].n_unique()} participants [{A.label}]")
```

- [ ] **Step 4: Run tests**

Run: `uv run ruff format -q . && uv run ruff check --fix -q; uv run pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add analyses/lo2022_walking tests/test_lo2022_build.py
git commit -m "feat: add Lo 2022 Table 1, Table 3 and cohort metrics" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: GEE models (`models.R`)

**Files:**
- Modify: `analyses/lo2022_walking/models.R` (replace the placeholder)
- Test: `tests/test_lo2022_models.py`

**Interfaces:**
- Consumes: `frame.parquet` (Task 8 columns) and `oaimodels::assumptions()` (Task 4).
- Produces: `table2.csv` (`outcome, model, n, events, or, lo, hi`) and `metrics_models.csv`, with keys `t2.<outcome>.<walkers|nonwalkers>.<events|n>` and `t2.<outcome>.<or_unadj|or_adj>[.lo|.hi]`.

- [ ] **Step 1: Write the failing test**

`tests/test_lo2022_models.py`:
```python
"""Run models.R through the runner on a simulated frame (skipped without R + geepack)."""

import random
import shutil
import subprocess
from pathlib import Path

import polars as pl
import pytest

from oai.config import load_settings
from oai.manifest import load_analysis
from oai.runner import run_analysis

REPO = Path(__file__).resolve().parents[1]
ANALYSIS = REPO / "analyses" / "lo2022_walking"


def _r_ready() -> bool:
    if shutil.which("Rscript") is None:
        return False
    probe = subprocess.run(
        ["Rscript", "-e", "library(geepack); library(nanoparquet); library(jsonlite)"],
        cwd=REPO / "r", capture_output=True,
    )
    return probe.returncode == 0


pytestmark = pytest.mark.skipif(not _r_ready(), reason="R with geepack in r/ is unavailable")


def simulated_frame() -> pl.DataFrame:
    rng = random.Random(1)
    rows = []
    for i in range(400):
        walker = i % 2 == 0
        age, sex = 50 + rng.random() * 25, 1 + (i % 3 == 0)
        for side in ("R", "L"):
            kl0 = rng.choice([2.0, 3.0, 4.0])
            pain0 = rng.random() < 0.4
            rows.append({
                "ID": 1000001 + i, "SIDE": side, "walker": walker, "age": age, "sex": sex, "kl0": kl0,
                "kl_worse": rng.random() < (0.12 if walker else 0.35),
                "jsn_worse": rng.random() < 0.25,
                "new_pain": None if pain0 else rng.random() < 0.3,
                "improved_pain": (rng.random() < 0.4) if pain0 else None,
            })
    return pl.DataFrame(rows)


def test_models_write_table2_and_metrics(tmp_path):
    frames = tmp_path / "work" / "lo2022_walking" / "default"
    frames.mkdir(parents=True)
    simulated_frame().write_parquet(frames / "frame.parquet")
    settings = load_settings(
        env={"OAI_WORK_DIR": str(tmp_path / "work"), "OAI_RESULTS_DIR": str(tmp_path / "results")},
        repo_root=REPO,
    )
    run_analysis(load_analysis(ANALYSIS), settings, step_id="models", echo=lambda _: None)
    out = tmp_path / "results" / "lo2022_walking" / "default"
    table2 = pl.read_csv(out / "table2.csv")
    assert table2.height == 8  # 4 outcomes x (unadjusted, adjusted)
    m = dict(pl.read_csv(out / "metrics_models.csv").iter_rows())
    for outcome in ("new_pain", "kl_worse", "jsn_worse", "improved_pain"):
        for key in ("or_unadj", "or_adj"):
            assert m[f"t2.{outcome}.{key}.lo"] <= m[f"t2.{outcome}.{key}"] <= m[f"t2.{outcome}.{key}.hi"]
    assert m["t2.kl_worse.or_unadj.hi"] < 1  # strongly protective by construction
    assert m["t2.kl_worse.walkers.n"] + m["t2.kl_worse.nonwalkers.n"] == 800
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_lo2022_models.py -q`
Expected: FAIL — `RunnerError: step 'models' failed` (placeholder `stop()`).

- [ ] **Step 3: Implement**

`analyses/lo2022_walking/models.R` (replace the placeholder):
```r
# Step `models`: knee-level GEE logistic models (Lo 2022 Table 2 and Supplementary Tables 2-3).
# Knees are clustered on participant; settings come from assumptions.toml.
suppressPackageStartupMessages(library(geepack))

A <- oaimodels::assumptions()
frame <- oaimodels::read_frame(required = c(
  "ID", "walker", "age", "sex", "kl0", "new_pain", "kl_worse", "jsn_worse", "improved_pain"
))
out_dir <- Sys.getenv("OAI_RESULTS_DIR")
outcomes <- c("new_pain", "kl_worse", "jsn_worse", "improved_pain")
kl_term <- if (identical(A[["model.kl_covariate"]], "factor")) "factor(kl0)" else "kl0"
covariates <- sub("^kl0$", kl_term, A[["model.covariates"]])
formulas <- list(or_unadj = "walker", or_adj = paste(c("walker", covariates), collapse = " + "))

fit_or <- function(d, rhs) {
  model <- geepack::geeglm(stats::as.formula(paste("y ~", rhs)), id = ID, data = d,
                           family = stats::binomial, corstr = A[["model.corstr"]])
  est <- summary(model)$coefficients["walkerTRUE", ]
  b <- est[["Estimate"]]
  se <- est[["Std.err"]]
  c(or = exp(b), lo = exp(b - 1.96 * se), hi = exp(b + 1.96 * se))
}

metrics <- list()
rows <- list()
for (o in outcomes) {
  d <- frame[!is.na(frame[[o]]), c("ID", "walker", "age", "sex", "kl0", o)]
  names(d)[names(d) == o] <- "y"
  d$y <- as.integer(d$y)
  d <- d[stats::complete.cases(d), ]
  d <- d[order(d$ID), ]
  for (g in c("walkers", "nonwalkers")) {
    part <- d[d$walker == (g == "walkers"), ]
    metrics[[sprintf("t2.%s.%s.events", o, g)]] <- sum(part$y)
    metrics[[sprintf("t2.%s.%s.n", o, g)]] <- nrow(part)
  }
  for (name in names(formulas)) {
    est <- fit_or(d, formulas[[name]])
    metrics[[sprintf("t2.%s.%s", o, name)]] <- est[["or"]]
    metrics[[sprintf("t2.%s.%s.lo", o, name)]] <- est[["lo"]]
    metrics[[sprintf("t2.%s.%s.hi", o, name)]] <- est[["hi"]]
    rows[[length(rows) + 1]] <- data.frame(
      outcome = o, model = name, n = nrow(d), events = sum(d$y),
      or = est[["or"]], lo = est[["lo"]], hi = est[["hi"]]
    )
  }
}
utils::write.csv(do.call(rbind, rows), file.path(out_dir, "table2.csv"), row.names = FALSE)
utils::write.csv(data.frame(metric = names(metrics), value = unlist(metrics)),
                 file.path(out_dir, "metrics_models.csv"), row.names = FALSE)
cat("Table 2 written to", out_dir, "\n")
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_lo2022_models.py -q && uv run pytest -q`
Expected: the models test passes (it's skipped only if R/geepack is unavailable, and it is available locally); full suite green.

- [ ] **Step 5: Commit**

```bash
git add analyses/lo2022_walking/models.R tests/test_lo2022_models.py
git commit -m "feat: fit Lo 2022 GEE models in R" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Graded comparison (`oai.replication`, `compare.py`)

**Files:**
- Create: `src/oai/replication.py`, `tests/test_replication.py`
- Modify: `analyses/lo2022_walking/compare.py` (replace the placeholder)

**Interfaces:**
- Produces:
  - `COUNT_REL_TOL = 0.03`, `COUNT_ABS_TOL = 2`, `MEAN_TOL = 0.5`, `OR_TOL = 0.1`
  - `related_for(metric, related) -> list[str]`
  - `grade(published, ours, related=None, statuses=None) -> DataFrame[metric, kind, published, ours, diff, verdict, related]`
  - `summarize(table, *, section, label) -> str`

- [ ] **Step 1: Write the failing tests**

`tests/test_replication.py`:
```python
import pytest

from oai.replication import grade, related_for, summarize

RELATED = {"flow": ["a"], "flow.knees": ["b", "c"], "t2": ["m"]}


def row(table, metric):
    return table.filter(table["metric"] == metric).row(0, named=True)


def test_related_uses_longest_prefix_on_dot_boundaries():
    assert related_for("flow.knees", RELATED) == ["b", "c"]
    assert related_for("flow.age50.persons", RELATED) == ["a"]
    assert related_for("flowx.y", RELATED) == []


@pytest.mark.parametrize(
    "published, ours, verdict",
    [(1808, 1760, "replicated"), (1808, 1700, "drift"), (13, 15, "replicated"), (13, 16, "drift")],
)
def test_count_tolerance(published, ours, verdict):
    assert row(grade({"flow.knees": published}, {"flow.knees": ours}), "flow.knees")["verdict"] == verdict


def test_mean_tolerance_and_missing():
    t = grade({"t1.age_mean.all": 63.2, "t1.bmi_mean.all": 29.4}, {"t1.age_mean.all": 63.6})
    assert row(t, "t1.age_mean.all")["verdict"] == "replicated"
    assert row(t, "t1.bmi_mean.all")["verdict"] == "missing"


def test_or_tolerance_and_significance():
    pub = {"t2.x.or_adj": {"or": 0.6, "lo": 0.4, "hi": 0.8, "sig": True}}
    ok = {"t2.x.or_adj": 0.64, "t2.x.or_adj.lo": 0.47, "t2.x.or_adj.hi": 0.86}
    assert row(grade(pub, ok), "t2.x.or_adj")["verdict"] == "replicated"
    not_sig = {"t2.x.or_adj": 0.64, "t2.x.or_adj.lo": 0.40, "t2.x.or_adj.hi": 1.02}
    assert row(grade(pub, not_sig), "t2.x.or_adj")["verdict"] == "drift"
    assert row(grade(pub, {"t2.x.or_adj": 0.6}), "t2.x.or_adj")["verdict"] == "missing"


def test_or_significance_uses_published_flag():
    # "0.8 (0.6-1.0)" was reported as significant: the true upper bound was < 1 before rounding.
    pub = {"t2.j.or_adj": {"or": 0.8, "lo": 0.6, "hi": 1.0, "sig": True}}
    ours = {"t2.j.or_adj": 0.78, "t2.j.or_adj.lo": 0.61, "t2.j.or_adj.hi": 0.99}
    assert row(grade(pub, ours), "t2.j.or_adj")["verdict"] == "replicated"


def test_related_statuses_and_summary():
    t = grade({"flow.knees": 1808}, {"flow.knees": 1700}, RELATED, {"b": "assumed", "c": "open"})
    assert row(t, "flow.knees")["related"] == "b (assumed), c (open)"
    text = summarize(t, section="default", label="default")
    assert "0 replicated · 1 drift · 0 missing" in text
    assert "flow.knees" in text and "b (1)" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_replication.py -q`
Expected: collection error — `No module named 'oai.replication'`.

- [ ] **Step 3: Implement**

`src/oai/replication.py`:
```python
"""Grade a run's metrics against published values (replication studies).

Published values: int = count, float = mean, {or, lo, hi, sig} = odds ratio.
A count replicates within max(3%, 2), a mean within 0.5, and an odds ratio within 0.1
with the same significance. The published `sig` flag is authoritative, because rounded
bounds such as "0.6-1.0" can hide an upper bound below 1.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

import polars as pl

COUNT_REL_TOL = 0.03
COUNT_ABS_TOL = 2
MEAN_TOL = 0.5
OR_TOL = 0.1
EPS = 1e-9
SCHEMA = {
    "metric": pl.String, "kind": pl.String, "published": pl.String, "ours": pl.String,
    "diff": pl.Float64, "verdict": pl.String, "related": pl.String,
}


def related_for(metric: str, related: Mapping[str, list[str]]) -> list[str]:
    """Assumption keys for the longest prefix of `metric` (matching on dot boundaries)."""
    prefixes = [p for p in related if metric == p or metric.startswith(p + ".")]
    return list(related[max(prefixes, key=len)]) if prefixes else []


def _grade_or(pub: Mapping[str, Any], ours: Mapping[str, float], metric: str) -> tuple[str, str | None, float | None]:
    o, lo, hi = ours.get(metric), ours.get(f"{metric}.lo"), ours.get(f"{metric}.hi")
    if o is None or lo is None or hi is None:
        return "missing", None, None
    sig = hi < 1 or lo > 1
    diff = o - float(pub["or"])
    verdict = "replicated" if abs(diff) <= OR_TOL + EPS and sig == bool(pub["sig"]) else "drift"
    return verdict, f"{o:.2f} ({lo:.2f}-{hi:.2f}){' *' if sig else ''}", diff


def grade(
    published: Mapping[str, Any],
    ours: Mapping[str, float],
    related: Mapping[str, list[str]] | None = None,
    statuses: Mapping[str, str] | None = None,
) -> pl.DataFrame:
    rows = []
    for metric, pub in published.items():
        keys = related_for(metric, related or {})
        related_text = ", ".join(f"{k} ({(statuses or {}).get(k, '?')})" for k in keys)
        if isinstance(pub, Mapping):
            kind = "or"
            pub_text = f"{pub['or']} ({pub['lo']}-{pub['hi']}){' *' if pub['sig'] else ''}"
            verdict, ours_text, diff = _grade_or(pub, ours, metric)
        else:
            kind = "mean" if isinstance(pub, float) else "count"
            pub_text, value = str(pub), ours.get(metric)
            if value is None:
                verdict, ours_text, diff = "missing", None, None
            else:
                diff = float(value) - float(pub)
                tol = MEAN_TOL if kind == "mean" else max(COUNT_REL_TOL * abs(pub), COUNT_ABS_TOL)
                verdict = "replicated" if abs(diff) <= tol + EPS else "drift"
                ours_text = f"{value:.1f}" if kind == "mean" else f"{value:g}"
        rows.append({
            "metric": metric, "kind": kind, "published": pub_text, "ours": ours_text,
            "diff": diff, "verdict": verdict, "related": related_text,
        })
    return pl.DataFrame(rows, schema=SCHEMA)


def summarize(table: pl.DataFrame, *, section: str, label: str) -> str:
    counts = {v: table.filter(pl.col("verdict") == v).height for v in ("replicated", "drift", "missing")}
    lines = [
        f"Replication vs published [{section}] (run: {label})",
        " · ".join(f"{n} {v}" for v, n in counts.items()),
    ]
    off = table.filter(pl.col("verdict") != "replicated")
    if off.height:
        lines += ["", "Not replicated:"]
        lines += [
            f"  {r['verdict']:<6} {r['metric']:<42} published {r['published']:<20} ours {r['ours']}"
            for r in off.iter_rows(named=True)
        ]
        implicated = Counter(
            part.split(" (")[0] for text in off["related"].to_list() if text for part in text.split(", ")
        )
        lines += ["", "Assumptions most implicated: " + ", ".join(f"{k} ({n})" for k, n in implicated.most_common(8))]
    return "\n".join(lines)
```

`analyses/lo2022_walking/compare.py` (replace the placeholder):
```python
"""Step `compare`: grade this run's metrics against the paper (published.toml)."""

import os
import tomllib
from pathlib import Path

import polars as pl

from oai.assumptions import current
from oai.replication import grade, summarize

A = current()
results = Path(os.environ["OAI_RESULTS_DIR"])
published = tomllib.loads(Path("published.toml").read_text())
section = A.variant if A.variant in published else "default"
ours: dict[str, float] = {}
for path in sorted(results.glob("metrics_*.csv")):
    for metric, value in pl.read_csv(path, null_values=["NA"]).iter_rows():  # R writes NA
        if value is not None:
            ours[metric] = float(value)
statuses = {key: item.status for key, item in A.items.items()}
table = grade(published[section], ours, published.get("related", {}), statuses)
table.write_csv(results / "comparison.csv")
print(summarize(table, section=section, label=A.label))
```

- [ ] **Step 4: Run tests**

Run: `uv run ruff format -q . && uv run ruff check --fix -q; uv run pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/oai/replication.py tests/test_replication.py analyses/lo2022_walking/compare.py
git commit -m "feat: grade replication metrics against published values" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: End-to-end on the real release

**Files:**
- Create: `tests/test_lo2022_realdata.py`
- Modify: `README.md` (add `lo2022_walking` to the Analyses table)

- [ ] **Step 1: Write the real-data test**

`tests/test_lo2022_realdata.py`:
```python
"""Full Lo 2022 replication on the real release (outputs exist; results are the finding)."""

import shutil
import subprocess
from pathlib import Path

import pytest

from oai.config import get_settings
from oai.manifest import find_analysis
from oai.runner import run_analysis

REPO = Path(__file__).resolve().parents[1]


def _r_ready() -> bool:
    return shutil.which("Rscript") is not None and subprocess.run(
        ["Rscript", "-e", "library(geepack)"], cwd=REPO / "r", capture_output=True
    ).returncode == 0


@pytest.mark.realdata
@pytest.mark.skipif(not _r_ready(), reason="R with geepack in r/ is unavailable")
def test_replication_runs_end_to_end():
    settings = get_settings()
    run_analysis(find_analysis("lo2022_walking", settings.analyses_dir), settings, echo=lambda _: None)
    out = settings.results_dir / "lo2022_walking" / "default"
    for name in ("flow.csv", "table1.csv", "table2.csv", "table3.csv", "comparison.csv",
                 "metrics_cohort.csv", "metrics_models.csv", "assumptions.resolved.json"):
        assert (out / name).is_file(), name
```

In `README.md`, add a row to the Analyses table:
```markdown
| `lo2022_walking` | local | Replication of Lo et al. 2022 ([README](analyses/lo2022_walking/README.md)) |
```

- [ ] **Step 2: Run the test and the replication for real**

```bash
uv run pytest -m realdata -q tests/test_lo2022_realdata.py
uv run oai run lo2022_walking
uv run oai run lo2022_walking --variant missing_as_nonwalkers
uv run oai run lo2022_walking --variant missing_as_walkers
uv run oai run lo2022_walking --variant replacement_not_worsening
uv run oai run lo2022_walking --variant corstr_independence
uv run oai check-egress "$HOME/oai-work/results/lo2022_walking"
```
Expected: the test passes; each run prints the flow and a graded summary; the egress check reports 0 problems (small-cell warnings allowed). **Do not commit any results.** Save the five summaries for the report to the user.

- [ ] **Step 3: Full verification and commit**

```bash
uv run ruff check && uv run ruff format --check && uv run python scripts/check_no_data.py
uv run pytest -q && uv run pytest -m realdata -q -k "not whole_release and not memory"
(cd r && Rscript -e 'testthat::test_local("oaimodels", stop_on_failure = TRUE)')
git add tests/test_lo2022_realdata.py README.md
git commit -m "test: run the Lo 2022 replication end to end on the real release" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
Expected: everything green.

- [ ] **Step 4: Push**

```bash
git push origin main && gh run list --repo Spiewart/oai-analytics --limit 1
```
Expected: push succeeds; one CI run listed (checked once, not polled).
