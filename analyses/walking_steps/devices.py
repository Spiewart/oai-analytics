"""The device walker definitions of walking_steps. The person-wave device measures moved to
oai.derive.devices and are re-exported here for this analysis's steps."""

from __future__ import annotations

import polars as pl

from oai.derive.devices import (  # noqa: F401 (re-exported)
    COUNT_MEASURES,
    DEVICE_KEYS,
    device_rules,
    person_wave,
    step_bout_measures,
    step_bouts_daily,
)


def combine(device: pl.DataFrame, measures: list[str]) -> pl.DataFrame:
    """Per person over valid waves: the mean of each measure (nulls skipped) and n_waves.

    `device` has one row per person and wave (`wave`, `valid`). As walking_validation's
    combine_waves, but a step measure missing at one wave uses the other wave alone.
    """
    return (
        device.filter("valid")
        .group_by("ID")
        .agg(pl.len().alias("n_waves"), *[pl.col(m).mean() for m in measures])
        .sort("ID")
    )


def walker_definitions(min_bout_days: float, min_bout_minutes: float, cadences: list[int]):
    """(name, family, expression) for every device walker definition.

    Each family uses one bout measure: count MV bouts or step walking bouts at a cadence. Each
    has the three walking_validation rules: bout days >= min_bout_days a week, any bout, or
    bout minutes >= min_bout_minutes a week.
    """
    families = [("counts_mv", "purposeful_min", "bout_days_per_week")]
    families += [
        (f"steps_{c}", f"step_bout{c}_min", f"step_bout{c}_days_per_week") for c in cadences
    ]
    out = []
    for family, minutes, days in families:
        out += [
            (f"{family}:bout_days", family, pl.col(days) >= min_bout_days),
            (f"{family}:any_bout", family, pl.col(days) > 0),
            (f"{family}:bout_minutes", family, pl.col(minutes) * 7 >= min_bout_minutes),
        ]
    return out


def either_week(per_wave: pl.DataFrame, names: list[str]) -> pl.DataFrame:
    """Per person: each walker definition is true when any of their valid waves meets it.

    `per_wave` has one row per person and valid wave, with a Boolean column per name.
    """
    return per_wave.group_by("ID").agg(pl.col(n).any() for n in names).sort("ID")
