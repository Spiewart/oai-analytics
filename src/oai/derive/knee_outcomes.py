"""Knee-level incidence and progression outcomes from any anchor visit.

Spec: docs/superpowers/specs/2026-11-12-knee-outcomes-module-design.md. Both knees (`SIDE`),
one anchor visit (baseline "00" for luyten_early_oa, "06" for steps_oa). Every function but
`knee_status` is pure on frames.

  knee_status       ID, SIDE, visit, roa, sx, soa, replaced, kl, jsm, jsl, read, readprj
  at_risk           knees with the outcome known absent, and not replaced, at the anchor
  periods           discrete-time rows between consecutive visits with a known outcome
  by_horizon        incident by a horizon visit (luyten_early_oa's rule, keyed by knee)
  progression       KL / JSM / JSL worsening after the anchor, plus KL transition flags
  selection_counts  read and unread knees per visit and reading project

An unread knee is null, never False. Settings come from the analysis's ledger, with defaults
where it lacks a key (`incident_soa.setting`):
  outcomes.roa_replacement     "ignore" | "event" (a replaced knee has ROA)
  readings.followup_project    "latest" (43, then 37) | "p37"
  readings.anchor_project      "followup" | "p15"
  progression.jsn_rule         "whole_grade" | "within_grade" (the analysis passes it as `rule`)
  progression.replacement_as_kl4  true (the analysis passes it as `replacement_as_kl4`)
"""

from __future__ import annotations

import dataclasses
from collections.abc import Collection, Mapping, Sequence

import polars as pl

from oai.assumptions import Resolved
from oai.derive.incident_soa import setting, soa_status
from oai.derive.knee import prefer_projects, xray_readings

SIDES = ("R", "L")
KEYS = ["ID", "SIDE"]
STATUS_COLUMNS = (
    "ID", "SIDE", "visit", "roa", "sx", "soa", "replaced", "kl", "jsm", "jsl", "read", "readprj",
)  # fmt: skip
OUTCOMES = ("roa", "soa")
MEASURES = ("kl", "jsm", "jsl")
SELECTIONS = ("known_or_case", "complete")
RULES = ("whole_grade", "within_grade")
ROA_REPLACEMENT = ("ignore", "event")
ANCHOR_PROJECT = ("followup", "p15")
# kXR_SQ_BU_Descrip.pdf: Projects 37 (42 recoded) and 43 read 48 months onwards
FOLLOWUP_PROJECTS = {"latest": (43, 37), "p37": (37,)}
FIRST_FOLLOWUP_ANCHOR = "06"
KL_REPLACED = 4.0
KL_ROA = 2


def _choice(A: Resolved, key: str, default: str, choices: Collection[str]) -> str:
    value = setting(A, key, default)
    if value not in choices:
        raise ValueError(f"{key} must be one of {sorted(choices)}, not {value!r}")
    return value


def for_side(A: Resolved, side: str) -> Resolved:
    """`A` with `cohort.side` set, for oai.derive.incident_soa's one-knee functions."""
    return dataclasses.replace(A, values={**A.values, "cohort.side": side})


def reading_projects(A: Resolved, visit: str, anchor: str) -> tuple[int, ...]:
    """Reading projects for `visit`, in preference order.

    Project `cohort.reading_project` (15) before the anchor, and throughout when the anchor is
    before V06. At and after an anchor of V06 or later, `readings.followup_project`, so the
    anchor and follow-up grades come from one reading project; `readings.anchor_project =
    "p15"` takes the anchor grade from Project 15 instead.
    """
    base = (int(setting(A, "cohort.reading_project", 15)),)
    followup = FOLLOWUP_PROJECTS[
        _choice(A, "readings.followup_project", "latest", FOLLOWUP_PROJECTS)
    ]
    anchor_rule = _choice(A, "readings.anchor_project", "followup", ANCHOR_PROJECT)
    if anchor < FIRST_FOLLOWUP_ANCHOR or visit < anchor:
        return base
    if visit == anchor and anchor_rule == "p15":
        return base
    return followup


