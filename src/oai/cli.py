"""`oai` command line."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated

import typer

from oai import __version__
from oai.catalog import catalog_for
from oai.config import get_settings
from oai.errors import OAIError
from oai.manifest import list_analyses

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
