from dataclasses import replace

import numpy as np
import polars as pl
import pytest

from oai.derive import accel
from oai.derive.accel import (
    DeviceRules,
    bout_mask,
    bout_spans,
    daily_summary,
    nonwear_mask,
    person_summary,
    read_minutes,
    release_valid_persons,
    reproduction,
)

RULES = DeviceRules()
HI = 3000.0


def nonwear(counts, days=None):
    c = np.array(counts, dtype=float)
    key = np.zeros(len(c), dtype=np.int64) if days is None else np.array(days, dtype=np.int64)
    return nonwear_mask(c, key, RULES)


def bouts(counts, wear=None):
    c = np.array(counts, dtype=float)
    w = np.ones(len(c), dtype=bool) if wear is None else np.array(wear)
    return bout_mask(c, np.zeros(len(c), dtype=np.int64), w, RULES)


def test_ninety_zero_minutes_are_nonwear_and_eighty_nine_are_wear():
    assert nonwear([500] + [0] * 90 + [500]).sum() == 90
    assert nonwear([500] + [0] * 89 + [500]).sum() == 0


def test_short_low_interruptions_join_zero_runs():
    assert nonwear([0] * 45 + [50, 99] + [0] * 45).all()
    assert nonwear([0] * 45 + [50, 60, 70] + [0] * 45).sum() == 0
    assert nonwear([0] * 45 + [100] + [0] * 45).sum() == 0


def test_interruptions_do_not_start_or_end_a_period():
    m = nonwear([50] + [0] * 90 + [50])
    assert not m[0] and not m[-1] and m[1:-1].all()


def test_nonwear_does_not_cross_days():
    assert nonwear([0] * 120, days=[1] * 60 + [2] * 60).sum() == 0
    assert nonwear([0] * 120, days=[1] * 120).sum() == 120


def test_missing_counts_count_as_zero_for_nonwear():
    assert nonwear([np.nan] * 90).all()


def test_bout_needs_eight_of_ten_minutes():
    assert bouts([HI] * 10).sum() == 10
    assert bouts([HI] * 7 + [0] * 8).sum() == 0
    # the bout spans its start through its last minute at or above the cutpoint
    assert bouts([HI] * 4 + [0] + [HI] * 4 + [0] * 6).sum() == 9


def test_bout_stops_at_three_below_and_trims_trailing_minutes():
    m = bouts([HI] * 12 + [0] * 3 + [HI] * 12)
    assert m.sum() == 24 and not m[12:15].any()


def test_bout_ignores_nonwear_minutes():
    assert bouts([HI] * 10, wear=[True] * 5 + [False] * 5).sum() == 0


def day_bouts(counts, days):
    c = np.array(counts, dtype=float)
    return bout_mask(c, np.array(days, dtype=np.int64), np.ones(len(c), dtype=bool), RULES)


def test_bout_does_not_span_two_days():
    # ten high minutes in a row, but five at the end of day 1 and five at the start of day 2
    assert day_bouts([HI] * 10, [1] * 5 + [2] * 5).sum() == 0
    assert day_bouts([HI] * 10, [1] * 10).sum() == 10


def test_bouts_are_found_within_each_day_and_stop_at_the_day_end():
    # day 1 ends inside a bout: its extension must not run into day 2's minutes
    counts = [0] * 5 + [HI] * 10 + [HI] * 4 + [0] * 8
    days = [1] * 15 + [2] * 12
    m = day_bouts(counts, days)
    assert m[:5].sum() == 0 and m[5:15].all()  # day 1: the full ten-minute bout
    assert m[15:19].sum() == 0  # day 2: four high minutes alone are not a bout
    assert m.sum() == 10


def test_bout_mask_of_empty_input_is_empty():
    m = bout_mask(np.array([]), np.array([], dtype=np.int64), np.array([], dtype=bool), RULES)
    assert m.shape == (0,) and m.dtype == bool


def minutes_frame(days, pid=1):
    rows = [(pid, day, i + 1, c) for day, counts in days.items() for i, c in enumerate(counts)]
    schema = {"ID": pl.Int64, "day": pl.Int64, "minute": pl.Int64, "cnt": pl.Float64}
    return pl.DataFrame(rows, schema=schema, orient="row")


def test_missing_counts_are_not_activity():
    # five missing minutes after 600 light ones: not activity (mv/light) but, as short zero
    # runs, still wear minutes, and they add nothing to the day's counts
    daily = daily_summary(minutes_frame({1: [500.0] * 600 + [None] * 5})).row(0, named=True)
    assert daily["wear_min"] == 605
    assert daily["mv_min"] == 0 and daily["light_min"] == 600
    assert daily["counts"] == 600 * 500.0


