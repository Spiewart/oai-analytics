"""Crepitus and device-measured activity at 48 and 72 months: person and knee frames.

Crepitus per person is the number of knees with it (0/1/2): exam crepitus present, or KOOS S2
at or above `crepitus.s2_cut`. Activity is walking_steps' person-wave measures (steps/day; MV and
light minutes/day from counts) at 48 (V06) and 72 months (V08), valid wear only. Changes are later
minus earlier.
"""

from __future__ import annotations

import polars as pl

from oai.assumptions import Resolved
from oai.derive.crepitus import crepitus_values

WAVES = {"06": "48", "08": "72"}
CREPITUS_VISITS = {"05": "36", "06": "48", "08": "72", "10": "96", "12": "120"}


def crepitus_counts(knees: pl.DataFrame, A: Resolved) -> pl.DataFrame:
    """ID, visit, s2_count, exam_count from one row per knee and visit."""
    both = A["crepitus.count_missing"] == "both_required"
    flags = knees.with_columns(
        (pl.col("koos_s2") >= A["crepitus.s2_cut"]).alias("_s2"),
        (pl.col("exam_crepitus") == 1).alias("_exam"),
    )

    def count(flag: str) -> pl.Expr:
        n = pl.col(flag).cast(pl.Int64).sum()
        known = pl.col(flag).is_not_null().sum()
        missing = known < 2 if both else known == 0
        return pl.when(missing).then(None).otherwise(n)

    return (
        flags.group_by("ID", "visit")
        .agg(count("_s2").alias("s2_count"), count("_exam").alias("exam_count"))
        .sort("ID", "visit")
    )


def person_frame(
    device: pl.DataFrame, counts: pl.DataFrame, covariates: pl.DataFrame, A: Resolved
) -> pl.DataFrame:
    """One row per person with valid wear at 48 months: activity at both waves and its change,
    crepitus counts by visit and their changes, and covariates."""
    measures = [*A["activity.measures"], "wear_hr"]
    valid = device.filter("valid")
    base = valid.filter(pl.col("wave") == "06").select(
        "ID", *[pl.col(m).alias(f"{m}_48") for m in measures]
    )
    later = valid.filter(pl.col("wave") == "08").select(
        "ID", pl.lit(True).alias("valid72"), *[pl.col(m).alias(f"{m}_72") for m in measures]
    )
    crep = counts.filter(pl.col("visit").is_in(list(CREPITUS_VISITS))).with_columns(
        pl.col("visit").replace_strict(CREPITUS_VISITS)
    )
    wide = crep.pivot(on="visit", index="ID", values=["s2_count", "exam_count"])
    rename = {
        c: c.replace("s2_count_", "s2_").replace("exam_count_", "exam_")
        for c in wide.columns
        if c != "ID"
    }
    wide = wide.rename(rename)
    for name in ("s2_36", "s2_48", "s2_72", "s2_96", "s2_120", "exam_36", "exam_48", "exam_120"):
        if name not in wide.columns:
            wide = wide.with_columns(pl.lit(None, pl.Int64).alias(name))
    out = (
        base.join(later, on="ID", how="left")
        .with_columns(pl.col("valid72").fill_null(False))
        .join(wide, on="ID", how="left")
        .join(covariates, on="ID", how="left")
        .with_columns(
            *[(pl.col(f"{m}_72") - pl.col(f"{m}_48")).alias(f"{m}_change") for m in measures],
            (pl.col("s2_72") - pl.col("s2_48")).alias("s2_change_48_72"),
            (pl.col("s2_48") - pl.col("s2_36")).alias("s2_change_36_48"),
            (pl.col("exam_48") - pl.col("exam_36")).alias("exam_change_36_48"),
        )
    )
    return out.drop("wear_hr_change").sort("ID")


def exam120_knees(knees: pl.DataFrame, persons: pl.DataFrame) -> pl.DataFrame:
    """Knees without exam crepitus at 48 months and examined at 120 months: event = new
    crepitus. Each carries its person's activity and covariates (persons valid at 48 months)."""
    at = lambda v, name: knees.filter(pl.col("visit") == v).select(  # noqa: E731
        "ID", "SIDE", pl.col("exam_crepitus").alias(name)
    )
    eligible = (
        at("06", "exam48")
        .join(at("12", "exam120"), on=["ID", "SIDE"], how="inner")
        .filter((pl.col("exam48") == 0) & pl.col("exam120").is_not_null())
        .select("ID", "SIDE", (pl.col("exam120") == 1).alias("event"))
    )
    return eligible.join(persons, on="ID", how="inner").sort("ID", "SIDE")


def flow_and_descriptives(
    persons: pl.DataFrame, knees120: pl.DataFrame, A: Resolved
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Aggregate flow and activity by crepitus count at 48 months (n, mean, SD)."""
    flow = [
        ("valid_48", persons.height),
        ("valid_both", persons.filter("valid72").height),
        ("exam_48", persons["exam_48"].drop_nulls().len()),
        ("s2_48", persons["s2_48"].drop_nulls().len()),
        ("s2_48_72", persons.filter(pl.col("s2_change_48_72").is_not_null()).height),
        ("s2_96", persons.filter(pl.col("s2_96").is_not_null() & pl.col("valid72")).height),
        ("exam120_knees", knees120.height),
        ("exam120_events", int(knees120["event"].sum())),
    ]
    rows = []
    for crep in ("exam_48", "s2_48"):
        for level, d in persons.filter(pl.col(crep).is_not_null()).group_by(crep):
            for m in A["activity.measures"]:
                for wave in ("48", "72"):
                    col = d[f"{m}_{wave}"].drop_nulls()
                    rows.append(
                        {
                            "crepitus": crep,
                            "knees": int(level[0]),
                            "activity": m,
                            "wave": wave,
                            "n": col.len(),
                            "mean": col.mean(),
                            "sd": col.std(),
                        }
                    )
    return (
        pl.DataFrame(flow, schema=["step", "n"], orient="row"),
        pl.DataFrame(rows).sort("crepitus", "activity", "wave", "knees"),
    )


# ---------------------------------------------------------------- release readers


def crepitus_knees() -> pl.DataFrame:
    """ID, SIDE, visit, koos_s2, exam_crepitus at 36, 48, 72, 96 and 120 months (null where the
    visit has no such item)."""
    frames = []
    for visit in CREPITUS_VISITS:
        try:
            frames.append(crepitus_values(visit, ["koos_s2", "exam_crepitus"]))
        except KeyError:  # 72 and 96 months: no exam
            frames.append(
                crepitus_values(visit, ["koos_s2"]).with_columns(
                    pl.lit(None, pl.Int64).alias("exam_crepitus")
                )
            )
    return pl.concat(frames).select("ID", "SIDE", "visit", "koos_s2", "exam_crepitus")
