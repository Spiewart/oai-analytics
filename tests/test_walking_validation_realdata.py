"""End-to-end walking_validation on the real release (short bias-analysis settings).

One run is shared by the tests in this module: it is made in throwaway work and results folders
(never the developer's own) and takes a few minutes.
"""

import dataclasses
import functools
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import polars as pl
import pytest
from pypdf import PdfReader

from oai.assumptions import load_assumptions
from oai.config import ConfigError, Settings, load_settings
from oai.export.egress import check_egress
from oai.manifest import Analysis, find_analysis
from oai.pdfcheck import find_terms, max_right_edge
from oai.report import ReportError, find_quarto, render_report
from oai.runner import (
    process_env,
    r_profile_env,
    resolve_assumptions,
    run_analysis,
    run_results_dir,
    select_steps,
    step_command,
)

REPO = Path(__file__).resolve().parents[1]
FAST = {
    "bias.iterations": 40,
    "bias.tipping_iterations": 4,
    "bias.tipping_step": 0.2,
    "validity.bootstrap_reps": 50,
    "validity.jt_permutations": 99,
}


@functools.cache
def _ready() -> bool:
    if shutil.which("Rscript") is None:
        return False
    probe = subprocess.run(
        ["Rscript", "-e", "library(quantreg); library(geepack); library(ggplot2)"],
        cwd=REPO / "r",
        capture_output=True,
        env={**os.environ, "RENV_PROFILE": "report"},
    )
    return probe.returncode == 0


@dataclasses.dataclass(frozen=True)
class FastRun:
    settings: Settings  # work and results folders of this module's run
    analysis: Analysis
    out: Path  # the run's results folder


@pytest.fixture(scope="module")
def fast_run(tmp_path_factory) -> FastRun:
    """walking_validation with short bias-analysis settings, after its lo2022_walking run.

    Skips only when no release is configured (as conftest does). With real data configured, a
    run that cannot be made fails the tests rather than skipping them. This fixture is set up
    before the autouse fixture that points OAI_* at throwaway folders, so it builds its own
    folders and environment.
    """
    try:
        real = load_settings()
        data_dir = real.data_dir
    except ConfigError:
        pytest.skip("OAI_DATA_DIR is not configured (env or .env)")
    if not _ready():
        pytest.fail("the R report profile with quantreg, geepack and ggplot2 is unavailable")
    root = tmp_path_factory.mktemp("walking_validation")
    paths = {
        **real.paths,
        "OAI_DATA_DIR": data_dir,
        "OAI_WORK_DIR": root / "work",
        "OAI_RESULTS_DIR": root / "results",
    }
    settings = dataclasses.replace(real, paths=paths)
    env = {**os.environ, **{key: str(path) for key, path in paths.items()}, "OAI_FRAME_DIR": ""}
    quiet = lambda _: None  # noqa: E731
    run_analysis(
        find_analysis("lo2022_walking", settings.analyses_dir),
        settings,
        variant="walker_requires_amount",
        base_env=env,
        echo=quiet,
    )
    analysis = find_analysis("walking_validation", settings.analyses_dir)
    run_analysis(analysis, settings, overrides=FAST, base_env=env, echo=quiet)
    # this run's own folder: the label the runner derives from these overrides
    out = run_results_dir(analysis, settings, resolve_assumptions(analysis, None, FAST).label)
    return FastRun(settings, analysis, out)


