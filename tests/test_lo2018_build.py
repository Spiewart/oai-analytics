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

FIXTURE = Path(__file__).parent / "fixtures" / "oai_lo2018"
P = {k: 2000000 + k for k in range(1, 12)}  # fixture participants, one rule each


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
    assert cohort.flow.filter(pl.col("step") == "all")["persons"].item() == 11
    assert cohort.people.height == 7
    assert set(cohort.people["ID"]) == {P[k] for k in (5, 6, 7, 8, 9, 10, 11)}


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


def test_subgroups_and_covariates():
    A = resolved()
    people = lo2018.build_cohort(A, lo2018.soa_status(A)).people
    assert set(people.columns) >= {"ID", "age", "sex", "bmi", "kl0", "sx0", "womac0", "subgroup"}
    by_id = {r["ID"]: r for r in people.iter_rows(named=True)}
    assert by_id[P[7]]["subgroup"] == "roa_nosx"
    assert by_id[P[6]]["subgroup"] == "noroa_nosx"
    assert by_id[P[5]]["sex"] == 1 and by_id[P[6]]["sex"] == 2
