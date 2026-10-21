"""Crepitus measures in the OAI: availability by visit, retention, and at-risk knees and events.

The measures and their column templates live in `oai.derive.crepitus`.

Everything is knee-level (ID, SIDE) and cohort-labelled from Enrollees `V00COHORT`
(1 Progression, 2 Incidence, 3 Non-exposed control). Counts only: no row-level output.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from functools import partial

import polars as pl

from oai.derive.crepitus import MEASURES, Measure  # noqa: F401  (Measure re-exported)
from oai.derive.knee import (
    KNEE_KEYS,
    find_col,
    frequent_knee_pain,
    knee_replacement,
    xray_readings,
)
from oai.loader import read_table
from oai.visits import load_visit_map

VISITS = tuple(f"{v:02d}" for v in range(15))
XRAY_FOLLOWUP = ("01", "03", "05", "06")
COHORTS = {1: "Progression", 2: "Incidence", 3: "Non-exposed control"}
ALL = "All"
ROA_KL = 2  # radiographic OA = tibiofemoral KL >= 2 (Lo 2018 abstract)


def participants() -> pl.DataFrame:
    """ID, cohort (label): one row per Enrollees participant."""
    df = read_table("enrollees", None)
    col = partial(find_col, df, where="enrollees")
    return df.select(
        pl.col(col("ID")).alias("ID"),
        pl.col(col("V00COHORT"))
        .replace_strict(COHORTS, default=None, return_dtype=pl.String)
        .alias("cohort"),
    )


def measures_long(visits: Sequence[str] = VISITS) -> tuple[pl.DataFrame, pl.DataFrame]:
    """(long, coverage). long: ID, SIDE, visit, measure, value (nulls dropped).

    coverage: measure, visit, collected, rows. `collected` is False when the visit's
    AllClinical table has no such column (e.g. V13/V14 carry none of the three).
    """
    long: list[pl.DataFrame] = []
    coverage: list[dict] = []
    for visit in visits:
        df = read_table("allclinical", visit)
        col = partial(find_col, df, where=f"allclinical{visit}")
        ids = pl.col(col("ID")).alias("ID")
        for m in MEASURES:
            try:
                names = {s: col(m.template.format(visit=visit, side=s)) for s in ("R", "L")}
            except KeyError:
                coverage.append(dict(measure=m.name, visit=visit, collected=False, rows=0))
                continue
            frame = pl.concat(
                [
                    df.select(
                        ids,
                        pl.lit(s).alias("SIDE"),
                        pl.lit(visit).alias("visit"),
                        pl.lit(m.name).alias("measure"),
                        pl.col(name).cast(pl.Int64, strict=False).alias("value"),
                    )
                    for s, name in names.items()
                ]
            ).drop_nulls("value")
            long.append(frame)
            coverage.append(dict(measure=m.name, visit=visit, collected=True, rows=frame.height))
    return pl.concat(long), pl.DataFrame(coverage)


def _positive(thresholds: Mapping[str, int]) -> pl.Expr:
    """True where the value counts as crepitus present, under each measure's threshold."""
    return pl.col("value") >= pl.col("measure").replace_strict(thresholds, return_dtype=pl.Int64)


def thresholds_for(s2_threshold: int) -> dict[str, int]:
    return {"exam_crepitus": 1, "exam_grind_pain": 1, "koos_s2": s2_threshold}


def _with_cohort(long: pl.DataFrame, people: pl.DataFrame) -> pl.DataFrame:
    return long.join(people, on="ID", how="left")


def _both_groupings(df: pl.DataFrame, by: list[str], aggs: list[pl.Expr]) -> pl.DataFrame:
    """Aggregate by `by` + cohort, and over all cohorts (cohort = "All")."""
    per_cohort = df.group_by([*by, "cohort"]).agg(aggs)
    overall = df.group_by(by).agg(aggs).with_columns(pl.lit(ALL).alias("cohort"))
    return pl.concat([per_cohort, overall.select(per_cohort.columns)])


