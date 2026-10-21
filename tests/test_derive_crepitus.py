import polars as pl
import pytest

import oai.derive.crepitus as crepitus
from oai.derive.crepitus import crepitus_values, measure


@pytest.fixture(autouse=True)
def one_visit(monkeypatch):
    table = pl.DataFrame({"ID": [1], "V00RKPFCRE": [1], "V00KSXRKN2": [3]})
    monkeypatch.setattr(crepitus, "read_table", lambda name, visit: table)


def test_crepitus_values_is_wide_per_side():
    out = crepitus_values("00", ["exam_crepitus", "koos_s2"], sides=("R",))
    assert out.to_dict(as_series=False) == {
        "ID": [1],
        "SIDE": ["R"],
        "visit": ["00"],
        "exam_crepitus": [1],
        "koos_s2": [3],
    }
    assert out.schema["ID"] == pl.Int64 and out.schema["koos_s2"] == pl.Int64


def test_missing_column_raises():
    with pytest.raises(KeyError):
        crepitus_values("00", ["exam_grind_pain"], sides=("R",))


def test_measure_lookup():
    assert measure("koos_s2").template == "V{visit}KSX{side}KN2"
    with pytest.raises(KeyError):
        measure("womac_crepitus")
