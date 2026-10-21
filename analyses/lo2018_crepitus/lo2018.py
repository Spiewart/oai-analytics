"""Lo 2018 replication: right-knee symptomatic OA status, cohort flow and observation periods.

Lo GH et al., Arthritis Care Res 2018;70:53-60 (PMC5671376). Person-based, one knee
(`cohort.side`): KOOS S2 at an exposure visit predicts incident symptomatic OA (SOA:
frequent pain and KL >= 2; a knee replacement counts as SOA) at the next annual visit.
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from oai.assumptions import Resolved
from oai.derive.crepitus import crepitus_values
from oai.derive.knee import (
    find_col,
    frequent_knee_pain,
    knee_replacement,
    visit_days,
    xray_readings,
)
from oai.loader import read_table
from oai.visits import DAYS_PER_YEAR, nominal_month

EXPOSURE_VISITS = ("00", "01", "03", "05")
OUTCOME_VISITS = ("01", "03", "05", "06")
VISITS = ("00", *OUTCOME_VISITS)
LEVELS = ("never", "rarely", "sometimes", "often", "always")
SUBGROUPS = ("roa_nosx", "noroa_sx", "noroa_nosx")
ROA_KL = 2
DAYS_PER_MONTH = DAYS_PER_YEAR / 12


@dataclass(frozen=True)
class Cohort:
    people: pl.DataFrame  # ID, age, sex, bmi, kl0, sx0, womac0, subgroup
    flow: pl.DataFrame  # step, persons, excluded


def _select(df: pl.DataFrame, **columns: str) -> pl.DataFrame:
    return df.select([pl.col(find_col(df, src)).alias(dst) for dst, src in columns.items()])


def _replacements(A: Resolved, scope: str) -> pl.DataFrame:
    """ID, replaced_at_baseline, replaced_days for the knee(s) `scope` names ("right" = the cohort side)."""
    rep = knee_replacement()
    if scope == "either":
        return rep.group_by("ID").agg(
            pl.col("replaced_at_baseline").any(), pl.col("replaced_days").min()
        )
    return rep.filter(pl.col("SIDE") == A["cohort.side"]).select(
        "ID", "replaced_at_baseline", "replaced_days"
    )


def _replaced_by_visit(A: Resolved) -> pl.DataFrame:
    """ID, visit, replaced: replaced at baseline, or on or before that visit's day count."""
    rep = _replacements(A, A["outcomes.arthroplasty_scope"])
    frames = [
        rep.select(
            "ID", pl.lit("00").alias("visit"), pl.col("replaced_at_baseline").alias("replaced")
        )
    ]
    for visit in OUTCOME_VISITS:
        nominal = nominal_month(visit) * DAYS_PER_MONTH
        days = visit_days(visit).select("ID", pl.col("days").alias("visit_day"))
        frames.append(
            rep.join(days, on="ID", how="left").select(
                "ID",
                pl.lit(visit).alias("visit"),
                (
                    pl.col("replaced_at_baseline")
                    | (pl.col("replaced_days") <= pl.col("visit_day").fill_null(nominal))
                )
                .fill_null(False)
                .alias("replaced"),
            )
        )
    return pl.concat(frames)


