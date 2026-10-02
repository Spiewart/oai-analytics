"""oai.derive.walking.walking_answers reads the 96-month survey (real data)."""

import polars as pl
import pytest

from oai.derive.walking import AMOUNT_ITEMS, WALKER_ITEM, walking_answers
from oai.loader import read_table


@pytest.mark.realdata
def test_walking_answers_reads_the_96_month_walking_items():
    answers = walking_answers()
    assert answers.columns == ["ID", "walk_item", "amount_years", "amount_months", "amount_times"]
    assert answers["ID"].n_unique() == answers.height == read_table("allclinical", "10").height
    assert set(answers["walk_item"].drop_nulls()) == {0, 1}
    # years 1-4, months 1-3 and times 1-3 are the categories the ledgered midpoints cover
    assert set(answers["amount_years"].drop_nulls()) <= {1, 2, 3, 4}
    assert set(answers["amount_months"].drop_nulls()) <= {1, 2, 3}
    assert set(answers["amount_times"].drop_nulls()) <= {1, 2, 3}
    # amounts are asked only of those who walk
    amounts = [f"amount_{name}" for name in AMOUNT_ITEMS]
    others = answers.filter(pl.col("walk_item").ne_missing(1))
    assert not others.select(pl.any_horizontal(pl.col(amounts).is_not_null()).any()).item()
    assert answers.filter(pl.col("walk_item") == 1)["amount_years"].is_not_null().any()


@pytest.mark.realdata
def test_walking_answers_item_lookup_is_case_insensitive():
    assert walking_answers(WALKER_ITEM.lower()).equals(walking_answers())
