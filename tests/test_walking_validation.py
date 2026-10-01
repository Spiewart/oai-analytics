import json
import sys
from pathlib import Path

import polars as pl
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "analyses" / "walking_validation"))

from wv import (  # noqa: E402
    CohortError,
    check_walker_coding,
    combine_waves,
    copy_lo_results,
    lo_model,
    person_outcomes,
    read_lo_frame,
    with_amount_level,
    with_device_walker,
)

MEASURE = {
    "purposeful_min": 0.0,
    "counts_per_day": 0.0,
    "light_min": 0.0,
    "bout_days_per_week": 0.0,
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
    with pytest.raises(ValueError, match="combination"):
        combine_waves(device, "both")


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
    with pytest.raises(CohortError, match="codes yes-without-amount as 'walker'") as err:
        read_lo_frame(tmp_path, "default", "non-walker")
    assert "`oai run lo2022_walking`" in str(err.value)
    assert "--variant default" not in str(err.value)
    frame, values = read_lo_frame(tmp_path, "default", "walker")
    assert frame.height == 1 and values["model.corstr"] == "exchangeable"


def test_copy_lo_results_names_a_command_the_cli_accepts(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    # the replication's default run takes no --variant (the CLI rejects --variant default)
    with pytest.raises(CohortError, match="comparison.csv is missing") as err:
        copy_lo_results(tmp_path / "lo2022_walking" / "default", "default", out)
    assert "`oai run lo2022_walking`" in str(err.value)
    assert "--variant default" not in str(err.value)
    with pytest.raises(CohortError) as err:
        copy_lo_results(tmp_path / "lo2022_walking" / "x", "walker_requires_amount", out)
    assert "`oai run lo2022_walking --variant walker_requires_amount`" in str(err.value)


def test_copy_lo_results(tmp_path):
    lo = tmp_path / "lo2022_walking" / "default"
    lo.mkdir(parents=True)
    pl.DataFrame({"metric": ["t2.new_pain.or_adj", "t1.age"], "ours": ["0.6", "61"]}).write_csv(
        lo / "comparison.csv"
    )
    pl.DataFrame({"outcome": ["new_pain"], "or": [0.6]}).write_csv(lo / "table2.csv")
    out = tmp_path / "out"
    out.mkdir()
    copy_lo_results(lo, "default", out)
    assert pl.read_csv(out / "lo2022_t2.csv")["metric"].to_list() == ["t2.new_pain.or_adj"]
    assert (out / "lo2022_table2.csv").read_text() == (lo / "table2.csv").read_text()


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


def test_check_walker_coding_agrees():
    answered = pl.DataFrame({"ID": [1, 2, 3], "walker": [True, False, True]})
    lo_people = pl.DataFrame({"ID": [1, 2, 4], "lo_walker": [True, False, False]})
    check_walker_coding(answered, lo_people)


def test_check_walker_coding_counts_differences():
    answered = pl.DataFrame({"ID": [1, 2, 3], "walker": [True, True, False]})
    lo_people = pl.DataFrame({"ID": [1, 2, 4], "lo_walker": [True, False, True]})
    with pytest.raises(CohortError, match="1 Lo 2022 participant"):
        check_walker_coding(answered, lo_people)