def availability(
    long: pl.DataFrame,
    people: pl.DataFrame,
    coverage: pl.DataFrame,
    s2_threshold: int,
) -> pl.DataFrame:
    """Knees and persons with a non-missing value, and with crepitus present, per measure,
    visit and cohort. Every measure x visit x cohort appears, zeros included."""
    df = _with_cohort(long, people).with_columns(
        _positive(thresholds_for(s2_threshold)).alias("positive")
    )
    counts = _both_groupings(
        df,
        ["measure", "visit"],
        [
            pl.len().alias("knees"),
            pl.col("positive").sum().alias("knees_positive"),
            pl.col("ID").n_unique().alias("persons"),
            pl.col("ID").filter(pl.col("positive")).n_unique().alias("persons_positive"),
        ],
    )
    denom = pl.concat(
        [
            people.group_by("cohort").agg(pl.len().alias("persons_in_cohort")),
            pl.DataFrame({"cohort": [ALL], "persons_in_cohort": [people.height]}).with_columns(
                pl.col("persons_in_cohort").cast(pl.UInt32)
            ),
        ]
    )
    grid = coverage.select("measure", "visit", "collected").join(denom, how="cross")
    visit_map = load_visit_map()
    meta = pl.DataFrame(
        {
            "visit": [v[1:] for v in visit_map],
            "month": [m.month for m in visit_map.values()],
            "contact": [m.contact for m in visit_map.values()],
        }
    )
    return (
        grid.join(counts, on=["measure", "visit", "cohort"], how="left")
        .join(meta, on="visit", how="left")
        .with_columns(pl.col("knees", "knees_positive", "persons", "persons_positive").fill_null(0))
        .with_columns(
            pl.col("cohort")
            .replace_strict(
                {ALL: 0, **{label: code for code, label in COHORTS.items()}}, return_dtype=pl.Int64
            )
            .alias("_order")
        )
        .sort("measure", "visit", "_order")
        .select(
            "measure",
            "visit",
            "month",
            "contact",
            "cohort",
            "collected",
            "persons_in_cohort",
            "persons",
            "persons_positive",
            "knees",
            "knees_positive",
        )
    )


def s2_distribution(long: pl.DataFrame, people: pl.DataFrame) -> pl.DataFrame:
    """KOOS S2 response counts (knees) per visit and cohort."""
    df = _with_cohort(long.filter(pl.col("measure") == "koos_s2"), people)
    return (
        _both_groupings(df, ["visit", "value"], [pl.len().alias("knees")])
        .sort("visit", "value", "cohort")
        .rename({"value": "response"})
    )


def paired_exam_s2(long: pl.DataFrame, people: pl.DataFrame, s2_threshold: int) -> pl.DataFrame:
    """Knees with both the exam item and KOOS S2 at one visit, as a 2 x 2 by cohort."""
    wide = (
        long.filter(pl.col("measure").is_in(["exam_crepitus", "koos_s2"]))
        .pivot(
            on="measure", index=[*KNEE_KEYS, "visit"], values="value", aggregate_function="first"
        )
        .drop_nulls(["exam_crepitus", "koos_s2"])
        .with_columns(
            (pl.col("exam_crepitus") == 1).alias("exam_pos"),
            (pl.col("koos_s2") >= s2_threshold).alias("s2_pos"),
        )
    )
    df = _with_cohort(wide, people)
    return _both_groupings(
        df,
        ["visit"],
        [
            pl.len().alias("knees_paired"),
            (pl.col("exam_pos") & pl.col("s2_pos")).sum().alias("exam_pos_s2_pos"),
            (pl.col("exam_pos") & ~pl.col("s2_pos")).sum().alias("exam_pos_s2_neg"),
            (~pl.col("exam_pos") & pl.col("s2_pos")).sum().alias("exam_neg_s2_pos"),
            (~pl.col("exam_pos") & ~pl.col("s2_pos")).sum().alias("exam_neg_s2_neg"),
        ],
    ).sort("visit", "cohort")


