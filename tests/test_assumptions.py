import json
import textwrap

import pytest

from oai.assumptions import (
    AssumptionsError,
    Resolved,
    current,
    load_assumptions,
    parse_override,
)

TOML = textwrap.dedent(
    """
    [cohort.min_age]
    value = 50
    status = "confirmed"
    source = "p.1661"

    [cohort.survey_start]
    value = "2012-09-12"
    status = "assumed"
    source = "p.1662"
    rationale = "visit date cutoff"
    alternatives = ["none"]

    [model.corstr]
    value = "exchangeable"
    status = "open"
    source = "not stated"

    [alignment.varus_max]
    value = -2.0
    status = "confirmed"
    source = "p.1662"

    [variants.indep]
    description = "independence working correlation"
    set = { "model.corstr" = "independence" }
    """
)


def write(tmp_path, text=TOML):
    root = tmp_path / "demo"
    root.mkdir(exist_ok=True)
    (root / "assumptions.toml").write_text(text)
    return root


def test_parses_dotted_keys_and_variants(tmp_path):
    a = load_assumptions(write(tmp_path))
    assert sorted(a.items) == [
        "alignment.varus_max",
        "cohort.min_age",
        "cohort.survey_start",
        "model.corstr",
    ]
    assert a.items["cohort.survey_start"].rationale == "visit date cutoff"
    assert a.items["cohort.survey_start"].alternatives == ("none",)
    assert a.variants["indep"].set == {"model.corstr": "independence"}


def test_missing_file_gives_empty_assumptions(tmp_path):
    a = load_assumptions(tmp_path)
    assert a.path is None and not a.items
    assert a.resolve("demo").label == "default"


def test_resolve_default_variant_and_overrides(tmp_path):
    a = load_assumptions(write(tmp_path))
    r = a.resolve("demo")
    assert r.label == "default" and r["model.corstr"] == "exchangeable"
    r = a.resolve("demo", "indep")
    assert r.label == "indep" and r["model.corstr"] == "independence"
    assert r.origins["model.corstr"] == "variant"
    r = a.resolve("demo", None, {"cohort.min_age": 45})
    assert r.label.startswith("default+custom-") and len(r.label) == len("default+custom-") + 8
    assert r["cohort.min_age"] == 45 and r.origins["cohort.min_age"] == "override"


def test_int_is_accepted_for_float_but_not_the_reverse(tmp_path):
    a = load_assumptions(write(tmp_path))
    assert a.resolve("demo", None, {"alignment.varus_max": -3})["alignment.varus_max"] == -3
    with pytest.raises(AssumptionsError, match="expects int"):
        a.resolve("demo", None, {"cohort.min_age": 45.5})


@pytest.mark.parametrize(
    "overrides, variant, message",
    [
        ({"nope.key": 1}, None, "unknown assumption"),
        ({"cohort.min_age": "fifty"}, None, "expects int"),
        ({}, "missing", "unknown variant"),
    ],
)
def test_bad_resolutions(tmp_path, overrides, variant, message):
    with pytest.raises(AssumptionsError, match=message):
        load_assumptions(write(tmp_path)).resolve("demo", variant, overrides)


@pytest.mark.parametrize(
    "old, new, message",
    [
        ('status = "open"', 'status = "maybe"', "status must be one of"),
        ('source = "not stated"', 'source = ""', "'source' is required"),
        ('source = "not stated"', 'source = "x"\nnotes = "y"', "unknown field"),
        ('"model.corstr" = "independence"', '"model.nope" = 1', "unknown assumption"),
        ('"model.corstr" = "independence"', '"model.corstr" = 3', "expects str"),
    ],
)
def test_invalid_files(tmp_path, old, new, message):
    assert old in TOML
    with pytest.raises(AssumptionsError, match=message):
        load_assumptions(write(tmp_path, TOML.replace(old, new)))


def test_invalid_toml(tmp_path):
    with pytest.raises(AssumptionsError, match="invalid TOML"):
        load_assumptions(write(tmp_path, "[x"))


@pytest.mark.parametrize(
    "text, expected",
    [
        ("model.corstr=independence", ("model.corstr", "independence")),
        ('model.corstr="independence"', ("model.corstr", "independence")),
        ("cohort.min_age=45", ("cohort.min_age", 45)),
        ("flag=true", ("flag", True)),
        ('visits=["06", "05"]', ("visits", ["06", "05"])),
    ],
)
def test_parse_override(text, expected):
    assert parse_override(text) == expected


def test_parse_override_requires_equals():
    with pytest.raises(AssumptionsError, match="key=value"):
        parse_override("model.corstr")


def test_resolved_round_trips_through_json_and_current(tmp_path, monkeypatch):
    r = load_assumptions(write(tmp_path)).resolve("demo", "indep")
    path = r.write(tmp_path / "out")
    data = json.loads(path.read_text())
    assert data["label"] == "indep"
    assert data["assumptions"]["model.corstr"] == {
        "value": "independence",
        "status": "open",
        "source": "not stated",
        "origin": "variant",
    }
    monkeypatch.setenv("OAI_ASSUMPTIONS", str(path))
    again = current()
    assert isinstance(again, Resolved) and again["model.corstr"] == "independence"


def test_current_requires_env(monkeypatch):
    monkeypatch.delenv("OAI_ASSUMPTIONS", raising=False)
    with pytest.raises(AssumptionsError, match="oai run"):
        current()


def test_unknown_key_lookup_is_a_user_error(tmp_path):
    with pytest.raises(AssumptionsError, match="no assumption"):
        load_assumptions(write(tmp_path)).resolve("demo")["nope"]