@pytest.mark.realdata
def test_walking_validation_end_to_end(fast_run):
    out, settings = fast_run.out, fast_run.settings
    comparison = pl.read_csv(out / "comparison.csv")
    device = comparison.filter(pl.col("metric").str.starts_with("device."))
    assert device.height == 10, device  # 2 waves x (valid persons, matched, wear, MV, bout)
    assert (device["verdict"] == "replicated").all(), device
    # R writes NA unquoted, so polars needs null_values or it reads the columns as strings
    pba = pl.read_csv(out / "bias_pba.csv", null_values=["NA"])
    assert pba.height == 4 * 2 * 2
    assert (pba["n"] == 40).all()
    assert pba["discarded"].is_between(0, 1).all()
    assert (pba["flagged"] == (pba["discarded"] > 0.10)).all()
    assert pba.filter(pl.col("discarded") < 1)["or"].is_not_null().all(), pba
    # perfect classification (Se = Sp = 1) reproduces the observed adjusted odds ratio
    tipping = pl.read_csv(out / "bias_tipping.csv", null_values=["NA"])
    identity = tipping.filter((pl.col("se") == 1) & (pl.col("sp") == 1)).join(
        pba.filter(pl.col("model") == "or_adj").select("outcome", "observed_or").unique(),
        on="outcome",
        validate="1:1",
    )
    assert identity.height == 4, identity
    # a discarded cell has a null odds ratio, which the comparison below would let through
    assert identity["or"].is_not_null().all(), f"cells at Se = Sp = 1 were discarded:\n{identity}"
    assert ((identity["or"] - identity["observed_or"]).abs() < 1e-8).all(), identity
    # validated participants outside an outcome's complete-case model frame feed its priors only
    metrics = pl.read_csv(out / "metrics_bias.csv", null_values=["NA"])
    outside = metrics.filter(pl.col("metric").str.ends_with("prior_persons_outside_model"))
    assert sorted(outside["metric"]) == sorted(
        f"bias.{o}.prior_persons_outside_model"
        for o in ("new_pain", "kl_worse", "jsn_worse", "improved_pain")
    )
    assert (outside["value"] == 0).all(), outside
    egress = settings.project["egress"]
    report = check_egress(
        out,
        min_cell=egress["min_cell"],
        small_cell=egress["small_cell"],
        ignore_id_pattern_columns=egress["ignore_id_pattern_columns"],
    )
    assert report.ok, report.problems


@pytest.mark.realdata
def test_e2e_dose_table_has_the_level_counts(fast_run):
    dose = pl.read_csv(fast_run.out / "validity_dose.csv")
    assert {"n_none", "n_lower", "n_upper", "n_walkers_no_level"} <= set(dose.columns)


@pytest.fixture
def step_copy(fast_run, tmp_path):
    """The fast run's frames and results copied into tmp_path, and a way to run one R step on them.

    Tests change the copies (never the run itself) and call `run(step_id, **env)`, which returns
    the finished process with its stderr.
    """
    analysis, settings = fast_run.analysis, fast_run.settings
    source = settings.work_dir / analysis.name / fast_run.out.name
    frames, results = tmp_path / "frames", tmp_path / "results"
    frames.mkdir()
    for name in ("frame.parquet", "lo_knees.parquet", "lo_model.json"):
        shutil.copy(source / name, frames / name)
    shutil.copytree(fast_run.out, results)

    def run(step_id: str, **env: str) -> subprocess.CompletedProcess:
        step = select_steps(analysis, step_id=step_id)[0]
        base = {
            **os.environ,
            "OAI_ANALYSIS": analysis.name,
            "OAI_FRAME_DIR": str(frames),
            "OAI_RESULTS_DIR": str(results),
            "OAI_RESULTS_BASE": str(settings.results_dir),
            "OAI_ASSUMPTIONS": str(results / "assumptions.resolved.json"),
            **r_profile_env(settings),
            **env,
        }
        return subprocess.run(
            step_command(step, analysis),
            cwd=analysis.root,
            env=process_env(step, analysis, base),
            capture_output=True,
            text=True,
        )

    return SimpleNamespace(frames=frames, results=results, run=run)


def _edit_frame(step_copy, edit):
    path = step_copy.frames / "frame.parquet"
    pl.read_parquet(path).pipe(edit).write_parquet(path)


def _edit_knees(step_copy, edit):
    path = step_copy.frames / "lo_knees.parquet"
    pl.read_parquet(path).pipe(edit).write_parquet(path)


def _set_assumption(step_copy, key, value):
    path = step_copy.results / "assumptions.resolved.json"
    resolved = json.loads(path.read_text())
    resolved["assumptions"][key]["value"] = value
    path.write_text(json.dumps(resolved))


def _edit_published(step_copy, edit):
    path = step_copy.results / "lo2022_t2.csv"
    edit(pl.read_csv(path)).write_csv(path)


