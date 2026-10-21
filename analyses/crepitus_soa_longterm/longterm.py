"""Crepitus -> incident symptomatic OA beyond 48 months: frames for S2 and exam, and coverage.

Three frames per measure (the cohort, outcome and periods are oai.derive.incident_soa's, with
the schedule to `periods.horizon` and ROA by visit from OUTCOMES99):
  periods     the measure at each period's start visit (time-varying), for one-period GEE (L1)
  hazard      the baseline measure on every at-risk period, a discrete-time hazard (L2)
  by_horizon  one row per person whose outcome at the horizon is known or who became a case
              earlier (L3, like Lo 2018's four-year table)
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from oai.assumptions import Resolved
from oai.derive import incident_soa as isoa
from oai.derive.knee import xray_readings

MEASURES = {"koos_s2": ("crep", "crep0"), "exam_crepitus": ("exam", "exam0")}
RECODE_PROJECT = {42: 37}  # kXR_SQ_BU_Descrip.pdf: READPRJ 42 participants belong to Project 37


@dataclass(frozen=True)
class Base:
    soa: pl.DataFrame
    cohort: isoa.Cohort
    crepitus: pl.DataFrame


def build(A: Resolved) -> Base:
    soa = isoa.soa_status(A)
    return Base(soa=soa, cohort=isoa.build_cohort(A, soa), crepitus=isoa.crepitus_frame(A))


def frames_for(
    A: Resolved, measure: str, base: Base
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame, dict[str, int]]:
    """(periods, hazard, by_horizon, counts) for `measure` ("koos_s2" or "exam_crepitus")."""
    _, baseline_col = MEASURES[measure]
    periods, counts = isoa.periods(A, base.cohort, base.soa, base.crepitus, require=(measure,))
    persons = isoa.four_year(base.cohort, base.soa, base.crepitus, require=(measure,))
    every, _ = isoa.periods(A, base.cohort, base.soa, base.crepitus, require=())
    hazard = every.drop("crep", "exam").join(
        persons.select("ID", "crep0", "exam0"), on="ID", how="inner"
    )
    horizon = isoa.outcome_visits(A)[-1]
    known = base.soa.filter((pl.col("visit") == horizon) & pl.col("soa").is_not_null()).select("ID")
    by_horizon = persons.filter(pl.col("event") | pl.col("ID").is_in(known["ID"].implode()))
    assert baseline_col in hazard.columns
    return periods, hazard, by_horizon, counts


def _project_reads(A: Resolved, project: int) -> pl.DataFrame:
    """ID of every participant whose cohort-side knee has any reading in `project`."""
    visits = ["00", "06", "08", "10", "12"]
    reads = [
        xray_readings([v], project=p)
        for v in visits
        for p in (project, *[k for k, t in RECODE_PROJECT.items() if t == project])
    ]
    return pl.concat(reads).filter(pl.col("SIDE") == A["cohort.side"]).select("ID").unique()


def coverage(A: Resolved, base: Base) -> pl.DataFrame:
    """metric, value: outcomes observed per visit, Projects 37/43 reads by subgroup, and knees
    whose ROA at 48 months differs between Project 15 and OUTCOMES99."""
    people = base.cohort.people.select("ID", "subgroup")
    m: dict[str, float] = {}
    in_cohort = base.soa.join(people, on="ID", how="semi")
    for visit in isoa.outcome_visits(A):
        seen = in_cohort.filter((pl.col("visit") == visit) & pl.col("soa").is_not_null())
        m[f"cov.outcome_at.{visit}"] = seen["ID"].n_unique()
    for project in (37, 43):
        read = people.join(_project_reads(A, project), on="ID", how="semi")
        for sub in isoa.SUBGROUPS:
            m[f"cov.p{project}.{sub}"] = read.filter(pl.col("subgroup") == sub).height
    at48 = in_cohort.filter(pl.col("visit") == "06")
    p15 = pl.col("kl") >= isoa.ROA_KL
    both = at48.filter(pl.col("kl").is_not_null() & pl.col("roa").is_not_null())
    m["cov.roa48.compared"] = both.height
    m["cov.roa48.disagree"] = both.filter(p15 != pl.col("roa")).height
    m["cov.roa48.p15_only"] = both.filter(p15 & ~pl.col("roa")).height
    m["cov.roa48.outcomes99_only"] = both.filter(~p15 & pl.col("roa")).height
    return pl.DataFrame(
        {"metric": list(m), "value": [float(v) for v in m.values()]},
        schema={"metric": pl.String, "value": pl.Float64},
    )


def cohort_metrics(base: Base, frames: dict[str, tuple]) -> pl.DataFrame:
    """metric, value: the flow and, per measure, observation and case counts in each frame."""
    flow = dict(zip(base.cohort.flow["step"], base.cohort.flow["excluded"], strict=True))
    m: dict[str, float] = {"flow.all.persons": base.cohort.flow["persons"][0]}
    for step in ("arthroplasty", "no_baseline_kl", "baseline_soa", "no_outcome"):
        m[f"flow.{step}.excluded"] = flow[step]
    m["flow.persons"] = base.cohort.people.height
    for short, (periods, hazard, horizon, counts) in frames.items():
        m |= {f"{short}.obs.{k}": v for k, v in counts.items()}
        for name, frame in (("obs", periods), ("hazard", hazard), ("horizon", horizon)):
            m[f"{short}.{name}.n"] = frame.height
            m[f"{short}.{name}.cases"] = int(frame["event"].sum())
    return pl.DataFrame(
        {"metric": list(m), "value": [float(v) for v in m.values()]},
        schema={"metric": pl.String, "value": pl.Float64},
    )
