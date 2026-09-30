import dataclasses
import json
import subprocess
import tarfile
import textwrap
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest
from typer.testing import CliRunner

from oai.cli import app
from oai.config import load_settings
from oai.export.bundle import Builders, ExportError, default_builders, export_analysis, sha256_file
from oai.manifest import ExportSpec, Step, load_analysis

REPO = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)

MANIFEST = textwrap.dedent(
    """
    name = "toy"

    [[steps]]
    id = "frame"
    lang = "python"
    stage = "local"
    entry = "build_frame.py"

    [[steps]]
    id = "models"
    lang = "r"
    stage = "enclave"
    entry = "models.R"
    needs = ["frame"]

    [export]
    frame = "frame.parquet"
    columns = ["ID", "SIDE", "age0"]
    """
)

BUILD_FRAME = textwrap.dedent(
    """
    import os, pathlib
    import polars as pl
    out = pathlib.Path(os.environ["OAI_FRAME_DIR"]) / "frame.parquet"
    pl.DataFrame(
        {"ID": [1000001, 1000002], "SIDE": [1, 2], "age0": [61, 55], "not_exported": ["x", "y"]}
    ).write_parquet(out)
    """
)


def _git(repo, *args):
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def export_repo(fake_repo):
    root = fake_repo / "analyses" / "toy"
    root.mkdir(parents=True)
    (root / "analysis.toml").write_text(MANIFEST)
    (root / "build_frame.py").write_text(BUILD_FRAME)
    (root / "models.R").write_text('stop("enclave only")\n')
    (fake_repo / "r").mkdir()
    (fake_repo / "r" / "renv.lock").write_text('{"R": {"Version": "4.5.2"}}\n')
    _git(fake_repo, "init", "-q", "-b", "main")
    _git(fake_repo, "add", "-A")
    _git(fake_repo, "commit", "-q", "-m", "init")
    return fake_repo


@pytest.fixture
def settings(export_repo, tmp_path):
    return load_settings(env={"OAI_WORK_DIR": str(tmp_path / "work")}, repo_root=export_repo)


@pytest.fixture
def toy(export_repo):
    return load_analysis(export_repo / "analyses" / "toy")


def fake_builders(calls):
    def wheel(dest):
        calls.append("wheel")
        (dest / "oai_analytics-0.1.0-py3-none-any.whl").write_bytes(b"wheel")

    def rpkg(dest):
        calls.append("r")
        (dest / "oaimodels_0.1.0.tar.gz").write_bytes(b"rpkg")

    def reqs(dest):
        calls.append("reqs")
        (dest / "requirements.txt").write_text("polars==1.30.0\n")

    return Builders(python_wheel=wheel, r_package=rpkg, python_requirements=reqs)


def _extract(tar_path, dest):
    with tarfile.open(tar_path) as tar:
        tar.extractall(dest, filter="data")
    return dest / tar_path.name.removesuffix(".tar.gz")


def test_bundle_contents_and_checksums(toy, settings, tmp_path):
    calls = []
    result = export_analysis(toy, settings, builders=fake_builders(calls), now=NOW)
    assert result.path.name == "toy-20260930T120000Z.tar.gz"
    assert calls == ["wheel", "r", "reqs"]
    root = _extract(result.path, tmp_path / "x")
    for rel in [
        "run.sh",
        "README_ENCLAVE.md",
        "MANIFEST.json",
        "SHA256SUMS",
        "env/renv.lock",
        "env/requirements.txt",
        "config/oai.toml",
        "code/analyses/toy/analysis.toml",
        "code/oai_analytics-0.1.0-py3-none-any.whl",
        "code/oaimodels_0.1.0.tar.gz",
        "data/frame.parquet",
    ]:
        assert (root / rel).is_file(), rel
    manifest = json.loads((root / "MANIFEST.json").read_text())
    for rel, digest in manifest["files"].items():
        assert sha256_file(root / rel) == digest
    assert manifest["frame"] == {
        "file": "data/frame.parquet",
        "rows": 2,
        "columns": ["ID", "SIDE", "age0"],
    }
    assert pl.read_parquet(root / "data" / "frame.parquet").columns == ["ID", "SIDE", "age0"]
    assert manifest["git_dirty"] is False and len(manifest["git_commit"]) == 40