@pytest.mark.realdata
def test_validity_dose_counts_each_level_and_the_walkers_without_one(step_copy):
    # Walkers who gave only some amount items already have no level. Three more lose theirs, two
    # of them in the Lo subset, and the count must rise by exactly those.
    def no_level(df, sample):
        d = df if sample == "validation" else df.filter("in_lo")
        return d.filter(pl.col("walker") & pl.col("amount_level").is_null()).height

    before = pl.read_parquet(step_copy.frames / "frame.parquet")
    expected = {
        "validation": no_level(before, "validation") + 3,
        "lo_subset": no_level(before, "lo_subset") + 2,
    }
    levelled = pl.col("walker") & pl.col("amount_level").is_not_null()
    losers = [
        *before.filter(levelled & pl.col("in_lo"))["ID"].head(2),
        *before.filter(levelled & ~pl.col("in_lo"))["ID"].head(1),
    ]
    _edit_frame(
        step_copy,
        lambda df: df.with_columns(
            pl.when(pl.col("ID").is_in(losers))
            .then(None)
            .otherwise(pl.col("amount_level"))
            .alias("amount_level")
        ),
    )
    done = step_copy.run("validity")
    assert done.returncode == 0, done.stderr
    frame = pl.read_parquet(step_copy.frames / "frame.parquet")
    dose = pl.read_csv(step_copy.results / "validity_dose.csv")
    assert dose.height == 6
    for row in dose.iter_rows(named=True):
        d = frame if row["sample"] == "validation" else frame.filter("in_lo")
        measured = d.filter(pl.col(row["measure"]).is_not_null())
        for level in ("none", "lower", "upper"):
            n = measured.filter(pl.col("amount_level") == level).height
            assert row[f"n_{level}"] == n, (row["sample"], row["measure"], level)
        assert row["n_walkers_no_level"] == expected[row["sample"]], (row["sample"], row["measure"])


@pytest.mark.realdata
def test_validity_names_the_columns_a_frame_lacks(step_copy):
    # columns the step reads but did not list as required used to fail deep inside the step
    _edit_frame(step_copy, lambda df: df.drop("pase_walking_10", "light_min_08", "new_pain_any"))
    done = step_copy.run("validity")
    assert done.returncode != 0
    assert "Frame is missing required columns" in done.stderr, done.stderr
    for column in ("pase_walking_10", "light_min_08", "new_pain_any"):
        assert column in done.stderr, done.stderr


@pytest.mark.realdata
@pytest.mark.parametrize("how", ["blank", "absent"])
def test_bias_stops_on_a_missing_published_odds_ratio(step_copy, how):
    target = "t2.new_pain.or_adj"

    def spoil(df):
        if how == "absent":
            return df.filter(pl.col("metric") != target)
        return df.with_columns(
            pl.when(pl.col("metric") == target)
            .then(None)
            .otherwise(pl.col("published"))
            .alias("published")
        )

    _edit_published(step_copy, spoil)
    done = step_copy.run("bias")
    assert done.returncode != 0
    assert "published odds ratio" in done.stderr and target in done.stderr, done.stderr


@pytest.mark.realdata
@pytest.mark.parametrize("how", ["blank", "absent"])
def test_bias_stops_on_a_missing_published_count(step_copy, how):
    target = "t2.new_pain.walkers.events"

    def spoil(df):
        if how == "absent":
            return df.filter(pl.col("metric") != target)
        return df.with_columns(
            pl.when(pl.col("metric") == target)
            .then(None)
            .otherwise(pl.col("published"))
            .alias("published")
        )

    _edit_published(step_copy, spoil)
    done = step_copy.run("bias")
    assert done.returncode != 0
    assert "published count" in done.stderr and target in done.stderr, done.stderr


@pytest.mark.realdata
def test_bias_names_the_knee_columns_a_frame_lacks(step_copy):
    # the knee frame's outcome and covariate columns are read by knee_data(), so they are required
    _edit_knees(step_copy, lambda df: df.drop("kl0", "jsn_worse"))
    done = step_copy.run("bias")
    assert done.returncode != 0
    assert "Frame is missing required columns" in done.stderr, done.stderr
    assert "kl0" in done.stderr and "jsn_worse" in done.stderr, done.stderr


