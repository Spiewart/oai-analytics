import os
import subprocess
import sys
from pathlib import Path

import polars as pl
import pytest

from oai import loader
from oai.catalog import CatalogError, catalog_for
from oai.config import get_settings
from oai.loader import LoaderError, MissingResolution, codebook, parse_table, read_table


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
    monkeypatch.setattr(
        loader, "parse_table", lambda path, **kw: calls.append(path) or real_parse(path, **kw)
    )
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


# --- Final-review fixes -------------------------------------------------------


def test_whitespace_only_cells_are_blank_not_text(tmp_path):
    # I1: the release uses " " as a blank; it must not force numeric columns to String.
    text = "ID|V09VISDYS|V09WOMKPR\n1000001|2900|3\n1000002| |  \n1000003| 3001 |1\n"
    df = parse_table(_write(tmp_path, "t09.txt", text))[0].collect()
    assert df.schema["V09VISDYS"] == pl.Int64
    assert df["V09VISDYS"].to_list() == [2900, None, 3001]
    assert df["V09WOMKPR"].to_list() == [3, None, 1]


def test_embedded_newlines_are_rejoined(tmp_path):
    # I2: records split by a newline inside a free-text field (COVIDQ97) are rejoined.
    text = "ID|V97NOTE|V97SCORE\n1000001|first line\nsecond line|5\n1000002|ok|6\n"
    df = parse_table(_write(tmp_path, "COVIDQ97.txt", text, newline="\r\n"))[0].collect()
    assert df.height == 2
    assert df.schema["ID"] == pl.Int64
    assert df["V97NOTE"].to_list() == ["first line second line", "ok"]
    assert df["V97SCORE"].to_list() == [5, 6]


def test_unrepairable_field_counts_raise(tmp_path):
    path = _write(tmp_path, "t00.txt", "ID|A|B\n1000001|1|2|3\n")
    with pytest.raises(LoaderError, match="line 2"):
        parse_table(path)


def test_comma_delimited_file_is_sniffed(tmp_path):
    # I2: hxr_sq_summary.txt is comma-delimited despite the .txt convention.
    path = _write(tmp_path, "hxr_sq_summary.txt", "ID,SIDE,SCORE\n1000001,1,2.5\n1000002,2,3\n")
    df = parse_table(path)[0].collect()
    assert df.columns == ["ID", "SIDE", "SCORE"]
    assert df["SCORE"].to_list() == [2.5, 3.0]


def test_header_without_a_known_separator_raises(tmp_path):
    with pytest.raises(LoaderError, match="separator"):
        parse_table(_write(tmp_path, "t00.txt", "just some text\nmore\n"))


def test_missing_policy_sees_column_and_table_and_can_keep_reasons(tmp_path, monkeypatch):
    # I5: the policy is column-aware and can keep a reason in a <col>__reason sidecar.
    calls = []

    def policy(raw, *, column, table):
        calls.append((column, table))
        if column == "V00XRKL" and raw.startswith(".P"):
            return MissingResolution(value=None, reason="prosthetic")
        return MissingResolution()

    monkeypatch.setattr(loader, "resolve_missing", policy)
    text = "ID|V00XRKL|V00XRJSM\n1000001|.P: Prosthetic|.P: Prosthetic\n1000002|2|1\n"
    df = parse_table(_write(tmp_path, "kxr_sq_bu00.txt", text), table="kxr_sq_bu_00")[0].collect()
    assert df["V00XRKL"].to_list() == [None, 2]
    assert df["V00XRKL__reason"].to_list() == ["prosthetic", None]
    assert "V00XRJSM__reason" not in df.columns
    assert ("V00XRKL", "kxr_sq_bu_00") in calls


def test_fingerprint_tracks_whole_loader_source(tmp_path, monkeypatch):
    # I6: helpers/constants the policy uses live in loader.py; editing any of it must rebuild caches.
    copy = tmp_path / "loader_copy.py"
    copy.write_text(Path(loader.__file__).read_text() + "\n# edited\n")
    before = loader.policy_fingerprint()
    monkeypatch.setattr(loader, "__file__", str(copy))
    assert loader.policy_fingerprint() != before


def test_fingerprint_tracks_polars_version(monkeypatch):
    before = loader.policy_fingerprint()
    monkeypatch.setattr(loader.pl, "__version__", "0.0.0-test")
    assert loader.policy_fingerprint() != before


@pytest.mark.realdata
def test_largest_table_caches_within_memory_budget():
    # I8: building the cache for the 786 MB by-minute accelerometer file must stream.
    code = (
        "import resource, sys; from oai.loader import read_table; "
        "read_table('acceldatabymin', '06', lazy=True); "
        "r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss; "
        "print(r if sys.platform == 'darwin' else r * 1024)"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert int(out.stdout.strip()) < 8 * 1024**3


@pytest.mark.realdata
def test_whole_release_loads_cleanly():
    # Audit every table: IDs are integer and present; no numeric column is left as text.
    catalog = catalog_for(get_settings().data_dir)
    offenders = []
    for table in catalog.tables():
        for visit in catalog.visits(table) or [None]:
            df = read_table(table, visit)
            for id_col in [c for c in df.columns if c.lower() == "id"]:
                if df.schema[id_col] != pl.Int64 or df[id_col].null_count():
                    offenders.append(f"{table}:{visit}:{id_col} id not clean Int64")
            for col, dtype in df.schema.items():
                if dtype != pl.String:
                    continue
                values = df[col].drop_nulls()
                if values.is_empty() or values.str.contains(loader.LEADING_ZERO).any():
                    continue
                if values.cast(pl.Float64, strict=False).null_count() == 0:
                    offenders.append(f"{table}:{visit}:{col} numeric values typed String")
    assert not offenders, offenders[:20]
