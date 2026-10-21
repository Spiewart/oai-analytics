import tomllib
from pathlib import Path

import pytest

from oai.assumptions import AssumptionsError, load_assumptions
from oai.manifest import load_analysis

ANALYSES = Path(__file__).resolve().parents[1] / "analyses"
ANALYSIS = ANALYSES / "exam_crepitus_soa"
LO2018 = ANALYSES / "lo2018_crepitus"
INHERITED = (
    "cohort.side",
    "cohort.reading_project",
    "cohort.arthroplasty_scope",
    "cohort.missing_baseline_pain",
    "outcomes.pain_baseline_item",
    "outcomes.pain_followup_item",
    "outcomes.roa_rule",
    "outcomes.arthroplasty_scope",
    "outcomes.arthroplasty_timing",
    "outcomes.soa_missing",
    "outcomes.replacement_counts",
    "outcomes.missing_visit_days",
    "periods.after_missing_outcome",
    "model.corstr",
    "model.covariates",
    "model.missing_covariates",
)
NEW = (
    "exposure.require_s2",
    "mahmoudian.knee_pick",
    "mahmoudian.seed",
    "mahmoudian.jsn_rule",
    "mahmoudian.osteophyte_rule",
    "mahmoudian.reading_project",
    "mahmoudian.missing_followup_pain",
    "mahmoudian.missing_osteophytes",
)


def published(root=ANALYSIS):
    return tomllib.loads((root / "published.toml").read_text())


def test_manifest_and_assumptions_load():
    a = load_analysis(ANALYSIS)
    assert [s.id for s in a.steps] == ["cohort", "anchor", "models", "compare"]
    loaded = load_assumptions(ANALYSIS)
    assert set(INHERITED) | set(NEW) <= set(loaded.items)
    assert set(loaded.variants) == {
        "require_s2",
        "exclude_missing_pain",
        "mahmoudian_right",
        "mahmoudian_left",
        "mahmoudian_any_jsn_increase",
        "mahmoudian_osteophyte_grade_sum",
        "mahmoudian_exclude_blank_osteophytes",
    }


@pytest.mark.parametrize("key", INHERITED)
def test_inherited_decisions_match_lo2018(key):
    ours, theirs = load_assumptions(ANALYSIS).items[key], load_assumptions(LO2018).items[key]
    assert (ours.value, ours.status, ours.choices) == (theirs.value, theirs.status, theirs.choices)


def test_flow_targets_match_lo2018_published():
    ours = {k: v for k, v in published()["default"].items() if k.startswith("flow.")}
    theirs = {k: v for k, v in published(LO2018)["default"].items() if k.startswith("flow.")}
    assert ours == theirs and len(ours) == 6


def test_mahmoudian_targets():
    d = published()["default"]
    assert d["m.subjects"] == 576 and d["m.crepitus"] == 264
    assert d["m.structural.events"] == 310 and d["m.structural_sx.events"] == 153
    assert d["m.structural_sx.or_adj_kl"] == {"or": 1.0, "lo": 0.7, "hi": 1.5, "sig": False}
    known = set(load_assumptions(ANALYSIS).items)
    for prefix, keys in published()["related"].items():
        assert set(keys) <= known, prefix


def test_published_sig_follows_the_rule():
    ors = {k: v for k, v in published()["default"].items() if isinstance(v, dict) and "or" in v}
    assert len(ors) == 6
    for metric, v in ors.items():
        if 1.0 in (v["lo"], v["hi"]):
            assert "sig" not in v, metric
        else:
            assert v["sig"] == (v["lo"] > 1 or v["hi"] < 1), metric


@pytest.mark.parametrize(
    "key, typo",
    [
        ("mahmoudian.knee_pick", "both"),
        ("mahmoudian.jsn_rule", "new"),
        ("mahmoudian.osteophyte_rule", "count"),
        ("mahmoudian.missing_followup_pain", "drop"),
        ("mahmoudian.missing_osteophytes", "zero"),
    ],
)
def test_enumerated_assumptions_reject_typos(key, typo):
    with pytest.raises(AssumptionsError, match="must be one of"):
        load_assumptions(ANALYSIS).resolve("exam_crepitus_soa", None, {key: typo})
