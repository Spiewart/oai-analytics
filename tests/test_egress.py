import polars as pl
import pytest
from typer.testing import CliRunner

from oai.cli import app
from oai.export.egress import EgressError, check_egress, small_cell_violations

FAKE_ID = int("9" + "000123")  # built at runtime; never type the pattern literally


def test_clean_aggregate_results_pass(tmp_path):
    pl.DataFrame({"term": ["time:geno_add"], "estimate": [0.12], "n": [1500]}).write_csv(
        tmp_path / "coef.csv"
    )
    report = check_egress(tmp_path, min_cell=11)
    assert report.ok, report.problems
    assert len(report.checked) == 1


def test_identifier_columns_fail(tmp_path):
    pl.DataFrame({"src_subject_id": ["x"], "value": [1.0]}).write_csv(tmp_path / "rows.csv")
    assert "identifier column" in check_egress(tmp_path, min_cell=11).problems[0]


def test_participant_id_values_fail_in_nested_parquet(tmp_path):
    (tmp_path / "sub").mkdir()
    pl.DataFrame({"who": [FAKE_ID]}).write_parquet(tmp_path / "sub" / "x.parquet")
    [problem] = check_egress(tmp_path, min_cell=11).problems
    assert "sub/x.parquet" in problem and "participant-ID-like" in problem
    assert str(FAKE_ID) not in problem  # never echo the value itself


def test_position_columns_are_exempt_from_id_pattern(tmp_path):
    pl.DataFrame({"SNP": ["rs1"], "POS": [FAKE_ID], "beta": [0.1]}).write_csv(
        tmp_path / "gwas.tsv", separator="\t"
    )
    assert check_egress(tmp_path, min_cell=11, ignore_id_pattern_columns=["POS"]).ok
    assert not check_egress(tmp_path, min_cell=11).ok


def test_small_cells_warn_by_default(tmp_path):
    pl.DataFrame({"group": ["a", "b", "c"], "n": [0, 4, 40]}).write_csv(tmp_path / "counts.csv")
    report = check_egress(tmp_path, min_cell=5)
    assert report.ok
    [warning] = report.warnings
    assert "'n'" in warning


def test_small_cells_fail_when_configured(tmp_path):
    pl.DataFrame({"group": ["a", "b"], "n": [4, 40]}).write_csv(tmp_path / "counts.csv")
    report = check_egress(tmp_path, min_cell=5, small_cell="fail")
    assert not report.ok and "'n'" in report.problems[0]
    assert report.warnings == []


def test_small_cell_check_can_be_turned_off(tmp_path):
    pl.DataFrame({"n": [1]}).write_csv(tmp_path / "counts.csv")
    report = check_egress(tmp_path, min_cell=5, small_cell="off")
    assert report.ok and report.warnings == []


def test_unknown_small_cell_mode_is_rejected(tmp_path):
    with pytest.raises(EgressError, match="small_cell"):
        check_egress(tmp_path, min_cell=5, small_cell="strict")


def test_repo_egress_defaults_favor_retention():
    from oai.config import get_settings

    egress = get_settings().project["egress"]
    assert egress["small_cell"] == "warn" and egress["min_cell"] == 5


