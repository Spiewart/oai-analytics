"""Crepitus counts: availability, retention and exposed/unexposed event tables, on synthetic knees."""

import sys
from pathlib import Path

import polars as pl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analyses" / "crepitus"))

import crepitus as c  # noqa: E402

PEOPLE = pl.DataFrame({"ID": [1, 2, 3], "cohort": ["Progression", "Incidence", "Incidence"]})


def long(rows):
    return pl.DataFrame(
        rows, schema=["ID", "SIDE", "visit", "measure", "value"], orient="row"
    ).with_columns(pl.col("ID", "value").cast(pl.Int64))


def test_positive_uses_each_measures_own_threshold():
    df = long(
        [
            (1, "R", "00", "exam_crepitus", 1),
            (1, "R", "00", "koos_s2", 2),
            (1, "L", "00", "koos_s2", 3),
        ]
    ).with_columns(c._positive(c.thresholds_for(3)).alias("positive"))
    assert df["positive"].to_list() == [True, False, True]


def test_availability_counts_knees_and_persons_per_cohort_and_overall():
    data = long(
        [
            (1, "R", "00", "koos_s2", 4),
            (1, "L", "00", "koos_s2", 0),
            (2, "R", "00", "koos_s2", 3),
            (3, "R", "01", "koos_s2", 1),
        ]
    )
    coverage = pl.DataFrame(
        {"measure": ["koos_s2"] * 3, "visit": ["00", "01", "13"], "collected": [True, True, False]}
    )
    out = c.availability(data, PEOPLE, coverage, s2_threshold=3)

    def row(visit, cohort):
        return out.filter((pl.col("visit") == visit) & (pl.col("cohort") == cohort)).row(
            0, named=True
        )

    base = row("00", c.ALL)
    assert (base["persons"], base["knees"], base["knees_positive"], base["persons_positive"]) == (
        2,
        3,
        2,
        2,
    )
    assert row("00", "Progression")["knees"] == 2
    assert row("00", "Incidence")["persons_in_cohort"] == 2
    # a collected visit nobody answered stays in the grid, and an uncollected one is flagged
    assert row("01", "Progression")["knees"] == 0
    assert row("13", c.ALL)["collected"] is False


def test_retention_needs_baseline_and_a_later_visit():
    data = long(
        [
            (1, "R", "00", "exam_crepitus", 1),
            (1, "R", "01", "exam_crepitus", 0),
            (2, "R", "00", "exam_crepitus", 0),
            (3, "R", "03", "exam_crepitus", 1),
        ]
    )
    all_rows = c.retention(data, PEOPLE).filter(pl.col("cohort") == c.ALL).row(0, named=True)
    assert all_rows["persons_any_visit"] == 3
    assert all_rows["persons_baseline"] == 2
    assert all_rows["baseline_plus_later"] == 1


def test_event_table_splits_exposed_and_unexposed_among_ascertained_knees():
    knees = pl.DataFrame(
        {
            "ID": [1, 1, 2, 3],
            "SIDE": ["R", "L", "R", "R"],
            "cohort": ["Progression", "Progression", "Incidence", "Incidence"],
            "exam_crepitus": [1, 0, 1, None],
            "exam_grind_pain": [None, None, None, None],
            "koos_s2": [4, 0, 2, 0],
        }
    ).with_columns(
        pl.lit(True).alias("kl_progression_risk"),
        pl.Series("kl_progression_asc", [True, True, True, False]),
        pl.Series("kl_progression_event", [True, False, False, False]),
    )
    for outcome in c.OUTCOMES:
        if outcome != "kl_progression":
            knees = knees.with_columns(
                pl.lit(False).alias(f"{outcome}_risk"),
                pl.lit(False).alias(f"{outcome}_asc"),
                pl.lit(False).alias(f"{outcome}_event"),
            )
    out = c.event_table(knees, s2_threshold=3)
    pick = lambda exposure: (  # noqa: E731
        out.filter(
            (pl.col("outcome") == "kl_progression")
            & (pl.col("cohort") == c.ALL)
            & (pl.col("exposure") == exposure)
        ).row(0, named=True)
    )
    exam = pick("exam_crepitus")
    assert exam["knees_at_risk"] == 4 and exam["knees_ascertained"] == 3
    # knee 3 is not ascertained, so only knees 1, 2 (exposed) and 1L (unexposed) count
    assert (exam["exposed"], exam["unexposed"]) == (2, 1)
    assert (exam["events_exposed"], exam["events_unexposed"]) == (1, 0)
    s2 = pick("koos_s2")
    assert (s2["exposed"], s2["unexposed"]) == (1, 2)  # response 4 is exposed at >= 3
    assert pick("exam_grind_pain")["knees_with_exposure"] == 0


@pytest.mark.parametrize("threshold", [1, 2, 3])
def test_thresholds_only_move_the_s2_cut(threshold):
    t = c.thresholds_for(threshold)
    assert t["koos_s2"] == threshold and t["exam_crepitus"] == 1
