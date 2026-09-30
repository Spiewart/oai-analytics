import os

import polars as pl
import pytest

from oai import loader
from oai.catalog import CatalogError, catalog_for
from oai.config import get_settings
from oai.loader import codebook, parse_table, read_table


def _write(directory, name, text, *, encoding="utf-8", newline="\n"):
    path = directory / name
    path.write_bytes(text.replace("\n", newline).encode(encoding))
    return path


def test_types_and_coded_split():
    df = read_table("kxr_sq_bu", "00")
    assert df.schema["ID"] == pl.Int64
    assert df.schema["SIDE"] == pl.Int64
    assert df["SIDE"].to_list() == [1, 2, 1]
    assert df.schema["VERSION"] == pl.Float64
    assert df["V00XRJSM"].to_list() == [1, 0, 2]


def test_codebook_records_labels_and_missing_codes():
    cb = codebook("allclinical", "00")
    assert cb.labels["V00KPACT30"] == {"0": "No", "1": "Yes"}
    assert cb.missing["P01BMI"] == {".": "Missing Form/Incomplete Workbook"}
    assert cb.missing["V00WOMKPR"] == {".A": "Not Expected"}


def test_missing_codes_become_null_under_reference_policy():
    # Assumes the reference resolve_missing (every missing code -> null).
    # Update if the user-authored policy differs.
    df = read_table("allclinical", "00")
    assert df["P01BMI"].to_list() == [27.4, None, 31.2]
    assert df.schema["P01BMI"] == pl.Float64


def test_leading_zero_barcodes_stay_strings():
    df = read_table("kxr_sq_bu", "00")
    assert df.schema["V00BARCDBU"] == pl.String
    assert df["V00BARCDBU"][0] == "016600000001"


def test_free_text_colon_and_leading_dot_decimals_are_not_misparsed(tmp_path):
    path = _write(
        tmp_path, "t00.txt", "ID|NOTE|FRAC\n1000001|Note: see form|.5\n1000002|plain|0.25\n"
    )
    lf, cb = parse_table(path)
    df = lf.collect()
    assert df["NOTE"].to_list() == ["Note: see form", "plain"]
    assert df["FRAC"].to_list() == [0.5, 0.25]
    assert "NOTE" not in cb.labels
    assert "FRAC" not in cb.missing


def test_crlf_and_latin1_files_load(tmp_path):
    text = "ID|NAME|V00AGE\n1000001|caf\xe9|61\n1000002|plain|55\n"
    path = _write(tmp_path, "t00.txt", text, encoding="latin-1", newline="\r\n")
    df = parse_table(path)[0].collect()
    assert df["V00AGE"].to_list() == [61, 55]
    assert df["NAME"].to_list()[1] == "plain"
    assert df["NAME"].to_list()[0].startswith("caf")


def test_columns_and_lazy():
    lf = read_table("allclinical", "00", columns=["ID", "V00AGE"], lazy=True)
    assert isinstance(lf, pl.LazyFrame)
    assert lf.collect().columns == ["ID", "V00AGE"]


def test_cache_is_reused(monkeypatch):
    read_table("enrollees")
    monkeypatch.setattr(loader, "parse_table", lambda path: pytest.fail("cache was not used"))
    assert read_table("enrollees").height == 3


def test_cache_rebuilt_when_source_changes(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    src = _write(data, "Enrollees.txt", "ID|P02SEX\n1000001|1: Male\n")
    monkeypatch.setenv("OAI_DATA_DIR", str(data))
    get_settings.cache_clear()
    catalog_for.cache_clear()
    assert read_table("enrollees")["P02SEX"].to_list() == [1]
    src.write_text("ID|P02SEX\n1000001|2: Female\n1000002|1: Male\n")
    st = src.stat()
    os.utime(src, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
    assert read_table("enrollees")["P02SEX"].to_list() == [2, 1]


def test_cache_rebuilt_when_missing_policy_changes(monkeypatch):
    read_table("enrollees")
    calls = []
    real_parse = loader.parse_table
    monkeypatch.setattr(loader, "policy_fingerprint", lambda: "a-different-policy")
    monkeypatch.setattr(loader, "parse_table", lambda path: calls.append(path) or real_parse(path))
    read_table("enrollees")
    assert len(calls) == 1


@pytest.mark.parametrize("max_columns", [0, 1000])
def test_streaming_and_in_memory_paths_agree(monkeypatch, max_columns):
    monkeypatch.setattr(loader, "STREAMING_MAX_COLUMNS", max_columns)
    df = read_table("allclinical", "01")
    assert df["V01PASE"].to_list() == [170, 100, None]
    assert df.schema["V01BMI"] == pl.Float64


def test_unknown_table_is_a_user_error():
    with pytest.raises(CatalogError, match="Unknown table"):
        read_table("nope")


@pytest.mark.realdata
def test_real_core_tables_load():
    enrollees = read_table("enrollees")
    assert enrollees.height > 4000
    assert enrollees.schema["ID"] == pl.Int64
    kxr = read_table("kxr_sq_bu", "00", columns=["ID", "SIDE", "V00XRKL"])
    assert set(kxr["SIDE"].drop_nulls().unique().to_list()) <= {1, 2}
    allclinical = read_table("allclinical", "00", lazy=True)
    assert {"V00AGE", "P01BMI", "V00WOMKPR"} <= set(allclinical.collect_schema().names())
