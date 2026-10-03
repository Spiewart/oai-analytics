import json
import runpy
import sys
import tomllib
import warnings
from pathlib import Path

import polars as pl
import pytest

from oai.assumptions import load_assumptions
from oai.derive import accel
from oai.replication import grade

REPO = Path(__file__).resolve().parents[1]
ANALYSIS = REPO / "analyses" / "walking_validation"
sys.path.insert(0, str(ANALYSIS))

from wv import (  # noqa: E402
    DEVICE_RULE_KEYS,
    OUTCOMES,
    CohortError,
    check_walker_coding,
    cohort_flow,
    combine_waves,
    lo_knee_columns,
    lo_model,
    lo_unanswered_with_device,
    person_outcomes,
    read_lo_frame,
    read_lo_results,
    with_amount_level,
    with_device_walker,
    without_ungradable_device_rows,
)

LEDGER = load_assumptions(ANALYSIS)
DEFAULTS = {key: item.value for key, item in LEDGER.items.items()}
EXPECTED = tomllib.loads((ANALYSIS / "expected.toml").read_text())

MEASURE = {
    "purposeful_min": 0.0,
    "counts_per_day": 0.0,
    "light_min": 0.0,
    "bout_days_per_week": 0.0,
    "mv_min": 0.0,
}


def device_rows(rows):
    return pl.DataFrame([{**MEASURE, **r} for r in rows])


def test_combine_waves_keeps_single_wave_persons():
    device = device_rows(
        [
            {"ID": 1, "wave": "06", "valid": True, "purposeful_min": 10.0},
            {"ID": 1, "wave": "08", "valid": True, "purposeful_min": 20.0},
            {"ID": 2, "wave": "06", "valid": True, "purposeful_min": 5.0},
            {"ID": 3, "wave": "06", "valid": False, "purposeful_min": 99.0},
        ]
    )
    out = combine_waves(device, "mean").sort("ID")
    assert out["ID"].to_list() == [1, 2]
    assert out["n_waves"].to_list() == [2, 1]
    assert out["purposeful_min"].to_list() == [15.0, 5.0]
    assert out["purposeful_min_08"].to_list() == [20.0, None]
    one_wave = combine_waves(device, "08")
    assert one_wave["ID"].to_list() == [1] and one_wave["purposeful_min"].to_list() == [20.0]
    assert "purposeful_min_06" in one_wave.columns
    assert one_wave["n_waves"].to_list() == [1]  # the waves used, not the waves the person has
    first_wave = combine_waves(device, "06").sort("ID")
    assert first_wave["ID"].to_list() == [1, 2] and first_wave["n_waves"].to_list() == [1, 1]
    with pytest.raises(ValueError, match="combination"):
        combine_waves(device, "both")


def test_combine_waves_carries_mv_minutes_per_wave():
    device = pl.DataFrame(
        {
            "ID": [1, 1, 2],
            "wave": ["06", "08", "06"],
            "valid": [True, True, True],
            "purposeful_min": [10.0, 20.0, 5.0],
            "counts_per_day": [1.0, 1.0, 1.0],
            "light_min": [1.0, 1.0, 1.0],
            "bout_days_per_week": [1.0, 1.0, 1.0],
            "mv_min": [30.0, 50.0, 12.0],
        }
    )
    out = combine_waves(device, "mean").sort("ID")
    assert out["mv_min"].to_list() == [40.0, 12.0]
    assert out["mv_min_06"].to_list() == [30.0, 12.0]
    assert out["mv_min_08"].to_list() == [50.0, None]


def test_device_walker_rules():
    df = pl.DataFrame({"bout_days_per_week": [0.0, 1.0, 2.0], "purposeful_min": [0.0, 10.0, 25.0]})
    rule = lambda r: with_device_walker(df, r, 2.0, 150.0)["device_walker"].to_list()  # noqa: E731
    assert rule("bout_days") == [False, False, True]
    assert rule("any_bout") == [False, True, True]
    assert rule("bout_minutes") == [False, False, True]
    with pytest.raises(ValueError, match="walker_rule"):
        rule("steps")


