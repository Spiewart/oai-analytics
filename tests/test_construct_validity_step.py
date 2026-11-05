"""The gated construct_validity step on synthetic frames only.

Nothing here reads the release. Every frame is simulated with the real measure names, and the gate
is opened only in these throwaway folders. Real-data runs keep construct.scope_approved false.
"""

import functools
import json
import math
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from oai.config import load_settings
from oai.derive.construct import MEASURES
from oai.export.egress import check_egress
from oai.manifest import find_analysis
from oai.runner import process_env, r_profile_env, resolve_assumptions, select_steps, step_command

REPO = Path(__file__).resolve().parents[1]
COMPUTED = ("contrasts", "rule", "kl", "dose", "attrition")
EARLY = ("00", "01", "03", "05", "06", "08", "10")
ALL_MONTHS = {
    "00": 0,
    "01": 12,
    "03": 24,
    "05": 36,
    "06": 48,
    "08": 72,
    "10": 96,
    "13": 168,
    "14": 192,
}
CONTINUOUS = {
    "total",
    "total_minus_walking",
    "womac_function",
    "womac_walk",
    "pace_20m",
    "koos_sport",
}
# Which visits each measure has, as in the release
WITH_192 = {"walking_any", "hours_5plus", "womac_function", "womac_walk"}
NOT_AFTER = {"pace_20m", "koos_sport"}
TRUE_GAP = 40.0
# Walker gaps that differ from the default: WOMAC walking is lower (better), sitting less likely
GAPS = {"total": TRUE_GAP, "womac_walk": -3.0, "sitting_long": -0.7}


@functools.cache
def _ready() -> bool:
    if shutil.which("Rscript") is None:
        return False
    probe = subprocess.run(
        ["Rscript", "-e", "library(nlme); library(geepack); library(pkgload)"],
        cwd=REPO / "r",
        capture_output=True,
        env={**os.environ, "RENV_PROFILE": "report"},
    )
    return probe.returncode == 0


def synthetic_frame(
    *,
    people: int = 200,
    measures: tuple[str, ...] = tuple(MEASURES),
    kl4_nonwalkers: int | None = None,
    seed: int = 20261105,
) -> pl.DataFrame:
    """Long rows as construct_frame.parquet has them, with 70% Walkers and a gap on every measure."""
    rng = np.random.default_rng(seed)
    walker = rng.random(people) < 0.7
    age = rng.uniform(45, 79, people)
    sex = rng.integers(1, 3, people)
    bmi = rng.normal(28, 4, people)
    kl = rng.integers(0, 4, people).astype(float)  # 0-3, so KL 4 is placed below
    if kl4_nonwalkers is None:
        kl[rng.choice(people, 20, replace=False)] = 4
    else:
        nonwalkers = np.flatnonzero(~walker)
        walkers = np.flatnonzero(walker)
        assert len(nonwalkers) > kl4_nonwalkers
        kl[rng.choice(nonwalkers, kl4_nonwalkers, replace=False)] = 4
        kl[rng.choice(walkers, 30, replace=False)] = 4
    person = rng.normal(0, 1, people)
    pain0 = np.clip(rng.normal(3, 2, people), 0, 20)
    cohort = rng.integers(1, 4, people)
    times = np.where(walker, rng.integers(1, 4, people), -1)
    years = np.where(walker, rng.integers(1, 5, people), -1)
    rows = []
    for m in measures:
        visits = list(EARLY)
        if m not in NOT_AFTER:
            visits.append("13")
        if m in WITH_192:
            visits.append("14")
        if m == "koos_sport":
            visits.remove("00")
        for visit in visits:
            for i in range(people):
                # about a tenth have left by each later visit
                if ALL_MONTHS[visit] >= 168 and i % 10 == 0:
                    continue
                if m in CONTINUOUS:
                    gap = GAPS.get(m, 3.0)
                    value = 50 + walker[i] * gap + 5 * person[i] + rng.normal(0, 5)
                else:
                    p = 1 / (1 + math.exp(-(0.1 + GAPS.get(m, 0.7) * walker[i] + 0.6 * person[i])))
                    value = float(rng.random() < p)
                rows.append(
                    {
                        "ID": f"P{i:04d}",
                        "visit": visit,
                        "month": ALL_MONTHS[visit],
                        "measure": m,
                        "value": value,
                        "walker_yes": bool(walker[i]),
                        "walk_item": int(walker[i]),
                        "amount_times": int(times[i]) if times[i] > 0 else None,
                        "amount_years": int(years[i]) if years[i] > 0 else None,
                        "age": float(age[i]),
                        "sex": int(sex[i]),
                        "bmi": float(bmi[i]),
                        "age_at_visit": float(age[i] + ALL_MONTHS[visit] / 12),
                        "kl_max0": float(kl[i]),
                        "kl_group0": "0-1" if kl[i] < 2 else "2-3" if kl[i] < 4 else "4",
                        "womac_pain0": float(pain0[i]),
                        "womac_pain_t": float(np.clip(pain0[i] + rng.normal(0, 1), 0, 20)),
                        "cohort": int(cohort[i]),
                    }
                )
    return pl.DataFrame(rows, infer_schema_length=None)