@pytest.mark.realdata
def test_bias_checks_every_published_value_before_any_fitting(step_copy):
    # The last outcome's published count is missing and the iterations are invalid, which the
    # first PBA call would reject. The published-value guard must be what stops the step.
    _set_assumption(step_copy, "bias.iterations", 0)
    target = "t2.improved_pain.nonwalkers.n"
    _edit_published(step_copy, lambda df: df.filter(pl.col("metric") != target))
    done = step_copy.run("bias")
    assert done.returncode != 0
    assert "published count" in done.stderr and target in done.stderr, done.stderr
    assert "iterations must be" not in done.stderr, done.stderr


@pytest.mark.realdata
@pytest.mark.parametrize("how", ["absent", "twice"])
def test_bias_checks_the_replicated_odds_ratios_before_any_fitting(step_copy, how):
    # The last outcome's replicated odds ratio is missing (or listed twice) and the iterations are
    # invalid, which the first PBA call would reject: the lookup guard must stop the step first.
    _set_assumption(step_copy, "bias.iterations", 0)
    path = step_copy.results / "lo2022_table2.csv"
    table = pl.read_csv(path)
    target = (pl.col("outcome") == "improved_pain") & (pl.col("model") == "or_adj")
    table = table.filter(~target) if how == "absent" else pl.concat([table, table.filter(target)])
    table.write_csv(path)
    done = step_copy.run("bias")
    assert done.returncode != 0
    assert "lo2022_table2.csv" in done.stderr and "improved_pain" in done.stderr, done.stderr
    assert "iterations must be" not in done.stderr, done.stderr


@pytest.mark.realdata
def test_bias_stops_when_a_prior_stratum_disagrees_with_the_model_frame(step_copy):
    # a validated person whose any-knee event differs from the complete-case model frame's
    def flip(df):
        first = df.filter(pl.col("in_lo") & pl.col("new_pain_any").is_not_null())["ID"][0]
        return df.with_columns(
            pl.when(pl.col("ID") == first)
            .then(~pl.col("new_pain_any"))
            .otherwise(pl.col("new_pain_any"))
            .alias("new_pain_any")
        )

    _edit_frame(step_copy, flip)
    done = step_copy.run("bias")
    assert done.returncode != 0
    assert "new_pain" in done.stderr and "case/noncase" in done.stderr, done.stderr


@pytest.mark.realdata
def test_bias_counts_prior_persons_outside_the_model_frame(step_copy):
    # bias.prior_population admits any validated Lo participant with the outcome observed, also one
    # the complete-case model frame later drops (a missing covariate). Such a person feeds the
    # priors only: the step counts them and goes on.
    def add(df):
        outside = df.filter(~pl.col("in_lo"))["ID"][0]
        return df.with_columns(
            (pl.col("in_lo") | (pl.col("ID") == outside)).alias("in_lo"),
            pl.when(pl.col("ID") == outside)
            .then(False)
            .otherwise(pl.col("new_pain_any"))
            .alias("new_pain_any"),
        )

    _edit_frame(step_copy, add)
    done = step_copy.run("bias")
    assert done.returncode == 0, done.stderr
    metrics = pl.read_csv(step_copy.results / "metrics_bias.csv", null_values=["NA"])
    outside = {
        m.split(".")[1]: v
        for m, v in metrics.iter_rows()
        if m.endswith("prior_persons_outside_model")
    }
    assert outside == {"new_pain": 1, "kl_worse": 0, "jsn_worse": 0, "improved_pain": 0}


