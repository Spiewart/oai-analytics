"""Incident symptomatic knee OA in person-periods, the Lo 2018 design.

Lo GH et al., Arthritis Care Res 2018;70:53-60 (PMC5671376), replicated in
analyses/lo2018_crepitus. Person-based, one knee (`cohort.side`): crepitus at an exposure
visit predicts incident symptomatic OA (SOA: frequent pain and KL >= 2; a knee replacement
counts as SOA) at the next annual visit. `require` names the crepitus measures an
observation needs (KOOS S2 in the paper; examiner crepitus in analyses/exam_crepitus_soa).

Optional settings (`periods.horizon`, `exposure.exam_after_48m`) default to the 48-month
Lo 2018 design, so analyses whose ledgers lack them behave as before.
"""

from __future__ import annotations

from collections.abc import Sequence
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

ALL_EXPOSURE_VISITS = ("00", "01", "03", "05", "06", "08", "10")
ALL_OUTCOME_VISITS = ("01", "03", "05", "06", "08", "10", "12")
EXPOSURE_VISITS = ALL_EXPOSURE_VISITS[:4]  # Lo 2018: annual visits to 48 months
OUTCOME_VISITS = ALL_OUTCOME_VISITS[:4]
VISITS = ("00", *OUTCOME_VISITS)
DEFAULT_HORIZON = "06"
READINGS_LAST_VISIT = "06"  # Project 15 reads baseline to 48 months
# V99E{R,L}XIOA / XIOAN: earliest visit with KL >= 2 (or KL >= 2 with JSN), Projects 15, 37, 43
INCIDENT_CODE_VISIT = {3: "01", 4: "03", 5: "05", 6: "06", 7: "08", 8: "10", 9: "12"}
ROA_AT_BASELINE, NO_INCIDENCE = 1, 2
ROA_COLUMN = {"kl2": "IOA", "kl2_jsn": "IOAN"}
LAST_NO_ROA_COLUMN = {"kl2": "NOA", "kl2_jsn": "NOAN"}  # coded by visit number (0, 1, 3, ... 12)
EXAM_CARRIED_FROM = "06"  # no exam at V08 or V10
SUBGROUPS = ("roa_nosx", "noroa_sx", "noroa_nosx")
ROA_KL = 2
DAYS_PER_MONTH = DAYS_PER_YEAR / 12


@dataclass(frozen=True)
class Cohort:
    people: pl.DataFrame  # ID, age, sex, bmi, kl0, sx0, womac0, subgroup
    flow: pl.DataFrame  # step, persons, excluded


def setting(A: Resolved, key: str, default):
    """An optional assumption: its value when the analysis's ledger has it, else `default`."""
    return A.values.get(key, default)


def schedule(horizon: str = DEFAULT_HORIZON) -> pl.DataFrame:
    """period, start_visit, end_visit: exposure -> outcome pairs up to the horizon visit."""
    pairs = [
        (s, e) for s, e in zip(ALL_EXPOSURE_VISITS, ALL_OUTCOME_VISITS, strict=True) if e <= horizon
    ]
    return pl.DataFrame(
        {
            "period": list(range(1, len(pairs) + 1)),
            "start_visit": [s for s, _ in pairs],
            "end_visit": [e for _, e in pairs],
        },
        schema={"period": pl.Int64, "start_visit": pl.String, "end_visit": pl.String},
    )


def horizon_of(A: Resolved) -> str:
    return setting(A, "periods.horizon", DEFAULT_HORIZON)


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


def outcome_visits(A: Resolved) -> list[str]:
    return schedule(horizon_of(A))["end_visit"].to_list()


def _replaced_by_visit(A: Resolved) -> pl.DataFrame:
    """ID, visit, replaced: replaced at baseline, or on or before that visit's day count."""
    rep = _replacements(A, A["outcomes.arthroplasty_scope"])
    frames = [
        rep.select(
            "ID", pl.lit("00").alias("visit"), pl.col("replaced_at_baseline").alias("replaced")
        )
    ]
    for visit in outcome_visits(A):
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


