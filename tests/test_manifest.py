import re
import textwrap

import pytest
from typer.testing import CliRunner

from oai.cli import app
from oai.manifest import (
    ManifestError,
    ReportSpec,
    find_analysis,
    list_analyses,
    load_analysis,
)

VALID = textwrap.dedent(
    """
    name = "demo"
    description = "Demo analysis"

    [inputs]
    tables = ["enrollees", "allclinical:00", "kxr_sq_bu:*"]

    [[steps]]
    id = "frame"
    lang = "python"
    stage = "local"
    entry = "frame.py"

    [[steps]]
    id = "models"
    lang = "r"
    stage = "enclave"
    entry = "models.R"
    needs = ["frame"]

    [export]
    frame = "frame.parquet"
    columns = ["ID", "SIDE"]

    [outputs]
    aggregate = ["results/*.csv"]
    """
)


def write_analysis(parent, text, name="demo", files=("frame.py", "models.R")):
    root = parent / name
    root.mkdir(parents=True)
    (root / "analysis.toml").write_text(text)
    for f in files:
        (root / f).write_text("# stub\n")
    return root


def test_valid_manifest(tmp_path):
    a = load_analysis(write_analysis(tmp_path, VALID))
    assert a.name == "demo" and a.description == "Demo analysis"
    assert a.inputs == ("enrollees", "allclinical:00", "kxr_sq_bu:*")
    assert [s.id for s in a.steps] == ["frame", "models"]
    assert a.steps[1].needs == ("frame",) and a.steps[1].stage == "enclave"
    assert a.export.columns == ("ID", "SIDE")
    assert a.aggregate_outputs == ("results/*.csv",)
    assert a.languages == {"python", "r"} and a.stages == {"local", "enclave"}


@pytest.mark.parametrize(
    "old, new, message",
    [
        ('name = "demo"', 'name = "other"', "must match its directory"),
        ('name = "demo"', 'name = "demo\\n"', "'name' must be a lowercase identifier"),
        ('id = "frame"', 'id = "frame\\n"', r"steps\[0\].id must be a lowercase identifier"),
        ('"allclinical:00"', '"AllClinical:0"', "bad input spec"),
        ('lang = "r"', 'lang = "julia"', "lang must be one of"),
        ('stage = "enclave"', 'stage = "cloud"', "stage must be one of"),
        ('needs = ["frame"]', 'needs = ["later"]', "not an earlier step"),
        ('entry = "models.R"', 'entry = "missing.R"', "not found"),
        ('id = "models"', 'id = "frame"', "duplicate step id"),
        ('columns = ["ID", "SIDE"]', "columns = []", "non-empty 'columns'"),
    ],
)
def test_invalid_manifests(tmp_path, old, new, message):
    assert old in VALID
    with pytest.raises(ManifestError, match=message):
        load_analysis(write_analysis(tmp_path, VALID.replace(old, new)))


def test_enclave_steps_require_export(tmp_path):
    text = VALID.split("[export]")[0]
    with pytest.raises(ManifestError, match=r"must declare \[export\]"):
        load_analysis(write_analysis(tmp_path, text))


def test_invalid_toml(tmp_path):
    with pytest.raises(ManifestError, match="invalid TOML"):
        load_analysis(write_analysis(tmp_path, "name = "))


def test_find_analysis_lists_available(tmp_path):
    write_analysis(tmp_path, VALID)
    with pytest.raises(ManifestError, match="available: demo"):
        find_analysis("nope", tmp_path)


def test_list_analyses(tmp_path):
    write_analysis(tmp_path, VALID)
    assert [a.name for a in list_analyses(tmp_path)] == ["demo"]


def test_cli_analyses(tmp_path, monkeypatch):
    write_analysis(tmp_path, VALID)
    monkeypatch.setenv("OAI_ANALYSES_DIR", str(tmp_path))
    result = CliRunner().invoke(app, ["analyses"])
    assert result.exit_code == 0, result.output
    assert "demo" in result.stdout and "[enclave,local]" in result.stdout


