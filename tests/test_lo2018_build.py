"""Lo 2018 cohort and symptomatic-OA status on the synthetic release (one participant per rule)."""

import sys
from pathlib import Path

import polars as pl
import pytest

from oai.assumptions import load_assumptions
from oai.catalog import catalog_for
from oai.config import get_settings

REPO = Path(__file__).resolve().parents[1]
ANALYSIS = REPO / "analyses" / "lo2018_crepitus"
sys.path.insert(0, str(ANALYSIS))

import lo2018  # noqa: E402
from soa_helpers import inline_cohort, inline_crepitus, inline_soa, person  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "oai_lo2018"
P = {k: 2000000 + k for k in range(1, 13)}  # fixture participants, one rule each


@pytest.fixture(autouse=True)
def lo2018_release(isolated_settings, monkeypatch):
    monkeypatch.setenv("OAI_DATA_DIR", str(FIXTURE))
    get_settings.cache_clear()
    catalog_for.cache_clear()


def resolved(variant=None, **overrides):
    return load_assumptions(ANALYSIS).resolve("lo2018_crepitus", variant, overrides)


def status(soa, person, visit):
    return soa.filter((pl.col("ID") == P[person]) & (pl.col("visit") == visit)).row(0, named=True)


def excluded(flow, step):
    return flow.filter(pl.col("step") == step)["excluded"].item()


def test_flow_counts_each_exclusion():
    A = resolved()
    cohort = lo2018.build_cohort(A, lo2018.soa_status(A))
    for step in ("arthroplasty", "no_baseline_kl", "baseline_soa", "no_outcome"):
        assert excluded(cohort.flow, step) == 1, step
    assert cohort.flow.filter(pl.col("step") == "all")["persons"].item() == 12
    assert cohort.people.height == 8
    assert set(cohort.people["ID"]) == {P[k] for k in (5, 6, 7, 8, 9, 10, 11, 12)}


def test_followup_replacement_is_soa_without_readings():
    soa = lo2018.soa_status(resolved())
    for visit in ("05", "06"):
        row = status(soa, 7, visit)
        assert row["replaced"] is True and row["soa"] is True, visit
    assert status(soa, 7, "03")["soa"] is False


def test_other_project_readings_are_ignored():
    row = status(lo2018.soa_status(resolved()), 10, "03")
    assert row["kl"] is None and row["roa"] is None and row["soa"] is None


def test_roa_rule_same_visit_vs_ever():
    assert status(lo2018.soa_status(resolved()), 9, "03")["soa"] is False
    ever = lo2018.soa_status(resolved(**{"outcomes.roa_rule": "ever"}))
    assert status(ever, 9, "03")["soa"] is True


def test_missing_baseline_pain_is_not_sx_by_default():
    A = resolved()
    people = lo2018.build_cohort(A, lo2018.soa_status(A)).people
    row = people.filter(pl.col("ID") == P[11]).row(0, named=True)
    assert row["sx0"] is False and row["subgroup"] == "roa_nosx"
    B = resolved("exclude_missing_pain")
    cohort = lo2018.build_cohort(B, lo2018.soa_status(B))
    assert excluded(cohort.flow, "baseline_soa") == 2
    assert P[11] not in cohort.people["ID"].to_list()


def test_left_knee_variant_reads_left_womac():
    right = lo2018._people(resolved()).filter(pl.col("ID") == P[6])["womac0"].item()
    left = lo2018._people(resolved("left_knee")).filter(pl.col("ID") == P[6])["womac0"].item()
    assert (right, left) == (1.0, 16.0)


def test_prevalent_replacement_never_counts_as_incident():
    """A left knee replaced at enrollment is SOA at V00 once either-knee replacements count."""
    A = resolved(**{"outcomes.arthroplasty_scope": "either"})
    soa = lo2018.soa_status(A)
    assert status(soa, 12, "00")["soa"] is True
    cohort = lo2018.build_cohort(A, soa)
    assert P[12] not in cohort.people["ID"].to_list()
    assert excluded(cohort.flow, "baseline_soa") == 2


