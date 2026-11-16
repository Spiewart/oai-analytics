"""walking_steps: walking-minute shares of the count measures, on synthetic minutes."""

import sys
from pathlib import Path

import numpy as np
import polars as pl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analyses" / "walking_steps"))

import devices  # noqa: E402
import discordance as d  # noqa: E402
import relation as r  # noqa: E402
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


# --- devices.py: step walking bouts and walker definitions
import devices as dv  # noqa: E402
import pro  # noqa: E402


def test_step_bouts_mirror_the_count_bout_rule():
    # 12 minutes at 70 steps/min on a valid day: one 12-minute walking bout at >= 60, none at 100
    m = minutes({(1, 1): [(800.0, 70.0)] * 12 + [(50.0, 0.0)] * 588})
    rules = DeviceRules(min_valid_days=1)
    day = dv.step_bouts_daily(m, rules, [60, 100]).row(0, named=True)
    assert (day["step_bout60_min"], day["step_bouts60"]) == (12, 1)
    assert (day["step_bout100_min"], day["step_bouts100"]) == (0, 0)


def test_short_step_runs_are_not_bouts():
    m = minutes({(1, 1): [(800.0, 70.0)] * 9 + [(50.0, 0.0)] * 591})
    day = dv.step_bouts_daily(m, DeviceRules(min_valid_days=1), [60]).row(0, named=True)
    assert day["step_bouts60"] == 0


def test_person_wave_has_count_and_step_measures_and_nulls_thin_step_data():
    walk = [(800.0, 70.0)] * 12 + [(50.0, 0.0)] * 588
    m = minutes({(1, 1): walk, (1, 2): walk, (2, 1): [(c, None) for c, _ in walk]})
    p = dv.person_wave(m, DeviceRules(min_valid_days=1), [60], min_step_days=1).sort("ID")
    one, two = p.row(0, named=True), p.row(1, named=True)
    assert one["step_bout60_days_per_week"] == 7.0 and one["step_bout60_min"] == 12.0
    assert one["bout_days_per_week"] == 0.0  # 800 counts/min is light, not MV
    assert two["valid"] and two["step_bout60_days_per_week"] is None and two["steps"] is None


def test_combine_skips_a_wave_without_step_measures():
    device = pl.DataFrame(
        {"ID": [1, 1], "wave": ["06", "08"], "valid": [True, True], "steps": [4000.0, None]}
    )
    row = dv.combine(device, ["steps"]).row(0, named=True)
    assert row["n_waves"] == 2 and row["steps"] == 4000.0


def test_walker_definitions_cover_every_family_and_rule():
    names = [d[0] for d in dv.walker_definitions(2.0, 150.0, [40, 100])]
    assert len(names) == 9 and "counts_mv:bout_days" in names and "steps_40:bout_minutes" in names


# --- pro.py: accuracy statistics
def test_accuracy_two_by_two():
    p = pl.Series([True, True, True, False, False, None])
    r = pl.Series([True, False, False, True, False, True])
    a = pro.accuracy(p, r)
    assert (a["tp"], a["fp"], a["fn"], a["tn"], a["n"]) == (1, 2, 1, 1, 5)
    assert a["sensitivity"] == 0.5 and a["specificity"] == pytest.approx(1 / 3)
    assert a["youden_j"] == pytest.approx(0.5 + 1 / 3 - 1)
    assert a["agreement"] == 0.4


def test_wilson_interval_known_value():
    lo, hi = pro.wilson(8, 10)
    assert lo == pytest.approx(0.4902, abs=1e-4) and hi == pytest.approx(0.9433, abs=1e-4)


def test_auc_counts_ties_as_half():
    x = np.array([3.0, 2.0, 2.0, 1.0])
    yes = np.array([True, True, False, False])
    assert pro.auc(x, yes) == pytest.approx((1 + 1 + 0.5 + 1) / 4)


