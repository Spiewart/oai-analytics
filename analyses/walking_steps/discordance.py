"""Step `discordance`: self-reported walkers who are, and are not, step-defined walkers.

Pure functions for the comparison; the step script wires them to the frames.
"""

from __future__ import annotations

import polars as pl

from oai.derive import construct

GROUPS = ("Yes, step walker", "Yes, not a step walker", "No")


def assign_groups(answers: pl.DataFrame, walkers: pl.DataFrame, definition: str) -> pl.DataFrame:
    """ID, group for people in both frames.

    `answers` has ID and yes (self-report); `walkers` has ID and a Boolean column `definition`.
    A self-reported walker is a step walker or not by that column; a non-walker is "No".
    """
    joined = answers.select("ID", "yes").join(walkers.select("ID", definition), on="ID")
    return joined.select(
        "ID",
        pl.when(~pl.col("yes"))
        .then(pl.lit(GROUPS[2]))
        .when(pl.col(definition))
        .then(pl.lit(GROUPS[0]))
        .otherwise(pl.lit(GROUPS[1]))
        .alias("group"),
    )


# measure -> (area, kind, source). Every release variable was checked against the release's
# *_Contents.pdf (Enrollees, SubjectChar00, AllClinical00-10, AccelDataByDay06/08).
MEASURES: dict[str, tuple[str, str, str]] = {
    # time-varying: health
    "bmi": ("health", "continuous", "P01BMI at 00, then V##BMI"),
    "comorbidity": ("health", "continuous", "V##COMORB"),
    "sf12_physical": ("health", "continuous", "V##HSPSS"),
    "sf12_mental": ("health", "continuous", "V##HSMSS"),
    "cesd": ("health", "continuous", "V##CESD"),
    "pace_20m": ("activity", "continuous", "V##20MPACE (construct.visit_measures)"),
    "walk_400m_time": ("activity", "continuous", "V##400MTIM"),
    "employed": ("demographic", "binary", "V##CEMPLOY in discordance.employed_codes"),
    # time-varying: knee (worse knee; both replacement rules)
    "womac_pain": ("knee", "continuous", "V##WOMKPR/L (worse knee)"),
    "womac_function": ("knee", "continuous", "V##WOMADLR/L (worse knee)"),
    "womac_walk": ("knee", "continuous", "V##DIRKN6/DILKN6 (worse knee)"),
    "frequent_pain_any": (
        "knee",
        "binary",
        "outcomes.pain_baseline_item / outcomes.pain_followup_item, either knee",
    ),
    "kl_worse": ("knee", "continuous", "knee_outcomes.knee_status kl (worse knee)"),
    "replaced_any": ("knee", "binary", "knee_outcomes.knee_status replaced, either knee"),
    "koos_sport": ("knee", "continuous", "V##KOOSFSR (construct.visit_measures)"),
    # time-varying: activity (construct.visit_measures)
    **{
        name: (
            "activity",
            "continuous" if kind in ("total", "total_minus_walking") else "binary",
            f"construct.visit_measures {name}",
        )
        for name, (kind, _) in construct.MEASURES.items()
        if kind not in ("worse_knee", "number")
    },
    # fixed: demographic
    "age": ("demographic", "continuous", "V06AGE"),
    "age0": ("demographic", "continuous", "V00AGE"),
    "sex": ("demographic", "binary", "P02SEX (1 male, 2 female)"),
    "race": ("demographic", "categorical", "P02RACE"),
    "education": ("demographic", "categorical", "V00EDCV"),
    "income": ("demographic", "categorical", "V00INCOME"),
    "married": ("demographic", "binary", "V00MARITST = 1 (married)"),
    "subcohort": ("demographic", "categorical", "V00COHORT"),
    "site": ("demographic", "categorical", "V00SITE"),
    # fixed: the 96-month item's amounts (category codes)
    "amount_years": ("item_amount", "categorical", "V10WKYRAR4 (walking.walking_answers)"),
    "amount_months": ("item_amount", "categorical", "V10WKMOAR4 (walking.walking_answers)"),
    "amount_times": ("item_amount", "categorical", "V10WKTMAR4 (walking.walking_answers)"),
    # fixed: the device week, over the group's device basis
    "valid_days": ("device", "continuous", "oai.derive.devices.person_wave valid_days"),
    "wear_hr": ("device", "continuous", "oai.derive.devices.person_wave wear_hr"),
    "steps": ("device", "continuous", "oai.derive.devices.person_wave steps"),
    "mv_min": ("device", "continuous", "oai.derive.devices.person_wave mv_min"),
    "season": ("device", "categorical", "AccelDataByDay V##PAMonth (monitoring month)"),
    "weekend_share": ("device", "continuous", "AccelDataByDay V##PAWeekDay (day of week)"),
}
# knee-level measures: long_table gives each one row per replacement rule
KNEE_LEVEL = ("womac_pain", "womac_function", "womac_walk", "frequent_pain_any", "kl_worse")
# per-knee AllClinical suffixes (right, left) for the worse-knee scores
KNEE_SCORES = {
    "womac_pain": construct.PAIN_KNEES,
    "womac_function": construct.MEASURES["womac_function"][1],
    "womac_walk": construct.MEASURES["womac_walk"][1],
}
# person-level numeric AllClinical measures: measure -> suffix after V<visit>
NUMBERS = {
    "comorbidity": "COMORB",
    "sf12_physical": "HSPSS",
    "sf12_mental": "HSMSS",
    "cesd": "CESD",
    "walk_400m_time": "400MTIM",
}
REPLACEMENT_RULES = ("keep_kl4", "censor")


