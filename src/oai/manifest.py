"""analysis.toml: the contract between an analysis folder and the runner/exporter."""

from __future__ import annotations

import re
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, NoReturn

from oai.assumptions import DEFAULT_LABEL, load_assumptions
from oai.catalog import INPUT_SPEC
from oai.errors import OAIError

MANIFEST_NAME = "analysis.toml"
LANGS = ("python", "r")
STAGES = ("local", "enclave")
_IDENT = re.compile(r"[a-z][a-z0-9_]*")  # matched with fullmatch: `$` accepts a trailing newline


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
class ReportSpec:
    documents: tuple[str, ...]  # .qmd files directly in the analysis folder, rendered in order
    runs: tuple[str, ...]  # run labels the report reads: "default" and/or variant names
    assets: tuple[str, ...] = ()  # files copied next to the documents before rendering
    combined: str | None = None  # a PDF joining the documents' PDFs, in order
    part_titles: tuple[str, ...] = ()  # one bookmark title per document in `combined`
    local_assets: tuple[str, ...] = ()  # untracked files (e.g. *.local.yml) copied when present


@dataclass(frozen=True)
class Analysis:
    name: str
    description: str
    root: Path
    inputs: tuple[str, ...]
    steps: tuple[Step, ...]
    export: ExportSpec | None
    aggregate_outputs: tuple[str, ...]
    report: ReportSpec | None = None
    r_profile: str | None = None  # renv profile for R steps ([r] profile); local-only

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
    if not isinstance(name, str) or not _IDENT.fullmatch(name):
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
        if not isinstance(sid, str) or not _IDENT.fullmatch(sid):
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
    report = _parse_report(data["report"], root, fail) if "report" in data else None
    r_profile = _parse_r(data["r"], steps, fail) if "r" in data else None
    return Analysis(
        name,
        data.get("description", ""),
        root,
        inputs,
        tuple(steps),
        export,
        outputs,
        report,
        r_profile,
    )


def _plain_file(root: Path, name: object) -> bool:
    """A bare file name (no directories) that exists directly in root."""
    return isinstance(name, str) and name == Path(name).name and (root / name).is_file()


def _plain_name(name: object) -> bool:
    """A bare file name (no directories), which need not exist."""
    return isinstance(name, str) and bool(name) and name == Path(name).name


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


def _parse_r(raw: Any, steps: list[Step], fail: Callable[[str], NoReturn]) -> str:
    profile = raw.get("profile") if isinstance(raw, dict) else None
    if not isinstance(profile, str) or not re.fullmatch(r"[a-z][a-z0-9_-]*", profile):
        fail('[r] profile must be a lowercase renv profile name, e.g. "report"')
    if any(s.stage == "enclave" for s in steps):
        fail("[r] profile is local-only: enclave bundles restore only the default R library")
    return profile


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