@pytest.fixture
def bare_bias_step(tmp_path):
    """A way to run the bias step before it reads anything, for what it checks first."""
    if not _ready():
        pytest.skip("the R report profile with quantreg, geepack and ggplot2 is unavailable")
    settings = load_settings(
        env={"OAI_WORK_DIR": str(tmp_path / "work"), "OAI_RESULTS_DIR": str(tmp_path / "results")},
        repo_root=REPO,
    )
    analysis = find_analysis("walking_validation", settings.analyses_dir)
    step = select_steps(analysis, step_id="bias")[0]

    def run(**env: str) -> subprocess.CompletedProcess:
        base = {**os.environ, "OAI_FRAME_DIR": str(tmp_path / "none"), **r_profile_env(settings)}
        base.pop("OAI_R_CORES", None)
        return subprocess.run(
            step_command(step, analysis),
            cwd=analysis.root,
            env=process_env(step, analysis, {**base, **env}),
            capture_output=True,
            text=True,
        )

    return run


@pytest.mark.parametrize("value", ["0", "1.5", "abc"])
def test_bias_rejects_a_bad_r_cores(bare_bias_step, value):
    done = bare_bias_step(OAI_R_CORES=value)
    assert done.returncode != 0
    assert f"OAI_R_CORES must be a positive integer, got '{value}'" in done.stderr, done.stderr


def test_bias_accepts_a_positive_integer_r_cores(bare_bias_step):
    # it then fails for want of a frame, which is the next thing the step reads
    done = bare_bias_step(OAI_R_CORES="4")
    assert done.returncode != 0
    assert "OAI_R_CORES" not in done.stderr, done.stderr


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


# right edge of the text block, in points: US-letter width less the Typst page's right margin
RIGHT_EDGE = {"brief.pdf": 550.8, "report.pdf": 547.2, "clinical.pdf": 550.8}
PLACEHOLDER = "Authors and contact to be added"
# spec 2026-10-05 §5.2: allowed only after the "Technical notes" heading
CLINICAL_BANNED = [
    "Hodges–Lehmann",
    "rank-biserial",
    "Jonckheere–Terpstra",
    "permutation",
    "bootstrap",
    "Wilson",
    "Spearman–Brown",
    "deattenuated",
    "limits of agreement",
    "non-differential",
    "differential misclassification",
    "probabilistic bias analysis",
    "bias analysis",
    "draws",
    "discarded",
    "device wave",
    "purposeful bout",
    "MV",
]


def _top_bookmarks(pdf: Path) -> list[str]:
    return [item.title for item in PdfReader(pdf).outline if not isinstance(item, list)]


@pytest.mark.realdata
@pytest.mark.skipif(
    not _report_tools_ready(), reason="Quarto or the r/ report profile is unavailable"
)
def test_walking_validation_report_renders(fast_run):
    # The report reads the "default" run. This module's run (short bias settings, same code and
    # data) stands in for it, copied into its own folder, so nothing depends on an earlier manual
    # run and rendering never replaces the developer's report.
    settings, analysis = fast_run.settings, fast_run.analysis
    shutil.copytree(fast_run.out, run_results_dir(analysis, settings, "default"))
    pdfs = render_report(analysis, settings, echo=lambda _: None)
    names = [p.name for p in pdfs]
    assert names == ["brief.pdf", "report.pdf", "clinical.pdf", "walking_validation_brief.pdf"]
    pages = {p.name: len(PdfReader(p).pages) for p in pdfs}
    assert pages["brief.pdf"] <= 6, pages
    assert pages["report.pdf"] <= 18, pages
    assert pages["clinical.pdf"] <= 12, pages
    assert pages["walking_validation_brief.pdf"] == pages["brief.pdf"] + pages["clinical.pdf"]
    for pdf in pdfs[:3]:
        text = "\n".join(page.extract_text() for page in PdfReader(pdf).pages)
        for bad in (r"\bNA\b", r"\bNaN\b", r"\bInf\b", r"`r "):
            assert not re.search(bad, text), f"{bad!r} in {pdf.name}"
    # the brief frames the Lo et al. 2022 analysis neutrally (spec 2026-10-05 §1, §3)
    assert find_terms(pdfs[0], ["bias", "correction", "corrected"], stop_heading="References") == []
    page_one = PdfReader(pdfs[0]).pages[0].extract_text()
    assert "The appendix summarises every result" in page_one  # page 1 ends on the appendix pointer
    if (analysis.root / "brief.local.yml").exists():
        assert PLACEHOLDER not in page_one
    else:
        assert PLACEHOLDER in page_one
    assert _top_bookmarks(pdfs[3]) == ["Brief", "Appendix: results"]
    clinical = pdfs[2]
    assert find_terms(clinical, CLINICAL_BANNED, stop_heading="Technical notes") == []
    clinical_text = "\n".join(page.extract_text() for page in PdfReader(clinical).pages)
    for leftover in ("#super", "{=typst}", "<tn-"):
        assert leftover not in clinical_text, leftover
    assert "Technical notes" in clinical_text
    for pdf in pdfs[:3]:
        edge = max_right_edge(pdf)
        if edge is not None:  # only the margin check needs poppler
            assert edge <= RIGHT_EDGE[pdf.name] + 0.01, pdf.name
    figures = {p.name for p in (pdfs[0].parent / "figures").iterdir()}
    for name in ("known_groups", "strata", "tipping", "forest_bias", "brief_fig1", "brief_fig4"):
        assert {f"{name}.pdf", f"{name}.png"} <= figures, name
    egress = settings.project["egress"]
    report = check_egress(
        pdfs[0].parent,
        min_cell=egress["min_cell"],
        small_cell=egress["small_cell"],
        ignore_id_pattern_columns=egress["ignore_id_pattern_columns"],
    )
    assert report.ok, report.problems


