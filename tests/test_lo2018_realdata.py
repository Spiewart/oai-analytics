"""Lo 2018 replication on the real release: the steps run, every metric is graded, egress is clean."""

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
def test_replication_is_graded_end_to_end():
    settings = get_settings()
    analysis = find_analysis("lo2018_crepitus", settings.analyses_dir)
    for step in ("cohort", "models", "compare"):
        run_analysis(analysis, settings, step_id=step, echo=lambda _: None)
    out = settings.results_dir / "lo2018_crepitus" / "default"
    comparison = pl.read_csv(out / "comparison.csv")
    assert comparison.filter(pl.col("verdict") == "missing").height == 0
    baseline_soa = comparison.filter(pl.col("metric") == "flow.baseline_soa.excluded")
    assert baseline_soa["verdict"].item() == "replicated"
    egress = settings.project["egress"]
    report = check_egress(
        out,
        min_cell=egress["min_cell"],
        small_cell=egress["small_cell"],
        ignore_id_pattern_columns=egress["ignore_id_pattern_columns"],
    )
    assert report.ok, report.problems
