"""Person-wave device measures, count-based and step-based (moved from analyses/walking_steps).

Count-based measures are the release's (oai.derive.accel). Step-based walking bouts mirror its
purposeful MV bouts with steps in place of counts: the same 10-minute bout rule (8 of 10 minutes
at or above the threshold to start, stop at 3 below) on wear minutes with at least `c`
steps/min, and a bout counts when it lasts at least device.purposeful_bout_minutes.

`covariates_48` (moved from analyses/crepitus_activity) gives the 48-month person covariates the
device analyses share.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

import numpy as np
import polars as pl

from oai.derive.accel import (
    DAY_KEY_SCALE,
    DeviceRules,
    StepRules,
    bout_spans,
    daily_summary,
    first_valid_days,
    nonwear_mask,
    person_summary,
)
from oai.derive.knee import find_col, xray_readings
from oai.loader import read_table

COVARIATES = ("age", "sex", "bmi", "kl_max", "womac_pain_max")
COUNT_MEASURES = ["counts_per_day", "mv_min", "light_min", "purposeful_min", "bout_days_per_week"]


def step_bout_measures(cadence: int) -> list[str]:
    return [f"step_bout{cadence}_min", f"step_bout{cadence}_days_per_week"]


def step_bouts_daily(
    minutes: pl.DataFrame, rules: DeviceRules, cadences: list[int]
) -> pl.DataFrame:
    """ID, day and, per cadence c, step_bout<c>_min (minutes in walking bouts) and step_bouts<c>."""
    m = minutes.sort(["ID", "day", "minute"])
    key = m["ID"].to_numpy() * DAY_KEY_SCALE + m["day"].to_numpy()
    wear = ~nonwear_mask(m["cnt"].to_numpy(), key, rules)
    steps = m["steps"].cast(pl.Float64).to_numpy()
    cols = []
    for c in cadences:
        in_bout = np.zeros(len(m), dtype=bool)
        bout_start = np.zeros(len(m), dtype=bool)
        for start, end in zip(
            *bout_spans(steps, key, wear, replace(rules, mv_cutpoint=c)), strict=True
        ):
            if end - start >= rules.purposeful_bout_minutes:
                in_bout[start:end] = True
                bout_start[start] = True
        cols += [pl.Series(f"_in{c}", in_bout), pl.Series(f"_start{c}", bout_start)]
    return (
        m.select("ID", "day")
        .with_columns(cols)
        .group_by(["ID", "day"], maintain_order=True)
        .agg(
            *[pl.col(f"_in{c}").sum().alias(f"step_bout{c}_min") for c in cadences],
            *[pl.col(f"_start{c}").sum().alias(f"step_bouts{c}") for c in cadences],
        )
    )


def person_wave(
    minutes: pl.DataFrame, rules: DeviceRules, cadences: list[int], min_step_days: int
) -> pl.DataFrame:
    """One row per person: count measures (person_summary), step measures and step bouts.

    Step measures are means over the person's first valid days (chosen by wear) whose steps are
    complete, and are null when fewer than `min_step_days` such days exist.
    """
    step_rules = StepRules(cadence_cutpoints=tuple(cadences))
    daily = daily_summary(minutes, rules, step_rules).join(
        step_bouts_daily(minutes, rules, cadences), on=["ID", "day"], how="left"
    )
    bout_cols = [f"step_bout{c}_min" for c in cadences] + [f"step_bouts{c}" for c in cadences]
    daily = daily.with_columns(  # a day whose steps are unusable has no step bouts either
        pl.when(pl.col("steps").is_not_null()).then(pl.col(b)).alias(b) for b in bout_cols
    )
    persons = person_summary(daily, rules, step_rules)
    bouts = (
        first_valid_days(daily, rules)
        .group_by("ID")
        .agg(
            *[pl.col(f"step_bout{c}_min").mean() for c in cadences],
            *[
                ((pl.col(f"step_bouts{c}").drop_nulls() > 0).mean() * 7).alias(
                    f"step_bout{c}_days_per_week"
                )
                for c in cadences
            ],
        )
    )
    step_cols = [c for c in persons.columns if c.startswith(("steps", "peak_cadence", "cadence"))]
    step_cols += [m for c in cadences for m in step_bout_measures(c)]
    enough = pl.col("step_days") >= min_step_days
    return persons.join(bouts, on="ID", how="left").with_columns(
        pl.when(enough).then(pl.col(c)).alias(c) for c in step_cols
    )


def mean_over_waves(
    device: pl.DataFrame, measures: Sequence[str], waves: Sequence[str] | None = None
) -> pl.DataFrame:
    """One row per person: n_waves and each measure's mean over the person's valid waves.

    `device` has one row per person and wave (`ID`, `wave`, `valid` and the measures), as
    person_wave() writes. `waves` keeps only those waves (one wave gives that wave's values). A
    measure missing at one wave is the mean of the others (nulls are skipped). Sorted by ID.
    """
    valid = device.filter("valid")
    if waves is not None:
        valid = valid.filter(pl.col("wave").is_in(list(waves)))
    return (
        valid.group_by("ID")
        .agg(pl.len().alias("n_waves"), *[pl.col(m).mean() for m in measures])
        .sort("ID")
    )


DEVICE_KEYS = (
    "nonwear_minutes",
    "interrupt_minutes",
    "interrupt_ceiling",
    "valid_day_hours",
    "max_valid_days",
    "min_valid_days",
    "mv_cutpoint",
    "light_floor",
    "bout_window",
    "bout_need",
    "bout_stop_below",
    "purposeful_bout_minutes",
)


def device_rules(assumptions) -> DeviceRules:
    """DeviceRules from the ledger's device.* entries."""
    return DeviceRules(**{k: assumptions[f"device.{k}"] for k in DEVICE_KEYS})


def covariates_48(project: int = 15) -> pl.DataFrame:
    """ID, age, sex, bmi at 48 months; kl_max (higher Project 15 KL of the knees) and
    womac_pain_max (worse knee's WOMAC pain) at 48 months."""
    enrollees = read_table("enrollees", None)
    sex = enrollees.select(
        pl.col(find_col(enrollees, "ID")).cast(pl.Int64).alias("ID"),
        pl.col(find_col(enrollees, "P02SEX")).cast(pl.Int64).alias("sex"),
    )
    clin = read_table("allclinical", "06")
    col = lambda n: pl.col(find_col(clin, n, where="allclinical06"))  # noqa: E731
    base = clin.select(
        col("ID").cast(pl.Int64).alias("ID"),
        col("V06AGE").cast(pl.Float64).alias("age"),
        col("V06BMI").cast(pl.Float64).alias("bmi"),
        pl.max_horizontal(
            col("V06WOMKPR").cast(pl.Float64), col("V06WOMKPL").cast(pl.Float64)
        ).alias("womac_pain_max"),
    )
    kl = (
        xray_readings(["06"], project=project)
        .group_by("ID")
        .agg(pl.col("KL").max().alias("kl_max"))
        .with_columns(pl.col("ID").cast(pl.Int64))
    )
    return (
        sex.join(base, on="ID", how="left").join(kl, on="ID", how="left").select("ID", *COVARIATES)
    )