def retention(long: pl.DataFrame, people: pl.DataFrame) -> pl.DataFrame:
    """Persons with the measure at baseline and at one or more later visits, per cohort."""
    per_person = long.group_by(["measure", "ID"]).agg(
        pl.col("visit").n_unique().alias("n_visits"),
        (pl.col("visit") == "00").any().alias("baseline"),
    )
    df = per_person.join(people, on="ID", how="left")
    return _both_groupings(
        df,
        ["measure"],
        [
            pl.len().alias("persons_any_visit"),
            pl.col("baseline").sum().alias("persons_baseline"),
            (pl.col("baseline") & (pl.col("n_visits") >= 2)).sum().alias("baseline_plus_later"),
            *[(pl.col("n_visits") >= k).sum().alias(f"persons_ge{k}_visits") for k in (2, 3, 4, 5)],
        ],
    ).sort("measure", "cohort")


# ---------------------------------------------------------------- at-risk knees and events


def _any(cond: pl.Expr) -> pl.Expr:
    return cond.fill_null(False).any()


def knee_table(A) -> pl.DataFrame:
    """One row per knee: cohort, baseline exposures, and risk / ascertained / event flags.

    Outcomes (docs in assumptions.toml):
      incident_roa  baseline KL < 2 -> any follow-up KL >= 2 (to the horizon visit)
      incident_soa  no baseline symptomatic ROA (KL >= 2 with frequent pain) -> KL >= 2 with
                    frequent pain at any follow-up visit (Lo 2018)
      kl_progression baseline KL in the risk set -> follow-up KL at least one grade higher
      tkr_all / tkr_roa  native at baseline (and KL >= 2 for tkr_roa) -> counted replacement
    """
    project = A["readings.project"]
    horizon = A["readings.horizon_visit"]
    visits = [v for v in XRAY_FOLLOWUP if v <= horizon]
    risk_kl = {"2-3": (2, 3), "1-3": (1, 2, 3)}[A["progression.risk_kl"]]

    people = participants()
    all_knees = pl.concat(
        [people.select("ID", "cohort").with_columns(pl.lit(s).alias("SIDE")) for s in ("R", "L")]
    )
    baseline = xray_readings(["00"], project=project).select(*KNEE_KEYS, pl.col("KL").alias("kl0"))
    replacement = knee_replacement().select(*KNEE_KEYS, "replaced_at_baseline", "replaced")
    pain0 = frequent_knee_pain("00", A["outcomes.pain_baseline_items"]).select(
        *KNEE_KEYS, pl.col("frequent_pain").alias("pain0")
    )

    fu = xray_readings(visits, project=project).select(*KNEE_KEYS, "visit", "KL")
    fu_pain = pl.concat(
        [frequent_knee_pain(v, A["outcomes.pain_followup_items"]) for v in visits]
    ).select(*KNEE_KEYS, "visit", "frequent_pain")
    fu = fu.join(fu_pain, on=[*KNEE_KEYS, "visit"], how="left")
    fu_knee = fu.group_by(KNEE_KEYS).agg(
        pl.col("KL").max().alias("kl_max"),
        pl.col("KL").is_not_null().sum().alias("n_kl"),
        _any((pl.col("KL") >= ROA_KL) & pl.col("frequent_pain")).alias("soa_event"),
        (pl.col("KL").is_not_null() & pl.col("frequent_pain").is_not_null()).any().alias("soa_asc"),
    )

    exposures = _baseline_exposures()

    k = (
        all_knees.join(baseline, on=KNEE_KEYS, how="left")
        .join(pain0, on=KNEE_KEYS, how="left")
        .join(replacement, on=KNEE_KEYS, how="left")
        .join(fu_knee, on=KNEE_KEYS, how="left")
        .join(exposures, on=KNEE_KEYS, how="left")
        .with_columns(pl.col("replaced_at_baseline", "replaced").fill_null(False))
    )
    native = ~pl.col("replaced_at_baseline")
    kl0, kl_max, n_kl = pl.col("kl0"), pl.col("kl_max"), pl.col("n_kl").fill_null(0)
    soa0 = (kl0 >= ROA_KL) & pl.col("pain0")
    return k.with_columns(
        (native & (kl0 < ROA_KL)).fill_null(False).alias("incident_roa_risk"),
        (n_kl > 0).alias("incident_roa_asc"),
        (kl_max >= ROA_KL).fill_null(False).alias("incident_roa_event"),
        (native & kl0.is_not_null() & pl.col("pain0").is_not_null() & ~soa0.fill_null(False))
        .fill_null(False)
        .alias("incident_soa_risk"),
        pl.col("soa_asc").fill_null(False).alias("incident_soa_asc"),
        pl.col("soa_event").fill_null(False).alias("incident_soa_event"),
        (native & kl0.is_in(risk_kl)).fill_null(False).alias("kl_progression_risk"),
        (n_kl > 0).alias("kl_progression_asc"),
        (kl_max >= kl0 + 1).fill_null(False).alias("kl_progression_event"),
        native.alias("tkr_all_risk"),
        pl.lit(True).alias("tkr_all_asc"),
        pl.col("replaced").alias("tkr_all_event"),
        (native & (kl0 >= ROA_KL)).fill_null(False).alias("tkr_roa_risk"),
        pl.lit(True).alias("tkr_roa_asc"),
        pl.col("replaced").alias("tkr_roa_event"),
    )