def assemble_status(
    soa_frames: Mapping[str, pl.DataFrame], readings: pl.DataFrame, A: Resolved, anchor: str
) -> pl.DataFrame:
    """The knee_status frame from per-side soa_status frames ({side: frame}) and readings
    (xray_readings-shaped, any projects): one row per ID x SIDE x visit of the soa frames."""
    rule = _choice(A, "outcomes.roa_replacement", "ignore", ROA_REPLACEMENT)
    status = pl.concat(
        [
            frame.select(
                pl.col("ID").cast(pl.Int64),
                pl.lit(side).alias("SIDE"),
                "visit",
                "roa",
                "sx",
                "soa",
                pl.col("replaced").fill_null(False),
            )
            for side, frame in soa_frames.items()
        ]
    )
    if rule == "event":
        status = status.with_columns((pl.col("roa") | pl.col("replaced")).alias("roa"))
    picked = [
        prefer_projects(
            readings.filter(pl.col("visit") == visit), reading_projects(A, visit, anchor)
        )
        for visit in status["visit"].unique().sort()
    ]
    reads = pl.concat(picked).select(
        pl.col("ID").cast(pl.Int64),
        "SIDE",
        "visit",
        pl.col("KL").alias("kl"),
        pl.col("JSM").alias("jsm"),
        pl.col("JSL").alias("jsl"),
        pl.lit(True).alias("read"),
        pl.col("READPRJ").cast(pl.Int64).alias("readprj"),
    )
    return (
        status.join(reads, on=[*KEYS, "visit"], how="left")
        .with_columns(pl.col("read").fill_null(False))
        .sort(*KEYS, "visit")
        .select(STATUS_COLUMNS)
    )


def knee_status(A: Resolved, visits: Sequence[str], anchor: str) -> pl.DataFrame:
    """ID, SIDE, visit, roa, sx, soa, replaced, kl, jsm, jsl, read, readprj for both knees.

    `roa`, `sx`, `soa` and `replaced` are oai.derive.incident_soa.soa_status's for each side
    (its visits follow `periods.horizon`; every visit in `visits` must be among them). `kl`,
    `jsm` and `jsl` come from the reading projects of `reading_projects`.
    """
    visits = sorted(set(visits))
    if anchor not in visits:
        raise ValueError(f"anchor V{anchor} is not among visits {visits}")
    soa = {}
    for side in SIDES:
        frame = soa_status(for_side(A, side))
        missing = sorted(set(visits) - set(frame["visit"].unique()))
        if missing:
            raise ValueError(f"soa_status has no visits {missing}; check periods.horizon")
        soa[side] = frame.filter(pl.col("visit").is_in(visits))
    readings = pl.concat(
        [xray_readings([v], project=reading_projects(A, v, anchor)) for v in visits]
    )
    return assemble_status(soa, readings, A, anchor)


def _outcome(outcome: str) -> str:
    if outcome not in OUTCOMES:
        raise ValueError(f"outcome must be one of {OUTCOMES}, not {outcome!r}")
    return outcome


def at_risk(status: pl.DataFrame, outcome: str, anchor: str) -> pl.DataFrame:
    """ID, SIDE: knees whose `outcome` is known False at `anchor` and not replaced there."""
    return status.filter(
        (pl.col("visit") == anchor)
        & (pl.col(_outcome(outcome)) == False)  # noqa: E712 (null is not at risk)
        & ~pl.col("replaced").fill_null(False)
    ).select(KEYS)


def _earlier(flag: pl.Expr) -> pl.Expr:
    """True where a previous row of the same knee had `flag` True (frame sorted by visit)."""
    return flag.fill_null(False).cast(pl.Int64).cum_sum().shift(1, fill_value=0).over(KEYS) > 0


