"""oai.derive.knee_outcomes on inline frames: reading projects, periods, by-horizon outcomes,
progression and KL transitions, and the selection counts."""

from pathlib import Path

import polars as pl
import pytest

from oai.assumptions import Resolved, load_assumptions
from oai.catalog import catalog_for
from oai.config import get_settings
from oai.derive.knee_outcomes import (
    STATUS_COLUMNS,
    assemble_status,
    at_risk,
    by_horizon,
    jsw_change_from,
    knee_status,
    periods,
    progression,
    replacement_times_from,
    selection_counts,
)

LUYTEN = Path(__file__).resolve().parents[1] / "analyses" / "luyten_early_oa"
LO2018_RELEASE = Path(__file__).parent / "fixtures" / "oai_lo2018"
FOLLOW = ("06", "08", "10")
LUYTEN_VISITS = ("00", "01", "03", "05", "06", "08", "10")
STATUS_SCHEMA = {
    "ID": pl.Int64,
    "SIDE": pl.String,
    "visit": pl.String,
    "roa": pl.Boolean,
    "sx": pl.Boolean,
    "soa": pl.Boolean,
    "replaced": pl.Boolean,
    "kl": pl.Float64,
    "jsm": pl.Float64,
    "jsl": pl.Float64,
    "read": pl.Boolean,
    "readprj": pl.Int64,
}
READINGS_SCHEMA = {
    "ID": pl.Int64,
    "SIDE": pl.String,
    "visit": pl.String,
    "KL": pl.Float64,
    "JSM": pl.Float64,
    "JSL": pl.Float64,
    "READPRJ": pl.Int64,
}


def resolved(**values):
    return Resolved(
        analysis="t", label="t", variant=None, overrides={}, values=values, origins={}, items={}
    )


def status(*knees, visits=FOLLOW):
    """A knee_status frame; each knee is (ID, SIDE, {column: one value per visit})."""
    rows = []
    for id_, side, columns in knees:
        for i, visit in enumerate(visits):
            row = {c: None for c in STATUS_SCHEMA}
            row.update(ID=id_, SIDE=side, visit=visit, replaced=False, read=False)
            row.update({c: v[i] for c, v in columns.items()})
            if row["read"] is False and row["kl"] is not None:
                row["read"] = True
            rows.append(row)
    return pl.DataFrame(rows, schema=STATUS_SCHEMA)


def soa_frame(visits=FOLLOW, **columns):
    """One knee's soa_status frame (ID 1)."""
    n = len(visits)
    data = {"ID": [1] * n, "visit": list(visits), "kl": [None] * n}
    for c in ("sx", "roa", "replaced", "soa"):
        data[c] = columns.get(c, [False] * n)
    schema = {"ID": pl.Int64, "visit": pl.String, "kl": pl.Float64}
    return pl.DataFrame(
        data, schema={**schema, **{c: pl.Boolean for c in ("sx", "roa", "replaced", "soa")}}
    )


def readings(*rows):
    """(ID, SIDE, visit, KL, READPRJ) rows; JSM and JSL follow KL."""
    return pl.DataFrame(
        [
            {"ID": i, "SIDE": s, "visit": v, "KL": kl, "JSM": kl, "JSL": kl, "READPRJ": p}
            for i, s, v, kl, p in rows
        ],
        schema=READINGS_SCHEMA,
    )


def one(df, id_=1, side="R"):
    return df.filter((pl.col("ID") == id_) & (pl.col("SIDE") == side)).row(0, named=True)


def value_at(df, visit, column, id_=1, side="R"):
    return df.filter((pl.col("ID") == id_) & (pl.col("SIDE") == side) & (pl.col("visit") == visit))[
        column
    ].item()


# ---------------------------------------------------------------- reading projects


