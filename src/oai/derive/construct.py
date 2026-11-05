"""Construct-validity measures: one long table of yes/no and numeric measures per visit.

`MEASURES` is the one place that maps each measure to its AllClinical variables. A visit gets a
measure only when it has every variable the measure needs (visit 14 asked little; visit 13 has no
KOOS), and `EXCLUDED_VISITS` drops a measure at a visit that has the variable but not a usable
value (the 20-m pace at visit 13, about 384 people).
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import partial
from types import MappingProxyType

import polars as pl

from oai.derive.knee import find_col
from oai.derive.pase import DEFAULT_WALKING, pase_visit, work_active

# measure -> (kind, variable suffixes after V<visit>). Right then left knee for per-knee kinds.
MEASURES = MappingProxyType(
    {
        "total": ("total", ("PASE",)),
        "total_minus_walking": ("total_minus_walking", ("PASE", "PASE2", "PASE2HR")),
        "walking_any": ("walking_any", ("PASE2", "PASE2HR")),
        "hours_5plus": ("hours_threshold", ("PASE2", "PASE2HR")),
        "sitting_long": ("sitting_long", ("PASE1", "PASE1HR")),
        "light_sport": ("positive", ("PASE3",)),
        "moderate_sport": ("positive", ("PASE4",)),
        "strenuous_sport": ("positive", ("PASE5",)),
        "muscle": ("positive", ("PASE6",)),
        "light_housework": ("yes", ("HOUACT1",)),
        "heavy_housework": ("yes", ("HOUACT2",)),
        "home_repairs": ("yes", ("HOUACT3",)),
        "yard": ("yes", ("HOUACT4",)),
        "garden": ("yes", ("HOUACT5",)),
        "caring": ("yes", ("HOUACT6",)),
        "work_active": ("work_active", ("WORK7", "WORKAMT")),
        "womac_function": ("worse_knee", ("WOMADLR", "WOMADLL")),
        "womac_walk": ("worse_knee", ("DIRKN6", "DILKN6")),
        "koos_sport": ("number", ("KOOSFSR",)),
        "pace_20m": ("number", ("20MPACE",)),
    }
)
EXCLUDED_VISITS = MappingProxyType({"pace_20m": ("13",)})
PAIN_KNEES = ("WOMKPR", "WOMKPL")


def worse_knee(right: pl.Expr, left: pl.Expr, higher_is_worse: bool = True) -> pl.Expr:
    """The worse of two knees' values; the available one if only one is; null only if both are."""
    return pl.max_horizontal(right, left) if higher_is_worse else pl.min_horizontal(right, left)


def kl_group(kl: pl.Expr, groups: Mapping) -> pl.Expr:
    """The name of the group holding the KL grade; null when the grade is missing or ungrouped."""
    out = pl.when(pl.lit(False)).then(pl.lit(None, dtype=pl.String))
    for name, grades in groups.items():
        out = out.when(kl.is_in(list(grades))).then(pl.lit(name))
    return out.otherwise(None)


def _has(df: pl.DataFrame, name: str) -> bool:
    return any(c.upper() == name.upper() for c in df.columns)


def _yes_no(condition: pl.Expr) -> pl.Expr:
    return condition.cast(pl.Float64)