def periods(status: pl.DataFrame, outcome: str, anchor: str, horizon: str) -> pl.DataFrame:
    """ID, SIDE, period, end_visit, span, event for the knees `at_risk` at `anchor`.

    One row per visit after the anchor, up to `horizon`, at which `outcome` is known; `span`
    counts the scheduled visits (those in `status`) since the previous known visit, so an
    unknown middle visit gives a span of 2. Rows stop after the first event, and after the
    first visit at which the knee is replaced (censored there when the replacement is not
    itself the event).
    """
    schedule = sorted(v for v in status["visit"].unique() if anchor < v <= horizon)
    position = {v: i + 1 for i, v in enumerate(schedule)}
    rows = (
        status.join(at_risk(status, outcome, anchor), on=KEYS, how="semi")
        .filter(pl.col("visit").is_in(schedule))
        .sort(*KEYS, "visit")
        .filter(~_earlier(pl.col("replaced")))
        .filter(pl.col(outcome).is_not_null())
        .with_columns(pl.col("visit").replace_strict(position, return_dtype=pl.Int64).alias("_pos"))
    )
    rows = rows.filter(~_earlier(pl.col(outcome))).with_columns(
        (pl.col("_pos") - pl.col("_pos").shift(1, fill_value=0).over(KEYS)).alias("span"),
        (pl.int_range(pl.len()).over(KEYS) + 1).cast(pl.Int64).alias("period"),
    )
    return rows.select(
        *KEYS, "period", pl.col("visit").alias("end_visit"), "span", pl.col(outcome).alias("event")
    )


def by_horizon(
    status: pl.DataFrame, outcome: str, anchor: str, horizon: str, selection: str
) -> pl.DataFrame:
    """ID, SIDE, event: `outcome` True at any visit after `anchor`, up to `horizon`.

    False when the horizon visit's value is known and no earlier visit is True; null otherwise
    (`known_or_case`). Under `complete` the horizon visit's value must be known even for a case.
    A knee True at the anchor is prevalent, not incident: null.
    """
    if selection not in SELECTIONS:
        raise ValueError(f"selection must be one of {SELECTIONS}, not {selection!r}")
    column = pl.col(outcome)
    at_horizon = column.filter(pl.col("visit") == horizon).first()
    return (
        status.filter((pl.col("visit") >= anchor) & (pl.col("visit") <= horizon))
        .group_by(KEYS, maintain_order=True)
        .agg(
            column.filter(pl.col("visit") == anchor).first().alias("_base"),
            column.filter(pl.col("visit") > anchor).fill_null(False).any().alias("_case"),
            at_horizon.alias("_last"),
        )
        .select(
            *KEYS,
            pl.when(pl.col("_base").fill_null(False))
            .then(None)
            .when(pl.col("_last").is_null() & (pl.lit(selection == "complete") | ~pl.col("_case")))
            .then(None)
            .otherwise(pl.col("_case"))
            .alias("event"),
        )
    )


def _kl_transitions() -> list[pl.Expr]:
    """base_kl, max_kl and the transition flags; null where no follow-up was read."""
    base, top = pl.col("base"), pl.col("max_kl")
    read = top.is_not_null()
    label = (
        pl.when(~read)
        .then(None)
        .when(top <= base)
        .then(pl.lit("none"))
        .when((base < KL_ROA) & (top >= KL_ROA))
        .then(pl.lit("0-1>2+"))
        .when((base >= KL_ROA) & (top >= KL_REPLACED))
        .then(pl.lit("2-3>4"))
        .otherwise(pl.format("{}>{}", base.cast(pl.Int64), top.cast(pl.Int64)))
    )
    return [
        base.alias("base_kl"),
        top,
        pl.when(read & (base < KL_ROA)).then(top >= KL_ROA).alias("kl_incident"),
        pl.when(read & (base >= KL_ROA) & (base < KL_REPLACED))
        .then(top >= KL_REPLACED)
        .alias("kl_to_4"),
        pl.when(read & (base < KL_REPLACED)).then(top > base).alias("kl_any"),
        label.alias("transition"),
    ]


