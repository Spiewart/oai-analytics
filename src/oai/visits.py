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
        df.select(
            [*id_cols, *[pl.col(src).alias(stem) for src, stem in cols.items()]]
        ).with_columns(pl.lit(code).alias("visit"))
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
    months = {
        code: nominal_month(code, visit_map=vm)
        for code in fallback_rows["visit"].unique().to_list()
    }
    nominal = pl.col("visit").replace_strict(months, default=None, return_dtype=pl.Float64)
    return df.with_columns(
        pl.coalesce(days / DAYS_PER_YEAR, nominal / 12).alias("time_years"),
        pl.when(days.is_not_null())
        .then(pl.lit("visdys"))
        .otherwise(pl.lit("nominal"))
        .alias("time_source"),
    )