def test_anchor_project():
    soa = {"R": soa_frame(visits=("00", "06", "08"))}
    reads = readings(
        (1, "R", "00", 0.0, 15),
        (1, "R", "00", 1.0, 43),  # Project 43 also read baseline: not used before the anchor
        (1, "R", "06", 1.0, 15),
        (1, "R", "06", 2.0, 43),
        (1, "R", "08", 3.0, 43),
    )
    followup = assemble_status(soa, reads, resolved(), "06")
    assert followup.columns == list(STATUS_SCHEMA)
    assert value_at(followup, "06", "kl") == 2.0
    assert value_at(followup, "06", "readprj") == 43
    assert value_at(followup, "00", "kl") == 0.0
    assert value_at(followup, "08", "kl") == 3.0
    p15 = assemble_status(soa, reads, resolved(**{"readings.anchor_project": "p15"}), "06")
    assert (value_at(p15, "06", "kl"), value_at(p15, "06", "readprj")) == (1.0, 15)
    assert value_at(p15, "08", "kl") == 3.0
    p37 = assemble_status(soa, reads, resolved(**{"readings.followup_project": "p37"}), "06")
    assert (value_at(p37, "06", "kl"), value_at(p37, "06", "readprj")) == (1.0, 15)  # fallback
    baseline = assemble_status(soa, reads, resolved(), "00")  # Project 15 throughout
    assert (value_at(baseline, "06", "kl"), value_at(baseline, "08", "read")) == (1.0, False)


def test_anchor_falls_back_to_project_15():
    # knee A: Projects 15 (KL 1) and 43 (KL 2) read V06; knee B: Project 15 only (KL 3)
    soa = {"R": soa_frame(visits=("06", "08")), "L": soa_frame(visits=("06", "08"))}
    reads = readings(
        (1, "R", "06", 1.0, 15),
        (1, "R", "06", 2.0, 43),
        (1, "L", "06", 3.0, 15),
        (1, "L", "08", 3.0, 15),  # Project 15 is never used after the anchor
    )
    followup = assemble_status(soa, reads, resolved(), "06")
    assert (value_at(followup, "06", "kl"), value_at(followup, "06", "readprj")) == (2.0, 43)
    b = (value_at(followup, "06", "kl", side="L"), value_at(followup, "06", "readprj", side="L"))
    assert b == (3.0, 15)
    assert value_at(followup, "08", "read", side="L") is False
    p15 = assemble_status(soa, reads, resolved(**{"readings.anchor_project": "p15"}), "06")
    assert (value_at(p15, "06", "kl"), value_at(p15, "06", "kl", side="L")) == (1.0, 3.0)


def test_unknown_ledger_values_are_rejected():
    soa = {"R": soa_frame()}
    with pytest.raises(ValueError, match="followup_project"):
        assemble_status(soa, readings(), resolved(**{"readings.followup_project": "x"}), "06")
    with pytest.raises(ValueError, match="roa_replacement"):
        assemble_status(soa, readings(), resolved(**{"outcomes.roa_replacement": "x"}), "06")


# ---------------------------------------------------------------- periods and at risk


def test_periods_span_unknown_visit():
    knees = status(
        (1, "R", {"roa": [False, None, True]}),
        (2, "R", {"roa": [False, False, False]}),
        (3, "R", {"roa": [False, True, None]}),
        (4, "R", {"roa": [True, True, True]}),
    )
    rows = periods(knees, "roa", "06", "10")
    assert rows.columns == ["ID", "SIDE", "period", "end_visit", "span", "event"]
    by_knee = {i: rows.filter(pl.col("ID") == i).drop("ID", "SIDE").rows() for i in (1, 2, 3, 4)}
    assert by_knee[1] == [(1, "10", 2, True)]
    assert by_knee[2] == [(1, "08", 1, False), (2, "10", 1, False)]
    assert by_knee[3] == [(1, "08", 1, True)]
    assert by_knee[4] == []
    assert at_risk(knees, "roa", "06").sort("ID")["ID"].to_list() == [1, 2, 3]


