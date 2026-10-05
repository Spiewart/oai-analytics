"""Checks on rendered PDFs: how far text reaches to the right, and terms that must not appear.

Used by the report tests; any analysis's documents can use them. pdftotext (poppler) and pypdf
are only needed when a check runs.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

_XMAX = re.compile(r'xMax="([0-9.]+)"')
_DASH_CHARS = r"[-‐‑‒–—―−­]"
_BROKEN_DASH = re.compile(f"({_DASH_CHARS})\\s*\\n\\s*")


def right_edge_from_bbox(bbox_html: str) -> float | None:
    """The largest word right edge, in points, in `pdftotext -bbox` output; None without words."""
    edges = [float(x) for x in _XMAX.findall(bbox_html)]
    return max(edges) if edges else None


def max_right_edge(pdf: Path) -> float | None:
    """The largest word right edge in a PDF, in points; None when pdftotext is unavailable.

    Raises ValueError if pdftotext runs but finds no words (e.g., a blank PDF).
    """
    if shutil.which("pdftotext") is None:
        return None
    out = subprocess.run(
        ["pdftotext", "-bbox", str(pdf), "-"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout
    edge = right_edge_from_bbox(out)
    if edge is None:
        raise ValueError(f"{pdf}: pdftotext found no words")
    return edge


def _escape_with_dash_variants(word: str) -> str:
    """Escape a word for regex, but replace dash variants with a character class."""
    result = ""
    for char in word:
        if char in "-‐‑‒–—―−­":
            result += _DASH_CHARS
        else:
            result += re.escape(char)
    return result


def _pattern(term: str) -> re.Pattern[str]:
    words = [_escape_with_dash_variants(word) for word in term.split()]
    return re.compile(r"(?<!\w)" + r"\s+".join(words) + r"(?!\w)", re.IGNORECASE)


def find_terms_in(
    pages: Sequence[str], terms: Sequence[str], stop_heading: str | None = None
) -> list[tuple[str, int]]:
    """Each term found in the pages' text, with its 1-based page.

    Matching is case-insensitive and on whole words; a term's words may be split across lines,
    and a word broken after a hyphen or dash is rejoined. With `stop_heading`, only the text
    before its last occurrence is searched (a heading such as "Technical notes" closes a document).
    """
    texts = [_BROKEN_DASH.sub(r"\1", page) for page in pages]
    if stop_heading:
        stop = _pattern(stop_heading)
        for number in range(len(texts) - 1, -1, -1):
            matches = list(stop.finditer(texts[number]))
            if matches:
                texts = texts[:number] + [texts[number][: matches[-1].start()]]
                break
    hits = []
    for number, text in enumerate(texts, start=1):
        for term in terms:
            if _pattern(term).search(text):
                hits.append((term, number))
    return hits


def find_terms(
    pdf: Path, terms: Sequence[str], stop_heading: str | None = None
) -> list[tuple[str, int]]:
    """`find_terms_in` over a PDF's pages (text extracted with pypdf)."""
    from pypdf import PdfReader

    return find_terms_in(
        [page.extract_text() or "" for page in PdfReader(pdf).pages], terms, stop_heading
    )
