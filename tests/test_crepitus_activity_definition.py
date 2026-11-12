from pathlib import Path

import pytest

from oai.assumptions import AssumptionsError, load_assumptions
from oai.manifest import load_analysis

ANALYSES = Path(__file__).resolve().parents[1] / "analyses"
ANALYSIS = ANALYSES / "crepitus_activity"
WALKING_STEPS = ANALYSES / "walking_steps"
NEW = {
    "crepitus.count_missing": "both_required",
    "crepitus.s2_cut": 1,
    "activity.measures": ["steps", "mv_min", "light_min"],
    "activity.transform": "none",
    "model.covariates": ["age", "sex", "bmi", "wear_hr"],
    "model.covariates_2": ["kl_max", "womac_pain_max"],
    "model.corstr": "exchangeable",
}
VARIANTS = {
    "available_knees": {"crepitus.count_missing": "available_knees"},
    "log_activity": {"activity.transform": "log"},
    "s2_cut_2": {"crepitus.s2_cut": 2},
}


def inherited():
    keys = load_assumptions(WALKING_STEPS).items
    return sorted(k for k in keys if k.startswith("device.")) + [
        "steps.day_rule",
        "sample.min_step_days",
    ]


def test_manifest_and_assumptions_load():
    assert [s.id for s in load_analysis(ANALYSIS).steps] == ["cohort", "models"]
    loaded = load_assumptions(ANALYSIS)
    assert {k: loaded.items[k].value for k in NEW} == NEW
    assert set(loaded.variants) == set(VARIANTS)


@pytest.mark.parametrize("key", inherited())
def test_device_keys_match_walking_steps(key):
    ours, theirs = load_assumptions(ANALYSIS).items[key], load_assumptions(WALKING_STEPS).items[key]
    assert (ours.value, ours.status, ours.source, ours.choices) == (
        theirs.value,
        theirs.status,
        theirs.source,
        theirs.choices,
    )


@pytest.mark.parametrize("key", ["crepitus.count_missing", "activity.transform", "model.corstr"])
def test_enumerated_assumptions_reject_typos(key):
    with pytest.raises(AssumptionsError, match="must be one of"):
        load_assumptions(ANALYSIS).resolve("crepitus_activity", None, {key: "no-such-choice"})


@pytest.mark.parametrize("variant", sorted(VARIANTS))
def test_variants_resolve(variant):
    loaded = load_assumptions(ANALYSIS)
    default = loaded.resolve("crepitus_activity", None, {})
    A = loaded.resolve("crepitus_activity", variant, {})
    assert {k: v for k, v in A.values.items() if v != default.values[k]} == VARIANTS[variant]