def test_auc_ci_brackets_the_estimate():
    rng = np.random.default_rng(1)
    x = pl.Series(np.r_[rng.normal(1, 1, 200), rng.normal(0, 1, 200)])
    yes = pl.Series([True] * 200 + [False] * 200)
    out = pro.auc_with_ci(x, yes, reps=200, seed=3)
    assert out["auc_lo"] < out["auc"] < out["auc_hi"] and out["auc"] > 0.7


def test_person_bands_average_each_persons_shares():
    w = frame(
        ID=[1, 1, 2, 2],
        cnt=[0.0, 3000.0, 100.0, 100.0],
        steps=[0.0, 110.0, 5.0, 5.0],
    )
    out = s.person_bands(w, [1, 100], mv_cutpoint=2020)
    row = out.filter((pl.col("band") == "100+") & (pl.col("measure") == "share_of_minutes"))
    r = row.row(0, named=True)
    assert r["persons"] == 2 and r["mean"] == pytest.approx(0.25)  # 0.5 and 0 (no minutes)
    mv = out.filter((pl.col("band") == "100+") & (pl.col("measure") == "share_minutes_mv"))
    assert mv.row(0, named=True)["persons"] == 1  # only person 1 has minutes in the band
    counts = out.filter((pl.col("band") == "1-99") & (pl.col("measure") == "share_of_counts"))
    assert counts.row(0, named=True)["mean"] == pytest.approx(0.5)  # 0 and 1


def test_either_week_credits_a_walker_from_any_wave():
    per_wave = pl.DataFrame({"ID": [1, 1, 2, 2, 3], "w": [True, False, False, False, False]})
    out = dv.either_week(per_wave, ["w"])
    assert out["w"].to_list() == [True, False, False]


# --- relation (Q1): steps against activity counts within a minute

EDGES = [0, 100, 500, 1000, 1500, 2020, 5999]
BANDS = [1, 20, 40, 60, 80, 100, 120]


def test_count_bin_labels_and_intensity():
    assert r.count_bin_labels(EDGES) == [
        "0-99",
        "100-499",
        "500-999",
        "1000-1499",
        "1500-2019",
        "2020-5998",
        "5999+",
    ]
    m = r.intensity_of(EDGES, 100, 2020, 5999)
    assert m["0-99"] == "sedentary" and m["1500-2019"] == "light"
    assert m["2020-5998"] == "moderate" and m["5999+"] == "vigorous"


@pytest.mark.parametrize("edges", [[0, 100, 500, 2000, 5999], [10, 100, 2020], [0, 500, 100, 2020]])
def test_count_bins_reject_edges_off_the_device_cutpoints(edges):
    with pytest.raises(ValueError):
        r.check_count_edges(edges, 100, 2020, 5999)


def test_bin_quantiles_by_count_bin():
    w = frame(
        cnt=[0.0, 50.0, 2019.0, 2020.0, 2020.0, 6000.0],
        steps=[0.0, 0.0, 30.0, 90.0, 110.0, 150.0],
    )
    q = r.bin_quantiles(w, EDGES)
    assert q["count_bin"].to_list() == r.count_bin_labels(EDGES)
    row = q.filter(pl.col("count_bin") == "2020-5998")
    assert row["steps_median"].item() == 100.0
    assert row["share_of_minutes"].item() == pytest.approx(2 / 6)
    assert q.filter(pl.col("count_bin") == "1500-2019")["steps_median"].item() == 30.0


def test_band_shares_sum_to_one_within_bin():
    w = frame(cnt=[2500.0] * 4, steps=[0.0, 19.0, 20.0, 125.0])
    b = r.band_shares(w, EDGES, BANDS).filter(pl.col("count_bin") == "2020-5998")
    got = dict(zip(b["band"], b["share"], strict=True))
    assert got["0"] == 0.25 and got["1-19"] == 0.25 and got["20-39"] == 0.25
    assert got["120+"] == 0.25
    assert sum(got.values()) == pytest.approx(1.0)


