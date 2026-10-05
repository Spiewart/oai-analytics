"""Text checks on rendered PDFs."""

from oai.pdfcheck import find_terms_in, max_right_edge, right_edge_from_bbox


def test_right_edge_from_bbox():
    html = (
        '<word xMin="72.0" yMin="1" xMax="540.5" yMax="2">a</word>'
        '<word xMin="1" yMin="1" xMax="547.25" yMax="2">b</word>'
    )
    assert right_edge_from_bbox(html) == 547.25
    assert right_edge_from_bbox("<doc></doc>") is None


def test_max_right_edge_without_pdftotext(monkeypatch, tmp_path):
    monkeypatch.setattr("oai.pdfcheck.shutil.which", lambda _: None)
    assert max_right_edge(tmp_path / "x.pdf") is None


def test_find_terms_whole_words_case_insensitive():
    pages = ["A median difference, not Hodges–Lehmann.", "the bootstrapped value; BOOTSTRAP here"]
    assert find_terms_in(pages, ["Hodges–Lehmann", "bootstrap", "rank-biserial"]) == [
        ("Hodges–Lehmann", 1),
        ("bootstrap", 2),
    ]


def test_find_terms_across_a_line_break():
    pages = ["limits of\nagreement", "Hodges–\nLehmann"]
    assert find_terms_in(pages, ["limits of agreement", "Hodges–Lehmann"]) == [
        ("limits of agreement", 1),
        ("Hodges–Lehmann", 2),
    ]


def test_find_terms_stops_at_the_last_heading():
    pages = [
        "See Technical notes about the bootstrap.",
        "Results",
        "Technical notes\na Bootstrap: ...",
    ]
    # page 1's mention of the heading is not the heading: the search stops at the last occurrence
    assert find_terms_in(pages, ["bootstrap"], stop_heading="Technical notes") == [("bootstrap", 1)]
    assert (
        find_terms_in(
            ["Results only", "Technical notes\nbootstrap"],
            ["bootstrap"],
            stop_heading="Technical notes",
        )
        == []
    )