def _baseline_exposures() -> pl.DataFrame:
    """ID, SIDE and one column per measure: the baseline (V00) value of every knee."""
    df = read_table("allclinical", "00")
    col = partial(find_col, df, where="allclinical00")
    return pl.concat(
        [
            df.select(
                pl.col(col("ID")).alias("ID"),
                pl.lit(s).alias("SIDE"),
                *[
                    pl.col(col(m.template.format(visit="00", side=s)))
                    .cast(pl.Int64, strict=False)
                    .alias(m.name)
                    for m in MEASURES
                ],
            )
            for s in ("R", "L")
        ]
    )


OUTCOMES = ("incident_roa", "incident_soa", "kl_progression", "tkr_all", "tkr_roa")
NO_EXPOSURE = "(exposure not required)"


def event_table(knees: pl.DataFrame, s2_threshold: int) -> pl.DataFrame:
    """Per outcome, cohort and baseline crepitus measure: knees at risk, ascertained, and the
    exposed / unexposed split with events in each. Knees need a non-missing baseline value
    of the measure to enter its rows."""
    thresholds = thresholds_for(s2_threshold)
    rows = []
    cohorts = [(ALL, knees), *[(c, knees.filter(pl.col("cohort") == c)) for c in COHORTS.values()]]
    for outcome in OUTCOMES:
        risk, asc, event = (pl.col(f"{outcome}_{s}") for s in ("risk", "asc", "event"))
        for cohort, frame in cohorts:
            at_risk = frame.filter(risk)
            ascertained = at_risk.filter(asc)
            base = dict(
                outcome=outcome,
                cohort=cohort,
                persons_at_risk=at_risk["ID"].n_unique(),
                knees_at_risk=at_risk.height,
                knees_ascertained=ascertained.height,
            )
            rows.append(
                {
                    **base,
                    "exposure": NO_EXPOSURE,
                    "knees_with_exposure": ascertained.height,
                    "exposed": None,
                    "unexposed": None,
                    "events_exposed": None,
                    "events_unexposed": None,
                    "events_total": ascertained.filter(event).height,
                }
            )
            for m in MEASURES:
                have = ascertained.filter(pl.col(m.name).is_not_null())
                pos = pl.col(m.name) >= thresholds[m.name]
                exposed, unexposed = have.filter(pos), have.filter(~pos)
                rows.append(
                    {
                        **base,
                        "exposure": m.name,
                        "knees_with_exposure": have.height,
                        "exposed": exposed.height,
                        "unexposed": unexposed.height,
                        "events_exposed": exposed.filter(event).height,
                        "events_unexposed": unexposed.filter(event).height,
                        "events_total": have.filter(event).height,
                    }
                )
    return pl.DataFrame(rows, infer_schema_length=None)