def test_empty_count_bin_is_kept():
    w = frame(cnt=[0.0, 300.0], steps=[0.0, 10.0])
    q = r.bin_quantiles(w, EDGES)
    vig = q.filter(pl.col("count_bin") == "5999+")
    assert vig.height == 1 and vig["steps_median"].item() is None
    b = r.band_shares(w, EDGES, BANDS).filter(pl.col("count_bin") == "5999+")
    assert b.height == 8 and b["share"].sum() == 0


def test_hex_cells_shares_sum_to_one_with_beyond():
    rng = np.random.default_rng(1)
    cnt = rng.integers(0, 4000, 5000).astype(float)
    cnt[:3] = 20000.0  # 0.06% of minutes: above the 99.9th percentile
    steps = rng.integers(0, 201, 5000).astype(float)
    cells, meta = r.hex_cells(cnt, steps, np.arange(5000), 0.999, 50, min_people=1)
    assert meta["share_beyond"] > 0
    assert cells["share"].sum() + meta["share_beyond"] == pytest.approx(1.0)
    assert cells["x"].max() <= meta["xcap"] + meta["hex_dx"]


def test_hex_cells_puts_identical_points_in_one_cell():
    cells, _ = r.hex_cells(
        np.array([0.0] * 9 + [1000.0]),
        np.array([0.0] * 9 + [100.0]),
        np.arange(10),
        1.0,
        50,
        min_people=1,
    )
    assert cells.height == 2
    assert sorted(cells["share"].to_list()) == pytest.approx([0.1, 0.9])


def test_hex_cells_rejects_steps_above_200():
    with pytest.raises(ValueError, match="200"):
        r.hex_cells(np.array([100.0]), np.array([201.0]), np.array([1]), 1.0, 50, min_people=1)


def test_relation_outputs_pass_egress(tmp_path):
    from oai.export.egress import check_egress

    w = frame(cnt=[0.0, 300.0, 2500.0, 7000.0] * 50, steps=[0.0, 10.0, 105.0, 130.0] * 50)
    r.bin_quantiles(w, EDGES).write_csv(tmp_path / "relation_bins.csv")
    r.band_shares(w, EDGES, BANDS).write_csv(tmp_path / "relation_bands.csv")
    cells, meta = r.hex_cells(
        w["cnt"].to_numpy(), w["steps"].to_numpy(), w["ID"].to_numpy(), 0.999, 50, min_people=1
    )
    cells.write_csv(tmp_path / "relation_hex.csv")
    pl.DataFrame([meta]).write_csv(tmp_path / "relation_hex_meta.csv")
    report = check_egress(tmp_path, min_cell=5, small_cell="fail")
    assert report.ok, report.problems
    assert not report.warnings, report.warnings


def test_hex_cells_suppresses_cells_with_few_people():
    # 9 minutes from 9 people in one cell; 6 minutes from 1 person in another
    cnt = np.array([0.0] * 9 + [1000.0] * 6)
    steps = np.array([0.0] * 9 + [100.0] * 6)
    ids = np.array(list(range(9)) + [99] * 6)
    cells, meta = r.hex_cells(cnt, steps, ids, 1.0, 50, min_people=5)
    assert cells.height == 1 and cells["share"].item() == pytest.approx(9 / 15)
    assert meta["share_suppressed"] == pytest.approx(6 / 15)
    total = cells["share"].sum() + meta["share_beyond"] + meta["share_suppressed"]
    assert total == pytest.approx(1.0)


def test_hex_cells_requires_min_people():
    with pytest.raises(TypeError):
        r.hex_cells(np.array([0.0]), np.array([0.0]), np.array([1]), 1.0, 50)


