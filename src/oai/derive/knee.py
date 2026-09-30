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
    return (
        pl.col(find_col(df, "SIDE"))
        .replace_strict(SIDE_CODES, return_dtype=pl.String)
        .alias("SIDE")
    )


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
