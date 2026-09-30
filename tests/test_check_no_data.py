import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_no_data.py"
_spec = importlib.util.spec_from_file_location("check_no_data", SCRIPT)
check_no_data = importlib.util.module_from_spec(_spec)
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
