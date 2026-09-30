"""`oai` command line."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

import typer

from oai import __version__
from oai.catalog import catalog_for
from oai.config import get_settings
from oai.errors import OAIError
from oai.export.egress import EgressError, check_egress
from oai.manifest import find_analysis, list_analyses
from oai.runner import run_analysis

app = typer.Typer(help="OAI analytics command line.", no_args_is_help=True)


@contextmanager
def user_errors() -> Iterator[None]:
    """Show OAIError messages without a traceback and exit 1."""
    try:
        yield
    except OAIError as exc:
        typer.secho(f"error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1) from None


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option("--version", callback=_version_callback, is_eager=True, help="Show version."),
    ] = False,
) -> None:
    """OAI analytics."""


@app.command()
def catalog() -> None:
    """List the OAI tables found in OAI_DATA_DIR."""
    with user_errors():
        settings = get_settings()
        cat = catalog_for(settings.data_dir)
        for table in cat.tables():
            visits = cat.visits(table)
            typer.echo(f"{table:<32} {' '.join(visits) if visits else '(no visit)'}")
        typer.echo(f"\n{len(cat)} files, {len(cat.tables())} tables in {settings.data_dir}")


@app.command()
def analyses() -> None:
    """List analyses and validate their manifests."""
    with user_errors():
        for a in list_analyses(get_settings().analyses_dir):
            typer.echo(f"{a.name:<28} [{','.join(sorted(a.stages))}] {a.description}")


@app.command()
def run(
    name: Annotated[str, typer.Argument(help="Analysis folder name under analyses/.")],
    stage: Annotated[
        str | None, typer.Option(help="Only run steps of this stage (local|enclave).")
    ] = None,
    step: Annotated[str | None, typer.Option(help="Only run this step id.")] = None,
) -> None:
    """Run an analysis's steps in declared order."""
    with user_errors():
        settings = get_settings()
        analysis = find_analysis(name, settings.analyses_dir)
        results = run_analysis(analysis, settings, stage=stage, step_id=step, echo=typer.echo)
        typer.echo(f"{len(results)} step(s) completed: {', '.join(r.step_id for r in results)}")


@app.command("check-egress")
def check_egress_cmd(
    results_dir: Annotated[Path, typer.Argument(help="Directory of results to be released.")],
    min_cell: Annotated[int | None, typer.Option(help="Override [egress] min_cell.")] = None,
) -> None:
    """Verify a results directory holds only aggregate, non-identifying outputs."""
    with user_errors():
        cfg = get_settings().project.get("egress", {})
        threshold = min_cell if min_cell is not None else cfg.get("min_cell")
        if threshold is None:
            raise EgressError("No [egress] min_cell in config/oai.toml and no --min-cell given")
        report = check_egress(
            results_dir,
            min_cell=int(threshold),
            ignore_id_pattern_columns=cfg.get("ignore_id_pattern_columns", []),
        )
    for problem in report.problems:
        typer.secho(f"FAIL   {problem}", err=True, fg=typer.colors.RED)
    for path in report.manual_review:
        typer.echo(f"REVIEW {path}")
    typer.echo(
        f"{len(report.checked)} file(s) checked; {len(report.problems)} problem(s); "
        f"{len(report.manual_review)} need manual review"
    )
    if not report.ok:
        raise typer.Exit(1)