def visit_measures(
    allclinical: pl.DataFrame,
    visit: str,
    measures: Mapping = MEASURES,
    *,
    walking: Mapping = DEFAULT_WALKING,
    hours_threshold: float = 5.0,
    sitting_long_code: int = 4,
) -> pl.DataFrame:
    """Long ID, visit, measure, value (Float64; yes/no are 0/1) for the measures a visit has.

    Refused, don't-know and missing answers are null, never a value. Per-knee measures use the
    worse knee (the available knee when one is missing).
    """
    v = visit.removeprefix("V")
    col = partial(find_col, allclinical, where=f"allclinical{v}")
    id_col = col("ID")
    # the table plus the PASE item-2 and total columns of pase_visit, one row per person
    wide = allclinical.join(
        pase_visit(allclinical, v, walking), left_on=id_col, right_on="ID", how="left"
    )
    days, hours = pl.col(f"pase_days_{v}"), pl.col(f"pase_hours_{v}")
    week = days.replace_strict(
        dict(enumerate(walking["days"])), default=None, return_dtype=pl.Float64
    ) * hours.replace_strict(
        {c + 1: h for c, h in enumerate(walking["hours"])}, default=None, return_dtype=pl.Float64
    )

    def raw(suffix: str) -> pl.Expr:
        return pl.col(col(f"V{v}{suffix}")).cast(pl.Float64)

    def build(kind: str, suffixes: tuple[str, ...]) -> pl.Expr:
        first = suffixes[0]
        if kind == "total":
            return pl.col(f"pase_total_{v}")
        if kind == "total_minus_walking":
            return pl.col(f"pase_total_{v}") - pl.col(f"pase_walking_{v}")
        if kind == "walking_any":
            return _yes_no(days > 0)
        if kind == "hours_threshold":
            return _yes_no(pl.when(days == 0).then(0.0).otherwise(week) >= hours_threshold)
        if kind == "sitting_long":
            asked = raw("PASE1")
            return _yes_no(
                pl.when(asked == 0)
                .then(False)
                .when(asked.is_not_null())
                .then(raw("PASE1HR") == sitting_long_code)
            )
        if kind == "positive":  # frequency codes 0 (never) to 3; refused and don't know are null
            return _yes_no(pl.when(raw(first).is_in([0, 1, 2, 3])).then(raw(first) > 0))
        if kind == "yes":
            return _yes_no(pl.when(raw(first).is_in([0, 1])).then(raw(first) == 1))
        if kind == "work_active":
            return _yes_no(
                work_active(
                    pl.col(col(f"V{v}WORKAMT")).cast(pl.Int64),
                    pl.col(col(f"V{v}WORK7")).cast(pl.Int64),
                )
            )
        if kind == "worse_knee":
            return worse_knee(raw(suffixes[0]), raw(suffixes[1]))
        if kind == "number":
            return raw(first)
        raise ValueError(f"unknown measure kind {kind!r}")

    columns = []
    for name, (kind, suffixes) in measures.items():
        if v in EXCLUDED_VISITS.get(name, ()):
            continue
        if not all(_has(allclinical, f"V{v}{s}") for s in suffixes):
            continue
        # pase_visit keeps the total only where the visit released one
        if kind in ("total", "total_minus_walking") and f"pase_total_{v}" not in wide.columns:
            continue
        columns.append(build(kind, suffixes).cast(pl.Float64).alias(name))
    table = wide.select(pl.col(id_col).alias("ID"), *columns)
    names = [c for c in table.columns if c != "ID"]
    if not names:
        return pl.DataFrame(
            schema={
                "ID": table.schema["ID"],
                "visit": pl.String,
                "measure": pl.String,
                "value": pl.Float64,
            }
        )
    return table.unpivot(names, index="ID", variable_name="measure", value_name="value").select(
        "ID", pl.lit(v).alias("visit"), "measure", pl.col("value").cast(pl.Float64)
    )


def womac_pain(allclinical: pl.DataFrame, visit: str) -> pl.DataFrame:
    """ID, visit, womac_pain_t: the worse knee's WOMAC pain score at the visit."""
    v = visit.removeprefix("V")
    col = partial(find_col, allclinical, where=f"allclinical{v}")
    right, left = (pl.col(col(f"V{v}{s}")).cast(pl.Float64) for s in PAIN_KNEES)
    return allclinical.select(
        pl.col(col("ID")).alias("ID"),
        pl.lit(v).alias("visit"),
        worse_knee(right, left).alias("womac_pain_t"),
    )
