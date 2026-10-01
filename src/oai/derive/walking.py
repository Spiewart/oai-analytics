"""The 96-month walking-for-exercise item (Historical Physical Activity Survey, AllClinical10).

Shared by lo2022_walking (its exposure) and walking_validation (the item under validation).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from functools import partial

import polars as pl

from oai.derive.knee import find_col
from oai.loader import read_table

WALKER_ITEM = "V10WLKAR4"  # walked for exercise >= 20 min a day, >= 10 times, at age >= 50
AMOUNT_ITEMS = {"years": "V10WKYRAR4", "months": "V10WKMOAR4", "times": "V10WKTMAR4"}
WALKER_VALUES = {"non-walker": False, "walker": True, "exclude": None}


def walking_answers(walker_item: str = WALKER_ITEM) -> pl.DataFrame:
    """ID, walk_item (1 yes, 0 no, null), amount_years, amount_months, amount_times (codes)."""
    ac10 = read_table("allclinical", "10")
    col = partial(find_col, ac10, where="allclinical10")
    return ac10.select(
        pl.col(col("ID")).alias("ID"),
        pl.col(col(walker_item)).alias("walk_item"),
        *[pl.col(col(item)).alias(f"amount_{name}") for name, item in AMOUNT_ITEMS.items()],
    )


def walker_status(*, yes_without_amount_as: str, missing_as: str) -> pl.Expr:
    """`walker` (Boolean; null = excluded) from walk_item and the amount_* columns."""
    no_amount = pl.all_horizontal([pl.col(f"amount_{name}").is_null() for name in AMOUNT_ITEMS])
    yes_value = (
        pl.when(no_amount)
        .then(pl.lit(WALKER_VALUES[yes_without_amount_as], dtype=pl.Boolean))
        .otherwise(True)
    )
    return (
        pl.when(pl.col("walk_item") == 1)
        .then(yes_value)
        .when(pl.col("walk_item") == 0)
        .then(False)
        .otherwise(pl.lit(WALKER_VALUES[missing_as], dtype=pl.Boolean))
        .alias("walker")
    )


def _amount(name: str, midpoints: Sequence[float]) -> pl.Expr:
    mapping = {code + 1: float(value) for code, value in enumerate(midpoints)}
    return pl.col(f"amount_{name}").replace_strict(mapping, default=None, return_dtype=pl.Float64)


def walking_sessions(midpoints: Mapping[str, Sequence[float]]) -> pl.Expr:
    """Sessions since age 50: years x months/year x times/month at category midpoints."""
    return (
        _amount("years", midpoints["years"])
        * _amount("months", midpoints["months"])
        * _amount("times", midpoints["times"])
    ).alias("sessions")