def roa_from_outcomes99(A: Resolved) -> pl.DataFrame:
    """ID, visit, roa for the cohort side at V00 and every outcome visit of the schedule, from
    OUTCOMES99's earliest-incidence variables (carried forward once a knee has ROA).

    "No incidence" is only known up to the knee's last reading without ROA (`V99E?XNOA`).
    After it, and between that reading and an incident visit, ROA is unknown (null) under
    `outcomes.roa_unread = "unknown"`, or taken as absent under `"no_roa"`.
    """
    side = A["cohort.side"]
    definition = setting(A, "outcomes.roa_definition", "kl2")
    unread_as_none = setting(A, "outcomes.roa_unread", "unknown") == "no_roa"
    df = read_table("outcomes", "99")
    col = lambda name: find_col(df, name, where="outcomes99")  # noqa: E731
    codes = df.select(
        pl.col(find_col(df, "ID")).cast(pl.Int64).alias("ID"),
        pl.col(col(f"V99E{side}X{ROA_COLUMN[definition]}")).cast(pl.Int64).alias("code"),
        pl.col(col(f"V99E{side}X{LAST_NO_ROA_COLUMN[definition]}")).cast(pl.Int64).alias("last_no"),
    )
    frames = []
    for visit in ("00", *outcome_visits(A)):
        incident_by = [c for c, v in INCIDENT_CODE_VISIT.items() if v <= visit]
        known = pl.col("code").is_in([ROA_AT_BASELINE, NO_INCIDENCE, *INCIDENT_CODE_VISIT])
        roa = (pl.col("code") == ROA_AT_BASELINE) | pl.col("code").is_in(incident_by)
        unread = (~roa) & pl.col("last_no").is_not_null() & (pl.col("last_no") < int(visit))
        value = pl.when(known).then(roa)
        if not unread_as_none:
            value = pl.when(known & unread).then(None).otherwise(value)
        frames.append(codes.select("ID", pl.lit(visit).alias("visit"), value.alias("roa")))
    return pl.concat(frames)


