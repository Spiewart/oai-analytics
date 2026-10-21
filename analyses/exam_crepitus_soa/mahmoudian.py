"""Mahmoudian 2023 anchor: baseline exam crepitus and tibiofemoral structural development.

Mahmoudian A et al., OARSI 2023 abstract 179 (Osteoarthritis Cartilage 31(S1):S214-5).
Progression and Incidence cohorts; knees with tibiofemoral KL 0-1 and frequent pain at
baseline, one per subject; outcome at V06 (48 months): incident joint-space narrowing and/or
more osteophytes in either tibiofemoral compartment, and the same with frequent pain at V06.
"""

from __future__ import annotations

import random
from functools import partial

import polars as pl

from oai.assumptions import Resolved
from oai.derive.crepitus import crepitus_values
from oai.derive.knee import KNEE_KEYS, SIDE_CODES, find_col, frequent_knee_pain
from oai.loader import read_table

TF_FEATURES = ("JSM", "JSL", "OSFM", "OSTM", "OSFL", "OSTL")
JSN = ("JSM", "JSL")
OSTEOPHYTES = ("OSFM", "OSTM", "OSFL", "OSTL")
ELIGIBLE_COHORTS = (1, 2)  # Progression, Incidence (no Non-exposed controls)
ELIGIBLE_KL = (0, 1)


def tf_readings(visit: str, project: int) -> pl.DataFrame:
    """ID, SIDE, kl and the six tibiofemoral features (Float64) from one reading project."""
    df = read_table("kxr_sq_bu", visit)
    col = partial(find_col, df, where=f"kxr_sq_bu{visit}")
    return (
        df.filter(pl.col(col("READPRJ")) == project)
        .select(
            pl.col(col("ID")).cast(pl.Int64).alias("ID"),
            pl.col(col("SIDE")).replace_strict(SIDE_CODES, return_dtype=pl.String).alias("SIDE"),
            pl.col(col(f"V{visit}XRKL")).cast(pl.Float64).alias("kl"),
            *[pl.col(col(f"V{visit}XR{f}")).cast(pl.Float64).alias(f) for f in TF_FEATURES],
        )
        .unique(list(KNEE_KEYS), keep="first", maintain_order=True)
    )


def _fill_osteophytes(readings: pl.DataFrame) -> pl.DataFrame:
    """Blank osteophyte grades in a KL 0-1 reading become 0 (Project 15 grades them for KL >= 2
    always, and 99% of the KL 0-1 knees it did grade are 0)."""
    low_kl = pl.col("kl").is_in(ELIGIBLE_KL)
    return readings.with_columns(
        [
            pl.when(low_kl & pl.col(c).is_null()).then(0.0).otherwise(pl.col(c)).alias(c)
            for c in OSTEOPHYTES
        ]
    )


def structural_development(
    base: pl.DataFrame,
    fu: pl.DataFrame,
    jsn_rule: str,
    osteophyte_rule: str,
    missing_osteophytes: str = "exclude",
) -> pl.DataFrame:
    """ID, SIDE, structural: JSN rule or osteophyte rule; null if any feature is missing.

    `missing_osteophytes = "absent"` first turns blank osteophyte grades in KL 0-1 readings
    into 0 (both frames then need a `kl` column).
    """
    if missing_osteophytes == "absent":
        base, fu = _fill_osteophytes(base), _fill_osteophytes(fu)
    df = base.select(*KNEE_KEYS, *TF_FEATURES).join(
        fu.select(*KNEE_KEYS, *TF_FEATURES), on=list(KNEE_KEYS), how="inner", suffix="_fu"
    )
    b, f = (lambda c: pl.col(c)), (lambda c: pl.col(f"{c}_fu"))
    if jsn_rule == "incident":
        jsn = pl.any_horizontal([(b(c) == 0) & (f(c) >= 1) for c in JSN])
    else:
        jsn = pl.any_horizontal([f(c) > b(c) for c in JSN])
    if osteophyte_rule == "sites":
        count = lambda g: pl.sum_horizontal([(g(c) >= 1).cast(pl.Int64) for c in OSTEOPHYTES])  # noqa: E731
        ost = count(f) > count(b)
    else:
        ost = pl.sum_horizontal([f(c) for c in OSTEOPHYTES]) > pl.sum_horizontal(
            [b(c) for c in OSTEOPHYTES]
        )
    missing = pl.any_horizontal([b(c).is_null() | f(c).is_null() for c in TF_FEATURES])
    return df.select(
        *KNEE_KEYS, pl.when(missing).then(None).otherwise(jsn | ost).alias("structural")
    )


