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
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from oai.assumptions import DEFAULT_LABEL, Resolved, load_assumptions
from oai.config import Settings
from oai.errors import OAIError
from oai.manifest import STAGES, Analysis, Step


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
    results = settings.results_dir / analysis.name / resolved.label
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
    r_profile = settings.repo_root / "r" / "step-profile.R" if settings.repo_root else None
    if r_profile is not None and r_profile.is_file():
        env.setdefault("OAI_R_DIR", str(r_profile.parent))
        env.setdefault("R_PROFILE_USER", str(r_profile))
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
    results: list[StepResult] = []
    for step, cmd in commands:
        echo(f"==> {analysis.name}:{step.id} [{resolved.label}] ({step.lang}, {step.stage})")
        proc = subprocess.run(cmd, cwd=analysis.root, env=env)
        results.append(StepResult(step.id, proc.returncode))
        if proc.returncode != 0:
            raise RunnerError(f"step {step.id!r} failed with exit code {proc.returncode}")
    return results