def test_replacement_event_vs_ignore():
    soa = {
        "R": soa_frame(
            roa=[False, False, False], replaced=[False, True, True], soa=[False, True, True]
        )
    }
    event = assemble_status(
        soa, readings(), resolved(**{"outcomes.roa_replacement": "event"}), "06"
    )
    assert periods(event, "roa", "06", "10").select("end_visit", "event").rows() == [("08", True)]
    for A in (resolved(**{"outcomes.roa_replacement": "ignore"}), resolved()):
        ignore = assemble_status(soa, readings(), A, "06")
        assert value_at(ignore, "08", "roa") is False
        rows = periods(ignore, "roa", "06", "10").select("end_visit", "event").rows()
        assert rows == [("08", False)]  # censored at the replacement


def test_at_risk_excludes_a_knee_replaced_at_the_anchor():
    knees = status((1, "R", {"roa": [False, False, False], "replaced": [True, True, True]}))
    assert at_risk(knees, "roa", "06").is_empty()


# ---------------------------------------------------------------- by horizon


def at(values, horizon, selection="known_or_case", anchor="00"):
    knees = status((1, "R", {"soa": values}), visits=LUYTEN_VISITS)
    out = by_horizon(knees, "soa", anchor, horizon, selection)
    assert out.columns == ["ID", "SIDE", "event"]
    return out["event"].item()


def test_by_horizon_anchor():
    # luyten_early_oa's by_horizon cases (tests/test_luyten_build.py), anchored at "00"
    case_at_24 = [False, False, True, True, None, None, None]
    assert (at(case_at_24, "06"), at(case_at_24, "10")) == (True, True)
    lost_after_48 = [False, False, False, False, False, None, None]
    assert (at(lost_after_48, "06"), at(lost_after_48, "10")) == (False, None)
    back_at_96 = [False, False, False, None, None, False, False]
    assert (at(back_at_96, "06"), at(back_at_96, "10")) == (None, False)
    assert at(case_at_24, "10", "complete") is None
    assert at([True] * 7, "10") is None
    # anchored at "06": V06 is the base; earlier visits are ignored
    earlier_case = [True, True, True, True, False, False, True]
    assert at(earlier_case, "10", anchor="06") is True
    assert at(earlier_case, "08", anchor="06") is False
    assert at([False, False, False, False, True, True, True], "10", anchor="06") is None
    assert at([False, False, False, False, False, None, None], "10", anchor="06") is None
    assert at([False, False, False, False, False, True, None], "10", anchor="06") is True
    assert at([False, False, False, False, False, True, None], "10", "complete", "06") is None


def test_by_horizon_replacement_under_event():
    # luyten's test_replacement_counts_as_roa_under_event, through assemble_status
    soa = {
        "R": soa_frame(
            visits=LUYTEN_VISITS,
            roa=[False, False, False, None, None, None, None],
            replaced=[False, False, False, True, True, True, True],
        )
    }
    roa = lambda rule: by_horizon(  # noqa: E731
        assemble_status(soa, readings(), resolved(**{"outcomes.roa_replacement": rule}), "00"),
        "roa",
        "00",
        "10",
        "known_or_case",
    )["event"].item()
    assert roa("event") is True
    assert roa("ignore") is None


def test_by_horizon_keys_by_knee():
    knees = status(
        (1, "R", {"soa": [False, False, True]}),
        (1, "L", {"soa": [False, False, False]}),
    )
    out = by_horizon(knees, "soa", "06", "10", "known_or_case")
    assert (one(out, side="R")["event"], one(out, side="L")["event"]) == (True, False)


# ---------------------------------------------------------------- progression


def test_progression_rules():
    knees = status(
        (1, "R", {"jsm": [1.0, None, 1.8]}),  # within-grade rise only
        (2, "R", {"jsm": [1.0, None, 2.0]}),  # whole grade
        (3, "R", {"jsm": [1.0, 1.0, None]}),  # unread at the horizon, no worsening seen
        (4, "R", {"jsm": [1.0, 2.0, None]}),  # worsened, then unread
        (5, "R", {"jsm": [3.0, 3.0, 3.0]}),  # outside the risk set
        visits=FOLLOW,
    )
    risk = {0, 1, 2}
    whole = progression(knees, "jsm", "06", "10", risk)
    within = progression(knees, "jsm", "06", "10", risk, rule="within_grade")
    assert whole.columns == ["ID", "SIDE", "base", "event", "read_at_horizon"]
    assert (one(whole, 1)["event"], one(within, 1)["event"]) == (False, True)
    assert one(whole, 2)["event"] is True
    row = one(whole, 3)
    assert (row["event"], row["read_at_horizon"]) == (None, False)
    assert one(whole, 4)["event"] is True
    assert 5 not in whole["ID"].to_list()
    with pytest.raises(ValueError, match="rule"):
        progression(knees, "jsm", "06", "10", risk, rule="halfway")


