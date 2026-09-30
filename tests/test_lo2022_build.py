import sys
from pathlib import Path

import polars as pl
import pytest

from oai.assumptions import load_assumptions
from oai.catalog import catalog_for
from oai.config import get_settings

REPO = Path(__file__).resolve().parents[1]
ANALYSIS = REPO / "analyses" / "lo2022_walking"
KNEE_DATA = Path(__file__).parent / "fixtures" / "oai_knee"
sys.path.insert(0, str(ANALYSIS))
import lo2022  # noqa: E402


@pytest.fixture(autouse=True)
def knee_release(isolated_settings, monkeypatch):
    monkeypatch.setenv("OAI_DATA_DIR", str(KNEE_DATA))
    get_settings.cache_clear()
    catalog_for.cache_clear()


def built(variant=None, **overrides):
    resolved = load_assumptions(ANALYSIS).resolve("lo2022_walking", variant, overrides)
    return lo2022.build(resolved)


def knee(df, id_, side):
    return df.filter((pl.col("ID") == id_) & (pl.col("SIDE") == side)).row(0, named=True)


def test_flow_matches_synthetic_design():
    b = built()
    flow = {r["step"]: r for r in b.flow.iter_rows(named=True)}
    assert [s for s in flow] == list(lo2022.FLOW_STEPS)
    assert {s: flow[s]["persons"] for s in flow} == {
        "all": 11,
        "age50": 10,
        "baseline_xray": 9,
        "roa": 7,
        "before_survey": 6,
        "no_visit96": 5,
        "no_survey": 4,
        "no_followup": 3,
    }
    assert flow["before_survey"]["excluded_knees"] == 1
    assert flow["no_visit96"]["male"] == 1  # 1000006
    assert sorted(b.knees.select("ID", "SIDE").rows()) == [
        (1000001, "R"),
        (1000009, "L"),
        (1000009, "R"),
        (1000010, "R"),
    ]


def test_exposure_coding():
    walkers = dict(built().knees.unique("ID").select("ID", "walker").iter_rows())
    assert walkers == {
        1000001: True,
        1000009: False,
        1000010: False,
    }  # 1000010: missing -> non-walker


def test_missing_walking_can_be_excluded():
    ids = built(None, **{"exposure.missing_walking_as": "exclude"}).knees["ID"].unique().to_list()
    assert 1000010 not in ids


def test_structural_outcomes_and_fallback():
    k = built().knees
    assert (knee(k, 1000001, "R")["kl_worse"], knee(k, 1000001, "R")["jsn_worse"]) == (True, True)
    row = knee(k, 1000009, "R")
    assert (row["source_visit"], row["kl_worse"], row["jsn_worse"]) == ("05", False, True)
    assert (knee(k, 1000010, "R")["kl_worse"], knee(k, 1000010, "R")["jsn_worse"]) == (False, False)


def test_replaced_knee_without_reading_is_included():
    row = knee(built().knees, 1000009, "L")
    assert (row["replaced"], row["klf"], row["kl_worse"], row["jsn_worse"]) == (
        True,
        None,
        True,
        True,
    )
    off = knee(built("replacement_not_worsening").knees, 1000009, "L")
    assert (off["kl_worse"], off["jsn_worse"]) == (None, None)


def test_pain_outcomes():
    k = built().knees
    assert (knee(k, 1000001, "R")["new_pain"], knee(k, 1000001, "R")["improved_pain"]) == (
        True,
        None,
    )
    assert (knee(k, 1000009, "R")["new_pain"], knee(k, 1000009, "R")["improved_pain"]) == (
        None,
        True,
    )
    assert knee(k, 1000009, "L")["new_pain"] is True  # replaced knee, pain kept
    excluded = built(None, **{"outcomes.replaced_knee_pain": "exclude"}).knees
    assert knee(excluded, 1000009, "L")["new_pain"] is None


def test_blank_baseline_pain_is_excluded_from_pain_outcomes():
    row = knee(built().knees, 1000010, "R")
    assert (row["pain0"], row["new_pain"], row["improved_pain"]) == (None, None, None)


def test_alignment_and_walking_amount():
    k = built().knees
    assert knee(k, 1000001, "R")["alignment"] == "varus"
    assert knee(k, 1000009, "R")["alignment"] == "valgus"
    assert knee(k, 1000010, "R")["alignment"] == "neutral"
    assert knee(k, 1000009, "L")["alignment"] is None
    assert knee(k, 1000001, "R")["walk_times"] == 2100.0  # >20 y x 9-12 mo x 9+ times
    assert knee(k, 1000009, "R")["walk_times"] == 0.0


