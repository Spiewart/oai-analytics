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
from oai.derive.walking import (
    AMOUNT_ITEMS,
    WALKER_VALUES,
    walker_status,
    walking_answers,
    walking_sessions,
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
DAYS_PER_MONTH = 365.25 / 12


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
    )
    return (
        enrollees.join(baseline, on="ID", how="left")
        .join(survey, on="ID", how="left")
        .join(walking_answers(A["exposure.walker_item"]), on="ID", how="left")
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
    # Analysis knees are always native. cohort.roa_counts_replaced_knees only widens the
    # person-level radiographic-OA step: a knee replaced at baseline (which has no reading)
    # counts as OA there.
    roa_ids = oa["ID"]
    if A["cohort.roa_counts_replaced_knees"]:
        replaced_ids = at_baseline.filter(pl.col("replaced_at_baseline"))["ID"]
        roa_ids = pl.concat([roa_ids, replaced_ids])
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
        "roa": pl.col("ID").is_in(roa_ids.unique().implode()),
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

    respondents = current.with_columns(
        walker_status(
            yes_without_amount_as=A["exposure.yes_without_amount_as"],
            missing_as=A["exposure.missing_walking_as"],
        )
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
    walk_times = walking_sessions(A["exposure.category_midpoints"])

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


def _metrics(rows: list[tuple[str, float | int | None]]) -> pl.DataFrame:
    return pl.DataFrame(
        [{"metric": key, "value": None if value is None else float(value)} for key, value in rows],
        schema={"metric": pl.String, "value": pl.Float64},
    )


def _by_group(df: pl.DataFrame) -> dict[str, pl.DataFrame]:
    return {
        "walkers": df.filter(pl.col("walker")),
        "nonwalkers": df.filter(~pl.col("walker")),
        "all": df,
    }


def flow_metrics(built: Built) -> pl.DataFrame:
    rows: list[tuple[str, float | int | None]] = []
    for r in built.flow.iter_rows(named=True):
        step = r["step"]
        rows.append((f"flow.{step}.persons", r["persons"]))
        if step != "all":
            rows += [
                (f"flow.{step}.excluded_persons", r["excluded_persons"]),
                (f"flow.{step}.excluded_knees", r["excluded_knees"]),
            ]
        if step in S1_STEPS:
            rows += [
                (f"s1.{step}.male", r["male"]),
                (f"s1.{step}.age_mean", r["age_mean"]),
                (f"s1.{step}.bmi_mean", r["bmi_mean"]),
            ]
    fallback = built.knees.filter(pl.col("source_visit") == built.fallback_visit)
    rows += [
        ("flow.knees", built.knees.height),
        ("flow.fallback36.persons", fallback["ID"].n_unique()),
    ]
    return _metrics(rows)


def table1(built: Built) -> pl.DataFrame:
    rows: list[tuple[str, float | int | None]] = []
    persons = built.knees.unique("ID", keep="first", maintain_order=True)
    for group, p in _by_group(persons).items():
        rows += [
            (f"t1.persons.{group}", p.height),
            (f"t1.age_mean.{group}", p["age"].mean()),
            (f"t1.male.{group}", (p["sex"] == 1).sum()),
            (f"t1.bmi_mean.{group}", p["bmi"].mean()),
        ]
    days = persons.filter(pl.col("walker"))["walk_times"].drop_nulls()
    for stat, q in (("min", 0.0), ("p25", 0.25), ("median", 0.5), ("p75", 0.75), ("max", 1.0)):
        rows.append(
            (f"t1.walk_days_{stat}.walkers", days.quantile(q, "linear") if len(days) else None)
        )
    for group, k in _by_group(built.knees).items():
        rows.append((f"t1.knees.{group}", k.height))
        rows += [(f"t1.kl{v}.{group}", (k["kl0"] == v).sum()) for v in (2, 3, 4)]
        rows += [(f"t1.jsm{v}.{group}", (k["jsm0"] == v).sum()) for v in (0, 1, 2, 3)]
        rows += [
            (f"t1.pain0.{group}", k["pain0"].sum()),
            (f"t1.align_knees.{group}", k["alignment"].is_not_null().sum()),
            (f"t1.pain48.{group}", k["painf"].sum()),
            (f"t1.replaced48.{group}", k["replaced"].sum()),
        ]
        rows += [(f"t1.{cat}.{group}", (k["alignment"] == cat).sum()) for cat in ALIGNMENTS]
    return _metrics(rows)


def table3(built: Built) -> pl.DataFrame:
    rows: list[tuple[str, float | int | None]] = []
    for outcome in OUTCOMES:
        for cat in ALIGNMENTS:
            for group, k in _by_group(built.knees).items():
                if group == "all":
                    continue
                cell = k.filter((pl.col("alignment") == cat) & pl.col(outcome).is_not_null())
                rows += [
                    (f"t3.{outcome}.{cat}.{group}.events", cell[outcome].sum()),
                    (f"t3.{outcome}.{cat}.{group}.n", cell.height),
                ]
    return _metrics(rows)
