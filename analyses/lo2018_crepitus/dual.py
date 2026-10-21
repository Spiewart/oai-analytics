"""Step `dual_counts`: KOOS S2 x exam crepitus 2 x 2 counts on the Lo 2018 cohort.

Adds combined-exposure columns (`combo_s2ge<cut>`: neither, s2_only, exam_only, both) to the
person-period and four-year frames for `dual.R`, and writes the cell counts with incident
SOA per cell, overall, by baseline subgroup and by enrollment cohort (Enrollees V00COHORT).
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

import polars as pl

from oai.derive.knee import find_col
from oai.loader import read_table

COMBOS = ("neither", "s2_only", "exam_only", "both")
COHORTS = {1: "Progression", 2: "Incidence", 3: "Non-exposed control"}


def combo(s2: pl.Expr, exam: pl.Expr, cut: int) -> pl.Expr:
    """neither / s2_only / exam_only / both, with S2 present at `s2 >= cut`; null if either is."""
    s2_pos, exam_pos = s2 >= cut, exam == 1
    return (
        pl.when(s2.is_null() | exam.is_null())
        .then(None)
        .when(s2_pos & exam_pos)
        .then(pl.lit("both"))
        .when(s2_pos)
        .then(pl.lit("s2_only"))
        .when(exam_pos)
        .then(pl.lit("exam_only"))
        .otherwise(pl.lit("neither"))
    )


def with_combos(df: pl.DataFrame, s2: str, exam: str, cuts: Sequence[int]) -> pl.DataFrame:
    return df.with_columns(
        [combo(pl.col(s2), pl.col(exam), cut).alias(f"combo_s2ge{cut}") for cut in cuts]
    )


def dual_counts(
    name: str, df: pl.DataFrame, s2: str, exam: str, cuts: Sequence[int]
) -> pl.DataFrame:
    """frame, cut, grouping (all | subgroup | cohort | period), group, combo, n, events.

    `period` grouping applies to the person-period frame only. Every combo appears in every
    group, with zeros."""
    coded = with_combos(df, s2, exam, cuts)
    parts = []
    for cut in cuts:
        col = f"combo_s2ge{cut}"
        rows = coded.filter(pl.col(col).is_not_null()).with_columns(pl.col(col).alias("combo"))
        groupings = [("all", None), ("subgroup", "subgroup"), ("cohort", "cohort")]
        if "period" in rows.columns:
            groupings.append(("period", "period"))
        for grouping, by in groupings:
            labelled = rows.with_columns(
                (pl.lit("all") if by is None else pl.col(by).cast(pl.String)).alias("group")
            )
            counts = labelled.group_by("group", "combo").agg(
                pl.len().alias("n"), pl.col("event").cast(pl.Int64).sum().alias("events")
            )
            grid = (
                labelled.select("group")
                .unique()
                .join(pl.DataFrame({"combo": list(COMBOS)}), how="cross")
            )
            parts.append(
                grid.join(counts, on=["group", "combo"], how="left")
                .with_columns(
                    pl.col("n", "events").fill_null(0).cast(pl.Int64),
                    pl.lit(name).alias("frame"),
                    pl.lit(cut).alias("cut"),
                    pl.lit(grouping).alias("grouping"),
                )
                .select("frame", "cut", "grouping", "group", "combo", "n", "events")
            )
    order = {c: i for i, c in enumerate(COMBOS)}
    return (
        pl.concat(parts)
        .with_columns(pl.col("combo").replace_strict(order, return_dtype=pl.Int64).alias("_o"))
        .sort("frame", "cut", "grouping", "group", "_o")
        .drop("_o")
    )


def enrollment_cohort() -> pl.DataFrame:
    df = read_table("enrollees", None)
    return df.select(
        pl.col(find_col(df, "ID")).cast(pl.Int64).alias("ID"),
        pl.col(find_col(df, "V00COHORT"))
        .replace_strict(COHORTS, default=None, return_dtype=pl.String)
        .alias("cohort"),
    )


def main() -> None:
    from oai.assumptions import current

    A = current()
    cuts = list(A["dual.s2_cuts"])
    frames, results = Path(os.environ["OAI_FRAME_DIR"]), Path(os.environ["OAI_RESULTS_DIR"])
    cohort = enrollment_cohort()
    periods = pl.read_parquet(frames / "frame.parquet").join(cohort, on="ID", how="left")
    persons = pl.read_parquet(frames / "persons.parquet").join(cohort, on="ID", how="left")
    with_combos(periods, "crep", "exam", cuts).write_parquet(frames / "dual_periods.parquet")
    with_combos(persons, "crep0", "exam0", cuts).write_parquet(frames / "dual_persons.parquet")
    counts = pl.concat(
        [
            dual_counts("periods", periods, "crep", "exam", cuts),
            dual_counts("persons", persons, "crep0", "exam0", cuts),
        ]
    )
    counts.write_csv(results / "dual_counts.csv")
    print(counts.filter(pl.col("grouping") == "all"))


if __name__ == "__main__":
    main()
