import polars as pl
import pytest

from oai.config import ConfigError
from oai.visits import (
    UnknownVisitError,
    UnverifiedVisitError,
    load_visit_map,
    nominal_month,
    normalize_code,
    time_years,
    to_long,
)


@pytest.mark.parametrize("raw", ["V06", "v06", "06", "6", 6])
def test_normalize_code(raw):
    assert normalize_code(raw) == "V06"


def test_normalize_code_rejects_non_visits():
    with pytest.raises(UnknownVisitError):
        normalize_code("P01")


def test_repo_visit_map_matches_docs():
    vm = load_visit_map()
    assert [vm[c].month for c in ("V00", "V01", "V03", "V05", "V06", "V08", "V10")] == [
        0,
        12,
        24,
        36,
        48,
        72,
        96,
    ]
    assert vm["V02"].contact == "phone"
    assert not vm["V13"].verified


def test_nominal_month_refuses_unverified_visits():
    with pytest.raises(UnverifiedVisitError, match="V13"):
        nominal_month("13")


def test_nominal_month_unknown_visit():
    with pytest.raises(UnknownVisitError, match="V20"):
        nominal_month("V20")


def test_verified_visit_without_month_is_a_config_error():
    with pytest.raises(ConfigError, match="V05"):
        load_visit_map({"visits": {"V05": {"verified": True}}})


def test_to_long_melts_visit_prefixed_columns():
    wide = pl.DataFrame(
        {
            "ID": [1000001, 1000001],
            "SIDE": [1, 2],
            "READPRJ": [15, 15],
            "V00XRKL": [1, 2],
            "V01XRKL": [2, 2],
            "V01XRJSM": [0, 1],
        }
    )
    long = to_long(wide, id_cols=("ID", "SIDE"))
    assert long.columns == ["ID", "SIDE", "visit", "XRKL", "XRJSM"]
    assert long.sort(["visit", "SIDE"]).rows() == [
        (1000001, 1, "V00", 1, None),
        (1000001, 2, "V00", 2, None),
        (1000001, 1, "V01", 2, 0),
        (1000001, 2, "V01", 2, 1),
    ]


def test_to_long_requires_id_columns():
    with pytest.raises(ValueError, match="SIDE"):
        to_long(pl.DataFrame({"ID": [1000001], "V00XRKL": [1]}), id_cols=("ID", "SIDE"))


def test_time_years_prefers_visdys_and_falls_back_to_nominal():
    long = pl.DataFrame(
        {"ID": [1000001] * 3, "visit": ["V00", "V01", "V03"], "VISDYS": [None, None, 740]}
    )
    out = time_years(long)
    assert out["time_years"].to_list() == pytest.approx([0.0, 1.0, 740 / 365.25])
    assert out["time_source"].to_list() == ["nominal", "nominal", "visdys"]


def test_time_years_without_visdys_column_uses_nominal():
    out = time_years(pl.DataFrame({"ID": [1000001, 1000001], "visit": ["V00", "V06"]}))
    assert out["time_years"].to_list() == [0.0, 4.0]


def test_unverified_visit_needs_visdys():
    long = pl.DataFrame({"ID": [1000001], "visit": ["V13"], "VISDYS": [None]})
    with pytest.raises(UnverifiedVisitError):
        time_years(long)


def test_unverified_visit_with_visdys_is_fine():
    long = pl.DataFrame({"ID": [1000001], "visit": ["V13"], "VISDYS": [4383]})
    assert time_years(long)["time_years"].to_list() == pytest.approx([4383 / 365.25])
