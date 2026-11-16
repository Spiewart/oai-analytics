"""Step `discordance`: self-reported walkers who are, and are not, step-defined walkers.

Pure functions for the comparison; the step script wires them to the frames.
"""

from __future__ import annotations

import numpy as np
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


# stage 1: standardized differences between the two "Yes" groups
WINDOWS = ("level_06", "change_00_06", "change_06_10")
_SHORT = ("step", "not", "no")


def _smd(a: np.ndarray, b: np.ndarray, kind: str, levels: np.ndarray) -> float | None:
    if len(a) < 2 or len(b) < 2:
        return None
    if kind == "categorical":
        pa = np.array([(a == lv).mean() for lv in levels])[:-1]
        pb = np.array([(b == lv).mean() for lv in levels])[:-1]
        if len(pa) == 0:
            return None

        def cov(p: np.ndarray) -> np.ndarray:
            return np.diag(p) - np.outer(p, p)

        diff = pa - pb
        quad = float(diff @ np.linalg.pinv((cov(pa) + cov(pb)) / 2) @ diff)
        return float(np.sqrt(max(quad, 0.0)))
    if kind == "binary":
        pa, pb = float(a.mean()), float(b.mean())
        denom = np.sqrt((pa * (1 - pa) + pb * (1 - pb)) / 2)
        diff = pa - pb
    elif kind == "continuous":
        denom = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)
        diff = float(a.mean() - b.mean())
    else:
        raise ValueError(f"kind must be continuous, binary or categorical, not {kind!r}")
    return float(diff / denom) if denom > 0 else None


def smd(a: np.ndarray, b: np.ndarray, kind: str) -> float | None:
    """Standardized mean difference, a ("Yes, not a step walker") minus b ("Yes, step walker").

    Continuous: difference over the pooled SD. Binary: difference in proportions over the
    pooled binomial SD. Categorical: the multi-level (Mahalanobis) form of Yang & Dalton (2012),
    which is unsigned. None when either group has fewer than 2 values or the pooled SD is 0.
    """
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    return _smd(a, b, kind, np.unique(np.concatenate([a, b])))


