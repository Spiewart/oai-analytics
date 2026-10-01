"""Check that a results directory holds only aggregate outputs before it leaves the enclave.

Fails closed: any file that cannot be positively checked is a problem, except figure
formats, which are listed for manual review.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import polars as pl

from oai.errors import OAIError

ID_COLUMN_NAMES = frozenset(
    {
        "id",
        "iid",
        "fid",
        "src_subject_id",
        "subjid",
        "subject_id",
        "sample_id",
        "sampid",
        "dbgap_subject_id",
        "participant_id",
    }
)
# A 9-prefixed 7-digit run not inside a longer number or a decimal fraction. Catches
# FID_IID joins and "OAI" prefixes; no lookbehind so polars (Rust regex) can use it too.
PARTICIPANT_ID = re.compile(r"(?:^|[^\d.])9\d{6}(?:\D|$)")
COUNT_COLUMN = re.compile(r"^(n|count|events|n_.+|.+_n|.+_count|.+_events)$", re.IGNORECASE)
TABULAR_SEPARATORS = {".csv": ",", ".tsv": "\t"}
TEXT_SUFFIXES = {".json", ".txt", ".md", ".log"}
MANUAL_REVIEW_SUFFIXES = {".png", ".pdf", ".svg", ".jpg", ".jpeg", ".html"}
SCANNED_REVIEW_SUFFIXES = {".svg", ".html"}  # text formats that can embed whole datasets


class EgressError(OAIError):
    """Egress could not be configured or run."""


SMALL_CELL_MODES = ("off", "warn", "fail")


@dataclass
class EgressReport:
    problems: list[str] = field(default_factory=list)  # block release
    warnings: list[str] = field(default_factory=list)  # reported, do not block
    manual_review: list[Path] = field(default_factory=list)
    checked: list[Path] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def small_cell_violations(df: pl.DataFrame, min_cell: int) -> list[str]:
    """Return one message per count column holding values in 1..min_cell-1.

    Count columns are named n, count, events, n_*, *_n, *_count or *_events; in a long
    (metric, value) table the metric's last dotted segment is matched. Zero is not flagged.
    Neither OAI/NDA nor dbGaP sets a minimum cell size, and NIH treats aggregate genomic
    summary results as releasable (NOT-OD-19-023), so by default these findings are
    advisory (`[egress] small_cell = "warn"`); set "fail" when a journal or collaborator
    requires suppression. See docs/egress.md.
    """
    messages = []
    if set(df.columns) == {"metric", "value"} and df.schema["value"].is_numeric():
        # Long format (metric, value): a metric whose last dotted segment is a count name.
        last = pl.col("metric").str.split(".").list.last()
        small = df.filter(
            last.str.contains(f"(?i){COUNT_COLUMN.pattern}")
            & (pl.col("value") > 0)
            & (pl.col("value") < min_cell)
        )
        if small.height:
            messages.append(f"{small.height} count metric(s) with 0 < n < {min_cell} (long format)")
        return messages
    for col in df.columns:
        if not COUNT_COLUMN.match(col) or not df.schema[col].is_numeric():
            continue
        small = df.filter((pl.col(col) > 0) & (pl.col(col) < min_cell)).height
        if small:
            messages.append(f"column {col!r} has {small} cell(s) with 0 < n < {min_cell}")
    return messages


def _identifier_problems(df: pl.DataFrame, name: str, *, ignore: set[str]) -> list[str]:
    problems = []
    for position, col in enumerate(df.columns):
        if PARTICIPANT_ID.search(col):
            problems.append(
                f"{name}: column name at position {position} looks like a participant ID"
            )
        if col.lower() in ID_COLUMN_NAMES:
            problems.append(f"{name}: identifier column {col!r}")
        if col in ignore:
            continue
        values = df.get_column(col).cast(pl.String, strict=False).drop_nulls()
        hits = values.str.contains(PARTICIPANT_ID.pattern).sum()
        if hits:
            problems.append(f"{name}: column {col!r} has {hits} participant-ID-like value(s)")
    return problems


def _read_txt_table(path: Path) -> pl.DataFrame | None:
    """A .txt that parses as tab-delimited with 2+ columns gets the table checks."""
    try:
        df = pl.read_csv(path, separator="\t", infer_schema_length=10_000)
    except pl.exceptions.PolarsError:
        return None
    return df if df.width > 1 else None


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


def check_egress(
    results_dir: Path,
    *,
    min_cell: int,
    small_cell: str = "warn",
    ignore_id_pattern_columns: Sequence[str] = (),
) -> EgressReport:
    """Identifier findings always block; small-cell findings follow `small_cell`."""
    if small_cell not in SMALL_CELL_MODES:
        raise EgressError(
            f"small_cell must be one of {', '.join(SMALL_CELL_MODES)}, not {small_cell!r}"
        )
    report = EgressReport()
    if not results_dir.is_dir():
        report.problems.append(f"{results_dir}: not a directory")
        return report
    ignore = set(ignore_id_pattern_columns)

    def check_frame(df: pl.DataFrame, name: str) -> None:
        report.problems.extend(_identifier_problems(df, name, ignore=ignore))
        if small_cell != "off":
            found = [f"{name}: {m}" for m in small_cell_violations(df, min_cell)]
            (report.problems if small_cell == "fail" else report.warnings).extend(found)

    for path in sorted(p for p in results_dir.rglob("*") if p.is_file()):
        rel = path.relative_to(results_dir).as_posix()
        suffix = path.suffix.lower()
        report.checked.append(path)
        try:
            if suffix in TABULAR_SEPARATORS:
                check_frame(
                    pl.read_csv(
                        path, separator=TABULAR_SEPARATORS[suffix], infer_schema_length=10_000
                    ),
                    rel,
                )
            elif suffix == ".parquet":
                check_frame(pl.read_parquet(path), rel)
            elif suffix in TEXT_SUFFIXES or suffix in SCANNED_REVIEW_SUFFIXES:
                text = path.read_text(errors="replace")
                if suffix == ".json" and ignore:
                    text = _without_keys(text, ignore)
                if PARTICIPANT_ID.search(text):
                    report.problems.append(f"{rel}: contains participant-ID-like values")
                if suffix == ".txt" and (df := _read_txt_table(path)) is not None:
                    check_frame(df, rel)
                if suffix in SCANNED_REVIEW_SUFFIXES:
                    report.manual_review.append(path)
            elif suffix in MANUAL_REVIEW_SUFFIXES:
                report.manual_review.append(path)
            else:
                report.problems.append(
                    f"{rel}: unrecognized file type {suffix or '(none)'}; egress fails closed"
                )
        except (pl.exceptions.PolarsError, OSError) as exc:
            report.problems.append(
                f"{rel}: could not be read ({type(exc).__name__}); egress fails closed"
            )
    return report
