from pathlib import Path

import pytest
from typer.testing import CliRunner

from oai.catalog import Catalog, CatalogError, TableFile, parse_filename
from oai.cli import app

OAI_FIXTURE_DATA = Path(__file__).parent / "fixtures" / "oai"


@pytest.mark.parametrize(
    "name, table, visit, kind",
    [
        ("AllClinical00.txt", "allclinical", "00", "visit"),
        ("ALLCLINICAL13.txt", "allclinical", "13", "visit"),
        ("kXR_SQ_BU01.txt", "kxr_sq_bu", "01", "visit"),
        ("Enrollees.txt", "enrollees", None, "static"),
        ("OUTCOMES99.txt", "outcomes", "99", "cumulative"),
        ("COVIDQ97.txt", "covidq", "97", "cumulative"),
        ("Something2010.txt", "something2010", None, "static"),
    ],
)
def test_parse_filename(name, table, visit, kind):
    tf = parse_filename(Path(name))
    assert (tf.table, tf.visit, tf.kind) == (table, visit, kind)


def test_formats_files_are_excluded():
    assert parse_filename(Path("sAGEAncillaryStudy_Formats.txt")) is None


def test_scan_fixture_release():
    cat = Catalog.scan(OAI_FIXTURE_DATA)
    assert cat.tables() == ["allclinical", "enrollees", "kxr_sq_bu", "outcomes"]
    assert cat.visits("kxr_sq_bu") == ["00", "01"]
    assert cat.get("outcomes", "99").kind == "cumulative"
    assert cat.get("enrollees").key == "enrollees"
    assert cat.get("AllClinical", "V01").key == "allclinical_01"
    assert len(cat) == 6


def test_duplicate_keys_raise():
    a = TableFile("kxr_sq_bu", "00", "visit", Path("kxr_sq_bu00.txt"))
    b = TableFile("kxr_sq_bu", "00", "visit", Path("KXR_SQ_BU00.txt"))
    with pytest.raises(CatalogError, match="Two files"):
        Catalog([a, b])


def test_unknown_table_and_visit_messages():
    cat = Catalog.scan(OAI_FIXTURE_DATA)
    with pytest.raises(CatalogError, match="Unknown table 'nope'"):
        cat.get("nope")
    with pytest.raises(CatalogError, match="available: 00, 01"):
        cat.get("kxr_sq_bu", "06")


@pytest.mark.parametrize(
    "spec, keys",
    [
        ("enrollees", ["enrollees"]),
        ("allclinical:01", ["allclinical_01"]),
        ("kxr_sq_bu:*", ["kxr_sq_bu_00", "kxr_sq_bu_01"]),
    ],
)
def test_resolve_input(spec, keys):
    assert [tf.key for tf in Catalog.scan(OAI_FIXTURE_DATA).resolve_input(spec)] == keys


def test_resolve_input_rejects_bad_spec():
    with pytest.raises(CatalogError, match="Bad input spec"):
        Catalog.scan(OAI_FIXTURE_DATA).resolve_input("AllClinical:0")


def test_missing_data_dir(tmp_path):
    with pytest.raises(CatalogError, match="not found"):
        Catalog.scan(tmp_path / "absent")


def test_cli_catalog_lists_tables():
    result = CliRunner().invoke(app, ["catalog"])
    assert result.exit_code == 0, result.output
    assert "kxr_sq_bu" in result.stdout and "00 01" in result.stdout
    assert "6 files, 4 tables" in result.stdout


def test_cli_reports_config_errors_without_traceback(monkeypatch):
    monkeypatch.setenv("OAI_DATA_DIR", "")
    result = CliRunner().invoke(app, ["catalog"])
    assert result.exit_code == 1
    assert "OAI_DATA_DIR is not set" in result.output
    assert "Traceback" not in result.output


@pytest.mark.realdata
def test_real_release_catalogs_cleanly():
    from oai.config import get_settings

    data_dir = get_settings().data_dir
    cat = Catalog.scan(data_dir)
    expected = [p for p in data_dir.glob("*.txt") if not p.stem.lower().endswith("_formats")]
    assert len(cat) == len(expected)
    assert "allclinical" in cat.tables() and "00" in cat.visits("allclinical")
