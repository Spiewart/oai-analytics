import json
import re
import subprocess
import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

import oai
from oai import runner
from oai.assumptions import AssumptionsError
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
    marker = tmp_path / "work" / "toy" / "default" / "a.done"
    assert marker.read_text() == f"{(tmp_path / 'results' / 'toy' / 'default').resolve()}|toy"
    assert not (tmp_path / "work" / "toy" / "default" / "b.done").exists()


def test_enclave_steps_need_geno_dir_and_nothing_runs_without_it(toy, tmp_path):
    with pytest.raises(RunnerError, match="OAI_GENO_DIR"):
        run_analysis(toy, make_settings(tmp_path), echo=lambda _: None)
    assert not (tmp_path / "work" / "toy" / "default" / "a.done").exists()


def test_enclave_steps_run_when_geno_dir_set(toy, tmp_path):
    settings = make_settings(tmp_path, OAI_GENO_DIR=str(tmp_path / "geno"))
    run_analysis(toy, settings, stage="enclave", echo=lambda _: None)
    assert (tmp_path / "work" / "toy" / "default" / "b.done").exists()


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
    assert not (tmp_path / "work" / "toy" / "default" / "b.done").exists()


def test_missing_rscript_fails_before_anything_runs(toy, tmp_path, monkeypatch):
    (toy.root / "m.R").write_text("cat('hi')\n")
    (toy.root / "analysis.toml").write_text(
        MANIFEST + '\n[[steps]]\nid = "m"\nlang = "r"\nstage = "local"\nentry = "m.R"\n'
    )
    analysis = load_analysis(toy.root)
    monkeypatch.setattr(runner.shutil, "which", lambda name: None)
    with pytest.raises(RunnerError, match="Rscript not found"):
        run_analysis(analysis, make_settings(tmp_path), stage="local", echo=lambda _: None)
    assert not (tmp_path / "work" / "toy" / "default" / "a.done").exists()


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
    assert (tmp_path / "work" / "toy" / "default" / "a.done").exists()


LABEL_STEP = textwrap.dedent(
    """
    import json, os, pathlib
    data = json.loads(pathlib.Path(os.environ["OAI_ASSUMPTIONS"]).read_text())
    out = pathlib.Path(os.environ["OAI_RESULTS_DIR"]) / "seen.txt"
    out.write_text(os.environ["OAI_RUN_LABEL"] + "|" + str(data["assumptions"]["model.corstr"]["value"]))
    """
)

TOY_ASSUMPTIONS = textwrap.dedent(
    """
    [model.corstr]
    value = "exchangeable"
    status = "open"
    source = "test"

    [variants.indep]
    description = "independence"
    set = { "model.corstr" = "independence" }
    """
)


@pytest.fixture
def labelled(toy):
    (toy.root / "a.py").write_text(LABEL_STEP)
    (toy.root / "assumptions.toml").write_text(TOY_ASSUMPTIONS)
    return load_analysis(toy.root)


def test_variants_write_to_separate_label_directories(labelled, tmp_path):
    settings = make_settings(tmp_path)
    run_analysis(labelled, settings, stage="local", echo=lambda _: None)
    run_analysis(labelled, settings, stage="local", variant="indep", echo=lambda _: None)
    results = tmp_path / "results" / "toy"
    assert (results / "default" / "seen.txt").read_text() == "default|exchangeable"
    assert (results / "indep" / "seen.txt").read_text() == "indep|independence"
    assert (tmp_path / "work" / "toy" / "indep" / "assumptions.resolved.json").is_file()
    assert (results / "indep" / "assumptions.resolved.json").is_file()


def test_override_creates_custom_label(labelled, tmp_path):
    run_analysis(
        labelled,
        make_settings(tmp_path),
        stage="local",
        overrides={"model.corstr": "ar1"},
        echo=lambda _: None,
    )
    [label_dir] = [
        p for p in (tmp_path / "results" / "toy").iterdir() if p.name.startswith("default+custom-")
    ]
    assert (label_dir / "seen.txt").read_text().endswith("|ar1")


def test_bad_override_fails_before_any_step_runs(labelled, tmp_path):
    with pytest.raises(AssumptionsError, match="unknown assumption"):
        run_analysis(labelled, make_settings(tmp_path), overrides={"nope": 1}, echo=lambda _: None)
    with pytest.raises(AssumptionsError, match="unknown variant"):
        run_analysis(labelled, make_settings(tmp_path), variant="nope", echo=lambda _: None)
    assert not (tmp_path / "results" / "toy").exists()


