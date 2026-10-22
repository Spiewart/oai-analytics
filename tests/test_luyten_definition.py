from pathlib import Path

import pytest

from oai.assumptions import AssumptionsError, load_assumptions
from oai.manifest import load_analysis

ANALYSES = Path(__file__).resolve().parents[1] / "analyses"
ANALYSIS = ANALYSES / "luyten_early_oa"
LONGTERM = ANALYSES / "crepitus_soa_longterm"
INHERITED = (
    "cohort.reading_project",
    "outcomes.pain_baseline_item",
    "outcomes.pain_followup_item",
    "outcomes.arthroplasty_timing",
    "outcomes.soa_missing",
    "outcomes.replacement_counts",
    "outcomes.missing_visit_days",
    "outcomes.roa_source",
    "outcomes.roa_definition",
    "outcomes.roa_unread",
    "outcomes.roa_rule",
    "horizon.selection",
    "model.corstr",
)
NEW = {
    "cohort.knees": "both",
    "cohort.cohorts": "all",
    "outcomes.arthroplasty_scope": "knee",
    "periods.horizon": "10",
    "outcomes.roa_replacement": "event",
    "luyten.kl_source": "project15",
    "luyten.koos_cutoff": 85,
    "luyten.koos_min": 2,
    "luyten.adl_source": "womac_function",
    "luyten.koos_missing": "not_met",
    "luyten.sign_missing": "not_met",
    "exposure.s2_coding": "any",
    "model.covariates": ["age", "sex", "bmi"],
}
VARIANTS = {
    "right_knee": {"cohort.knees": "right"},
    "progression_incidence": {"cohort.cohorts": "progression_incidence"},
    "kl_outcomes99": {"luyten.kl_source": "outcomes99"},
    "adl_omitted": {"luyten.adl_source": "omit"},
    "koos_missing_exclude": {"luyten.koos_missing": "exclude"},
    "sign_missing_exclude": {"luyten.sign_missing": "exclude"},
    "s2_levels": {"exposure.s2_coding": "levels"},
    "horizon_complete": {"horizon.selection": "complete"},
    "roa_kl2_jsn": {"outcomes.roa_definition": "kl2_jsn"},
    "roa_replacement_ignore": {"outcomes.roa_replacement": "ignore"},
}


def test_manifest_and_assumptions_load():
    assert [s.id for s in load_analysis(ANALYSIS).steps] == ["cohort", "models", "compare"]
    loaded = load_assumptions(ANALYSIS)
    assert {k: loaded.items[k].value for k in NEW} == NEW
    assert set(loaded.variants) == set(VARIANTS)


@pytest.mark.parametrize("key", INHERITED)
def test_inherited_decisions_match_longterm(key):
    ours, theirs = load_assumptions(ANALYSIS).items[key], load_assumptions(LONGTERM).items[key]
    assert (ours.value, ours.status, ours.source, ours.choices) == (
        theirs.value,
        theirs.status,
        theirs.source,
        theirs.choices,
    )


@pytest.mark.parametrize(
    "key",
    sorted(k for k, a in load_assumptions(ANALYSIS).items.items() if a.choices)
    if (ANALYSIS / "assumptions.toml").exists()
    else ["missing"],
)
def test_enumerated_assumptions_reject_typos(key):
    with pytest.raises(AssumptionsError, match="must be one of"):
        load_assumptions(ANALYSIS).resolve("luyten_early_oa", None, {key: "no-such-choice"})


@pytest.mark.parametrize("variant", sorted(VARIANTS))
def test_variants_resolve(variant):
    loaded = load_assumptions(ANALYSIS)
    default = loaded.resolve("luyten_early_oa", None, {})
    A = loaded.resolve("luyten_early_oa", variant, {})
    changed = {k: A.values[k] for k in A.values if A.values[k] != default.values[k]}
    assert changed == VARIANTS[variant]
