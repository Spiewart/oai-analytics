"""Execute an analysis's steps in declared order.

Each run resolves the analysis's assumptions (variant + `--set` overrides) into a run
label: "default", "<variant>" or "<base>+custom-<hash>". Steps run as subprocesses in
the analysis folder with:
  OAI_ANALYSIS     analysis name
  OAI_RUN_LABEL    the run label
  OAI_FRAME_DIR    frames: OAI_WORK_DIR/<analysis>/<label> (a bundle's run.sh sets it
                   explicitly to the bundle's data/, which is then used as-is)
  OAI_RESULTS_DIR  aggregate outputs: <results_dir>/<analysis>/<label>
  OAI_ASSUMPTIONS  the per-label assumptions.resolved.json in OAI_RESULTS_DIR
Each run also writes OAI_RESULTS_DIR/run_info.json (analysis, label, variant, git commit,
start/finish times, oai version, steps); finished_utc stays null unless every step succeeds.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from oai import __version__
from oai.assumptions import DEFAULT_LABEL, Resolved, load_assumptions
from oai.catalog import catalog_for
from oai.config import Settings
from oai.errors import OAIError
from oai.loader import table_version
from oai.manifest import STAGES, Analysis, Step

RUN_INFO_FILE = "run_info.json"


class RunnerError(OAIError):
    """A step could not be selected, started or completed."""


@dataclass(frozen=True)
class StepResult:
    step_id: str
    returncode: int


def select_steps(
    analysis: Analysis, *, stage: str | None = None, step_id: str | None = None
) -> list[Step]:
    if stage is not None and stage not in STAGES:
        raise RunnerError(f"stage must be one of {', '.join(STAGES)}, not {stage!r}")
    steps = list(analysis.steps)
    if step_id is not None:
        steps = [s for s in steps if s.id == step_id]
        if not steps:
            raise RunnerError(f"{analysis.name} has no step {step_id!r}")
    if stage is not None:
        steps = [s for s in steps if s.stage == stage]
    if not steps:
        raise RunnerError(f"No steps of {analysis.name} match stage={stage!r} step={step_id!r}")
    return steps


def frame_dir(
    analysis: Analysis, settings: Settings, env: Mapping[str, str], label: str = DEFAULT_LABEL
) -> Path:
    """Where a run's frames live; an explicit OAI_FRAME_DIR (a bundle) is used as-is."""
    override = env.get("OAI_FRAME_DIR")
    return Path(override) if override else settings.work_dir / analysis.name / label


def run_results_dir(analysis: Analysis, settings: Settings, label: str = DEFAULT_LABEL) -> Path:
    """Aggregate outputs of one run: <results_dir>/<analysis>/<label>."""
    return settings.results_dir / analysis.name / label


def checkout_state(repo_root: Path | None) -> tuple[str | None, bool]:
    """(HEAD commit, has uncommitted changes) of a git checkout; (None, False) outside one."""
    if repo_root is None or shutil.which("git") is None:
        return None, False
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True
    )
    if head.returncode != 0:
        return None, False
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo_root, capture_output=True, text=True
    )
    return head.stdout.strip(), bool(status.stdout.strip())


def is_finished(results: Path, steps: Iterable[str] = ()) -> bool:
    """True when results/run_info.json records a successful run that included `steps`.

    A run of only some steps (`--step`, `--stage`) does not finish the steps it skipped.
    """
    try:
        info = json.loads((results / RUN_INFO_FILE).read_text())
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(info, dict) or not info.get("finished_utc"):
        return False
    ran = info.get("steps")
    return isinstance(ran, list) and set(steps) <= set(ran)


def data_versions(analysis: Analysis, settings: Settings) -> dict[str, str]:
    """VERSION of each declared input file, e.g. {"allclinical_10": "10.2.2"}.

    Empty when the release is not available here (no OAI_DATA_DIR, e.g. in the enclave).
    """
    try:
        catalog = catalog_for(settings.data_dir)
        files = [tf for spec in analysis.inputs for tf in catalog.resolve_input(spec)]
        versions = {tf.key: table_version(tf) for tf in files}
    except (OAIError, OSError):
        return {}
    return {key: version for key, version in versions.items() if version is not None}


