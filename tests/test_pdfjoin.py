"""Joining PDFs for `oai report`'s combined document."""

import logging
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PyPdfError

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


def test_a_part_that_is_not_a_pdf_is_an_oai_error_and_leaves_no_output(tmp_path):
    good = blank_pdf(tmp_path / "good.pdf", 1)
    bad = tmp_path / "x.pdf"
    bad.write_text("not a pdf")
    out = tmp_path / "both.pdf"
    with pytest.raises(PdfJoinError, match="could not join PDFs"):
        combine_pdfs([("Good", good), ("Bad", bad)], out)
    # the write is atomic: neither the output nor its temporary file is left behind
    assert sorted(p.name for p in tmp_path.iterdir()) == ["good.pdf", "x.pdf"]


def test_an_output_folder_that_does_not_exist_is_an_oai_error(tmp_path):
    brief = blank_pdf(tmp_path / "brief.pdf", 1)
    with pytest.raises(PdfJoinError, match="could not join PDFs"):
        combine_pdfs([("Brief", brief)], tmp_path / "nowhere" / "both.pdf")


def test_a_failed_write_keeps_an_existing_output_intact(tmp_path, monkeypatch):
    brief = blank_pdf(tmp_path / "brief.pdf", 1)
    out = tmp_path / "both.pdf"
    out.write_text("previous")

    def explode(self, stream):
        stream.write(b"%PDF-partial")
        raise OSError("disk full")

    monkeypatch.setattr(PdfWriter, "write", explode)
    with pytest.raises(PdfJoinError, match="could not join PDFs: disk full"):
        combine_pdfs([("Brief", brief)], out)
    assert out.read_text() == "previous"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["both.pdf", "brief.pdf"]


def test_an_output_path_under_a_regular_file_is_an_oai_error(tmp_path):
    brief = blank_pdf(tmp_path / "brief.pdf", 1)
    blocker = tmp_path / "file.txt"
    blocker.write_text("a file, not a folder")
    # the cleanup unlink raises NotADirectoryError here: it must not replace the join error
    with pytest.raises(PdfJoinError, match="could not join PDFs"):
        combine_pdfs([("Brief", brief)], blocker / "out.pdf")


def test_the_pypdf_logger_level_is_restored_after_a_failed_join(tmp_path):
    good = blank_pdf(tmp_path / "good.pdf", 1)
    bad = tmp_path / "x.pdf"
    bad.write_text("not a pdf")
    logger = logging.getLogger("pypdf")
    before = logger.level
    try:
        logger.setLevel(logging.WARNING)
        with pytest.raises(PdfJoinError):
            combine_pdfs([("Good", good), ("Bad", bad)], tmp_path / "both.pdf")
        assert logger.level == logging.WARNING
        with pytest.raises(PdfJoinError):
            combine_pdfs([("Good", good)], tmp_path / "nowhere" / "both.pdf")
        assert logger.level == logging.WARNING
    finally:
        logger.setLevel(before)


def test_a_nonsensical_output_path_leaves_the_pypdf_logger_alone(tmp_path):
    brief = blank_pdf(tmp_path / "brief.pdf", 1)
    logger = logging.getLogger("pypdf")
    before = logger.level
    try:
        logger.setLevel(logging.WARNING)
        with pytest.raises((PdfJoinError, ValueError)):
            combine_pdfs([("Brief", brief)], Path("."))
        assert logger.level == logging.WARNING
    finally:
        logger.setLevel(before)


def test_the_wrapped_error_keeps_the_original_as_its_cause(tmp_path):
    good = blank_pdf(tmp_path / "good.pdf", 1)
    bad = tmp_path / "x.pdf"
    bad.write_text("not a pdf")
    with pytest.raises(PdfJoinError) as caught:
        combine_pdfs([("Good", good), ("Bad", bad)], tmp_path / "both.pdf")
    cause = caught.value.__cause__
    assert isinstance(cause, (PyPdfError, OSError))
    assert str(cause) in str(caught.value)
