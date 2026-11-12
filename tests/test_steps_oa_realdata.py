"""steps_oa on the real release with the Northwestern steps: runs, tables exist, egress is clean."""

import csv
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from oai.config import ConfigError, get_settings
from oai.export.egress import check_egress
from oai.manifest import find_analysis
from oai.runner import run_analysis

REPO = Path(__file__).resolve().parents[1]
CAUSAL_WORDS = re.compile(r"protect|harm|\bbias|correct(ed|s|ion|ive|ly)?\b", re.IGNORECASE)


def _r_ready() -> bool:
    return (
        shutil.which("Rscript") is not None
        and subprocess.run(
            ["Rscript", "-e", "library(geepack); library(survival)"],
            cwd=REPO / "r",
            capture_output=True,
        ).returncode
        == 0
    )


@pytest.mark.realdata
@pytest.mark.skipif(not _r_ready(), reason="R with geepack and survival in r/ is unavailable")
def test_steps_oa_runs_end_to_end():
    settings = get_settings()
    try:
        _ = settings.steps_dir
    except ConfigError:
        pytest.skip("OAI_STEPS_DIR is not configured")
    run_analysis(find_analysis("steps_oa", settings.analyses_dir), settings, echo=lambda _: None)
    out = settings.results_dir / "steps_oa" / "default"

    for table in ("p1", "p2", "s3b", "r1"):
        path = out / f"table_{table}.csv"
        assert path.is_file(), table
        with path.open(newline="") as fh:
            assert list(csv.DictReader(fh)), f"{table} is empty"

    with (out / "flow.csv").open(newline="") as fh:
        samples = {row["sample"] for row in csv.DictReader(fh)}
    assert {"selection_incident_roa", "selection_progression"} <= samples

    egress = settings.project["egress"]
    report = check_egress(
        out,
        min_cell=egress["min_cell"],
        small_cell=egress["small_cell"],
        ignore_id_pattern_columns=egress["ignore_id_pattern_columns"],
    )
    assert report.ok, report.problems

    for path in out.iterdir():
        if path.is_file():
            assert not CAUSAL_WORDS.search(path.read_text(errors="ignore")), path.name
