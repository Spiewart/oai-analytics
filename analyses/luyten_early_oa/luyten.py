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

import polars as pl

from oai.assumptions import Resolved
from oai.derive.crepitus import crepitus_values
from oai.derive.knee import find_col, xray_readings
from oai.loader import read_table

KOOS = ("pain", "symptoms", "adl", "qol")
WOMAC_FUNCTION_MAX = 68
ROA_AT_BASELINE = 1  # V99E?XIOA: KL >= 2 at baseline; 2-9: no ROA at baseline (read knee)
OUTCOMES99_READ = tuple(range(2, 10))
PROGRESSION_INCIDENCE = (1, 2)


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
