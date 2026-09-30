"""Lo et al. 2022 (Arthritis Rheumatol 74:1660): cohort, exposure, outcomes, descriptives.

Every analytic choice comes from assumptions.toml through `A[...]`; see ASSUMPTIONS.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import polars as pl

from oai.assumptions import Resolved
from oai.derive.knee import (
    KNEE_KEYS,
    find_col,
    frequent_knee_pain,
    knee_alignment,
    knee_replacement,
    visit_days,
    with_fallback,
    xray_readings,
)
from oai.loader import read_table
from oai.visits import nominal_month

FLOW_STEPS = (
    "all",
    "age50",
    "baseline_xray",
    "roa",
    "before_survey",
    "no_visit96",
    "no_survey",
    "no_followup",
)
SURVEY_STEPS = ("before_survey", "no_visit96", "no_survey")
S1_STEPS = (*SURVEY_STEPS, "no_followup")
OUTCOMES = ("new_pain", "kl_worse", "jsn_worse", "improved_pain")
GROUPS = ("walkers", "nonwalkers", "all")
ALIGNMENTS = ("varus", "neutral", "valgus")
AMOUNT_ITEMS = {"years": "V10WKYRAR4", "months": "V10WKMOAR4", "times": "V10WKTMAR4"}
DAYS_PER_MONTH = 365.25 / 12
WALKER_VALUES = {"non-walker": False, "walker": True, "exclude": None}


@dataclass
class Built:
    knees: pl.DataFrame
    flow: pl.DataFrame
    fallback_visit: str | None


def _select(df: pl.DataFrame, **columns: str) -> pl.DataFrame:
    return df.select([pl.col(find_col(df, src)).alias(dst) for dst, src in columns.items()])


def _people(A: Resolved) -> pl.DataFrame:
    enrollees = _select(read_table("enrollees"), ID="ID", sex="P02SEX")
    baseline = _select(read_table("allclinical", "00"), ID="ID", age="V00AGE", bmi="P01BMI")
    ac10 = read_table("allclinical", "10")
    answered = pl.any_horizontal(
        [pl.col(find_col(ac10, item)).is_not_null() for item in A["cohort.survey_completed_items"]]
    )
    survey = ac10.select(
        pl.col(find_col(ac10, "ID")).alias("ID"),
        pl.col(find_col(ac10, "V10FVDATE"))
        .cast(pl.String)
        .str.to_date("%m/%d/%Y", strict=False)
        .alias("visit96"),
        answered.alias("answered"),
        pl.col(find_col(ac10, A["exposure.walker_item"])).alias("walk_item"),
        *[
            pl.col(find_col(ac10, item)).alias(f"amount_{name}")
            for name, item in AMOUNT_ITEMS.items()
        ],
    )
    return (
        enrollees.join(baseline, on="ID", how="left")
        .join(survey, on="ID", how="left")
        .with_columns(
            pl.col("age").cast(pl.Float64),
            pl.col("bmi").cast(pl.Float64),
            pl.col("answered").fill_null(False),
        )
    )


def _followup_days(ids: pl.DataFrame, visits: list[str]) -> pl.DataFrame:
    out = ids
    for visit in visits:
        out = out.join(visit_days(visit).rename({"days": f"d{visit}"}), on="ID", how="left")
    nominal = nominal_month(visits[0]) * DAYS_PER_MONTH
    return out.select(
        "ID", pl.coalesce([pl.col(f"d{v}") for v in visits] + [pl.lit(nominal)]).alias("days")
    )


def _flow_row(step: str, remaining: pl.DataFrame, excluded: pl.DataFrame, oa: pl.DataFrame) -> dict:
    ids = excluded["ID"].implode()
    return {
        "step": step,
        "persons": remaining.height,
        "excluded_persons": excluded.height,
        "excluded_knees": oa.filter(pl.col("ID").is_in(ids)).height,
        "male": int((excluded["sex"] == 1).sum()),
        "age_mean": excluded["age"].mean(),
        "bmi_mean": excluded["bmi"].mean(),
    }


def _walk_amount(name: str, midpoints: list[float]) -> pl.Expr:
    mapping = {code + 1: float(value) for code, value in enumerate(midpoints)}
    return pl.col(f"amount_{name}").replace_strict(mapping, default=None, return_dtype=pl.Float64)


def build(A: Resolved) -> Built:
    project, min_kl = A["cohort.reading_project"], A["knees.min_kl"]
    fu_visits = list(A["outcomes.followup_visits"])
    people = _people(A)

    baseline = xray_readings(["00"], project=project).filter(pl.col("KL").is_not_null())
    at_baseline = knee_replacement().select(*KNEE_KEYS, "replaced_at_baseline")
    oa = (
        baseline.join(at_baseline, on=list(KNEE_KEYS), how="left")
        .filter(~pl.col("replaced_at_baseline").fill_null(False) & (pl.col("KL") >= min_kl))
        .select(*KNEE_KEYS, pl.col("KL").alias("kl0"), pl.col("JSM").alias("jsm0"))
    )
    followup = with_fallback(
        *[xray_readings([v], project=project) for v in fu_visits], value_cols=["KL", "JSM"]
    ).select(*KNEE_KEYS, pl.col("KL").alias("klf"), pl.col("JSM").alias("jsmf"), "source_visit")
    replaced = knee_replacement(_followup_days(people.select("ID"), fu_visits)).select(
        *KNEE_KEYS, "replaced"
    )
    knees = (
        oa.join(followup, on=list(KNEE_KEYS), how="left")
        .join(replaced, on=list(KNEE_KEYS), how="left")
        .with_columns(pl.col("replaced").fill_null(False))
        .with_columns(
            (pl.col("source_visit").is_not_null() | pl.col("replaced")).alias("has_followup")
        )
    )

    # Person-level flow (Figure 1 and Supplementary Table 1).
    survey_start = date.fromisoformat(A["cohort.survey_start"])
    rules = {
        "age50": pl.col("age") >= A["cohort.min_age"],
        "baseline_xray": pl.col("ID").is_in(baseline["ID"].unique().implode()),
        "roa": pl.col("ID").is_in(oa["ID"].unique().implode()),
        "before_survey": ~(pl.col("visit96") < survey_start).fill_null(False),
        "no_visit96": pl.col("visit96").is_not_null(),
        "no_survey": pl.col("answered"),
        "no_followup": pl.col("ID").is_in(knees.filter("has_followup")["ID"].unique().implode()),
    }
    current = people
    flow = [_flow_row("all", people, people.clear(), oa)]
    survey_excluded = []
    for step, keep in rules.items():
        excluded = current.filter(~keep.fill_null(False))
        current = current.filter(keep.fill_null(False))
        flow.append(_flow_row(step, current, excluded, oa))
        if step in SURVEY_STEPS:
            survey_excluded.append(excluded)

    missing_as = WALKER_VALUES[A["exposure.missing_walking_as"]]
    respondents = current.with_columns(
        pl.when(pl.col("walk_item") == 1)
        .then(True)
        .when(pl.col("walk_item") == 0)
        .then(False)
        .otherwise(pl.lit(missing_as, dtype=pl.Boolean))
        .alias("walker")
    )
    cohort = [respondents]
    impute = A["cohort.impute_missing_walking"]
    if impute != "none":
        imputed = pl.concat(survey_excluded).filter(rules["no_followup"])
        cohort.append(
            imputed.with_columns(pl.lit(WALKER_VALUES[impute], dtype=pl.Boolean).alias("walker"))
        )
    persons = pl.concat(cohort).filter(pl.col("walker").is_not_null())

    # Pain, alignment and outcomes (knee level).
    pain0 = frequent_knee_pain("00", A["outcomes.pain_baseline_items"]).select(
        *KNEE_KEYS, pl.col("frequent_pain").alias("pain0")
    )
    painf = with_fallback(
        *[frequent_knee_pain(v, A["outcomes.pain_followup_items"]) for v in fu_visits],
        value_cols=["frequent_pain"],
    ).select(*KNEE_KEYS, pl.col("frequent_pain").alias("painf"))
    films = knee_alignment(
        source=A["alignment.source"], visits=A["alignment.visits"], pick=A["alignment.pick"]
    ).select(*KNEE_KEYS, "hka")
    alignment = (
        pl.when(pl.col("hka") <= A["alignment.varus_max"])
        .then(pl.lit("varus"))
        .when(pl.col("hka") >= A["alignment.valgus_min"])
        .then(pl.lit("valgus"))
        .when(pl.col("hka").is_not_null())
        .then(pl.lit("neutral"))
        .alias("alignment")
    )
    structural = pl.col("replaced") & pl.lit(A["outcomes.replacement_is_structural_worsening"])
    pain_counts = (
        pl.lit(True) if A["outcomes.replaced_knee_pain"] == "keep" else ~pl.col("replaced")
    )
    midpoints = A["exposure.category_midpoints"]
    walk_times = (
        _walk_amount("years", midpoints["years"])
        * _walk_amount("months", midpoints["months"])
        * _walk_amount("times", midpoints["times"])
    )

    frame = (
        knees.filter("has_followup")
        .join(
            persons.select(
                "ID", "walker", "age", "sex", "bmi", *[f"amount_{n}" for n in AMOUNT_ITEMS]
            ),
            on="ID",
            how="inner",
        )
        .join(pain0, on=list(KNEE_KEYS), how="left")
        .join(painf, on=list(KNEE_KEYS), how="left")
        .join(films, on=list(KNEE_KEYS), how="left")
        .with_columns(
            alignment,
            pl.when(pl.col("walker")).then(walk_times).otherwise(0.0).alias("walk_times"),
            pl.when(structural)
            .then(True)
            .otherwise(pl.col("klf") > pl.col("kl0"))
            .alias("kl_worse"),
            pl.when(structural)
            .then(True)
            .otherwise(pl.col("jsmf") > pl.col("jsm0"))
            .alias("jsn_worse"),
            pl.when(pl.col("pain0").not_() & pain_counts).then(pl.col("painf")).alias("new_pain"),
            pl.when(pl.col("pain0") & pain_counts)
            .then(pl.col("painf").not_())
            .alias("improved_pain"),
        )
        .drop("has_followup", *[f"amount_{n}" for n in AMOUNT_ITEMS])
        .sort(["ID", "SIDE"])
    )
    fallback_visit = fu_visits[-1] if len(fu_visits) > 1 else None
    return Built(knees=frame, flow=pl.DataFrame(flow), fallback_visit=fallback_visit)
