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
# Interim visit before each follow-up reading: its knee pain predicts being read at that reading
INTERIM_BEFORE = {"08": "07", "10": "09"}


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

    - read_08, read_10: the knee has a follow-up interval ending at that visit (`periods`);
    - event_08: the knee's V08 interval had the event (so it leaves the risk set for V10);
    - any_read: read at either visit;
    - known: status by the horizon is known (`horizon.event` not null).
    """
    ends = periods.group_by(KEYS).agg(
        (pl.col("end_visit") == "08").any().alias("read_08"),
        (pl.col("end_visit") == "10").any().alias("read_10"),
        ((pl.col("end_visit") == "08") & pl.col("event").cast(pl.Boolean)).any().alias("event_08"),
    )
    flags = ["read_08", "read_10", "event_08"]
    return (
        horizon.join(ends, on=KEYS, how="left")
        .with_columns(pl.col(f).fill_null(False) for f in flags)
        .with_columns(
            (pl.col("read_08") | pl.col("read_10")).alias("any_read"),
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
    """ID, SIDE, womac_<v>, freq_pain_<v> for each interim visit in INTERIM_BEFORE, wide.

    `per_visit` is long: ID, SIDE, visit, womac, freq_pain. A knee whose person missed the visit
    has nulls there (the weight model codes that as its own indicator).
    """
    wanted = sorted(INTERIM_BEFORE.values())
    long = per_visit.filter(pl.col("visit").is_in(wanted))
    out = long.select(KEYS).unique()
    for v in wanted:
        one = long.filter(pl.col("visit") == v).select(
            *KEYS, pl.col("womac").alias(f"womac_{v}"), pl.col("freq_pain").alias(f"freq_pain_{v}")
        )
        out = out.join(one, on=KEYS, how="left")
    return out
