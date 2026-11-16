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


def band_labels(edges: list[int]) -> list[str]:
    """Cadence band labels: 0 steps, then one band per pair of lower edges, then the top band."""
    return (
        ["0"] + [f"{a}-{b - 1}" for a, b in zip(edges, edges[1:], strict=False)] + [f"{edges[-1]}+"]
    )


def cadence_bands(w: pl.DataFrame, edges: list[int], mv_cutpoint: float) -> pl.DataFrame:
    """Minutes, counts and MV share by cadence band; 0 steps is its own band below edges[0]."""
    labels = band_labels(edges)
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


def person_bands(w: pl.DataFrame, edges: list[int], mv_cutpoint: float) -> pl.DataFrame:
    """Across participants, per cadence band: mean (95% CI) and quartiles of each person's
    share of wear minutes, share of counts, and share of the band's minutes at MV.

    A person counts for the counts share only with counts > 0, and for the MV share only with
    minutes in the band; `persons` gives each n. Bands where a person has no minutes count as 0
    for the minutes and counts shares.
    """
    labels = band_labels(edges)
    banded = w.with_columns(
        pl.col("steps").cut([e - 0.5 for e in edges], labels=labels).cast(pl.String).alias("band")
    )
    per = banded.group_by("ID", "band").agg(
        pl.len().alias("minutes"),
        pl.col("cnt").sum().alias("counts"),
        (pl.col("cnt") >= mv_cutpoint).sum().alias("mv"),
    )
    totals = per.group_by("ID").agg(
        pl.col("minutes").sum().alias("all_minutes"), pl.col("counts").sum().alias("all_counts")
    )
    grid = totals.select("ID").join(pl.DataFrame({"band": labels}), how="cross")
    per = (
        grid.join(per, on=["ID", "band"], how="left")
        .join(totals, on="ID")
        .with_columns(pl.col("minutes", "counts", "mv").fill_null(0))
        .with_columns(
            (pl.col("minutes") / pl.col("all_minutes")).alias("share_of_minutes"),
            pl.when(pl.col("all_counts") > 0)
            .then(pl.col("counts") / pl.col("all_counts"))
            .alias("share_of_counts"),
            pl.when(pl.col("minutes") > 0)
            .then(pl.col("mv") / pl.col("minutes"))
            .alias("share_minutes_mv"),
        )
    )
    rows = []
    for band in labels:
        b = per.filter(pl.col("band") == band)
        for measure in ("share_of_minutes", "share_of_counts", "share_minutes_mv"):
            x = b[measure].drop_nulls()
            n = x.len()
            mean = x.mean() if n else None
            half = 1.959963984540054 * x.std() / n**0.5 if n > 1 else None
            rows.append(
                {
                    "band": band,
                    "measure": measure,
                    "persons": n,
                    "mean": mean,
                    "ci_lo": mean - half if half is not None else None,
                    "ci_hi": mean + half if half is not None else None,
                    "q1": x.quantile(0.25) if n else None,
                    "median": x.median() if n else None,
                    "q3": x.quantile(0.75) if n else None,
                }
            )
    return pl.DataFrame(rows)
