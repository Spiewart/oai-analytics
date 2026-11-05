"""PASE scoring (Washburn et al. 1993) from AllClinical items.

The total score is released as VxxPASE. The walking subscore (item 2, walking outside the home)
is weight x days/7 x hours/day from VxxPASE2 (0 never, 1 = 1-2 days, 2 = 3-4 days, 3 = 5-7 days)
and VxxPASE2HR (1 <1 h, 2 = 1-2 h, 3 = 2-4 h, 4 >4 h; skipped when never).
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import partial
from types import MappingProxyType

import polars as pl

from oai.derive.knee import find_col

DEFAULT_WALKING = MappingProxyType(
    {"days": (0.0, 1.5, 3.5, 6.0), "hours": (0.5, 1.5, 3.0, 5.0), "weight": 20.0}
)
N_DAYS_CODES = 4  # VxxPASE2: 0 never, 1, 2, 3
N_HOURS_CODES = 4  # VxxPASE2HR: 1, 2, 3, 4


def _check_scoring(walking: Mapping) -> None:
    """One value per answer code, or raise: a short list would silently null the other codes."""
    for key, expected in (("days", N_DAYS_CODES), ("hours", N_HOURS_CODES)):
        if len(walking[key]) != expected:
            raise ValueError(
                f"walking scoring {key!r} needs {expected} values (one per answer code), "
                f"got {len(walking[key])}"
            )


def score_pase(
    allclinical: pl.DataFrame, visit: str, walking: Mapping = DEFAULT_WALKING
) -> pl.DataFrame:
    """ID, visit, pase_total (released VxxPASE), pase_walking (item-2 subscore; 0 if never)."""
    _check_scoring(walking)
    v = visit.removeprefix("V")
    col = partial(find_col, allclinical, where=f"allclinical{v}")
    # The code maps differ by one. PASE2 (days) has a code 0 for "never", so its code is the
    # index into walking["days"]. PASE2HR (hours) is skipped for "never", so its codes start at
    # 1 and the index is code - 1. Codes outside either range map to null.
    days = pl.col(col(f"V{v}PASE2")).replace_strict(
        dict(enumerate(walking["days"])), default=None, return_dtype=pl.Float64
    )
    hours = pl.col(col(f"V{v}PASE2HR")).replace_strict(
        {code + 1: h for code, h in enumerate(walking["hours"])},
        default=None,
        return_dtype=pl.Float64,
    )
    subscore = pl.when(days == 0).then(0.0).otherwise(walking["weight"] * days / 7 * hours)
    return allclinical.select(
        pl.col(col("ID")).alias("ID"),
        pl.lit(v).alias("visit"),
        pl.col(col(f"V{v}PASE")).cast(pl.Float64).alias("pase_total"),
        subscore.alias("pase_walking"),
    )


DAYS_CODES = (0, 1, 2, 3)  # VxxPASE2: never, 1-2, 3-4, 5-7 days (77 refused, 88 don't know)
HOURS_CODES = (1, 2, 3, 4)  # VxxPASE2HR: <1, 1 to <2, 2-4, >4 hours (88 don't know)


def pase_walking_answers(allclinical: pl.DataFrame, visit: str) -> pl.DataFrame:
    """ID, pase_days_<v>, pase_hours_<v>: PASE item 2's answer codes (walking outside the home).

    A code outside the answer codes (refused, don't know) is no answer (null). Hours are asked
    only after a days answer other than never, so they are null when days is 0 or missing.
    """
    v = visit.removeprefix("V")
    col = partial(find_col, allclinical, where=f"allclinical{v}")
    raw_days = pl.col(col(f"V{v}PASE2")).cast(pl.Int64)
    raw_hours = pl.col(col(f"V{v}PASE2HR")).cast(pl.Int64)
    days = pl.when(raw_days.is_in(DAYS_CODES)).then(raw_days)
    hours = pl.when(raw_days.is_in(DAYS_CODES[1:]) & raw_hours.is_in(HOURS_CODES)).then(raw_hours)
    return allclinical.select(
        pl.col(col("ID")).alias("ID"),
        days.alias(f"pase_days_{v}"),
        hours.alias(f"pase_hours_{v}"),
    )


def _has_col(df: pl.DataFrame, name: str) -> bool:
    return any(c.upper() == name.upper() for c in df.columns)


def pase_visit(
    allclinical: pl.DataFrame, visit: str, walking: Mapping = DEFAULT_WALKING
) -> pl.DataFrame:
    """ID and every PASE measure a visit has, suffixed by visit: pase_total_<v> (when released;
    V14 asked item 2 but released no total), pase_walking_<v> (the item-2 subscore, as in
    score_pase), pase_days_<v> and pase_hours_<v> (the item-2 answer codes, as in
    pase_walking_answers), and visdys_<v> (days since enrollment, when the table has them)."""
    v = visit.removeprefix("V")
    col = partial(find_col, allclinical, where=f"allclinical{v}")
    if _has_col(allclinical, f"V{v}PASE"):
        scored = score_pase(allclinical, v, walking).select(
            "ID",
            pl.col("pase_total").alias(f"pase_total_{v}"),
            pl.col("pase_walking").alias(f"pase_walking_{v}"),
        )
    else:
        # no total: score item 2 alone, through score_pase on a placeholder total
        placeholder = allclinical.with_columns(pl.lit(None, dtype=pl.Float64).alias(f"V{v}PASE"))
        scored = score_pase(placeholder, v, walking).select(
            "ID", pl.col("pase_walking").alias(f"pase_walking_{v}")
        )
    out = scored.join(pase_walking_answers(allclinical, v), on="ID", how="full", coalesce=True)
    if _has_col(allclinical, f"V{v}VISDYS"):
        days = allclinical.select(
            pl.col(col("ID")).alias("ID"), pl.col(col(f"V{v}VISDYS")).alias(f"visdys_{v}")
        )
        out = out.join(days, on="ID", how="left")
    return out


LEISURE_WEIGHTS = {2: 20.0, 3: 21.0, 4: 23.0, 5: 23.0, 6: 30.0}  # Washburn items 2-6
HOUSEHOLD_WEIGHTS = (25.0, 25.0, 30.0, 36.0, 20.0, 35.0)  # HOUACT1-6
WORK_WEIGHT = 21.0  # x hours worked in the past 7 days / 7


def work_active(workamt: pl.Expr, work7: pl.Expr) -> pl.Expr:
    """True when working in the past 7 days at more than sitting (WORKAMT 2-4); False when not
    working (WORK7 == 0) or mainly sitting (WORKAMT 1); null when working with the amount
    unanswered (88 don't know or missing)."""
    return (
        pl.when(work7 == 0)
        .then(False)
        .when(work7 == 1)
        .then(pl.when(workamt.is_in([1])).then(False).when(workamt.is_in([2, 3, 4])).then(True))
    )


def pase_rebuilt(
    allclinical: pl.DataFrame, visit: str, walking: Mapping = DEFAULT_WALKING
) -> pl.DataFrame:
    """ID and pase_rebuilt_<v>: the PASE total from the Washburn weights, item by item.

    Items 2-6 are weight x days/7 x hours (the walking scoring's day and hour values); HOUACT1-6
    are weight x yes; work is 21 x hours worked in the past 7 days / 7, counted only when
    working (WORK7 == 1) at more than sitting (WORKAMT > 1). Null if any component is
    unanswered (refused and don't-know codes included).
    """
    _check_scoring(walking)
    v = visit.removeprefix("V")
    col = partial(find_col, allclinical, where=f"allclinical{v}")
    parts: list[pl.Expr] = []
    for item, weight in LEISURE_WEIGHTS.items():
        days = pl.col(col(f"V{v}PASE{item}")).replace_strict(
            dict(enumerate(walking["days"])), default=None, return_dtype=pl.Float64
        )
        hours = pl.col(col(f"V{v}PASE{item}HR")).replace_strict(
            {code + 1: h for code, h in enumerate(walking["hours"])},
            default=None,
            return_dtype=pl.Float64,
        )
        parts.append(pl.when(days == 0).then(0.0).otherwise(weight * days / 7 * hours))
    for k, weight in enumerate(HOUSEHOLD_WEIGHTS, start=1):
        yes = pl.col(col(f"V{v}HOUACT{k}")).cast(pl.Int64)
        parts.append(pl.when(yes.is_in([0, 1])).then(yes * weight))
    active = work_active(
        pl.col(col(f"V{v}WORKAMT")).cast(pl.Int64), pl.col(col(f"V{v}WORK7")).cast(pl.Int64)
    )
    hours_worked = pl.col(col(f"V{v}WKHR7CV")).cast(pl.Float64)
    parts.append(pl.when(active).then(WORK_WEIGHT * hours_worked / 7).when(~active).then(0.0))
    total = pl.when(pl.all_horizontal([p.is_not_null() for p in parts])).then(
        pl.sum_horizontal(parts)
    )
    return allclinical.select(pl.col(col("ID")).alias("ID"), total.alias(f"pase_rebuilt_{v}"))