REPORT_MANIFEST = textwrap.dedent(
    """
    name = "demo"

    [[steps]]
    id = "frame"
    lang = "python"
    entry = "frame.py"

    [report]
    entry = "report.qmd"
    runs = ["default", "alt"]
    assets = ["notes.md"]
    """
)
REPORT_ASSUMPTIONS = textwrap.dedent(
    """
    [cohort.min_age]
    value = 50
    status = "confirmed"
    source = "test"

    [variants.alt]
    description = "older"
    set = { "cohort.min_age" = 60 }
    """
)


def write_report_analysis(tmp_path, manifest=REPORT_MANIFEST):
    root = write_analysis(tmp_path, manifest, files=("frame.py", "report.qmd", "notes.md"))
    (root / "assumptions.toml").write_text(REPORT_ASSUMPTIONS)
    return root


def test_report_section_parsed(tmp_path):
    analysis = load_analysis(write_report_analysis(tmp_path))
    assert analysis.report == ReportSpec(("report.qmd",), ("default", "alt"), ("notes.md",))


def test_report_section_is_optional(tmp_path):
    assert load_analysis(write_analysis(tmp_path, VALID)).report is None


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ('entry = "report.qmd"', 'entry = "missing.qmd"', "entry 'missing.qmd'"),
        ('entry = "report.qmd"', 'entry = "notes.md"', "must be a .qmd file"),
        ('entry = "report.qmd"', 'entry = "../demo/report.qmd"', "directly in"),
        ('runs = ["default", "alt"]', "runs = []", "non-empty list"),
        ('runs = ["default", "alt"]', 'runs = ["default", "default"]', "duplicates"),
        ('runs = ["default", "alt"]', 'runs = ["default", "nope"]', "runs nope are not"),
        ('assets = ["notes.md"]', 'assets = ["missing.md"]', "asset 'missing.md'"),
        ('assets = ["notes.md"]', 'assets = ["../demo/notes.md"]', "asset '../demo/notes.md'"),
        ('assets = ["notes.md"]', 'assets = "notes.md"', "assets must be a list"),
    ],
)
def test_invalid_report_sections(tmp_path, old, new, message):
    root = write_report_analysis(tmp_path, REPORT_MANIFEST.replace(old, new))
    with pytest.raises(ManifestError, match=re.escape(message)):
        load_analysis(root)


DOCS_MANIFEST = REPORT_MANIFEST.replace(
    'entry = "report.qmd"',
    'documents = ["brief.qmd", "report.qmd"]\n'
    'combined = "together.pdf"\n'
    'part_titles = ["Brief", "Appendix"]\n'
    'local_assets = ["brief.local.yml"]',
)


def write_docs_analysis(tmp_path, manifest=DOCS_MANIFEST):
    root = write_report_analysis(tmp_path, manifest)
    (root / "brief.qmd").write_text("# brief\n")
    return root


def test_single_entry_is_one_document(tmp_path):
    spec = load_analysis(write_report_analysis(tmp_path)).report
    assert spec.documents == ("report.qmd",)
    assert spec.combined is None and spec.part_titles == () and spec.local_assets == ()


def test_documents_combined_titles_and_local_assets_parsed(tmp_path):
    analysis = load_analysis(write_docs_analysis(tmp_path))
    assert analysis.report == ReportSpec(
        ("brief.qmd", "report.qmd"),
        ("default", "alt"),
        ("notes.md",),
        "together.pdf",
        ("Brief", "Appendix"),
        ("brief.local.yml",),
    )


