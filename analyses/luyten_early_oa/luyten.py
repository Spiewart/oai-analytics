"""Early-stage knee OA by the Luyten 2018 criteria, as Mahmoudian 2021 applied them in OAI.

Mahmoudian A et al., Semin Arthritis Rheum 2021;51:285-91. One row per knee:
  KL 0-1      baseline tibiofemoral KL (`luyten.kl_source`)
  KOOS        at least `luyten.koos_min` of pain, symptoms, function in daily living (WOMAC
              function rescaled; the release has no KOOS ADL) and quality of life (one value per
              person) at or below `luyten.koos_cutoff`
  sign        crepitus or medial or lateral joint-line tenderness on examination
Framing 1 compares crepitus with tenderness only inside the group (every member has a sign);
Framing 2 compares crepitus with none among KL 0-1 knees meeting the KOOS criterion.
"""

from __future__ import annotations

import dataclasses

import polars as pl

from oai.assumptions import Resolved
from oai.derive.crepitus import crepitus_values
from oai.derive.incident_soa import soa_status
from oai.derive.knee import find_col, xray_readings
from oai.loader import read_table

KOOS = ("pain", "symptoms", "adl", "qol")
WOMAC_FUNCTION_MAX = 68
ROA_AT_BASELINE = 1  # V99E?XIOA: KL >= 2 at baseline; 2-9: no ROA at baseline (read knee)
OUTCOMES99_READ = tuple(range(2, 10))
PROGRESSION_INCIDENCE = (1, 2)
HORIZONS = {"48": "06", "96": "10"}  # outcome label -> last visit
OUTCOMES = ("roa48", "roa96", "soa48", "soa96")
# Case-count frames (early OA vs controls, Framing 1, Framing 2) and their exposure levels
FRAMES = {"early": ("yes", "no"), "f1": ("yes", "jlt_only"), "f2": ("yes", "no")}


def sides_of(A: Resolved) -> tuple[str, ...]:
    return ("R",) if A["cohort.knees"] == "right" else ("R", "L")


def _baseline_kl(A: Resolved, sides: tuple[str, ...]) -> pl.DataFrame:
    """ID, SIDE, kl0: Project 15 KL, or 2.0 / 0.0 from OUTCOMES99's baseline-ROA code."""
    if A["luyten.kl_source"] == "project15":
        return (
            xray_readings(["00"], project=A["cohort.reading_project"])
            .filter(pl.col("SIDE").is_in(sides))
            .select("ID", "SIDE", pl.col("KL").alias("kl0"))
        )
    df = read_table("outcomes", "99")
    code = lambda side: pl.col(find_col(df, f"V99E{side}XIOA", where="outcomes99")).cast(pl.Int64)  # noqa: E731
    return pl.concat(
        [
            df.select(
                pl.col(find_col(df, "ID")).cast(pl.Int64).alias("ID"),
                pl.lit(side).alias("SIDE"),
                pl.when(code(side) == ROA_AT_BASELINE)
                .then(2.0)
                .when(code(side).is_in(OUTCOMES99_READ))
                .then(0.0)
                .alias("kl0"),
            )
            for side in sides
        ]
    )