def soa_status(A: Resolved) -> pl.DataFrame:
    """ID, visit, kl, sx, roa, replaced, soa for the cohort side at V00 and every outcome visit.

    `soa` is True when the knee is replaced (`outcomes.arthroplasty_scope`); otherwise frequent
    pain and ROA. With `outcomes.soa_missing = "both_required"` a missing component leaves it
    null; with `"known_false"` a known absence of either component makes it False.
    """
    side, project = A["cohort.side"], A["cohort.reading_project"]
    enrollees = read_table("enrollees", None)
    ids = enrollees.select(pl.col(find_col(enrollees, "ID")).cast(pl.Int64).alias("ID"))
    grid = ids.join(pl.DataFrame({"visit": list(VISITS)}), how="cross")
    kl = (
        xray_readings(list(VISITS), project=project)
        .filter(pl.col("SIDE") == side)
        .select("ID", "visit", pl.col("KL").alias("kl"))
    )
    pain = (
        pl.concat(
            [frequent_knee_pain("00", A["outcomes.pain_baseline_item"])]
            + [frequent_knee_pain(v, A["outcomes.pain_followup_item"]) for v in OUTCOME_VISITS]
        )
        .filter(pl.col("SIDE") == side)
        .select("ID", "visit", pl.col("frequent_pain").alias("sx"))
    )
    df = (
        grid.join(kl, on=["ID", "visit"], how="left")
        .join(pain, on=["ID", "visit"], how="left")
        .join(_replaced_by_visit(A), on=["ID", "visit"], how="left")
        .with_columns(pl.col("replaced").fill_null(False))
        .sort("ID", "visit")
    )
    roa_now = pl.col("kl") >= ROA_KL
    if A["outcomes.roa_rule"] == "ever":
        seen = roa_now.fill_null(False).cast(pl.Int8).cum_max().over("ID") == 1
        roa = pl.when(seen).then(True).otherwise(roa_now)
    else:
        roa = roa_now
    df = df.with_columns(roa.alias("roa"))
    both = pl.col("sx") & pl.col("roa")
    if A["outcomes.soa_missing"] == "both_required":
        both = pl.when(pl.col("sx").is_null() | pl.col("roa").is_null()).then(None).otherwise(both)
    return df.with_columns(pl.when(pl.col("replaced")).then(True).otherwise(both).alias("soa"))


def _people(A: Resolved) -> pl.DataFrame:
    """ID, sex, age, bmi, womac0 (baseline WOMAC pain of the cohort side)."""
    enrollees = _select(read_table("enrollees", None), ID="ID", sex="P02SEX")
    baseline = _select(
        read_table("allclinical", "00"),
        ID="ID",
        age="V00AGE",
        bmi="P01BMI",
        womac0=f"V00WOMKP{A['cohort.side']}",
    )
    return enrollees.join(baseline, on="ID", how="left").with_columns(
        pl.col("ID").cast(pl.Int64), pl.col("age", "bmi", "womac0").cast(pl.Float64)
    )


def _flow_row(step: str, before: pl.DataFrame, after: pl.DataFrame) -> dict:
    return {"step": step, "persons": after.height, "excluded": before.height - after.height}


def build_cohort(A: Resolved, soa: pl.DataFrame) -> Cohort:
    """The paper's flow: arthroplasty at enrollment, no baseline KL, baseline SOA, no outcome."""
    people = _people(A)
    rows = [{"step": "all", "persons": people.height, "excluded": 0}]

    replaced0 = _replacements(A, A["cohort.arthroplasty_scope"]).filter(
        pl.col("replaced_at_baseline")
    )
    kept = people.join(replaced0.select("ID"), on="ID", how="anti")
    rows.append(_flow_row("arthroplasty", people, kept))

    base = soa.filter(pl.col("visit") == "00").select(
        "ID", pl.col("kl").alias("kl0"), pl.col("sx").alias("sx0"), pl.col("soa").alias("soa0")
    )
    before, kept = kept, kept.join(base, on="ID", how="left").filter(pl.col("kl0").is_not_null())
    rows.append(_flow_row("no_baseline_kl", before, kept))

    before = kept
    if A["cohort.missing_baseline_pain"] == "exclude":
        kept = kept.filter(pl.col("sx0").is_not_null())
    kept = (
        kept.with_columns(pl.col("sx0").fill_null(False))
        .filter(~(((pl.col("kl0") >= ROA_KL) & pl.col("sx0")) | pl.col("soa0").fill_null(False)))
        .drop("soa0")
    )
    rows.append(_flow_row("baseline_soa", before, kept))

    known = (
        soa.filter(pl.col("visit").is_in(OUTCOME_VISITS) & pl.col("soa").is_not_null())
        .select("ID")
        .unique()
    )
    before, kept = kept, kept.join(known, on="ID", how="semi")
    rows.append(_flow_row("no_outcome", before, kept))

    roa0 = pl.col("kl0") >= ROA_KL
    subgroup = (
        pl.when(roa0 & ~pl.col("sx0"))
        .then(pl.lit("roa_nosx"))
        .when(~roa0 & pl.col("sx0"))
        .then(pl.lit("noroa_sx"))
        .otherwise(pl.lit("noroa_nosx"))
    )
    return Cohort(
        people=kept.with_columns(subgroup.alias("subgroup")).sort("ID"),
        flow=pl.DataFrame(rows),
    )


