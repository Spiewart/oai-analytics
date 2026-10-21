"""Mahmoudian 2023 anchor: eligibility, structural outcomes and the knee pick."""

import sys
import tomllib
from pathlib import Path

import polars as pl
import pytest

from oai.assumptions import load_assumptions
from oai.catalog import catalog_for
from oai.config import get_settings

ANALYSIS = Path(__file__).resolve().parents[1] / "analyses" / "exam_crepitus_soa"
sys.path.insert(0, str(ANALYSIS))

import mahmoudian  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "oai_lo2018"
P = {k: 2000000 + k for k in range(1, 19)}
FEATURES = list(mahmoudian.TF_FEATURES)


@pytest.fixture(autouse=True)
def lo2018_release(isolated_settings, monkeypatch):
    monkeypatch.setenv("OAI_DATA_DIR", str(FIXTURE))
    get_settings.cache_clear()
    catalog_for.cache_clear()


def resolved(variant=None, **overrides):
    return load_assumptions(ANALYSIS).resolve("exam_crepitus_soa", variant, overrides)


def knees(rows):
    """rows: per knee (ID, feature values in TF_FEATURES order)."""
    return pl.DataFrame(
        [(i, "R", *map(float, vals)) for i, vals in rows],
        schema=["ID", "SIDE", *FEATURES],
        orient="row",
    )


def developed(base, fu, jsn="incident", osteophytes="sites"):
    out = mahmoudian.structural_development(knees(base), knees(fu), jsn, osteophytes, "exclude")
    return out.sort("ID")["structural"].to_list()


def test_structural_development_rules():
    zero = [0, 0, 0, 0, 0, 0]
    base = [(1, zero), (2, zero), (3, zero), (4, [0, 0, 1, 0, 0, 0])]
    fu = [
        (1, [1, 0, 0, 0, 0, 0]),
        (2, [0.5, 0, 0, 0, 0, 0]),
        (3, [0, 0, 1, 0, 0, 0]),
        (4, [0, 0, 2, 0, 0, 0]),
    ]
    assert developed(base, fu) == [True, False, True, False]
    assert developed(base, fu, jsn="any_increase") == [True, True, True, False]
    assert developed(base, fu, osteophytes="grade_sum") == [True, False, True, True]


def test_missing_feature_leaves_structural_null():
    base = knees([(1, [0, 0, 0, 0, 0, 0])])
    fu = knees([(1, [0, 0, 0, 0, 0, 0])]).with_columns(pl.lit(None, pl.Float64).alias("OSTL"))
    out = mahmoudian.structural_development(base, fu, "incident", "sites", "exclude")
    assert out["structural"].to_list() == [None]


def test_pick_knee_is_seeded_and_one_per_person():
    both = pl.DataFrame({"ID": [1, 1, 2, 2, 3], "SIDE": ["R", "L", "R", "L", "R"]})
    first = mahmoudian.pick_knee(both, "random", 2023)
    assert sorted(first["ID"].to_list()) == [1, 2, 3]
    assert first.equals(mahmoudian.pick_knee(both, "random", 2023))
    assert set(mahmoudian.pick_knee(both, "right", 2023)["SIDE"]) == {"R"}
    left = mahmoudian.pick_knee(both, "left", 2023)
    assert dict(zip(left["ID"], left["SIDE"], strict=True)) == {1: "L", 2: "L", 3: "R"}


def test_anchor_eligibility():
    ids = mahmoudian.anchor_frame(resolved())["ID"].to_list()
    assert P[17] not in ids and P[18] not in ids
    assert ids.count(P[13]) == 1
    assert {P[14], P[15], P[16]} <= set(ids)


def test_symptomatic_outcome_needs_followup_pain():
    def row(A):
        return mahmoudian.anchor_frame(A).filter(pl.col("ID") == P[14]).row(0, named=True)

    default = row(resolved())
    assert default["structural"] is True and default["structural_sx"] is None
    assert row(resolved(**{"mahmoudian.missing_followup_pain": "not_sx"}))["structural_sx"] is False
    assert (
        mahmoudian.anchor_frame(resolved()).filter(pl.col("ID") == P[16])["structural_sx"].item()
        is True
    )


def test_anchor_metrics_keys():
    published = tomllib.loads((ANALYSIS / "published.toml").read_text())["default"]
    wanted = {
        k
        for k in published
        if k.startswith("m.") and not isinstance(published[k], dict) or k == "m.women"
    }
    values = dict(mahmoudian.anchor_metrics(mahmoudian.anchor_frame(resolved())).iter_rows())
    assert set(values) == wanted
    assert values["m.structural.events"] >= 2


def test_blank_osteophytes_in_kl01_readings_count_as_none():
    """Project 15 leaves osteophyte grades blank for many KL 0-1 readings (never for KL >= 2)."""
    blank = [None] * 4
    base = pl.DataFrame(
        [(1, "R", 0.0, 0.0, 0.0, *blank), (2, "R", 1.0, 0.0, 0.0, *blank)],
        schema=["ID", "SIDE", "kl", *FEATURES],
        orient="row",
    )
    fu = pl.DataFrame(
        [(1, "R", 2.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0), (2, "R", 1.0, 0.0, 0.0, *blank)],
        schema=["ID", "SIDE", "kl", *FEATURES],
        orient="row",
    )
    absent = mahmoudian.structural_development(base, fu, "incident", "sites", "absent")
    assert absent.sort("ID")["structural"].to_list() == [True, False]
    excluded = mahmoudian.structural_development(base, fu, "incident", "sites", "exclude")
    assert excluded["structural"].to_list() == [None, None]


def test_structural_development_needs_an_explicit_blank_rule():
    base = knees([(1, [0, 0, 0, 0, 0, 0])])
    with pytest.raises(TypeError):
        mahmoudian.structural_development(base, base, "incident", "sites")


def test_knee_pick_does_not_depend_on_who_else_is_eligible():
    both = pl.DataFrame({"ID": [i for i in range(1, 41) for _ in (0, 1)], "SIDE": ["R", "L"] * 40})
    full = mahmoudian.pick_knee(both, "random", 2023)
    fewer = mahmoudian.pick_knee(both.filter(pl.col("ID") != 1), "random", 2023)
    kept = full.filter(pl.col("ID") != 1).sort("ID")
    assert kept.equals(fewer.sort("ID"))
    assert set(full["SIDE"]) == {"R", "L"}


def test_crepitus_in_either_knee():
    def exam(A, person):
        return mahmoudian.anchor_frame(A).filter(pl.col("ID") == P[person])["exam0"].item()

    # 13: both knees eligible, exam right 1 / left 0; 15: exam 0 in both knees
    assert exam(resolved(**{"mahmoudian.knee_pick": "left"}), 13) == 0
    either = resolved(**{"mahmoudian.knee_pick": "left", "mahmoudian.crepitus_knee": "either"})
    assert exam(either, 13) == 1 and exam(either, 15) == 0


def test_person_level_kl_needs_both_knees_kl01():
    ids = mahmoudian.anchor_frame(resolved(**{"mahmoudian.kl_level": "person"}))["ID"].to_list()
    assert P[14] not in ids  # left knee KL 2
    assert {P[13], P[15], P[16]} <= set(ids)