def _censor_mask(status: pl.DataFrame) -> pl.Expr:
    """True from a knee's first replaced visit on (visit codes sort in time order)."""
    return (
        pl.col("replaced")
        .fill_null(False)
        .cast(pl.Int8)
        .cum_max()
        .over(["ID", "SIDE"], order_by="visit")
        > 0
    )


def worse_knee_kl(status: pl.DataFrame, rule: str) -> pl.DataFrame:
    """ID, visit, kl_worse: the worse knee's KL grade at each visit.

    `status` is knee_status-shaped (ID, SIDE, visit, kl, replaced). Under "keep_kl4" a replaced
    knee counts as KL 4; under "censor" a knee is dropped from its first replaced visit on.
    """
    if rule not in REPLACEMENT_RULES:
        raise ValueError(f"rule must be one of {REPLACEMENT_RULES}, not {rule!r}")
    st = status.with_columns(_censor_mask(status).alias("_gone"))
    kl = pl.col("kl").cast(pl.Float64)
    if rule == "keep_kl4":
        value = pl.when(pl.col("_gone")).then(4.0).otherwise(kl)
    else:
        value = pl.when(pl.col("_gone")).then(None).otherwise(kl)
    return st.group_by("ID", "visit").agg(value.max().alias("kl_worse")).sort("ID", "visit")


def nearest_values(long: pl.DataFrame, target: str, steps: int, order: list[str]) -> pl.DataFrame:
    """ID, measure (and censored, when present), used, value: each measure's value at the
    visit nearest `target` within `steps` positions of `order`. Ties go to the target itself,
    then to the earlier visit; null values don't count."""
    keys = ["ID", "measure", *(["censored"] if "censored" in long.columns else [])]
    pos = {v: i for i, v in enumerate(order)}
    at = pos[target]
    reach = [v for v in order if abs(pos[v] - at) <= steps]
    rank = pl.col("visit").replace_strict(pos, return_dtype=pl.Int64)
    return (
        long.filter(pl.col("visit").is_in(reach) & pl.col("value").is_not_null())
        .with_columns((rank - at).abs().alias("_dist"), rank.alias("_pos"))
        .sort(*keys, "_dist", "_pos")
        .group_by(keys, maintain_order=True)
        .first()
        .select(*keys, pl.col("visit").alias("used"), "value")
    )


