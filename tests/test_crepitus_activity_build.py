"""crepitus_activity frames on inline data (analyses/crepitus_activity/activity.py)."""

import sys
from pathlib import Path

import polars as pl

from oai.assumptions import load_assumptions

ANALYSIS = Path(__file__).resolve().parents[1] / "analyses" / "crepitus_activity"
sys.path.insert(0, str(ANALYSIS))
import activity as act  # noqa: E402


def resolved(variant=None, **overrides):
    return load_assumptions(ANALYSIS).resolve("crepitus_activity", variant, overrides)


KNEE_SCHEMA = {
    "ID": pl.Int64,
    "SIDE": pl.String,
    "visit": pl.String,
    "koos_s2": pl.Int64,
    "exam_crepitus": pl.Int64,
}


def knees(*rows):
    return pl.DataFrame([dict(zip(KNEE_SCHEMA, r, strict=True)) for r in rows], schema=KNEE_SCHEMA)


DEVICE_SCHEMA = {
    "ID": pl.Int64,
    "wave": pl.String,
    "valid": pl.Boolean,
    "steps": pl.Float64,
    "mv_min": pl.Float64,
    "light_min": pl.Float64,
    "wear_hr": pl.Float64,
}


def device(*rows):
    return pl.DataFrame(
        [dict(zip(DEVICE_SCHEMA, r, strict=True)) for r in rows], schema=DEVICE_SCHEMA
    )


def covariates(*ids):
    return pl.DataFrame(
        {
            "ID": list(ids),
            "age": [65.0] * len(ids),
            "sex": [2] * len(ids),
            "bmi": [28.0] * len(ids),
            "kl_max": [1.0] * len(ids),
            "womac_pain_max": [2.0] * len(ids),
        },
        schema_overrides={"ID": pl.Int64, "sex": pl.Int64},
    )


def counts_for(*rows, A=None):
    return act.crepitus_counts(knees(*rows), A or resolved())


def test_count_missing_rules():
    k = [(1, "R", "08", 2, None), (1, "L", "08", None, None)]
    assert counts_for(*k)["s2_count"].to_list() == [None]
    assert counts_for(*k, A=resolved("available_knees"))["s2_count"].to_list() == [1]
    assert counts_for((1, "R", "08", 0, None), (1, "L", "08", 3, None))["s2_count"].item() == 1
    assert counts_for((1, "R", "08", 1, None), (1, "L", "08", 4, None))["s2_count"].item() == 2
    both_rarely = [(1, "R", "08", 1, None), (1, "L", "08", 1, None)]
    assert counts_for(*both_rarely, A=resolved("s2_cut_2"))["s2_count"].item() == 0
    exam = counts_for((1, "R", "06", 0, 1), (1, "L", "06", 0, 0))
    assert exam["exam_count"].item() == 1


def frame(dev, crep_rows, ids):
    A = resolved()
    return act.person_frame(dev, act.crepitus_counts(knees(*crep_rows), A), covariates(*ids), A)


def test_wave_validity_drives_inclusion():
    dev = device(
        (1, "06", True, 5000.0, 20.0, 200.0, 14.0),
        (2, "06", False, 6000.0, 30.0, 210.0, 9.0),
        (2, "08", True, 6000.0, 30.0, 210.0, 14.0),
    )
    p = frame(dev, [], [1, 2])
    assert p["ID"].to_list() == [1]
    row = p.row(0, named=True)
    assert row["valid72"] is False
    assert row["steps_72"] is None and row["steps_change"] is None


def test_steps_missing_keeps_count_measures():
    dev = device(
        (1, "06", True, 5000.0, 20.0, 200.0, 14.0),
        (1, "08", True, None, 18.0, 190.0, 14.0),
    )
    row = frame(dev, [], [1]).row(0, named=True)
    assert row["mv_min_72"] == 18.0 and row["mv_min_change"] == -2.0
    assert row["steps_72"] is None and row["steps_change"] is None


def test_change_is_later_minus_earlier():
    dev = device(
        (1, "06", True, 5000.0, 20.0, 200.0, 14.0),
        (1, "08", True, 4000.0, 25.0, 200.0, 13.0),
    )
    crep = [
        (1, "R", "06", 0, 0),
        (1, "L", "06", 0, 1),
        (1, "R", "08", 2, None),
        (1, "L", "08", 3, None),
    ]
    row = frame(dev, crep, [1]).row(0, named=True)
    assert row["steps_change"] == -1000.0
    assert (row["s2_48"], row["s2_72"], row["s2_change_48_72"]) == (0, 2, 2)
    assert (row["exam_48"], row["wear_hr_48"], row["wear_hr_72"]) == (1, 14.0, 13.0)


def test_exam120_knee_frame():
    dev = device(
        (1, "06", True, 5000.0, 20.0, 200.0, 14.0), (2, "06", True, 7000.0, 25.0, 220.0, 15.0)
    )
    persons = frame(dev, [], [1, 2])
    k = knees(
        (1, "R", "06", 0, 1),
        (1, "R", "12", 0, 1),  # crepitus at 48: excluded
        (1, "L", "06", 0, 0),
        (1, "L", "12", 0, None),  # no 120-month exam: excluded
        (2, "R", "06", 0, 0),
        (2, "R", "12", 0, 1),  # new crepitus
        (2, "L", "06", 0, 0),
        (2, "L", "12", 0, 0),  # none
    )
    out = act.exam120_knees(k, persons).sort("ID", "SIDE")
    assert out.select("ID", "SIDE", "event").rows() == [(2, "L", False), (2, "R", True)]
    assert out["steps_48"].to_list() == [7000.0, 7000.0]