def test_daily_and_person_summaries():
    worn = [500.0] * 600
    active = [500.0] * 580 + [HI] * 20
    days = {1: worn, 2: active, 3: [500.0] * 599, **{d: worn for d in range(4, 11)}}
    frame = pl.concat(
        [minutes_frame(days, pid=1), minutes_frame({1: worn, 2: worn, 3: worn}, pid=2)]
    )
    daily = daily_summary(frame)
    day2 = daily.filter((pl.col("ID") == 1) & (pl.col("day") == 2)).row(0, named=True)
    assert day2["wear_min"] == 600 and day2["valid"]
    assert (day2["mv_min"], day2["light_min"], day2["counts"]) == (20, 580, 580 * 500 + 20 * HI)
    assert (day2["bout_min"], day2["purposeful_min"], day2["purposeful_bouts"]) == (20, 20, 1)
    assert not daily.filter((pl.col("ID") == 1) & (pl.col("day") == 3))["valid"].item()
    people = person_summary(daily).sort("ID")
    one, two = people.row(0, named=True), people.row(1, named=True)
    assert one["valid_days"] == 7 and one["valid"]  # days 1, 2, 4-8: the first 7 valid days
    assert abs(one["mv_min"] - 20 / 7) < 1e-9 and abs(one["bout_days_per_week"] - 1.0) < 1e-9
    assert abs(one["wear_hr"] - 10.0) < 1e-9
    assert two["valid_days"] == 3 and not two["valid"]


# Adjacent bouts. With the release's rules a bout always ends at least one minute before the
# next can start (a window holds <= 2 minutes below the cutpoint, so the minute after a bout's
# last high minute is low); rules that need fewer high minutes than the window leaves after
# the stop threshold (need <= window - stop_below) can place bouts back to back.
LOOSE = DeviceRules(bout_window=3, bout_need=2, bout_stop_below=1, purposeful_bout_minutes=3)


def spans(counts, rules):
    c = np.array(counts, dtype=float)
    return bout_spans(c, np.zeros(len(c), dtype=np.int64), np.ones(len(c), dtype=bool), rules)


def never_touch(starts, ends):
    """True when every bout starts at least one minute after the previous one ended."""
    return bool((starts[1:] > ends[:-1]).all())


def test_adjacent_bouts_are_counted_separately():
    # minutes 1-3 (high, low, high) and 4-6 (high x 3) are two bouts that touch
    frame = minutes_frame({1: [HI, 0.0, HI, HI, HI, HI]})
    day = daily_summary(frame, LOOSE).row(0, named=True)
    assert day["bout_min"] == 6 and day["purposeful_min"] == 6
    assert day["purposeful_bouts"] == 2


def test_release_rule_bouts_are_separate_and_counted_separately():
    # two real release-rule bouts: ten high minutes, three low, ten high
    counts = [HI] * 10 + [0.0] * 3 + [HI] * 10
    starts, ends = spans(counts, RULES)
    assert (starts.tolist(), ends.tolist()) == ([0, 13], [10, 23])
    assert never_touch(starts, ends)
    day = daily_summary(minutes_frame({1: counts}), RULES).row(0, named=True)
    assert (day["bout_min"], day["purposeful_min"], day["purposeful_bouts"]) == (20, 20, 2)


def test_purposeful_bouts_need_the_minimum_length_each():
    # the same two touching bouts, each three minutes long, are not 4-minute bouts
    rules = replace(LOOSE, purposeful_bout_minutes=4)
    day = daily_summary(minutes_frame({1: [HI, 0.0, HI, HI, HI, HI]}), rules).row(0, named=True)
    assert day["bout_min"] == 6
    assert (day["purposeful_min"], day["purposeful_bouts"]) == (0, 0)


def random_counts(n=300, seed=20261002):
    rng = np.random.default_rng(seed)
    for _ in range(n):
        yield np.where(rng.random(rng.integers(20, 60)) < 0.75, HI, 0.0)


def test_release_rules_never_place_bouts_back_to_back():
    several = 0
    for counts in random_counts():
        starts, ends = spans(counts, RULES)
        assert never_touch(starts, ends)
        several += len(starts) >= 2
    assert several > 50  # the check has something to compare in most sequences


def test_the_back_to_back_check_fails_where_bouts_touch():
    starts, ends = spans([HI, 0.0, HI, HI, HI, HI], LOOSE)
    assert (starts.tolist(), ends.tolist()) == ([0, 3], [3, 6])
    assert not never_touch(starts, ends)
    assert sum(not never_touch(*spans(counts, LOOSE)) for counts in random_counts()) > 50