def test_kl_transitions():
    knees = status(
        (1, "R", {"kl": [1.0, 1.0, 2.0]}),
        (2, "R", {"kl": [3.0, 4.0, None]}),
        (3, "R", {"kl": [2.0, 3.0, 3.0]}),
        (4, "R", {"kl": [2.0, None, None]}),  # unread, not replaced
        (5, "R", {"kl": [3.0, None, None], "replaced": [False, True, True]}),
        (6, "R", {"kl": [0.0, 1.0, 1.0]}),
        (7, "R", {"kl": [2.0, 2.0, 2.0]}),
    )
    out = progression(knees, "kl", "06", "10", None)
    flags = ("max_kl", "kl_incident", "kl_to_4", "kl_any", "transition")
    assert out.columns == [
        "ID", "SIDE", "base", "event", "read_at_horizon", "base_kl", *flags,
    ]  # fmt: skip
    pick = lambda i, df=out: tuple(one(df, i)[c] for c in flags)  # noqa: E731
    assert pick(1) == (2.0, True, None, True, "0-1>2+")
    assert pick(2) == (4.0, None, True, True, "2-3>4")
    assert pick(3) == (3.0, None, False, True, "2>3")
    assert pick(4) == (None, None, None, None, None)
    assert one(out, 4)["event"] is None
    assert pick(5) == (4.0, None, True, True, "2-3>4")  # replacement counts as KL 4
    assert pick(6) == (1.0, False, None, True, "0>1")
    assert pick(7) == (2.0, None, False, False, "none")
    no_kl4 = progression(knees, "kl", "06", "10", None, replacement_as_kl4=False)
    assert pick(5, no_kl4) == (None, None, None, None, None)  # unread is null, never False
    assert one(no_kl4, 5)["event"] is None


# ---------------------------------------------------------------- selection


def test_selection_counts():
    knees = status(
        (1, "R", {"kl": [1.0, 1.0, 2.0], "readprj": [43, 43, 43]}),
        (2, "R", {"kl": [1.0, 1.0, 1.0], "readprj": [43, 37, 43]}),
        (3, "L", {"kl": [0.0, 0.0, None], "readprj": [43, 43, None]}),
    )
    counts = selection_counts(knees, "06", ["08", "10"])
    assert counts.columns == ["visit", "knees_at_risk", "read", "unread", "readprj", "knees"]
    v10 = counts.filter(pl.col("visit") == "10")
    assert v10.select("knees_at_risk", "read", "unread").unique().rows() == [(3, 2, 1)]
    assert v10.select("readprj", "knees").rows() == [(43, 2), (None, 1)]
    assert counts.filter(pl.col("visit") == "08").select("readprj", "knees").rows() == [
        (37, 1),
        (43, 2),
    ]


# ---------------------------------------------------------------- knee_status (table wrapper)


