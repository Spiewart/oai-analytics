"""`oai` command line."""

from __future__ import annotations

from typing import Annotated

import typer

from oai import __version__

app = typer.Typer(help="OAI analytics command line.", no_args_is_help=True)


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