@pytest.mark.parametrize("edges", [[0, 100, 2020], [0, 100, 500, 2020, 4000]])
def test_count_bins_reject_a_missing_vigorous_cut(edges):
    with pytest.raises(ValueError, match="vigorous"):
        r.check_count_edges(edges, 100, 2020, 5999)


def test_ledger_count_edges_pass():
    r.check_count_edges(EDGES, 100, 2020, 5999)


@pytest.mark.parametrize("bad", [np.nan, -1.0])
def test_hex_cells_rejects_nan_or_negative_steps(bad):
    with pytest.raises(ValueError):
        r.hex_cells(
            np.array([100.0, 100.0]),
            np.array([bad, 300.0 if bad != bad else 10.0]),
            np.array([1, 2]),
            1.0,
            50,
            min_people=1,
        )


def test_assign_groups_three_way():
    answers = pl.DataFrame({"ID": [1, 2, 3, 4], "yes": [True, True, False, True]})
    walkers = pl.DataFrame({"ID": [1, 2, 3], "steps_100:bout_days": [True, False, True]})
    g = d.assign_groups(answers, walkers, "steps_100:bout_days").sort("ID")
    assert g["group"].to_list() == ["Yes, step walker", "Yes, not a step walker", "No"]


def test_device_waves_mean_matches_combine():
    defs = devices.walker_definitions(2.0, 150.0, [100])
    cols = [
        "steps",
        "bout_days_per_week",
        "purposeful_min",
        "step_bout100_min",
        "step_bout100_days_per_week",
    ]
    dev = pl.DataFrame(
        {
            "ID": [1, 1, 2],
            "wave": ["06", "08", "06"],
            "valid": [True, True, True],
            "steps": [5000.0, 7000.0, 3000.0],
            "bout_days_per_week": [3.0, 1.0, 0.0],
            "purposeful_min": [30.0, 10.0, 0.0],
            "step_bout100_min": [20.0, 0.0, 0.0],
            "step_bout100_days_per_week": [3.0, 0.0, 0.0],
        }
    )
    w = devices.device_waves(dev, defs, cols)
    mean = w["mean"].sort("ID")
    assert mean["steps"].to_list() == [6000.0, 3000.0]
    assert mean["steps_100:bout_days"].to_list() == [False, False]  # (3 + 0) / 2 = 1.5 < 2
    assert w["06"].sort("ID")["steps_100:bout_days"].to_list() == [True, False]


def test_worse_knee_kl_replacement_rules():
    st = pl.DataFrame(
        {
            "ID": [1, 1, 1, 1],
            "SIDE": [1, 2, 1, 2],
            "visit": ["06", "06", "10", "10"],
            "kl": [2, None, 3, None],
            "replaced": [False, False, True, False],
        }
    )
    keep = d.worse_knee_kl(st, "keep_kl4").sort("visit")
    assert keep["kl_worse"].to_list() == [2, 4]
    cens = d.worse_knee_kl(st, "censor").sort("visit")
    assert cens.filter(pl.col("visit") == "10")["kl_worse"].item() is None


ORDER = ["00", "01", "03", "05", "06", "08", "10"]


def test_window_uses_nearest_visit_and_reports_it():
    long = pl.DataFrame(
        {"ID": [1, 1], "visit": ["01", "06"], "measure": ["m", "m"], "value": [10.0, 13.0]}
    )
    w = d.window_values(long, "00", "06", 1, ORDER)
    assert w.row(0, named=True) == {
        "ID": 1,
        "measure": "m",
        "start_used": "01",
        "end_used": "06",
        "change": 3.0,
    }


def test_window_blank_beyond_one_visit():
    long = pl.DataFrame(
        {"ID": [1, 1], "visit": ["03", "06"], "measure": ["m", "m"], "value": [10.0, 13.0]}
    )
    assert d.window_values(long, "00", "06", 1, ORDER).height == 0