COMPONENTS_SCHEMA = {"visit": pl.Utf8, "level": pl.Utf8, "sample": pl.Utf8}
# the weekly comparators, and the frame column prefix of the device measure behind each
WEEKLY_MEASURES = {
    "purposeful_week": "purposeful_min",
    "mv_week": "mv_min",
    "light_week": "light_min",
}


def _components(results: Path, name: str) -> pl.DataFrame:
    path = results / f"validity_components_{name}.csv"
    header = path.read_text().splitlines()[0].replace('"', "").split(",")
    overrides = {k: v for k, v in COMPONENTS_SCHEMA.items() if k in header}
    return pl.read_csv(path, null_values=["NA"], schema_overrides=overrides)


@pytest.mark.realdata
def test_e2e_components_reconcile(fast_run):
    out = fast_run.out
    work = fast_run.settings.work_dir / fast_run.analysis.name / out.name
    frame = pl.read_parquet(work / "frame.parquet")
    pase, item, hexes = (_components(out, n) for n in ("pase", "item", "hex"))
    for v in ("06", "08"):
        paired = frame.filter(
            pl.col(f"pase_days_{v}").is_not_null() & pl.col(f"device_walker_{v}").is_not_null()
        )
        at = pase.filter(pl.col("visit") == v)
        shares = at.filter((pl.col("component") == "frequency") & (pl.col("statistic") == "share"))
        assert shares["n"].sum() == paired.height  # every answer in exactly one category
        for cut in (1, 2, 3):
            rows = at.filter(pl.col("level") == f"cut{cut}")
            se_n = rows.filter(pl.col("statistic") == "se")["n"].item()
            sp_n = rows.filter(pl.col("statistic") == "sp")["n"].item()
            assert se_n + sp_n == paired.height  # the cut's 2x2 adds up to n
            assert se_n == paired[f"device_walker_{v}"].sum()
        # estimated weekly walking needs days == 0 or an hours answer, as well as the pairing
        weekly_paired = paired.filter(
            (pl.col(f"pase_days_{v}") == 0) | pl.col(f"pase_hours_{v}").is_not_null()
        )
        weekly = at.filter(pl.col("component") == "weekly")
        for comparator, measure in WEEKLY_MEASURES.items():
            rows = weekly.filter(pl.col("comparator") == comparator)
            for statistic in ("rho", "jt_p", "median_diff", "loa"):
                n = rows.filter((pl.col("level") == "all") & (pl.col("statistic") == statistic))[
                    "n"
                ].item()
                assert n == weekly_paired.height, (v, comparator, statistic)
            # a reliability is the between-wave correlation, so its n is the people valid at both
            both_waves = frame.filter(
                pl.col(f"{measure}_06").is_not_null() & pl.col(f"{measure}_08").is_not_null()
            )
            reliability = rows.filter(pl.col("statistic") == "reliability")["n"].item()
            assert reliability == both_waves.height, (v, comparator)
        # duration is asked of PASE walkers (days >= 1) who gave an hours answer
        walkers = paired.filter(
            (pl.col(f"pase_days_{v}") >= 1) & pl.col(f"pase_hours_{v}").is_not_null()
        )
        duration = at.filter(pl.col("component") == "duration")
        for statistic in ("jt_p", "rho"):
            n = duration.filter((pl.col("level") == "all") & (pl.col("statistic") == statistic))[
                "n"
            ].item()
            assert n == walkers.height, (v, statistic)
        medians = duration.filter(pl.col("statistic") == "median")
        assert medians["n"].sum() == walkers.height, v
    for sample, rows in (("validation", frame), ("lo_subset", frame.filter("in_lo"))):
        for component in ("times", "months", "years"):
            sel = item.filter((pl.col("sample") == sample) & (pl.col("component") == component))
            levels_n = sel.filter(pl.col("statistic") == "share")["n"].sum()
            no_band = sel.filter(pl.col("level") == "no_band")["n"].item()
            assert levels_n + no_band == rows.height
    correction = item.filter(
        (pl.col("sample") == "lo_subset") & (pl.col("statistic") == "correction")
    )
    assert correction.height == 3
    assert hexes.height > 0
    min_cell = load_assumptions(fast_run.analysis.root).items["components.min_cell_count"].value
    assert (hexes["count"] >= min_cell).all()


