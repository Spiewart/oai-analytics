"""Helpers for steps that write aggregate results.

A run's metrics live in `metrics_*.csv` files with two columns, `metric` (String) and `value`
(Float64; R writes missing values as NA). `oai.replication` grades them against a paper and
`oaireport::load_results()` reads them into `run$metrics`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

import polars as pl

METRICS_SCHEMA = {"metric": pl.String, "value": pl.Float64}


def metrics_frame(
    metrics: Mapping[str, float | int | None] | Iterable[tuple[str, float | int | None]],
) -> pl.DataFrame:
    """A metrics table from {metric: value} or (metric, value) pairs, in the order given.

    Values become floats; None stays null (written as an empty cell).
    """
    pairs = metrics.items() if isinstance(metrics, Mapping) else metrics
    rows = [(str(k), None if v is None else float(v)) for k, v in pairs]
    return pl.DataFrame(rows, schema=METRICS_SCHEMA, orient="row")


def md_table(df: pl.DataFrame) -> str:
    """A GitHub-flavoured Markdown table of `df`; nulls are empty cells."""
    head = "| " + " | ".join(df.columns) + " |\n|" + "---|" * len(df.columns) + "\n"
    rows = "".join(
        "| " + " | ".join("" if v is None else str(v) for v in r) + " |\n" for r in df.iter_rows()
    )
    return head + rows
