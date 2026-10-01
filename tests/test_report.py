"""`oai report`: render an analysis's Quarto report (fake quarto; one real render if available)."""

import json
import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from oai import config as oai_config
from oai.cli import app
from oai.config import load_settings
from oai.manifest import load_analysis
from oai.report import ReportError, find_quarto, missing_runs, render_report
from oai.runner import run_analysis

REPO = Path(__file__).resolve().parents[1]

MANIFEST = textwrap.dedent(
    """
    name = "toy"

    [[steps]]
    id = "a"
    lang = "python"
    entry = "a.py"

    [report]
    entry = "report.qmd"
    runs = ["default", "alt"]
    assets = ["notes.md"]
    """
)
ASSUMPTIONS = textwrap.dedent(
    """
    [cohort.min_age]
    value = 50
    status = "confirmed"
    source = "test"

    [variants.alt]
    description = "older"
    set = { "cohort.min_age" = 60 }
    """
)
STEP = 'import os, pathlib\npathlib.Path(os.environ["OAI_RESULTS_DIR"], "out.csv").write_text("metric,value\\nm,1\\n")\n'
# Stands in for `quarto render <entry> --to typst`, run in the report directory.
FAKE_QUARTO = textwrap.dedent(
    """\
    #!/bin/sh
    stem="${2%.qmd}"
    mkdir -p figures .quarto
    echo fig > figures/f.png
    echo scratch > .quarto/x
    echo typ > "$stem.typ"
    if [ -n "$FAKE_QUARTO_FAIL" ]; then echo "boom: render failed" >&2; exit 1; fi
    {
      echo "args=$*"
      echo "root=$OAI_RESULTS_ROOT"
      echo "report=$OAI_REPORT_DIR"
      echo "runs=$OAI_REPORT_RUNS"
      echo "profile=$RENV_PROFILE"
      ls
    } > "$stem.pdf"
    """
)


def make_toy(tmp_path, manifest=MANIFEST, qmd="# toy\n"):
    root = tmp_path / "analyses" / "toy"
    root.mkdir(parents=True)
    (root / "analysis.toml").write_text(manifest)
    (root / "assumptions.toml").write_text(ASSUMPTIONS)
    (root / "a.py").write_text(STEP)
    (root / "report.qmd").write_text(qmd)
    (root / "notes.md").write_text("notes\n")
    return load_analysis(root)


def make_settings(tmp_path, repo_root=None):
    env = {"OAI_WORK_DIR": str(tmp_path / "work"), "OAI_RESULTS_DIR": str(tmp_path / "results")}
    return load_settings(env=env, repo_root=repo_root)


def fake_quarto(tmp_path) -> Path:
    path = tmp_path / "bin" / "quarto"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(FAKE_QUARTO)
    path.chmod(0o755)
    return path


@pytest.fixture
def toy(tmp_path):
    return make_toy(tmp_path)


@pytest.fixture
def quarto_env(tmp_path):
    return {**os.environ, "OAI_QUARTO": str(fake_quarto(tmp_path))}


def quiet(_):
    pass


def test_render_needs_a_report_section(tmp_path, quarto_env):
    analysis = make_toy(tmp_path, MANIFEST.split("[report]")[0])
    with pytest.raises(ReportError, match="no \\[report\\] section"):
        render_report(analysis, make_settings(tmp_path), base_env=quarto_env, echo=quiet)


def test_missing_runs_counts_only_finished_runs(toy, tmp_path):
    settings = make_settings(tmp_path)
    assert missing_runs(toy, settings) == ["default", "alt"]
    run_analysis(toy, settings, echo=quiet)
    assert missing_runs(toy, settings) == ["alt"]
    info = tmp_path / "results" / "toy" / "default" / "run_info.json"
    info.write_text(json.dumps({**json.loads(info.read_text()), "finished_utc": None}))
    assert missing_runs(toy, settings) == ["default", "alt"]


def test_report_without_run_flag_names_missing_runs(toy, tmp_path, quarto_env):
    with pytest.raises(ReportError, match="default, alt.*oai report toy --run"):
        render_report(toy, make_settings(tmp_path), base_env=quarto_env, echo=quiet)


def test_run_flag_runs_only_the_missing_runs(toy, tmp_path, quarto_env):
    settings = make_settings(tmp_path)
    run_analysis(toy, settings, echo=quiet)
    default_info = (tmp_path / "results" / "toy" / "default" / "run_info.json").read_text()
    pdf = render_report(toy, settings, run_missing=True, base_env=quarto_env, echo=quiet)
    assert pdf.is_file()
    assert missing_runs(toy, settings) == []
    assert (tmp_path / "results" / "toy" / "default" / "run_info.json").read_text() == default_info


def test_render_copies_inputs_sets_env_and_keeps_only_pdf_and_figures(toy, tmp_path, quarto_env):
    pdf = render_report(
        toy, make_settings(tmp_path), run_missing=True, base_env=quarto_env, echo=quiet
    )
    out = (tmp_path / "results" / "toy" / "report").resolve()  # settings resolve paths
    assert pdf == out / "report.pdf"
    lines = pdf.read_text().splitlines()
    assert "args=render report.qmd --to typst" in lines
    assert f"root={(tmp_path / 'results' / 'toy').resolve()}" in lines
    assert f"report={out.resolve()}" in lines
    assert "runs=default,alt" in lines
    assert "profile=report" in lines
    assert {"report.qmd", "notes.md"} <= set(lines)  # copied before rendering
    assert sorted(p.name for p in out.iterdir()) == ["figures", "report.pdf"]
    assert (out / "figures" / "f.png").is_file()