def baseline_knees(A: Resolved) -> pl.DataFrame:
    """One row per enrollee and knee side with the criteria's inputs, exposures and covariates."""
    sides = sides_of(A)
    enrollees = read_table("enrollees", None)
    people = enrollees.select(
        pl.col(find_col(enrollees, "ID")).cast(pl.Int64).alias("ID"),
        pl.col(find_col(enrollees, "V00COHORT")).cast(pl.Int64).alias("cohort"),
        pl.col(find_col(enrollees, "P02SEX")).cast(pl.Int64).alias("sex"),
    )
    if A["cohort.cohorts"] == "progression_incidence":
        people = people.filter(pl.col("cohort").is_in(PROGRESSION_INCIDENCE))
    clin = read_table("allclinical", "00")
    col = lambda name: pl.col(find_col(clin, name, where="allclinical00"))  # noqa: E731
    adl = lambda side: (  # noqa: E731
        100 - col(f"V00WOMADL{side}").cast(pl.Float64) * 100 / WOMAC_FUNCTION_MAX
        if A["luyten.adl_source"] == "womac_function"
        else pl.lit(None, pl.Float64)
    )
    knees = pl.concat(
        [
            clin.select(
                col("ID").cast(pl.Int64).alias("ID"),
                pl.lit(side).alias("SIDE"),
                col("V00AGE").cast(pl.Float64).alias("age"),
                col("P01BMI").cast(pl.Float64).alias("bmi"),
                col(f"V00KOOSKP{side}").cast(pl.Float64).alias("pain"),
                col(f"V00KOOSYM{side}").cast(pl.Float64).alias("symptoms"),
                adl(side).alias("adl"),
                col("V00KOOSQOL").cast(pl.Float64).alias("qol"),
                col(f"V00{side}KMTTPN").cast(pl.Int64, strict=False).alias("jlt_m"),
                col(f"V00{side}KLTTPN").cast(pl.Int64, strict=False).alias("jlt_l"),
            )
            for side in sides
        ]
    )
    crep = crepitus_values("00", ["exam_crepitus", "koos_s2"], sides=sides).select(
        "ID", "SIDE", pl.col("exam_crepitus").alias("exam0"), pl.col("koos_s2").alias("s2_0")
    )
    return (
        people.join(knees, on="ID", how="inner")
        .join(_baseline_kl(A, sides), on=["ID", "SIDE"], how="left")
        .join(crep, on=["ID", "SIDE"], how="left")
        .sort("ID", "SIDE", descending=[False, True])
    )


def criteria(knees: pl.DataFrame, A: Resolved) -> pl.DataFrame:
    """The criteria and both framings' exposures.

    `luyten` and `kl01_koos` are null for a knee whose KL is unread or that leaves the KL 0-1
    denominator under an `exclude` rule; False for a KL >= 2 knee.
    """
    counted = [s for s in KOOS if not (s == "adl" and A["luyten.adl_source"] == "omit")]
    cutoff = A["luyten.koos_cutoff"]
    koos_n = pl.sum_horizontal(
        [(pl.col(s) <= cutoff).fill_null(False).cast(pl.Int64) for s in counted]
    )
    koos_ok = koos_n >= A["luyten.koos_min"]
    if A["luyten.koos_missing"] == "exclude":
        any_missing = pl.any_horizontal([pl.col(s).is_null() for s in counted])
        koos_ok = pl.when(any_missing).then(None).otherwise(koos_ok)
    crep, jlt = pl.col("exam0") == 1, (pl.col("jlt_m") == 1) | (pl.col("jlt_l") == 1)
    sign_ok = crep.fill_null(False) | jlt.fill_null(False)
    if A["luyten.sign_missing"] == "exclude":
        any_missing = pl.any_horizontal([pl.col(c).is_null() for c in ("exam0", "jlt_m", "jlt_l")])
        sign_ok = pl.when(~sign_ok & any_missing).then(None).otherwise(sign_ok)
    df = knees.with_columns(
        koos_n=koos_n, koos_ok=koos_ok, sign_ok=sign_ok, kl01=pl.col("kl0").is_in([0.0, 1.0])
    )
    in_kl01 = pl.col("kl01").fill_null(False)
    out = pl.col("kl01") == False  # noqa: E712 (KL >= 2: False, unread KL: null)

    def within_kl01(test: pl.Expr, known: pl.Expr) -> pl.Expr:
        return pl.when(in_kl01 & known).then(test).when(out).then(False).otherwise(None)

    df = df.with_columns(
        luyten=within_kl01(
            pl.col("koos_ok") & pl.col("sign_ok"),
            pl.col("koos_ok").is_not_null() & pl.col("sign_ok").is_not_null(),
        ),
        kl01_koos=within_kl01(pl.col("koos_ok"), pl.col("koos_ok").is_not_null()),
        sign_group=pl.when(pl.col("exam0").is_null())
        .then(None)
        .when(crep & jlt.fill_null(False))
        .then(pl.lit("crepitus_jlt"))
        .when(crep)
        .then(pl.lit("crepitus_only"))
        .when(jlt.fill_null(False))
        .then(pl.lit("jlt_only"))
        .otherwise(pl.lit("none")),
    )
    return df.with_columns(
        f1_exposure=pl.when(pl.col("luyten").fill_null(False)).then(pl.col("exam0")),
        f2_exposure=pl.when(pl.col("kl01_koos").fill_null(False)).then(pl.col("exam0")),
    )


