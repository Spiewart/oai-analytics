"""Joining PDFs for `oai report`'s combined document."""

from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from oai.pdfjoin import PdfJoinError, combine_pdfs


def blank_pdf(
    path: Path, pages: int, bookmark: str | None = None, title: str | None = None
) -> Path:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    if bookmark:
        writer.add_outline_item(bookmark, 0)
    if title:
        writer.add_metadata({"/Title": title})
    with path.open("wb") as handle:
        writer.write(handle)
    return path


def test_combine_keeps_every_page_in_order_with_a_bookmark_per_part(tmp_path):
    brief = blank_pdf(tmp_path / "brief.pdf", 2, bookmark="Inner")
    report = blank_pdf(tmp_path / "report.pdf", 3)
    out = combine_pdfs([("Brief", brief), ("Appendix", report)], tmp_path / "both.pdf")
    assert out == tmp_path / "both.pdf"
    reader = PdfReader(out)
    assert len(reader.pages) == 5
    top = [item for item in reader.outline if not isinstance(item, list)]
    assert [(i.title, reader.get_destination_page_number(i)) for i in top] == [
        ("Brief", 0),
        ("Appendix", 2),
    ]
    nested = [item for item in reader.outline if isinstance(item, list)]
    assert [[i.title for i in group] for group in nested] == [["Inner"]]


def test_combine_carries_the_first_parts_title(tmp_path):
    brief = blank_pdf(tmp_path / "brief.pdf", 1, title="Is reported walking really walking?")
    report = blank_pdf(tmp_path / "report.pdf", 1, title="Technical report")
    out = combine_pdfs([("Brief", brief), ("Appendix", report)], tmp_path / "both.pdf")
    assert PdfReader(out).metadata.title == "Is reported walking really walking?"


def test_combine_rejects_no_parts_and_missing_files(tmp_path):
    with pytest.raises(PdfJoinError, match="no PDFs to join"):
        combine_pdfs([], tmp_path / "x.pdf")
    with pytest.raises(PdfJoinError, match="missing PDF"):
        combine_pdfs([("A", tmp_path / "nope.pdf")], tmp_path / "x.pdf")
    assert not (tmp_path / "x.pdf").exists()
