import json
import textwrap

import pytest
from typer.testing import CliRunner

from oai.assumptions import (
    AssumptionsError,
    Resolved,
    current,
    load_assumptions,
    parse_override,
    render_ledger,
)
from oai.cli import app

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


def test_render_ledger_groups_by_status(tmp_path):
    text = render_ledger("demo", load_assumptions(write(tmp_path)))
    assert text.startswith("# Assumptions: demo\n")
    assert "2 confirmed · 1 assumed · 1 open" in text
    assert "## Confirmed (2)" in text and "## Open (1)" in text
    assert "| `cohort.survey_start` | `2012-09-12` | p.1662 | visit date cutoff |" in text
    assert "| `alignment.varus_max` | `-2.0` | p.1662 |  |" in text
    assert "## Variants" in text and "`model.corstr = independence`" in text


def test_render_ledger_escapes_pipes(tmp_path):
    text = TOML.replace('source = "p.1661"', 'source = "a | b"')
    assert "a \\| b" in render_ledger("demo", load_assumptions(write(tmp_path, text)))


def test_cli_assumptions_prints_and_writes(tmp_path, monkeypatch):
    root = write(tmp_path)
    (root / "analysis.toml").write_text(
        'name = "demo"\n[[steps]]\nid = "a"\nlang = "python"\nentry = "a.py"\n'
    )
    (root / "a.py").write_text("")
    monkeypatch.setenv("OAI_ANALYSES_DIR", str(tmp_path))
    shown = CliRunner().invoke(app, ["assumptions", "demo"])
    assert shown.exit_code == 0 and "## Open (1)" in shown.stdout
    written = CliRunner().invoke(app, ["assumptions", "demo", "--write"])
    assert written.exit_code == 0
    assert (root / "ASSUMPTIONS.md").read_text() == render_ledger("demo", load_assumptions(root))


def test_cli_assumptions_without_file(tmp_path, monkeypatch):
    root = tmp_path / "bare"
    root.mkdir()
    (root / "analysis.toml").write_text(
        'name = "bare"\n[[steps]]\nid = "a"\nlang = "python"\nentry = "a.py"\n'
    )
    (root / "a.py").write_text("")
    monkeypatch.setenv("OAI_ANALYSES_DIR", str(tmp_path))
    result = CliRunner().invoke(app, ["assumptions", "bare"])
    assert result.exit_code == 1 and "has no assumptions.toml" in result.output


CHOICES_TOML = TOML + textwrap.dedent(
    """
    [model.kl_covariate]
    value = "factor"
    status = "open"
    source = "not stated"
    choices = ["factor", "numeric"]
    """
)


def test_choices_are_enforced_for_overrides_and_variants(tmp_path):
    a = load_assumptions(write(tmp_path, CHOICES_TOML))
    assert a.items["model.kl_covariate"].choices == ("factor", "numeric")
    assert (
        a.resolve("demo", None, {"model.kl_covariate": "numeric"})["model.kl_covariate"]
        == "numeric"
    )
    with pytest.raises(AssumptionsError, match="must be one of factor, numeric"):
        a.resolve("demo", None, {"model.kl_covariate": "factr"})
    typo = CHOICES_TOML + '[variants.typo]\nset = { "model.kl_covariate" = "factr" }\n'
    with pytest.raises(AssumptionsError, match="must be one of"):
        load_assumptions(write(tmp_path, typo))


def test_default_must_be_one_of_its_choices(tmp_path):
    with pytest.raises(AssumptionsError, match="not one of its choices"):
        load_assumptions(
            write(tmp_path, CHOICES_TOML.replace('value = "factor"', 'value = "other"'))
        )


def test_ledger_shows_choices(tmp_path):
    text = render_ledger("demo", load_assumptions(write(tmp_path, CHOICES_TOML)))
    assert "`factor` (choices: factor, numeric)" in text
