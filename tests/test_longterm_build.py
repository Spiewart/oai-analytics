"""crepitus_soa_longterm frames on the synthetic release (V08, V10, V12 and OUTCOMES99 codes)."""

import sys
from pathlib import Path

import polars as pl
import pytest

from oai.assumptions import load_assumptions
from oai.catalog import catalog_for
from oai.config import get_settings

ANALYSIS = Path(__file__).resolve().parents[1] / "analyses" / "crepitus_soa_longterm"
sys.path.insert(0, str(ANALYSIS))

import longterm  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "oai_lo2018"
P = {k: 2000000 + k for k in range(1, 19)}


@pytest.fixture(autouse=True)
def lo2018_release(isolated_settings, monkeypatch):
    monkeypatch.setenv("OAI_DATA_DIR", str(FIXTURE))
    get_settings.cache_clear()
    catalog_for.cache_clear()


def resolved(variant=None):
    return load_assumptions(ANALYSIS).resolve("crepitus_soa_longterm", variant, {})


@pytest.mark.parametrize("measure, column", [("koos_s2", "crep0"), ("exam_crepitus", "exam0")])
def test_frames_for_both_measures(measure, column):
    A = resolved()
    base = longterm.build(A)
    periods, hazard, horizon, counts = longterm.frames_for(A, measure, base)
    assert periods.height > 0 and hazard.height > 0 and horizon.height > 0
    assert periods["period"].max() == 6  # V08 -> V10 is the last period at 96 months
    assert hazard.group_by("ID").agg(pl.col(column).n_unique())[column].max() == 1
    assert set(counts) == {"potential", "missing_outcome", "missing_crepitus"}


def test_by_horizon_frame_needs_outcome_at_horizon():
    A = resolved()
    periods, _, horizon, _ = longterm.frames_for(A, "koos_s2", longterm.build(A))
    assert P[8] in periods["ID"].to_list()  # seen to 48 months
    assert P[8] not in horizon["ID"].to_list()  # nothing after 48 months, no earlier SOA
    assert P[11] in horizon.filter(pl.col("event"))["ID"].to_list()  # SOA at 96 months


def test_coverage_report():
    values = dict(longterm.coverage(resolved(), longterm.build(resolved())).iter_rows())
    # 14 in the cohort: 2000014 has a blank 48-month pain answer, 2000008 nothing after 48 months
    assert (values["cov.outcome_at.06"], values["cov.outcome_at.10"]) == (13, 13)
    assert values["cov.p37.noroa_nosx"] + values["cov.p37.noroa_sx"] >= 2  # 2000006, 2000013 (42)
    assert {"cov.roa48.disagree", "cov.p37.roa_nosx", "cov.p43.roa_nosx"} <= set(values)
