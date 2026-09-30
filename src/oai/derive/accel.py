"""ActiGraph GT1M processing (activity-agreement plan §3, 'Accelerometer')."""

import polars as pl

REFERENCE = "docs/reference/oai-activity-agreement-analysis-plan.md §3"


def valid_wear_days(
    by_minute: pl.LazyFrame, *, nonwear_minutes: int = 90, min_wear_hours: float = 10.0
) -> pl.DataFrame:
    """Per-participant valid days: >= min_wear_hours of wear after removing >= nonwear_minutes zero-count runs."""
    raise NotImplementedError(f"valid_wear_days: see {REFERENCE}")
