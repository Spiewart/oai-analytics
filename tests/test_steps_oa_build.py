"""steps_oa frames on inline data (analyses/steps_oa/persons.py)."""

import importlib.util
from pathlib import Path

import polars as pl

from oai.assumptions import load_assumptions

ANALYSIS = Path(__file__).resolve().parents[1] / "analyses" / "steps_oa"
# loaded under its own name: analyses/walking_steps also has a persons.py
_spec = importlib.util.spec_from_file_location("steps_oa_persons", ANALYSIS / "persons.py")
P = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(P)


def resolved(variant=None, **overrides):
    return load_assumptions(ANALYSIS).resolve("steps_oa", variant, overrides)


DEVICE_SCHEMA = {
    "ID": pl.Int64,
    "wave": pl.String,
    "valid": pl.Boolean,
    "steps": pl.Float64,
    "mv_min": pl.Float64,
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


STATUS_SCHEMA = {
    "ID": pl.Int64,
    "SIDE": pl.String,
    "visit": pl.String,
    "roa": pl.Boolean,
    "replaced": pl.Boolean,
    "kl": pl.Float64,
    "read": pl.Boolean,
    "kl_p15": pl.Float64,
}


def status(*rows):
    return pl.DataFrame(
        [dict(zip(STATUS_SCHEMA, r, strict=True)) for r in rows], schema=STATUS_SCHEMA
    )


def knee(id_, side, roa, replaced, kl, kl_p15):
    """Rows at V05, V06, V08 for one knee; each argument is a 3-tuple by visit (kl_p15 is
    read at V05 and V06 only)."""
    return [
        (id_, side, v, roa[i], replaced[i], kl[i], kl[i] is not None, kl_p15[i])
        for i, v in enumerate(("05", "06", "08"))
    ]


def test_wave_and_steps_inclusion():
    A = resolved()
    dev = device(
        (1, "06", True, 6000.0, 20.0, 14.0),  # valid at 48 months only
        (2, "06", True, None, 25.0, 13.0),  # counts valid, steps unusable at 48 months
        (2, "08", True, 7000.0, 30.0, 14.0),
        (3, "06", False, 9000.0, 40.0, 8.0),  # not valid at 48 months: out
        (3, "08", True, 9000.0, 40.0, 14.0),
        (4, "06", True, 8000.0, 30.0, 14.0),
        (4, "08", True, 7500.0, 33.0, 15.0),
    )
    p = P.person_frame(dev, covariates(1, 2, 3, 4), A)
    assert p["ID"].to_list() == [1, 2, 4]
    one, two, four = p.rows(named=True)
    assert one["valid72"] is False
    assert one["steps_72"] is None and one["steps_change"] is None
    assert one["steps_48"] == 6000.0 and one["steps_band"] == "5000_7499"
    assert two["valid72"] is True and two["steps_48"] is None and two["steps_band"] is None
    assert two["mv_min_48"] == 25.0 and two["mv_min_change"] == 5.0
    assert two["steps_change"] is None
    assert four["steps_change"] == -500.0 and four["mv_min_change"] == 3.0
    assert (four["wear_hr_48"], four["wear_hr_72"]) == (14.0, 15.0)
    assert set(P.PERSON_COLUMNS) == set(p.columns)
    assert four["kl_max"] == 1.0 and four["sex"] == 2


def test_steps_band_edges():
    A = resolved()
    assert P.band_labels(A["steps.bands"]) == ["lt5000", "5000_7499", "7500_9999", "ge10000"]
    steps = pl.DataFrame({"s": [4999.0, 5000.0, 7499.9, 7500.0, 9999.0, 10000.0, None]})
    bands = steps.select(P.steps_band(pl.col("s"), A["steps.bands"]).alias("b"))["b"].to_list()
    assert bands == [
        "lt5000", "5000_7499", "5000_7499", "7500_9999", "7500_9999", "ge10000", None,
    ]  # fmt: skip


def test_reverse_exposures_windows():
    A = resolved()
    F3, N3 = (False, False, False), (None, None, None)
    s = status(
        # person 1: right knee replaced between 48 and 72 months; left knee unchanged
        *knee(
            1, "R", (False, False, True), (False, False, True), (1.0, 1.0, None), (1.0, 1.0, None)
        ),
        *knee(1, "L", F3, F3, (0.0, 0.0, 0.0), (0.0, 0.0, None)),
        # person 2: a KL rise 0 -> 1 at 72 months without ROA; left knee not read at V08
        *knee(2, "R", F3, F3, (0.0, 0.0, 1.0), (0.0, 0.0, None)),
        *knee(2, "L", F3, F3, (0.0, 0.0, None), (0.0, 0.0, None)),
        # person 3: every knee unknown
        *knee(3, "R", N3, F3, N3, N3),
        *knee(3, "L", N3, F3, N3, N3),
        # person 4: new ROA at 48 months (right); a Project 15 KL rise 2 -> 3 (left)
        *knee(4, "R", (False, True, True), F3, (1.0, 2.0, 2.0), (1.0, 2.0, None)),
        *knee(4, "L", (True, True, True), F3, (2.0, 2.0, 2.0), (2.0, 3.0, None)),
    )
    # person 5: both knees read at V08 with no KL grade there; no new ROA
    for side in ("R", "L"):
        s = pl.concat(
            [s, status(*[(5, side, v, False, False, k, True, p) for v, k, p in (
                ("05", 0.0, 0.0), ("06", 0.0, 0.0), ("08", None, None))])]
        )  # fmt: skip
    out = {r["ID"]: r for r in P.reverse_exposures(s, A).rows(named=True)}
    assert out[5]["new_oa_48_72"] is False and out[5]["new_oa_read_48_72"] is False
    assert out[1]["new_oa_48_72"] is True and out[1]["new_oa_count_48_72"] == 1
    assert out[1]["new_oa_read_48_72"] is True
    assert out[1]["new_oa_36_48"] is False and out[1]["new_oa_count_36_48"] == 0
    assert out[2]["new_oa_48_72"] is False and out[2]["new_oa_count_48_72"] == 0
    assert out[2]["new_oa_read_48_72"] is True
    for c in P.REVERSE_COLUMNS[1:]:
        assert out[3][c] is None, c
    assert out[4]["new_oa_36_48"] is True and out[4]["new_oa_count_36_48"] == 2
    assert out[4]["new_oa_48_72"] is False


def test_exclude_baseline_pain_applies_to_incident_roa_only():
    s = pl.DataFrame(
        {
            "ID": [1, 1, 2, 2],
            "SIDE": ["R", "L", "R", "L"],
            "visit": ["06"] * 4,
            "roa": [False, False, False, True],
            "soa": [False, False, False, False],
            "replaced": [False] * 4,
            "sx": [True, False, None, True],
        }
    )
    keys = lambda d: sorted(d.select("ID", "SIDE").rows())  # noqa: E731
    assert keys(P.incidence_sample(s, "roa", "06", resolved())) == [(1, "L"), (1, "R"), (2, "R")]
    pain = resolved("exclude_baseline_pain")
    assert keys(P.incidence_sample(s, "roa", "06", pain)) == [(1, "L")]
    assert len(keys(P.incidence_sample(s, "soa", "06", pain))) == 4


def test_knee_events_and_agreement():
    periods = pl.DataFrame(
        {
            "ID": [1, 1, 2],
            "SIDE": ["R", "R", "R"],
            "steps_band": ["lt5000", "lt5000", "ge10000"],
            "event": [False, True, False],
        }
    )
    k = P.knee_events(periods, "event").sort("ID")
    assert k["event"].to_list() == [True, False]
    kl = pl.DataFrame({"ID": [1, 2, 3], "SIDE": ["R"] * 3, "kl_incident": [True, False, None]})
    roa = pl.DataFrame({"ID": [1, 2, 3], "SIDE": ["R"] * 3, "event": [True, True, False]})
    table = {r["level"]: r["n"] for r in P.agreement(kl, roa)}
    assert table == {"true/true": 1, "true/false": 0, "false/true": 1, "false/false": 0}


def _base(*rows):
    return pl.DataFrame(
        [dict(zip(("ID", "SIDE", "kl48"), r, strict=True)) for r in rows],
        schema={"ID": pl.Int64, "SIDE": pl.String, "kl48": pl.Float64},
    )


def test_replacement_frame_flags_follow_the_given_at_risk_set():
    # tkr_72: at_risk_roa marks only the knees at risk at V08; progression_tkr is KL >= 2 at V06;
    # people without valid 48-month wear (not in persons) leave
    times = pl.DataFrame(
        {
            "ID": [1, 1, 2, 3],
            "SIDE": ["R", "L", "R", "R"],
            "time_yr": [3.0, 4.0, 5.0, 2.0],
            "event": [True, False, False, True],
        }
    )
    base = _base((1, "R", 0.0), (1, "L", 1.0), (2, "R", 2.0), (3, "R", 3.0))
    persons = pl.DataFrame({"ID": [1, 2], "steps_48": [5000.0, 8000.0]})
    at_risk_v08 = pl.DataFrame({"ID": [1], "SIDE": ["R"]}, schema_overrides={"ID": pl.Int64})
    out = P.replacement_frame(times, base, persons, at_risk_v08).sort("ID", "SIDE")
    assert out.select("ID", "SIDE").rows() == [(1, "L"), (1, "R"), (2, "R")]
    assert out["at_risk_roa"].to_list() == [False, True, False]
    assert out["progression_tkr"].to_list() == [False, False, True]


def test_jsw_frame_keeps_the_progression_sample_only():
    change = pl.DataFrame(
        {
            "ID": [1, 1, 2],
            "SIDE": ["R", "L", "R"],
            "base_mm": [4.0, 3.5, 3.0],
            "change_mm": [-0.8, -0.1, None],
        }
    )
    sample = pl.DataFrame({"ID": [1, 2], "SIDE": ["R", "R"]}, schema_overrides={"ID": pl.Int64})
    base = _base((1, "R", 2.0), (1, "L", 0.0), (2, "R", 3.0))
    persons = pl.DataFrame({"ID": [1, 2], "steps_48": [5000.0, 8000.0]})
    out = P.jsw_frame(change, sample, base, persons).sort("ID", "SIDE")
    assert out.select("ID", "SIDE").rows() == [(1, "R"), (2, "R")]
    assert out["kl48"].to_list() == [2.0, 3.0]
