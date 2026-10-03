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
import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, time
from pathlib import Path
from typing import Any

from oai.errors import OAIError

ASSUMPTIONS_FILE = "assumptions.toml"
RESOLVED_FILE = "assumptions.resolved.json"
LEDGER_FILE = "ASSUMPTIONS.md"
STATUSES = ("confirmed", "assumed", "open")
DEFAULT_LABEL = "default"
_FIELDS = {"value", "status", "source", "rationale", "alternatives", "choices"}
_VARIANT_NAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")


class AssumptionsError(OAIError):
    """assumptions.toml is invalid, or a variant/override does not fit it."""


@dataclass(frozen=True)
class Assumption:
    key: str
    value: Any
    status: str
    source: str
    rationale: str = ""
    alternatives: tuple[Any, ...] = ()  # documentation only
    choices: tuple[Any, ...] = ()  # enforced: every resolved value must be one of these


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
            items={
                key: Assumption(key, e["value"], e["status"], e["source"])
                for key, e in entries.items()
            },
        )


def _has_datetime(value: Any) -> bool:
    if isinstance(value, (date, time)):
        return True
    if isinstance(value, list):
        return any(_has_datetime(v) for v in value)
    if isinstance(value, dict):
        return any(_has_datetime(v) for v in value.values())
    return False


def _coerce(default: Any, value: Any) -> Any:
    """Normalize a variant/--set value to its default's type where that is lossless."""
    if isinstance(default, str) and isinstance(value, (date, time)):
        return value.isoformat()  # `--set key=2013-01-01` parses as a TOML date
    if isinstance(default, float) and isinstance(value, int) and not isinstance(value, bool):
        return float(value)  # so -2 and -2.0 resolve (and label) identically
    return value


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
        item = self.items[key]
        if not _same_type(item.value, value):
            raise AssumptionsError(
                f"{where}: {key} expects {type(item.value).__name__}, got {type(value).__name__} ({value!r})"
            )
        if item.choices and value not in item.choices:
            allowed = ", ".join(str(c) for c in item.choices)
            raise AssumptionsError(f"{where}: {key} must be one of {allowed}, not {value!r}")

    def resolve(
        self, analysis: str, variant: str | None = None, overrides: Mapping[str, Any] | None = None
    ) -> Resolved:
        overrides = dict(overrides or {})
        values = {key: item.value for key, item in self.items.items()}
        origins = dict.fromkeys(values, "default")
        if variant is not None:
            if variant not in self.variants:
                available = ", ".join(sorted(self.variants)) or "(none)"
                raise AssumptionsError(
                    f"{analysis}: unknown variant {variant!r}; available: {available}"
                )
            for key, value in self.variants[variant].set.items():
                values[key], origins[key] = value, "variant"
        overrides = {
            key: _coerce(self.items[key].value, value) if key in self.items else value
            for key, value in overrides.items()
        }
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
    if _has_datetime(entry.get("value")):
        raise AssumptionsError(
            f'{where}: {key}: dates must be strings (quote them, e.g. "2012-09-12")'
        )
    if entry.get("status") not in STATUSES:
        raise AssumptionsError(f"{where}: {key}: status must be one of {', '.join(STATUSES)}")
    source = entry.get("source")
    if not isinstance(source, str) or not source.strip():
        raise AssumptionsError(f"{where}: {key}: 'source' is required")
    choices = tuple(entry.get("choices", []))
    if choices and entry["value"] not in choices:
        raise AssumptionsError(
            f"{where}: {key}: default {entry['value']!r} is not one of its choices"
        )
    return Assumption(
        key,
        entry["value"],
        entry["status"],
        source,
        entry.get("rationale", ""),
        tuple(entry.get("alternatives", [])),
        choices,
    )


def _walk(table: dict[str, Any], prefix: str, where: Path, out: dict[str, Assumption]) -> None:
    for name, entry in table.items():
        key = f"{prefix}.{name}" if prefix else name
        if not isinstance(entry, dict):
            raise AssumptionsError(
                f"{where}: {key!r} must be a table with value, status and source"
            )
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
        if name == DEFAULT_LABEL or ".." in name or not _VARIANT_NAME.match(name):
            raise AssumptionsError(
                f"{path}: variant name {name!r} must use letters, digits, '_', '.' or '-' "
                f"(no '..') and must not be {DEFAULT_LABEL!r}"
            )
        if not isinstance(spec, dict) or not isinstance(spec.get("set"), dict):
            raise AssumptionsError(f"{path}: variant {name!r} needs a 'set' table")
        settings = {
            key: _coerce(items[key].value, value) if key in items else value
            for key, value in spec["set"].items()
        }
        for key, value in settings.items():
            base.check(key, value, f"{path}: variant {name!r}")
        variants[name] = Variant(name, spec.get("description", ""), settings)
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


def _fmt(value: Any) -> str:
    # ensure_ascii=False: characters such as the en dash in "1–2 days" are shown, not \u escapes
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _value_cell(a: Assumption) -> str:
    cell = f"`{_cell(_fmt(a.value))}`"
    if a.choices:
        cell += " (choices: " + ", ".join(_cell(_fmt(c)) for c in a.choices) + ")"
    return cell


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
            f"| `{a.key}` | {_value_cell(a)} | {_cell(a.source)} | {_cell(a.rationale)} |"
            for a in rows
        ]
    if assumptions.variants:
        lines += ["", "## Variants", "", "| Variant | Sets | Description |", "|---|---|---|"]
        for v in sorted(assumptions.variants.values(), key=lambda v: v.name):
            # "; ", not <br>: a table cell cannot hold a line break that GitHub and Typst both
            # render, and Typst (the reports) drops raw HTML, running the values together.
            sets = "; ".join(f"`{k} = {_cell(_fmt(val))}`" for k, val in v.set.items())
            lines.append(f"| `{v.name}` | {sets} | {_cell(v.description)} |")
    return "\n".join(lines) + "\n"
