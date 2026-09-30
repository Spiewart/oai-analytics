"""Progression endpoints (docs/reference/oai-progression-definition-crosswalk.md)."""

import polars as pl

REFERENCE = "docs/reference/oai-progression-definition-crosswalk.md §1"


def kl_progression(
    kl_long: pl.DataFrame,
    *,
    baseline: str = "V00",
    followup: str = "V06",
    exclude_0_to_1: bool = True,
) -> pl.DataFrame:
    """Knee-level KL progression (>= 1 grade, optionally excluding 0 -> 1) between two visits."""
    raise NotImplementedError(f"kl_progression: see {REFERENCE}")


def fnih_jsw_progressor(jsw_long: pl.DataFrame, *, threshold_mm: float = 0.7) -> pl.DataFrame:
    """FNIH structural progressor: medial minimum JSW loss >= threshold_mm at 24/36/48 months."""
    raise NotImplementedError(f"fnih_jsw_progressor: see {REFERENCE}")