def test_knee_status_on_the_synthetic_release(isolated_settings, monkeypatch):
    monkeypatch.setenv("OAI_DATA_DIR", str(LO2018_RELEASE))
    get_settings.cache_clear()
    catalog_for.cache_clear()
    A = load_assumptions(LUYTEN).resolve("luyten_early_oa", None, {})
    knees = knee_status(A, LUYTEN_VISITS, "00")
    assert knees.columns == list(STATUS_COLUMNS)
    assert set(knees["SIDE"].unique()) == {"R", "L"}
    assert knees.select("ID", "SIDE").unique().height * len(LUYTEN_VISITS) == knees.height
    read = knees.filter(pl.col("read"))
    assert set(read["readprj"].unique()) == {15}  # anchor V00: Project 15 throughout
    later = knee_status(A, ("06", "08", "10"), "06").filter(pl.col("read"))
    # no Project 37/43 V06 rows here: the anchor falls back to Project 15
    assert set(later.filter(pl.col("visit") == "06")["readprj"].unique()) == {15}
    assert set(later.filter(pl.col("visit") > "06")["readprj"].unique()) == {37, 43}
    assert value_at(later, "08", "readprj", id_=2000013) == 37  # READPRJ 42 read as 37
    with pytest.raises(ValueError, match="anchor"):
        knee_status(A, ("08", "10"), "06")


def widths(*rows):
    """A jsw_widths frame; each row is (ID, SIDE, {visit: width})."""
    return pl.DataFrame(
        [{"ID": i, "SIDE": s, "visit": v, "mjsw": w} for i, s, by in rows for v, w in by.items()],
        schema={"ID": pl.Int64, "SIDE": pl.String, "visit": pl.String, "mjsw": pl.Float64},
    )


def jsw(end, middle="keep", base=4.0, horizon="10"):
    w = widths((1, "R", {"06": base, "10": end}))
    return jsw_change_from(w, "06", horizon, resolved(**{"jsw.middle": middle})).row(0, named=True)


def test_jsw_progressor_threshold():
    hit = jsw(3.3)
    assert hit["change_mm"] == pytest.approx(-0.7)
    assert hit["base_mm"] == 4.0 and hit["end_mm"] == 3.3
    assert hit["progressor"] is True
    assert jsw(3.4)["progressor"] is False
    assert jsw(3.45, middle="keep")["progressor"] is False
    assert jsw(3.45, middle="exclude")["progressor"] is None
    assert jsw(3.6, middle="exclude")["progressor"] is False
    assert jsw(3.3, middle="exclude")["progressor"] is True
    gone = jsw(None)
    assert gone["change_mm"] is None and gone["progressor"] is None
    assert jsw(4.2)["progressor"] is False  # a gain is not progression
    assert hit["years"] == pytest.approx(4.0)


def test_jsw_horizon_fallback():
    assert jsw(3.3)["horizon_used"] == "10"
    assert jsw(3.3, horizon="12")["horizon_used"] == "10"
    assert jsw(3.3, horizon="12")["progressor"] is True


def test_replacement_times():
    rep = pl.DataFrame(
        {
            "ID": [1, 2, 3, 4, 5],
            "SIDE": ["R"] * 5,
            "replaced_at_baseline": [False, False, False, False, True],
            "replaced_days": [1400.0, None, 3000.0, None, None],
            "replaced": [True, False, True, True, False],
        }
    )
    rep = rep.vstack(
        pl.DataFrame(
            {
                "ID": [6],
                "SIDE": ["R"],
                "replaced_at_baseline": [False],
                "replaced_days": [900.0],
                "replaced": [True],
            }
        )
    )
    days = pl.DataFrame(
        {
            "ID": [i for i in range(1, 7) for _ in (0, 1)],
            "visit": ["06", "10"] * 6,
            "days": [1000.0, 2500.0] * 6,
        }
    )
    out, flow = replacement_times_from(rep, days, "06", resolved())
    by_id = {r["ID"]: r for r in out.iter_rows(named=True)}
    assert by_id[1]["event"] is True and by_id[1]["time_yr"] == pytest.approx(400 / 365.25)
    assert by_id[2]["event"] is False and by_id[2]["time_yr"] == pytest.approx(1500 / 365.25)
    assert by_id[3]["event"] is True and by_id[3]["time_yr"] == pytest.approx(2000 / 365.25)
    assert set(by_id) == {1, 2, 3}  # 4: counted, no day; 5: baseline; 6: before the anchor
    assert flow["excluded_no_day"][0] == 1
    assert flow["replaced_by_anchor"][0] == 2
