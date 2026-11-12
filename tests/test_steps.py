import polars as pl
import pytest

from oai import config as oai_config
from oai import steps
from oai.steps import StepsError, parse_steps, read_steps, step_file


def raw(visit="06", **over):
    cols = {
        "ID": ["1000001", "1000001", "1000002"],
        f"V{visit}PAStudyDay": [253.0, 253.0, 10.0],
        f"V{visit}MINSequence": [2.0, 1.0, 1.0],
        f"v{visit}MINStep": [12.0, 0.0, None],  # the 48-month file spells this in lower case
    }
    cols.update(over)
    return pl.DataFrame(cols)


@pytest.fixture
def steps_dir(tmp_path, monkeypatch):
    d = tmp_path / "steps"
    d.mkdir()
    monkeypatch.setenv("OAI_STEPS_DIR", str(d))
    oai_config.get_settings.cache_clear()
    return d


def test_parse_steps_names_types_and_sorts():
    out = parse_steps(raw(), "06")
    assert out.columns == ["ID", "day", "minute", "steps"]
    assert out.schema["ID"] == pl.Int64 and out.schema["steps"] == pl.Float64
    assert out["minute"].to_list() == [1, 2, 1]
    assert out["steps"].to_list() == [0.0, 12.0, None]  # missing stays missing, never zero


def test_parse_steps_rejects_duplicate_minutes():
    dup = raw(**{"V06MINSequence": [1.0, 1.0, 1.0]})
    with pytest.raises(StepsError, match="1 duplicate"):
        parse_steps(dup, "06")


@pytest.mark.parametrize("bad", [-1.0, 2.5])
def test_parse_steps_rejects_negative_or_fractional_steps(bad):
    with pytest.raises(StepsError, match="whole numbers"):
        parse_steps(raw(**{"v06MINStep": [bad, 0.0, None]}), "06")


def test_parse_steps_missing_column_names_the_file():
    with pytest.raises(KeyError, match="V06MINStep.*not found in step file 06"):
        parse_steps(raw().drop("v06MINStep"), "06")


def test_step_file_matches_names_case_insensitively(steps_dir):
    (steps_dir / "StepMinbyMin08_modified.sas7bdat").touch()
    (steps_dir / "stepminbymin06.sas7bdat").touch()
    assert step_file("08").name == "StepMinbyMin08_modified.sas7bdat"
    assert step_file("06").name == "stepminbymin06.sas7bdat"


def test_step_file_missing_or_ambiguous_raises(steps_dir):
    with pytest.raises(StepsError, match="no step file for visit 06"):
        step_file("06")
    (steps_dir / "stepminbymin06.sas7bdat").touch()
    (steps_dir / "StepMinByMin06_v2.sas7bdat").touch()
    with pytest.raises(StepsError, match="2 step files for visit 06"):
        step_file("06")


def test_step_file_rejects_unknown_visit(steps_dir):
    with pytest.raises(StepsError, match="visit 10"):
        step_file("10")


def test_read_steps_caches_and_rebuilds_when_the_source_changes(steps_dir, monkeypatch):
    src = steps_dir / "stepminbymin06.sas7bdat"
    src.write_bytes(b"x")
    calls = []

    def fake_sas(path):
        calls.append(path)
        return raw()

    monkeypatch.setattr(steps, "_read_sas", fake_sas)
    first = read_steps("06")
    again = read_steps("06")
    assert len(calls) == 1 and first.equals(again)
    cache = oai_config.get_settings().work_dir / "cache" / "steps" / "steps_06.parquet"
    assert cache.is_file()
    src.write_bytes(b"xy")  # a new delivery replaces the file
    read_steps("06")
    assert len(calls) == 2


@pytest.mark.realdata
@pytest.mark.parametrize("visit", steps.STEP_VISITS)
def test_real_steps_join_every_minute_and_cover_most_people(visit):
    from oai.derive.accel import read_minutes

    if oai_config.get_settings().paths.get("OAI_STEPS_DIR") is None:
        pytest.skip("OAI_STEPS_DIR is not configured (env or .env)")
    m = read_minutes(visit, steps=True)  # raises if any step minute has no count minute
    per_person = m.group_by("ID").agg(pl.col("steps").is_not_null().any().alias("has"))
    assert per_person["has"].mean() > 0.99  # steps were captured for nearly everyone
    assert (m["steps"].drop_nulls() <= 255).all()