def r_profile_env(settings: Settings) -> dict[str, str]:
    """OAI_R_DIR and R_PROFILE_USER, so R starts through r/step-profile.R (checkouts only)."""
    r_profile = settings.repo_root / "r" / "step-profile.R" if settings.repo_root else None
    if r_profile is None or not r_profile.is_file():
        return {}
    return {"OAI_R_DIR": str(r_profile.parent), "R_PROFILE_USER": str(r_profile)}


def process_env(step: Step, analysis: Analysis, env: Mapping[str, str]) -> dict[str, str]:
    """One step's environment: R steps get the analysis's renv profile ([r] profile)."""
    out = dict(env)
    if step.lang == "r" and analysis.r_profile:
        out["RENV_PROFILE"] = analysis.r_profile
    return out


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def resolve_assumptions(
    analysis: Analysis, variant: str | None = None, overrides: Mapping[str, object] | None = None
) -> Resolved:
    return load_assumptions(analysis.root).resolve(analysis.name, variant, overrides)


def step_env(
    analysis: Analysis,
    settings: Settings,
    base_env: Mapping[str, str] | None = None,
    *,
    resolved: Resolved | None = None,
) -> dict[str, str]:
    env = dict(os.environ if base_env is None else base_env)
    resolved = resolved or resolve_assumptions(analysis)
    frames = frame_dir(analysis, settings, env, resolved.label)
    results = run_results_dir(analysis, settings, resolved.label)
    frames.mkdir(parents=True, exist_ok=True)
    results.mkdir(parents=True, exist_ok=True)
    resolved.write(frames)
    # Point steps at the results copy: results are always per label, while an explicit
    # OAI_FRAME_DIR (a bundle) is shared by every run.
    assumptions_path = resolved.write(results)
    env.update(
        OAI_ANALYSIS=analysis.name,
        OAI_FRAME_DIR=str(frames),
        OAI_RESULTS_DIR=str(results),
        OAI_ASSUMPTIONS=str(assumptions_path),
        OAI_RUN_LABEL=resolved.label,
    )
    for key, value in r_profile_env(settings).items():
        env.setdefault(key, value)
    return env


def step_command(step: Step, analysis: Analysis) -> list[str]:
    entry = str(analysis.root / step.entry)
    if step.lang == "python":
        return [sys.executable, entry]
    rscript = shutil.which("Rscript")
    if rscript is None:
        raise RunnerError("Rscript not found on PATH; install R to run R steps")
    return [rscript, entry]


def run_analysis(
    analysis: Analysis,
    settings: Settings,
    *,
    stage: str | None = None,
    step_id: str | None = None,
    variant: str | None = None,
    overrides: Mapping[str, object] | None = None,
    base_env: Mapping[str, str] | None = None,
    echo: Callable[[str], None] = print,
) -> list[StepResult]:
    steps = select_steps(analysis, stage=stage, step_id=step_id)
    resolved = resolve_assumptions(analysis, variant, overrides)  # fail before running anything
    if any(s.stage == "enclave" for s in steps) and settings.geno_dir is None:
        raise RunnerError(
            "Enclave steps require OAI_GENO_DIR; they only run inside the secure enclave."
        )
    commands = [(step, step_command(step, analysis)) for step in steps]
    env = step_env(analysis, settings, base_env, resolved=resolved)
    commit, dirty = checkout_state(settings.repo_root)
    info: dict[str, object] = {
        "analysis": analysis.name,
        "label": resolved.label,
        "variant": resolved.variant,
        "git_commit": commit,
        "git_dirty": dirty,
        "started_utc": _utc_now(),
        "finished_utc": None,
        "oai_version": __version__,
        "steps": [s.id for s in steps],
        "data_versions": data_versions(analysis, settings),
    }
    info_path = Path(env["OAI_RESULTS_DIR"]) / RUN_INFO_FILE
    info_path.write_text(json.dumps(info, indent=2))
    results: list[StepResult] = []
    for step, cmd in commands:
        echo(f"==> {analysis.name}:{step.id} [{resolved.label}] ({step.lang}, {step.stage})")
        proc = subprocess.run(cmd, cwd=analysis.root, env=process_env(step, analysis, env))
        results.append(StepResult(step.id, proc.returncode))
        if proc.returncode != 0:
            raise RunnerError(f"step {step.id!r} failed with exit code {proc.returncode}")
    info["finished_utc"] = _utc_now()
    info_path.write_text(json.dumps(info, indent=2))
    return results
