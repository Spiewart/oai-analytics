#!/usr/bin/env python3
"""Fail if any given (or git-tracked) file looks like OAI participant data.

Pre-commit passes staged file names; CI runs it with no arguments to check every
tracked file. Exemptions live in scripts/leak_allowlist.txt as "<rule> <glob>".
"""

from __future__ import annotations

import fnmatch
import re
import subprocess
import sys
from collections.abc import Collection
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST_FILE = REPO_ROOT / "scripts" / "leak_allowlist.txt"
DATA_EXTENSIONS = {".parquet", ".feather", ".sas7bdat", ".rds", ".rdata", ".xpt", ".sav", ".dta"}
PARTICIPANT_ID = re.compile(rb"\b9\d{6}\b")
RULES = ("header", "id")
MAX_SCAN_BYTES = 20 * 1024 * 1024


def load_allowlist(path: Path = ALLOWLIST_FILE) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for line in path.read_text().splitlines() if path.exists() else []:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        rule, _, pattern = line.partition(" ")
        if rule not in (*RULES, "all") or not pattern.strip():
            raise SystemExit(
                f"{path}: bad allowlist line {line!r} (expected '<all|header|id> <glob>')"
            )
        entries.append((rule, pattern.strip()))
    return entries


def skipped_rules(rel_path: str, allowlist: list[tuple[str, str]]) -> set[str]:
    skip: set[str] = set()
    for rule, pattern in allowlist:
        if fnmatch.fnmatch(rel_path, pattern):
            skip |= set(RULES) if rule == "all" else {rule}
    return skip


def check_file(path: Path, skip: Collection[str] = ()) -> list[str]:
    """Return problems for one file; an empty list means clean."""
    if path.suffix.lower() in DATA_EXTENSIONS:
        return [f"{path}: data file type {path.suffix!r} is never allowed in the repo"]
    try:
        with path.open("rb") as fh:
            head = fh.read(MAX_SCAN_BYTES)
    except (FileNotFoundError, IsADirectoryError):
        return []
    if b"\x00" in head[:8192]:
        return []  # binary (e.g. .docx); only the extension rule applies
    problems: list[str] = []
    if "header" not in skip and head.split(b"\n", 1)[0].startswith(b"ID|"):
        problems.append(f"{path}: first line starts with 'ID|' (OAI table header)")
    if "id" not in skip and (match := PARTICIPANT_ID.search(head)):
        line_no = head.count(b"\n", 0, match.start()) + 1
        problems.append(
            f"{path}:{line_no}: 7-digit number starting with 9 (OAI participant ID pattern)"
        )
    return problems


def tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO_ROOT, check=True, capture_output=True
    ).stdout.decode()
    return [REPO_ROOT / p for p in out.split("\0") if p]


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    files = [Path(a) for a in args] if args else tracked_files()
    allowlist = load_allowlist()
    problems: list[str] = []
    for f in files:
        resolved = f.resolve()
        rel = (
            resolved.relative_to(REPO_ROOT).as_posix()
            if resolved.is_relative_to(REPO_ROOT)
            else f.as_posix()
        )
        problems.extend(check_file(f, skipped_rules(rel, allowlist)))
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        print(
            f"\n{len(problems)} potential data leak(s). If a hit is a false positive, "
            "add '<rule> <path>' to scripts/leak_allowlist.txt.",
            file=sys.stderr,
        )
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