def run_step(folder: Path, frame: pl.DataFrame | None, *, approved: bool, **overrides):
    """The step in folder/frames and folder/results, set up as the runner does."""
    settings = load_settings()
    analysis = find_analysis("walking_validation", settings.analyses_dir)
    frames, results = folder / "frames", folder / "results"
    frames.mkdir(parents=True, exist_ok=True)
    results.mkdir(parents=True, exist_ok=True)
    if frame is not None:
        frame.write_parquet(frames / "construct_frame.parquet")
    resolved = resolve_assumptions(
        analysis, None, {"construct.scope_approved": approved, **overrides}
    ).write(results)
    step = select_steps(analysis, step_id="construct_validity")[0]
    env = {
        **os.environ,
        "OAI_ANALYSIS": analysis.name,
        "OAI_FRAME_DIR": str(frames),
        "OAI_RESULTS_DIR": str(results),
        "OAI_RESULTS_BASE": str(results.parent),
        "OAI_ASSUMPTIONS": str(resolved),
        **r_profile_env(settings),
    }
    done = subprocess.run(
        step_command(step, analysis),
        cwd=analysis.root,
        env=process_env(step, analysis, env),
        capture_output=True,
        text=True,
    )
    return done, results


def read(results: Path, name: str) -> pl.DataFrame:
    return pl.read_csv(
        results / f"construct_{name}.csv", null_values="NA", infer_schema_length=None
    )


def ledger(key: str):
    settings = load_settings()
    analysis = find_analysis("walking_validation", settings.analyses_dir)
    return resolve_assumptions(analysis, None, {}).values[key]


@pytest.fixture(autouse=True)
def needs_r():
    if not _ready():
        pytest.skip("the R report profile with nlme and geepack is unavailable")


@pytest.fixture(scope="module")
def approved(tmp_path_factory):
    """One gate-open run on the full synthetic frame, shared for speed."""
    if not _ready():
        pytest.skip("the R report profile with nlme and geepack is unavailable")
    folder = tmp_path_factory.mktemp("approved")
    frame = synthetic_frame()
    # module scope is set up before conftest's per-test isolation, so isolate here too
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("OAI_DATA_DIR", str(REPO / "tests" / "fixtures" / "oai"))
        patch.setenv("OAI_WORK_DIR", str(folder / "work"))
        patch.setenv("OAI_RESULTS_DIR", str(folder / "out"))
        for key in ("OAI_GENO_DIR", "OAI_ANALYSES_DIR", "OAI_CONFIG", "OAI_FRAME_DIR"):
            patch.setenv(key, "")
        done, results = run_step(folder, frame, approved=True)
    assert done.returncode == 0, done.stderr
    return frame, results


