"""GT1M steps at 48 and 72 months and knee OA: person and knee frames (pure functions on frames).

Spec: docs/superpowers/specs/2026-11-12-steps-oa-design.md. Device measures are walking_steps'
person-wave measures (oai.derive.devices.person_wave); a person enters with valid wear at 48
months (V06), whether or not their steps are usable. Changes are 72 minus 48 months. Knee
outcomes come from oai.derive.knee_outcomes with the anchor at V06; the table reading is in
build_frame.py.

An unknown knee stays null. A person-level reverse exposure is null only when every knee is
unknown; otherwise it is True when any knee had the event (or the count of such knees).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import polars as pl

from oai.assumptions import Resolved
from oai.derive import knee_outcomes as ko
from oai.derive.devices import COVARIATES

ANCHOR = "06"
KEYS = ["ID", "SIDE"]
WAVES = {"06": "48", "08": "72"}
MEASURES = ("steps", "mv_min", "wear_hr")
CHANGES = ("steps", "mv_min")
PERSON_COLUMNS = (
    "ID", "valid72",
    "steps_48", "steps_72", "steps_change", "mv_min_48", "mv_min_72", "mv_min_change",
    "wear_hr_48", "wear_hr_72", "steps_band", *COVARIATES,
)  # fmt: skip
REVERSE_COLUMNS = (
    "ID", "new_oa_36_48", "new_oa_count_36_48", "new_oa_48_72", "new_oa_count_48_72",
    "new_oa_read_48_72",
)  # fmt: skip
REVERSE_VISITS = ("05", "06", "08")
BASE_COLUMNS = ("kl48", "womac48", "roa48", "sx48")


# ---------------------------------------------------------------- persons


def band_labels(edges: Sequence[int]) -> list[str]:
    """lt<e0>, <e0>_<e1 - 1>, ..., ge<eN> for ascending cut points."""
    edges = [int(e) for e in edges]
    middle = [f"{lo}_{hi - 1}" for lo, hi in zip(edges, edges[1:], strict=False)]
    return [f"lt{edges[0]}", *middle, f"ge{edges[-1]}"]


def steps_band(steps: pl.Expr, edges: Sequence[int]) -> pl.Expr:
    """The `band_labels` band of steps/day (each band includes its lower edge); null stays null."""
    labels = band_labels(edges)
    expr = pl.when(steps.is_null()).then(None)
    for edge, label in zip(edges, labels, strict=False):
        expr = expr.when(steps < edge).then(pl.lit(label))
    return expr.otherwise(pl.lit(labels[-1]))


def person_frame(device: pl.DataFrame, covariates: pl.DataFrame, A: Resolved) -> pl.DataFrame:
    """One row per person with valid wear at 48 months (PERSON_COLUMNS).

    `device` is ID, wave ("06"/"08"), valid, steps, mv_min, wear_hr. A person valid at 48 months
    only has valid72 False and null 72-month measures; steps null with valid counts keep the
    count measures (mv_min). `steps_band` is the 48-month band of `steps.bands`.
    """
    valid = device.filter("valid")
    base = valid.filter(pl.col("wave") == "06").select(
        "ID", *[pl.col(m).alias(f"{m}_48") for m in MEASURES]
    )
    later = valid.filter(pl.col("wave") == "08").select(
        "ID", pl.lit(True).alias("valid72"), *[pl.col(m).alias(f"{m}_72") for m in MEASURES]
    )
    return (
        base.join(later, on="ID", how="left")
        .with_columns(pl.col("valid72").fill_null(False))
        .join(covariates, on="ID", how="left")
        .with_columns(
            *[(pl.col(f"{m}_72") - pl.col(f"{m}_48")).alias(f"{m}_change") for m in CHANGES],
            steps_band(pl.col("steps_48"), A["steps.bands"]).alias("steps_band"),
        )
        .select(PERSON_COLUMNS)
        .sort("ID")
    )


# ---------------------------------------------------------------- reverse exposures


def _new_roa(before: str, after: str) -> pl.Expr:
    """True: no ROA before, ROA after; False: ROA already before, or none after; else null."""
    a, b = pl.col(f"roa_{before}"), pl.col(f"roa_{after}")
    return (
        pl.when(a == True)  # noqa: E712
        .then(False)
        .when(b == False)  # noqa: E712
        .then(False)
        .when((a == False) & (b == True))  # noqa: E712
        .then(True)
    )


def _new_replacement(before: str, after: str) -> pl.Expr:
    return pl.col(f"replaced_{after}") & ~pl.col(f"replaced_{before}")


def _person(flag: str, name: str, count: bool = True) -> list[pl.Expr]:
    known = pl.col(flag).is_not_null().sum()
    n = pl.col(flag).fill_null(False).cast(pl.Int64).sum()
    out = [pl.when(known == 0).then(None).otherwise(n > 0).alias(f"new_oa_{name}")]
    if count:
        out.append(pl.when(known == 0).then(None).otherwise(n).alias(f"new_oa_count_{name}"))
    return out


def reverse_exposures(status: pl.DataFrame, A: Resolved) -> pl.DataFrame:
    """REVERSE_COLUMNS: one row per person in `status`.

    `status` is knee_status (anchor V06) at V05, V06 and V08 plus `kl_p15`, Project 15's KL at
    V05 and V06. Per knee (null where unknown, Kleene logic):
      36_48       new ROA (V05 -> V06), a new replacement, or a Project 15 KL rise V05 -> V06
      48_72       new ROA (V06 -> V08) or a new replacement
      read_48_72  48_72, or a KL rise V06 -> V08 in a knee read at V08 (knee_status grades);
                  an unread knee adds no rise
    A knee replaced at the window's start has no new event (False). Per person: any knee
    (`new_oa_*`) or the number of knees (`new_oa_count_*`); null when every knee is unknown.
    `A` is taken for the analysis's interface; no setting changes these rules.
    """
    missing = sorted(set(REVERSE_VISITS) - set(status["visit"].unique()))
    if missing:
        raise ValueError(f"reverse_exposures: status lacks visits {missing}")
    wide = status.filter(pl.col("visit").is_in(REVERSE_VISITS)).pivot(
        on="visit", index=KEYS, values=["roa", "replaced", "kl", "read", "kl_p15"]
    )
    replaced = lambda v: pl.col(f"replaced_{v}").fill_null(False)  # noqa: E731
    wide = wide.with_columns(*[replaced(v).alias(f"replaced_{v}") for v in REVERSE_VISITS])
    rise_36_48 = pl.col("kl_p15_06") > pl.col("kl_p15_05")
    # a knee without a KL grade at V06 or V08 (unread, or read without a grade) adds no rise
    rise_read = (
        pl.col("read_08").fill_null(False) & (pl.col("kl_08") > pl.col("kl_06"))
    ).fill_null(False)
    w_48_72 = _new_roa("06", "08") | _new_replacement("06", "08")
    knees = wide.select(
        "ID",
        pl.when(replaced("05"))
        .then(False)
        .otherwise(_new_roa("05", "06") | _new_replacement("05", "06") | rise_36_48)
        .alias("k_36_48"),
        pl.when(replaced("06")).then(False).otherwise(w_48_72).alias("k_48_72"),
        pl.when(replaced("06")).then(False).otherwise(w_48_72 | rise_read).alias("k_read"),
    )
    return (
        knees.group_by("ID")
        .agg(
            *_person("k_36_48", "36_48"),
            *_person("k_48_72", "48_72"),
            *_person("k_read", "read_48_72", count=False),
        )
        .select(REVERSE_COLUMNS)
        .sort("ID")
    )


# ---------------------------------------------------------------- knee samples and frames


def risk_grades(value: str) -> list[float]:
    """ "2-3" -> [2.0, 3.0] (progression.risk_kl)."""
    lo, hi = (int(x) for x in value.split("-"))
    return [float(k) for k in range(lo, hi + 1)]


def knee_base(status: pl.DataFrame, womac: pl.DataFrame, anchor: str = ANCHOR) -> pl.DataFrame:
    """ID, SIDE, kl48, womac48, roa48, sx48: the knee at the anchor (`womac` is ID, SIDE, womac)."""
    return (
        status.filter(pl.col("visit") == anchor)
        .select(
            *KEYS,
            pl.col("kl").alias("kl48"),
            pl.col("roa").alias("roa48"),
            pl.col("sx").alias("sx48"),
        )  # fmt: skip
        .join(womac.rename({"womac": "womac48"}), on=KEYS, how="left")
        .select(*KEYS, *BASE_COLUMNS)
    )


def incidence_sample(
    status: pl.DataFrame, outcome: str, anchor: str, A: Resolved, pain_visit: str = ANCHOR
) -> pl.DataFrame:
    """ID, SIDE: knees at risk of `outcome` at `anchor`. Under sample.exclude_baseline_pain,
    incident ROA also needs no frequent pain (sx known False) at `pain_visit` (48 months)."""
    knees = ko.at_risk(status, outcome, anchor)
    if outcome == "roa" and A["sample.exclude_baseline_pain"]:
        painless = status.filter((pl.col("visit") == pain_visit) & (pl.col("sx") == False))  # noqa: E712
        knees = knees.join(painless.select(KEYS), on=KEYS, how="semi")
    return knees


def with_person(knees: pl.DataFrame, base: pl.DataFrame, persons: pl.DataFrame) -> pl.DataFrame:
    """Knee rows with the knee's 48-month columns and the person's (people valid at 48 months)."""
    return (
        knees.join(base, on=KEYS, how="left")
        .join(persons, on="ID", how="inner")
        .sort(*KEYS, *(["period"] if "period" in knees.columns else []))
    )


def progression_frame(
    status: pl.DataFrame, horizon: str, risk: Sequence[float] | None, A: Resolved
) -> pl.DataFrame:
    """KL and JSN worsening from V06 to `horizon` for knees whose V06 KL is in `risk`.

    ID, SIDE, base_kl, kl_event, kl_read (read at the horizon), max_kl, kl_incident, kl_to_4,
    kl_any, transition; jsm_base, jsm_event, jsl_base, jsl_event, and jsn_event (medial or
    lateral, null when neither is known and neither worsened). Unread knees stay, with null
    outcomes.
    """
    rule = A["progression.jsn_rule"]
    kl = ko.progression(
        status, "kl", ANCHOR, horizon, risk, rule,
        replacement_as_kl4=bool(A["progression.replacement_as_kl4"]),
    ).rename({"event": "kl_event", "read_at_horizon": "kl_read"}).drop("base")  # fmt: skip
    out = kl
    for measure in ("jsm", "jsl"):
        jsn = ko.progression(status, measure, ANCHOR, horizon, None, rule).select(
            *KEYS,
            pl.col("base").alias(f"{measure}_base"),
            pl.col("event").alias(f"{measure}_event"),
        )
        out = out.join(jsn, on=KEYS, how="left")
    return out.with_columns((pl.col("jsm_event") | pl.col("jsl_event")).alias("jsn_event")).sort(
        KEYS
    )


# ---------------------------------------------------------------- flow and descriptives


def knee_events(frame: pl.DataFrame, event: str) -> pl.DataFrame:
    """ID, SIDE, steps_band, event: one row per knee (a period frame's knee had any event)."""
    return frame.group_by(*KEYS, "steps_band").agg(
        pl.when(pl.col(event).is_not_null().any()).then(pl.col(event).fill_null(False).any())
        .alias("event")
    )  # fmt: skip


def frame_flow(sample: str, frame: pl.DataFrame, event: str) -> list[dict]:
    """people, knees, rows, knees_known and events for one knee frame."""
    knees = knee_events(frame, event)
    return [
        {"sample": sample, "step": "people", "n": frame["ID"].n_unique()},
        {"sample": sample, "step": "knees", "n": knees.height},
        {"sample": sample, "step": "rows", "n": frame.height},
        {"sample": sample, "step": "knees_known", "n": knees["event"].is_not_null().sum()},
        {"sample": sample, "step": "events", "n": int(knees["event"].fill_null(False).sum())},
    ]


def selection_flow(sample: str, counts: pl.DataFrame) -> list[dict]:
    """selection_counts rows as flow rows: V<visit>_at_risk, _read, _unread, _read_P<project>."""
    rows = []
    for (visit,), d in counts.group_by("visit", maintain_order=True):
        first = d.row(0, named=True)
        for what in ("knees_at_risk", "read", "unread"):
            rows.append({"sample": sample, "step": f"V{visit}_{what}", "n": first[what]})
        for r in d.filter(pl.col("readprj").is_not_null()).iter_rows(named=True):
            rows.append(
                {"sample": sample, "step": f"V{visit}_read_P{r['readprj']}", "n": r["knees"]}
            )
    return rows


DESCRIPTIVE_SCHEMA = {
    "table": pl.String,
    "outcome": pl.String,
    "level": pl.String,
    "n": pl.Int64,
    "events": pl.Int64,
    "mean": pl.Float64,
    "sd": pl.Float64,
}


def by_band(table: str, outcome: str, knees: pl.DataFrame, event: str, A: Resolved) -> list[dict]:
    """n (knees with `event` known) and events per 48-month step band (null band left out)."""
    rows = []
    for band in band_labels(A["steps.bands"]):
        d = knees.filter((pl.col("steps_band") == band) & pl.col(event).is_not_null())
        rows.append(
            {"table": table, "outcome": outcome, "level": band, "n": d.height,
             "events": int(d[event].sum())}
        )  # fmt: skip
    return rows


def steps_by(table: str, persons: pl.DataFrame, group: str) -> list[dict]:
    """n, mean and SD of steps_48 per level of `group` (people with steps and the group known)."""
    d = persons.filter(pl.col(group).is_not_null() & pl.col("steps_48").is_not_null())
    rows = []
    for (level,), g in d.group_by(group):
        rows.append(
            {"table": table, "outcome": "steps_48", "level": str(level), "n": g.height,
             "mean": g["steps_48"].mean(), "sd": g["steps_48"].std()}
        )  # fmt: skip
    return sorted(rows, key=lambda r: r["level"])


def soa_person(status: pl.DataFrame, anchor: str = ANCHOR) -> pl.DataFrame:
    """ID, soa48: SOA in either knee at the anchor; False only when both knees are known free."""
    return (
        status.filter(pl.col("visit") == anchor)
        .group_by("ID")
        .agg(
            pl.when(pl.col("soa").fill_null(False).any())
            .then(True)
            .when(pl.col("soa").is_not_null().all())
            .then(False)
            .alias("soa48")
        )
    )


def agreement(kl: pl.DataFrame, roa99: pl.DataFrame) -> list[dict]:
    """2x2 of reading-based kl_incident (0-1 -> 2+) against OUTCOMES99 incident ROA, knees with
    both known. `kl` is ID, SIDE, kl_incident; `roa99` is ID, SIDE, event."""
    both = kl.join(roa99, on=KEYS, how="inner").filter(
        pl.col("kl_incident").is_not_null() & pl.col("event").is_not_null()
    )
    rows = []
    for a in (True, False):
        for b in (True, False):
            n = both.filter((pl.col("kl_incident") == a) & (pl.col("event") == b)).height
            rows.append(
                {"table": "agreement_kl_incident_roa99", "outcome": "kl_incident/roa99",
                 "level": f"{str(a).lower()}/{str(b).lower()}", "n": n}
            )  # fmt: skip
    return rows


def descriptives(
    case_frames: Mapping[str, tuple[pl.DataFrame, str]],
    persons: pl.DataFrame,
    soa48: pl.DataFrame,
    progression: pl.DataFrame,
    transitions: pl.DataFrame,
    agreement_rows: list[dict],
    A: Resolved,
) -> pl.DataFrame:
    """The descriptives table (DESCRIPTIVE_SCHEMA).

    cases_by_band        per outcome frame: knees with a known outcome and cases, by band
    steps_by_kl_max      steps_48 by the higher Project 15 KL at 48 months (R3)
    steps_by_soa48       steps_48 by SOA in either knee at 48 months (R3)
    worsening_by_band    KL and JSN worsening among read knees of the progression sample
    transitions_by_band  KL transitions (0-1>2+, 2-3>4, any) among read knees, all V06 grades
    agreement_...        `agreement`
    """
    rows = []
    for name, (frame, event) in case_frames.items():
        rows += by_band("cases_by_band", name, knee_events(frame, event), "event", A)
    rows += steps_by("steps_by_kl_max", persons, "kl_max")
    rows += steps_by("steps_by_soa48", persons.join(soa48, on="ID", how="left"), "soa48")
    for event in ("kl_event", "jsn_event"):
        rows += by_band("worsening_by_band", event, progression, event, A)
    for flag, label in (("kl_incident", "0-1>2+"), ("kl_to_4", "2-3>4"), ("kl_any", "any")):
        rows += by_band("transitions_by_band", label, transitions, flag, A)
    rows += agreement_rows
    return pl.DataFrame(rows, schema=DESCRIPTIVE_SCHEMA)
