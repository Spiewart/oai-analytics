"""Luyten 2018 early-OA criteria on inline knee frames (analyses/luyten_early_oa/luyten.py)."""

import sys
from pathlib import Path

import polars as pl
import pytest

from oai.assumptions import load_assumptions

ANALYSIS = Path(__file__).resolve().parents[1] / "analyses" / "luyten_early_oa"
sys.path.insert(0, str(ANALYSIS))
from luyten import criteria, group_metrics  # noqa: E402

GROUP_KEYS = {
    "g.knees",
    "g.persons",
    "g.kl01",
    "g.share",
    "g.kl01_koos",
    "g.early.age_mean",
    "g.control.age_mean",
    "g.early.bmi_mean",
    "g.control.bmi_mean",
    "g.early.women",
    "g.control.women",
    "g.sign.crepitus_jlt",
    "g.sign.crepitus_only",
    "g.sign.jlt_only",
}


def resolved(**overrides):
    return load_assumptions(ANALYSIS).resolve("luyten_early_oa", None, overrides)


def knee(**overrides):
    """A KL 0 knee meeting every criterion (pain and symptoms <= 85, medial tenderness)."""
    row = {
        "ID": 1,
        "SIDE": "R",
        "cohort": 2,
        "age": 60.0,
        "sex": 2,
        "bmi": 28.0,
        "kl0": 0.0,
        "pain": 80.0,
        "symptoms": 80.0,
        "adl": 95.0,
        "qol": 90.0,
        "exam0": 0,
        "s2_0": 0,
        "jlt_m": 1,
        "jlt_l": 0,
    }
    row.update(overrides)
    return row


SCHEMA = {
    "ID": pl.Int64,
    "SIDE": pl.String,
    "cohort": pl.Int64,
    "age": pl.Float64,
    "sex": pl.Int64,
    "bmi": pl.Float64,
    "kl0": pl.Float64,
    "pain": pl.Float64,
    "symptoms": pl.Float64,
    "adl": pl.Float64,
    "qol": pl.Float64,
    "exam0": pl.Int64,
    "s2_0": pl.Int64,
    "jlt_m": pl.Int64,
    "jlt_l": pl.Int64,
}


def frame(*rows):
    return pl.DataFrame(list(rows), schema=SCHEMA)


def one(rows, A=None, **overrides):
    return criteria(frame(*rows), A or resolved(**overrides)).row(0, named=True)


def test_luyten_needs_all_three():
    assert one([knee(kl0=1.0)])["luyten"] is True
    assert one([knee(kl0=2.0)])["luyten"] is False
    assert one([knee(symptoms=90.0)])["luyten"] is False
    assert one([knee(jlt_m=0)])["luyten"] is False


def test_cutoff_is_inclusive():
    assert one([knee(pain=85.0, symptoms=85.0)])["koos_ok"] is True
    assert one([knee(pain=85.1, symptoms=85.1)])["koos_ok"] is False


def test_koos_missing_rules():
    r = one([knee(pain=80.0, symptoms=None, adl=80.0, qol=90.0)])
    assert (r["koos_n"], r["koos_ok"]) == (2, True)
    r = one([knee(pain=80.0, symptoms=None, adl=90.0, qol=90.0)])
    assert (r["koos_n"], r["koos_ok"]) == (1, False)
    A = resolved(**{"luyten.koos_missing": "exclude"})
    knees = criteria(frame(knee(symptoms=None, adl=80.0), knee(ID=2)), A)
    assert knees.row(0, named=True)["koos_ok"] is None
    assert knees.row(0, named=True)["luyten"] is None
    assert dict(group_metrics(knees).iter_rows())["g.kl01"] == 1


def test_adl_omitted():
    rows = [knee(symptoms=90.0, adl=80.0)]
    assert one(rows)["koos_ok"] is True
    assert one(rows, **{"luyten.adl_source": "omit"})["koos_ok"] is False


def test_sign_missing_rules():
    rows = [knee(exam0=None, jlt_m=None, jlt_l=0)]
    assert one(rows)["luyten"] is False
    assert one(rows, **{"luyten.sign_missing": "exclude"})["luyten"] is None


def test_missing_crepitus_with_tenderness():
    r = one([knee(exam0=None, jlt_m=1)])
    assert r["luyten"] is True
    assert (r["sign_group"], r["f1_exposure"], r["f2_exposure"]) == (None, None, None)


def test_sign_groups():
    both = one([knee(exam0=1, jlt_m=1)])
    assert (both["sign_group"], both["f1_exposure"]) == ("crepitus_jlt", 1)
    crep = one([knee(exam0=1, jlt_m=0)])
    assert (crep["sign_group"], crep["f1_exposure"]) == ("crepitus_only", 1)
    jlt = one([knee(exam0=0, jlt_l=1, jlt_m=0)])
    assert (jlt["sign_group"], jlt["f1_exposure"]) == ("jlt_only", 0)
    # Framing 2 needs no sign: exam0 is the exposure in every KL 0-1 + KOOS knee
    nosign = one([knee(exam0=0, jlt_m=0)])
    assert (nosign["luyten"], nosign["kl01_koos"], nosign["f2_exposure"]) == (False, True, 0)
    assert nosign["f1_exposure"] is None
    assert one([knee(exam0=1, kl0=2.0)])["f2_exposure"] is None


def test_qol_is_shared_but_knees_differ():
    knees = criteria(
        frame(
            knee(SIDE="R", pain=70.0, symptoms=90.0, qol=70.0),
            knee(SIDE="L", pain=95.0, symptoms=90.0, qol=70.0),
        ),
        resolved(),
    )
    assert knees.sort("SIDE", descending=True)["koos_ok"].to_list() == [True, False]


def test_group_metrics_keys():
    knees = criteria(
        frame(knee(ID=1), knee(ID=2, exam0=1), knee(ID=3, kl0=2.0), knee(ID=4, jlt_m=0)),
        resolved(),
    )
    m = dict(group_metrics(knees).iter_rows())
    assert set(m) == GROUP_KEYS
    assert (m["g.knees"], m["g.kl01"], m["g.kl01_koos"]) == (2, 3, 3)
    assert m["g.share"] == pytest.approx(2 / 3)
    assert (m["g.sign.jlt_only"], m["g.sign.crepitus_jlt"]) == (1, 1)
