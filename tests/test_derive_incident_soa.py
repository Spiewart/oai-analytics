"""oai.derive.incident_soa: which crepitus measures an observation needs (`require`)."""

import sys
from pathlib import Path

import polars as pl
import pytest
from soa_helpers import inline_cohort, inline_crepitus, inline_soa, person

from oai.assumptions import load_assumptions
from oai.derive.incident_soa import four_year, periods

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
