"""Step `discordance`: self-reported walkers who are, and are not, step-defined walkers.

Pure functions for the comparison; the step script wires them to the frames.
"""

from __future__ import annotations

import polars as pl

GROUPS = ("Yes, step walker", "Yes, not a step walker", "No")


def assign_groups(answers: pl.DataFrame, walkers: pl.DataFrame, definition: str) -> pl.DataFrame:
    """ID, group for people in both frames.

    `answers` has ID and yes (self-report); `walkers` has ID and a Boolean column `definition`.
    A self-reported walker is a step walker or not by that column; a non-walker is "No".
    """
    joined = answers.select("ID", "yes").join(walkers.select("ID", definition), on="ID")
    return joined.select(
        "ID",
        pl.when(~pl.col("yes"))
        .then(pl.lit(GROUPS[2]))
        .when(pl.col(definition))
        .then(pl.lit(GROUPS[0]))
        .otherwise(pl.lit(GROUPS[1]))
        .alias("group"),
    )