@pytest.mark.realdata
def test_components_handles_a_visit_without_paired_participants(step_copy):
    _edit_frame(
        step_copy,
        lambda f: f.with_columns(pl.lit(None, dtype=pl.Boolean).alias("device_walker_08")),
    )
    done = step_copy.run("components")
    assert done.returncode == 0, done.stderr
    pase = _components(step_copy.results, "pase")
    later = pase.filter(pl.col("visit") == "08")
    assert later.height > 0
    shares = later.filter(pl.col("statistic") == "share")
    assert (shares["n"] == 0).all()
    assert shares["estimate"].is_null().all()


def _spearman(df: pl.DataFrame, a: str, b: str) -> float:
    """Spearman correlation among the rows where both are present (average ranks for ties, as R)."""
    both = df.filter(pl.col(a).is_not_null() & pl.col(b).is_not_null())
    return both.select(pl.corr(pl.col(a).rank("average"), pl.col(b).rank("average"))).item()


@pytest.mark.realdata
def test_components_follows_the_two_wave_mean_pairing(step_copy):
    # Under two_wave_mean each visit's PASE answers are read against the participant's combined
    # device waves, and the device reliability is that of a mean over one or two waves
    adjacent = _components(step_copy.results, "pase")
    _set_assumption(step_copy, "pase.device_pairing", "two_wave_mean")
    done = step_copy.run("components")
    assert done.returncode == 0, done.stderr
    combined = _components(step_copy.results, "pase")
    frame = pl.read_parquet(step_copy.frames / "frame.parquet")

    def reliability(df, level="all"):
        return df.filter(
            (pl.col("component") == "weekly")
            & (pl.col("statistic") == "reliability")
            & (pl.col("level") == level)
        ).sort("visit", "comparator")

    before, after = reliability(adjacent), reliability(combined)
    assert before.height == after.height == 2 * len(WEEKLY_MEASURES)
    assert (after["n"] == before["n"]).all()  # the same between-wave correlation behind both
    assert (after["estimate"] > before["estimate"]).all(), after  # a mean is more reliable
    for v in ("06", "08"):
        paired = frame.filter(
            pl.col(f"pase_days_{v}").is_not_null() & pl.col("device_walker").is_not_null()
        )
        at = combined.filter(pl.col("visit") == v)
        shares = at.filter((pl.col("component") == "frequency") & (pl.col("statistic") == "share"))
        assert shares["n"].sum() == paired.height, v
        weekly = paired.filter(
            (pl.col(f"pase_days_{v}") == 0) | pl.col(f"pase_hours_{v}").is_not_null()
        )
        walkers = weekly.filter(pl.col(f"pase_walking_{v}") > 0)
        for comparator, measure in WEEKLY_MEASURES.items():
            r = _spearman(frame, f"{measure}_06", f"{measure}_08")
            for level, people in (("all", weekly), ("pase_walkers", walkers)):
                # wave_reliability(r, share): the share with two valid waves among those correlated
                share = (people["n_waves"] == 2).mean()
                expected = r / (r + (1 - r) * (1 - share / 2))
                row = at.filter(
                    (pl.col("comparator") == comparator)
                    & (pl.col("level") == level)
                    & (pl.col("statistic") == "reliability")
                )
                assert row["estimate"].item() == pytest.approx(expected, abs=1e-9), (v, level)
                rho = at.filter(
                    (pl.col("comparator") == comparator)
                    & (pl.col("level") == level)
                    & (pl.col("statistic") == "rho")
                )
                assert rho["n"].item() == people.height, (v, comparator, level)