def group_metrics(knees: pl.DataFrame) -> pl.DataFrame:
    """g.* metrics: the early-OA group, its KL 0-1 denominator and controls (KL 0-1, not early)."""
    early = knees.filter(pl.col("luyten").fill_null(False))
    control = knees.filter(pl.col("luyten") == False)  # noqa: E712
    control = control.filter(pl.col("kl01").fill_null(False))
    denominator = early.height + control.height
    women = lambda d: d.filter(pl.col("sex") == 2).height  # noqa: E731
    metrics = {
        "g.knees": early.height,
        "g.persons": early["ID"].n_unique(),
        "g.kl01": denominator,
        "g.share": early.height / denominator if denominator else None,
        "g.kl01_koos": knees.filter(pl.col("kl01_koos").fill_null(False)).height,
        "g.early.age_mean": early["age"].mean(),
        "g.control.age_mean": control["age"].mean(),
        "g.early.bmi_mean": early["bmi"].mean(),
        "g.control.bmi_mean": control["bmi"].mean(),
        "g.early.women": women(early),
        "g.control.women": women(control),
    }
    for group in ("crepitus_jlt", "crepitus_only", "jlt_only"):
        metrics[f"g.sign.{group}"] = early.filter(pl.col("sign_group") == group).height
    return pl.DataFrame(
        {
            "metric": list(metrics),
            "value": [None if v is None else float(v) for v in metrics.values()],
        },
        schema={"metric": pl.String, "value": pl.Float64},
    )


# ---------------------------------------------------------------- outcomes


def for_side(A: Resolved, side: str) -> Resolved:
    """`A` with `cohort.side` set, for oai.derive.incident_soa's one-knee functions."""
    return dataclasses.replace(A, values={**A.values, "cohort.side": side})


def roa_series(status: pl.DataFrame, rule: str) -> pl.DataFrame:
    """ID, visit, roa: OUTCOMES99 ROA, or ROA or a replacement (`outcomes.roa_replacement`)."""
    roa = pl.col("roa") | pl.col("replaced") if rule == "event" else pl.col("roa")
    return status.select("ID", "visit", roa.alias("roa"))


def by_horizon(status: pl.DataFrame, column: str, horizon: str, selection: str) -> pl.DataFrame:
    """ID, value: incident `column` (True at any follow-up visit up to `horizon`).

    False when the horizon visit's value is known and no earlier visit is True; null otherwise
    (`known_or_case`). Under `complete` the horizon visit's value must be known even for a case.
    A knee True at baseline is prevalent, not incident: null.
    """
    up_to = status.filter(pl.col("visit") <= horizon)
    follow = pl.col("visit") != "00"
    at_horizon = pl.col(column).filter(pl.col("visit") == horizon).first()
    return (
        up_to.group_by("ID", maintain_order=True)
        .agg(
            pl.col(column).filter(pl.col("visit") == "00").first().alias("_base"),
            pl.col(column).filter(follow).fill_null(False).any().alias("_case"),
            at_horizon.alias("_last"),
        )
        .select(
            "ID",
            pl.when(pl.col("_base").fill_null(False))
            .then(None)
            .when(pl.col("_last").is_null() & (pl.lit(selection == "complete") | ~pl.col("_case")))
            .then(None)
            .otherwise(pl.col("_case"))
            .alias("value"),
        )
    )


