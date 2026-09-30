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
                (pl.col(find_col(df, item.format(visit=visit, side=side))) == 1).alias(
                    "frequent_pain"
                ),
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
                pl.when(counted)
                .then(_outcome(df, code, "DAYS").cast(pl.Float64))
                .alias("replaced_days"),
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
