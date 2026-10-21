"""Lo 2018 replication: cohort metrics graded against the paper.

The symptomatic-OA status, cohort flow, observation periods and four-year frame live in
`oai.derive.incident_soa` (shared with analyses/exam_crepitus_soa); they are re-exported here.
"""

from __future__ import annotations

import polars as pl

from oai.derive.incident_soa import (  # noqa: F401  (re-exported for build_frame.py and tests)
    COVARIATES,
    EXPOSURE_VISITS,
    OUTCOME_VISITS,
    PERIODS,
    ROA_KL,
    SUBGROUPS,
    VISITS,
    Cohort,
    _people,
    build_cohort,
    crepitus_frame,
    four_year,
    periods,
    soa_status,
)

LEVELS = ("never", "rarely", "sometimes", "often", "always")


def _spearman(df: pl.DataFrame, x: str, y: str) -> float | None:
    d = df.drop_nulls([x, y])
    return d.select(pl.corr(x, y, method="spearman")).item() if d.height > 2 else None


def cohort_metrics(
    cohort: Cohort, frame: pl.DataFrame, counts: dict[str, int], persons: pl.DataFrame
) -> pl.DataFrame:
    """metric, value for every flow.*, obs.*, d.* and r.* key in published.toml."""
    flow = dict(zip(cohort.flow["step"], cohort.flow["excluded"], strict=True))
    m: dict[str, float | None] = {"flow.all.persons": cohort.flow["persons"][0]}
    for step in ("arthroplasty", "no_baseline_kl", "baseline_soa", "no_outcome"):
        m[f"flow.{step}.excluded"] = flow[step]
    m["flow.persons"] = cohort.people.height
    m |= {f"obs.{k}": v for k, v in counts.items()}
    m["obs.n"] = frame.height
    m["obs.cases"] = int(frame["event"].sum())
    for p in range(1, 5):
        m[f"obs.cases.p{p}"] = int(frame.filter(pl.col("period") == p)["event"].sum())
    m["d.age_mean"] = cohort.people["age"].mean()
    m["d.bmi_mean"] = cohort.people["bmi"].mean()
    m["d.male"] = cohort.people.filter(pl.col("sex") == 1).height
    for code, level in enumerate(LEVELS):
        m[f"d.obs.{level}"] = frame.filter(pl.col("crep") == code).height
        m[f"d.base.{level}"] = persons.filter(pl.col("crep0") == code).height
    m["r.womac"] = _spearman(persons, "crep0", "womac0")
    m["r.kl"] = _spearman(persons, "crep0", "kl0")
    for sub in SUBGROUPS:
        m[f"r.womac.{sub}"] = _spearman(
            persons.filter(pl.col("subgroup") == sub), "crep0", "womac0"
        )
    return pl.DataFrame(
        {"metric": list(m), "value": [None if v is None else float(v) for v in m.values()]},
        schema={"metric": pl.String, "value": pl.Float64},
    )