# ---------------------------------------------------------------- observation periods

PERIODS = pl.DataFrame(
    {
        "period": [1, 2, 3, 4],
        "start_visit": list(EXPOSURE_VISITS),
        "end_visit": list(OUTCOME_VISITS),
    },
    schema={"period": pl.Int64, "start_visit": pl.String, "end_visit": pl.String},
)
COVARIATES = ("age", "sex", "bmi", "subgroup")


def crepitus_frame(A: Resolved) -> pl.DataFrame:
    """ID, SIDE, visit, koos_s2, exam_crepitus for the cohort side at every exposure visit."""
    side = A["cohort.side"]
    return pl.concat(
        [crepitus_values(v, ["koos_s2", "exam_crepitus"], sides=(side,)) for v in EXPOSURE_VISITS]
    )


def periods(
    A: Resolved, cohort: Cohort, soa: pl.DataFrame, crepitus: pl.DataFrame
) -> tuple[pl.DataFrame, dict[str, int]]:
    """Person-period observations: S2 at a period's exposure visit, SOA at its outcome visit.

    A person is at risk until an outcome visit shows SOA (then censored). Each at-risk period
    is potential; it is dropped when its outcome is missing (`missing_outcome`) or its S2 is
    (`missing_crepitus`). With `periods.after_missing_outcome = "stop"`, a missing outcome
    also ends the person's follow-up.
    """
    crep = crepitus.select(
        "ID",
        pl.col("visit").alias("start_visit"),
        pl.col("koos_s2").alias("crep"),
        pl.col("exam_crepitus").alias("exam"),
    )
    outcome = soa.select("ID", pl.col("visit").alias("end_visit"), pl.col("soa").alias("event"))
    df = (
        cohort.people.select("ID", *COVARIATES)
        .join(PERIODS, how="cross")
        .join(crep, on=["ID", "start_visit"], how="left")
        .join(outcome, on=["ID", "end_visit"], how="left")
        .sort("ID", "period")
    )
    earlier = lambda e: e.cast(pl.Int64).cum_sum().shift(1, fill_value=0).over("ID") > 0  # noqa: E731
    at_risk = ~earlier(pl.col("event").fill_null(False))
    if A["periods.after_missing_outcome"] == "stop":
        at_risk = at_risk & ~earlier(pl.col("event").is_null())
    potential = df.filter(at_risk)
    has_outcome = pl.col("event").is_not_null()
    counts = {
        "potential": potential.height,
        "missing_outcome": potential.filter(~has_outcome).height,
        "missing_crepitus": potential.filter(has_outcome & pl.col("crep").is_null()).height,
    }
    frame = potential.filter(has_outcome & pl.col("crep").is_not_null()).select(
        "ID", "period", "crep", "exam", "event", *COVARIATES
    )
    return frame, counts


def four_year(cohort: Cohort, soa: pl.DataFrame, crepitus: pl.DataFrame) -> pl.DataFrame:
    """One row per person with baseline S2: incident SOA at any outcome visit to 48 months."""
    event = (
        soa.filter(pl.col("visit").is_in(OUTCOME_VISITS))
        .group_by("ID")
        .agg(pl.col("soa").fill_null(False).any().alias("event"))
    )
    baseline = crepitus.filter(pl.col("visit") == "00").select(
        "ID", pl.col("koos_s2").alias("crep0"), pl.col("exam_crepitus").alias("exam0")
    )
    return (
        cohort.people.join(baseline, on="ID", how="inner")
        .filter(pl.col("crep0").is_not_null())
        .join(event, on="ID", how="left")
        .with_columns(pl.col("event").fill_null(False))
        .select("ID", "crep0", "exam0", "event", *COVARIATES, "kl0", "womac0")
        .sort("ID")
    )


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