# reproduction(): a null on either side of a comparison is a mismatch.
def ref_frame(**columns):
    n = len(columns["day"])
    base = {
        "ID": [1] * n,
        "wear_ref": [600.0] * n,
        "mv_ref": [20.0] * n,
        "bout_ref": [10.0] * n,
    }
    schema = {c: pl.Int64 if c in ("ID", "day") else pl.Float64 for c in (*base, "day")}
    return pl.DataFrame({**base, **columns}, schema=schema)


def daily_frame(days, **columns):
    n = len(days)
    base = {
        "ID": [1] * n,
        "day": days,
        "wear_min": [600.0] * n,
        "mv_min": [20.0] * n,
        "bout_min": [10.0] * n,
        "valid": [True] * n,
    }
    schema = {
        c: {"ID": pl.Int64, "day": pl.Int64, "valid": pl.Boolean}.get(c, pl.Float64) for c in base
    }
    return pl.DataFrame({**base, **columns}, schema=schema)


def test_reproduction_counts_a_null_on_either_side_as_a_mismatch(monkeypatch):
    days = [1, 2, 3, 4, 5, 6, 7]
    ref = ref_frame(
        day=days,
        wear_ref=[600.0, None, 600.0, 600.0, 600.0, 600.0, 600.0],
        mv_ref=[20.0, 20.0, None, 20.0, 20.0, 20.0, 20.0],
        bout_ref=[10.0, 10.0, 10.0, None, 10.0, 10.0, 10.0],
    )
    monkeypatch.setattr(accel, "release_by_day", lambda visit: ref)
    daily = daily_frame(
        days,
        wear_min=[600.0, 600.0, 600.0, 600.0, None, 600.0, 600.0],
        mv_min=[20.0, 20.0, 20.0, 20.0, 20.0, None, 20.0],
        bout_min=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, None],
    )
    rep = reproduction(daily, "06", RULES)
    assert rep["release_days"] == rep["matched_days"] == 7
    assert rep["wear_mismatch_days"] == 2  # a null reference (day 2) and a null ours (day 5)
    assert rep["mv_mismatch_days"] == 2  # days 3 and 6
    assert rep["bout_mismatch_days"] == 2  # days 4 and 7


def test_reproduction_without_nulls_counts_only_real_differences(monkeypatch):
    ref = ref_frame(day=[1, 2, 3], wear_ref=[600.0, 600.0, 600.0])
    monkeypatch.setattr(accel, "release_by_day", lambda visit: ref)
    daily = daily_frame(
        [1, 2, 3], wear_min=[600.0, 600.4, 601.0], mv_min=[20.0, 21.0, 20.0], bout_min=[10.0] * 3
    )
    rep = reproduction(daily, "08", RULES)
    assert rep["wear_mismatch_days"] == 1  # only the 1-minute difference reaches 0.5
    assert rep["mv_mismatch_days"] == 1 and rep["bout_mismatch_days"] == 0


# read_minutes() and release_valid_persons() read release tables; fake read_table.
def test_read_minutes_finds_columns_case_insensitively(monkeypatch):
    lf = pl.LazyFrame(
        {"id": [1, 1], "v06pastudyday": [1, 1], "v06minsequence": [2, 1], "v06mincnt": [5, 7]}
    )
    monkeypatch.setattr(accel, "read_table", lambda name, visit, lazy=False: lf)
    out = read_minutes("06")
    assert out.columns == ["ID", "day", "minute", "cnt"]
    assert out["minute"].to_list() == [1, 2] and out["cnt"].to_list() == [7.0, 5.0]


def test_read_minutes_missing_column_names_the_table(monkeypatch):
    lf = pl.LazyFrame({"ID": [1], "V06PAStudyDay": [1], "V06MinSequence": [1]})
    monkeypatch.setattr(accel, "read_table", lambda name, visit, lazy=False: lf)
    with pytest.raises(KeyError, match="V06MINCnt.*not found in acceldatabymin06"):
        read_minutes("06")


def test_release_valid_persons_uses_the_rules_minimum(monkeypatch):
    df = pl.DataFrame({"ID": [1, 2, 3, 4], "V06ANVDAYS": [3, 4, 5, None]})
    monkeypatch.setattr(accel, "read_table", lambda name, visit: df)
    assert release_valid_persons("06") == 2  # the default rules: at least 4 valid days
    assert release_valid_persons("06", DeviceRules(min_valid_days=5)) == 1
    assert release_valid_persons("06", DeviceRules(min_valid_days=3)) == 3
