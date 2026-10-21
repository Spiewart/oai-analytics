"""crepitus_soa_longterm on the real release: runs, egress is clean, and its 48-month settings
reproduce lo2018_crepitus (S2) and exam_crepitus_soa (exam crepitus)."""

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
LEVELS = ("rarely", "sometimes", "often", "always")


def _r_ready() -> bool:
    return (
        shutil.which("Rscript") is not None
        and subprocess.run(
            ["Rscript", "-e", "library(geepack)"], cwd=REPO / "r", capture_output=True
        ).returncode
        == 0
    )


def metrics(out: Path, name: str) -> dict[str, float]:
    return dict(pl.read_csv(out / name, null_values=["NA"]).iter_rows())


def run(name: str, variant=None, steps=None):
    settings = get_settings()
    analysis = find_analysis(name, settings.analyses_dir)
    for step in steps or [None]:
        run_analysis(analysis, settings, step_id=step, variant=variant, echo=lambda _: None)
    return settings.results_dir / name / (variant or "default")


pytestmark = [
    pytest.mark.realdata,
    pytest.mark.skipif(not _r_ready(), reason="R with geepack in r/ is unavailable"),
]


def test_longterm_runs_and_egress_is_clean():
    out = run("crepitus_soa_longterm")
    for table in ("l1", "l2", "l3", "l4"):
        assert (out / f"table_{table}.csv").is_file(), table
    assert (out / "coverage.csv").is_file()
    egress = get_settings().project["egress"]
    report = check_egress(
        out,
        min_cell=egress["min_cell"],
        small_cell=egress["small_cell"],
        ignore_id_pattern_columns=egress["ignore_id_pattern_columns"],
    )
    assert report.ok, report.problems


def test_48_month_settings_reproduce_existing_analyses():
    ours = run("crepitus_soa_longterm", variant="lo2018_48m")
    exam = run("exam_crepitus_soa", steps=["cohort", "anchor", "models"])
    lo = run("lo2018_crepitus", steps=["cohort", "models"])
    m, e, s = (
        metrics(ours, "metrics_models.csv"),
        metrics(exam, "metrics_models.csv"),
        metrics(lo, "metrics_models.csv"),
    )
    for model in ("or_unadj", "or_adj", "or_adj_s2"):
        assert m[f"l1.exam.all.exam.{model}"] == pytest.approx(e[f"e1.exam.{model}"], abs=1e-9), (
            model
        )
    for level in LEVELS:
        assert m[f"l1.s2.all.{level}.or_adj"] == pytest.approx(s[f"t1.{level}.or_adj"], abs=1e-9), (
            level
        )
        # lo2018's models drop rows missing any covariate even for the unadjusted model
        assert m[f"l1.s2.all.{level}.or_unadj"] == pytest.approx(
            s[f"t1.{level}.or_unadj"], abs=0.01
        ), level
    c, ce, cl = (
        metrics(ours, "metrics_cohort.csv"),
        metrics(exam, "metrics_cohort.csv"),
        metrics(lo, "metrics_cohort.csv"),
    )
    assert c["exam.obs.n"] == ce["obs.n"] and c["s2.obs.n"] == cl["obs.n"]