DOCS_LINE = 'documents = ["brief.qmd", "report.qmd"]'


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        (DOCS_LINE, DOCS_LINE + '\nentry = "report.qmd"', "takes entry or documents, not both"),
        (DOCS_LINE, "documents = []", "documents must be a non-empty list"),
        (DOCS_LINE, 'documents = "brief.qmd"', "documents must be a non-empty list"),
        (DOCS_LINE, 'documents = ["brief.qmd", "brief.qmd"]', "documents has duplicates"),
        (DOCS_LINE, 'documents = ["brief.qmd", "missing.qmd"]', "documents 'missing.qmd'"),
        (DOCS_LINE, 'documents = ["brief.qmd", "notes.md"]', "must be a .qmd file"),
        ('combined = "together.pdf"', 'combined = "together.html"', "must be a .pdf file name"),
        ('combined = "together.pdf"', 'combined = "out/together.pdf"', "must be a .pdf file name"),
        ('combined = "together.pdf"', 'combined = "report.pdf"', "would overwrite"),
        ('combined = "together.pdf"', 'combined = ".pdf"', "must be a .pdf file name"),
        ('combined = "together.pdf"', "combined = 3", "must be a .pdf file name"),
        (DOCS_LINE, 'documents = ["brief.qmd", 3]', "must be a .qmd file"),
        (
            'assets = ["notes.md"]',
            'assets = ["notes.md", "notes.md"]',
            "[report] assets has duplicates",
        ),
        (
            'local_assets = ["brief.local.yml"]',
            'local_assets = ["brief.local.yml", "brief.local.yml"]',
            "[report] local_assets has duplicates",
        ),
        (
            'local_assets = ["brief.local.yml"]',
            'local_assets = ["together.pdf"]',
            "combined 'together.pdf' would overwrite an asset",
        ),
        (
            'part_titles = ["Brief", "Appendix"]',
            'part_titles = ["Brief"]',
            "one title per document",
        ),
        ('part_titles = ["Brief", "Appendix"]', 'part_titles = ["Brief", ""]', "list of titles"),
        ('part_titles = ["Brief", "Appendix"]', 'part_titles = ["Brief", "  "]', "list of titles"),
        (
            'local_assets = ["brief.local.yml"]',
            'local_assets = ["../x.yml"]',
            "local_assets must be",
        ),
        (
            'local_assets = ["brief.local.yml"]',
            'local_assets = "brief.local.yml"',
            "local_assets must be",
        ),
        ('local_assets = ["brief.local.yml"]', 'local_assets = [".."]', "local_assets must be"),
        ('local_assets = ["brief.local.yml"]', 'local_assets = ["."]', "local_assets must be"),
    ],
)
def test_invalid_document_sections(tmp_path, old, new, message):
    root = write_docs_analysis(tmp_path, DOCS_MANIFEST.replace(old, new))
    with pytest.raises(ManifestError, match=re.escape(message)):
        load_analysis(root)


def test_combined_may_not_overwrite_an_existing_asset(tmp_path):
    root = write_docs_analysis(
        tmp_path,
        DOCS_MANIFEST.replace('assets = ["notes.md"]', 'assets = ["notes.md", "together.pdf"]'),
    )
    (root / "together.pdf").write_bytes(b"%PDF-")
    with pytest.raises(ManifestError, match=re.escape("combined 'together.pdf' would overwrite")):
        load_analysis(root)


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        ('combined = "together.pdf"', "combined needs documents"),
        ('part_titles = ["Report"]', "part_titles needs combined"),
    ],
)
def test_combined_and_titles_need_documents(tmp_path, extra, message):
    manifest = REPORT_MANIFEST.replace('assets = ["notes.md"]', f'assets = ["notes.md"]\n{extra}')
    with pytest.raises(ManifestError, match=re.escape(message)):
        load_analysis(write_report_analysis(tmp_path, manifest))


SELECT_MANIFEST = DOCS_MANIFEST.replace(
    'part_titles = ["Brief", "Appendix"]',
    'part_titles = ["Brief"]\ncombined_documents = ["brief.qmd"]',
)


def test_combined_documents_parsed(tmp_path):
    spec = load_analysis(write_docs_analysis(tmp_path, SELECT_MANIFEST)).report
    assert spec.combined_documents == ("brief.qmd",)
    assert spec.part_titles == ("Brief",)


