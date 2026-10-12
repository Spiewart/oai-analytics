import tomllib
from pathlib import Path

import polars as pl
import pytest

from oai.derive.pase import DEFAULT_WALKING, pase_visit, pase_walking_answers, score_pase
from oai.derive.walking import WALKER_ITEM, walker_status, walking_sessions

REPO = Path(__file__).resolve().parents[1]

MIDPOINTS = {"years": [3.0, 8.0, 15.5, 20.0], "months": [2.5, 6.5, 10.5], "times": [2.0, 6.0, 10.0]}
ANSWERS = pl.DataFrame(
    {
        "walk_item": [1, 1, 0, None],
        "amount_years": [2, None, None, None],
        "amount_months": [3, None, None, None],
        "amount_times": [3, None, None, None],
    },
    schema={c: pl.Int64 for c in ("walk_item", "amount_years", "amount_months", "amount_times")},
)


def walker(**kw):
    return ANSWERS.select(walker_status(**kw))["walker"].to_list()


def test_walker_status_codings():
    assert walker(yes_without_amount_as="walker", missing_as="non-walker") == [
        True,
        True,
        False,
        False,
    ]
    assert walker(yes_without_amount_as="non-walker", missing_as="exclude") == [
        True,
        False,
        False,
        None,
    ]
    assert walker(yes_without_amount_as="exclude", missing_as="walker") == [True, None, False, True]


def test_walking_sessions_uses_category_midpoints():
    df = pl.DataFrame(
        {"amount_years": [4, 1, None], "amount_months": [3, 1, 2], "amount_times": [3, 1, 2]}
    )
    assert df.select(walking_sessions(MIDPOINTS))["sessions"].to_list() == [
        20.0 * 10.5 * 10.0,
        3.0 * 2.5 * 2.0,
        None,
    ]


def test_score_pase_walking_subscore():
    ac = pl.DataFrame(
        {
            "ID": [1, 2, 3, 4],
            "V06PASE": [100.0, 50.0, None, 80.0],
            "V06PASE2": [0, 1, 3, None],
            "V06PASE2HR": [None, 2, 4, None],
        }
    )
    out = score_pase(ac, "V06")
    assert out["visit"].to_list() == ["06"] * 4
    assert out["pase_total"].to_list() == [100.0, 50.0, None, 80.0]
    assert out["pase_walking"].to_list() == [
        0.0,
        pytest.approx(20 * 1.5 / 7 * 1.5),
        pytest.approx(20 * 6 / 7 * 5),
        None,
    ]


def pase_frame(days, hours):
    return pl.DataFrame(
        {
            "ID": list(range(1, len(days) + 1)),
            "V06PASE": [50.0] * len(days),
            "V06PASE2": days,
            "V06PASE2HR": hours,
        },
        schema={
            "ID": pl.Int64,
            "V06PASE": pl.Float64,
            "V06PASE2": pl.Int64,
            "V06PASE2HR": pl.Int64,
        },
    )


def test_score_pase_walking_override():
    scoring = {"days": [0.0, 1.0, 2.0, 3.0], "hours": [1.0, 2.0, 3.0, 4.0], "weight": 14.0}
    ac = pase_frame([0, 1, 3], [None, 2, 4])
    assert score_pase(ac, "V06", scoring)["pase_walking"].to_list() == [
        0.0,
        pytest.approx(14 * 1 / 7 * 2),
        pytest.approx(14 * 3 / 7 * 4),
    ]
    # the override replaces the default scoring rather than adding to it
    assert (
        score_pase(ac, "V06")["pase_walking"].to_list()
        != score_pase(ac, "V06", scoring)["pase_walking"].to_list()
    )


def test_score_pase_out_of_range_codes_give_null_unless_never():
    ac = pase_frame(
        [4, -1, 1, 1, 1, 0],  # days 4 and -1 are not categories; the last never walks
        [2, 2, 0, 5, 9, 9],  # hours 0, 5 and 9 are not categories
    )
    assert score_pase(ac, "V06")["pase_walking"].to_list() == [None, None, None, None, None, 0.0]


def test_score_pase_zero_days_ignores_any_hours_answer():
    ac = pase_frame([0, 0, 0], [3, None, 99])
    assert score_pase(ac, "V06")["pase_walking"].to_list() == [0.0, 0.0, 0.0]


def test_score_pase_walking_without_a_days_answer_is_null():
    assert score_pase(pase_frame([None], [3]), "V06")["pase_walking"].to_list() == [None]


def test_default_walking_is_immutable():
    with pytest.raises(TypeError):
        DEFAULT_WALKING["weight"] = 1.0
    assert all(isinstance(DEFAULT_WALKING[k], tuple) for k in ("days", "hours"))


