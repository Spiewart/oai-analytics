"""Execute an analysis's steps in declared order.

Each step runs as a subprocess in its analysis folder with:
  OAI_ANALYSIS     analysis name
  OAI_FRAME_DIR    where frames are read/written (default OAI_WORK_DIR/<analysis>;
                   a bundle's run.sh points it at the bundle's data/)
  OAI_RESULTS_DIR  aggregate outputs for this analysis (<results_dir>/<analysis>)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

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


def frame_dir(analysis: Analysis, settings: Settings, env: Mapping[str, str]) -> Path:
    override = env.get("OAI_FRAME_DIR")
    return Path(override) if override else settings.work_dir / analysis.name


def step_env(
    analysis: Analysis, settings: Settings, base_env: Mapping[str, str] | None = None
) -> dict[str, str]:
    env = dict(os.environ if base_env is None else base_env)
    frames = frame_dir(analysis, settings, env)
    results = settings.results_dir / analysis.name
    frames.mkdir(parents=True, exist_ok=True)
    results.mkdir(parents=True, exist_ok=True)
    env.update(OAI_ANALYSIS=analysis.name, OAI_FRAME_DIR=str(frames), OAI_RESULTS_DIR=str(results))
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
    base_env: Mapping[str, str] | None = None,
    echo: Callable[[str], None] = print,
) -> list[StepResult]:
    steps = select_steps(analysis, stage=stage, step_id=step_id)
    if any(s.stage == "enclave" for s in steps) and settings.geno_dir is None:
        raise RunnerError(
            "Enclave steps require OAI_GENO_DIR; they only run inside the secure enclave."
        )
    commands = [
        (step, step_command(step, analysis)) for step in steps
    ]  # fail before running anything
    env = step_env(analysis, settings, base_env)
    results: list[StepResult] = []
    for step, cmd in commands:
        echo(f"==> {analysis.name}:{step.id} ({step.lang}, {step.stage})")
        proc = subprocess.run(cmd, cwd=analysis.root, env=env)
        results.append(StepResult(step.id, proc.returncode))
        if proc.returncode != 0:
            raise RunnerError(f"step {step.id!r} failed with exit code {proc.returncode}")
    return results
