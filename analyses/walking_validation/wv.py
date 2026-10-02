"""Walking-validation helpers: combine device waves, the device reference, amount levels and the
link to the Lo 2022 replication's knee frame."""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import polars as pl

from oai.derive.accel import DeviceRules
from oai.errors import OAIError

MEASURES = ("purposeful_min", "counts_per_day", "light_min", "bout_days_per_week")
OUTCOMES = ("new_pain", "kl_worse", "jsn_worse", "improved_pain")
LO2022 = "lo2022_walking"
# The assumptions that change how the minute files are processed (every DeviceRules field).
# device.wave_combination is not one: it only chooses which waves the cohort step combines.
DEVICE_RULE_KEYS = tuple(f"device.{f.name}" for f in dataclasses.fields(DeviceRules))


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
    persons: pl.DataFrame,
    rule: str,
    min_bout_days: float,
    min_bout_minutes: float,
    wave: str | None = None,
) -> pl.DataFrame:
    """Add device_walker, the reference standard, from the combined measures.

    With `wave` ("06"/"08"), add device_walker_<wave> from that wave's own measures instead
    (<measure>_<wave>); it is null where the person has no valid wave there.
    """
    suffix = "" if wave is None else f"_{wave}"
    bout_days = pl.col(f"bout_days_per_week{suffix}")
    rules = {
        "bout_days": bout_days >= min_bout_days,
        "any_bout": bout_days > 0,
        "bout_minutes": pl.col(f"purposeful_min{suffix}") * 7 >= min_bout_minutes,
    }
    if rule not in rules:
        raise ValueError(f"reference.walker_rule must be one of {', '.join(rules)}, not {rule!r}")
    return persons.with_columns(rules[rule].alias(f"device_walker{suffix}"))