def test_cli_run_with_variant_and_set(labelled, tmp_path, monkeypatch):
    monkeypatch.setenv("OAI_ANALYSES_DIR", str(labelled.root.parent))
    result = CliRunner().invoke(app, ["run", "toy", "--stage", "local", "--variant", "indep"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "results" / "toy" / "indep" / "seen.txt").is_file()
    bad = CliRunner().invoke(app, ["run", "toy", "--stage", "local", "--set", "model.corstr=3"])
    assert bad.exit_code == 1 and "expects str" in bad.output


def test_assumptions_env_points_at_per_label_results_copy(labelled, tmp_path):
    # With an explicit OAI_FRAME_DIR (a bundle) frames are shared across labels, so steps
    # must read the per-label results copy of the resolved assumptions.
    (labelled.root / "a.py").write_text(
        "import os, pathlib\n"
        "pathlib.Path(os.environ['OAI_RESULTS_DIR'], 'where.txt').write_text(os.environ['OAI_ASSUMPTIONS'])\n"
    )
    env = {"OAI_FRAME_DIR": str(tmp_path / "bundle-data"), "PATH": ""}
    settings = make_settings(tmp_path)
    run_analysis(
        labelled, settings, stage="local", variant="indep", base_env=env, echo=lambda _: None
    )
    results = tmp_path / "results" / "toy" / "indep"
    assert Path((results / "where.txt").read_text()).parent == results.resolve()


def read_run_info(tmp_path, label="default"):
    return json.loads((tmp_path / "results" / "toy" / label / "run_info.json").read_text())


def test_run_info_records_a_finished_run(toy, tmp_path):
    run_analysis(toy, make_settings(tmp_path), stage="local", echo=lambda _: None)
    info = read_run_info(tmp_path)
    assert info["analysis"] == "toy"
    assert info["label"] == "default"
    assert info["variant"] is None
    assert info["steps"] == ["a"]
    assert info["git_commit"] is None and info["git_dirty"] is False  # repo_root=None
    assert info["oai_version"] == oai.__version__
    assert info["started_utc"] <= info["finished_utc"]
    assert runner.is_finished(tmp_path / "results" / "toy" / "default")


def test_run_info_has_no_finish_time_when_a_step_fails(toy, tmp_path):
    (toy.root / "a.py").write_text("raise SystemExit(3)\n")
    with pytest.raises(RunnerError, match="exit code 3"):
        run_analysis(toy, make_settings(tmp_path), stage="local", echo=lambda _: None)
    assert read_run_info(tmp_path)["finished_utc"] is None
    assert not runner.is_finished(tmp_path / "results" / "toy" / "default")


@pytest.mark.parametrize("content", [None, "not json", "[]", '{"finished_utc": null}'])
def test_is_finished_false_for_missing_or_unfinished(tmp_path, content):
    if content is not None:
        (tmp_path / "run_info.json").write_text(content)
    assert not runner.is_finished(tmp_path)


def test_checkout_state_reports_commit_and_uncommitted_changes(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)

    git("init", "-q")
    (repo / "f.txt").write_text("x")
    git("add", "f.txt")
    git("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "init")
    commit, dirty = runner.checkout_state(repo)
    assert re.fullmatch(r"[0-9a-f]{40}", commit) and dirty is False
    (repo / "f.txt").write_text("y")
    assert runner.checkout_state(repo) == (commit, True)
    assert runner.checkout_state(None) == (None, False)
    outside = tmp_path / "plain"
    outside.mkdir()
    assert runner.checkout_state(outside) == (None, False)


def test_r_profile_env_only_inside_a_checkout(tmp_path):
    assert runner.r_profile_env(make_settings(tmp_path)) == {}


def test_is_finished_requires_the_given_steps(toy, tmp_path):
    run_analysis(toy, make_settings(tmp_path), stage="local", echo=lambda _: None)
    results = tmp_path / "results" / "toy" / "default"
    assert runner.is_finished(results, ["a"])
    assert not runner.is_finished(results, ["a", "b"])


def test_run_info_records_input_table_versions(tmp_path):
    root = tmp_path / "analyses" / "versions"
    root.mkdir(parents=True)
    (root / "analysis.toml").write_text(
        'name = "versions"\n\n[inputs]\ntables = ["allclinical:00", "kxr_sq_bu:*"]\n\n'
        '[[steps]]\nid = "a"\nlang = "python"\nentry = "a.py"\n'
    )
    (root / "a.py").write_text("")
    fixtures = Path(__file__).parent / "fixtures" / "oai"
    settings = make_settings(tmp_path, OAI_DATA_DIR=str(fixtures))
    run_analysis(load_analysis(root), settings, echo=lambda _: None)
    info = json.loads((tmp_path / "results" / "versions" / "default" / "run_info.json").read_text())
    assert set(info["data_versions"]) == {"allclinical_00", "kxr_sq_bu_00", "kxr_sq_bu_01"}
    assert all(isinstance(v, str) and v for v in info["data_versions"].values())


def test_run_info_data_versions_empty_without_data(toy, tmp_path):
    run_analysis(toy, make_settings(tmp_path), stage="local", echo=lambda _: None)
    assert read_run_info(tmp_path)["data_versions"] == {}