def pick_knee(knees: pl.DataFrame, rule: str, seed: int) -> pl.DataFrame:
    """One knee per ID: random (seeded) or the named side when both are eligible."""
    df = knees.sort("ID", "SIDE")
    if rule == "random":
        rng = random.Random(seed)
        order = pl.Series("_order", [rng.random() for _ in range(df.height)])
    else:
        wanted = {"right": "R", "left": "L"}[rule]
        order = (df["SIDE"] != wanted).cast(pl.Float64).alias("_order")
    return (
        df.with_columns(order)
        .sort("ID", "_order")
        .unique("ID", keep="first", maintain_order=True)
        .drop("_order")
    )


def _sided(frame: pl.DataFrame, value: str, name: str) -> pl.DataFrame:
    return frame.select(*KNEE_KEYS, pl.col(value).alias(name))


def anchor_frame(A: Resolved) -> pl.DataFrame:
    """ID, SIDE, exam0, structural, structural_sx, age, sex, bmi, kl0: one eligible knee each."""
    project = A["mahmoudian.reading_project"]
    base, fu = tf_readings("00", project), tf_readings("06", project)
    enrollees = read_table("enrollees", None)
    ecol = partial(find_col, enrollees, where="enrollees")
    people = enrollees.select(
        pl.col(ecol("ID")).cast(pl.Int64).alias("ID"),
        pl.col(ecol("V00COHORT")).alias("cohort"),
        pl.col(ecol("P02SEX")).alias("sex"),
    )
    ac00 = read_table("allclinical", "00")
    acol = partial(find_col, ac00, where="allclinical00")
    baseline = ac00.select(
        pl.col(acol("ID")).cast(pl.Int64).alias("ID"),
        pl.col(acol("V00AGE")).cast(pl.Float64).alias("age"),
        pl.col(acol("P01BMI")).cast(pl.Float64).alias("bmi"),
    )
    pain0 = _sided(
        frequent_knee_pain("00", A["outcomes.pain_baseline_item"]), "frequent_pain", "pain0"
    )
    pain6 = _sided(
        frequent_knee_pain("06", A["outcomes.pain_followup_item"]), "frequent_pain", "pain6"
    )
    exam0 = _sided(crepitus_values("00", ["exam_crepitus"]), "exam_crepitus", "exam0")
    structural = structural_development(
        base,
        fu,
        A["mahmoudian.jsn_rule"],
        A["mahmoudian.osteophyte_rule"],
        A["mahmoudian.missing_osteophytes"],
    )
    knees = (
        base.select(*KNEE_KEYS, pl.col("kl").alias("kl0"))
        .join(people, on="ID", how="inner")
        .join(pain0, on=list(KNEE_KEYS), how="left")
        .join(exam0, on=list(KNEE_KEYS), how="left")
        .join(structural, on=list(KNEE_KEYS), how="left")
        .filter(
            pl.col("cohort").is_in(ELIGIBLE_COHORTS)
            & pl.col("kl0").is_in(ELIGIBLE_KL)
            & pl.col("pain0").fill_null(False)
            & pl.col("exam0").is_not_null()
            & pl.col("structural").is_not_null()
        )
    )
    picked = pick_knee(knees, A["mahmoudian.knee_pick"], A["mahmoudian.seed"])
    pain_at_4y = pl.col("pain6")
    if A["mahmoudian.missing_followup_pain"] == "not_sx":
        pain_at_4y = pain_at_4y.fill_null(False)
    return (
        picked.join(pain6, on=list(KNEE_KEYS), how="left")
        .join(baseline, on="ID", how="left")
        .with_columns((pl.col("structural") & pain_at_4y).alias("structural_sx"))
        .select("ID", "SIDE", "exam0", "structural", "structural_sx", "age", "sex", "bmi", "kl0")
        .sort("ID")
    )


def anchor_metrics(frame: pl.DataFrame) -> pl.DataFrame:
    """metric, value for the Mahmoudian count and descriptive targets."""
    m = {
        "m.subjects": frame.height,
        "m.crepitus": frame.filter(pl.col("exam0") == 1).height,
        "m.women": frame.filter(pl.col("sex") == 2).height,
        "m.age_mean": frame["age"].mean(),
        "m.bmi_mean": frame["bmi"].mean(),
        "m.structural.events": int(frame["structural"].sum()),
        "m.structural_sx.events": int(frame["structural_sx"].sum()),
    }
    return pl.DataFrame(
        {"metric": list(m), "value": [float(v) for v in m.values()]},
        schema={"metric": pl.String, "value": pl.Float64},
    )
