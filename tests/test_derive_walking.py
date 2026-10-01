import polars as pl
import pytest

from oai.derive.pase import score_pase
from oai.derive.walking import walker_status, walking_sessions

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
