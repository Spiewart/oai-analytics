import textwrap

import pytest
from typer.testing import CliRunner

from oai.cli import app
from oai.manifest import ManifestError, find_analysis, list_analyses, load_analysis

VALID = textwrap.dedent(
    """
    name = "demo"
    description = "Demo analysis"

    [inputs]
    tables = ["enrollees", "allclinical:00", "kxr_sq_bu:*"]

    [[steps]]
    id = "frame"
    lang = "python"
    stage = "local"
    entry = "frame.py"

    [[steps]]
    id = "models"
    lang = "r"
    stage = "enclave"
    entry = "models.R"
    needs = ["frame"]

    [export]
    frame = "frame.parquet"
    columns = ["ID", "SIDE"]

    [outputs]
    aggregate = ["results/*.csv"]
    """
)


def write_analysis(parent, text, name="demo", files=("frame.py", "models.R")):
    root = parent / name
    root.mkdir(parents=True)
    (root / "analysis.toml").write_text(text)
    for f in files:
        (root / f).write_text("# stub\n")
    return root


def test_valid_manifest(tmp_path):
    a = load_analysis(write_analysis(tmp_path, VALID))
    assert a.name == "demo" and a.description == "Demo analysis"
    assert a.inputs == ("enrollees", "allclinical:00", "kxr_sq_bu:*")
    assert [s.id for s in a.steps] == ["frame", "models"]
    assert a.steps[1].needs == ("frame",) and a.steps[1].stage == "enclave"
    assert a.export.columns == ("ID", "SIDE")
    assert a.aggregate_outputs == ("results/*.csv",)
    assert a.languages == {"python", "r"} and a.stages == {"local", "enclave"}


@pytest.mark.parametrize(
    "old, new, message",
    [
        ('name = "demo"', 'name = "other"', "must match its directory"),
        ('"allclinical:00"', '"AllClinical:0"', "bad input spec"),
        ('lang = "r"', 'lang = "julia"', "lang must be one of"),
        ('stage = "enclave"', 'stage = "cloud"', "stage must be one of"),
        ('needs = ["frame"]', 'needs = ["later"]', "not an earlier step"),
        ('entry = "models.R"', 'entry = "missing.R"', "not found"),
        ('id = "models"', 'id = "frame"', "duplicate step id"),
        ('columns = ["ID", "SIDE"]', "columns = []", "non-empty 'columns'"),
    ],
)
def test_invalid_manifests(tmp_path, old, new, message):
    assert old in VALID
    with pytest.raises(ManifestError, match=message):
        load_analysis(write_analysis(tmp_path, VALID.replace(old, new)))


def test_enclave_steps_require_export(tmp_path):
    text = VALID.split("[export]")[0]
    with pytest.raises(ManifestError, match=r"must declare \[export\]"):
        load_analysis(write_analysis(tmp_path, text))


def test_invalid_toml(tmp_path):
    with pytest.raises(ManifestError, match="invalid TOML"):
        load_analysis(write_analysis(tmp_path, "name = "))


def test_find_analysis_lists_available(tmp_path):
    write_analysis(tmp_path, VALID)
    with pytest.raises(ManifestError, match="available: demo"):
        find_analysis("nope", tmp_path)


def test_list_analyses(tmp_path):
    write_analysis(tmp_path, VALID)
    assert [a.name for a in list_analyses(tmp_path)] == ["demo"]


def test_cli_analyses(tmp_path, monkeypatch):
    write_analysis(tmp_path, VALID)
    monkeypatch.setenv("OAI_ANALYSES_DIR", str(tmp_path))
    result = CliRunner().invoke(app, ["analyses"])
    assert result.exit_code == 0, result.output
    assert "demo" in result.stdout and "[enclave,local]" in result.stdout
