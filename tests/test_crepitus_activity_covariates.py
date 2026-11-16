"""crepitus_activity's covariate sets (analyses/crepitus_activity/covariates.R): a model that
spans both device waves adjusts for wear time at both, and the sets follow the ledger."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HELPER = REPO / "analyses" / "crepitus_activity" / "covariates.R"

pytestmark = pytest.mark.skipif(shutil.which("Rscript") is None, reason="Rscript unavailable")


def covariates(model: str, waves: list[str]) -> list[str]:
    code = (
        'pkgload::load_all("oaimodels", quiet = TRUE, export_all = FALSE); '
        f'source("{HELPER}"); '
        'A <- list("model.covariates" = c("age", "sex", "bmi", "wear_hr"), '
        '"model.covariates_2" = c("kl_max", "womac_pain_max")); '
        f'cat(jsonlite::toJSON(covariates_for(A, "{model}", c({", ".join(repr(w) for w in waves)}))))'
    )
    out = subprocess.run(["Rscript", "-e", code], cwd=REPO / "r", capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_one_wave_model_adjusts_for_that_waves_wear():
    assert covariates("m1", ["48"]) == ["age", "sex", "bmi", "wear_hr_48"]
    assert covariates("m1", ["72"]) == ["age", "sex", "bmi", "wear_hr_72"]


def test_two_wave_model_adjusts_for_wear_at_both_waves():
    assert covariates("m1", ["48", "72"]) == ["age", "sex", "bmi", "wear_hr_48", "wear_hr_72"]


def test_model_2_adds_kl_and_pain():
    assert covariates("m2", ["48", "72"])[-2:] == ["kl_max", "womac_pain_max"]