def knee_outcomes(A: Resolved) -> pl.DataFrame:
    """ID, SIDE, replaced0, roa48, roa96, soa48, soa96 for every knee of the cohort."""
    selection, rule = A["horizon.selection"], A["outcomes.roa_replacement"]
    frames = []
    for side in sides_of(A):
        status = soa_status(for_side(A, side))
        knee = status.filter(pl.col("visit") == "00").select(
            "ID", pl.lit(side).alias("SIDE"), pl.col("replaced").alias("replaced0")
        )
        sources = {"roa": roa_series(status, rule), "soa": status.select("ID", "visit", "soa")}
        for label, visit in HORIZONS.items():
            for name, frame in sources.items():
                value = by_horizon(frame, name, visit, selection).rename(
                    {"value": f"{name}{label}"}
                )
                knee = knee.join(value, on="ID", how="left")
        frames.append(knee)
    return pl.concat(frames).select("ID", "SIDE", "replaced0", *OUTCOMES)


def all_knees(A: Resolved) -> pl.DataFrame:
    """Every knee with the criteria and outcomes, before the enrollment-replacement exclusion."""
    return criteria(baseline_knees(A), A).join(knee_outcomes(A), on=["ID", "SIDE"], how="left")


def knee_frame(A: Resolved, knees: pl.DataFrame | None = None) -> pl.DataFrame:
    """The criteria joined to the outcomes, without knees replaced at enrollment."""
    knees = all_knees(A) if knees is None else knees
    return knees.filter(~pl.col("replaced0").fill_null(False)).drop("replaced0")


def flow(A: Resolved, knees: pl.DataFrame | None = None) -> pl.DataFrame:
    """step, knees, persons: every knee, then each restriction in turn."""
    knees = all_knees(A) if knees is None else knees
    kept = knee_frame(A, knees)
    steps = {
        "all": knees,
        "replaced_at_baseline": kept,
        "kl_read": kept.filter(pl.col("kl0").is_not_null()),
        "kl01": kept.filter(pl.col("luyten").is_not_null() & pl.col("kl01")),
        "kl01_koos": kept.filter(pl.col("kl01_koos").fill_null(False)),
        "luyten": kept.filter(pl.col("luyten").fill_null(False)),
        "f1": kept.filter(pl.col("f1_exposure").is_not_null()),
        "f2": kept.filter(pl.col("f2_exposure").is_not_null()),
    }
    return pl.DataFrame(
        [{"step": s, "knees": d.height, "persons": d["ID"].n_unique()} for s, d in steps.items()]
    )


def _level(frame: str) -> pl.Expr:
    """The case-count level of each knee in `frame` (null outside it)."""
    if frame == "early":
        return (
            pl.when(pl.col("luyten").fill_null(False))
            .then(pl.lit("yes"))
            .when((pl.col("luyten") == False) & pl.col("kl01").fill_null(False))  # noqa: E712
            .then(pl.lit("no"))
        )
    exposure = pl.col(f"{frame}_exposure")
    reference = "jlt_only" if frame == "f1" else "no"
    return pl.when(exposure == 1).then(pl.lit("yes")).when(exposure == 0).then(pl.lit(reference))


def cohort_metrics(knees: pl.DataFrame) -> pl.DataFrame:
    """group_metrics plus o.<frame>.<outcome>.<level>.cases and .n (knees with a known outcome)."""
    rows = group_metrics(knees).to_dicts()
    for frame, levels in FRAMES.items():
        d = knees.with_columns(_level(frame).alias("_level"))
        for level in levels:
            at_level = d.filter(pl.col("_level") == level)
            for outcome in OUTCOMES:
                known = at_level.filter(pl.col(outcome).is_not_null())
                key = f"o.{frame}.{outcome}.{level}"
                rows.append({"metric": f"{key}.cases", "value": float(known[outcome].sum())})
                rows.append({"metric": f"{key}.n", "value": float(known.height)})
    return pl.DataFrame(rows, schema={"metric": pl.String, "value": pl.Float64})
