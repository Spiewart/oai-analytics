import polars as pl
from typer.testing import CliRunner

from oai.cli import app
from oai.export.egress import check_egress, small_cell_violations

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


def test_small_cells_fail(tmp_path):
    pl.DataFrame({"group": ["a", "b", "c"], "n": [0, 4, 40]}).write_csv(tmp_path / "counts.csv")
    [problem] = check_egress(tmp_path, min_cell=11).problems
    assert "'n'" in problem


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
