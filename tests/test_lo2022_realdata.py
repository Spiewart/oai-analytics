"""Full Lo 2022 replication on the real release (outputs exist; results are the finding)."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from oai.config import get_settings
from oai.export.egress import check_egress
from oai.manifest import find_analysis
from oai.report import ReportError, find_quarto, render_report
from oai.runner import run_analysis

REPO = Path(__file__).resolve().parents[1]


def _r_ready() -> bool:
    return (
        shutil.which("Rscript") is not None
        and subprocess.run(
            ["Rscript", "-e", "library(geepack)"], cwd=REPO / "r", capture_output=True
        ).returncode
        == 0
    )


@pytest.mark.realdata
@pytest.mark.skipif(not _r_ready(), reason="R with geepack in r/ is unavailable")
def test_replication_runs_end_to_end():
    settings = get_settings()
    run_analysis(
        find_analysis("lo2022_walking", settings.analyses_dir), settings, echo=lambda _: None
    )
    out = settings.results_dir / "lo2022_walking" / "default"
    for name in (
        "flow.csv",
        "table1.csv",
        "table2.csv",
        "table3.csv",
        "comparison.csv",
        "metrics_cohort.csv",
        "metrics_models.csv",
        "assumptions.resolved.json",
    ):
        assert (out / name).is_file(), name
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
        ["Rscript", "-e", "library(knitr); library(ggplot2); library(tinytable); library(geepack)"],
        cwd=REPO / "r",
        capture_output=True,
        env={**os.environ, "RENV_PROFILE": "report"},
    )
    return probe.returncode == 0


@pytest.mark.realdata
@pytest.mark.skipif(
    not _report_tools_ready(), reason="Quarto or the r/ report profile is unavailable"
)
def test_lo2022_report_renders():
    settings = get_settings()
    analysis = find_analysis("lo2022_walking", settings.analyses_dir)
    pdf = render_report(analysis, settings, run_missing=True, echo=lambda _: None)
    assert pdf.stat().st_size > 50_000
    figures = {p.name for p in (pdf.parent / "figures").iterdir()}
    for name in ("flow", "forest_table2", "forest_supp2", "forest_supp3", "replication_grid"):
        assert {f"{name}.pdf", f"{name}.png"} <= figures, name
    egress = settings.project["egress"]
    report = check_egress(
        pdf.parent,
        min_cell=egress["min_cell"],
        small_cell=egress["small_cell"],
        ignore_id_pattern_columns=egress["ignore_id_pattern_columns"],
    )
    assert report.ok, report.problems
