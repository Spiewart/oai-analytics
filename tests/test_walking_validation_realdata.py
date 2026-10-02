"""End-to-end walking_validation on the real release (short bias-analysis settings)."""

import os
import shutil
import subprocess
from pathlib import Path

import polars as pl
import pytest

from oai.config import ConfigError, get_settings, load_settings
from oai.export.egress import check_egress
from oai.manifest import find_analysis
from oai.report import ReportError, find_quarto, render_report
from oai.runner import is_finished, resolve_assumptions, run_analysis, run_results_dir

REPO = Path(__file__).resolve().parents[1]


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


@pytest.mark.realdata
@pytest.mark.skipif(not _ready(), reason="R report profile with quantreg/geepack is unavailable")
def test_walking_validation_end_to_end():
    settings = get_settings()
    quiet = lambda _: None  # noqa: E731
    run_analysis(
        find_analysis("lo2022_walking", settings.analyses_dir),
        settings,
        variant="walker_requires_amount",
        echo=quiet,
    )
    analysis = find_analysis("walking_validation", settings.analyses_dir)
    fast = {
        "bias.iterations": 40,
        "bias.tipping_iterations": 4,
        "bias.tipping_step": 0.2,
        "validity.bootstrap_reps": 50,
        "validity.jt_permutations": 99,
    }
    run_analysis(analysis, settings, overrides=fast, echo=quiet)
    # this run's own folder (the label the runner derives from these overrides), not whichever
    # earlier default+custom-* run the filesystem lists first
    out = run_results_dir(analysis, settings, resolve_assumptions(analysis, None, fast).label)
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
    assert identity["or"].is_not_null().all(), (
        identity
    )  # a discarded cell is null, and null passes .all()
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


def _existing_run() -> Path | None:
    """The developer's own finished default run, looked up at collection time, before the
    autouse fixture points OAI_RESULTS_DIR at a throwaway folder."""
    try:
        run = load_settings().results_dir / "walking_validation" / "default"
    except ConfigError:
        return None
    return run if is_finished(run) else None


EXISTING_RUN = _existing_run()


@pytest.mark.realdata
@pytest.mark.skipif(
    not _report_tools_ready(), reason="Quarto or the r/ report profile is unavailable"
)
@pytest.mark.skipif(
    EXISTING_RUN is None,
    reason="no finished walking_validation default run; `oai run walking_validation` first",
)
def test_walking_validation_report_renders():
    # Renders from the existing full run without --run (a run takes ~8 minutes). The run's
    # aggregate results are copied into this test's throwaway results folder, so rendering never
    # replaces the developer's own report.
    settings = get_settings()
    analysis = find_analysis("walking_validation", settings.analyses_dir)
    shutil.copytree(EXISTING_RUN, run_results_dir(analysis, settings, "default"))
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
