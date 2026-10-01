"""`oai` command line."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

import typer

from oai import __version__
from oai.assumptions import (
    LEDGER_FILE,
    AssumptionsError,
    load_assumptions,
    parse_override,
    render_ledger,
)
from oai.catalog import catalog_for
from oai.config import get_settings
from oai.errors import OAIError
from oai.export.bundle import export_analysis
from oai.export.egress import EgressError, check_egress
from oai.loader import missing_summary
from oai.manifest import find_analysis, list_analyses
from oai.report import render_report
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
    variant: Annotated[
        str | None, typer.Option(help="Named variant from the analysis's assumptions.toml.")
    ] = None,
    set_: Annotated[
        list[str] | None,
        typer.Option("--set", help="Override an assumption, key=value (repeatable)."),
    ] = None,
) -> None:
    """Run an analysis's steps in declared order."""
    with user_errors():
        overrides = dict(parse_override(text) for text in set_ or [])
        settings = get_settings()
        analysis = find_analysis(name, settings.analyses_dir)
        results = run_analysis(
            analysis,
            settings,
            stage=stage,
            step_id=step,
            variant=variant,
            overrides=overrides,
            echo=typer.echo,
        )
        typer.echo(f"{len(results)} step(s) completed: {', '.join(r.step_id for r in results)}")


@app.command()
def report(
    name: Annotated[str, typer.Argument(help="Analysis folder name under analyses/.")],
    run_: Annotated[
        bool,
        typer.Option("--run", help="First run any [report] runs that have not finished."),
    ] = False,
) -> None:
    """Render an analysis's [report] (Quarto -> PDF) under OAI_RESULTS_DIR."""
    with user_errors():
        settings = get_settings()
        analysis = find_analysis(name, settings.analyses_dir)
        pdf = render_report(analysis, settings, run_missing=run_, echo=typer.echo)
    typer.echo(f"Report: {pdf}")
    typer.echo(f"Before sharing: oai check-egress {pdf.parent}")


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
            small_cell=cfg.get("small_cell", "warn"),
            ignore_id_pattern_columns=cfg.get("ignore_id_pattern_columns", []),
        )
    for problem in report.problems:
        typer.secho(f"FAIL   {problem}", err=True, fg=typer.colors.RED)
    for warning in report.warnings:
        typer.secho(f"WARN   {warning}", err=True, fg=typer.colors.YELLOW)
    for path in report.manual_review:
        typer.echo(f"REVIEW {path}")
    typer.echo(
        f"{len(report.checked)} file(s) checked; {len(report.problems)} problem(s); "
        f"{len(report.warnings)} warning(s); {len(report.manual_review)} need manual review"
    )
    if not report.ok:
        raise typer.Exit(1)


@app.command()
def export(
    name: Annotated[str, typer.Argument(help="Analysis with an [export] section.")],
    out: Annotated[
        Path | None, typer.Option(help="Output directory (default OAI_WORK_DIR/bundles).")
    ] = None,
    allow_dirty: Annotated[
        bool, typer.Option(help="Export from a tree with uncommitted changes.")
    ] = False,
    skip_local: Annotated[
        bool, typer.Option(help="Reuse the existing frame; don't rerun local steps.")
    ] = False,
    vendor: Annotated[
        bool, typer.Option(help="Vendor offline dependencies (not implemented yet).")
    ] = False,
) -> None:
    """Bundle an analysis's enclave stage with its phenotype frame."""
    with user_errors():
        settings = get_settings()
        analysis = find_analysis(name, settings.analyses_dir)
        result = export_analysis(
            analysis,
            settings,
            out_dir=out,
            allow_dirty=allow_dirty,
            run_local=not skip_local,
            vendor=vendor,
        )
        frame = result.manifest["frame"]
        typer.echo(f"Bundle: {result.path}")
        typer.echo(f"Frame: {frame['rows']} rows x {len(frame['columns'])} columns")
        typer.echo(f"Logged to {settings.work_dir / 'export_log.jsonl'}")


@app.command()
def missing(
    table: Annotated[str, typer.Argument(help="Table name, e.g. allclinical.")],
    visit: Annotated[str | None, typer.Argument(help="Visit code, e.g. 00 or V06.")] = None,
    csv: Annotated[Path | None, typer.Option(help="Also write the summary to this CSV.")] = None,
) -> None:
    """Show what the missing-value policy did to a table: code, label, count, result."""
    with user_errors():
        summary = missing_summary(table, visit)
    if summary.is_empty():
        typer.echo("No missing-value codes in this table.")
    for row in summary.iter_rows(named=True):
        result = "null" if row["value"] is None else repr(row["value"])
        reason = f"  reason={row['reason']!r}" if row["reason"] is not None else ""
        typer.echo(
            f"{row['column']:<16} {row['code']:<3} {row['n']:>8}  -> {result:<6}{reason}  {row['label']}"
        )
    typer.echo(f"\n{summary['n'].sum()} cell(s) across {summary['column'].n_unique()} column(s)")
    if csv is not None:
        summary.write_csv(csv)
        typer.echo(f"Wrote {csv}")


@app.command("assumptions")
def assumptions_cmd(
    name: Annotated[str, typer.Argument(help="Analysis folder name under analyses/.")],
    write: Annotated[
        bool, typer.Option(help="Write ASSUMPTIONS.md next to assumptions.toml.")
    ] = False,
) -> None:
    """Show (or write) an analysis's assumptions ledger."""
    with user_errors():
        analysis = find_analysis(name, get_settings().analyses_dir)
        loaded = load_assumptions(analysis.root)
        if loaded.path is None:
            raise AssumptionsError(f"{name} has no assumptions.toml")
        text = render_ledger(name, loaded)
        if write:
            out = analysis.root / LEDGER_FILE
            out.write_text(text)
            typer.echo(f"Wrote {out}")
        else:
            typer.echo(text)
