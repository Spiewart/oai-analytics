import tomllib
from pathlib import Path

import pytest

from oai.assumptions import AssumptionsError, load_assumptions
from oai.manifest import load_analysis

ANALYSIS = Path(__file__).resolve().parents[1] / "analyses" / "lo2022_walking"


def test_manifest_and_assumptions_load():
    a = load_analysis(ANALYSIS)
    assert [s.id for s in a.steps] == ["cohort", "models", "compare"]
    loaded = load_assumptions(ANALYSIS)
    assert set(loaded.variants) == {
        "missing_as_nonwalkers",
        "missing_as_walkers",
        "replacement_not_worsening",
        "corstr_independence",
        "roa_counts_replaced_knees",
        "walker_requires_amount",
        "published_counts",
    }
    assert loaded.items["model.corstr"].status == "open"


def test_published_targets_are_well_formed():
    published = tomllib.loads((ANALYSIS / "published.toml").read_text())
    assert set(published) == {"related", "default", "missing_as_nonwalkers", "missing_as_walkers"}
    default = published["default"]
    assert default["flow.no_followup.persons"] == 1212 and default["flow.knees"] == 1808
    assert default["t2.jsn_worse.or_adj"] == {"or": 0.8, "lo": 0.6, "hi": 1.0, "sig": True}
    assert published["missing_as_walkers"]["t2.kl_worse.walkers.n"] == 2711
    known = set(load_assumptions(ANALYSIS).items)
    for prefix, keys in published["related"].items():
        assert set(keys) <= known, prefix
    for section in ("default", "missing_as_nonwalkers", "missing_as_walkers"):
        for metric, value in published[section].items():
            assert isinstance(value, (int, float)) or set(value) == {"or", "lo", "hi", "sig"}, (
                metric
            )


@pytest.mark.parametrize(
    "key, typo",
    [
        ("model.kl_covariate", "factr"),
        ("model.corstr", "exchangable"),
        ("outcomes.replaced_knee_pain", "kep"),
        ("outcomes.replacement_window", "calendar_48m"),
        ("cohort.impute_missing_walking", "walkers"),
        ("exposure.missing_walking_as", "nonwalker"),
        ("alignment.source", "cook"),
        ("alignment.pick", "first"),
    ],
)
def test_enumerated_assumptions_reject_typos(key, typo):
    with pytest.raises(AssumptionsError, match="must be one of"):
        load_assumptions(ANALYSIS).resolve("lo2022_walking", None, {key: typo})
