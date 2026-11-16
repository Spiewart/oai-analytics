"""The device walker definitions of walking_steps. The person-wave device measures moved to
oai.derive.devices and are re-exported here for this analysis's steps."""

from __future__ import annotations

import polars as pl

from oai.derive.devices import (  # noqa: F401 (re-exported)
    COUNT_MEASURES,
    DEVICE_KEYS,
    device_rules,
    mean_over_waves,
    person_wave,
    step_bout_measures,
    step_bouts_daily,
)


def combine(device: pl.DataFrame, measures: list[str]) -> pl.DataFrame:
    """Per person over valid waves: the mean of each measure (nulls skipped) and n_waves.

    `device` has one row per person and wave (`wave`, `valid`); oai.derive.devices.mean_over_waves,
    as walking_validation's combine_waves uses.
    """
    return mean_over_waves(device, measures)


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


def device_waves(device: pl.DataFrame, definitions, measures: list[str]) -> dict[str, pl.DataFrame]:
    """Walker status per person for each device basis: wave "06", wave "08", the "mean" of valid
    waves, and "either" valid wave. Every basis keeps the same people for every definition (those
    with step measures); "either" is limited to the people in "mean".
    """

    def with_walkers(df: pl.DataFrame) -> pl.DataFrame:
        common = df.filter(pl.col("steps").is_not_null())  # the same people for every definition
        return common.with_columns(expr.alias(name) for name, _, expr in definitions)

    wave = {
        w: with_walkers(device.filter(pl.col("valid") & (pl.col("wave") == w)))
        for w in ("06", "08")
    }
    wave["mean"] = with_walkers(combine(device, measures))
    # Either week: a device walker when any valid wave meets the definition (for the self-reports
    # paired with the mean of both waves). Same people as "mean": the combined step measures exist.
    names = [name for name, _, _ in definitions]
    wave["either"] = either_week(pl.concat([wave["06"], wave["08"]], how="diagonal"), names).join(
        wave["mean"].select("ID"), on="ID", how="semi"
    )
    return wave


def device_inputs(A) -> tuple[list, list[str]]:
    """(walker definitions, device measures) as pro_validity and discordance_frame use them."""
    cadences = [int(c) for c in A["reference.step_cadences"]]
    step_measures = ["steps", "peak_cadence"]
    step_measures += [f"cadence{c}_min" for c in cadences]
    step_measures += [m for c in cadences for m in step_bout_measures(c)]
    definitions = walker_definitions(
        A["reference.min_bout_days_per_week"], A["reference.min_bout_minutes_per_week"], cadences
    )
    return definitions, COUNT_MEASURES + step_measures
