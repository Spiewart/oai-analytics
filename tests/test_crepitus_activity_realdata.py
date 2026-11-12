"""crepitus_activity on the real release with the Northwestern steps: runs, egress is clean."""

import shutil
import subprocess
from pathlib import Path

import pytest

from oai.config import ConfigError, get_settings
from oai.export.egress import check_egress
from oai.manifest import find_analysis
from oai.runner import run_analysis

REPO = Path(__file__).resolve().parents[1]


def _r_ready() -> bool:
    return (
        shutil.which("Rscript") is not None
        and subprocess.run(
            ["Rscript", "-e", "library(geepack); library(MASS)"],
            cwd=REPO / "r",
            capture_output=True,
        ).returncode
        == 0
    )


@pytest.mark.realdata
@pytest.mark.skipif(not _r_ready(), reason="R with geepack and MASS in r/ is unavailable")
def test_crepitus_activity_runs_end_to_end():
    settings = get_settings()
    try:
        _ = settings.steps_dir
    except ConfigError:
        pytest.skip("OAI_STEPS_DIR is not configured")
    run_analysis(
        find_analysis("crepitus_activity", settings.analyses_dir), settings, echo=lambda _: None
    )
    out = settings.results_dir / "crepitus_activity" / "default"
    for table in ("a1", "a2", "a3", "b1", "b2", "b3"):
        assert (out / f"table_{table}.csv").is_file(), table
    egress = settings.project["egress"]
    report = check_egress(
        out,
        min_cell=egress["min_cell"],
        small_cell=egress["small_cell"],
        ignore_id_pattern_columns=egress["ignore_id_pattern_columns"],
    )
    assert report.ok, report.problems
