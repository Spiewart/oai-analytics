"""ActiGraph GT1M processing from OAI minute counts (AccelData_Descrip.pdf algorithm).

Parameterised by DeviceRules:
- non-wear: runs of >= nonwear_minutes zero-count minutes, which may include interruptions of
  <= interrupt_minutes consecutive minutes with 0 < count < interrupt_ceiling, found within each
  calendar day (PAStudyDay); a missing count counts as zero for non-wear and is never activity;
- valid day: >= valid_day_hours of wear; only the first max_valid_days valid days count;
- MV bout: starts at a wear minute >= mv_cutpoint once bout_need of the bout_window minutes from
  it are >= the cutpoint; extends while each bout_window-minute window holds fewer than
  bout_stop_below minutes below it; spans its start through its last minute >= the cutpoint;
- purposeful bout: an MV bout of at least purposeful_bout_minutes minutes (each bout the
  algorithm finds is judged on its own length and counted once).
With the release's rules this reproduces the release's by-day files (tests/test_accel_realdata.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial

import numpy as np
import polars as pl

from oai.derive.knee import find_col
from oai.loader import read_table

DAY_KEY_SCALE = 100_000  # ID * scale + PAStudyDay identifies one participant-day


@dataclass(frozen=True)
class DeviceRules:
    nonwear_minutes: int = 90
    interrupt_minutes: int = 2
    interrupt_ceiling: int = 100
    valid_day_hours: float = 10.0
    max_valid_days: int = 7
    min_valid_days: int = 4
    mv_cutpoint: int = 2020
    light_floor: int = 100
    bout_window: int = 10
    bout_need: int = 8
    bout_stop_below: int = 3
    purposeful_bout_minutes: int = 10


DEFAULT_RULES = DeviceRules()  # frozen, so safe as a default argument


def _runs(values: np.ndarray, key: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Start, end (exclusive) and value of each run of equal values within each key."""
    n = len(values)
    if n == 0:
        empty = np.zeros(0, dtype=np.int64)
        return empty, empty, empty
    change = np.ones(n, dtype=bool)
    change[1:] = (values[1:] != values[:-1]) | (key[1:] != key[:-1])
    starts = np.flatnonzero(change)
    ends = np.r_[starts[1:], n]
    return starts, ends, values[starts]


def nonwear_mask(
    counts: np.ndarray, day_key: np.ndarray, rules: DeviceRules = DEFAULT_RULES
) -> np.ndarray:
    """True for non-wear minutes; rows sorted by participant-day and minute."""
    c = np.nan_to_num(np.asarray(counts, dtype=float), nan=0.0)
    kind = np.where(c == 0, 0, np.where(c < rules.interrupt_ceiling, 1, 2))
    starts, ends, kinds = _runs(kind, day_key)
    keys = day_key[starts]
    out = np.zeros(len(c), dtype=bool)
    i, n = 0, len(starts)
    while i < n:
        if kinds[i] != 0:
            i += 1
            continue
        last = i
        while (
            last + 2 < n
            and kinds[last + 1] == 1
            and ends[last + 1] - starts[last + 1] <= rules.interrupt_minutes
            and kinds[last + 2] == 0
            and keys[last + 1] == keys[i]
            and keys[last + 2] == keys[i]
        ):
            last += 2
        if ends[last] - starts[i] >= rules.nonwear_minutes:
            out[starts[i] : ends[last]] = True
        i = last + 1
    return out


