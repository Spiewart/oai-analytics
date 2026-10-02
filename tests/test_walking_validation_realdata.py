"""End-to-end walking_validation on the real release (short bias-analysis settings).

One run is shared by the tests in this module: it is made in throwaway work and results folders
(never the developer's own) and takes a few minutes.
"""

import dataclasses
import os
import shutil
import subprocess
from pathlib import Path

import polars as pl
import pytest

from oai.config import ConfigError, Settings, load_settings
from oai.export.egress import check_egress
from oai.manifest import Analysis, find_analysis
from oai.report import ReportError, find_quarto, render_report
from oai.runner import resolve_assumptions, run_analysis, run_results_dir

REPO = Path(__file__).resolve().parents[1]
FAST = {
    "bias.iterations": 40,
    "bias.tipping_iterations": 4,
    "bias.tipping_step": 0.2,
    "validity.bootstrap_reps": 50,
    "validity.jt_permutations": 99,
}


def _ready() -> bool:
    if shutil.which("Rscript") is None:
        return False
    probe = subprocess.run(
        ["Rscript", "-e", "library(quantreg); library(geepack); library(ggplot2)"],
        cwd=REPO / "r",
        capture_output=True,
        env={**os.environ, "RENV_PROFILE": "report"},
    )
    return probe.returncode == 0


@dataclasses.dataclass(frozen=True)
class FastRun:
    settings: Settings  # work and results folders of this module's run
    analysis: Analysis
    out: Path  # the run's results folder


@pytest.fixture(scope="module")
def fast_run(tmp_path_factory) -> FastRun:
    """walking_validation with short bias-analysis settings, after its lo2022_walking run.

    Skips only when no release is configured (as conftest does). With real data configured, a
    run that cannot be made fails the tests rather than skipping them. This fixture is set up
    before the autouse fixture that points OAI_* at throwaway folders, so it builds its own
    folders and environment.
    """
    try:
        real = load_settings()
        data_dir = real.data_dir
    except ConfigError:
        pytest.skip("OAI_DATA_DIR is not configured (env or .env)")
    if not _ready():
        pytest.fail("the R report profile with quantreg, geepack and ggplot2 is unavailable")
    root = tmp_path_factory.mktemp("walking_validation")
    paths = {
        **real.paths,
        "OAI_DATA_DIR": data_dir,
        "OAI_WORK_DIR": root / "work",
        "OAI_RESULTS_DIR": root / "results",
    }
    settings = dataclasses.replace(real, paths=paths)
    env = {**os.environ, **{key: str(path) for key, path in paths.items()}, "OAI_FRAME_DIR": ""}
    quiet = lambda _: None  # noqa: E731
    run_analysis(
        find_analysis("lo2022_walking", settings.analyses_dir),
        settings,
        variant="walker_requires_amount",
        base_env=env,
        echo=quiet,
    )
    analysis = find_analysis("walking_validation", settings.analyses_dir)
    run_analysis(analysis, settings, overrides=FAST, base_env=env, echo=quiet)
    # this run's own folder: the label the runner derives from these overrides
    out = run_results_dir(analysis, settings, resolve_assumptions(analysis, None, FAST).label)
    return FastRun(settings, analysis, out)


@pytest.mark.realdata
def test_walking_validation_end_to_end(fast_run):
    out, settings = fast_run.out, fast_run.settings
    comparison = pl.read_csv(out / "comparison.csv")
    device = comparison.filter(pl.col("metric").str.starts_with("device."))
    assert device.height == 10, device  # 2 waves x (valid persons, matched, wear, MV, bout)
    assert (device["verdict"] == "replicated").all(), device
    # R writes NA unquoted, so polars needs null_values or it reads the columns as strings
    pba = pl.read_csv(out / "bias_pba.csv", null_values=["NA"])
    assert pba.height == 4 * 2 * 2
    assert (pba["n"] == 40).all()
    assert pba["discarded"].is_between(0, 1).all()
    assert (pba["flagged"] == (pba["discarded"] > 0.10)).all()
    assert pba.filter(pl.col("discarded") < 1)["or"].is_not_null().all(), pba
    # perfect classification (Se = Sp = 1) reproduces the observed adjusted odds ratio
    tipping = pl.read_csv(out / "bias_tipping.csv", null_values=["NA"])
    identity = tipping.filter((pl.col("se") == 1) & (pl.col("sp") == 1)).join(
        pba.filter(pl.col("model") == "or_adj").select("outcome", "observed_or").unique(),
        on="outcome",
        validate="1:1",
    )
    assert identity.height == 4, identity
    # a discarded cell has a null odds ratio, which the comparison below would let through
    assert identity["or"].is_not_null().all(), f"cells at Se = Sp = 1 were discarded:\n{identity}"
    assert ((identity["or"] - identity["observed_or"]).abs() < 1e-8).all(), identity
    egress = settings.project["egress"]
    report = check_egress(
        out,
        min_cell=egress["min_cell"],
        small_cell=egress["small_cell"],
        ignore_id_pattern_columns=egress["ignore_id_pattern_columns"],
    )
    assert report.ok, report.problems


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


@pytest.mark.realdata
@pytest.mark.skipif(
    not _report_tools_ready(), reason="Quarto or the r/ report profile is unavailable"
)
def test_walking_validation_report_renders(fast_run):
    # The report reads the "default" run. This module's run (short bias settings, same code and
    # data) stands in for it, copied into its own folder, so nothing depends on an earlier manual
    # run and rendering never replaces the developer's report.
    settings, analysis = fast_run.settings, fast_run.analysis
    shutil.copytree(fast_run.out, run_results_dir(analysis, settings, "default"))
    pdf = render_report(analysis, settings, echo=lambda _: None)
    assert pdf.stat().st_size > 50_000
    figures = {p.name for p in (pdf.parent / "figures").iterdir()}
    for name in ("known_groups", "strata", "tipping", "forest_bias"):
        assert {f"{name}.pdf", f"{name}.png"} <= figures, name
    egress = settings.project["egress"]
    report = check_egress(
        pdf.parent,
        min_cell=egress["min_cell"],
        small_cell=egress["small_cell"],
        ignore_id_pattern_columns=egress["ignore_id_pattern_columns"],
    )
    assert report.ok, report.problems
