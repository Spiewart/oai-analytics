"""PASE scoring (activity-agreement plan §3, 'PASE (index self-report)')."""

import polars as pl

REFERENCE = "docs/reference/oai-activity-agreement-analysis-plan.md §3"


def score_pase(allclinical: pl.DataFrame, visit: str) -> pl.DataFrame:
    """Return ID, visit, pase_total, pase_walking from one visit's AllClinical PASE items."""
    raise NotImplementedError(f"score_pase: see {REFERENCE}")