def test_combined_documents_default_to_none_selected(tmp_path):
    assert load_analysis(write_docs_analysis(tmp_path)).report.combined_documents == ()


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        (
            'combined_documents = ["brief.qmd"]',
            "combined_documents = []",
            "combined_documents must be a non-empty list",
        ),
        (
            'combined_documents = ["brief.qmd"]',
            'combined_documents = "brief.qmd"',
            "combined_documents must be a non-empty list",
        ),
        (
            'combined_documents = ["brief.qmd"]',
            'combined_documents = ["other.qmd"]',
            "combined_documents other.qmd are not in documents",
        ),
        (
            'combined_documents = ["brief.qmd"]',
            'combined_documents = ["brief.qmd", "brief.qmd"]',
            "combined_documents has duplicates",
        ),
        (
            'part_titles = ["Brief"]',
            'part_titles = ["Brief", "Appendix"]',
            "one title per document joined",
        ),
    ],
)
def test_invalid_combined_documents(tmp_path, old, new, message):
    root = write_docs_analysis(tmp_path, SELECT_MANIFEST.replace(old, new))
    with pytest.raises(ManifestError, match=re.escape(message)):
        load_analysis(root)


def test_combined_documents_needs_combined(tmp_path):
    manifest = DOCS_MANIFEST.replace('combined = "together.pdf"\n', "").replace(
        'part_titles = ["Brief", "Appendix"]', 'combined_documents = ["brief.qmd"]'
    )
    with pytest.raises(ManifestError, match=re.escape("combined_documents needs combined")):
        load_analysis(write_docs_analysis(tmp_path, manifest))


R_PROFILE = REPORT_MANIFEST + '\n[r]\nprofile = "report"\n'


def test_r_profile_parsed(tmp_path):
    assert load_analysis(write_report_analysis(tmp_path, R_PROFILE)).r_profile == "report"
    assert (
        load_analysis(
            write_analysis(
                tmp_path / "other", VALID.replace('stage = "enclave"', 'stage = "local"')
            )
        ).r_profile
        is None
    )


R_PROFILE_NAME = '[r] profile must be a lowercase renv profile name, e.g. "report"'
R_PROFILE_ENCLAVE = "[r] profile is local-only: enclave bundles restore only the default R library"


R_PROFILES = {
    "uppercase and space": (REPORT_MANIFEST + '\n[r]\nprofile = "Bad Name"\n', R_PROFILE_NAME),
    "trailing newline": (REPORT_MANIFEST + '\n[r]\nprofile = "report\\n"\n', R_PROFILE_NAME),
    "leading digit": (REPORT_MANIFEST + '\n[r]\nprofile = "1report"\n', R_PROFILE_NAME),
    "not a string": (REPORT_MANIFEST + "\n[r]\nprofile = 3\n", R_PROFILE_NAME),
    "empty table": (REPORT_MANIFEST + "\n[r]\n", R_PROFILE_NAME),
    "not a table": ('r = "report"\n' + REPORT_MANIFEST, R_PROFILE_NAME),
    "enclave step": (VALID + '\n[r]\nprofile = "report"\n', R_PROFILE_ENCLAVE),
}


@pytest.mark.parametrize(("text", "message"), R_PROFILES.values(), ids=R_PROFILES.keys())
def test_invalid_r_profile(tmp_path, text, message):
    root = write_analysis(tmp_path, text, files=("frame.py", "models.R", "report.qmd", "notes.md"))
    (root / "assumptions.toml").write_text(REPORT_ASSUMPTIONS)
    with pytest.raises(ManifestError) as raised:
        load_analysis(root)
    assert str(raised.value) == f"{root / 'analysis.toml'}: {message}"


@pytest.mark.parametrize("profile", ["report", "report-2", "a_b", "x"])
def test_valid_r_profile_names(tmp_path, profile):
    text = REPORT_MANIFEST + f'\n[r]\nprofile = "{profile}"\n'
    assert load_analysis(write_report_analysis(tmp_path, text)).r_profile == profile
