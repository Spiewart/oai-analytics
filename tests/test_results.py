"""oai.results (metrics tables, Markdown) and oai.replication's shared compare step."""

import polars as pl
import pytest

from oai.assumptions import load_assumptions
from oai.derive.knee import select_cols
from oai.replication import compare_step, read_metrics
from oai.results import METRICS_SCHEMA, md_table, metrics_frame


def test_metrics_frame_from_a_mapping_keeps_order_and_nulls():
    df = metrics_frame({"b.n": 3, "a.mean": 1.5, "c.r": None})
    assert df.schema == pl.Schema(METRICS_SCHEMA)
    assert df.rows() == [("b.n", 3.0), ("a.mean", 1.5), ("c.r", None)]


def test_metrics_frame_from_pairs_and_empty():
    assert metrics_frame([("x", True), ("y", 2)]).rows() == [("x", 1.0), ("y", 2.0)]
    empty = metrics_frame({})
    assert empty.height == 0 and empty.schema == pl.Schema(METRICS_SCHEMA)


def test_md_table_writes_nulls_as_empty_cells():
    df = pl.DataFrame({"a": [1, None], "b": ["x", "y"]})
    assert md_table(df) == "| a | b |\n|---|---|\n| 1 | x |\n|  | y |\n"


def test_select_cols_matches_case_insensitively_and_renames():
    df = pl.DataFrame({"id": [1], "V00AGE": [60], "other": [0]})
    assert select_cols(df, ID="ID", age="v00age").columns == ["ID", "age"]
    with pytest.raises(KeyError):
        select_cols(df, bmi="P01BMI")


def test_read_metrics_combines_files_and_drops_na(tmp_path):
    (tmp_path / "metrics_a.csv").write_text("metric,value\nx,1\ny,NA\n")
    (tmp_path / "metrics_b.csv").write_text("metric,value\nz,2.5\n")
    (tmp_path / "flow.csv").write_text("metric,value\nignored,9\n")
    assert read_metrics(tmp_path) == {"x": 1.0, "z": 2.5}


LEDGER = """\
[cohort.min_age]
value = 45
status = "assumed"
source = "test"

[variants.older]
set = { "cohort.min_age" = 60 }
"""
PUBLISHED = """\
[default]
"flow.persons" = 100
"flow.knees" = 200

[older]
"flow.persons" = 50
"""


@pytest.fixture
def analysis(tmp_path, monkeypatch):
    root = tmp_path / "toy"
    root.mkdir()
    (root / "assumptions.toml").write_text(LEDGER)
    (root / "published.toml").write_text(PUBLISHED)
    results = tmp_path / "results"
    results.mkdir()
    metrics_frame({"flow.persons": 100, "flow.knees": 150}).write_csv(results / "metrics_x.csv")
    monkeypatch.setenv("OAI_RESULTS_DIR", str(results))
    monkeypatch.chdir(root)

    def use(variant=None):
        resolved = load_assumptions(root).resolve("toy", variant, None)
        monkeypatch.setenv("OAI_ASSUMPTIONS", str(resolved.write(tmp_path / "res")))
        return results

    return use


def test_compare_step_grades_the_run_and_writes_comparison(analysis, capsys):
    results = analysis()
    table = compare_step()
    assert dict(zip(table["metric"], table["verdict"], strict=True)) == {
        "flow.persons": "replicated",
        "flow.knees": "drift",
    }
    assert pl.read_csv(results / "comparison.csv").height == 2
    assert "1 replicated · 1 drift" in capsys.readouterr().out


def test_compare_step_uses_the_variant_section_and_row_filter(analysis):
    analysis("older")
    assert compare_step()["metric"].to_list() == ["flow.persons"]  # the [older] section
    analysis()
    kept = compare_step(rows=lambda rows: {k: v for k, v in rows.items() if k != "flow.knees"})
    assert kept["metric"].to_list() == ["flow.persons"]
