import numpy as np
import polars as pl

from oai.derive.accel import DeviceRules, bout_mask, daily_summary, nonwear_mask, person_summary

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


def minutes_frame(days, pid=1):
    rows = [(pid, day, i + 1, c) for day, counts in days.items() for i, c in enumerate(counts)]
    schema = {"ID": pl.Int64, "day": pl.Int64, "minute": pl.Int64, "cnt": pl.Float64}
    return pl.DataFrame(rows, schema=schema, orient="row")


def test_missing_counts_are_not_activity():
    daily = daily_summary(minutes_frame({1: [500.0] * 600 + [None] * 5}))
    assert daily["mv_min"].item() == 0 and daily["light_min"].item() == 600


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
