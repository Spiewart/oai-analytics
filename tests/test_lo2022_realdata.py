"""Full Lo 2022 replication on the real release (outputs exist; results are the finding)."""

import shutil
import subprocess
from pathlib import Path

import pytest

from oai.config import get_settings
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