def soa_status(A: Resolved) -> pl.DataFrame:
    """ID, visit, kl, sx, roa, replaced, soa for the cohort side at V00 and every outcome visit.

    `soa` is True when the knee is replaced (`outcomes.arthroplasty_scope`); otherwise frequent
    pain and ROA. With `outcomes.soa_missing = "both_required"` a missing component leaves it
    null; with `"known_false"` a known absence of either component makes it False.

    ROA comes from Project 15 readings at the same visit (`outcomes.roa_source = "readings"`,
    48 months at most) or from OUTCOMES99 (`"outcomes99"`). `kl` is always Project 15's.
    """
    side, project = A["cohort.side"], A["cohort.reading_project"]
    source = setting(A, "outcomes.roa_source", "readings")
    visits = ["00", *outcome_visits(A)]
    if source == "readings" and visits[-1] > READINGS_LAST_VISIT:
        raise ValueError(
            f"outcomes.roa_source = 'readings' uses Project 15, which ends at V{READINGS_LAST_VISIT}; "
            f"periods.horizon V{visits[-1]} needs outcomes.roa_source = 'outcomes99'"
        )
    enrollees = read_table("enrollees", None)
    ids = enrollees.select(pl.col(find_col(enrollees, "ID")).cast(pl.Int64).alias("ID"))
    grid = ids.join(pl.DataFrame({"visit": visits}), how="cross")
    read_visits = [v for v in visits if v <= READINGS_LAST_VISIT]
    kl = (
        xray_readings(read_visits, project=project)
        .filter(pl.col("SIDE") == side)
        .select("ID", "visit", pl.col("KL").alias("kl"))
    )
    pain = (
        pl.concat(
            [frequent_knee_pain("00", A["outcomes.pain_baseline_item"])]
            + [frequent_knee_pain(v, A["outcomes.pain_followup_item"]) for v in visits[1:]]
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
    if source == "outcomes99":
        df = df.join(roa_from_outcomes99(A), on=["ID", "visit"], how="left")
    else:
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
        soa.filter((pl.col("visit") != "00") & pl.col("soa").is_not_null()).select("ID").unique()
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

PERIODS = schedule(DEFAULT_HORIZON)
COVARIATES = ("age", "sex", "bmi", "subgroup")
REQUIRE_COLUMNS = {"koos_s2": "crep", "exam_crepitus": "exam"}


def _required(require: Sequence[str], suffix: str = "") -> list[str]:
    """Frame columns for the required measures; KeyError for an unknown measure."""
    return [REQUIRE_COLUMNS[m] + suffix for m in require]


def _present(columns: Sequence[str]) -> pl.Expr:
    """True where every column is non-null (always True for no columns)."""
    return (
        pl.all_horizontal([pl.col(c).is_not_null() for c in columns]) if columns else pl.lit(True)
    )


def _crepitus_at(visit: str, side: str) -> pl.DataFrame:
    try:
        return crepitus_values(visit, ["koos_s2", "exam_crepitus"], sides=(side,))
    except KeyError:  # V08 and V10 carry S2 but no exam
        return crepitus_values(visit, ["koos_s2"], sides=(side,)).with_columns(
            pl.lit(None, pl.Int64).alias("exam_crepitus")
        )


def crepitus_frame(A: Resolved) -> pl.DataFrame:
    """ID, SIDE, visit, koos_s2, exam_crepitus for the cohort side at every exposure visit of
    the schedule (null exam where the visit has none)."""
    side = A["cohort.side"]
    visits = schedule(horizon_of(A))["start_visit"].to_list()
    return pl.concat([_crepitus_at(v, side) for v in visits])


def periods(
    A: Resolved,
    cohort: Cohort,
    soa: pl.DataFrame,
    crepitus: pl.DataFrame,
    require: Sequence[str] = ("koos_s2",),
) -> tuple[pl.DataFrame, dict[str, int]]:
    """Person-period observations: crepitus at a period's exposure visit, SOA at its outcome visit.

    A person is at risk until an outcome visit shows SOA (then censored). Each at-risk period
    is potential; it is dropped when its outcome is missing (`missing_outcome`) or any measure
    in `require` is (`missing_crepitus`). With `periods.after_missing_outcome = "stop"`, a
    missing outcome also ends the person's follow-up.
    """
    needed = _present(_required(require))
    crep = crepitus.select(
        "ID",
        pl.col("visit").alias("start_visit"),
        pl.col("koos_s2").alias("crep"),
        pl.col("exam_crepitus").alias("exam"),
    )
    if setting(A, "exposure.exam_after_48m", "carry_v06") == "carry_v06":
        carried = crep.filter(pl.col("start_visit") == EXAM_CARRIED_FROM).select(
            "ID", pl.col("exam").alias("_exam_carried")
        )
        later = pl.col("start_visit") > EXAM_CARRIED_FROM
        crep = (
            crep.join(carried, on="ID", how="left")
            .with_columns(
                pl.when(later).then(pl.col("_exam_carried")).otherwise(pl.col("exam")).alias("exam")
            )
            .drop("_exam_carried")
        )
    outcome = soa.select("ID", pl.col("visit").alias("end_visit"), pl.col("soa").alias("event"))
    df = (
        cohort.people.select("ID", *COVARIATES)
        .join(schedule(horizon_of(A)), how="cross")
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
        "missing_crepitus": potential.filter(has_outcome & ~needed).height,
    }
    frame = potential.filter(has_outcome & needed).select(
        "ID", "period", "crep", "exam", "event", *COVARIATES
    )
    return frame, counts


def four_year(
    cohort: Cohort,
    soa: pl.DataFrame,
    crepitus: pl.DataFrame,
    require: Sequence[str] = ("koos_s2",),
) -> pl.DataFrame:
    """One row per person with every required baseline measure: incident SOA at any outcome
    visit in `soa` (48 months for Lo 2018; to the horizon when soa_status covers more)."""
    needed = _present(_required(require, "0"))
    event = (
        soa.filter(pl.col("visit") != "00")
        .group_by("ID")
        .agg(pl.col("soa").fill_null(False).any().alias("event"))
    )
    baseline = crepitus.filter(pl.col("visit") == "00").select(
        "ID", pl.col("koos_s2").alias("crep0"), pl.col("exam_crepitus").alias("exam0")
    )
    return (
        cohort.people.join(baseline, on="ID", how="inner")
        .filter(needed)
        .join(event, on="ID", how="left")
        .with_columns(pl.col("event").fill_null(False))
        .select("ID", "crep0", "exam0", "event", *COVARIATES, "kl0", "womac0")
        .sort("ID")
    )
