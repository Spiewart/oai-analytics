"""Post hoc checks on P1 (user request 2026-11-12, after the primary results were seen).

Three checks on the incident-ROA association with steps at 48 months:
- which knees were read: the share of knees at risk with a later reading, by step band;
- knee injury: a per-knee flag for an injury reported by 48 months;
- reweighting: inverse-probability-of-being-read weights for each follow-up interval
  (fitted in posthoc.R from the frame built here).

Pure functions on polars frames; `posthoc_frame.py` reads the release and writes the frames.
"""

from __future__ import annotations

from collections.abc import Sequence

import polars as pl

KEYS = ["ID", "SIDE"]
# Interim visits whose 12-month knee-injury item (V##INJ{side}12) covers the time up to 48 months
INJURY_VISITS = ("01", "03", "05", "06")
# Interim visit before each follow-up reading: its knee pain predicts being read at that reading.
# V12 (120 months) is a follow-up reading only under periods.horizon = "12".
INTERIM_BEFORE = {"08": "07", "10": "09", "12": "11"}


def injury_flags(raw: pl.DataFrame, visits: Sequence[str] = INJURY_VISITS) -> pl.DataFrame:
    """ID, SIDE, injury_48, surgery_00 from per-knee answers.

    `raw` has ID, SIDE, inj_ever (baseline "ever injured badly enough to limit walking"),
    surg_ever (baseline "ever had knee surgery") and inj12_<visit> (injury in the past 12 months)
    coded 1/0/null. injury_48 is True when any answer is 1; False when the baseline answer is 0
    and no later answer is 1 (a missed interim visit counts as no reported injury); null when the
    baseline answer is blank and no later answer is 1.
    """
    later = [pl.col(f"inj12_{v}") == 1 for v in visits]
    any_yes = (pl.col("inj_ever") == 1).fill_null(False) | pl.any_horizontal(later).fill_null(False)
    return raw.select(
        *KEYS,
        pl.when(any_yes)
        .then(True)
        .when(pl.col("inj_ever") == 0)
        .then(False)
        .otherwise(None)
        .alias("injury_48"),
        (pl.col("surg_ever") == 1).alias("surgery_00"),
    )


def read_flags(horizon: pl.DataFrame, periods: pl.DataFrame) -> pl.DataFrame:
    """The incident-ROA sample (`horizon`, one row per knee) with what was read afterwards.

    For each follow-up reading <v> in `periods.end_visit` (keys of INTERIM_BEFORE):
    - read_<v>: the knee has a follow-up interval ending at that visit;
    - prior_event_<v>: an earlier interval had the event (so the knee is not at risk at <v>).
    And any_read (read at any of them) and known (`horizon.event` not null).
    """
    ends = sorted(periods["end_visit"].unique().to_list())
    unknown = set(ends) - set(INTERIM_BEFORE)
    if unknown:
        raise ValueError(f"no interim visit for follow-up reading(s) {sorted(unknown)}")
    event = pl.col("event").cast(pl.Boolean)
    per_knee = periods.group_by(KEYS).agg(
        *((pl.col("end_visit") == v).any().alias(f"read_{v}") for v in ends),
        *(((pl.col("end_visit") < v) & event).any().alias(f"prior_event_{v}") for v in ends),
    )
    flags = [c for c in per_knee.columns if c not in KEYS]
    return (
        horizon.join(per_knee, on=KEYS, how="left")
        .with_columns(pl.col(f).fill_null(False) for f in flags)
        .with_columns(
            pl.any_horizontal(f"read_{v}" for v in ends).alias("any_read"),
            pl.col("event").is_not_null().alias("known"),
        )
    )


def read_share(flags: pl.DataFrame, bands: Sequence[str]) -> pl.DataFrame:
    """Aggregate by step band: knees, share read, share with known status, incidence among known,
    and the band's makeup (women, injury by 48 months, KL 1, mean age and BMI). Knees without a
    band (no steps) are left out."""
    return (
        flags.filter(pl.col("steps_band").is_not_null())
        .group_by("steps_band")
        .agg(
            pl.len().alias("knees"),
            pl.col("any_read").mean().alias("share_read"),
            pl.col("known").mean().alias("share_known"),
            pl.col("event").cast(pl.Float64).mean().alias("incidence_known"),
            (pl.col("sex") == 2).mean().alias("share_women"),
            pl.col("injury_48").cast(pl.Float64).mean().alias("share_injury"),
            (pl.col("kl48") == 1).mean().alias("share_kl1"),
            pl.col("age").mean().alias("mean_age"),
            pl.col("bmi").mean().alias("mean_bmi"),
        )
        .with_columns(pl.col("steps_band").cast(pl.Enum(list(bands))))
        .sort("steps_band")
        .with_columns(pl.col("steps_band").cast(pl.String))
    )


def interim_pain(per_visit: pl.DataFrame) -> pl.DataFrame:
    """ID, SIDE, womac_<v>, freq_pain_<v> for each interim visit in `per_visit`, wide.

    `per_visit` is long: ID, SIDE, visit, womac, freq_pain. A knee whose person missed the visit
    has nulls there (the weight model codes that as its own indicator).
    """
    long = per_visit
    wanted = sorted(long["visit"].unique().to_list())
    out = long.select(KEYS).unique()
    for v in wanted:
        one = long.filter(pl.col("visit") == v).select(
            *KEYS, pl.col("womac").alias(f"womac_{v}"), pl.col("freq_pain").alias(f"freq_pain_{v}")
        )
        out = out.join(one, on=KEYS, how="left")
    return out
