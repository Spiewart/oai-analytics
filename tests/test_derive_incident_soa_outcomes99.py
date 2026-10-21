"""Radiographic OA by visit from OUTCOMES99 (Projects 15, 37 and 43 combined), to 120 months."""

import dataclasses
from pathlib import Path

import polars as pl
import pytest

from oai.assumptions import load_assumptions
from oai.catalog import catalog_for
from oai.config import get_settings
from oai.derive import incident_soa

ANALYSIS = Path(__file__).resolve().parents[1] / "analyses" / "exam_crepitus_soa"
FIXTURE = Path(__file__).parent / "fixtures" / "oai_lo2018"
P = {k: 2000000 + k for k in range(1, 19)}


@pytest.fixture(autouse=True)
def lo2018_release(isolated_settings, monkeypatch):
    monkeypatch.setenv("OAI_DATA_DIR", str(FIXTURE))
    get_settings.cache_clear()
    catalog_for.cache_clear()


def resolved(**values):
    A = load_assumptions(ANALYSIS).resolve("exam_crepitus_soa", None, {})
    extra = {k.replace("__", "."): v for k, v in values.items()}
    return dataclasses.replace(A, values={**A.values, **extra})


LONG = {"periods__horizon": "12", "outcomes__roa_source": "outcomes99"}


def roa(frame, person, visit):
    return frame.filter((pl.col("ID") == P[person]) & (pl.col("visit") == visit))["roa"].item()


def test_outcomes99_roa_is_carried_forward():
    frame = incident_soa.roa_from_outcomes99(resolved(**LONG))
    for person in (3, 11):  # KL >= 2 at baseline (code 1), no readings after 48 months
        assert [roa(frame, person, v) for v in ("08", "10", "12")] == [True, True, True]


def test_incident_visit_sets_roa_from_then_on():
    frame = incident_soa.roa_from_outcomes99(resolved(**LONG))
    assert [roa(frame, 6, v) for v in ("06", "08", "10")] == [False, True, True]  # code 7


def test_readings_refused_past_48_months():
    with pytest.raises(ValueError, match="outcomes.roa_source"):
        incident_soa.soa_status(resolved(periods__horizon="10"))


def test_kl2_jsn_definition():
    kl2 = incident_soa.roa_from_outcomes99(resolved(**LONG))
    jsn = incident_soa.roa_from_outcomes99(resolved(**LONG, outcomes__roa_definition="kl2_jsn"))
    assert roa(kl2, 5, "03") is True and roa(jsn, 5, "03") is False  # XIOA 4, XIOAN 2


def test_followup_soa_at_96_months():
    soa = incident_soa.soa_status(resolved(**LONG))
    row = soa.filter((pl.col("ID") == P[11]) & (pl.col("visit") == "10")).row(0, named=True)
    assert row["roa"] is True and row["sx"] is True and row["soa"] is True
    early = soa.filter(
        (pl.col("ID") == P[11]) & (pl.col("visit") <= "06") & (pl.col("visit") != "00")
    )
    assert not early["soa"].fill_null(False).any()


def test_roa_unknown_after_the_last_reading_without_roa():
    """Code 2 says no incidence while read; after the last no-ROA visit (XNOA) ROA is unknown."""
    frame = incident_soa.roa_from_outcomes99(resolved(**LONG))
    assert [roa(frame, 8, v) for v in ("06", "08", "10")] == [False, None, None]  # XNOA 48 mo
    assert [roa(frame, 13, v) for v in ("06", "08", "10")] == [False, False, None]  # read at 72 mo
    assert [roa(frame, 6, v) for v in ("06", "08")] == [False, True]  # incident at 72, XNOA 48
    as_none = incident_soa.roa_from_outcomes99(resolved(**LONG, outcomes__roa_unread="no_roa"))
    assert roa(as_none, 8, "10") is False
