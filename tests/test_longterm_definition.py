from pathlib import Path

import pytest

from oai.assumptions import AssumptionsError, load_assumptions
from oai.manifest import load_analysis

ANALYSES = Path(__file__).resolve().parents[1] / "analyses"
ANALYSIS = ANALYSES / "crepitus_soa_longterm"
LO2018 = ANALYSES / "lo2018_crepitus"
NEW = {
    "periods.horizon": "10",
    "outcomes.roa_source": "outcomes99",
    "outcomes.roa_definition": "kl2",
    "exposure.exam_after_48m": "carry_v06",
    "model.period_term": "factor",
    "outcomes.roa_unread": "unknown",
    "horizon.selection": "known_or_case",
}


def shared_keys():
    return sorted(set(load_assumptions(ANALYSIS).items) & set(load_assumptions(LO2018).items))


def test_manifest_and_assumptions_load():
    assert [s.id for s in load_analysis(ANALYSIS).steps] == ["cohort", "models"]
    loaded = load_assumptions(ANALYSIS)
    assert {k: loaded.items[k].value for k in NEW} == NEW
    assert set(loaded.variants) == {
        "horizon_120",
        "roa_kl2_jsn",
        "exam_no_carry",
        "period_term_none",
        "roa_unread_as_none",
        "horizon_complete",
        "lo2018_48m",
    }
    assert len(shared_keys()) >= 15


@pytest.mark.parametrize("key", shared_keys())
def test_inherited_decisions_match_lo2018(key):
    ours, theirs = load_assumptions(ANALYSIS).items[key], load_assumptions(LO2018).items[key]
    assert (ours.value, ours.status, ours.choices) == (theirs.value, theirs.status, theirs.choices)


def test_lo2018_48m_variant_restores_the_48_month_design():
    A = load_assumptions(ANALYSIS).resolve("crepitus_soa_longterm", "lo2018_48m", {})
    assert (A["periods.horizon"], A["outcomes.roa_source"], A["model.period_term"]) == (
        "06",
        "readings",
        "none",
    )


@pytest.mark.parametrize(
    "key, typo",
    [
        ("periods.horizon", "96"),
        ("outcomes.roa_source", "outcomes"),
        ("outcomes.roa_definition", "kl2jsn"),
        ("exposure.exam_after_48m", "carry"),
        ("model.period_term", "linear"),
        ("outcomes.roa_unread", "none"),
        ("horizon.selection", "all"),
    ],
)
def test_enumerated_assumptions_reject_typos(key, typo):
    with pytest.raises(AssumptionsError, match="must be one of"):
        load_assumptions(ANALYSIS).resolve("crepitus_soa_longterm", None, {key: typo})
