"""walking_counts: walking-minute shares of the count measures, on synthetic minutes."""

import sys
from pathlib import Path

import polars as pl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analyses" / "walking_counts"))

import share as s  # noqa: E402

from oai.derive.accel import DeviceRules  # noqa: E402

RULES = DeviceRules(min_valid_days=1)


def minutes(days):
    """days: {(ID, day): [(cnt, steps), ...]} -> a read_minutes(..., steps=True) frame."""
    rows = [
        (pid, day, i + 1, c, st)
        for (pid, day), mins in days.items()
        for i, (c, st) in enumerate(mins)
    ]
    schema = {
        "ID": pl.Int64,
        "day": pl.Int64,
        "minute": pl.Int64,
        "cnt": pl.Float64,
        "steps": pl.Float64,
    }
    return pl.DataFrame(rows, schema=schema, orient="row")


def wear_day(walk=0, mv_walk=0, mv_still=0, light=0):
    """A valid (600 wear minutes) day built from minute kinds; the rest are low, stepless."""
    mins = [(3000.0, 110.0)] * mv_walk + [(3000.0, 0.0)] * mv_still
    mins += [(800.0, 50.0)] * walk + [(500.0, 5.0)] * light
    return mins + [(50.0, 0.0)] * (600 - len(mins))


def frame(**cols):
    """Analysis minutes; columns not given default to one person, day 1, no flags."""
    n = len(next(iter(cols.values())))
    base = {"ID": [1] * n, "day": [1] * n, "cnt": [0.0] * n, "steps": [0.0] * n}
    base.update(mv=[False] * n, light=[False] * n, bout=[False] * n)
    return pl.DataFrame({**base, **cols})


def test_analysis_minutes_keeps_complete_step_days_of_counted_people():
    m = minutes(
        {
            (1, 1): wear_day(walk=10),
            (1, 2): [(c, None) for c, _ in wear_day()],  # no steps captured: day dropped
            (2, 1): [(c, None) for c, _ in wear_day()],  # person 2 has no complete day
        }
    )
    w, flow = s.analysis_minutes(m, RULES, min_step_days=1)
    assert w["ID"].unique().to_list() == [1] and w["day"].unique().to_list() == [1]
    assert flow["valid_days"] == 3 and flow["valid_days_steps_incomplete"] == 2
    assert (flow["persons_valid"], flow["persons_analysed"]) == (2, 1)
    assert flow["analysis_wear_minutes"] == 600


def test_analysis_minutes_needs_min_step_days():
    m = minutes({(1, 1): wear_day(), (1, 2): [(c, None) for c, _ in wear_day()]})
    _, flow = s.analysis_minutes(m, RULES, min_step_days=2)
    assert flow["persons_analysed"] == 0


def test_analysis_minutes_flags_intensity_and_bouts():
    w, _ = s.analysis_minutes(minutes({(1, 1): wear_day(mv_walk=12, light=5)}), RULES, 1)
    assert w["mv"].sum() == 12 and w["bout"].sum() == 12 and w["light"].sum() == 5


def test_shares_pool_minutes_and_report_person_quartiles():
    w = pl.DataFrame(
        {
            "ID": [1, 1, 1, 1, 2, 2],
            "cnt": [3000.0, 3000.0, 500.0, 0.0, 3000.0, 100.0],
            "steps": [100.0, 0.0, 50.0, 0.0, 100.0, 0.0],
            "mv": [True, True, False, False, True, False],
            "light": [False, False, True, False, False, True],
            "bout": [False] * 6,
        }
    )
    out = s.shares(w, [40]).filter(pl.col("measure") == "mv_minutes_walking").row(0, named=True)
    assert out["pooled"] == pytest.approx(2 / 3)  # 2 of 3 MV minutes have >= 40 steps
    assert out["person_median"] == pytest.approx(0.75)  # persons: 1/2 and 1/1
    counts = s.shares(w, [40]).filter(pl.col("measure") == "wear_counts_in_walking").row(0)
    assert counts[2] == pytest.approx(6500 / 9600)


def test_people_without_a_denominator_have_no_share():
    w = frame(
        ID=[1, 2], cnt=[3000.0, 50.0], steps=[100.0, 0.0], mv=[True, False], bout=[True, False]
    )
    out = s.shares(w, [1]).filter(pl.col("measure") == "mv_bout_minutes_walking").row(0, named=True)
    assert out["persons"] == 1 and out["person_median"] == 1.0


def test_cadence_bands_cover_every_minute_once():
    w = frame(
        cnt=[0.0, 100.0, 900.0, 2500.0, 4000.0],
        steps=[0.0, 1.0, 19.0, 100.0, 130.0],
    )
    out = s.cadence_bands(w, [1, 20, 100, 120], mv_cutpoint=2020)
    # a band with no minutes (20-99 here) has no row
    assert out["band"].to_list() == ["0", "1-19", "100-119", "120+"]
    assert out["minutes"].to_list() == [1, 2, 1, 1]
    assert out["share_of_minutes"].sum() == pytest.approx(1.0)
    row = out.filter(pl.col("band") == "1-19").row(0, named=True)
    assert row["minutes"] == 2 and row["share_minutes_mv"] == 0.0


def test_wear_minute_share_divides_by_the_number_of_minutes():
    w = frame(ID=[1, 1, 1, 2], steps=[50.0, 0.0, 0.0, 50.0])
    out = s.shares(w, [40]).filter(pl.col("measure") == "wear_minutes_walking").row(0, named=True)
    assert out["pooled"] == pytest.approx(0.5)
    assert (out["person_q1"], out["person_q3"]) == (pytest.approx(1 / 3), 1.0)