def test_imputation_variants_add_survey_nonrespondents_with_followup():
    for variant, expected in (("missing_as_nonwalkers", False), ("missing_as_walkers", True)):
        k = built(variant).knees
        assert knee(k, 1000006, "R")["walker"] is expected
        assert k["ID"].n_unique() == 4
    assert 1000006 not in built().knees["ID"].to_list()


def metrics(df):
    return dict(df.iter_rows())


def test_flow_metrics_keys_and_values():
    m = metrics(lo2022.flow_metrics(built()))
    assert m["flow.no_followup.persons"] == 3
    assert m["flow.before_survey.excluded_persons"] == 1
    assert m["s1.no_visit96.male"] == 1
    assert m["flow.knees"] == 4
    assert m["flow.fallback36.persons"] == 1


def test_table1_metrics():
    m = metrics(lo2022.table1(built()))
    assert (m["t1.persons.walkers"], m["t1.persons.nonwalkers"], m["t1.persons.all"]) == (1, 2, 3)
    assert m["t1.age_mean.all"] == pytest.approx((61 + 68 + 59) / 3)
    assert (m["t1.male.walkers"], m["t1.male.all"]) == (1, 2)
    assert (m["t1.knees.nonwalkers"], m["t1.knees.all"]) == (3, 4)
    assert (m["t1.kl2.all"], m["t1.kl3.all"], m["t1.kl4.all"]) == (2, 1, 1)
    assert (m["t1.jsm1.walkers"], m["t1.jsm3.nonwalkers"]) == (1, 1)
    assert (m["t1.pain0.all"], m["t1.pain48.all"], m["t1.replaced48.nonwalkers"]) == (1, 2, 1)
    assert (m["t1.align_knees.all"], m["t1.varus.walkers"], m["t1.valgus.nonwalkers"]) == (3, 1, 1)
    assert m["t1.walk_days_max.walkers"] == 2100.0


def test_table3_metrics():
    m = metrics(lo2022.table3(built()))
    assert (m["t3.kl_worse.varus.walkers.events"], m["t3.kl_worse.varus.walkers.n"]) == (1, 1)
    assert (m["t3.kl_worse.valgus.nonwalkers.events"], m["t3.kl_worse.valgus.nonwalkers.n"]) == (
        0,
        1,
    )
    assert m["t3.new_pain.neutral.nonwalkers.n"] == 0  # 1000010 R has blank baseline pain


def test_roa_can_count_knees_replaced_at_baseline():
    # 1000011's only OA knee and 1000004's left knee were replaced at baseline (no readings).
    # 1000011's 96-month visit predates the survey; 1000004 has no native OA knee, so it
    # leaves at the follow-up step.
    default = {r["step"]: r for r in built().flow.iter_rows(named=True)}
    counted = {
        r["step"]: r
        for r in built(None, **{"cohort.roa_counts_replaced_knees": True}).flow.iter_rows(
            named=True
        )
    }
    assert (default["roa"]["persons"], counted["roa"]["persons"]) == (7, 9)
    assert (
        default["before_survey"]["excluded_persons"],
        counted["before_survey"]["excluded_persons"],
    ) == (1, 2)
    assert (
        default["no_followup"]["excluded_persons"],
        counted["no_followup"]["excluded_persons"],
    ) == (1, 2)
    assert default["no_followup"]["persons"] == counted["no_followup"]["persons"] == 3
    assert (
        1000011
        not in built(None, **{"cohort.roa_counts_replaced_knees": True}).knees["ID"].to_list()
    )


def test_walkers_without_amount_answers_can_be_reclassified():
    # With the 19-34 screener as exposure, 1000009 is a "yes" walker with no age-50+ amounts.
    base = {"exposure.walker_item": "V10WLKAR2"}
    assert knee(built(None, **base).knees, 1000009, "R")["walker"] is True
    recoded = built(None, **base, **{"exposure.yes_without_amount_as": "non-walker"}).knees
    assert knee(recoded, 1000009, "R")["walker"] is False
    assert knee(recoded, 1000001, "R")["walker"] is True  # has amount answers
    dropped = built(None, **base, **{"exposure.yes_without_amount_as": "exclude"}).knees
    assert 1000009 not in dropped["ID"].to_list()