def with_amount_level(persons: pl.DataFrame) -> pl.DataFrame:
    """amount_level: 'none' (non-walker), 'lower'/'upper' half of sessions among walkers.

    The median is null only when no walker has an amount. There is then no split, so walkers get
    no level (and the comparison with a null median, which polars warns about, is not built).
    """
    median = persons.filter(pl.col("walker") & pl.col("sessions").is_not_null())[
        "sessions"
    ].median()
    half = (
        pl.lit(None, dtype=pl.String)
        if median is None
        else pl.when(pl.col("sessions") <= median).then(pl.lit("lower")).otherwise(pl.lit("upper"))
    )
    level = (
        pl.when(pl.col("walker").is_null())
        .then(pl.lit(None, dtype=pl.String))
        .when(~pl.col("walker"))
        .then(pl.lit("none"))
        .when(pl.col("sessions").is_null())
        .then(pl.lit(None, dtype=pl.String))
        .otherwise(half)
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


def check_walker_coding(answered: pl.DataFrame, lo_people: pl.DataFrame) -> None:
    """Stop if any participant in both frames is a walker in one coding and not in the other.

    The replication's frame codes every participant it keeps (lo2022.py drops a null walker
    before building it), so a null lo_walker means a frame this step cannot trust: stop rather
    than skip the comparison for it.
    """
    nulls = lo_people.filter(pl.col("lo_walker").is_null()).height
    if nulls:
        who = "1 Lo 2022 participant has" if nulls == 1 else f"{nulls} Lo 2022 participants have"
        raise CohortError(
            f"{who} no walker code in the {LO2022} frame, which codes every participant it keeps; "
            "rebuild the frame"
        )
    differ = (
        answered.select("ID", "walker")
        .join(lo_people.select("ID", "lo_walker"), on="ID", how="inner")
        .filter(pl.col("walker") != pl.col("lo_walker"))
        .height
    )
    if differ:
        raise CohortError(
            f"{differ} Lo 2022 participant{'s' if differ != 1 else ''} coded differently here "
            f"and in {LO2022}; check that bias.lo2022_label names a run with this run's "
            "exposure coding"
        )


def lo_command(label: str) -> str:
    """The command that produces the replication's run `label` (its default run takes no
    --variant)."""
    return f"oai run {LO2022}" + ("" if label == "default" else f" --variant {label}")


def read_lo_frame(
    work_dir: Path, label: str, yes_without_amount_as: str
) -> tuple[pl.DataFrame, dict]:
    """The replication's knee frame and resolved assumptions for `label`, checked for coding."""
    d = work_dir / LO2022 / label
    frame, resolved = d / "frame.parquet", d / "assumptions.resolved.json"
    command = lo_command(label)
    if not frame.is_file() or not resolved.is_file():
        raise CohortError(f"no {LO2022} frame for {label!r} in {d}; run `{command}` first")
    values = {k: v["value"] for k, v in json.loads(resolved.read_text())["assumptions"].items()}
    coding = values["exposure.yes_without_amount_as"]
    if coding != yes_without_amount_as:
        raise CohortError(
            f"set bias.lo2022_label to the label of a {LO2022} run that codes yes-without-amount "
            f"as {yes_without_amount_as!r}, or run {LO2022} with a variant that does "
            f"(`{lo_command('<variant>')}`) and use its label; {LO2022} {label!r} codes it as "
            f"{coding!r}, but this run uses {yes_without_amount_as!r}"
        )
    return pl.read_parquet(frame), values


def read_lo_results(lo_results: Path, label: str) -> dict[str, bytes]:
    """The replication's Table 2 rows and table, as {file name here: CSV bytes}.

    Reads and checks both files without writing anything: comparison.csv gives lo2022_t2.csv
    (its t2.* rows), table2.csv gives lo2022_table2.csv.
    """
    out: dict[str, bytes] = {}
    for name, target in (("comparison.csv", "lo2022_t2.csv"), ("table2.csv", "lo2022_table2.csv")):
        source = lo_results / name
        if not source.is_file():
            raise CohortError(f"{source} is missing; run `{lo_command(label)}` first")
        if name == "comparison.csv":
            comparison = pl.read_csv(source)
            if "metric" not in comparison.columns:
                raise CohortError(f"{source} has no metric column; run `{lo_command(label)}` again")
            t2 = comparison.filter(pl.col("metric").str.starts_with("t2."))
            if t2.is_empty():
                raise CohortError(
                    f"{source} has no t2.* rows to copy as {target}; "
                    f"run `{lo_command(label)}` again"
                )
            out[target] = t2.write_csv().encode()
        else:
            out[target] = source.read_bytes()
    return out


def lo_knee_columns(lo_knees: pl.DataFrame, covariates: Sequence[str], label: str) -> pl.DataFrame:
    """The columns of the replication's knee frame the R steps read.

    Stops, naming the columns, if the frame lacks any, rather than passing a narrower frame on.
    """
    keep = ["ID", "SIDE", "walker", *dict.fromkeys(["age", "sex", "bmi", *covariates]), *OUTCOMES]
    missing = [c for c in keep if c not in lo_knees.columns]
    if missing:
        raise CohortError(
            f"the {LO2022} frame for {label!r} lacks column{'s' if len(missing) != 1 else ''} "
            f"{', '.join(missing)}; rebuild it with `{lo_command(label)}`"
        )
    return lo_knees.select(keep)


def cohort_flow(
    answered: pl.DataFrame, persons: pl.DataFrame, lo_people: pl.DataFrame
) -> pl.DataFrame:
    """The cohort step's flow: the validation sample, then the Lo 2022 cohort's own steps.

    `answered` are the walking-item respondents, `persons` the validation sample (with `in_lo`)
    and `lo_people` the Lo 2022 cohort. A Lo participant who did not answer the item is excluded
    at lo2022_answered_item (the replication codes them as non-walkers), whether or not they
    have a device wave.
    """
    steps = {
        "answered_walking_item": answered.height,
        "with_valid_device_wave": persons.height,
        "lo2022_cohort": lo_people.height,
        "lo2022_answered_item": lo_people.join(answered.select("ID"), on="ID", how="semi").height,
        "lo2022_answered_with_device": persons.filter("in_lo").height,
    }
    return pl.DataFrame({"step": list(steps), "persons": list(steps.values())})


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


def without_ungradable_device_rows(
    published: Mapping[str, Any], values: Mapping[str, Any], defaults: Mapping[str, Any]
) -> tuple[dict[str, Any], list[str], list[str]]:
    """The published rows a run can be graded against: (rows, changed rules, omitted rows).

    The device.* rows are the release's own counts, produced by the ledger's device rules. A run
    that changes one of those rules (for example `nonwear60`) would be graded against counts it
    cannot be expected to match, so its device.* rows are dropped. oai.replication has no "not
    graded" verdict; the caller reports what was omitted.
    """
    changed = [key for key in DEVICE_RULE_KEYS if values[key] != defaults[key]]
    if not changed:
        return dict(published), [], []
    omitted = [metric for metric in published if metric.startswith("device.")]
    return {m: v for m, v in published.items() if m not in omitted}, changed, omitted