def bout_spans(
    counts: np.ndarray, day_key: np.ndarray, wear: np.ndarray, rules: DeviceRules = DEFAULT_RULES
) -> tuple[np.ndarray, np.ndarray]:
    """Start and end (exclusive) row of each MV bout, in row order; a bout never spans two days.

    Only wear minutes count as >= the cutpoint.
    """
    c = np.nan_to_num(np.asarray(counts, dtype=float), nan=0.0)
    above = (c >= rules.mv_cutpoint) & wear
    starts: list[int] = []
    ends: list[int] = []
    win, need, stop = rules.bout_window, rules.bout_need, rules.bout_stop_below
    if len(c) == 0:
        return np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.int64)
    seg_starts = np.flatnonzero(np.r_[True, day_key[1:] != day_key[:-1]])
    seg_ends = np.r_[seg_starts[1:], len(c)]
    for s, e in zip(seg_starts, seg_ends, strict=True):
        a = above[s:e]
        n = e - s
        if n < win or a.sum() < need:
            continue
        cs = np.r_[0, np.cumsum(a)]
        candidates = np.flatnonzero(a[: n - win + 1] & (cs[win:] - cs[: n - win + 1] >= need))
        next_free = 0
        for i in candidates:
            if i < next_free:
                continue
            j = i
            while j + win <= n and win - (cs[j + win] - cs[j]) < stop:
                j += 1
            end = min(j + win, n) - 1
            while not a[end]:
                end -= 1
            starts.append(s + i)
            ends.append(s + end + 1)
            next_free = end + 1
    return np.array(starts, dtype=np.int64), np.array(ends, dtype=np.int64)


def bout_mask(
    counts: np.ndarray, day_key: np.ndarray, wear: np.ndarray, rules: DeviceRules = DEFAULT_RULES
) -> np.ndarray:
    """True for minutes inside an MV bout; only wear minutes count as >= the cutpoint."""
    out = np.zeros(len(counts), dtype=bool)
    for start, end in zip(*bout_spans(counts, day_key, wear, rules), strict=True):
        out[start:end] = True
    return out


def daily_summary(minutes: pl.DataFrame, rules: DeviceRules = DEFAULT_RULES) -> pl.DataFrame:
    """One row per ID x day from `minutes` (ID, day, minute, cnt; one row per recorded minute)."""
    m = minutes.sort(["ID", "day", "minute"])
    key = m["ID"].to_numpy() * DAY_KEY_SCALE + m["day"].to_numpy()
    cnt = m["cnt"].cast(pl.Float64).to_numpy()
    wear = ~nonwear_mask(cnt, key, rules)
    c = np.nan_to_num(cnt, nan=0.0)
    bout = np.zeros(len(c), dtype=bool)
    purposeful = np.zeros(len(c), dtype=bool)
    purposeful_start = np.zeros(len(c), dtype=bool)
    for start, end in zip(*bout_spans(cnt, key, wear, rules), strict=True):
        bout[start:end] = True
        if end - start >= rules.purposeful_bout_minutes:
            purposeful[start:end] = True
            purposeful_start[start] = True
    per_minute = m.select("ID", "day").with_columns(
        pl.Series("wear", wear),
        pl.Series("mv", wear & (c >= rules.mv_cutpoint)),
        pl.Series("light", wear & (c >= rules.light_floor) & (c < rules.mv_cutpoint)),
        pl.Series("wear_counts", np.where(wear, c, 0.0)),
        pl.Series("bout", bout),
        pl.Series("purposeful", purposeful),
        pl.Series("purposeful_start", purposeful_start),
    )
    return (
        per_minute.group_by(["ID", "day"], maintain_order=True)
        .agg(
            pl.col("wear").sum().alias("wear_min"),
            pl.col("mv").sum().alias("mv_min"),
            pl.col("light").sum().alias("light_min"),
            pl.col("wear_counts").sum().alias("counts"),
            pl.col("bout").sum().alias("bout_min"),
            pl.col("purposeful").sum().alias("purposeful_min"),
            pl.col("purposeful_start").sum().alias("purposeful_bouts"),
        )
        .with_columns((pl.col("wear_min") >= rules.valid_day_hours * 60).alias("valid"))
    )


def first_valid_days(daily: pl.DataFrame, rules: DeviceRules = DEFAULT_RULES) -> pl.DataFrame:
    """Valid days only, the first max_valid_days per participant."""
    return (
        daily.filter("valid")
        .sort(["ID", "day"])
        .with_columns(pl.int_range(pl.len()).over("ID").alias("_k"))
        .filter(pl.col("_k") < rules.max_valid_days)
        .drop("_k")
    )


