"""Join PDFs into one, with a top-level bookmark per part.

`oai report` uses this for an analysis whose [report] sets `combined`. pypdf is a dev
dependency (report rendering is local-only, like Quarto), so it is imported only when a join
is asked for and enclave bundles never need it.
"""

from __future__ import annotations

import contextlib
import logging
import os
from collections.abc import Sequence
from pathlib import Path

from oai.errors import OAIError


class PdfJoinError(OAIError):
    """PDFs could not be joined."""


def combine_pdfs(parts: Sequence[tuple[str, Path]], out: Path) -> Path:
    """Write the parts' pages in order to `out`; each part gets a bookmark with its title,
    and the part's own bookmarks are nested under it. The first part's document title, if it
    has one, becomes the joined PDF's title. Returns `out`."""
    if not parts:
        raise PdfJoinError("no PDFs to join")
    for _, path in parts:
        if not Path(path).is_file():
            raise PdfJoinError(f"missing PDF: {path}")
    try:
        from pypdf import PdfReader, PdfWriter
        from pypdf.errors import PyPdfError
    except ImportError as exc:  # pragma: no cover - dev dependency
        raise PdfJoinError("joining PDFs needs pypdf: run `uv sync` (a dev dependency)") from exc
    out = Path(out)
    # written beside `out` and moved over it, so a failure never leaves a truncated PDF
    partial = out.with_suffix(".pdf.part")
    # pypdf warns "Annotation sizes differ" on every join of Typst PDFs: quiet only its logger,
    # and only while joining. Nothing between the level change and the try may raise.
    logger = logging.getLogger("pypdf")
    level = logger.level
    logger.setLevel(logging.ERROR)
    try:
        writer = PdfWriter()
        for title, path in parts:
            writer.append(str(path), outline_item=title)
        first = PdfReader(str(parts[0][1])).metadata
        if first is not None and first.title:
            writer.add_metadata({"/Title": first.title})
        with partial.open("wb") as handle:
            writer.write(handle)
        os.replace(partial, out)
    except (PyPdfError, OSError) as exc:
        raise PdfJoinError(f"could not join PDFs: {exc}") from exc
    finally:
        logger.setLevel(level)
        # best effort: a cleanup failure must not replace the join error
        with contextlib.suppress(OSError):
            partial.unlink(missing_ok=True)
    return out