def test_device_walker_per_wave():
    # The same rule on one wave's own measures; null where the person has no valid wave there
    df = pl.DataFrame(
        {
            "bout_days_per_week_06": [0.0, 3.0, None],
            "purposeful_min_06": [0.0, 30.0, None],
            "bout_days_per_week_08": [2.0, 1.0, 0.0],
            "purposeful_min_08": [25.0, 5.0, 0.0],
        }
    )
    out = with_device_walker(df, "bout_days", 2.0, 150.0, wave="06")
    assert out["device_walker_06"].to_list() == [False, True, None]
    assert "device_walker" not in out.columns
    out = with_device_walker(out, "bout_minutes", 2.0, 150.0, wave="08")
    assert out["device_walker_08"].to_list() == [True, False, False]


def test_amount_level_median_split():
    df = pl.DataFrame(
        {"walker": [False, True, True, True, True], "sessions": [None, 10.0, 20.0, 30.0, None]}
    )
    assert with_amount_level(df)["amount_level"].to_list() == [
        "none",
        "lower",
        "lower",
        "upper",
        None,
    ]


def test_amount_level_without_a_median_is_null_for_walkers():
    # no walker has an amount, so there is no median and no split: walkers have no level
    df = pl.DataFrame(
        {"walker": [False, True, True, None], "sessions": [None, None, None, None]},
        schema_overrides={"sessions": pl.Float64},
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # no comparison with a null median
        level = with_amount_level(df)["amount_level"].to_list()
    assert level == ["none", None, None, None]


def test_person_outcomes_any_knee():
    knees = pl.DataFrame(
        {
            "ID": [1, 1, 2, 3],
            "walker": [True, True, False, True],
            "new_pain": [False, True, None, None],
            "kl_worse": [False, False, True, None],
            "jsn_worse": [None, None, None, None],
            "improved_pain": [None, False, None, True],
        },
        schema_overrides={"jsn_worse": pl.Boolean},
    )
    out = person_outcomes(knees).sort("ID")
    assert out["new_pain_any"].to_list() == [True, None, None]
    assert out["kl_worse_any"].to_list() == [False, True, None]
    assert out["jsn_worse_any"].to_list() == [None, None, None]
    assert out["lo_walker"].to_list() == [True, False, True]


def write_lo(tmp_path, label, coding):
    d = tmp_path / "lo2022_walking" / label
    d.mkdir(parents=True)
    pl.DataFrame({"ID": [1], "walker": [True]}).write_parquet(d / "frame.parquet")
    values = {
        "exposure.yes_without_amount_as": coding,
        "model.covariates": ["age", "sex", "kl0"],
        "model.kl_covariate": "factor",
        "model.corstr": "exchangeable",
    }
    (d / "assumptions.resolved.json").write_text(
        json.dumps({"assumptions": {k: {"value": v} for k, v in values.items()}})
    )


def test_read_lo_frame_rejects_other_coding(tmp_path):
    write_lo(tmp_path, "default", "walker")
    with pytest.raises(CohortError, match="codes it as 'walker'") as err:
        read_lo_frame(tmp_path, "default", "non-walker")
    message = str(err.value)
    # the first instruction is to choose another run, not to re-run the one that does not match
    assert message.startswith("set bias.lo2022_label to the label of a lo2022_walking run")
    assert "yes-without-amount as 'non-walker'" in message
    assert "`oai run lo2022_walking --variant <variant>`" in message
    assert "`oai run lo2022_walking`" not in message  # the same label again would not help
    frame, values = read_lo_frame(tmp_path, "default", "walker")
    assert frame.height == 1 and values["model.corstr"] == "exchangeable"


def test_read_lo_results_names_a_command_the_cli_accepts(tmp_path):
    # the replication's default run takes no --variant (the CLI rejects --variant default)
    with pytest.raises(CohortError, match="comparison.csv is missing") as err:
        read_lo_results(tmp_path / "lo2022_walking" / "default", "default")
    assert "`oai run lo2022_walking`" in str(err.value)
    assert "--variant default" not in str(err.value)
    with pytest.raises(CohortError) as err:
        read_lo_results(tmp_path / "lo2022_walking" / "x", "walker_requires_amount")
    assert "`oai run lo2022_walking --variant walker_requires_amount`" in str(err.value)


def test_read_lo_results(tmp_path):
    lo = tmp_path / "lo2022_walking" / "default"
    lo.mkdir(parents=True)
    pl.DataFrame({"metric": ["t2.new_pain.or_adj", "t1.age"], "ours": ["0.6", "61"]}).write_csv(
        lo / "comparison.csv"
    )
    pl.DataFrame({"outcome": ["new_pain"], "or": [0.6]}).write_csv(lo / "table2.csv")
    out = read_lo_results(lo, "default")
    assert list(out) == ["lo2022_t2.csv", "lo2022_table2.csv"]
    assert out["lo2022_t2.csv"] == b"metric,ours\nt2.new_pain.or_adj,0.6\n"
    assert out["lo2022_table2.csv"] == (lo / "table2.csv").read_bytes()
    assert list(tmp_path.rglob("lo2022_t2.csv")) == []  # reading writes nothing


def test_read_lo_results_stops_on_an_empty_table_2(tmp_path):
    lo = tmp_path / "lo2022_walking" / "walker_requires_amount"
    lo.mkdir(parents=True)
    pl.DataFrame({"metric": ["t1.age"], "ours": ["61"]}).write_csv(lo / "comparison.csv")
    pl.DataFrame({"outcome": ["new_pain"]}).write_csv(lo / "table2.csv")
    with pytest.raises(CohortError, match="no t2.* rows") as err:
        read_lo_results(lo, "walker_requires_amount")
    assert "`oai run lo2022_walking --variant walker_requires_amount`" in str(err.value)
    pl.DataFrame({"name": ["t2.x"]}).write_csv(lo / "comparison.csv")
    with pytest.raises(CohortError, match="no metric column"):
        read_lo_results(lo, "walker_requires_amount")


def test_lo_knee_columns_names_what_is_missing():
    knees = pl.DataFrame(
        {c: [1] for c in ["ID", "SIDE", "walker", "age", "sex", "bmi", "kl0", "extra", *OUTCOMES]}
    )
    out = lo_knee_columns(knees, ["age", "sex", "kl0"], "default")
    assert out.columns == ["ID", "SIDE", "walker", "age", "sex", "bmi", "kl0", *OUTCOMES]
    with pytest.raises(CohortError) as err:
        lo_knee_columns(knees.drop("kl0", "bmi", "kl_worse"), ["age", "sex", "kl0"], "default")
    message = str(err.value)
    assert "lacks columns bmi, kl0, kl_worse" in message
    assert "`oai run lo2022_walking`" in message
    with pytest.raises(CohortError, match="lacks column alignment;"):
        lo_knee_columns(knees, ["age", "alignment"], "default")


def test_read_lo_frame_names_the_command(tmp_path):
    with pytest.raises(
        CohortError, match="oai run lo2022_walking --variant walker_requires_amount"
    ):
        read_lo_frame(tmp_path, "walker_requires_amount", "non-walker")


def test_lo_model_mirrors_models_r():
    values = {
        "model.covariates": ["age", "sex", "kl0"],
        "model.kl_covariate": "factor",
        "model.corstr": "exchangeable",
    }
    assert lo_model(values) == {
        "or_unadj": "walker",
        "or_adj": "walker + age + sex + factor(kl0)",
        "corstr": "exchangeable",
        "covariates": "age,sex,kl0",
    }


def test_lo_model_with_a_linear_kl_term():
    values = {
        "model.covariates": ["age", "kl0", "bmi"],
        "model.kl_covariate": "numeric",
        "model.corstr": "independence",
    }
    assert lo_model(values) == {
        "or_unadj": "walker",
        "or_adj": "walker + age + kl0 + bmi",
        "corstr": "independence",
        "covariates": "age,kl0,bmi",
    }


def test_check_walker_coding_agrees():
    answered = pl.DataFrame({"ID": [1, 2, 3], "walker": [True, False, True]})
    lo_people = pl.DataFrame({"ID": [1, 2, 4], "lo_walker": [True, False, False]})
    check_walker_coding(answered, lo_people)


def test_check_walker_coding_stops_on_a_null_lo_walker():
    # a null would make the comparison null, which the join filter drops: it must not be skipped
    answered = pl.DataFrame({"ID": [1, 2, 3], "walker": [True, False, True]})
    lo_people = pl.DataFrame({"ID": [1, 2, 3], "lo_walker": [True, None, None]})
    with pytest.raises(CohortError, match="2 Lo 2022 participants have no walker code"):
        check_walker_coding(answered, lo_people)
    with pytest.raises(CohortError, match="1 Lo 2022 participant has no walker code"):
        check_walker_coding(answered, lo_people.head(2))


def test_check_walker_coding_counts_differences():
    answered = pl.DataFrame({"ID": [1, 2, 3], "walker": [True, True, False]})
    lo_people = pl.DataFrame({"ID": [1, 2, 4], "lo_walker": [True, False, True]})
    with pytest.raises(CohortError, match="1 Lo 2022 participant coded differently") as err:
        check_walker_coding(answered, lo_people)
    assert "bias.lo2022_label" in str(err.value)


def test_lo_unanswered_with_device_counts_only_those_with_a_device_wave():
    answered = pl.DataFrame({"ID": [1, 2, 3, 5, 6]})
    combined = pl.DataFrame({"ID": [1, 2, 3, 4, 8]})  # a valid device wave
    lo_people = pl.DataFrame({"ID": [1, 2, 4, 5, 7, 8]})
    # 4 and 8 are in the Lo cohort with a device wave and did not answer; 7 did not answer either
    # but has no device wave, and 5 answered but has none
    assert lo_unanswered_with_device(answered, combined, lo_people) == 2
    assert lo_unanswered_with_device(answered, combined, lo_people.head(2)) == 0


def test_cohort_flow_shows_who_the_lo_cohort_loses():
    answered = pl.DataFrame({"ID": [1, 2, 3, 5, 6]})
    persons = pl.DataFrame({"ID": [1, 2, 3], "in_lo": [True, True, False]})
    lo_people = pl.DataFrame({"ID": [1, 2, 4, 5, 7]})  # 4 and 7 did not answer the item
    assert cohort_flow(answered, persons, lo_people).rows() == [
        ("answered_walking_item", 5),
        ("with_valid_device_wave", 3),
        ("lo2022_cohort", 5),
        ("lo2022_answered_item", 3),
        ("lo2022_answered_with_device", 2),
    ]


# Comparison grading: expected.toml, wv.without_ungradable_device_rows and compare.py.
def perfect_run(**changes):
    """Our metrics equal to every published value, except the changes."""
    ours = {
        metric: pub["count"] if isinstance(pub, dict) else pub
        for metric, pub in EXPECTED["default"].items()
    }
    return {**ours, **changes}


def verdicts(**changes):
    table = grade(EXPECTED["default"], perfect_run(**changes), EXPECTED["related"])
    return dict(table.select("metric", "verdict").iter_rows())


def test_a_perfect_run_replicates_every_row():
    assert set(verdicts().values()) == {"replicated"}


@pytest.mark.parametrize("wave", ["06", "08"])
@pytest.mark.parametrize("kind", ["mv", "bout"])
def test_mv_and_bout_mismatch_days_are_graded_exactly(wave, kind):
    metric = f"device.{wave}.{kind}_mismatch_days"
    # the replication tolerance, max(3%, 2), would pass a published 0 with up to 2 days off
    assert verdicts(**{metric: 1})[metric] == "drift"
    assert verdicts(**{metric: 0})[metric] == "replicated"


@pytest.mark.parametrize(("wave", "matched", "limit"), [("06", 13040, 65), ("08", 9399, 46)])
def test_wear_must_match_on_99_5_percent_of_matched_days(wave, matched, limit):
    metric = f"device.{wave}.wear_mismatch_days"
    assert 0.005 * matched - 1 < limit <= 0.005 * matched  # 65.2 and 46.995
    assert verdicts(**{metric: limit})[metric] == "replicated"
    assert verdicts(**{metric: limit + 1})[metric] == "drift"
    # a smaller run is held to 0.5% of its own matched days
    smaller = {f"device.{wave}.matched_days": 1000, metric: 6}
    assert verdicts(**smaller)[metric] == "drift"
    assert verdicts(**{**smaller, metric: 5})[metric] == "replicated"


@pytest.mark.parametrize(("wave", "released"), [("06", 1927), ("08", 1394)])
def test_valid_persons_must_be_within_one_of_the_release(wave, released):
    metric = f"device.{wave}.valid_persons"
    for ours, verdict in [
        (released - 2, "drift"),
        (released - 1, "replicated"),
        (released, "replicated"),
        (released + 1, "replicated"),
        (released + 2, "drift"),  # max(3%, 2) would have passed this
    ]:
        assert verdicts(**{metric: ours})[metric] == verdict, ours


@pytest.mark.parametrize(("wave", "released"), [("06", 13040), ("08", 9399)])
def test_every_release_person_day_must_be_matched(wave, released):
    metric = f"device.{wave}.matched_days"
    assert verdicts(**{metric: released})[metric] == "replicated"
    assert verdicts(**{metric: released - 1})[metric] == "drift"  # 3% would be hundreds of days
    assert verdicts(**{metric: released + 1})[metric] == "drift"


def test_device_rule_keys_are_the_ledgered_device_rules():
    assert set(DEVICE_RULE_KEYS) <= set(DEFAULTS)
    # every other device.* ledger key is not a processing rule: only the wave choice
    ledgered = {key for key in DEFAULTS if key.startswith("device.")}
    assert ledgered - set(DEVICE_RULE_KEYS) == {"device.wave_combination"}


def resolved_values(variant=None, **overrides):
    return LEDGER.resolve("walking_validation", variant, overrides).values


def test_device_rows_are_graded_under_the_ledger_device_rules():
    rows, changed, omitted = without_ungradable_device_rows(
        EXPECTED["default"], resolved_values(), DEFAULTS
    )
    assert rows == EXPECTED["default"] and changed == [] and omitted == []
    # Variants that do not touch the device rules still reproduce the release's counts.
    for variant in ("wave48", "wave72", "walker_any_bout", "walker_150min"):
        rows, changed, omitted = without_ungradable_device_rows(
            EXPECTED["default"], resolved_values(variant), DEFAULTS
        )
        assert len(rows) == len(EXPECTED["default"]) and not omitted, variant


def check_device_rows_are_omitted(values, rule):
    published = EXPECTED["default"]
    rows, changed, omitted = without_ungradable_device_rows(published, values, DEFAULTS)
    assert changed == [rule]
    assert omitted == [m for m in published if m.startswith("device.")] and len(omitted) == 10
    assert set(rows) == {"sample.validation.persons", "sample.lo_subset.persons"}


def test_device_rows_are_not_graded_under_the_nonwear60_variant():
    check_device_rows_are_omitted(resolved_values("nonwear60"), "device.nonwear_minutes")


@pytest.mark.parametrize("rule", DEVICE_RULE_KEYS)
def test_device_rows_are_not_graded_when_any_device_rule_changes(rule):
    # a changed value of the same type (every device rule is a number)
    check_device_rows_are_omitted(resolved_values(None, **{rule: DEFAULTS[rule] + 1}), rule)


def run_compare(tmp_path, monkeypatch, capsys, variant=None, **overrides):
    """compare.py on a results folder whose metrics equal the published values."""
    results = tmp_path / "results"
    results.mkdir()
    ours = perfect_run()
    for name, prefix in (("metrics_device.csv", "device."), ("metrics_cohort.csv", "sample.")):
        rows = [(m, float(v)) for m, v in ours.items() if m.startswith(prefix)]
        pl.DataFrame(rows, schema=["metric", "value"], orient="row").write_csv(results / name)
    resolved = LEDGER.resolve("walking_validation", variant, overrides).write(tmp_path / "res")
    monkeypatch.setenv("OAI_RESULTS_DIR", str(results))
    monkeypatch.setenv("OAI_ASSUMPTIONS", str(resolved))
    monkeypatch.chdir(ANALYSIS)
    runpy.run_path(str(ANALYSIS / "compare.py"), run_name="__main__")
    return pl.read_csv(results / "comparison.csv"), capsys.readouterr().out


def test_compare_grades_every_row_for_the_default_run(tmp_path, monkeypatch, capsys):
    table, out = run_compare(tmp_path, monkeypatch, capsys)
    assert table.height == len(EXPECTED["default"]) == 12
    assert (table["verdict"] == "replicated").all()
    assert "Not graded" not in out


def test_compare_omits_and_logs_device_rows_for_a_changed_device_rule(
    tmp_path, monkeypatch, capsys
):
    table, out = run_compare(tmp_path, monkeypatch, capsys, "nonwear60")
    assert table["metric"].to_list() == ["sample.validation.persons", "sample.lo_subset.persons"]
    assert "Not graded: 10 device.* rows" in out
    assert "device.06.valid_persons" in out and "device.nonwear_minutes" in out


# Settings that exist in both ledgers are copied, not shared: they must not drift apart.
LO2022 = load_assumptions(REPO / "analyses" / "lo2022_walking")


@pytest.mark.parametrize(
    ("ours", "lo2022"),
    [
        ("exposure.category_midpoints", "exposure.category_midpoints"),
        ("strata.reading_project", "cohort.reading_project"),
        ("strata.pain_baseline_item", "outcomes.pain_baseline_items"),
    ],
)
def test_duplicated_ledger_values_match_lo2022_walking(ours, lo2022):
    assert DEFAULTS[ours] == LO2022.items[lo2022].value


# Device step: participant-level measures stay in the frame folder, results are aggregates.
def minute_table(visit, days_per_person):
    """acceldatabymin rows: 650 light minutes a day; person 3 adds a 20-minute MV bout daily."""
    rows = []
    for person, days in days_per_person.items():
        for day in range(1, days + 1):
            for minute in range(1, 651):
                busy = person == 3 and minute <= 20
                rows.append((person, day, minute, 3000.0 if busy else 600.0))
    return pl.LazyFrame(
        rows,
        schema=["ID", f"V{visit}PAStudyDay", f"V{visit}MinSequence", f"V{visit}MINCnt"],
        orient="row",
    )


def release_by_day_table(visit, days_per_person, mv_off_by_one=False):
    rows = []
    for person, days in days_per_person.items():
        for day in range(1, days + 1):
            mv = 20.0 if person == 3 else 0.0
            if mv_off_by_one and (person, day) == (3, 1):
                mv += 1  # one released day disagrees with ours
            rows.append((person, day, 650 / 60, mv, mv))
    names = ["ID", "PAStudyDay", "WearHr", "DAYMVMinT", "DAYMVBoutMinT"]
    schema = [n if n == "ID" else f"V{visit}{n}" for n in names]
    return pl.DataFrame(rows, schema=schema, orient="row")


def test_device_step_keeps_person_rows_out_of_results(tmp_path, monkeypatch, capsys):
    persons = {"06": {1: 4, 2: 3, 3: 4}, "08": {1: 4, 2: 4, 3: 4}}  # wave 06: person 2 is short

    def read_table(name, visit, lazy=False):
        if name == "acceldatabymin":
            return minute_table(visit, persons[visit])
        if name == "acceldatabyday":
            return release_by_day_table(visit, persons[visit], mv_off_by_one=visit == "06")
        assert name == "accelerometry", name
        return pl.DataFrame(
            {"ID": list(persons[visit]), f"V{visit}ANVDAYS": list(persons[visit].values())}
        )

    monkeypatch.setattr(accel, "read_table", read_table)
    frames, results = tmp_path / "frames", tmp_path / "results"
    frames.mkdir()
    results.mkdir()
    resolved = LEDGER.resolve("walking_validation").write(tmp_path / "resolved")
    monkeypatch.setenv("OAI_FRAME_DIR", str(frames))
    monkeypatch.setenv("OAI_RESULTS_DIR", str(results))
    monkeypatch.setenv("OAI_ASSUMPTIONS", str(resolved))
    runpy.run_path(str(ANALYSIS / "device.py"), run_name="__main__")
    capsys.readouterr()

    # participant-level measures: only in the frame folder
    assert sorted(p.name for p in frames.iterdir()) == ["device.parquet"]
    device = pl.read_parquet(frames / "device.parquet")
    assert device.columns == [
        "ID", "valid_days", "wear_hr", "mv_min", "light_min", "counts_per_day", "bout_min",
        "purposeful_min", "bout_days_per_week", "valid", "wave",
    ]  # fmt: skip
    assert device.sort("wave", "ID").select("wave", "ID", "valid").rows() == [
        ("06", 1, True), ("06", 2, False), ("06", 3, True),
        ("08", 1, True), ("08", 2, True), ("08", 3, True),
    ]  # fmt: skip
    assert device.filter(pl.col("ID") == 3)["mv_min"].to_list() == [20.0, 20.0]

    # results: aggregate CSVs only, one row per wave, nothing keyed by person
    assert sorted(p.name for p in results.iterdir()) == [
        "device_reproduction.csv",
        "metrics_device.csv",
    ]
    reproduction = pl.read_csv(results / "device_reproduction.csv")
    assert reproduction.columns == [
        "wave", "release_days", "matched_days", "wear_mismatch_days", "mv_mismatch_days",
        "bout_mismatch_days", "valid_persons", "release_valid_persons",
    ]  # fmt: skip
    assert reproduction.rows() == [
        (6, 11, 11, 0, 1, 1, 2, 2),  # one disagreeing day: counted for MV and for bouts
        (8, 12, 12, 0, 0, 0, 3, 3),
    ]
    metrics = pl.read_csv(results / "metrics_device.csv")
    assert metrics.columns == ["metric", "value"]
    assert metrics["metric"].to_list() == [
        f"device.{wave}.{key}" for wave in ("06", "08") for key in reproduction.columns[1:]
    ]
    assert metrics.filter(pl.col("metric") == "device.06.mv_mismatch_days")["value"].to_list() == [
        1.0
    ]