def progression(
    status: pl.DataFrame,
    measure: str,
    anchor: str,
    horizon: str,
    risk: Collection[float] | None,
    rule: str = "whole_grade",
    *,
    replacement_as_kl4: bool = True,
) -> pl.DataFrame:
    """ID, SIDE, base, event, read_at_horizon: `measure` worsening after `anchor`, to `horizon`.

    Knees with a `base` reading at the anchor in `risk` (any base when None), not replaced
    there. `event` is True when any read visit after the anchor, up to the horizon, is worse
    than base: `whole_grade` = floor(follow-up) >= floor(base) + 1, `within_grade` = follow-up >
    base. Otherwise False when the horizon visit was read, else null.

    For `measure = "kl"` it adds base_kl, max_kl (the highest follow-up grade), kl_incident
    (base 0-1 -> 2+), kl_to_4 (base 2-3 -> 4), kl_any (any rise) and transition ("0-1>2+",
    "2-3>4", "2>3", "none", ...). Each flag is null outside its base grades and where no
    follow-up was read. Under `replacement_as_kl4`, a visit at which the knee is replaced
    counts as a KL 4 reading, for `event` and the flags alike.
    """
    if measure not in MEASURES:
        raise ValueError(f"measure must be one of {MEASURES}, not {measure!r}")
    if rule not in RULES:
        raise ValueError(f"rule must be one of {RULES}, not {rule!r}")
    base = status.filter(
        (pl.col("visit") == anchor)
        & ~pl.col("replaced").fill_null(False)
        & pl.col(measure).is_not_null()
    ).select(*KEYS, pl.col(measure).alias("base"))
    if risk is not None:
        base = base.filter(pl.col("base").is_in(list(risk)))
    value = pl.col(measure)
    if measure == "kl" and replacement_as_kl4:
        value = pl.when(pl.col("replaced").fill_null(False)).then(KL_REPLACED).otherwise(value)
    follow = (
        status.filter((pl.col("visit") > anchor) & (pl.col("visit") <= horizon))
        .join(base, on=KEYS, how="inner")
        .with_columns(value.alias("_value"))
    )
    if rule == "whole_grade":
        worse = pl.col("_value").floor() >= pl.col("base").floor() + 1
    else:
        worse = pl.col("_value") > pl.col("base")
    summary = follow.group_by(KEYS).agg(
        worse.fill_null(False).any().alias("_case"),
        pl.col(measure).filter(pl.col("visit") == horizon).first().is_not_null().alias("_read"),
        pl.col("_value").max().alias("max_kl"),
    )
    out = base.join(summary, on=KEYS, how="left").with_columns(
        pl.col("_read").fill_null(False).alias("read_at_horizon"),
        pl.when(pl.col("_case").fill_null(False))
        .then(True)
        .when(pl.col("_read").fill_null(False))
        .then(False)
        .alias("event"),
    )
    columns = [*KEYS, "base", "event", "read_at_horizon"]
    if measure == "kl":
        return out.select(*columns, *_kl_transitions())
    return out.select(columns)


def selection_counts(status: pl.DataFrame, anchor: str, visits: Sequence[str]) -> pl.DataFrame:
    """visit, knees_at_risk, read, unread, readprj, knees: selective follow-up per visit.

    `status` holds the knees to count (e.g. joined to `at_risk`); a knee replaced by a visit
    leaves that visit's count. One row per visit and reading project (`knees` read by it), and
    one with readprj null for the unread knees. `anchor` is the visit the knees were selected
    at; it is counted only when it is in `visits`.
    """
    rows = status.filter(
        pl.col("visit").is_in(list(visits))
        & (pl.col("visit") >= anchor)
        & ~pl.col("replaced").fill_null(False)
    ).select(
        "visit",
        pl.col("read").fill_null(False).alias("read"),
        pl.when(pl.col("read").fill_null(False)).then(pl.col("readprj")).alias("readprj"),
    )
    totals = rows.group_by("visit").agg(
        pl.len().cast(pl.Int64).alias("knees_at_risk"),
        pl.col("read").sum().cast(pl.Int64).alias("read"),
    )
    cells = rows.group_by("visit", "readprj").agg(pl.len().cast(pl.Int64).alias("knees"))
    return (
        totals.with_columns((pl.col("knees_at_risk") - pl.col("read")).alias("unread"))
        .join(cells, on="visit", how="left")
        .sort("visit", "readprj", nulls_last=True)
        .select("visit", "knees_at_risk", "read", "unread", "readprj", "knees")
    )
