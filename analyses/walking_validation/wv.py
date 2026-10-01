"""Walking-validation helpers: combine device waves, the device reference, amount levels and the
link to the Lo 2022 replication's knee frame."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from oai.errors import OAIError

MEASURES = ("purposeful_min", "counts_per_day", "light_min", "bout_days_per_week")
OUTCOMES = ("new_pain", "kl_worse", "jsn_worse", "improved_pain")
LO2022 = "lo2022_walking"


class CohortError(OAIError):
    """The Lo 2022 frame needed here is missing or was built with another exposure coding."""


def combine_waves(device: pl.DataFrame, combination: str) -> pl.DataFrame:
    """One row per person over their valid waves: the mean ("mean") or one wave ("06"/"08").

    Also returns each wave's measures as <measure>_06 / <measure>_08 and n_waves.
    """
    if combination not in ("mean", "06", "08"):
        raise ValueError(f"combination must be 'mean', '06' or '08', not {combination!r}")
    valid = device.filter("valid")
    per_wave = valid.select("ID")
    for wave in ("06", "08"):
        one = valid.filter(pl.col("wave") == wave).select(
            "ID", *[pl.col(m).alias(f"{m}_{wave}") for m in MEASURES]
        )
        per_wave = per_wave.join(one, on="ID", how="left")
    per_wave = per_wave.unique("ID")
    used = valid if combination == "mean" else valid.filter(pl.col("wave") == combination)
    combined = used.group_by("ID").agg(
        pl.len().alias("n_waves"), *[pl.col(m).mean() for m in MEASURES]
    )
    return combined.join(per_wave, on="ID", how="left").sort("ID")


def with_device_walker(
    persons: pl.DataFrame, rule: str, min_bout_days: float, min_bout_minutes: float
) -> pl.DataFrame:
    """Add device_walker, the reference standard."""
    rules = {
        "bout_days": pl.col("bout_days_per_week") >= min_bout_days,
        "any_bout": pl.col("bout_days_per_week") > 0,
        "bout_minutes": pl.col("purposeful_min") * 7 >= min_bout_minutes,
    }
    if rule not in rules:
        raise ValueError(f"reference.walker_rule must be one of {', '.join(rules)}, not {rule!r}")
    return persons.with_columns(rules[rule].alias("device_walker"))


def with_amount_level(persons: pl.DataFrame) -> pl.DataFrame:
    """amount_level: 'none' (non-walker), 'lower'/'upper' half of sessions among walkers."""
    median = persons.filter(pl.col("walker") & pl.col("sessions").is_not_null())[
        "sessions"
    ].median()
    level = (
        pl.when(pl.col("walker").is_null())
        .then(pl.lit(None, dtype=pl.String))
        .when(~pl.col("walker"))
        .then(pl.lit("none"))
        .when(pl.col("sessions").is_null())
        .then(pl.lit(None, dtype=pl.String))
        .when(pl.col("sessions") <= median)
        .then(pl.lit("lower"))
        .otherwise(pl.lit("upper"))
    )
    return persons.with_columns(level.alias("amount_level"))


def person_outcomes(knees: pl.DataFrame) -> pl.DataFrame:
    """Per person: lo_walker and <outcome>_any (any knee with the event; null if none observed)."""
    return knees.group_by("ID").agg(
        pl.col("walker").first().alias("lo_walker"),
        *[
            pl.when(pl.col(o).is_not_null().any())
            .then(pl.col(o).fill_null(False).any())
            .alias(f"{o}_any")
            for o in OUTCOMES
        ],
    )


def read_lo_frame(
    work_dir: Path, label: str, yes_without_amount_as: str
) -> tuple[pl.DataFrame, dict]:
    """The replication's knee frame and resolved assumptions for `label`, checked for coding."""
    d = work_dir / LO2022 / label
    frame, resolved = d / "frame.parquet", d / "assumptions.resolved.json"
    if not frame.is_file() or not resolved.is_file():
        command = f"oai run {LO2022}" + ("" if label == "default" else f" --variant {label}")
        raise CohortError(f"no {LO2022} frame for {label!r} in {d}; run `{command}` first")
    values = {k: v["value"] for k, v in json.loads(resolved.read_text())["assumptions"].items()}
    coding = values["exposure.yes_without_amount_as"]
    if coding != yes_without_amount_as:
        raise CohortError(
            f"{LO2022} {label!r} codes yes-without-amount as {coding!r}, but this run uses "
            f"{yes_without_amount_as!r}; set bias.lo2022_label to the matching run"
        )
    return pl.read_parquet(frame), values


def lo_model(values: dict) -> dict[str, str]:
    """The replication's Table 2 model, as models.R builds it."""
    kl_term = "factor(kl0)" if values["model.kl_covariate"] == "factor" else "kl0"
    covariates = [kl_term if c == "kl0" else c for c in values["model.covariates"]]
    return {
        "or_unadj": "walker",
        "or_adj": " + ".join(["walker", *covariates]),
        "corstr": values["model.corstr"],
        "covariates": ",".join(values["model.covariates"]),
    }