def test_render_replaces_a_previous_report(toy, tmp_path, quarto_env):
    settings = make_settings(tmp_path)
    stale = tmp_path / "results" / "toy" / "report" / "figures" / "stale.png"
    stale.parent.mkdir(parents=True)
    stale.write_text("old")
    render_report(toy, settings, run_missing=True, base_env=quarto_env, echo=quiet)
    assert not stale.exists()


def test_failed_render_keeps_partial_output_and_shows_stderr(toy, tmp_path, quarto_env):
    with pytest.raises(ReportError, match="(?s)exit 1.*partial output kept.*boom: render failed"):
        render_report(
            toy,
            make_settings(tmp_path),
            run_missing=True,
            base_env={**quarto_env, "FAKE_QUARTO_FAIL": "1"},
            echo=quiet,
        )
    out = tmp_path / "results" / "toy" / "report"
    assert (out / "report.typ").is_file() and (out / "report.qmd").is_file()


def test_find_quarto_order(tmp_path):
    def exe(name):
        path = tmp_path / name / "quarto"
        path.parent.mkdir()
        path.write_text("#!/bin/sh\n")
        path.chmod(0o755)
        return path

    explicit, configured, on_path, bundle = exe("e"), exe("c"), exe("p"), exe("b")
    env = {"OAI_QUARTO": str(explicit), "PATH": str(on_path.parent)}
    assert find_quarto(env, str(configured), [bundle]) == explicit
    del env["OAI_QUARTO"]
    assert find_quarto(env, str(configured), [bundle]) == configured
    assert find_quarto(env, None, [bundle]) == on_path
    assert find_quarto({"PATH": str(tmp_path)}, None, [bundle]) == bundle
    with pytest.raises(ReportError, match="install it.*OAI_QUARTO"):
        find_quarto({"PATH": str(tmp_path)}, None, [tmp_path / "nope"])


def test_find_quarto_rejects_a_bad_explicit_path(tmp_path):
    with pytest.raises(ReportError, match="OAI_QUARTO=.*not an executable"):
        find_quarto({"OAI_QUARTO": str(tmp_path / "missing")}, None, [])
    with pytest.raises(ReportError, match="\\[tools\\] quarto=.*not an executable"):
        find_quarto({"PATH": ""}, str(tmp_path / "missing"), [])


def test_cli_report(tmp_path, monkeypatch):
    make_toy(tmp_path)
    monkeypatch.setenv("OAI_ANALYSES_DIR", str(tmp_path / "analyses"))
    monkeypatch.setenv("OAI_QUARTO", str(fake_quarto(tmp_path)))
    oai_config.get_settings.cache_clear()
    missing = CliRunner().invoke(app, ["report", "toy"])
    assert missing.exit_code == 1 and "--run" in missing.output
    result = CliRunner().invoke(app, ["report", "toy", "--run"])
    assert result.exit_code == 0, result.output
    assert "Report:" in result.output and "report.pdf" in result.output
    assert "oai check-egress" in result.output


def _report_tools_ready() -> bool:
    try:
        find_quarto(os.environ)
    except ReportError:
        return False
    if shutil.which("Rscript") is None:
        return False
    probe = subprocess.run(
        ["Rscript", "-e", "library(knitr); library(ggplot2); library(tinytable)"],
        cwd=REPO / "r",
        capture_output=True,
        env={**os.environ, "RENV_PROFILE": "report"},
    )
    return probe.returncode == 0


SMOKE_QMD = textwrap.dedent(
    """\
    ---
    format:
      typst:
        papersize: us-letter
    execute:
      echo: false
    knitr:
      opts_chunk:
        dev: cairo_pdf
    ---

    ```{r}
    p <- ggplot2::ggplot(data.frame(x = 1:3, y = 1:3), ggplot2::aes(x, y)) +
      ggplot2::geom_point() + oaireport::theme_oai()
    oaireport::save_figure(p, "smoke", "1col")
    p
    ```

    ```{r}
    oaireport::compare_table(data.frame(metric = "m", verdict = "replicated"))
    ```
    """
)


@pytest.mark.skipif(
    not _report_tools_ready(), reason="Quarto or the r/ report profile is unavailable"
)
def test_real_quarto_renders_with_oaireport(tmp_path):
    analysis = make_toy(
        tmp_path, MANIFEST.replace('runs = ["default", "alt"]', 'runs = ["default"]'), SMOKE_QMD
    )
    settings = make_settings(tmp_path, repo_root=REPO)
    pdf = render_report(analysis, settings, run_missing=True, base_env=dict(os.environ), echo=quiet)
    assert pdf.stat().st_size > 5_000
    assert sorted(p.name for p in pdf.parent.iterdir()) == ["figures", "report.pdf"]
    assert {p.name for p in (pdf.parent / "figures").iterdir()} == {"smoke.pdf", "smoke.png"}
