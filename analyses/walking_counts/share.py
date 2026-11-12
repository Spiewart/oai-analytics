"""How much of the count-based activity measures fall in walking minutes (by per-minute steps).

A walking minute is a wear minute whose step count is at least a cadence threshold. For each
threshold, `shares` reports what part of the wear counts, MV minutes, MV-bout minutes and
light minutes are walking minutes, and what part of the walking minutes reach MV, both pooled
over all analysis minutes and as the distribution of per-person shares.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from oai.derive.accel import (
    DAY_KEY_SCALE,
    DeviceRules,
    bout_mask,
    daily_summary,
    first_valid_days,
    nonwear_mask,
)

# measure name -> (numerator, denominator), both over analysis wear minutes; `walk` is set per
# cadence threshold
MEASURES: dict[str, tuple[pl.Expr, pl.Expr]] = {
    "wear_counts_in_walking": (pl.col("cnt") * pl.col("walk"), pl.col("cnt")),
    "mv_minutes_walking": (pl.col("mv") & pl.col("walk"), pl.col("mv")),
    "mv_bout_minutes_walking": (pl.col("bout") & pl.col("walk"), pl.col("bout")),
    "light_minutes_walking": (pl.col("light") & pl.col("walk"), pl.col("light")),
    "wear_minutes_walking": (pl.col("walk"), pl.col("walk").is_not_null()),
    "walking_minutes_reaching_mv": (pl.col("walk") & pl.col("mv"), pl.col("walk")),
}


def analysis_minutes(
    minutes: pl.DataFrame, rules: DeviceRules, min_step_days: int
) -> tuple[pl.DataFrame, dict[str, int]]:
    """Wear minutes on each person's analysis days, with intensity and bout flags, and a flow.

    Analysis days are a person's first valid days (chosen by wear, as in person_summary) whose
    steps are complete; a person needs at least `min_step_days` of them. `minutes` comes from
    read_minutes(visit, steps=True).
    """
    m = minutes.sort(["ID", "day", "minute"])
    key = m["ID"].to_numpy() * DAY_KEY_SCALE + m["day"].to_numpy()
    cnt = m["cnt"].to_numpy()
    wear = ~nonwear_mask(cnt, key, rules)
    m = m.with_columns(
        pl.Series("wear", wear),
        pl.Series("bout", bout_mask(cnt, key, wear, rules)),
        pl.Series("cnt", np.nan_to_num(cnt, nan=0.0)),
    )
    valid = first_valid_days(daily_summary(minutes, rules), rules)
    complete = valid.filter(pl.col("steps").is_not_null())
    counted = complete.group_by("ID").len().filter(pl.col("len") >= min_step_days)
    days = complete.join(counted.select("ID"), on="ID").select("ID", "day")
    w = (
        m.join(days, on=["ID", "day"])
        .filter("wear")
        .with_columns(
            (pl.col("cnt") >= rules.mv_cutpoint).alias("mv"),
            ((pl.col("cnt") >= rules.light_floor) & (pl.col("cnt") < rules.mv_cutpoint)).alias(
                "light"
            ),
        )
        .select("ID", "day", "cnt", "steps", "mv", "light", "bout")
    )
    persons_valid = valid.group_by("ID").len().filter(pl.col("len") >= rules.min_valid_days)
    flow = {
        "persons_in_files": m["ID"].n_unique(),
        "persons_valid": persons_valid.height,
        "valid_days": valid.height,
        "valid_days_steps_incomplete": valid.height - complete.height,
        "persons_analysed": counted.height,
        "analysis_days": days.height,
        "analysis_wear_minutes": w.height,
    }
    return w, flow


def shares(w: pl.DataFrame, cadences: list[int]) -> pl.DataFrame:
    """Per cadence threshold and measure: pooled share and per-person quartiles.

    Per-person shares use only people with a non-zero denominator (`persons`); someone with no
    MV bouts, say, has no MV-bout share rather than a share of zero.
    """
    rows = []
    for cad in cadences:
        x = w.with_columns((pl.col("steps") >= cad).alias("walk"))
        for name, (num, den) in MEASURES.items():
            totals = x.select(num.cast(pl.Float64).sum().alias("n"), den.sum().alias("d"))
            n, d = totals.row(0)
            per = (
                x.group_by("ID")
                .agg(num.cast(pl.Float64).sum().alias("n"), den.cast(pl.Float64).sum().alias("d"))
                .filter(pl.col("d") > 0)
                .select((pl.col("n") / pl.col("d")).alias("s"))["s"]
            )
            rows.append(
                {
                    "cadence_ge": cad,
                    "measure": name,
                    "pooled": n / d if d else None,
                    "person_q1": per.quantile(0.25),
                    "person_median": per.median(),
                    "person_q3": per.quantile(0.75),
                    "persons": per.len(),
                }
            )
    return pl.DataFrame(rows)


def cadence_bands(w: pl.DataFrame, edges: list[int], mv_cutpoint: float) -> pl.DataFrame:
    """Minutes, counts and MV share by cadence band; 0 steps is its own band below edges[0]."""
    labels = ["0"] + [f"{a}-{b - 1}" for a, b in zip(edges, edges[1:], strict=False)]
    labels.append(f"{edges[-1]}+")
    breaks = [e - 0.5 for e in edges]
    return (
        w.with_columns(pl.col("steps").cut(breaks, labels=labels).alias("band"))
        .group_by("band")
        .agg(
            pl.len().alias("minutes"),
            pl.col("cnt").sum().alias("counts"),
            pl.col("cnt").median().alias("median_counts_per_min"),
            (pl.col("cnt") >= mv_cutpoint).mean().alias("share_minutes_mv"),
        )
        .sort("band")
        .with_columns(
            (pl.col("minutes") / pl.col("minutes").sum()).alias("share_of_minutes"),
            (pl.col("counts") / pl.col("counts").sum()).alias("share_of_counts"),
        )
        .with_columns(pl.col("band").cast(pl.String))
    )