def test_cli_small_cells_warn_but_pass(tmp_path):
    pl.DataFrame({"n": [3]}).write_csv(tmp_path / "c.csv")
    result = CliRunner().invoke(app, ["check-egress", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "WARN" in result.output and "1 warning" in result.output


def test_small_cell_rule_reference_behavior():
    # Reference rule; update if the user-authored rule differs.
    df = pl.DataFrame({"n_cases": [3, 20], "count": [0, 12], "estimate": [1.0, 2.0]})
    assert len(small_cell_violations(df, 11)) == 1


def test_unknown_file_types_fail_closed(tmp_path):
    (tmp_path / "model.rds").write_bytes(b"\x00binary")
    assert "fails closed" in check_egress(tmp_path, min_cell=11).problems[0]


def test_figures_go_to_manual_review(tmp_path):
    (tmp_path / "plot.png").write_bytes(b"\x89PNG")
    report = check_egress(tmp_path, min_cell=11)
    assert report.ok and report.manual_review == [tmp_path / "plot.png"]


def test_text_files_are_scanned(tmp_path):
    (tmp_path / "log.txt").write_text(f"subject {FAKE_ID} dropped\n")
    assert not check_egress(tmp_path, min_cell=11).ok


def test_missing_directory_fails(tmp_path):
    assert not check_egress(tmp_path / "absent", min_cell=11).ok


def test_cli_exit_codes(tmp_path):
    pl.DataFrame({"n": [100]}).write_csv(tmp_path / "ok.csv")
    ok = CliRunner().invoke(app, ["check-egress", str(tmp_path)])
    assert ok.exit_code == 0, ok.output
    pl.DataFrame({"ID": [1]}).write_csv(tmp_path / "bad.csv")
    bad = CliRunner().invoke(app, ["check-egress", str(tmp_path)])
    assert bad.exit_code == 1
    assert "identifier column" in bad.output


# --- Final-review fixes (I3) ----------------------------------------------------


def test_joined_and_prefixed_ids_fail(tmp_path):
    pl.DataFrame({"sample": [f"{FAKE_ID}_{FAKE_ID}", f"OAI{FAKE_ID}"]}).write_csv(
        tmp_path / "s.csv"
    )
    report = check_egress(tmp_path, min_cell=11)
    assert any("participant-ID-like" in p for p in report.problems)


def test_ids_as_column_headers_fail(tmp_path):
    pl.DataFrame({"term": ["x"], str(FAKE_ID): [0.1]}).write_csv(tmp_path / "wide.csv")
    assert any("column name" in p for p in check_egress(tmp_path, min_cell=11).problems)


@pytest.mark.parametrize("name", ["IID", "FID", "dbGaP_Subject_ID", "participant_id"])
def test_genomics_identifier_column_names_fail(tmp_path, name):
    pl.DataFrame({name: ["a"], "beta": [0.1]}).write_csv(tmp_path / "t.csv")
    assert "identifier column" in check_egress(tmp_path, min_cell=11).problems[0]


def test_tab_delimited_txt_gets_table_checks(tmp_path):
    (tmp_path / "t.txt").write_text("IID\tbeta\nabc\t0.1\n")
    assert any("identifier column" in p for p in check_egress(tmp_path, min_cell=11).problems)


def test_html_and_svg_are_scanned_and_reviewed(tmp_path):
    (tmp_path / "w.html").write_text(f"<script>var d = [{FAKE_ID}];</script>")
    report = check_egress(tmp_path, min_cell=11)
    assert not report.ok
    assert report.manual_review == [tmp_path / "w.html"]


def test_decimal_fractions_are_not_ids(tmp_path):
    digits = "9" + "123456"
    (tmp_path / "p.csv").write_text(f"term,p\nx,1.{digits}e-05\ny,0.{digits}\n")
    assert check_egress(tmp_path, min_cell=11).ok


def test_long_format_metrics_get_the_small_cell_check(tmp_path):
    pl.DataFrame(
        {
            "metric": ["t3.x.valgus.nonwalkers.events", "t3.x.valgus.nonwalkers.n", "t2.x.or_adj"],
            "value": [3.0, 62.0, 0.8],
        }
    ).write_csv(tmp_path / "metrics_cohort.csv")
    report = check_egress(tmp_path, min_cell=5)
    assert report.ok
    [warning] = report.warnings
    assert "long format" in warning


def test_events_columns_count_as_counts(tmp_path):
    pl.DataFrame({"outcome": ["a"], "n": [100], "events": [3]}).write_csv(tmp_path / "table2.csv")
    [warning] = check_egress(tmp_path, min_cell=5).warnings
    assert "'events'" in warning
