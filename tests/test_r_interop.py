"""Python -> Parquet -> R round trips through oaimodels (skipped when r/ isn't restored)."""

import shutil
import subprocess
import textwrap
from pathlib import Path

import polars as pl
import pytest

from oai.config import load_settings
from oai.manifest import load_analysis
from oai.runner import run_analysis

REPO = Path(__file__).resolve().parents[1]
R_DIR = REPO / "r"


def _r_ready() -> bool:
    if shutil.which("Rscript") is None:
        return False
    probe = subprocess.run(
        ["Rscript", "-e", "library(nanoparquet); library(pkgload)"], cwd=R_DIR, capture_output=True
    )
    return probe.returncode == 0


pytestmark = pytest.mark.skipif(
    not _r_ready(), reason="R with the restored r/ renv library is unavailable"
)


def test_polars_frame_reads_in_r(tmp_path):
    path = tmp_path / "frame.parquet"
    pl.DataFrame(
        {"ID": [1000001, 1000002], "time_years": [0.0, 1.02], "sex": ["F", "M"], "age0": [61, None]}
    ).write_parquet(path)
    code = (
        'pkgload::load_all("oaimodels", quiet = TRUE); '
        'f <- read_frame(commandArgs(TRUE)[1], required = c("ID", "time_years")); '
        'cat(nrow(f), sum(f$ID), f$sex[2], is.na(f$age0[2]), sep = "|")'
    )
    out = subprocess.run(
        ["Rscript", "-e", code, str(path)], cwd=R_DIR, capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "2|2000003|M|TRUE"


def test_runner_r_step_sees_oaimodels(tmp_path):
    root = tmp_path / "analyses" / "rstep"
    root.mkdir(parents=True)
    (root / "analysis.toml").write_text(
        'name = "rstep"\n[[steps]]\nid = "m"\nlang = "r"\nstage = "local"\nentry = "m.R"\n'
    )
    (root / "m.R").write_text(
        textwrap.dedent(
            """
            covs <- oaimodels::default_covariates(1)
            writeLines(paste(covs, collapse = ","), file.path(Sys.getenv("OAI_RESULTS_DIR"), "covs.txt"))
            """
        )
    )
    settings = load_settings(
        env={"OAI_WORK_DIR": str(tmp_path / "work"), "OAI_RESULTS_DIR": str(tmp_path / "results")},
        repo_root=REPO,
    )
    run_analysis(load_analysis(root), settings, echo=lambda _: None)
    assert (tmp_path / "results" / "rstep" / "covs.txt").read_text().strip() == "age0,sex,bmi0,PC1"