def smd_ci(
    a: np.ndarray, b: np.ndarray, kind: str, reps: int, seed: int
) -> tuple[float | None, float | None]:
    """Percentile 95% bootstrap CI for `smd`, resampling within each group."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if len(a) < 2 or len(b) < 2:
        return None, None
    levels = np.unique(np.concatenate([a, b]))
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(reps):
        x = _smd(rng.choice(a, len(a)), rng.choice(b, len(b)), kind, levels)
        if x is not None:
            draws.append(x)
    if not draws:
        return None, None
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return float(lo), float(hi)


def band(x: float | None, small: float, lead: float) -> str:
    """Reading band for |SMD|: negligible below `small`, small below `lead`, else lead."""
    if x is None:
        return ""
    return "negligible" if abs(x) < small else "small" if abs(x) < lead else "lead"


def _summary(x: np.ndarray, kind: str, min_cell: int = 1) -> str:
    """A group's summary: mean (SD), or the share of 1s, or the share of each level.

    Shares that stand for 1..min_cell-1 people show as "<min_cell": a binary summary when its
    1s or its 0s are that few; a categorical level that small. When only one level is masked,
    the smallest other level is masked too, since the rest would give it away by subtraction
    (this covers the case of a single other level).
    """
    if len(x) == 0:
        return ""
    small = lambda c: 0 < c < min_cell  # noqa: E731
    if kind == "continuous":
        sd = f"{x.std(ddof=1):.2f}" if len(x) > 1 else "-"
        return f"{x.mean():.2f} ({sd})"
    if kind == "binary":
        ones = int((x == 1).sum())
        if small(ones) or small(len(x) - ones):
            return f"<{min_cell}"
        return f"{100 * x.mean():.1f}%"
    levels, counts = np.unique(x, return_counts=True)
    masked = [small(int(c)) for c in counts]
    if masked.count(True) == 1:
        # one masked level is the total minus the others: mask the smallest other level too
        others = [i for i, m in enumerate(masked) if not m]
        masked[min(others, key=lambda i: counts[i])] = True
    return "; ".join(
        f"{lv:g}: <{min_cell}" if m else f"{lv:g}: {100 * c / len(x):.1f}%"
        for lv, c, m in zip(levels, counts, masked, strict=True)
    )


def _used(cell: pl.DataFrame, col: str) -> str:
    return "/".join(sorted(set(cell[col].drop_nulls().to_list())))


def screen(
    groups: pl.DataFrame, values: pl.DataFrame, kinds: dict[str, str], A, *, min_cell: int
) -> pl.DataFrame:
    """The stage-1 screen: one row per measure and window.

    `groups` is ID, group; `values` is ID, measure, window, value, start_used, end_used (one
    row per person; a level has the one visit in both *_used). Persons are those with a value,
    per group. SMD is "Yes, not a step walker" minus "Yes, step walker"; "No" is summarised
    only. Count columns are named persons_* so they stay clear of the egress count pattern, which
    means egress's small-cell check never sees them; so a group with 1..min_cell-1 persons in a
    cell has its persons_* nulled and summary_* blanked here, and when either "Yes" group is
    below min_cell the SMD, its CI and the band are left blank.
    """
    reps = int(A["discordance.bootstrap_reps"])
    seed = int(A["discordance.seed"])
    bands = A["discordance.smd_bands"]
    df = values.filter(pl.col("value").is_not_null() & pl.col("value").is_not_nan()).join(
        groups, on="ID"
    )
    schema = {
        "measure": pl.String,
        "area": pl.String,
        "window": pl.String,
        "start_used": pl.String,
        "end_used": pl.String,
        **{f"persons_{k}": pl.Int64 for k in _SHORT},
        **{f"summary_{k}": pl.String for k in _SHORT},
        "smd": pl.Float64,
        "smd_lo": pl.Float64,
        "smd_hi": pl.Float64,
        "band": pl.String,
    }
    rows = []
    for (measure, window), cell in df.group_by("measure", "window", maintain_order=True):
        kind = kinds[measure]
        vals = {
            g: cell.filter(pl.col("group") == g)["value"].to_numpy().astype(float) for g in GROUPS
        }
        a, b = vals[GROUPS[1]], vals[GROUPS[0]]
        if min(len(a), len(b)) < min_cell:
            est, lo, hi = None, None, None
        else:
            est = smd(a, b, kind)
            lo, hi = smd_ci(a, b, kind, reps, seed)
        row = {
            "measure": measure,
            "area": MEASURES.get(measure, ("",))[0],
            "window": window,
            "start_used": _used(cell, "start_used"),
            "end_used": _used(cell, "end_used"),
            "smd": est,
            "smd_lo": lo,
            "smd_hi": hi,
            "band": band(est, bands["small"], bands["lead"]),
        }
        for short, g in zip(_SHORT, GROUPS, strict=True):
            small = 0 < len(vals[g]) < min_cell
            row[f"persons_{short}"] = None if small else len(vals[g])
            row[f"summary_{short}"] = "" if small else _summary(vals[g], kind, min_cell)
        rows.append(row)
    return pl.DataFrame(rows, schema=schema).sort("measure", "window")


# the device week: descriptors over the same waves that define the group
DEVICE_NUMBERS = ("valid_days", "wear_hr", "steps", "mv_min")
# steps and MV minutes are part of how the groups are defined: context, never a lead
DEFINING = ("steps", "mv_min")
WEEKEND = ("Saturday", "Sunday")


def season(month: pl.Expr) -> pl.Expr:
    """Meteorological season of a month (1-12): 1 winter (Dec-Feb), 2 spring, 3 summer,
    4 autumn."""
    return (month.cast(pl.Int64) % 12 // 3 + 1).cast(pl.Float64)


def device_calendar(byday: pl.DataFrame, wave: str) -> pl.DataFrame:
    """ID, wave, season, weekend_share from one wave's AccelDataByDay (one row per valid day).

    Season is that of the monitoring month of the first valid day (the release has the month
    only, no date); weekend_share is the share of the valid days that are Saturday or Sunday.
    """
    v = wave
    return (
        byday.select(
            pl.col("ID").cast(pl.Int64),
            pl.col(f"V{v}VDaySequence").alias("_day"),
            pl.col(f"V{v}PAMonth").alias("_month"),
            pl.col(f"V{v}PAWeekDay").str.strip_chars().is_in(WEEKEND).alias("_weekend"),
        )
        .sort("ID", "_day")
        .group_by("ID", maintain_order=True)
        .agg(
            season(pl.col("_month").drop_nulls().first()).alias("season"),
            pl.col("_weekend").cast(pl.Float64).mean().alias("weekend_share"),
        )
        .with_columns(pl.lit(wave).alias("wave"))
    )


def device_descriptors(device: pl.DataFrame, calendar: pl.DataFrame, key: str) -> pl.DataFrame:
    """ID, valid_days, wear_hr, steps, mv_min, season, weekend_share over a device basis.

    `device` is the person-wave frame (ID, wave, valid, ...); `calendar` is device_calendar for
    the waves stacked. Basis "06" or "08" is that valid wave; "mean" averages the numbers and
    weekend_share over the person's valid waves (nulls skipped, as devices.combine) and takes
    season from the earliest valid wave.
    """
    valid = device.filter("valid").select(
        pl.col("ID").cast(pl.Int64), "wave", *[pl.col(m).cast(pl.Float64) for m in DEVICE_NUMBERS]
    )
    if key != "mean":
        valid = valid.filter(pl.col("wave") == key)
    joined = valid.join(calendar, on=["ID", "wave"], how="left").sort("ID", "wave")
    return joined.group_by("ID", maintain_order=True).agg(
        *[pl.col(m).mean() for m in DEVICE_NUMBERS],
        pl.col("season").first(),
        pl.col("weekend_share").mean(),
    )


def kl_coverage(groups: pl.DataFrame, long: pl.DataFrame, min_cell: int = 1) -> pl.DataFrame:
    """comparison, group, visit, share: the share of each group with a KL reading (kl_worse,
    replacement kept as KL 4) at each visit. `groups` is comparison, ID, group.

    The share is null where the people with a reading, or without one, number 1..min_cell-1
    (the default, 1, suppresses nothing: compute gaps from that frame).
    """
    kl = long.filter(
        (pl.col("measure") == "kl_worse") & ~pl.col("censored") & pl.col("value").is_not_null()
    ).select("ID", "visit")
    visits = long.select("visit").unique().sort("visit")
    size = groups.group_by("comparison", "group").agg(pl.len().alias("_size"))
    have = (
        groups.join(kl, on="ID")
        .group_by("comparison", "group", "visit")
        .agg(pl.len().alias("_have"))
    )
    return (
        size.join(visits, how="cross")
        .join(have, on=["comparison", "group", "visit"], how="left")
        .with_columns(pl.col("_have").fill_null(0))
        .select(
            "comparison",
            "group",
            "visit",
            pl.when(
                ((pl.col("_have") > 0) & (pl.col("_have") < min_cell))
                | (
                    (pl.col("_size") - pl.col("_have") > 0)
                    & (pl.col("_size") - pl.col("_have") < min_cell)
                )
            )
            .then(None)
            .otherwise(pl.col("_have") / pl.col("_size"))
            .alias("share"),
        )
        .sort("comparison", "group", "visit")
    )


def coverage_gaps(coverage: pl.DataFrame) -> dict[str, float | None]:
    """Per comparison: the largest gap, over visits, between the two "Yes" groups' KL coverage."""
    wide = coverage.filter(pl.col("group").is_in(GROUPS[:2])).pivot(
        on="group", index=["comparison", "visit"], values="share"
    )
    gaps = wide.group_by("comparison").agg(
        (pl.col(GROUPS[0]) - pl.col(GROUPS[1])).abs().max().alias("gap")
    )
    return {r["comparison"]: r["gap"] for r in gaps.iter_rows(named=True)}


