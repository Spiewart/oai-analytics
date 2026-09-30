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
COUNT_COLUMN = re.compile(r"^(n|count|n_.+|.+_n|.+_count)$", re.IGNORECASE)
TABULAR_SEPARATORS = {".csv": ",", ".tsv": "\t"}
TEXT_SUFFIXES = {".json", ".txt", ".md", ".log"}
MANUAL_REVIEW_SUFFIXES = {".png", ".pdf", ".svg", ".jpg", ".jpeg", ".html"}
SCANNED_REVIEW_SUFFIXES = {".svg", ".html"}  # text formats that can embed whole datasets


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
    problems.extend(f"{name}: {message}" for message in small_cell_violations(df, min_cell))
    return problems


def _txt_table_problems(path: Path, rel: str, *, min_cell: int, ignore: set[str]) -> list[str]:
    """Apply table checks to a .txt that parses as tab-delimited with 2+ columns."""
    try:
        df = pl.read_csv(path, separator="\t", infer_schema_length=10_000)
    except pl.exceptions.PolarsError:
        return []
    return _frame_problems(df, rel, min_cell=min_cell, ignore=ignore) if df.width > 1 else []


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
                df = pl.read_csv(
                    path, separator=TABULAR_SEPARATORS[suffix], infer_schema_length=10_000
                )
                report.problems += _frame_problems(df, rel, min_cell=min_cell, ignore=ignore)
            elif suffix == ".parquet":
                report.problems += _frame_problems(
                    pl.read_parquet(path), rel, min_cell=min_cell, ignore=ignore
                )
            elif suffix in TEXT_SUFFIXES or suffix in SCANNED_REVIEW_SUFFIXES:
                if PARTICIPANT_ID.search(path.read_text(errors="replace")):
                    report.problems.append(f"{rel}: contains participant-ID-like values")
                if suffix == ".txt":
                    report.problems += _txt_table_problems(
                        path, rel, min_cell=min_cell, ignore=ignore
                    )
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
