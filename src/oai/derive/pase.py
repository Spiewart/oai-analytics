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
