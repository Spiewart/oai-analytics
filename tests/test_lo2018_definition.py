import tomllib
from pathlib import Path

import pytest

from oai.assumptions import AssumptionsError, load_assumptions
from oai.manifest import load_analysis

ANALYSIS = Path(__file__).resolve().parents[1] / "analyses" / "lo2018_crepitus"
LEVELS = ("never", "rarely", "sometimes", "often", "always")
SUBGROUPS = ("roa_nosx", "noroa_sx", "noroa_nosx")
STRATA = (("men", "women"), ("age_lt65", "age_ge65"))
DECISIONS = {
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
    "periods.after_missing_outcome",
    "model.corstr",
    "model.covariates",
    "model.trend",
    "dual.s2_cuts",
    "outcomes.replacement_counts",
    "outcomes.missing_visit_days",
    "model.missing_covariates",
}


def published():
    return tomllib.loads((ANALYSIS / "published.toml").read_text())


def test_manifest_and_assumptions_load():
    a = load_analysis(ANALYSIS)
    assert [s.id for s in a.steps] == ["cohort", "models", "compare", "dual_counts", "dual_models"]
    loaded = load_assumptions(ANALYSIS)
    assert DECISIONS <= set(loaded.items)
    assert set(loaded.variants) == {
        "left_knee",
        "arthroplasty_either",
        "exclude_missing_pain",
        "roa_ever",
        "stop_after_missing_outcome",
        "soa_known_false",
        "corstr_independence",
    }
    assert loaded.items["periods.after_missing_outcome"].status == "open"


def test_published_related_keys_exist():
    p = published()
    assert set(p) == {"related", "default"}
    known = set(load_assumptions(ANALYSIS).items)
    for prefix, keys in p["related"].items():
        assert set(keys) <= known, prefix


def _sum(d, prefix, field):
    return sum(d[f"{prefix}.{level}.{field}"] for level in LEVELS)


def test_published_categories_sum_to_totals():
    d = published()["default"]
    flow = d["flow.all.persons"] - sum(
        d[f"flow.{step}.excluded"]
        for step in ("arthroplasty", "no_baseline_kl", "baseline_soa", "no_outcome")
    )
    assert flow == d["flow.persons"] == 3495
    assert d["obs.potential"] - d["obs.missing_outcome"] - d["obs.missing_crepitus"] == d["obs.n"]
    assert sum(d[f"obs.cases.p{p}"] for p in range(1, 5)) == d["obs.cases"]
    assert sum(d[f"d.obs.{level}"] for level in LEVELS) == d["obs.n"]
    assert sum(d[f"d.base.{level}"] for level in LEVELS) == d["flow.persons"]
    assert _sum(d, "t1", "n") == d["obs.n"] and _sum(d, "t1", "cases") == d["obs.cases"]
    assert _sum(d, "t3", "n") == d["flow.persons"] and _sum(d, "t3", "cases") == d["obs.cases"]
    for sub in SUBGROUPS:
        assert _sum(d, f"t2.{sub}", "n") == d[f"t2.{sub}.obs"], sub
        assert _sum(d, f"t2.{sub}", "cases") == d[f"t2.{sub}.cases"], sub
        assert _sum(d, f"t4.{sub}", "n") == d[f"t2.{sub}.persons"], sub
        assert _sum(d, f"t4.{sub}", "cases") == d[f"t2.{sub}.cases"], sub
    assert sum(d[f"t2.{sub}.persons"] for sub in SUBGROUPS) == d["flow.persons"]
    assert sum(d[f"t2.{sub}.obs"] for sub in SUBGROUPS) == d["obs.n"]
    for pair in STRATA:
        assert sum(d[f"t6.{s}.persons"] for s in pair) == d["flow.persons"], pair
        assert sum(d[f"t6.{s}.cases"] for s in pair) == d["obs.cases"], pair
        for s in pair:
            assert _sum(d, f"t6.{s}", "n") == d[f"t6.{s}.persons"], s
            assert _sum(d, f"t6.{s}", "cases") == d[f"t6.{s}.cases"], s
    assert d["d.male"] == d["t6.men.persons"]


def test_published_sig_follows_the_rule():
    """sig = CI excludes 1; no sig when a rounded bound is exactly 1.0."""
    ors = {k: v for k, v in published()["default"].items() if isinstance(v, dict) and "or" in v}
    assert len(ors) == 4 * 2 * (1 + 3 + 1 + 3 + 4)  # Tables 1-4 and 6, four levels, two models
    for metric, v in ors.items():
        if 1.0 in (v["lo"], v["hi"]):
            assert "sig" not in v, metric
        else:
            assert v["sig"] == (v["lo"] > 1 or v["hi"] < 1), metric


@pytest.mark.parametrize(
    "key, typo",
    [
        ("cohort.side", "right"),
        ("cohort.arthroplasty_scope", "both"),
        ("cohort.missing_baseline_pain", "drop"),
        ("outcomes.roa_rule", "carry"),
        ("outcomes.arthroplasty_scope", "any"),
        ("periods.after_missing_outcome", "skip"),
        ("outcomes.soa_missing", "missing"),
        ("model.corstr", "exchangable"),
        ("model.trend", "armitage"),
    ],
)
def test_enumerated_assumptions_reject_typos(key, typo):
    with pytest.raises(AssumptionsError, match="must be one of"):
        load_assumptions(ANALYSIS).resolve("lo2018_crepitus", None, {key: typo})