def window_values(
    long: pl.DataFrame, start: str, end: str, steps: int, order: list[str]
) -> pl.DataFrame:
    """ID, measure, start_used, end_used, change (end minus start) for a change window.

    Each endpoint uses the visit holding the measure nearest to it within `steps` positions of
    `order` (ties: the endpoint itself, then the earlier visit). A measure with no visit within
    reach of either endpoint, or whose two picks are not in time order, gets no row.
    """
    a = nearest_values(long, start, steps, order)
    b = nearest_values(long, end, steps, order)
    keys = [c for c in a.columns if c not in ("used", "value")]
    pos = {v: i for i, v in enumerate(order)}
    joined = a.join(b, on=keys, suffix="_end")
    return joined.filter(
        pl.col("used").replace_strict(pos, return_dtype=pl.Int64)
        < pl.col("used_end").replace_strict(pos, return_dtype=pl.Int64)
    ).select(
        *keys,
        pl.col("used").alias("start_used"),
        pl.col("used_end").alias("end_used"),
        (pl.col("value_end") - pl.col("value")).alias("change"),
    )


def knee_level(per_knee: pl.DataFrame, status: pl.DataFrame, rule: str) -> pl.DataFrame:
    """ID, visit, measure, value: the worse knee's value of each per-knee measure.

    `per_knee` is ID, SIDE ("R"/"L"), visit, measure, value; `status` gives replaced by knee.
    Under "keep_kl4" every knee keeps its recorded value; under "censor" a knee is dropped from
    its first replaced visit on. A person-visit stays (null) when every knee is dropped.
    """
    if rule not in REPLACEMENT_RULES:
        raise ValueError(f"rule must be one of {REPLACEMENT_RULES}, not {rule!r}")
    gone = status.select("ID", "SIDE", "visit", _censor_mask(status).alias("_gone"))
    df = per_knee.join(gone, on=["ID", "SIDE", "visit"], how="left").with_columns(
        pl.col("_gone").fill_null(False)
    )
    value = pl.col("value")
    if rule == "censor":
        value = pl.when(pl.col("_gone")).then(None).otherwise(value)
    return df.group_by("ID", "visit", "measure").agg(value.max().alias("value"))


def _visit_tables(allclinical: pl.DataFrame, visit: str, A) -> tuple[pl.DataFrame, pl.DataFrame]:
    """(person-level long ID, visit, measure, value; per-knee long ID, SIDE, visit, measure,
    value) for the measures one visit's AllClinical has."""
    v = visit
    cols = {c.upper(): c for c in allclinical.columns}

    def has(name: str) -> bool:
        return name.upper() in cols

    def num(name: str) -> pl.Expr:
        return pl.col(cols[name.upper()]).cast(pl.Float64)

    id_expr = pl.col(cols["ID"]).cast(pl.Int64).alias("ID")
    person = {k: spec for k, spec in construct.MEASURES.items() if spec[0] != "worse_knee"}
    frames = [
        construct.visit_measures(allclinical, v, person).with_columns(pl.col("ID").cast(pl.Int64))
    ]
    extra = []
    bmi = "P01BMI" if v == "00" else f"V{v}BMI"
    if has(bmi):
        extra.append(num(bmi).alias("bmi"))
    for name, suffix in NUMBERS.items():
        if has(f"V{v}{suffix}"):
            extra.append(num(f"V{v}{suffix}").alias(name))
    if has(f"V{v}CEMPLOY"):
        codes = [float(c) for c in A["discordance.employed_codes"]]
        employ = num(f"V{v}CEMPLOY")
        extra.append(
            pl.when(employ.is_not_null())
            .then(employ.is_in(codes))
            .cast(pl.Float64)
            .alias("employed")
        )
    if extra:
        frames.append(
            allclinical.select(id_expr, *extra)
            .unpivot(index="ID", variable_name="measure", value_name="value")
            .select("ID", pl.lit(v).alias("visit"), "measure", "value")
        )
    person_long = pl.concat(frames)

    knees = []
    for side, i in (("R", 0), ("L", 1)):
        exprs = []
        for name, suffixes in KNEE_SCORES.items():
            if has(f"V{v}{suffixes[i]}"):
                exprs.append(num(f"V{v}{suffixes[i]}").alias(name))
        item = A["outcomes.pain_baseline_item" if v == "00" else "outcomes.pain_followup_item"]
        pain = item.format(visit=v, side=side)
        if has(pain):
            exprs.append((num(pain) == 1).cast(pl.Float64).alias("frequent_pain_any"))
        if exprs:
            knees.append(
                allclinical.select(id_expr, *exprs)
                .unpivot(index="ID", variable_name="measure", value_name="value")
                .select(
                    "ID", pl.lit(side).alias("SIDE"), pl.lit(v).alias("visit"), "measure", "value"
                )
            )
    per_knee = pl.concat(knees) if knees else None
    return person_long, per_knee


