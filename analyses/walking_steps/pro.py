"""Self-reported walking against device walking: accuracy, AUC and rank correlation.

Each comparison pairs one self-report with one device reference over the people who have both.
Sensitivity is the share of device walkers who report walking; specificity is the share of
device non-walkers who do not.
"""

from __future__ import annotations

import math

import numpy as np
import polars as pl

Z = 1.959963984540054  # two-sided 95%


def wilson(k: int, n: int) -> tuple[float | None, float | None]:
    """Wilson score 95% interval for k of n."""
    if n == 0:
        return None, None
    p = k / n
    centre = (p + Z * Z / (2 * n)) / (1 + Z * Z / n)
    half = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / (1 + Z * Z / n)
    return centre - half, centre + half


def accuracy(pro: pl.Series, ref: pl.Series) -> dict[str, float | int | None]:
    """2x2 accuracy of `pro` (self-report) against `ref` (device); rows with a null dropped."""
    both = pl.DataFrame({"p": pro, "r": ref}).drop_nulls()
    p, r = both["p"].to_numpy().astype(bool), both["r"].to_numpy().astype(bool)
    tp, fn = int((p & r).sum()), int((~p & r).sum())
    fp, tn = int((p & ~r).sum()), int((~p & ~r).sum())
    n = tp + fn + fp + tn

    def ratio(a: int, b: int) -> float | None:
        return a / b if b else None

    se, sp = ratio(tp, tp + fn), ratio(tn, tn + fp)
    agree = ratio(tp + tn, n)
    chance = ratio((tp + fp) * (tp + fn) + (fn + tn) * (fp + tn), n * n) if n else None
    kappa = (
        (agree - chance) / (1 - chance) if agree is not None and chance not in (None, 1) else None
    )
    se_lo, se_hi = wilson(tp, tp + fn)
    sp_lo, sp_hi = wilson(tn, tn + fp)
    return {
        "n": n,
        "tp": tp,
        "fn": fn,
        "fp": fp,
        "tn": tn,
        "pro_yes_share": ratio(tp + fp, n),
        "device_walker_share": ratio(tp + fn, n),
        "sensitivity": se,
        "sensitivity_lo": se_lo,
        "sensitivity_hi": se_hi,
        "specificity": sp,
        "specificity_lo": sp_lo,
        "specificity_hi": sp_hi,
        "youden_j": se + sp - 1 if se is not None and sp is not None else None,
        "ppv": ratio(tp, tp + fp),
        "npv": ratio(tn, tn + fn),
        "agreement": agree,
        "kappa": kappa,
    }


def auc(x: np.ndarray, yes: np.ndarray) -> float | None:
    """P(a random 'yes' has a higher x than a random 'no'), ties counting half (Mann-Whitney)."""
    a, b = x[yes], x[~yes]
    if len(a) == 0 or len(b) == 0:
        return None
    ranks = pl.Series(np.r_[a, b]).rank("average").to_numpy()
    return float((ranks[: len(a)].sum() - len(a) * (len(a) + 1) / 2) / (len(a) * len(b)))


def auc_with_ci(
    measure: pl.Series, pro: pl.Series, reps: int, seed: int
) -> dict[str, float | int | None]:
    """AUC of a continuous device measure for the self-report, with a stratified bootstrap CI."""
    both = pl.DataFrame({"x": measure, "p": pro}).drop_nulls()
    x, yes = both["x"].to_numpy().astype(float), both["p"].to_numpy().astype(bool)
    est = auc(x, yes)
    out: dict[str, float | int | None] = {"n": len(x), "auc": est, "auc_lo": None, "auc_hi": None}
    if est is None or reps == 0:
        return out
    rng = np.random.default_rng(seed)
    a, b = x[yes], x[~yes]
    boots = []
    for _ in range(reps):
        ra, rb = rng.choice(a, len(a)), rng.choice(b, len(b))
        boots.append(auc(np.r_[ra, rb], np.r_[np.ones(len(ra), bool), np.zeros(len(rb), bool)]))
    out["auc_lo"], out["auc_hi"] = (float(q) for q in np.quantile(boots, [0.025, 0.975]))
    return out


def spearman(x: pl.Series, y: pl.Series) -> dict[str, float | int | None]:
    """Spearman's rho with a Fisher-z 95% CI (SE 1/sqrt(n - 3))."""
    both = pl.DataFrame({"x": x, "y": y}).drop_nulls()
    n = both.height
    if n < 4:
        return {"n": n, "rho": None, "rho_lo": None, "rho_hi": None}
    rho = both.select(pl.corr("x", "y", method="spearman")).item()
    z, half = math.atanh(rho), Z / math.sqrt(n - 3)
    return {"n": n, "rho": rho, "rho_lo": math.tanh(z - half), "rho_hi": math.tanh(z + half)}
