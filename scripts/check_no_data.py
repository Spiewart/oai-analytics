#!/usr/bin/env python3
"""Fail if any given (or git-tracked) file looks like OAI participant data.

Pre-commit passes staged file names; CI runs it with no arguments to check every
tracked file. Exemptions live in scripts/leak_allowlist.txt as "<rule> <glob>".
When OAI_DATA_DIR is configured (env or .env), files whose content or name matches a
file in the release are flagged too.
"""

from __future__ import annotations

import fnmatch
import hashlib
import re
import subprocess
import sys
from collections.abc import Collection
from dataclasses import dataclass
from functools import cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST_FILE = REPO_ROOT / "scripts" / "leak_allowlist.txt"
DATA_EXTENSIONS = {
    ".parquet",
    ".feather",
    ".sas7bdat",
    ".rds",
    ".rdata",
    ".rda",
    ".xpt",
    ".sav",
    ".dta",
}
# Binary files are refused unless their type is one we expect in a code/docs repo.
ALLOWED_BINARY_EXTENSIONS = {
    ".docx",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".woff",
    ".woff2",
}
# A 9-prefixed 7-digit run not inside a longer number or a decimal fraction.
PARTICIPANT_ID = re.compile(rb"(?:^|[^\d.])(9\d{6})(?:\D|$)")
UTF8_BOM = b"\xef\xbb\xbf"
RULES = ("header", "id", "name")
MAX_SCAN_BYTES = 20 * 1024 * 1024


@dataclass(frozen=True)
class ReleaseIndex:
    """File names and sizes of an OAI release, for matching copies that enter the repo."""

    names: frozenset[str]
    by_size: dict[int, list[Path]]


def release_index(data_dir: Path) -> ReleaseIndex:
    files = [p for p in data_dir.rglob("*") if p.is_file() and not p.name.startswith(".")]
    by_size: dict[int, list[Path]] = {}
    for p in files:
        by_size.setdefault(p.stat().st_size, []).append(p)
    return ReleaseIndex(frozenset(p.name.lower() for p in files), by_size)


@cache
def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_allowlist(path: Path = ALLOWLIST_FILE) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for line in path.read_text().splitlines() if path.exists() else []:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        rule, _, pattern = line.partition(" ")
        if rule not in (*RULES, "all") or not pattern.strip():
            raise SystemExit(
                f"{path}: bad allowlist line {line!r} (expected '<all|header|id|name> <glob>')"
            )
        entries.append((rule, pattern.strip()))
    return entries


def skipped_rules(rel_path: str, allowlist: list[tuple[str, str]]) -> set[str]:
    skip: set[str] = set()
    for rule, pattern in allowlist:
        if fnmatch.fnmatch(rel_path, pattern):
            skip |= set(RULES) if rule == "all" else {rule}
    return skip


def _release_problems(path: Path, skip: Collection[str], release: ReleaseIndex) -> list[str]:
    """Content matches can never be allow-listed; name matches can (fixtures reuse names)."""
    size = path.stat().st_size
    if any(_sha256(path) == _sha256(candidate) for candidate in release.by_size.get(size, [])):
        return [f"{path}: identical to a file in the OAI release"]
    if "name" not in skip and path.name.lower() in release.names:
        return [f"{path}: has the same name as a file in the OAI release"]
    return []


def check_file(
    path: Path, skip: Collection[str] = (), release: ReleaseIndex | None = None
) -> list[str]:
    """Return problems for one file; an empty list means clean."""
    if not path.is_file():
        return []
    if release is not None and (problems := _release_problems(path, skip, release)):
        return problems
    suffix = path.suffix.lower()
    if suffix in DATA_EXTENSIONS:
        return [f"{path}: data file type {path.suffix!r} is never allowed in the repo"]
    with path.open("rb") as fh:
        head = fh.read(MAX_SCAN_BYTES)
    if b"\x00" in head[:8192]:
        if suffix in ALLOWED_BINARY_EXTENSIONS:
            return []
        return [
            f"{path}: binary file of unexpected type {suffix or '(none)'}; allow-list the type if intended"
        ]
    problems: list[str] = []
    first_line = head.split(b"\n", 1)[0].removeprefix(UTF8_BOM)
    if "header" not in skip and first_line.lower().startswith(b"id|"):
        problems.append(f"{path}: first line starts with 'ID|' (OAI table header)")
    if "id" not in skip and (match := PARTICIPANT_ID.search(head)):
        line_no = head.count(b"\n", 0, match.start(1)) + 1
        problems.append(
            f"{path}:{line_no}: 7-digit number starting with 9 (OAI participant ID pattern)"
        )
    return problems


def configured_release() -> ReleaseIndex | None:
    """Index OAI_DATA_DIR when configured and outside the repo (test fixtures live inside)."""
    try:
        from oai.config import ConfigError, load_settings
    except ImportError:
        return None
    try:
        data_dir = load_settings().data_dir
    except ConfigError:
        return None
    if not data_dir.is_dir() or data_dir.resolve().is_relative_to(REPO_ROOT):
        return None
    return release_index(data_dir)


def tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO_ROOT, check=True, capture_output=True
    ).stdout.decode()
    return [REPO_ROOT / p for p in out.split("\0") if p]


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    files = [Path(a) for a in args] if args else tracked_files()
    allowlist = load_allowlist()
    release = configured_release()
    problems: list[str] = []
    for f in files:
        resolved = f.resolve()
        rel = (
            resolved.relative_to(REPO_ROOT).as_posix()
            if resolved.is_relative_to(REPO_ROOT)
            else f.as_posix()
        )
        problems.extend(check_file(f, skipped_rules(rel, allowlist), release))
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
