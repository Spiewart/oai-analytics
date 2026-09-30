from pathlib import Path

import polars as pl
import pytest

from oai.catalog import catalog_for
from oai.config import get_settings
from oai.derive.knee import find_col, with_fallback, xray_readings

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
