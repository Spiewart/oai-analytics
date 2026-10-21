"""oai.derive.incident_soa: which crepitus measures an observation needs (`require`)."""

import dataclasses
import sys
from pathlib import Path

import polars as pl
import pytest
from soa_helpers import inline_cohort, inline_crepitus, inline_soa, person

from oai.assumptions import load_assumptions
from oai.derive.incident_soa import PERIODS, four_year, periods, schedule

LO2018 = Path(__file__).resolve().parents[1] / "analyses" / "lo2018_crepitus"
sys.path.insert(0, str(LO2018))


def resolved():
    return load_assumptions(LO2018).resolve("lo2018_crepitus", None, {})


NO_SOA = inline_soa(1, [False, False, False, False])


def test_require_exam_drops_periods_without_exam():
    crep = inline_crepitus(1, [0, 1, 1, 1], exam=(1, None, 0, 0))
    frame, counts = periods(resolved(), inline_cohort(person()), NO_SOA, crep)
    assert frame["period"].to_list() == [1, 2, 3, 4]
    frame, counts = periods(
        resolved(), inline_cohort(person()), NO_SOA, crep, require=("exam_crepitus",)
    )
    assert frame["period"].to_list() == [1, 3, 4]
    assert counts["missing_crepitus"] == 1


def test_require_both_needs_both():
    crep = inline_crepitus(1, [0, None, 1, 1], exam=(1, 1, None, 0))
    frame, counts = periods(
        resolved(), inline_cohort(person()), NO_SOA, crep, require=("koos_s2", "exam_crepitus")
    )
    assert frame["period"].to_list() == [1, 4]
    assert counts["missing_crepitus"] == 2


def test_four_year_require_exam():
    crep = inline_crepitus(1, [2, 2, 2, 2], exam=(None, 1, 1, 1))
    assert four_year(inline_cohort(person()), NO_SOA, crep)["ID"].to_list() == [1]
    out = four_year(inline_cohort(person()), NO_SOA, crep, require=("exam_crepitus",))
    assert out.height == 0


def test_unknown_requirement_raises():
    crep = inline_crepitus(1, [0, 0, 0, 0])
    with pytest.raises(KeyError):
        periods(resolved(), inline_cohort(person()), NO_SOA, crep, require=("womac",))
    assert isinstance(crep, pl.DataFrame)


def with_settings(A, **values):
    """A copy of resolved assumptions with extra settings (keys use __ for dots)."""
    extra = {k.replace("__", "."): v for k, v in values.items()}
    return dataclasses.replace(A, values={**A.values, **extra})


def test_default_schedule_is_lo2018s():
    assert schedule("06").equals(PERIODS)
    assert schedule("10")["end_visit"].to_list() == ["01", "03", "05", "06", "08", "10"]
    assert schedule("10")["start_visit"].to_list() == ["00", "01", "03", "05", "06", "08"]
    assert schedule("12").height == 7


def test_exam_carry_forward():
    exposure = ("00", "01", "03", "05", "06", "08")
    outcome = ("01", "03", "05", "06", "08", "10")
    soa = inline_soa(1, [False] * 6, visits=outcome)
    crep = inline_crepitus(1, [0] * 6, exam=(0, 0, 0, 0, 1, None), visits=exposure)
    A = with_settings(resolved(), periods__horizon="10")
    frame, _ = periods(A, inline_cohort(person()), soa, crep, require=("exam_crepitus",))
    assert frame["period"].to_list() == [1, 2, 3, 4, 5, 6]
    assert frame.filter(pl.col("period") >= 5)["exam"].to_list() == [1, 1]
    none = with_settings(A, exposure__exam_after_48m="none")
    frame, counts = periods(none, inline_cohort(person()), soa, crep, require=("exam_crepitus",))
    assert frame["period"].to_list() == [1, 2, 3, 4, 5]
    assert counts["missing_crepitus"] == 1


def test_empty_require_keeps_every_period():
    crep = inline_crepitus(1, [None, None, 1, 1], exam=(None, 1, None, 0))
    frame, counts = periods(resolved(), inline_cohort(person()), NO_SOA, crep, require=())
    assert frame["period"].to_list() == [1, 2, 3, 4] and counts["missing_crepitus"] == 0
