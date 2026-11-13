"""steps_oa's R helpers: the restricted cubic spline basis (analyses/steps_oa/shape.R) and the
covariate sets per model level (analyses/steps_oa/covariates.R)."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SHAPE = REPO / "analyses" / "steps_oa" / "shape.R"
COVARIATES = REPO / "analyses" / "steps_oa" / "covariates.R"

pytestmark = pytest.mark.skipif(shutil.which("Rscript") is None, reason="Rscript unavailable")


def r_json(code: str):
    out = subprocess.run(["Rscript", "-e", code], cwd=REPO / "r", capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_three_knots_give_two_columns():
    dims = r_json(
        f'source("{SHAPE}"); x <- seq(1, 15, by = 0.5); '
        "cat(jsonlite::toJSON(dim(rcs_basis(x, c(3, 7, 11)))))"
    )
    assert dims == [29, 2]


def test_first_column_is_x_and_nonlinear_column_is_zero_up_to_first_knot():
    out = r_json(
        f'source("{SHAPE}"); x <- c(0, 2, 3, 3.5, 7, 12); B <- rcs_basis(x, c(3, 7, 11)); '
        "cat(jsonlite::toJSON(list(lin = B[, 1], nl = B[, 2]), digits = NA))"
    )
    assert out["lin"] == [0, 2, 3, 3.5, 7, 12]
    assert out["nl"][:3] == [0, 0, 0]
    assert all(v > 0 for v in out["nl"][3:])


def test_nonlinear_column_is_linear_beyond_the_last_knot():
    # Restricted: the spline's second derivative is 0 past the last knot
    out = r_json(
        f'source("{SHAPE}"); B <- rcs_basis(c(12, 13, 14), c(3, 7, 11)); '
        "cat(jsonlite::toJSON(diff(diff(B[, 2])), digits = NA))"
    )
    assert abs(out[0]) < 1e-9


def test_linear_data_give_a_nonsignificant_nonlinear_term():
    p = r_json(
        f'source("{SHAPE}"); set.seed(20261112); n <- 2000; '
        "x <- runif(n, 1, 15); id <- rep(seq_len(n / 2), each = 2); "
        "y <- rbinom(n, 1, plogis(-1 + 0.15 * x)); "
        "d <- data.frame(y = y, id = id); "
        "B <- rcs_basis(x, stats::quantile(x, c(0.1, 0.5, 0.9))); d$s1 <- B[, 1]; d$s2 <- B[, 2]; "
        "fit <- geepack::geeglm(y ~ s1 + s2, id = id, data = d, family = binomial, "
        'corstr = "exchangeable"); '
        'cat(jsonlite::toJSON(summary(fit)$coefficients["s2", "Pr(>|W|)"], digits = NA))'
    )
    assert p[0] > 0.05


def covariates(model: str, waves: list[str], level: str) -> list[str]:
    return r_json(
        'pkgload::load_all("oaimodels", quiet = TRUE, export_all = FALSE); '
        f'source("{COVARIATES}"); '
        'A <- list("model.covariates" = c("age", "sex", "bmi", "wear_hr"), '
        '"model.covariates_2_knee" = c("kl48", "womac48"), '
        '"model.covariates_2_person" = c("kl_max", "womac_pain_max")); '
        f'cat(jsonlite::toJSON(covariates_for(A, "{model}", '
        f'c({", ".join(repr(w) for w in waves)}), "{level}")))'
    )


def test_model_1_is_the_same_at_both_levels_with_wear_at_each_wave():
    for level in ("knee", "person"):
        assert covariates("m1", ["48"], level) == ["age", "sex", "bmi", "wear_hr_48"]
        assert covariates("m1", ["48", "72"], level) == [
            "age", "sex", "bmi", "wear_hr_48", "wear_hr_72",
        ]  # fmt: skip


def test_model_2_adds_the_knee_or_person_set():
    assert covariates("m2", ["48"], "knee")[-2:] == ["kl48", "womac48"]
    assert covariates("m2", ["48", "72"], "person")[-2:] == ["kl_max", "womac_pain_max"]
