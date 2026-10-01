"""Run models.R through the runner on a simulated frame (skipped without R + geepack)."""

import random
import shutil
import subprocess
from pathlib import Path

import polars as pl
import pytest

from oai.config import load_settings
from oai.manifest import load_analysis
from oai.runner import run_analysis

REPO = Path(__file__).resolve().parents[1]
ANALYSIS = REPO / "analyses" / "lo2022_walking"


def _r_ready() -> bool:
    if shutil.which("Rscript") is None:
        return False
    probe = subprocess.run(
        ["Rscript", "-e", "library(geepack); library(nanoparquet); library(jsonlite)"],
        cwd=REPO / "r",
        capture_output=True,
    )
    return probe.returncode == 0


pytestmark = pytest.mark.skipif(not _r_ready(), reason="R with geepack in r/ is unavailable")


def simulated_frame() -> pl.DataFrame:
    rng = random.Random(1)
    rows = []
    for i in range(400):
        walker = i % 2 == 0
        age, sex = 50 + rng.random() * 25, 1 + (i % 3 == 0)
        for side in ("R", "L"):
            kl0 = rng.choice([2.0, 3.0, 4.0])
            pain0 = rng.random() < 0.4
            rows.append(
                {
                    "ID": 1000001 + i,
                    "SIDE": side,
                    "walker": walker,
                    "age": age,
                    "sex": sex,
                    "kl0": kl0,
                    "bmi": 22 + rng.random() * 15,
                    "kl_worse": rng.random() < (0.12 if walker else 0.35),
                    "jsn_worse": rng.random() < 0.25,
                    "new_pain": None if pain0 else rng.random() < 0.3,
                    "improved_pain": (rng.random() < 0.4) if pain0 else None,
                }
            )
    return pl.DataFrame(rows)


def test_models_write_table2_and_metrics(tmp_path):
    frames = tmp_path / "work" / "lo2022_walking" / "default"
    frames.mkdir(parents=True)
    simulated_frame().write_parquet(frames / "frame.parquet")
    settings = load_settings(
        env={"OAI_WORK_DIR": str(tmp_path / "work"), "OAI_RESULTS_DIR": str(tmp_path / "results")},
        repo_root=REPO,
    )
    run_analysis(load_analysis(ANALYSIS), settings, step_id="models", echo=lambda _: None)
    out = tmp_path / "results" / "lo2022_walking" / "default"
    table2 = pl.read_csv(out / "table2.csv")
    assert table2.height == 8  # 4 outcomes x (unadjusted, adjusted)
    m = dict(pl.read_csv(out / "metrics_models.csv").iter_rows())
    for outcome in ("new_pain", "kl_worse", "jsn_worse", "improved_pain"):
        for key in ("or_unadj", "or_adj"):
            assert (
                m[f"t2.{outcome}.{key}.lo"]
                <= m[f"t2.{outcome}.{key}"]
                <= m[f"t2.{outcome}.{key}.hi"]
            )
    assert m["t2.kl_worse.or_unadj.hi"] < 1  # strongly protective by construction
    assert m["t2.kl_worse.walkers.n"] + m["t2.kl_worse.nonwalkers.n"] == 800


def test_models_accept_extra_covariates(tmp_path):
    frames = tmp_path / "work" / "lo2022_walking"
    settings = load_settings(
        env={"OAI_WORK_DIR": str(tmp_path / "work"), "OAI_RESULTS_DIR": str(tmp_path / "results")},
        repo_root=REPO,
    )
    overrides = {"model.covariates": ["age", "sex", "kl0", "bmi"]}
    label = load_analysis(ANALYSIS)
    from oai.runner import resolve_assumptions

    run_label = resolve_assumptions(label, None, overrides).label
    (frames / run_label).mkdir(parents=True)
    simulated_frame().write_parquet(frames / run_label / "frame.parquet")
    run_analysis(label, settings, step_id="models", overrides=overrides, echo=lambda _: None)
    table2 = pl.read_csv(tmp_path / "results" / "lo2022_walking" / run_label / "table2.csv")
    assert table2.height == 8