def test_run_script_is_rendered_and_valid_bash(toy, settings, tmp_path):
    result = export_analysis(toy, settings, builders=fake_builders([]), now=NOW)
    run_sh = _extract(result.path, tmp_path / "x") / "run.sh"
    text = run_sh.read_text()
    assert 'ANALYSIS="toy"' in text and "@@" not in text
    assert run_sh.stat().st_mode & 0o111
    subprocess.run(["bash", "-n", str(run_sh)], check=True)


def test_export_is_logged(toy, settings):
    result = export_analysis(toy, settings, builders=fake_builders([]), now=NOW)
    record = json.loads((settings.work_dir / "export_log.jsonl").read_text().splitlines()[-1])
    assert record["analysis"] == "toy"
    assert record["sha256"] == sha256_file(result.path)
    assert record["frame_rows"] == 2


def test_dirty_tree_is_refused(toy, settings, export_repo):
    (export_repo / "notes.md").write_text("uncommitted\n")
    with pytest.raises(ExportError, match="uncommitted"):
        export_analysis(toy, settings, builders=fake_builders([]))


def test_allow_dirty_is_recorded(toy, settings, export_repo):
    (export_repo / "notes.md").write_text("uncommitted\n")
    result = export_analysis(toy, settings, builders=fake_builders([]), allow_dirty=True)
    assert result.manifest["git_dirty"] is True


def test_missing_export_column(toy, settings):
    broken = dataclasses.replace(toy, export=ExportSpec("frame.parquet", ("ID", "nope")))
    with pytest.raises(ExportError, match="nope"):
        export_analysis(broken, settings, builders=fake_builders([]))


def test_analysis_without_export(toy, settings):
    with pytest.raises(ExportError, match=r"no \[export\]"):
        export_analysis(dataclasses.replace(toy, export=None), settings, builders=fake_builders([]))


def test_vendor_flag_explains_offline_procedure(toy, settings):
    with pytest.raises(ExportError, match="pip download"):
        export_analysis(toy, settings, builders=fake_builders([]), vendor=True)


def test_python_only_analysis_skips_r(toy, settings, tmp_path):
    python_only = dataclasses.replace(
        toy, steps=(Step("frame", "python", "local", "build_frame.py"),)
    )
    calls = []
    result = export_analysis(python_only, settings, builders=fake_builders(calls), now=NOW)
    assert calls == ["wheel", "reqs"]
    assert not (_extract(result.path, tmp_path / "x") / "env" / "renv.lock").exists()


def test_cli_export_unknown_analysis():
    result = CliRunner().invoke(app, ["export", "nope"])
    assert result.exit_code == 1
    assert "Unknown analysis" in result.output


@pytest.mark.slow
def test_real_wheel_ships_templates(tmp_path):
    default_builders(REPO).python_wheel(tmp_path)
    with zipfile.ZipFile(next(tmp_path.glob("*.whl"))) as zf:
        names = zf.namelist()
    assert "oai/export/templates/run.sh" in names
    assert "oai/export/templates/README_ENCLAVE.md" in names


# --- Final-review fixes (I7) ----------------------------------------------------


def test_run_script_bootstraps_renv_and_checks_r_version(toy, settings, tmp_path):
    result = export_analysis(toy, settings, builders=fake_builders([]), now=NOW)
    text = (_extract(result.path, tmp_path / "x") / "run.sh").read_text()
    assert 'requireNamespace("renv"' in text
    assert "lockfile_read" in text and "R.version" in text


def test_offline_recipe_fetches_exact_locked_versions(toy, settings, tmp_path):
    result = export_analysis(toy, settings, builders=fake_builders([]), now=NOW)
    readme = (_extract(result.path, tmp_path / "x") / "README_ENCLAVE.md").read_text()
    assert "lockfile_read" in readme and '"Archive"' in readme  # exact versions, incl. archived
    assert "download.packages" not in readme  # would fetch current, not locked, versions


def test_documented_r_floor_matches_lockfile_requirements():
    # MASS 7.3-65 / Matrix 1.7-4 in r/renv.lock need R >= 4.4.
    assert "R (>= 4.4)" in (REPO / "r" / "oaimodels" / "DESCRIPTION").read_text()
    assert "R ≥ 4.4" in (REPO / "README.md").read_text()
    assert "R >= 4.4" in (REPO / "src" / "oai" / "export" / "templates" / "run.sh").read_text()