@pytest.mark.parametrize(
    ("scoring", "message"),
    [
        ({"days": [0.0, 1.5, 3.5], "hours": [0.5, 1.5, 3.0, 5.0], "weight": 20.0}, "days.*4"),
        ({"days": [0.0, 1.5, 3.5, 6.0], "hours": [0.5, 1.5, 3.0], "weight": 20.0}, "hours.*4"),
        (
            {"days": [0.0, 1.5, 3.5, 6.0, 7.0], "hours": [0.5, 1.5, 3.0, 5.0], "weight": 20.0},
            "days",
        ),
    ],
)
def test_score_pase_rejects_scoring_with_the_wrong_number_of_values(scoring, message):
    with pytest.raises(ValueError, match=message):
        score_pase(pase_frame([1], [1]), "V06", scoring)


@pytest.mark.parametrize(
    ("item", "values"),
    [("years", [3.0, 8.0, 15.5]), ("months", [2.5, 6.5]), ("times", [2.0, 6.0, 10.0, 12.0])],
)
def test_walking_sessions_rejects_midpoints_with_the_wrong_number_of_values(item, values):
    df = pl.DataFrame({"amount_years": [1], "amount_months": [1], "amount_times": [1]})
    with pytest.raises(ValueError, match=item):
        df.select(walking_sessions({**MIDPOINTS, item: values}))


def test_walker_item_is_the_lo2022_ledgered_item():
    ledger = tomllib.loads((REPO / "analyses/lo2022_walking/assumptions.toml").read_text())
    assert WALKER_ITEM == ledger["exposure"]["walker_item"]["value"]


def test_pase_walking_answers_keeps_the_answer_codes():
    ac = pase_frame([0, 1, 2, 3, 77, 88, None], [None, 1, 4, 2, 3, 2, 1])
    out = pase_walking_answers(ac, "V06")
    assert out.columns == ["ID", "pase_days_06", "pase_hours_06"]
    assert out["pase_days_06"].to_list() == [0, 1, 2, 3, None, None, None]
    assert out["pase_hours_06"].to_list() == [None, 1, 4, 2, None, None, None]


def test_pase_walking_answers_ignores_hours_after_never():
    ac = pase_frame([0, 0], [2, 4])
    assert pase_walking_answers(ac, "V06")["pase_hours_06"].to_list() == [None, None]


def test_pase_walking_answers_drops_hours_codes_outside_the_answers():
    ac = pase_frame([1, 2, 3], [88, 5, 0])
    assert pase_walking_answers(ac, "V06")["pase_hours_06"].to_list() == [None, None, None]


def test_pase_visit_gives_every_measure_a_visit_has_suffixed_by_visit():
    ac = pl.DataFrame(
        {
            "ID": [1, 2, 3],
            "V13PASE": [120, None, 40],
            "V13PASE2": [3, 0, None],
            "V13PASE2HR": [2, None, None],
            "V13VISDYS": [5120, 5150, None],
        },
        schema_overrides={"V13PASE2HR": pl.Int64},
    )
    out = pase_visit(ac, "13")
    assert out.columns == [
        "ID",
        "pase_total_13",
        "pase_walking_13",
        "pase_days_13",
        "pase_hours_13",
        "visdys_13",
    ]
    assert out["pase_total_13"].to_list() == [120.0, None, 40.0]
    assert out["pase_walking_13"].to_list() == [20.0 * 6.0 / 7 * 1.5, 0.0, None]
    assert out["pase_days_13"].to_list() == [3, 0, None]
    assert out["pase_hours_13"].to_list() == [2, None, None]
    assert out["visdys_13"].to_list() == [5120, 5150, None]


def test_pase_visit_without_a_total_gives_the_walking_item_only():
    # V14 asked PASE item 2 but released no total score
    ac = pl.DataFrame({"ID": [1], "V14PASE2": [1], "V14PASE2HR": [3], "V14VISDYS": [5860]})
    out = pase_visit(ac, "V14")
    assert out.columns == ["ID", "pase_walking_14", "pase_days_14", "pase_hours_14", "visdys_14"]
    assert out["pase_walking_14"].to_list() == [20.0 * 1.5 / 7 * 3.0]


def test_pase_visit_finds_a_lowercase_visit_days_column():
    # the release spells V01visdys in lowercase
    ac = pl.DataFrame(
        {"ID": [1], "V01PASE": [90], "V01PASE2": [0], "V01PASE2HR": [None], "V01visdys": [371]},
        schema_overrides={"V01PASE2HR": pl.Int64},
    )
    assert pase_visit(ac, "01")["visdys_01"].to_list() == [371]
