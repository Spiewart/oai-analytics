from pathlib import Path

import polars as pl
import pytest

from oai.catalog import catalog_for
from oai.config import get_settings
from oai.derive.knee import (
    find_col,
    frequent_knee_pain,
    knee_alignment,
    knee_replacement,
    visit_days,
    with_fallback,
    xray_readings,
)

KNEE_DATA = Path(__file__).parent / "fixtures" / "oai_knee"


@pytest.fixture(autouse=True)
def knee_release(isolated_settings, monkeypatch):
    monkeypatch.setenv("OAI_DATA_DIR", str(KNEE_DATA))
    get_settings.cache_clear()
    catalog_for.cache_clear()


def knee(df, id_, side):
    return df.filter((pl.col("ID") == id_) & (pl.col("SIDE") == side)).row(0, named=True)


def test_find_col_is_case_insensitive():
    df = pl.DataFrame({"readprj": [15], "ID": [1]})
    assert find_col(df, "READPRJ") == "readprj"
    with pytest.raises(KeyError):
        find_col(df, "SIDE")


def test_xray_readings_filters_project_and_maps_side():
    base = xray_readings(["00"], project=15)
    assert base.columns == ["ID", "SIDE", "visit", "KL", "JSM"]
    assert 1000003 not in base["ID"].to_list()  # only read in Project 37
    assert knee(base, 1000009, "L") == {
        "ID": 1000009,
        "SIDE": "L",
        "visit": "00",
        "KL": 4.0,
        "JSM": 3.0,
    }


def test_xray_readings_handles_lowercase_readprj_and_decimal_jsn():
    assert knee(xray_readings(["05"]), 1000009, "R")["JSM"] == 2.2


def test_with_fallback_prefers_first_frame_and_records_source():
    fu = with_fallback(xray_readings(["06"]), xray_readings(["05"]), value_cols=["KL", "JSM"])
    assert knee(fu, 1000001, "R")["source_visit"] == "06"
    row = knee(fu, 1000009, "R")  # 48-month reading is Project 37 only -> 36-month fallback
    assert (row["source_visit"], row["JSM"]) == ("05", 2.2)
    assert fu.filter((pl.col("ID") == 1000009) & (pl.col("SIDE") == "L")).is_empty()


def test_frequent_knee_pain_baseline_and_blank():
    pain = frequent_knee_pain("00", "P01KP{side}12CV")
    assert knee(pain, 1000009, "R")["frequent_pain"] is True
    assert knee(pain, 1000001, "L")["frequent_pain"] is False
    assert knee(pain, 1000010, "R")["frequent_pain"] is None  # blank cell


def test_frequent_knee_pain_followup_template():
    pain = frequent_knee_pain("05", "V{visit}KP{side}12CV")
    assert knee(pain, 1000009, "L")["frequent_pain"] is True


def test_visit_days():
    days = dict(visit_days("06").iter_rows())
    assert days[1000001] == 1470.0 and days[1000009] is None


def test_knee_replacement_counts_and_baseline_flag():
    rep = knee_replacement()
    assert knee(rep, 1000004, "L")["replaced_at_baseline"] is True
    assert knee(rep, 1000008, "R")["replaced"] is False  # adjudicated, failed to confirm
    assert knee(rep, 1000009, "L")["replaced"] is True  # adjudicated, confirmed
    assert knee(rep, 1000010, "R")["replaced"] is True  # seen on follow-up x-ray


def test_knee_replacement_by_days_window():
    by = pl.DataFrame({"ID": [1000009, 1000010], "days": [1100.0, 1455.0]})
    rep = knee_replacement(by)
    assert knee(rep, 1000009, "L")["replaced"] is True  # day 900 <= 1100
    assert knee(rep, 1000010, "R")["replaced"] is False  # day 2000 > 1455
    assert knee(rep, 1000001, "R")["replaced"] is False  # no days for this ID -> not replaced


def test_knee_alignment_pick_and_blank_films():
    earliest = knee_alignment()
    assert knee(earliest, 1000001, "R") == {"ID": 1000001, "SIDE": "R", "visit": "01", "hka": -3.5}
    assert knee(knee_alignment(pick="latest"), 1000001, "R")["hka"] == -1.0
    assert earliest.filter((pl.col("ID") == 1000009) & (pl.col("SIDE") == "L")).is_empty()


def test_knee_alignment_rejects_unknown_pick():
    with pytest.raises(ValueError, match="pick"):
        knee_alignment(pick="middle")


def test_find_col_error_names_the_table():
    with pytest.raises(KeyError, match="kxr_sq_bu00"):
        find_col(pl.DataFrame({"ID": [1]}), "SIDE", where="kxr_sq_bu00")
