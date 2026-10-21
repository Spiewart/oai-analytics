"""Palpable crepitus -> incident symptomatic OA: which measures an observation needs, and the
cohort metrics. The cohort, outcome and periods are oai.derive.incident_soa's (Lo 2018 design).
"""

from __future__ import annotations

import polars as pl

from oai.assumptions import Resolved
from oai.derive.incident_soa import Cohort

FLOW_STEPS = ("arthroplasty", "no_baseline_kl", "baseline_soa", "no_outcome")


def require_for(A: Resolved) -> tuple[str, ...]:
    """The exam item, plus S2 when `exposure.require_s2` (head-to-head on the same rows)."""
    return ("exam_crepitus", "koos_s2") if A["exposure.require_s2"] else ("exam_crepitus",)


def exposure_metrics(
    cohort: Cohort, frame: pl.DataFrame, counts: dict[str, int], persons: pl.DataFrame
) -> pl.DataFrame:
    """metric, value: the Lo 2018 flow, observation counts and exam prevalence."""
    flow = dict(zip(cohort.flow["step"], cohort.flow["excluded"], strict=True))
    m: dict[str, float] = {"flow.all.persons": cohort.flow["persons"][0]}
    m |= {f"flow.{step}.excluded": flow[step] for step in FLOW_STEPS}
    m["flow.persons"] = cohort.people.height
    m |= {f"obs.{k}": v for k, v in counts.items()}
    m["obs.n"] = frame.height
    m["obs.cases"] = int(frame["event"].sum())
    for p in range(1, 5):
        m[f"obs.cases.p{p}"] = int(frame.filter(pl.col("period") == p)["event"].sum())
    for label, code in (("yes", 1), ("no", 0)):
        m[f"d.obs.{label}"] = frame.filter(pl.col("exam") == code).height
        m[f"d.base.{label}"] = persons.filter(pl.col("exam0") == code).height
    m["d.age_mean"] = cohort.people["age"].mean()
    m["d.bmi_mean"] = cohort.people["bmi"].mean()
    m["d.male"] = cohort.people.filter(pl.col("sex") == 1).height
    return pl.DataFrame(
        {"metric": list(m), "value": [float(v) for v in m.values()]},
        schema={"metric": pl.String, "value": pl.Float64},
    )
