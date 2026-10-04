"""Join PDFs into one, with a top-level bookmark per part.

`oai report` uses this for an analysis whose [report] sets `combined`. pypdf is a dev
dependency (report rendering is local-only, like Quarto), so it is imported only when a join
is asked for and enclave bundles never need it.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from oai.errors import OAIError


class PdfJoinError(OAIError):
    """PDFs could not be joined."""


def combine_pdfs(parts: Sequence[tuple[str, Path]], out: Path) -> Path:
    """Write the parts' pages in order to `out`; each part gets a bookmark with its title,
    and the part's own bookmarks are nested under it. Returns `out`."""
    if not parts:
        raise PdfJoinError("no PDFs to join")
    for _, path in parts:
        if not Path(path).is_file():
            raise PdfJoinError(f"missing PDF: {path}")
    try:
        from pypdf import PdfWriter
    except ImportError as exc:  # pragma: no cover - dev dependency
        raise PdfJoinError("joining PDFs needs pypdf: run `uv sync` (a dev dependency)") from exc
    writer = PdfWriter()
    for title, path in parts:
        writer.append(str(path), outline_item=title)
    with Path(out).open("wb") as handle:
        writer.write(handle)
    return Path(out)