def test_step_fits_nothing_until_approved(tmp_path):
    # The frame file is garbage, so a step that read any data before the gate would fail.
    (tmp_path / "frames").mkdir()
    (tmp_path / "frames" / "construct_frame.parquet").write_text("not a parquet file")
    done, results = run_step(tmp_path, None, approved=False)
    assert done.returncode == 0, done.stderr
    assert read(results, "status")["status"].to_list() == ["awaiting_review"]
    assert sorted(p.name for p in results.glob("construct_*.csv")) == ["construct_status.csv"]


def test_step_removes_results_left_from_an_approved_run_when_the_gate_closes(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    for name in COMPUTED:
        (results / f"construct_{name}.csv").write_text("x\n1\n")
    (results / "construct_counts.csv").write_text("x\n1\n")  # the cohort step's, stays
    done, results = run_step(tmp_path, None, approved=False)
    assert done.returncode == 0, done.stderr
    assert sorted(p.name for p in results.glob("construct_*.csv")) == [
        "construct_counts.csv",
        "construct_status.csv",
    ]


def test_step_computes_when_approved(approved):
    _, results = approved
    assert read(results, "status")["status"].to_list() == ["computed"]
    for name in COMPUTED:
        assert (results / f"construct_{name}.csv").exists(), name


def test_contrasts_have_the_models_structures_and_ledger_labels(approved):
    frame, results = approved
    got = read(results, "contrasts")
    assert got.columns[:17] == [
        "facet",
        "measure",
        "model",
        "term",
        "estimate",
        "lo",
        "hi",
        "p",
        "p_holm",
        "scale",
        "std_diff",
        "n_people",
        "n_obs",
        "converged",
        "expected",
        "period_test",
        "favors_walkers",
    ]
    assert set(got["measure"]) == set(MEASURES)
    facets, expected = ledger("construct.facets"), ledger("construct.expected")
    for row in got.iter_rows(named=True):
        assert row["facet"] == facets[row["measure"]]
        assert row["expected"] == expected[row["measure"]]
        assert row["scale"] == ("difference" if row["measure"] in CONTINUOUS else "or")
    assert got["converged"].all(), got.filter(~pl.col("converged"))

    # base: overall, periods, visits; sensitivity models: overall and periods only
    def terms(model, measure):
        return set(got.filter(model=model, measure=measure)["term"])

    visits = {"00", "01", "03", "05", "06", "08", "10", "13"}
    assert terms("base", "total") == {"overall", "before", "at", "after"} | visits
    assert terms("base", "walking_any") == {"overall", "before", "at", "after"} | visits | {"14"}
    assert terms("base", "pace_20m") == {"overall", "before", "at"} | (visits - {"13"})
    for model in ("enroll_disease", "time_pain", "age50"):
        assert terms(model, "total") == {"overall", "before", "at", "after"}
    assert set(got["model"]) == {"base", "enroll_disease", "time_pain", "age50", "completers_168"}


def test_base_overall_recovers_the_true_gap_and_std_diff_is_over_the_first_visit_sd(approved):
    frame, results = approved
    got = read(results, "contrasts")
    row = got.filter(model="base", measure="total", term="overall").row(0, named=True)
    assert row["lo"] < TRUE_GAP < row["hi"]
    first = frame.filter(measure="total", visit="00")
    sums = [(g["value"] - g["value"].mean()).pow(2).sum() for _, g in first.group_by("walker_yes")]
    pooled = math.sqrt(sum(sums) / (first.height - 2))
    assert row["std_diff"] == pytest.approx(row["estimate"] / pooled, rel=1e-9)
    # std_diff is on gaussian rows only
    assert got.filter(scale="or")["std_diff"].null_count() == got.filter(scale="or").height
    assert got.filter(scale="difference")["std_diff"].null_count() == 0


def test_holm_families_follow_the_spec(approved):
    _, results = approved
    got = read(results, "contrasts")
    with_holm = got.filter(pl.col("p_holm").is_not_null())
    assert with_holm["measure"].sort().to_list() == sorted(
        ["total", "walking_any", "hours_5plus", "womac_walk", "pace_20m", "womac_function"]
    )
    assert set(with_holm["model"]) == {"base"}
    assert set(with_holm["term"]) == {"overall"}
    # p appears only where a claim rests on it
    with_p = got.filter(pl.col("p").is_not_null())
    assert (
        with_p.select("measure", "model", "term")
        .sort("measure")
        .equals(with_holm.select("measure", "model", "term").sort("measure"))
    )
    divergent = got.filter(facet="divergent")
    assert divergent["p"].null_count() == divergent.height
    assert divergent["p_holm"].null_count() == divergent.height

    def holm(ps):
        order = sorted(range(len(ps)), key=lambda i: ps[i])
        out, running = [0.0] * len(ps), 0.0
        for rank, i in enumerate(order):
            running = max(running, min(1.0, (len(ps) - rank) * ps[i]))
            out[i] = running
        return out

    for family in ("primary", "convergent"):
        rows = with_holm.filter(facet=family)
        assert rows["p_holm"].to_list() == pytest.approx(holm(rows["p"].to_list()))
    # the discriminative family, on its own
    kl = read(results, "kl")
    discriminative = kl.filter(pl.col("p_holm").is_not_null())
    assert set(discriminative["analysis"]) == {"walker_share", "walker_x_kl"}
    tests = discriminative.unique(["analysis", "measure"], maintain_order=True)
    assert tests.height == 3
    assert tests["p_holm"].to_list() == pytest.approx(holm(tests["p"].to_list()))
    assert (
        kl.filter(analysis="within_kl")["p"].null_count() == kl.filter(analysis="within_kl").height
    )


def test_period_test_is_on_the_pase_total_base_row_only(approved):
    _, results = approved
    got = read(results, "contrasts").filter(pl.col("period_test").is_not_null())
    assert got.select("measure", "model", "term").rows() == [("total", "base", "overall")]
    assert 0 <= got["period_test"][0] <= 1


def test_sensitivity_models_use_their_own_rows_and_covariates(approved):
    frame, results = approved
    got = read(results, "contrasts")

    def row(model, measure="total", term="overall"):
        return got.filter(model=model, measure=measure, term=term).row(0, named=True)

    assert row("enroll_disease")["estimate"] != row("base")["estimate"]
    assert row("time_pain")["estimate"] != row("enroll_disease")["estimate"]
    assert row("time_pain")["n_obs"] == row("base")["n_obs"]
    total = frame.filter(measure="total")
    assert row("age50")["n_obs"] == total.filter(pl.col("age_at_visit") >= 50).height
    assert row("base")["n_obs"] == total.height


def test_completers_are_those_with_data_at_both_visits_and_report_visit_13_only(approved):
    frame, results = approved
    contrasts = read(results, "contrasts")
    got = contrasts.filter(model="completers_168")
    assert set(got["term"]) == {"visit_13"}
    # a 192-month measure's row is the 168-month contrast, not 168 and 192 together
    base_after = contrasts.filter(model="base", measure="walking_any", term="after")
    assert got.filter(measure="walking_any")["estimate"][0] != base_after["estimate"][0]
    # no 168-month data, so no row
    assert set(got["measure"]) == set(MEASURES) - NOT_AFTER
    assert got.height == len(set(got["measure"]))
    measure = frame.filter(measure="total")
    both = set(measure.filter(visit="10")["ID"]) & set(measure.filter(visit="13")["ID"])
    assert got.filter(measure="total")["n_people"][0] == len(both)


def test_rule_has_the_divergent_measures_and_the_narrowing_result(approved):
    _, results = approved
    rule = read(results, "rule")
    facets = ledger("construct.facets")
    assert set(rule["measure"]) == {m for m, f in facets.items() if f == "divergent"}
    assert rule.columns == [
        "measure",
        "estimate",
        "scale",
        "std_diff",
        "band",
        "relative_met",
        "lo",
        "hi",
        "narrows",
        "narrow_count",
        "narrow_evaluable",
    ]
    contrasts = read(results, "contrasts").filter(model="base", term="overall")
    items = ledger("construct.rule.narrow_items")
    count = contrasts.filter(pl.col("measure").is_in(items), pl.col("estimate") >= 1.44).height
    assert rule["narrow_count"].unique().to_list() == [count]
    assert rule["narrow_evaluable"].unique().to_list() == [7]
    assert rule["narrows"].unique().to_list() == [count >= 4]
    assert rule.filter(measure="koos_sport")["relative_met"].null_count() == 0
    assert rule.filter(measure="garden")["relative_met"].null_count() == 1


def test_kl_table_has_each_analysis_with_its_reporting_place(approved):
    frame, results = approved
    kl = read(results, "kl")
    assert kl.columns[:12] == [
        "analysis",
        "group",
        "measure",
        "term",
        "estimate",
        "lo",
        "hi",
        "p",
        "p_holm",
        "n_people",
        "kl_groups_used",
        "reporting",
    ]
    assert kl["kl_groups_used"].unique().to_list() == ["0-1,2-4"]  # few KL 4 non-walkers here
    share = kl.filter(analysis="walker_share")
    assert share["group"].to_list() == ["2-4"]
    assert set(share["reporting"]) == {"table"}
    # by hand: the number of people with a KL group
    assert (
        share["n_people"][0] == frame.unique("ID").filter(pl.col("kl_group0").is_not_null()).height
    )
    within = kl.filter(analysis="within_kl")
    assert set(within["reporting"]) == {"supplement"}
    assert within.select("group", "measure").sort("group", "measure").rows() == [
        ("0-1", "total"),
        ("0-1", "walking_any"),
        ("2-4", "total"),
        ("2-4", "walking_any"),
    ]
    assert within.drop_nulls("estimate").height == 4
    tests = kl.filter(analysis="walker_x_kl")
    assert sorted(tests["measure"]) == ["total", "walking_any"]
    assert set(tests["reporting"]) == {"supplement"}
    assert tests.drop_nulls("p").height == 2


def test_dose_has_each_level_against_not_walkers_and_a_trend(approved):
    frame, results = approved
    dose = read(results, "dose")
    assert set(dose["grouping"]) == {"times", "years"}
    assert dose.filter(grouping="times")["level"].sort().to_list() == [1, 2, 3]
    assert dose.filter(grouping="years")["level"].sort().to_list() == [1, 2, 3, 4]
    labels = ledger("components.answer_labels")
    assert dose.filter(grouping="times").sort("level")["label"].to_list() == labels["times"]
    assert dose.drop_nulls(["estimate", "lo", "hi", "trend_p"]).height == dose.height
    assert "p" not in dose.columns
    at_96 = frame.filter(measure="walking_any", visit="10")
    assert dose["n_ref"].unique().to_list() == [at_96.filter(~pl.col("walker_yes")).height]
    one = dose.filter(grouping="times", level=2)["n"][0]
    assert one == at_96.filter(amount_times=2).height


def test_attrition_describes_who_stayed_with_counts_and_no_p_values(approved):
    frame, results = approved
    attrition = read(results, "attrition")
    assert not any(c.startswith("p") and c != "people" for c in attrition.columns)
    total = frame.filter(measure="total")
    at_96 = set(total.filter(visit="10")["ID"])
    at_168 = set(total.filter(visit="13")["ID"])

    def value(group, characteristic, statistic):
        return attrition.filter(group=group, characteristic=characteristic, statistic=statistic)[
            "value"
        ][0]

    assert value("all", "pase_total_96", "n") == len(at_96)
    assert value("all", "pase_total_168", "n") == len(at_168)
    assert value("with_168", "people", "n") == len(at_96 & at_168)
    assert value("without_168", "people", "n") == len(at_96 - at_168)
    people = frame.unique("ID")
    stayed = people.filter(pl.col("ID").is_in(at_96 & at_168))
    assert value("with_168", "age", "mean") == pytest.approx(stayed["age"].mean())
    assert value("with_168", "female", "share") == pytest.approx((stayed["sex"] == 2).mean())
    assert value("with_168", "kl_2plus", "share") == pytest.approx((stayed["kl_max0"] >= 2).mean())
    assert value("with_168", "walker", "share") == pytest.approx(stayed["walker_yes"].mean())
    first = total.filter(pl.col("ID").is_in(at_96 & at_168), visit="00")["value"]
    assert value("with_168", "pase_total_enrollment", "mean") == pytest.approx(first.mean())
    characteristics = set(attrition.filter(group="without_168")["characteristic"])
    assert {"people", "age", "female", "bmi", "kl_2plus", "pase_total_enrollment", "walker"} == (
        characteristics
    )


def test_results_pass_the_egress_check(approved):
    _, results = approved
    keep = results / "assumptions.resolved.json"
    settings = load_settings()
    egress = settings.project["egress"]
    assert keep.exists()
    report = check_egress(
        results,
        min_cell=egress["min_cell"],
        small_cell=egress["small_cell"],
        ignore_id_pattern_columns=egress["ignore_id_pattern_columns"],
    )
    assert report.ok, report.problems


def test_enroll_disease_and_walker_share_match_models_written_by_hand(approved):
    # Categories stay categories: kl_group0 and cohort as factors, the pain score numeric.
    _, results = approved
    script = f"""
    d <- as.data.frame(nanoparquet::read_parquet("{results.parent / "frames" / "construct_frame.parquet"}"))
    t <- d[d$measure == "total", ]
    t$walker <- as.numeric(t$walker_yes)
    fit <- nlme::lme(value ~ walker + factor(visit) + age + sex + bmi + factor(kl_group0) + womac_pain0 +
                       factor(cohort), random = ~ 1 | ID, data = t, method = "ML")
    p <- d[!duplicated(d$ID), ]
    p$kl <- ifelse(p$kl_group0 == "0-1", "0-1", "2-4")
    share <- glm(walker_yes ~ age + sex + bmi + kl, family = binomial, data = p)
    null <- glm(walker_yes ~ age + sex + bmi, family = binomial, data = p)
    cat(nlme::fixef(fit)[["walker"]], exp(coef(share)[["kl2-4"]]),
        anova(null, share, test = "Chisq")[2, "Pr(>Chi)"], "\n")
    """
    done = subprocess.run(
        ["Rscript", "-e", script],
        cwd=REPO / "r",
        capture_output=True,
        text=True,
        env={**os.environ, "RENV_PROFILE": "report"},
    )
    assert done.returncode == 0, done.stderr
    gap, share_or, share_p = (float(v) for v in done.stdout.split()[-3:])
    got = read(results, "contrasts").filter(model="enroll_disease", measure="total", term="overall")
    assert got["estimate"][0] == pytest.approx(gap, rel=1e-6)
    share = read(results, "kl").filter(analysis="walker_share")
    assert share["estimate"][0] == pytest.approx(share_or, rel=1e-6)
    assert share["p"][0] == pytest.approx(share_p, rel=1e-6)


@pytest.mark.parametrize(("count", "used"), [(10, "0-1,2-4"), (30, "0-1,2-3,4")])
def test_kl4_combines_below_the_minimum(tmp_path, count, used):
    frame = synthetic_frame(people=220, measures=("total", "walking_any"), kl4_nonwalkers=count)
    done, results = run_step(tmp_path, frame, approved=True)
    assert done.returncode == 0, done.stderr
    kl = read(results, "kl")
    assert kl["kl_groups_used"].unique().to_list() == [used]
    assert kl.filter(analysis="walker_share")["group"].to_list() == used.split(",")[1:]
    within = kl.filter(analysis="within_kl", measure="total")
    assert within["group"].to_list() == used.split(",")


def test_a_failed_model_is_recorded_and_the_step_continues(tmp_path):
    frame = synthetic_frame(
        measures=("total", "walking_any", "garden", "caring", "yard", "home_repairs")
    )
    frame = frame.with_columns(
        # unfittable: a binary outcome with no events at any visit
        pl.when(pl.col("measure") == "garden").then(0.0).otherwise(pl.col("value")).alias("value")
    )
    # a visit no period holds stops walker_model() itself, in the period model only
    extra = frame.filter(measure="caring", visit="00").with_columns(visit=pl.lit("99"))
    # no variation at all at visit 13
    frame = frame.with_columns(
        pl.when(pl.col("measure") == "home_repairs", pl.col("visit") == "13")
        .then(1.0)
        .otherwise(pl.col("value"))
        .alias("value")
    )
    # separated after the survey only: every Walker walks, so that period has no estimate
    frame = frame.with_columns(
        pl.when(pl.col("measure") == "yard", pl.col("walker_yes"), pl.col("visit").is_in(["13"]))
        .then(1.0)
        .otherwise(pl.col("value"))
        .alias("value")
    )
    done, results = run_step(tmp_path, pl.concat([frame, extra]), approved=True)
    assert done.returncode == 0, done.stderr
    got = read(results, "contrasts")
    garden = got.filter(model="base", measure="garden", term="overall").row(0, named=True)
    assert garden["converged"] is False
    assert garden["estimate"] is None
    assert garden["fit_note"]
    period = got.filter(pl.col("term").is_null(), model="base", measure="caring")
    assert period["converged"].to_list() == [False]
    assert "not in periods" in period["fit_note"][0]
    for measure in ("total", "walking_any", "yard"):
        fine = got.filter(model="base", measure=measure, term="overall").row(0, named=True)
        assert fine["converged"] is True
        assert fine["estimate"] is not None
    for model, term in (("base", "after"), ("completers_168", "visit_13")):
        after = got.filter(model=model, measure="yard", term=term).row(0, named=True)
        assert after["converged"] is False
        assert after["fit_note"] == "separated"
    # the fit succeeds with visit 13 left out, so its term cannot be estimated: still a visible row
    gone = got.filter(model="completers_168", measure="home_repairs").row(0, named=True)
    assert gone["term"] == "visit_13"
    assert gone["converged"] is False
    assert gone["estimate"] is None
    assert "not estimable" in gone["fit_note"]
    assert gone["favors_walkers"] is None
    assert got.filter(model="base", measure="yard", term="at")["estimate"][0] is not None
    # measures with no rows produce no rows
    assert "koos_sport" not in set(got["measure"])
    rule = read(results, "rule")
    assert rule.filter(measure="garden")["band"].null_count() == 1
    assert rule["narrow_evaluable"].unique().to_list() == [3]
    assert read(results, "status")["status"].to_list() == ["computed"]


def test_holm_family_size_stays_fixed_when_a_model_fails(tmp_path):
    frame = synthetic_frame(people=120, measures=("total", "walking_any")).with_columns(
        pl.when(pl.col("measure") == "walking_any")
        .then(0.0)
        .otherwise(pl.col("value"))
        .alias("value")
    )
    done, results = run_step(tmp_path, frame, approved=True)
    assert done.returncode == 0, done.stderr
    got = read(results, "contrasts").filter(model="base", term="overall")
    survivor = got.filter(measure="total").row(0, named=True)
    assert 0 < survivor["p"] < 0.5
    assert survivor["p_holm"] == pytest.approx(min(1, 2 * survivor["p"]), rel=1e-6, abs=0)
    assert got.filter(measure="walking_any")["p_holm"][0] is None
    # discriminative: three tests are pre-specified, and one failed here
    kl = read(results, "kl")
    assert kl.filter(analysis="walker_x_kl", measure="walking_any")["p"][0] is None
    tests = kl.filter(pl.col("p").is_not_null()).unique(
        ["analysis", "measure"], maintain_order=True
    )
    assert tests.height == 2
    small, large = sorted(tests["p"].to_list())
    expected = {small: min(1, 3 * small), large: min(1, max(3 * small, 2 * large))}
    for row in tests.iter_rows(named=True):
        assert row["p_holm"] == pytest.approx(expected[row["p"]], rel=1e-6, abs=0)


def test_favors_walkers_follows_the_estimate_and_each_measures_direction(approved):
    _, results = approved
    got = read(results, "contrasts")
    higher = ledger("construct.higher_is_better")
    for row in got.filter(pl.col("estimate").is_not_null()).iter_rows(named=True):
        null = 1 if row["scale"] == "or" else 0
        better = row["estimate"] > null if higher[row["measure"]] else row["estimate"] < null
        assert row["favors_walkers"] is better, row
    overall = got.filter(model="base", term="overall")

    def favors(measure):
        return overall.filter(measure=measure)["favors_walkers"][0]

    # the simulated gaps: more activity and a lower WOMAC walking score favor Walkers
    assert favors("total") is True
    assert favors("womac_walk") is True
    assert favors("womac_function") is False  # simulated higher, which is worse
    assert favors("sitting_long") is True  # simulated less likely, with lower as the direction


def test_a_dose_level_with_no_variation_has_no_estimate_and_says_why(tmp_path):
    frame = synthetic_frame(people=120, measures=("total", "walking_any"))
    walkers = frame.filter(pl.col("walker_yes")).unique("ID", maintain_order=True)["ID"].to_list()
    tiny = walkers[:3]
    frame = frame.with_columns(
        pl.when(pl.col("ID").is_in(tiny))
        .then(3)
        .when(pl.col("amount_times") == 3)
        .then(2)
        .otherwise(pl.col("amount_times"))
        .alias("amount_times"),
        pl.when(pl.col("ID").is_in(tiny), measure="walking_any", visit="10")
        .then(1.0)
        .otherwise(pl.col("value"))
        .alias("value"),
    )
    done, results = run_step(tmp_path, frame, approved=True)
    assert done.returncode == 0, done.stderr
    dose = read(results, "dose").filter(grouping="times").sort("level")
    small = dose.filter(level=3).row(0, named=True)
    assert small["n"] == 3
    assert (small["estimate"], small["lo"], small["hi"]) == (None, None, None)
    assert "constant" in small["fit_note"]
    assert dose.filter(level=1)["estimate"][0] is not None
    assert dose.filter(level=1)["fit_note"][0] is None
    assert dose.filter(level=1)["trend_p"][0] is not None


def test_a_measure_the_ledger_does_not_know_stops_the_step(tmp_path):
    frame = synthetic_frame(people=60, measures=("total",)).with_columns(measure=pl.lit("mystery"))
    done, _ = run_step(tmp_path, frame, approved=True)
    assert done.returncode != 0
    assert "mystery" in done.stderr


def test_ledger_entries_behind_the_step_are_present():
    assert set(ledger("construct.continuous_measures")) == CONTINUOUS
    higher = ledger("construct.higher_is_better")
    assert set(higher) == set(MEASURES)
    assert {m for m, up in higher.items() if not up} == {
        "womac_function",
        "womac_walk",
        "sitting_long",
    }
    assert json.dumps(ledger("construct.sensitivity_covariates"), sort_keys=True) == json.dumps(
        {"enroll_disease": ["kl_group0", "womac_pain0", "cohort"], "time_pain": ["womac_pain_t"]},
        sort_keys=True,
    )
