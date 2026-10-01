"""End-to-end walking_validation on the real release (short bias-analysis settings)."""

import os
import shutil
import subprocess
from pathlib import Path

import polars as pl
import pytest

from oai.config import get_settings
from oai.export.egress import check_egress
from oai.manifest import find_analysis
from oai.runner import run_analysis

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
    out = next((settings.results_dir / "walking_validation").glob("default+custom-*"))
    comparison = pl.read_csv(out / "comparison.csv")
    device = comparison.filter(pl.col("metric").str.starts_with("device."))
    assert (device["verdict"] == "replicated").all(), device
    pba = pl.read_csv(out / "bias_pba.csv")
    assert pba.height == 4 * 2 * 2
    assert pba["or"].is_not_null().all()
    egress = settings.project["egress"]
    report = check_egress(
        out,
        min_cell=egress["min_cell"],
        small_cell=egress["small_cell"],
        ignore_id_pattern_columns=egress["ignore_id_pattern_columns"],
    )
    assert report.ok, report.problems
