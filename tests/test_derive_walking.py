import tomllib
from pathlib import Path

import polars as pl
import pytest

from oai.derive.pase import DEFAULT_WALKING, score_pase
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