@pytest.mark.realdata
def test_components_follows_the_pase_walker_threshold(step_copy):
    frame = pl.read_parquet(step_copy.frames / "frame.parquet")
    positive = frame.filter(pl.col("pase_walking_06") > 0)["pase_walking_06"]
    threshold = float(positive.quantile(0.25))
    assert threshold > 0
    _set_assumption(step_copy, "pase.walker_threshold", threshold)
    done = step_copy.run("components")
    assert done.returncode == 0, done.stderr
    pase = _components(step_copy.results, "pase").filter(pl.col("visit") == "06")
    paired = frame.filter(
        pl.col("pase_days_06").is_not_null() & pl.col("device_walker_06").is_not_null()
    )
    walkers = paired.filter(pl.col("pase_walking_06") > threshold)
    # the threshold leaves out some who walked (days >= 1), so it is the threshold that counts
    assert 0 < walkers.height < paired.filter(pl.col("pase_days_06") >= 1).height
    for comparator in WEEKLY_MEASURES:
        n = pase.filter(
            (pl.col("comparator") == comparator)
            & (pl.col("level") == "pase_walkers")
            & (pl.col("statistic") == "rho")
        )["n"].item()
        assert n == walkers.height, comparator
    duration = pase.filter(
        (pl.col("component") == "duration")
        & (pl.col("level") == "all")
        & (pl.col("statistic") == "rho")
    )["n"].item()
    assert duration == walkers.height  # PASE walkers by the threshold (all have an hours answer)


@pytest.mark.realdata
def test_components_hex_size_comes_from_the_ledger(step_copy):
    before = _components(step_copy.results, "hex")
    _set_assumption(step_copy, "components.hex_bins", 10)
    done = step_copy.run("components")
    assert done.returncode == 0, done.stderr
    after = _components(step_copy.results, "hex")
    assert after.height > 0

    def width(cells):  # half-width of a cell, which is the same for every cell of a visit
        return cells.group_by("visit").agg(pl.col("dx").first()).sort("visit")["dx"]

    assert (width(after) > width(before)).all()  # a third of the bins make wider cells


@pytest.mark.realdata
def test_components_deattenuation_needs_a_positive_reliability(step_copy):
    # a device measure that reverses between the waves has a negative reliability, which cannot
    # correct a correlation (it would give NaN): the corrected value is left out instead
    _edit_frame(step_copy, lambda f: f.with_columns((-pl.col("mv_min_06")).alias("mv_min_08")))
    done = step_copy.run("components")
    assert done.returncode == 0, done.stderr
    assert "NaNs produced" not in done.stderr, done.stderr  # no square root of a negative number
    pase = _components(step_copy.results, "pase")
    rows = pase.filter(pl.col("comparator") == "mv_week")
    reliability = rows.filter(pl.col("statistic") == "reliability")
    assert (reliability["estimate"] < 0).all()
    assert (reliability["n"] > 0).all()
    corrected = rows.filter(pl.col("statistic") == "rho_deattenuated")
    assert corrected.height > 0
    assert corrected["estimate"].is_null().all()  # NA, not NaN
    assert not rows["estimate"].is_nan().any()
