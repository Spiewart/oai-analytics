"""Build a self-contained, checksummed bundle that runs an analysis's enclave stage.

Only the phenotype columns declared in [export] leave the laptop. Every export is
appended to OAI_WORK_DIR/export_log.jsonl (NIH: "track all copies or extracts").
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any

import polars as pl

from oai import __version__
from oai.assumptions import DEFAULT_LABEL
from oai.config import Settings
from oai.errors import OAIError
from oai.manifest import Analysis
from oai.runner import frame_dir, run_analysis

VENDOR_HELP = (
    "--vendor is not implemented yet. For an offline enclave, populate vendor/ inside the "
    "extracted bundle on a connected Linux x86_64 machine: `pip download -r env/requirements.txt "
    "--platform manylinux2014_x86_64 --python-version 3.11 --only-binary=:all: -d vendor/wheels`, "
    "and see README_ENCLAVE.md ('Offline enclaves') for the R packages."
)


class ExportError(OAIError):
    """The bundle could not be built."""


Builder = Callable[[Path], None]


@dataclass(frozen=True)
class Builders:
    python_wheel: Builder
    r_package: Builder
    python_requirements: Builder


@dataclass(frozen=True)
class BundleResult:
    path: Path
    manifest: dict[str, Any]


def _run(cmd: list[str], cwd: Path) -> None:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise ExportError(f"`{' '.join(cmd)}` failed:\n{proc.stderr.strip()}")


def default_builders(repo_root: Path) -> Builders:
    def python_wheel(dest: Path) -> None:
        _run(["uv", "build", "--wheel", "--out-dir", str(dest)], cwd=repo_root)

    def r_package(dest: Path) -> None:
        _run(
            ["R", "CMD", "build", "--no-build-vignettes", str(repo_root / "r" / "oaimodels")],
            cwd=dest,
        )

    def python_requirements(dest: Path) -> None:
        _run(
            [
                "uv",
                "export",
                "--format",
                "requirements-txt",
                "--no-dev",
                "--no-emit-project",
                "--frozen",
                "--output-file",
                str(dest / "requirements.txt"),
            ],
            cwd=repo_root,
        )

    return Builders(python_wheel, r_package, python_requirements)


def git_state(repo_root: Path) -> tuple[str, bool]:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True
    )
    if head.returncode != 0:
        raise ExportError("Export needs a git checkout with at least one commit")
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo_root, capture_output=True, text=True, check=True
    )
    return head.stdout.strip(), bool(status.stdout.strip())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _render(template: str, analysis: str) -> str:
    text = resources.files("oai.export").joinpath("templates", template).read_text()
    return text.replace("@@ANALYSIS@@", analysis)


def _append_export_log(settings: Settings, tar_path: Path, manifest: dict[str, Any]) -> None:
    record = {
        "bundle": str(tar_path),
        "sha256": sha256_file(tar_path),
        "analysis": manifest["analysis"],
        "created_utc": manifest["created_utc"],
        "git_commit": manifest["git_commit"],
        "frame_rows": manifest["frame"]["rows"],
    }
    settings.work_dir.mkdir(parents=True, exist_ok=True)
    with (settings.work_dir / "export_log.jsonl").open("a") as fh:
        fh.write(json.dumps(record) + "\n")


def export_analysis(
    analysis: Analysis,
    settings: Settings,
    *,
    out_dir: Path | None = None,
    allow_dirty: bool = False,
    run_local: bool = True,
    vendor: bool = False,
    builders: Builders | None = None,
    now: datetime | None = None,
) -> BundleResult:
    if analysis.export is None:
        raise ExportError(f"{analysis.name} has no [export] section; nothing to export")
    if vendor:
        raise ExportError(VENDOR_HELP)
    if settings.repo_root is None or settings.config_path is None:
        raise ExportError("Export must run from a repository checkout with config/oai.toml")
    repo = settings.repo_root
    commit, dirty = git_state(repo)
    if dirty and not allow_dirty:
        raise ExportError(
            "Working tree has uncommitted changes; commit first or pass --allow-dirty"
        )
    builders = builders or default_builders(repo)

    if run_local and "local" in analysis.stages:
        run_analysis(analysis, settings, stage="local")
    frame_path = frame_dir(analysis, settings, os.environ, DEFAULT_LABEL) / analysis.export.frame
    if not frame_path.is_file():
        raise ExportError(f"Frame {frame_path} not found; run the local steps first")
    frame = pl.read_parquet(frame_path)
    missing = [c for c in analysis.export.columns if c not in frame.columns]
    if missing:
        raise ExportError(f"Frame is missing declared export columns: {missing}")
    frame = frame.select(analysis.export.columns)

    stamp = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    bundle_name = f"{analysis.name}-{stamp}"
    out_dir = out_dir or settings.work_dir / "bundles"
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp) / bundle_name
        for sub in ("code", "env", "data", "config"):
            (stage / sub).mkdir(parents=True)
        builders.python_wheel(stage / "code")
        if "r" in analysis.languages:
            builders.r_package(stage / "code")
            shutil.copy2(repo / "r" / "renv.lock", stage / "env" / "renv.lock")
        builders.python_requirements(stage / "env")
        shutil.copytree(
            analysis.root,
            stage / "code" / "analyses" / analysis.name,
            ignore=shutil.ignore_patterns("__pycache__", "*.parquet"),
        )
        shutil.copy2(settings.config_path, stage / "config" / "oai.toml")
        frame.write_parquet(stage / "data" / analysis.export.frame)
        for template, mode in (("run.sh", 0o755), ("README_ENCLAVE.md", 0o644)):
            target = stage / template
            target.write_text(_render(template, analysis.name))
            target.chmod(mode)

        files = sorted(p for p in stage.rglob("*") if p.is_file())
        checksums = {p.relative_to(stage).as_posix(): sha256_file(p) for p in files}
        (stage / "SHA256SUMS").write_text("".join(f"{h}  {rel}\n" for rel, h in checksums.items()))
        manifest: dict[str, Any] = {
            "analysis": analysis.name,
            "created_utc": stamp,
            "git_commit": commit,
            "git_dirty": dirty,
            "oai_version": __version__,
            "frame": {
                "file": f"data/{analysis.export.frame}",
                "rows": frame.height,
                "columns": list(frame.columns),
            },
            "files": checksums,
        }
        (stage / "MANIFEST.json").write_text(json.dumps(manifest, indent=2))
        tar_path = out_dir / f"{bundle_name}.tar.gz"
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(stage, arcname=bundle_name)
    _append_export_log(settings, tar_path, manifest)
    return BundleResult(tar_path, manifest)
