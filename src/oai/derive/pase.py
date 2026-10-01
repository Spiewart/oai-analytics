"""PASE scoring (Washburn et al. 1993) from AllClinical items.

The total score is released as VxxPASE. The walking subscore (item 2, walking outside the home)
is weight x days/7 x hours/day from VxxPASE2 (0 never, 1 = 1-2 days, 2 = 3-4 days, 3 = 5-7 days)
and VxxPASE2HR (1 <1 h, 2 = 1-2 h, 3 = 2-4 h, 4 >4 h; skipped when never).
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import partial

import polars as pl

from oai.derive.knee import find_col

DEFAULT_WALKING = {"days": [0.0, 1.5, 3.5, 6.0], "hours": [0.5, 1.5, 3.0, 5.0], "weight": 20.0}


def score_pase(
    allclinical: pl.DataFrame, visit: str, walking: Mapping = DEFAULT_WALKING
) -> pl.DataFrame:
    """ID, visit, pase_total (released VxxPASE), pase_walking (item-2 subscore; 0 if never)."""
    v = visit.removeprefix("V")
    col = partial(find_col, allclinical, where=f"allclinical{v}")
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