def test_subgroups_and_covariates():
    A = resolved()
    people = lo2018.build_cohort(A, lo2018.soa_status(A)).people
    assert set(people.columns) >= {"ID", "age", "sex", "bmi", "kl0", "sx0", "womac0", "subgroup"}
    by_id = {r["ID"]: r for r in people.iter_rows(named=True)}
    assert by_id[P[7]]["subgroup"] == "roa_nosx"
    assert by_id[P[6]]["subgroup"] == "noroa_nosx"
    assert by_id[P[5]]["sex"] == 1 and by_id[P[6]]["sex"] == 2


# ---------------------------------------------------------------- periods and four-year frame


def test_censored_after_incident_soa():
    frame, counts = lo2018.periods(
        resolved(),
        inline_cohort(person()),
        inline_soa(1, [False, True, True, True]),
        inline_crepitus(1, [0, 2, 3, 3]),
    )
    assert frame["period"].to_list() == [1, 2]
    assert frame["event"].to_list() == [False, True]
    assert frame["crep"].to_list() == [0, 2]
    assert counts == {"potential": 2, "missing_outcome": 0, "missing_crepitus": 0}


def test_missing_middle_outcome_continues():
    args = (
        inline_cohort(person()),
        inline_soa(1, [None, False, False, False]),
        inline_crepitus(1, [1, 1, 1, 1]),
    )
    frame, counts = lo2018.periods(resolved(), *args)
    assert frame["period"].to_list() == [2, 3, 4]
    assert counts == {"potential": 4, "missing_outcome": 1, "missing_crepitus": 0}
    frame, counts = lo2018.periods(resolved("stop_after_missing_outcome"), *args)
    assert frame.height == 0
    assert counts == {"potential": 1, "missing_outcome": 1, "missing_crepitus": 0}


def test_missing_crepitus_is_counted_separately():
    frame, counts = lo2018.periods(
        resolved(),
        inline_cohort(person()),
        inline_soa(1, [False, False, False, False]),
        inline_crepitus(1, [0, None, 0, 0], exam=(1, None, 0, 0)),
    )
    assert frame["period"].to_list() == [1, 3, 4]
    assert counts == {"potential": 4, "missing_outcome": 0, "missing_crepitus": 1}
    assert frame["exam"].to_list() == [1, 0, 0]


def test_blank_baseline_s2_only_drops_four_year_row():
    cohort = inline_cohort(person(1), person(2))
    soa = pl.concat([inline_soa(1, [False, True, True, True]), inline_soa(2, [False] * 4)])
    crep = pl.concat(
        [inline_crepitus(1, [None, 2, 3, 3]), inline_crepitus(2, [4, 4, 4, 4], (1, 1, 1, 1))]
    )
    four = lo2018.four_year(cohort, soa, crep)
    assert four["ID"].to_list() == [2]
    assert four.select("crep0", "exam0", "event").row(0) == (4, 1, False)
    frame, _ = lo2018.periods(resolved(), cohort, soa, crep)
    assert frame.filter(pl.col("ID") == 1)["period"].to_list() == [2]


def test_four_year_event_is_any_followup_soa():
    cohort = inline_cohort(person(1))
    four = lo2018.four_year(
        cohort, inline_soa(1, [False, None, True, True]), inline_crepitus(1, [1, 1, 1, 1])
    )
    assert four["event"].to_list() == [True]


def test_cohort_metrics_has_every_published_key():
    import tomllib

    A = resolved()
    soa = lo2018.soa_status(A)
    cohort = lo2018.build_cohort(A, soa)
    crep = lo2018.crepitus_frame(A)
    frame, counts = lo2018.periods(A, cohort, soa, crep)
    persons = lo2018.four_year(cohort, soa, crep)
    metrics = lo2018.cohort_metrics(cohort, frame, counts, persons)
    published = tomllib.loads((ANALYSIS / "published.toml").read_text())["default"]
    wanted = {k for k in published if k.split(".")[0] in {"flow", "obs", "d", "r"}}
    assert set(metrics["metric"]) == wanted
    values = dict(metrics.iter_rows())
    assert values["flow.persons"] == 8 and values["obs.n"] == frame.height
