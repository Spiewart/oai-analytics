"""`oai report`: render an analysis's Quarto report ([report] in analysis.toml) to PDF.

The documents and their assets are copied into <results_dir>/<analysis>/report/ and each is
rendered there with `quarto render <document> --to typst`, so nothing is written into the
repository. R chunks start through r/step-profile.R under the `report` renv profile, which
loads oaimodels and oaireport. A [report] `combined` PDF joins the documents' PDFs. After a
successful render only the PDFs and figures/ remain, so `oai check-egress` sees nothing but
reviewable outputs; a failed render is left in place.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from oai.assumptions import DEFAULT_LABEL
from oai.config import Settings
from oai.errors import OAIError
from oai.manifest import Analysis, ReportSpec
from oai.pdfjoin import combine_pdfs
from oai.runner import RUN_INFO_FILE, is_finished, r_profile_env, run_analysis, run_results_dir

REPORT_DIR = "report"
FIGURES_DIR = "figures"
RENV_PROFILE = "report"
QUARTO_BUNDLES = (Path("/Applications/RStudio.app/Contents/Resources/app/quarto/bin/quarto"),)
STDERR_TAIL_LINES = 40


class ReportError(OAIError):
    """A report could not be prepared or rendered."""


def _executable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def find_quarto(
    env: Mapping[str, str],
    configured: str | None = None,
    bundles: Sequence[Path] = QUARTO_BUNDLES,
) -> Path:
    """OAI_QUARTO, then [tools] quarto in config/oai.toml, then PATH, then RStudio's bundle."""
    for source, raw in (("OAI_QUARTO", env.get("OAI_QUARTO")), ("[tools] quarto", configured)):
        if raw:
            path = Path(raw).expanduser()
            if not _executable(path):
                raise ReportError(f"{source}={raw} is not an executable Quarto")
            return path
    on_path = shutil.which("quarto", path=env.get("PATH"))
    if on_path:
        return Path(on_path)
    for bundle in bundles:
        if _executable(bundle):
            return bundle
    raise ReportError(
        "Quarto not found: install it (https://quarto.org) or set OAI_QUARTO to its path"
    )


def _spec(analysis: Analysis) -> ReportSpec:
    if analysis.report is None:
        raise ReportError(f"{analysis.name} has no [report] section in analysis.toml")
    return analysis.report


def missing_runs(analysis: Analysis, settings: Settings) -> list[str]:
    """The [report] runs without a finished run of every local step."""
    local = [s.id for s in analysis.steps if s.stage == "local"]
    return [
        label
        for label in _spec(analysis).runs
        if not is_finished(run_results_dir(analysis, settings, label), local)
    ]


def _tail(text: str) -> str:
    return "\n".join(text.strip().splitlines()[-STDERR_TAIL_LINES:])


def render_report(
    analysis: Analysis,
    settings: Settings,
    *,
    run_missing: bool = False,
    base_env: Mapping[str, str] | None = None,
    echo: Callable[[str], None] = print,
    bundles: Sequence[Path] = QUARTO_BUNDLES,
) -> list[Path]:
    """Render the analysis's report documents; returns their PDFs, then the combined PDF."""
    spec = _spec(analysis)
    env = dict(os.environ if base_env is None else base_env)
    missing = missing_runs(analysis, settings)
    if missing and not run_missing:
        raise ReportError(
            f"{analysis.name}: no finished run for {', '.join(missing)}; "
            f"run `oai report {analysis.name} --run` to run them first"
        )
    for label in missing:
        variant = None if label == DEFAULT_LABEL else label
        run_analysis(analysis, settings, variant=variant, base_env=env, echo=echo)
    quarto = find_quarto(env, settings.project.get("tools", {}).get("quarto"), bundles)
    results_root = settings.results_dir / analysis.name
    out = results_root / REPORT_DIR
    if (out / RUN_INFO_FILE).exists():
        raise ReportError(
            f"{out} holds a run (a variant named {REPORT_DIR!r}?); rename that variant, "
            "because rendering replaces this folder"
        )
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for name in (*spec.documents, *spec.assets):
        shutil.copy2(analysis.root / name, out / name)
    env.update(
        OAI_ANALYSIS=analysis.name,
        OAI_RESULTS_ROOT=str(results_root),
        OAI_REPORT_DIR=str(out),
        OAI_REPORT_RUNS=",".join(spec.runs),
        RENV_PROFILE=RENV_PROFILE,
    )
    for key, value in r_profile_env(settings).items():
        env.setdefault(key, value)
    pdfs: list[Path] = []
    # Untracked local assets (e.g. the brief's author file) are copied if present and always
    # removed, even when a render or the join fails; other partial output is kept for debugging
    local: list[Path] = []
    try:
        for name in spec.local_assets:
            if (analysis.root / name).is_file():
                local.append(out / name)
                shutil.copy2(analysis.root / name, out / name)
        echo(f"==> {analysis.name}: rendering with {quarto}")
        for document in spec.documents:
            echo(f"==> {analysis.name}: rendering {document}")
            proc = subprocess.run(
                [str(quarto), "render", document, "--to", "typst"],
                cwd=out,
                env=env,
                capture_output=True,
                text=True,
            )
            pdf = out / f"{Path(document).stem}.pdf"
            if proc.returncode != 0 or not pdf.is_file():
                raise ReportError(
                    f"quarto render of {document} failed (exit {proc.returncode}); "
                    f"partial output kept in {out}\n" + _tail(proc.stderr or proc.stdout)
                )
            pdfs.append(pdf)
        if spec.combined:
            titles = spec.part_titles or tuple(Path(d).stem for d in spec.documents)
            echo(f"==> {analysis.name}: joining {len(pdfs)} PDFs into {spec.combined}")
            pdfs.append(combine_pdfs(list(zip(titles, pdfs, strict=True)), out / spec.combined))
    finally:
        for path in local:
            path.unlink(missing_ok=True)
    keep = set(pdfs)
    for child in out.iterdir():
        if child in keep or child.name == FIGURES_DIR:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    return pdfs