def test_window_tie_goes_to_earlier_visit():
    long = pl.DataFrame(
        {
            "ID": [1, 1, 1],
            "visit": ["05", "08", "10"],
            "measure": ["m"] * 3,
            "value": [1.0, 2.0, 5.0],
        }
    )
    w = d.window_values(long, "06", "10", 1, ORDER)
    assert w.row(0, named=True)["start_used"] == "05" and w["change"].item() == 4.0


def test_knee_level_censors_replaced_knee_from_replacement_on():
    per_knee = pl.DataFrame(
        {
            "ID": [1] * 4,
            "SIDE": ["R", "L", "R", "L"],
            "visit": ["06", "06", "10", "10"],
            "measure": ["womac_pain"] * 4,
            "value": [3.0, 1.0, 9.0, 2.0],
        }
    )
    status = pl.DataFrame(
        {
            "ID": [1] * 4,
            "SIDE": ["R", "L", "R", "L"],
            "visit": ["06", "06", "10", "10"],
            "kl": [2.0, 1.0, None, 1.0],
            "replaced": [False, False, True, False],
        }
    )
    keep = d.knee_level(per_knee, status, "keep_kl4").sort("visit")
    assert keep["value"].to_list() == [3.0, 9.0]
    cens = d.knee_level(per_knee, status, "censor").sort("visit")
    assert cens["value"].to_list() == [3.0, 2.0]


def test_assemble_long_kl4_only_at_attended_visits():
    # knee R replaced at 06 (attended); the person misses 10, where knee_status still says
    # replaced (nominal-month timing): no kl_worse row at 10 under either rule
    person = pl.DataFrame({"ID": [1], "visit": ["06"], "measure": ["bmi"], "value": [30.0]})
    knee = pl.DataFrame(
        {
            "ID": [1, 1],
            "SIDE": ["R", "L"],
            "visit": ["06", "06"],
            "measure": ["womac_pain"] * 2,
            "value": [5.0, 2.0],
        }
    )
    status = pl.DataFrame(
        {
            "ID": [1] * 4,
            "SIDE": ["R", "L", "R", "L"],
            "visit": ["06", "06", "10", "10"],
            "kl": [None, 2.0, None, None],
            "replaced": [True, False, True, False],
        }
    )
    out = d.assemble_long([person], knee, status)
    kl = out.filter(pl.col("measure") == "kl_worse")
    assert kl.filter(pl.col("visit") == "10").height == 0
    keep = kl.filter(~pl.col("censored"))
    assert keep["value"].to_list() == [4.0]


def test_long_table_refuses_either_knee_replacement_scope():
    A = {
        "outcomes.arthroplasty_scope": "either",
        "discordance.trend_visits": ["06"],
        "discordance.anchor_visit": "06",
    }
    with pytest.raises(ValueError, match="arthroplasty_scope"):
        d.long_table(A)


A_TEST = {
    "discordance.bootstrap_reps": 50,
    "discordance.seed": 7,
    "discordance.smd_bands": {"small": 0.1, "lead": 0.2},
}


def test_smd_continuous_and_binary():
    assert d.smd(np.array([2.0, 4.0]), np.array([0.0, 2.0]), "continuous") == pytest.approx(
        2 / np.sqrt(2)
    )
    assert d.smd(np.array([1.0, 1.0, 0.0, 0.0]), np.array([0.0] * 4), "binary") == pytest.approx(
        0.5 / np.sqrt(0.125)
    )


def test_smd_needs_two_values_per_group():
    assert d.smd(np.array([1.0]), np.array([1.0, 2.0]), "continuous") is None


def test_smd_categorical_two_levels_matches_binary():
    a = np.array([1, 1, 2, 2, 2, 2.0])
    b = np.array([1, 1, 1, 1, 2, 2.0])
    as_binary = d.smd(a - 1, b - 1, "binary")
    assert d.smd(a, b, "categorical") == pytest.approx(abs(as_binary))


