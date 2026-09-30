import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_no_data.py"
_spec = importlib.util.spec_from_file_location("check_no_data", SCRIPT)
check_no_data = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = check_no_data  # dataclasses resolve their module here
_spec.loader.exec_module(check_no_data)

# Built at runtime so this file never contains the participant-ID pattern itself.
FAKE_ID = "9" + "000123"


def test_clean_file_passes(tmp_path):
    p = tmp_path / "notes.md"
    p.write_text("KL grade 2, n = 1500\n")
    assert check_no_data.check_file(p) == []


def test_oai_header_is_flagged(tmp_path):
    p = tmp_path / "t.txt"
    p.write_text("ID|SIDE|V00XRKL\n")
    [problem] = check_no_data.check_file(p)
    assert "ID|" in problem


def test_participant_id_is_flagged_with_line_number(tmp_path):
    p = tmp_path / "t.csv"
    p.write_text(f"a,b\nx,{FAKE_ID}\n")
    [problem] = check_no_data.check_file(p)
    assert ":2:" in problem


def test_longer_numbers_are_not_flagged(tmp_path):
    p = tmp_path / "t.csv"
    p.write_text(f"pos\n1{FAKE_ID}\n{FAKE_ID}4\n")
    assert check_no_data.check_file(p) == []


def test_data_extensions_are_always_flagged(tmp_path):
    p = tmp_path / "frame.parquet"
    p.write_bytes(b"PAR1")
    assert check_no_data.check_file(p, skip={"header", "id"})


def test_binary_files_are_not_content_scanned(tmp_path):
    p = tmp_path / "doc.docx"
    p.write_bytes(b"PK\x03\x04\x00\x00" + FAKE_ID.encode())
    assert check_no_data.check_file(p) == []


def test_allowlist_rules(tmp_path):
    allow = tmp_path / "allow.txt"
    allow.write_text("# comment\nid uv.lock\nheader tests/fixtures/*\n")
    entries = check_no_data.load_allowlist(allow)
    assert check_no_data.skipped_rules("uv.lock", entries) == {"id"}
    assert check_no_data.skipped_rules("tests/fixtures/oai/Enrollees.txt", entries) == {"header"}
    assert check_no_data.skipped_rules("src/oai/cli.py", entries) == set()


def test_bad_allowlist_line_is_rejected(tmp_path):
    allow = tmp_path / "allow.txt"
    allow.write_text("ids uv.lock\n")
    with pytest.raises(SystemExit):
        check_no_data.load_allowlist(allow)


def test_main_exit_codes(tmp_path, capsys):
    good = tmp_path / "good.md"
    good.write_text("ok\n")
    bad = tmp_path / "bad.txt"
    bad.write_text("ID|X\n")
    assert check_no_data.main([str(good)]) == 0
    assert check_no_data.main([str(good), str(bad)]) == 1
    assert "potential data leak" in capsys.readouterr().err


def test_repository_is_clean():
    assert check_no_data.main([]) == 0


# --- Final-review fixes (I4) ----------------------------------------------------


def test_unlisted_binary_files_are_flagged(tmp_path):
    # The release ships SQLite .sf3 files; binaries pass only if their type is allow-listed.
    p = tmp_path / "LabCorp Kit.sf3"
    p.write_bytes(b"SQLite format 3\x00" + b"\x00" * 64)
    [problem] = check_no_data.check_file(p)
    assert "binary" in problem


def test_header_rule_is_case_insensitive_and_bom_tolerant(tmp_path):
    lower = tmp_path / "a.txt"
    lower.write_text("id|side\n")
    bom = tmp_path / "b.txt"
    bom.write_bytes(b"\xef\xbb\xbfID|SIDE\n")
    assert check_no_data.check_file(lower)
    assert check_no_data.check_file(bom)


def test_underscore_joined_ids_are_flagged(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text(f"sample\n{FAKE_ID}_{FAKE_ID}\n")
    assert check_no_data.check_file(p)


def test_decimal_fractions_are_not_flagged(tmp_path):
    p = tmp_path / "p.csv"
    p.write_text(f"p\n0.{FAKE_ID}\n")
    assert check_no_data.check_file(p) == []


def test_release_files_are_flagged_by_content_or_name(tmp_path):
    release = tmp_path / "release"
    release.mkdir()
    (release / "Biospec_Demo.txt").write_text("subject,age\nabc,61\n")
    renamed = tmp_path / "renamed.csv"
    renamed.write_text("subject,age\nabc,61\n")
    same_name = tmp_path / "biospec_demo.txt"
    same_name.write_text("unrelated\n")
    index = check_no_data.release_index(release)
    assert "release" in check_no_data.check_file(renamed, release=index)[0]
    assert "release" in check_no_data.check_file(same_name, release=index)[0]
    # The name rule can be allow-listed (fixtures reuse release names); content cannot.
    assert check_no_data.check_file(same_name, skip={"name"}, release=index) == []
    assert check_no_data.check_file(renamed, skip={"header", "id", "name"}, release=index)