def person_summary(daily: pl.DataFrame, rules: DeviceRules = DEFAULT_RULES) -> pl.DataFrame:
    """Per participant, means per valid day over the first max_valid_days valid days."""
    return (
        first_valid_days(daily, rules)
        .group_by("ID", maintain_order=True)
        .agg(
            pl.len().alias("valid_days"),
            (pl.col("wear_min").mean() / 60).alias("wear_hr"),
            pl.col("mv_min").mean(),
            pl.col("light_min").mean(),
            pl.col("counts").mean().alias("counts_per_day"),
            pl.col("bout_min").mean(),
            pl.col("purposeful_min").mean(),
            ((pl.col("purposeful_bouts") > 0).mean() * 7).alias("bout_days_per_week"),
        )
        .with_columns((pl.col("valid_days") >= rules.min_valid_days).alias("valid"))
    )


def read_minutes(visit: str) -> pl.DataFrame:
    """ID, day, minute, cnt for one accelerometer wave ("06" or "08"), sorted."""
    lf = read_table("acceldatabymin", visit, lazy=True)
    # find_col wants a frame; one with no rows resolves names without reading the large file
    col = partial(
        find_col, pl.DataFrame(schema=lf.collect_schema()), where=f"acceldatabymin{visit}"
    )
    return (
        lf.select(
            pl.col(col("ID")).cast(pl.Int64).alias("ID"),
            pl.col(col(f"V{visit}PAStudyDay")).cast(pl.Int64).alias("day"),
            pl.col(col(f"V{visit}MinSequence")).cast(pl.Int64).alias("minute"),
            pl.col(col(f"V{visit}MINCnt")).cast(pl.Float64).alias("cnt"),
        )
        .sort(["ID", "day", "minute"])
        .collect()
    )


def release_by_day(visit: str) -> pl.DataFrame:
    """The release's by-day values: ID, day, wear_ref (minutes), mv_ref, bout_ref (Troiano)."""
    df = read_table("acceldatabyday", visit)
    col = partial(find_col, df, where=f"acceldatabyday{visit}")
    return df.select(
        pl.col(col("ID")).cast(pl.Int64).alias("ID"),
        pl.col(col(f"V{visit}PAStudyDay")).cast(pl.Int64).alias("day"),
        (pl.col(col(f"V{visit}WearHr")).cast(pl.Float64) * 60).round(0).alias("wear_ref"),
        pl.col(col(f"V{visit}DAYMVMinT")).cast(pl.Float64).alias("mv_ref"),
        pl.col(col(f"V{visit}DAYMVBoutMinT")).cast(pl.Float64).alias("bout_ref"),
    )


def reproduction(
    daily: pl.DataFrame, visit: str, rules: DeviceRules = DEFAULT_RULES
) -> dict[str, int]:
    """Agreement of our first valid days with the release's by-day file.

    A day is a mismatch when the values differ (wear by half a minute or more, MV and bout
    minutes at all) or when either side is null, so a missing value never counts as agreement.
    """
    ref = release_by_day(visit)
    matched = ref.join(first_valid_days(daily, rules), on=["ID", "day"], how="inner")

    def mismatches(differ: pl.Series) -> int:
        return int(differ.fill_null(True).sum())  # null in either value -> null -> mismatch

    return {
        "release_days": ref.height,
        "matched_days": matched.height,
        "wear_mismatch_days": mismatches((matched["wear_min"] - matched["wear_ref"]).abs() >= 0.5),
        "mv_mismatch_days": mismatches(matched["mv_min"] != matched["mv_ref"]),
        "bout_mismatch_days": mismatches(matched["bout_min"] != matched["bout_ref"]),
    }


def release_valid_persons(visit: str, rules: DeviceRules = DEFAULT_RULES) -> int:
    """Participants the release counts as valid (VxxANVDAYS >= rules.min_valid_days)."""
    df = read_table("accelerometry", visit)
    return df.filter(pl.col(find_col(df, f"V{visit}ANVDAYS")) >= rules.min_valid_days).height
