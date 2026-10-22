"""luyten_early_oa on the real release: every step runs, the group is graded, egress is clean."""

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
def test_luyten_early_oa_runs_end_to_end():
    settings = get_settings()
    analysis = find_analysis("luyten_early_oa", settings.analyses_dir)
    run_analysis(analysis, settings, echo=lambda _: None)
    out = settings.results_dir / "luyten_early_oa" / "default"
    for table in ("g1", "c1", "c2"):
        assert (out / f"table_{table}.csv").is_file(), table
    comparison = pl.read_csv(out / "comparison.csv")
    assert comparison.filter(pl.col("verdict") == "missing").height == 0
    egress = settings.project["egress"]
    report = check_egress(
        out,
        min_cell=egress["min_cell"],
        small_cell=egress["small_cell"],
        ignore_id_pattern_columns=egress["ignore_id_pattern_columns"],
    )
    assert report.ok, report.problems