def assemble_long(
    person: list[pl.DataFrame], knee: pl.DataFrame, status: pl.DataFrame
) -> pl.DataFrame:
    """The long table from its parts: person-level long frames (ID, visit, measure, value),
    per-knee long (ID, SIDE, visit, measure, value) and knee_status (ID, SIDE, visit, kl,
    replaced).

    knee_status has every enrollee at every visit, and its replacement timing counts a knee as
    replaced at visits after a replacement whether or not the person came. So replaced_any and
    kl_worse (both rules) are kept only at attended person-visits: those with some non-null
    AllClinical value.
    """
    attended = (
        pl.concat([*person, knee.drop("SIDE")], how="vertical_relaxed")
        .filter(pl.col("value").is_not_null())
        .select("ID", "visit")
        .unique()
    )
    replaced_any = (
        status.group_by("ID", "visit")
        .agg(pl.col("replaced").fill_null(False).any().cast(pl.Float64).alias("value"))
        .join(attended, on=["ID", "visit"], how="semi")
        .select("ID", "visit", pl.lit("replaced_any").alias("measure"), "value")
    )
    frames = [
        pl.concat([*person, replaced_any], how="vertical_relaxed").with_columns(
            pl.lit(False).alias("censored")
        )
    ]
    for rule, censored in (("keep_kl4", False), ("censor", True)):
        kl = (
            worse_knee_kl(status, rule)
            .join(attended, on=["ID", "visit"], how="semi")
            .select(
                "ID",
                "visit",
                pl.lit("kl_worse").alias("measure"),
                pl.col("kl_worse").cast(pl.Float64).alias("value"),
            )
        )
        frames.append(
            pl.concat([knee_level(knee, status, rule), kl], how="vertical_relaxed")
            .select("ID", "visit", "measure", "value")
            .with_columns(pl.lit(censored).alias("censored"))
        )
    return (
        pl.concat(frames, how="vertical_relaxed")
        .select(
            pl.col("ID").cast(pl.Int64),
            pl.col("visit").cast(pl.String),
            pl.col("measure").cast(pl.String),
            pl.col("value").cast(pl.Float64),
            pl.col("censored").cast(pl.Boolean),
        )
        .sort("censored", "measure", "ID", "visit")
    )


def long_table(A) -> pl.DataFrame:
    """ID, visit, measure, value (Float64; binary 0/1), censored for every time-varying measure
    at `discordance.trend_visits`.

    Knee-level measures (KNEE_LEVEL) have one row per replacement rule: censored False under
    "keep_kl4", True under "censor". Every other measure has censored False only.
    """
    # the per-knee replacement rules need each knee's own replacement, which knee_status gives
    # only under outcomes.arthroplasty_scope = "right" (the side it is run for)
    scope = A["outcomes.arthroplasty_scope"]
    if scope != "right":
        raise ValueError(
            f"outcomes.arthroplasty_scope must be 'right' (side-specific) for the per-knee "
            f"replacement rules, not {scope!r}"
        )
    from oai.derive.knee_outcomes import knee_status
    from oai.loader import read_table

    visits = list(A["discordance.trend_visits"])
    status = knee_status(A, visits, A["discordance.anchor_visit"]).select(
        pl.col("ID").cast(pl.Int64), "SIDE", "visit", "kl", "replaced"
    )
    person, per_knee = [], []
    for v in visits:
        p, k = _visit_tables(read_table("allclinical", v), v, A)
        person.append(p)
        if k is not None:
            per_knee.append(k)
    return assemble_long(person, pl.concat(per_knee), status)
