from pathlib import Path

import pytest

from oai.assumptions import AssumptionsError, load_assumptions
from oai.derive import knee_outcomes as ko
from oai.manifest import load_analysis

ANALYSES = Path(__file__).resolve().parents[1] / "analyses"
ANALYSIS = ANALYSES / "steps_oa"
WALKING_STEPS = ANALYSES / "walking_steps"
LONGTERM = ANALYSES / "crepitus_soa_longterm"
NEW = {
    "periods.horizon": "10",
    "outcomes.roa_replacement": "event",
    "readings.anchor_project": "followup",
    "readings.followup_project": "latest",
    "incidence.model": "discrete_time",
    "horizon.selection": "known_or_case",
    "progression.risk_kl": "2-3",
    "progression.models": "read_knees",
    "progression.jsn_rule": "whole_grade",
    "progression.replacement_as_kl4": True,
    "jsw.threshold_mm": 0.7,
    "jsw.middle": "keep",
    "jsw.nonprogressor_mm": 0.5,
    "steps.bands": [5000, 7500, 10000],
    "steps.spline_knots": [0.10, 0.50, 0.90],
    "steps.transform": "none",
    "tkr.min_events": 20,
    "tkr.censor": "last_visit",
    "reverse.coding": "any",
    "reverse.r2_kl_read": False,
    "model.covariates": ["age", "sex", "bmi", "wear_hr"],
    "model.covariates_2_knee": ["kl48", "womac48"],
    "model.covariates_2_person": ["kl_max", "womac_pain_max"],
    "model.corstr": "exchangeable",
    "sample.exclude_baseline_pain": False,
}
VARIANTS = {
    "horizon_120": {"periods.horizon": "12"},
    "roa_kl2_jsn": {"outcomes.roa_definition": "kl2_jsn"},
    "exclude_baseline_pain": {"sample.exclude_baseline_pain": True},
    "progression_kl_1_to_3": {"progression.risk_kl": "1-3"},
    "log_steps": {"steps.transform": "log"},
    "by_horizon": {"incidence.model": "by_horizon"},
    "anchor_p15": {"readings.anchor_project": "p15"},
    "followup_p37": {"readings.followup_project": "p37"},
    "reverse_count": {"reverse.coding": "count"},
    "r2_kl_worsening_read": {"reverse.r2_kl_read": True},
    "jsw_fnih_middle": {"jsw.middle": "exclude"},
    "jsn_within_grade": {"progression.jsn_rule": "within_grade"},
}


def inherited(path, keep):
    return sorted(k for k in load_assumptions(path).items if keep(k))


def from_walking_steps(key):
    return key.startswith("device.") or key in ("steps.day_rule", "sample.min_step_days")


def from_longterm(key):
    return key.startswith("outcomes.") or key in ("cohort.reading_project", "cohort.side")


def test_manifest_and_assumptions_load():
    assert [s.id for s in load_analysis(ANALYSIS).steps] == ["cohort", "models"]
    loaded = load_assumptions(ANALYSIS)
    assert {k: loaded.items[k].value for k in NEW} == NEW
    assert set(loaded.variants) == set(VARIANTS)


def same(ours, theirs):
    assert (ours.value, ours.status, ours.source, ours.choices) == (
        theirs.value,
        theirs.status,
        theirs.source,
        theirs.choices,
    )


@pytest.mark.parametrize("key", inherited(WALKING_STEPS, from_walking_steps))
def test_device_keys_match_walking_steps(key):
    same(load_assumptions(ANALYSIS).items[key], load_assumptions(WALKING_STEPS).items[key])


def test_every_device_key_is_inherited():
    ours = inherited(ANALYSIS, from_walking_steps)
    assert ours == inherited(WALKING_STEPS, from_walking_steps)


@pytest.mark.parametrize("key", inherited(LONGTERM, from_longterm))
def test_outcome_keys_match_longterm(key):
    same(load_assumptions(ANALYSIS).items[key], load_assumptions(LONGTERM).items[key])


def test_every_outcome_key_is_inherited_or_new():
    ours = {k for k in load_assumptions(ANALYSIS).items if from_longterm(k)}
    theirs = {k for k in load_assumptions(LONGTERM).items if from_longterm(k)}
    assert ours == theirs | {"outcomes.roa_replacement"}


@pytest.mark.parametrize(
    "key",
    [
        "periods.horizon",
        "outcomes.roa_replacement",
        "readings.anchor_project",
        "incidence.model",
        "progression.risk_kl",
        "jsw.middle",
        "steps.transform",
        "reverse.coding",
        "model.corstr",
    ],
)
def test_enumerated_assumptions_reject_typos(key):
    with pytest.raises(AssumptionsError, match="must be one of"):
        load_assumptions(ANALYSIS).resolve("steps_oa", None, {key: "no-such-choice"})


@pytest.mark.parametrize("variant", sorted(VARIANTS))
def test_variants_resolve(variant):
    loaded = load_assumptions(ANALYSIS)
    default = loaded.resolve("steps_oa", None, {})
    A = loaded.resolve("steps_oa", variant, {})
    assert {k: v for k, v in A.values.items() if v != default.values[k]} == VARIANTS[variant]


MODULE_CHOICES = {
    "outcomes.roa_replacement": ko.ROA_REPLACEMENT,
    "readings.anchor_project": ko.ANCHOR_PROJECT,
    "readings.followup_project": tuple(ko.FOLLOWUP_PROJECTS),
    "progression.jsn_rule": ko.RULES,
    "jsw.middle": ko.JSW_MIDDLE,
    "tkr.censor": ko.TKR_CENSOR,
    "horizon.selection": ko.SELECTIONS,
}


@pytest.mark.parametrize("key", sorted(MODULE_CHOICES))
def test_ledger_choices_are_values_the_module_accepts(key):
    item = load_assumptions(ANALYSIS).items[key]
    assert item.choices and set(item.choices) <= set(MODULE_CHOICES[key])