def _fmt(x: float | None) -> str:
    return "" if x is None else f"{x:.2f}"


def _md_table(rows: pl.DataFrame) -> str:
    cols = [
        "Measure",
        "Window",
        "Visits used",
        f"{GROUPS[0]}",
        f"{GROUPS[1]}",
        f"{GROUPS[2]} (reference)",
        "SMD (95% CI)",
    ]
    out = "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n"
    for r in rows.iter_rows(named=True):
        used = (
            r["start_used"]
            if r["start_used"] == r["end_used"]
            else (f"{r['start_used']} to {r['end_used']}")
        )
        ci = f"{_fmt(r['smd'])} ({_fmt(r['smd_lo'])} to {_fmt(r['smd_hi'])})"
        cells = [
            r["measure"],
            r["window"],
            used or "",
            r["summary_step"],
            r["summary_not"],
            r["summary_no"],
            ci,
        ]
        out += "| " + " | ".join(str(c) for c in cells) + " |\n"
    return out


def render_markdown(
    screen: pl.DataFrame,
    trends: pl.DataFrame,
    coverage_gap: float | dict[str, float],
    label: str,
    threshold: float = 0.10,
    self_report_measures: dict[str, list[str]] | None = None,
) -> str:
    """DISCORDANCE.md: per comparison, the stage-1 leads (band "lead"), in neutral wording.

    `screen` is the stage-1 screen with comparison and censored columns; `trends` may be empty
    (stage 2 not yet run). `coverage_gap` is the KL-coverage gap between the two "Yes" groups,
    one number for every comparison or one per comparison; above `threshold` the KL rows carry
    a caveat and are not listed as leads. Steps and MV minutes define the groups, and so do the
    measures built from a comparison's own self-report (`self_report_measures`, per comparison:
    e.g. PASE walking for the PASE comparison), so they are shown as context, never as leads.
    """

    def gap(c: str) -> float:
        # fail closed: a missing, null or NaN gap counts as above the threshold
        g = coverage_gap.get(c) if isinstance(coverage_gap, dict) else coverage_gap
        return float("inf") if g is None or g != g else float(g)

    lines = [
        f"# Self-reported walkers by device walking status [{label}]",
        "",
        f'Stage 1 compares "{GROUPS[1]}" with "{GROUPS[0]}" on each measure: the level at the '
        "anchor visit, the change up to it and the change after it, and fixed measures. The "
        "difference is a standardized mean difference (SMD), the second group minus the first, "
        "with a bootstrap 95% CI; categorical SMDs are unsigned. A lead is |SMD| >= 0.2, a "
        "reading rule fixed in the ledger before computing. Leads point to measures worth a "
        f'closer look; they are not tests. "{GROUPS[2]}" is shown for reference only. The '
        "self-report and the device may capture different aspects of walking, so a difference "
        "describes the groups and does not say which source is right. Full table: "
        "discordance_screen.csv.",
        "",
    ]
    comparisons = (
        screen["comparison"].unique(maintain_order=True).to_list() if screen.height else []
    )
    for c in comparisons:
        rows = screen.filter(pl.col("comparison") == c)
        main = rows.filter(~pl.col("censored"))
        flagged = gap(c) > threshold
        defining = [*DEFINING, *(self_report_measures or {}).get(c, [])]
        lead = main.filter(
            (pl.col("band") == "lead")
            & ~pl.col("measure").is_in(defining)
            & ~(pl.lit(flagged) & (pl.col("measure") == "kl_worse"))
        ).sort("area", "measure", "window")
        lines += [f"## {c}", "", "### Leads", ""]
        if lead.height:
            lines += [_md_table(lead)]
        else:
            lines += ["No measure reaches |SMD| >= 0.2.", ""]
        sens = rows.filter(
            pl.col("censored")
            & (pl.col("band") == "lead")
            & ~pl.col("measure").is_in(defining)
            & ~(pl.lit(flagged) & (pl.col("measure") == "kl_worse"))
        )
        if sens.height:
            lines += [
                "### Knee-level leads with replaced knees censored (sensitivity)",
                "",
                _md_table(sens.sort("measure", "window")),
            ]
        if flagged:
            size = (
                f"largest gap {100 * gap(c):.0f} percentage points at a visit"
                if gap(c) != float("inf")
                else "the gap could not be computed"
            )
            lines += [
                "### KL coverage",
                "",
                f'KL readings may cover the two "Yes" groups differently ({size}; '
                "discordance_kl_coverage.csv), so the KL rows are reported in the CSV with this "
                "caveat and are not listed as leads.",
                "",
            ]
        context = main.filter(pl.col("measure").is_in(defining))
        if context.height:
            lines += [
                "### Measures that define the groups (context, not findings)",
                "",
                _md_table(context.sort("measure", "window")),
            ]
    lines += ["## Stage 2: trajectories", ""]
    if trends.height == 0:
        lines += ["Not yet run.", ""]
    else:
        lines += ["See discordance_trends.csv.", ""]
    return "\n".join(lines)