def test_smd_ci_brackets_and_is_reproducible():
    a = np.array([2.0, 4, 5, 7, 3, 6])
    b = np.array([0.0, 2, 1, 3, 2, 1])
    lo, hi = d.smd_ci(a, b, "continuous", 50, 1)
    assert lo < d.smd(a, b, "continuous") < hi
    assert (lo, hi) == d.smd_ci(a, b, "continuous", 50, 1)


def test_band_rule():
    assert [d.band(x, 0.1, 0.2) for x in (0.05, -0.15, 0.25, None)] == [
        "negligible",
        "small",
        "lead",
        "",
    ]


def test_screen_runs_without_no_group():
    groups = pl.DataFrame(
        {"ID": [1, 2, 3, 4], "group": ["Yes, step walker"] * 2 + ["Yes, not a step walker"] * 2}
    )
    values = pl.DataFrame(
        {
            "ID": [1, 2, 3, 4],
            "measure": ["bmi"] * 4,
            "window": ["level_06"] * 4,
            "value": [25.0, 27.0, 30.0, 32.0],
            "start_used": ["06"] * 4,
            "end_used": ["06"] * 4,
        }
    )
    out = d.screen(groups, values, {"bmi": "continuous"}, A_TEST, min_cell=1)
    assert out["persons_no"].item() == 0 and out["band"].item() == "lead"
    assert out["persons_step"].item() == 2 and out["area"].item() == "health"
    assert out["smd"].item() > 0


def test_screen_suppresses_small_groups():
    groups = pl.DataFrame(
        {
            "ID": list(range(1, 13)),
            "group": ["Yes, step walker"] * 2 + ["Yes, not a step walker"] * 6 + ["No"] * 4,
        }
    )
    values = pl.DataFrame(
        {
            "ID": list(range(1, 13)),
            "measure": ["bmi"] * 12,
            "window": ["level_06"] * 12,
            "value": [25.0, 27.0, 30.0, 32.0, 29.0, 31.0, 28.0, 33.0, 26.0, 27.0, 28.0, 29.0],
            "start_used": ["06"] * 12,
            "end_used": ["06"] * 12,
        }
    )
    row = d.screen(groups, values, {"bmi": "continuous"}, A_TEST, min_cell=5).row(0, named=True)
    assert row["summary_step"] == "" and row["persons_step"] is None
    assert row["summary_no"] == "" and row["persons_no"] is None
    assert row["persons_not"] == 6 and row["summary_not"] != ""
    assert row["smd"] is None and row["smd_lo"] is None and row["smd_hi"] is None
    assert row["band"] == ""


def test_summary_never_prints_nan():
    assert "nan" not in d._summary(np.array([3.0]), "continuous")


SCREEN_FIXTURE = pl.DataFrame(
    {
        "comparison": ["primary"] * 3,
        "censored": [False, False, True],
        "measure": ["bmi", "kl_worse", "womac_pain"],
        "area": ["health", "knee", "knee"],
        "window": ["level_06", "level_06", "change_00_06"],
        "start_used": ["06", "06", "00"],
        "end_used": ["06", "06", "06"],
        "persons_step": [300, 200, 250],
        "persons_not": [800, 500, 700],
        "persons_no": [280, 150, 260],
        "summary_step": ["27.10 (4.00)", "2.10 (1.00)", "0.50 (2.00)"],
        "summary_not": ["29.00 (5.00)", "2.50 (1.10)", "1.20 (2.50)"],
        "summary_no": ["29.50 (5.20)", "2.60 (1.00)", "1.30 (2.40)"],
        "smd": [0.42, 0.37, 0.25],
        "smd_lo": [0.30, 0.20, 0.10],
        "smd_hi": [0.55, 0.50, 0.40],
        "band": ["lead", "lead", "lead"],
    }
)
TRENDS_FIXTURE_EMPTY = pl.DataFrame()


