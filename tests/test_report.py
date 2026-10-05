"""`oai report`: render an analysis's Quarto report (fake quarto; one real render if available)."""

import json
import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from oai import config as oai_config
from oai.cli import app
from oai.config import load_settings
from oai.manifest import load_analysis
from oai.report import ReportError, find_quarto, missing_runs, render_report
from oai.runner import run_analysis

REPO = Path(__file__).resolve().parents[1]

MANIFEST = textwrap.dedent(
    """
    name = "toy"

    [[steps]]
    id = "a"
    lang = "python"
    entry = "a.py"

    [report]
    entry = "report.qmd"
    runs = ["default", "alt"]
    assets = ["notes.md"]
    """
)
ASSUMPTIONS = textwrap.dedent(
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
STEP = 'import os, pathlib\npathlib.Path(os.environ["OAI_RESULTS_DIR"], "out.csv").write_text("metric,value\\nm,1\\n")\n'
# Stands in for `quarto render <document> --to typst`, run in the report directory.
FAKE_QUARTO = textwrap.dedent(
    """\
    #!/bin/sh
    stem="${2%.qmd}"
    mkdir -p figures .quarto
    echo fig > figures/f.png
    echo scratch > .quarto/x
    echo typ > "$stem.typ"
    if [ "$FAKE_QUARTO_FAIL" = "1" ] || [ "$FAKE_QUARTO_FAIL" = "$2" ]; then echo "boom: render failed" >&2; exit 1; fi
    if [ -n "$FAKE_QUARTO_PDF" ]; then cp "$FAKE_QUARTO_PDF" "$stem.pdf"; exit 0; fi
    {
      echo "args=$*"
      echo "root=$OAI_RESULTS_ROOT"
      echo "report=$OAI_REPORT_DIR"
      echo "runs=$OAI_REPORT_RUNS"
      echo "profile=$RENV_PROFILE"
      ls
    } > "$stem.pdf"
    """
)


def make_toy(tmp_path, manifest=MANIFEST, qmd="# toy\n"):
    root = tmp_path / "analyses" / "toy"
    root.mkdir(parents=True)
    (root / "analysis.toml").write_text(manifest)
    (root / "assumptions.toml").write_text(ASSUMPTIONS)
    (root / "a.py").write_text(STEP)
    (root / "report.qmd").write_text(qmd)
    (root / "notes.md").write_text("notes\n")
    return load_analysis(root)


def make_settings(tmp_path, repo_root=None):
    env = {"OAI_WORK_DIR": str(tmp_path / "work"), "OAI_RESULTS_DIR": str(tmp_path / "results")}
    return load_settings(env=env, repo_root=repo_root)


def fake_quarto(tmp_path) -> Path:
    path = tmp_path / "bin" / "quarto"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(FAKE_QUARTO)
    path.chmod(0o755)
    return path


@pytest.fixture
def toy(tmp_path):
    return make_toy(tmp_path)


@pytest.fixture
def quarto_env(tmp_path):
    return {**os.environ, "OAI_QUARTO": str(fake_quarto(tmp_path))}


def quiet(_):
    pass


def test_render_needs_a_report_section(tmp_path, quarto_env):
    analysis = make_toy(tmp_path, MANIFEST.split("[report]")[0])
    with pytest.raises(ReportError, match="no \\[report\\] section"):
        render_report(analysis, make_settings(tmp_path), base_env=quarto_env, echo=quiet)


def test_missing_runs_counts_only_finished_runs(toy, tmp_path):
    settings = make_settings(tmp_path)
    assert missing_runs(toy, settings) == ["default", "alt"]
    run_analysis(toy, settings, echo=quiet)
    assert missing_runs(toy, settings) == ["alt"]
    info = tmp_path / "results" / "toy" / "default" / "run_info.json"
    info.write_text(json.dumps({**json.loads(info.read_text()), "finished_utc": None}))
    assert missing_runs(toy, settings) == ["default", "alt"]


def test_report_without_run_flag_names_missing_runs(toy, tmp_path, quarto_env):
    with pytest.raises(ReportError, match="default, alt.*oai report toy --run"):
        render_report(toy, make_settings(tmp_path), base_env=quarto_env, echo=quiet)


def test_run_flag_runs_only_the_missing_runs(toy, tmp_path, quarto_env):
    settings = make_settings(tmp_path)
    run_analysis(toy, settings, echo=quiet)
    default_info = (tmp_path / "results" / "toy" / "default" / "run_info.json").read_text()
    [pdf] = render_report(toy, settings, run_missing=True, base_env=quarto_env, echo=quiet)
    assert pdf.is_file()
    assert missing_runs(toy, settings) == []
    assert (tmp_path / "results" / "toy" / "default" / "run_info.json").read_text() == default_info


def test_render_copies_inputs_sets_env_and_keeps_only_pdf_and_figures(toy, tmp_path, quarto_env):
    [pdf] = render_report(
        toy, make_settings(tmp_path), run_missing=True, base_env=quarto_env, echo=quiet
    )
    out = (tmp_path / "results" / "toy" / "report").resolve()  # settings resolve paths
    assert pdf == out / "report.pdf"
    lines = pdf.read_text().splitlines()
    assert "args=render report.qmd --to typst" in lines
    assert f"root={(tmp_path / 'results' / 'toy').resolve()}" in lines
    assert f"report={out.resolve()}" in lines
    assert "runs=default,alt" in lines
    assert "profile=report" in lines
    assert {"report.qmd", "notes.md"} <= set(lines)  # copied before rendering
    assert sorted(p.name for p in out.iterdir()) == ["figures", "report.pdf"]
    assert (out / "figures" / "f.png").is_file()


def test_render_replaces_a_previous_report(toy, tmp_path, quarto_env):
    settings = make_settings(tmp_path)
    stale = tmp_path / "results" / "toy" / "report" / "figures" / "stale.png"
    stale.parent.mkdir(parents=True)
    stale.write_text("old")
    render_report(toy, settings, run_missing=True, base_env=quarto_env, echo=quiet)
    assert not stale.exists()


def test_failed_render_keeps_partial_output_and_shows_stderr(toy, tmp_path, quarto_env):
    with pytest.raises(ReportError, match="(?s)exit 1.*partial output kept.*boom: render failed"):
        render_report(
            toy,
            make_settings(tmp_path),
            run_missing=True,
            base_env={**quarto_env, "FAKE_QUARTO_FAIL": "1"},
            echo=quiet,
        )
    out = tmp_path / "results" / "toy" / "report"
    assert (out / "report.typ").is_file() and (out / "report.qmd").is_file()


def test_find_quarto_order(tmp_path):
    def exe(name):
        path = tmp_path / name / "quarto"
        path.parent.mkdir()
        path.write_text("#!/bin/sh\n")
        path.chmod(0o755)
        return path

    explicit, configured, on_path, bundle = exe("e"), exe("c"), exe("p"), exe("b")
    env = {"OAI_QUARTO": str(explicit), "PATH": str(on_path.parent)}
    assert find_quarto(env, str(configured), [bundle]) == explicit
    del env["OAI_QUARTO"]
    assert find_quarto(env, str(configured), [bundle]) == configured
    assert find_quarto(env, None, [bundle]) == on_path
    assert find_quarto({"PATH": str(tmp_path)}, None, [bundle]) == bundle
    with pytest.raises(ReportError, match="install it.*OAI_QUARTO"):
        find_quarto({"PATH": str(tmp_path)}, None, [tmp_path / "nope"])


def test_find_quarto_rejects_a_bad_explicit_path(tmp_path):
    with pytest.raises(ReportError, match="OAI_QUARTO=.*not an executable"):
        find_quarto({"OAI_QUARTO": str(tmp_path / "missing")}, None, [])
    with pytest.raises(ReportError, match="\\[tools\\] quarto=.*not an executable"):
        find_quarto({"PATH": ""}, str(tmp_path / "missing"), [])


def test_cli_report(tmp_path, monkeypatch):
    make_toy(tmp_path)
    monkeypatch.setenv("OAI_ANALYSES_DIR", str(tmp_path / "analyses"))
    monkeypatch.setenv("OAI_QUARTO", str(fake_quarto(tmp_path)))
    oai_config.get_settings.cache_clear()
    missing = CliRunner().invoke(app, ["report", "toy"])
    assert missing.exit_code == 1 and "--run" in missing.output
    result = CliRunner().invoke(app, ["report", "toy", "--run"])
    assert result.exit_code == 0, result.output
    assert "Report:" in result.output and "report.pdf" in result.output
    assert "oai check-egress" in result.output


def _report_tools_ready() -> bool:
    try:
        find_quarto(os.environ)
    except ReportError:
        return False
    if shutil.which("Rscript") is None:
        return False
    probe = subprocess.run(
        ["Rscript", "-e", "library(knitr); library(ggplot2); library(tinytable)"],
        cwd=REPO / "r",
        capture_output=True,
        env={**os.environ, "RENV_PROFILE": "report"},
    )
    return probe.returncode == 0


SMOKE_QMD = textwrap.dedent(
    """\
    ---
    format:
      typst:
        papersize: us-letter
    execute:
      echo: false
    knitr:
      opts_chunk:
        dev: cairo_pdf
    ---

    ```{r}
    p <- ggplot2::ggplot(data.frame(x = 1:3, y = 1:3), ggplot2::aes(x, y)) +
      ggplot2::geom_point() + oaireport::theme_oai()
    oaireport::save_figure(p, "smoke", "1col")
    p
    ```

    ```{r}
    oaireport::compare_table(data.frame(metric = "m", verdict = "replicated"))
    ```
    """
)


@pytest.mark.skipif(
    not _report_tools_ready(), reason="Quarto or the r/ report profile is unavailable"
)
def test_real_quarto_renders_with_oaireport(tmp_path):
    analysis = make_toy(
        tmp_path, MANIFEST.replace('runs = ["default", "alt"]', 'runs = ["default"]'), SMOKE_QMD
    )
    settings = make_settings(tmp_path, repo_root=REPO)
    [pdf] = render_report(
        analysis, settings, run_missing=True, base_env=dict(os.environ), echo=quiet
    )
    assert pdf.stat().st_size > 5_000
    assert sorted(p.name for p in pdf.parent.iterdir()) == ["figures", "report.pdf"]
    assert {p.name for p in (pdf.parent / "figures").iterdir()} == {"smoke.pdf", "smoke.png"}


def test_partial_run_is_not_finished_for_the_report(tmp_path):
    two_steps = MANIFEST.replace(
        "[report]", '[[steps]]\nid = "c"\nlang = "python"\nentry = "a.py"\n\n[report]'
    )
    analysis = make_toy(tmp_path, two_steps)
    settings = make_settings(tmp_path)
    run_analysis(analysis, settings, step_id="a", echo=quiet)
    assert missing_runs(analysis, settings) == ["default", "alt"]
    run_analysis(analysis, settings, echo=quiet)
    assert missing_runs(analysis, settings) == ["alt"]


def test_render_refuses_to_delete_a_run_folder(toy, tmp_path, quarto_env):
    settings = make_settings(tmp_path)
    for label in ("default", "alt"):
        run_analysis(toy, settings, variant=None if label == "default" else label, echo=quiet)
    clash = tmp_path / "results" / "toy" / "report"
    clash.mkdir(parents=True)
    (clash / "run_info.json").write_text("{}")
    with pytest.raises(ReportError, match="holds a run"):
        render_report(toy, settings, base_env=quarto_env, echo=quiet)
    assert (clash / "run_info.json").is_file()


DOCS_MANIFEST = MANIFEST.replace(
    'entry = "report.qmd"',
    'documents = ["brief.qmd", "report.qmd"]\n'
    'combined = "together.pdf"\n'
    'part_titles = ["Brief", "Appendix"]\n'
    'local_assets = ["brief.local.yml", "absent.local.yml"]',
)


def make_docs_toy(tmp_path, manifest=DOCS_MANIFEST):
    # make_toy loads the analysis, so it starts from the single-entry manifest; the brief, a
    # local asset and the multi-document manifest are added before loading it again
    root = make_toy(tmp_path).root
    (root / "brief.qmd").write_text("# brief\n")
    (root / "brief.local.yml").write_text("authors: []\n")
    (root / "analysis.toml").write_text(manifest)
    return load_analysis(root)


def blank_pdf(path: Path, pages: int) -> Path:
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    with path.open("wb") as handle:
        writer.write(handle)
    return path


def top_bookmarks(path: Path) -> list[str]:
    from pypdf import PdfReader

    return [item.title for item in PdfReader(path).outline if not isinstance(item, list)]


def test_documents_render_in_order_and_combine(tmp_path, quarto_env):
    from pypdf import PdfReader

    env = {**quarto_env, "FAKE_QUARTO_PDF": str(blank_pdf(tmp_path / "blank.pdf", 2))}
    pdfs = render_report(
        make_docs_toy(tmp_path), make_settings(tmp_path), run_missing=True, base_env=env, echo=quiet
    )
    out = (tmp_path / "results" / "toy" / "report").resolve()
    assert pdfs == [out / "brief.pdf", out / "report.pdf", out / "together.pdf"]
    assert len(PdfReader(pdfs[-1]).pages) == 4
    assert top_bookmarks(pdfs[-1]) == ["Brief", "Appendix"]


def test_local_assets_are_copied_when_present_and_cleaned_up(tmp_path, quarto_env, monkeypatch):
    import oai.report as report_module

    joined = []

    def fake_join(parts, out):
        joined.append(parts)
        out.write_text("joined")
        return out

    monkeypatch.setattr(report_module, "combine_pdfs", fake_join)
    pdfs = render_report(
        make_docs_toy(tmp_path),
        make_settings(tmp_path),
        run_missing=True,
        base_env=quarto_env,
        echo=quiet,
    )
    # the text fake lists the folder into each PDF: the present local asset was there while
    # rendering, the absent one was skipped without error
    listing = set(pdfs[0].read_text().splitlines())
    assert "brief.local.yml" in listing and "absent.local.yml" not in listing
    assert [title for title, _ in joined[0]] == ["Brief", "Appendix"]
    out = pdfs[0].parent
    assert sorted(p.name for p in out.iterdir()) == [
        "brief.pdf",
        "figures",
        "report.pdf",
        "together.pdf",
    ]


def test_a_failing_document_is_named_and_nothing_is_combined(tmp_path, quarto_env):
    env = {**quarto_env, "FAKE_QUARTO_FAIL": "report.qmd"}
    with pytest.raises(ReportError, match=r"(?s)report\.qmd failed.*partial output kept"):
        render_report(
            make_docs_toy(tmp_path),
            make_settings(tmp_path),
            run_missing=True,
            base_env=env,
            echo=quiet,
        )
    out = tmp_path / "results" / "toy" / "report"
    assert (out / "brief.pdf").exists() and not (out / "together.pdf").exists()
    # the local author file never stays behind, even when a render fails
    assert not (out / "brief.local.yml").exists()


def test_a_failing_first_document_is_named_and_leaves_no_pdfs(tmp_path, quarto_env):
    env = {**quarto_env, "FAKE_QUARTO_FAIL": "brief.qmd"}
    with pytest.raises(ReportError, match=r"brief\.qmd failed"):
        render_report(
            make_docs_toy(tmp_path),
            make_settings(tmp_path),
            run_missing=True,
            base_env=env,
            echo=quiet,
        )
    out = tmp_path / "results" / "toy" / "report"
    assert list(out.glob("*.pdf")) == []
    assert not (out / "brief.local.yml").exists()


def test_a_failing_join_keeps_the_document_pdfs_and_cleans_local_assets(
    tmp_path, quarto_env, monkeypatch
):
    import oai.report as report_module
    from oai.pdfjoin import PdfJoinError

    def failing_join(parts, out):
        raise PdfJoinError("boom")

    monkeypatch.setattr(report_module, "combine_pdfs", failing_join)
    with pytest.raises(PdfJoinError, match="boom"):
        render_report(
            make_docs_toy(tmp_path),
            make_settings(tmp_path),
            run_missing=True,
            base_env=quarto_env,
            echo=quiet,
        )
    out = tmp_path / "results" / "toy" / "report"
    assert sorted(p.name for p in out.glob("*.pdf")) == ["brief.pdf", "report.pdf"]
    assert not (out / "together.pdf").exists()
    assert not (out / "brief.local.yml").exists()


def test_the_quarto_path_is_logged_once_and_each_document_by_name(tmp_path, quarto_env):
    lines = []
    render_report(
        make_docs_toy(tmp_path),
        make_settings(tmp_path),
        run_missing=True,
        base_env={**quarto_env, "FAKE_QUARTO_PDF": str(blank_pdf(tmp_path / "blank.pdf", 1))},
        echo=lines.append,
    )
    quarto = quarto_env["OAI_QUARTO"]
    assert [line for line in lines if quarto in line] == [f"==> toy: rendering with {quarto}"]
    assert "==> toy: rendering brief.qmd" in lines
    assert "==> toy: rendering report.qmd" in lines


def test_part_titles_default_to_document_names(tmp_path, quarto_env):
    manifest = DOCS_MANIFEST.replace('part_titles = ["Brief", "Appendix"]\n', "")
    env = {**quarto_env, "FAKE_QUARTO_PDF": str(blank_pdf(tmp_path / "blank.pdf", 1))}
    pdfs = render_report(
        make_docs_toy(tmp_path, manifest),
        make_settings(tmp_path),
        run_missing=True,
        base_env=env,
        echo=quiet,
    )
    assert top_bookmarks(pdfs[-1]) == ["brief", "report"]


def test_combined_documents_joins_only_the_selected_in_their_order(tmp_path, quarto_env):
    from pypdf import PdfReader

    manifest = DOCS_MANIFEST.replace(
        'part_titles = ["Brief", "Appendix"]',
        'part_titles = ["Second", "First"]\ncombined_documents = ["report.qmd", "brief.qmd"]',
    )
    env = {**quarto_env, "FAKE_QUARTO_PDF": str(blank_pdf(tmp_path / "blank.pdf", 2))}
    pdfs = render_report(
        make_docs_toy(tmp_path, manifest),
        make_settings(tmp_path),
        run_missing=True,
        base_env=env,
        echo=quiet,
    )
    assert [p.name for p in pdfs] == ["brief.pdf", "report.pdf", "together.pdf"]
    assert top_bookmarks(pdfs[-1]) == ["Second", "First"]
    assert len(PdfReader(pdfs[-1]).pages) == 4


def test_combined_documents_can_leave_a_document_out(tmp_path, quarto_env):
    from pypdf import PdfReader

    manifest = DOCS_MANIFEST.replace(
        'part_titles = ["Brief", "Appendix"]',
        'part_titles = ["Brief"]\ncombined_documents = ["brief.qmd"]',
    )
    env = {**quarto_env, "FAKE_QUARTO_PDF": str(blank_pdf(tmp_path / "blank.pdf", 2))}
    pdfs = render_report(
        make_docs_toy(tmp_path, manifest),
        make_settings(tmp_path),
        run_missing=True,
        base_env=env,
        echo=quiet,
    )
    assert top_bookmarks(pdfs[-1]) == ["Brief"]
    assert len(PdfReader(pdfs[-1]).pages) == 2


def test_cli_report_prints_every_pdf(tmp_path, monkeypatch):
    make_docs_toy(tmp_path)
    monkeypatch.setenv("OAI_ANALYSES_DIR", str(tmp_path / "analyses"))
    monkeypatch.setenv("OAI_QUARTO", str(fake_quarto(tmp_path)))
    monkeypatch.setenv("FAKE_QUARTO_PDF", str(blank_pdf(tmp_path / "blank.pdf", 1)))
    oai_config.get_settings.cache_clear()
    result = CliRunner().invoke(app, ["report", "toy", "--run"])
    assert result.exit_code == 0, result.output
    reports = [line for line in result.output.splitlines() if line.startswith("Report: ")]
    assert [Path(line.removeprefix("Report: ")).name for line in reports] == [
        "brief.pdf",
        "report.pdf",
        "together.pdf",
    ]
    assert "Before sharing: oai check-egress" in result.output
