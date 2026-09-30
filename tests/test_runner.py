import textwrap

import pytest
from typer.testing import CliRunner

from oai import runner
from oai.cli import app
from oai.config import load_settings
from oai.manifest import load_analysis
from oai.runner import RunnerError, run_analysis, select_steps

MANIFEST = textwrap.dedent(
    """
    name = "toy"

    [[steps]]
    id = "a"
    lang = "python"
    stage = "local"
    entry = "a.py"

    [[steps]]
    id = "b"
    lang = "python"
    stage = "enclave"
    entry = "b.py"
    needs = ["a"]

    [export]
    frame = "frame.parquet"
    columns = ["ID"]
    """
)

MARKER = textwrap.dedent(
    """
    import os, pathlib
    frame = pathlib.Path(os.environ["OAI_FRAME_DIR"])
    (frame / "{step}.done").write_text(os.environ["OAI_RESULTS_DIR"] + "|" + os.environ["OAI_ANALYSIS"])
    """
)


@pytest.fixture
def toy(tmp_path):
    root = tmp_path / "analyses" / "toy"
    root.mkdir(parents=True)
    (root / "analysis.toml").write_text(MANIFEST)
    for step in ("a", "b"):
        (root / f"{step}.py").write_text(MARKER.replace("{step}", step))
    return load_analysis(root)


def make_settings(tmp_path, **extra):
    env = {
        "OAI_WORK_DIR": str(tmp_path / "work"),
        "OAI_RESULTS_DIR": str(tmp_path / "results"),
        **extra,
    }
    return load_settings(env=env, repo_root=None)


def test_runs_local_steps_with_step_env(toy, tmp_path):
    results = run_analysis(toy, make_settings(tmp_path), stage="local", echo=lambda _: None)
    assert [(r.step_id, r.returncode) for r in results] == [("a", 0)]
    marker = tmp_path / "work" / "toy" / "a.done"
    assert marker.read_text() == f"{(tmp_path / 'results' / 'toy').resolve()}|toy"
    assert not (tmp_path / "work" / "toy" / "b.done").exists()


def test_enclave_steps_need_geno_dir_and_nothing_runs_without_it(toy, tmp_path):
    with pytest.raises(RunnerError, match="OAI_GENO_DIR"):
        run_analysis(toy, make_settings(tmp_path), echo=lambda _: None)
    assert not (tmp_path / "work" / "toy" / "a.done").exists()


def test_enclave_steps_run_when_geno_dir_set(toy, tmp_path):
    settings = make_settings(tmp_path, OAI_GENO_DIR=str(tmp_path / "geno"))
    run_analysis(toy, settings, stage="enclave", echo=lambda _: None)
    assert (tmp_path / "work" / "toy" / "b.done").exists()


def test_frame_dir_override(toy, tmp_path):
    frame = tmp_path / "bundle-data"
    env = {"OAI_FRAME_DIR": str(frame), "PATH": ""}
    run_analysis(toy, make_settings(tmp_path), stage="local", base_env=env, echo=lambda _: None)
    assert (frame / "a.done").exists()


def test_failing_step_stops_the_run(toy, tmp_path):
    (toy.root / "a.py").write_text("raise SystemExit(3)\n")
    settings = make_settings(tmp_path, OAI_GENO_DIR=str(tmp_path / "geno"))
    with pytest.raises(RunnerError, match="step 'a' failed with exit code 3"):
        run_analysis(toy, settings, echo=lambda _: None)
    assert not (tmp_path / "work" / "toy" / "b.done").exists()


def test_missing_rscript_fails_before_anything_runs(toy, tmp_path, monkeypatch):
    (toy.root / "m.R").write_text("cat('hi')\n")
    (toy.root / "analysis.toml").write_text(
        MANIFEST + '\n[[steps]]\nid = "m"\nlang = "r"\nstage = "local"\nentry = "m.R"\n'
    )
    analysis = load_analysis(toy.root)
    monkeypatch.setattr(runner.shutil, "which", lambda name: None)
    with pytest.raises(RunnerError, match="Rscript not found"):
        run_analysis(analysis, make_settings(tmp_path), stage="local", echo=lambda _: None)
    assert not (tmp_path / "work" / "toy" / "a.done").exists()


def test_select_steps_errors(toy):
    with pytest.raises(RunnerError, match="no step 'zz'"):
        select_steps(toy, step_id="zz")
    with pytest.raises(RunnerError, match="stage must be"):
        select_steps(toy, stage="cloud")


def test_cli_run(toy, tmp_path, monkeypatch):
    monkeypatch.setenv("OAI_ANALYSES_DIR", str(toy.root.parent))
    result = CliRunner().invoke(app, ["run", "toy", "--stage", "local"])
    assert result.exit_code == 0, result.output
    assert "a" in result.stdout
    assert (tmp_path / "work" / "toy" / "a.done").exists()