def test_discordance_text_is_neutral():
    text = d.render_markdown(
        SCREEN_FIXTURE, TRENDS_FIXTURE_EMPTY, coverage_gap=0.0, label="default"
    )
    for word in ("bias", "over-report", "overreport", "false positive", "correction", "misclassif"):
        assert word not in text.lower()


def test_discordance_text_lists_leads_and_kl_caveat():
    text = d.render_markdown(
        SCREEN_FIXTURE, TRENDS_FIXTURE_EMPTY, coverage_gap=0.0, label="default"
    )
    assert "bmi" in text and "kl_worse" in text and "[default]" in text
    flagged = d.render_markdown(
        SCREEN_FIXTURE, TRENDS_FIXTURE_EMPTY, coverage_gap={"primary": 0.2}, label="default"
    )
    assert "KL coverage" in flagged
    leads = flagged.split("### Leads")[1].split("###")[0]
    assert "kl_worse" not in leads


def test_season_and_weekend_share_from_valid_days():
    byday = pl.DataFrame(
        {
            "ID": [1, 1, 1, 1, 2],
            "V06VDaySequence": [2, 1, 3, 4, 1],
            "V06PAMonth": [3, 2, 3, 3, 12],
            "V06PAWeekDay": ["Sunday", "Saturday", "Monday", "Tuesday", "Friday"],
        }
    )
    cal = d.device_calendar(byday, "06").sort("ID")
    assert cal["season"].to_list() == [1.0, 1.0]  # first valid day in Feb; December
    assert cal["weekend_share"].to_list() == [0.5, 0.0]
    months = pl.DataFrame({"m": list(range(1, 13))})
    seasons = months.select(d.season(pl.col("m")))["m"].to_list()
    assert seasons == [1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 1]


def test_device_descriptors_mean_basis_averages_valid_waves():
    device = pl.DataFrame(
        {
            "ID": [1, 1, 2],
            "wave": ["06", "08", "08"],
            "valid": [True, True, False],
            "valid_days": [7.0, 5.0, 7.0],
            "wear_hr": [14.0, 16.0, 15.0],
            "steps": [5000.0, None, 4000.0],
            "mv_min": [10.0, 20.0, 5.0],
        }
    )
    cal = pl.DataFrame(
        {"ID": [1, 1], "wave": ["06", "08"], "season": [2.0, 4.0], "weekend_share": [0.2, 0.4]}
    )
    out = d.device_descriptors(device, cal, "mean")
    assert out.height == 1
    r = out.row(0, named=True)
    assert r["valid_days"] == 6.0 and r["steps"] == 5000.0 and r["season"] == 2.0
    assert r["weekend_share"] == pytest.approx(0.3)
    assert d.device_descriptors(device, cal, "08")["valid_days"].to_list() == [5.0]


def test_kl_coverage_gap_between_yes_groups():
    groups = pl.DataFrame(
        {
            "comparison": ["c"] * 4,
            "ID": [1, 2, 3, 4],
            "group": ["Yes, step walker"] * 2 + ["Yes, not a step walker"] * 2,
        }
    )
    long = pl.DataFrame(
        {
            "ID": [1, 2, 3, 3],
            "visit": ["06", "06", "06", "06"],
            "measure": ["kl_worse"] * 4,
            "value": [2.0, 3.0, 1.0, 1.0],
            "censored": [False, False, False, True],
        }
    )
    cov = d.kl_coverage(groups, long)
    assert cov.filter(pl.col("group") == "Yes, not a step walker")["share"].item() == 0.5
    assert d.coverage_gaps(cov) == {"c": pytest.approx(0.5)}


def test_self_report_measures_are_context_not_leads():
    text = d.render_markdown(
        SCREEN_FIXTURE,
        TRENDS_FIXTURE_EMPTY,
        coverage_gap=0.0,
        label="default",
        self_report_measures={"primary": ["bmi"]},
    )
    leads = text.split("### Leads")[1].split("###")[0]
    assert "bmi" not in leads and "define the groups" in text
