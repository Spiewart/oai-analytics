"""luyten_early_oa outcomes and knee frame: the by-horizon rule on inline frames, and the knee
frame on the synthetic release (tests/fixtures/oai_lo2018)."""

import sys
from pathlib import Path

import polars as pl
import pytest

from oai.assumptions import load_assumptions
from oai.catalog import catalog_for
from oai.config import get_settings

ANALYSIS = Path(__file__).resolve().parents[1] / "analyses" / "luyten_early_oa"
sys.path.insert(0, str(ANALYSIS))
import luyten  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "oai_lo2018"
P = {k: 2000000 + k for k in range(1, 19)}
VISITS = ("00", "01", "03", "05", "06", "08", "10")


@pytest.fixture(autouse=True)
def lo2018_release(isolated_settings, monkeypatch):
    monkeypatch.setenv("OAI_DATA_DIR", str(FIXTURE))
    get_settings.cache_clear()
    catalog_for.cache_clear()


def resolved(variant=None, **overrides):
    return load_assumptions(ANALYSIS).resolve("luyten_early_oa", variant, overrides)


def test_left_knee_uses_left_columns():
    knees = luyten.knee_frame(resolved()).filter(pl.col("ID") == P[3]).sort("SIDE")
    left, right = knees.row(0, named=True), knees.row(1, named=True)
    assert (left["SIDE"], left["koos_ok"], left["jlt_m"], left["luyten"]) == ("L", True, 1, True)
    assert (right["SIDE"], right["koos_ok"], right["jlt_m"]) == ("R", False, 0)
    assert right["exam0"] == 1 and left["exam0"] == 0


def test_frame_one_row_per_knee():
    knees = luyten.knee_frame(resolved())
    assert knees.select("ID", "SIDE").is_duplicated().sum() == 0
    assert {"roa48", "roa96", "soa48", "soa96"} <= set(knees.columns)
    assert luyten.knee_frame(resolved("right_knee"))["SIDE"].unique().to_list() == ["R"]


def test_replaced_at_baseline_excluded():
    """2000001's right knee is replaced at enrollment (V99ERKBLRP)."""
    A = resolved()
    knees = luyten.knee_frame(A)
    assert knees.filter((pl.col("ID") == P[1]) & (pl.col("SIDE") == "R")).height == 0
    flow = luyten.flow(A).to_dicts()
    step = {r["step"]: r for r in flow}
    assert [r["step"] for r in flow] == [
        "all",
        "replaced_at_baseline",
        "kl_read",
        "kl01",
        "kl01_koos",
        "luyten",
        "f1",
        "f2",
    ]
    assert step["all"]["knees"] - step["replaced_at_baseline"]["knees"] >= 2  # 2000001 R, 2000012 L


def test_cohort_metrics_case_counts():
    knees = luyten.knee_frame(resolved())
    m = dict(luyten.cohort_metrics(knees).iter_rows())
    for frame, levels in luyten.FRAMES.items():
        for level in levels:
            for outcome in luyten.OUTCOMES:
                assert (
                    m[f"o.{frame}.{outcome}.{level}.cases"] <= m[f"o.{frame}.{outcome}.{level}.n"]
                )
    assert "g.knees" in m
