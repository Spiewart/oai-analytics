"""The walking_validation `cohort` step end to end on a small synthetic cohort.

The step reads release tables through oai.loader and the knee/PASE derivations; those are
replaced by small frames, so what is under test is the step itself: the flow, the linked Lo 2022
frame and results, and that a failed check leaves nothing written.
"""

import json
import runpy
import sys
from pathlib import Path

import polars as pl
import pytest

from oai import loader
from oai.assumptions import load_assumptions
from oai.config import get_settings
from oai.derive import knee, pase, walking

ANALYSIS = Path(__file__).resolve().parents[1] / "analyses" / "walking_validation"
sys.path.insert(0, str(ANALYSIS))

from wv import CohortError  # noqa: E402

LEDGER = load_assumptions(ANALYSIS)
LABEL = LEDGER.items["bias.lo2022_label"].value  # the replication run matching the default coding

# ID: (walk_item, amount codes) for the 96-month item. 4 and 7 did not answer.
ANSWERS = {
    1: (1, 2),
    2: (1, None),
    3: (0, None),
    4: (None, None),
    5: (1, 2),
    6: (0, None),
    7: (None, None),
}
DEVICE_IDS = [1, 2, 3, 4]  # valid device wave; 5 and 6 have none
LO_WALKER = {1: True, 2: False, 4: False, 5: True, 7: False}  # the replication's cohort


def answers_frame():
    rows = [(i, item, a, a, a) for i, (item, a) in ANSWERS.items()]
    return pl.DataFrame(
        rows,
        schema=["ID", "walk_item", "amount_years", "amount_months", "amount_times"],
        orient="row",
    )


def device_frame():
    rows = [(i, "06", True, 30.0, 100000.0, 200.0, 3.0) for i in DEVICE_IDS]
    rows += [(1, "08", True, 35.0, 110000.0, 210.0, 2.0)]  # person 1 has both waves
    measures = ["purposeful_min", "counts_per_day", "light_min", "bout_days_per_week"]
    return pl.DataFrame(rows, schema=["ID", "wave", "valid", *measures], orient="row")


def lo_knee_frame(**changes):
    ids = list(LO_WALKER)
    frame = pl.DataFrame(
        {
            "ID": ids,
            "SIDE": ["R"] * len(ids),
            "walker": [LO_WALKER[i] for i in ids],
            "age": [60.0] * len(ids),
            "sex": ["F"] * len(ids),
            "bmi": [27.0] * len(ids),
            "kl0": [2] * len(ids),
            "new_pain": [False, True, None, False, True],
            "kl_worse": [False, False, True, None, False],
            "jsn_worse": [None, False, False, True, False],
            "improved_pain": [True, None, False, False, None],
        }
    )
    return frame.with_columns(**changes) if changes else frame


@pytest.fixture
def cohort(tmp_path, monkeypatch, capsys):
    """Run the step; `run(...)` takes the replication's knee frame and comparison rows."""
    work, base = get_settings().work_dir, tmp_path / "results"
    frames, results = tmp_path / "frames", base / "walking_validation" / LABEL
    for d in (frames, results, base / "lo2022_walking" / LABEL, work / "lo2022_walking" / LABEL):
        d.mkdir(parents=True, exist_ok=True)
    device_frame().write_parquet(frames / "device.parquet")
    resolved = LEDGER.resolve("walking_validation").write(tmp_path / "resolved")

    def table(name, visit=None, **_):
        if name == "enrollees":
            return pl.DataFrame({"ID": list(ANSWERS), "P02SEX": ["2"] * len(ANSWERS)})
        assert name == "allclinical", name  # also read for the PASE scores (replaced below)
        return pl.DataFrame(
            {"ID": list(ANSWERS), "V00AGE": [60] * len(ANSWERS), "P01BMI": [27.0] * len(ANSWERS)}
        )

    monkeypatch.setattr(loader, "read_table", table)
    monkeypatch.setattr(walking, "walking_answers", lambda *a, **k: answers_frame())
    monkeypatch.setattr(
        pase, "score_pase", lambda df, visit, *a: pl.DataFrame({"ID": [1], "pase_walking": [5.0]})
    )
    monkeypatch.setattr(
        knee, "xray_readings", lambda *a, **k: pl.DataFrame({"ID": [1, 2], "KL": [2, 3]})
    )
    monkeypatch.setattr(
        knee,
        "frequent_knee_pain",
        lambda *a, **k: pl.DataFrame({"ID": [1, 2], "frequent_pain": [True, None]}),
    )
    monkeypatch.setenv("OAI_FRAME_DIR", str(frames))
    monkeypatch.setenv("OAI_RESULTS_DIR", str(results))
    monkeypatch.setenv("OAI_RESULTS_BASE", str(base))
    monkeypatch.setenv("OAI_ASSUMPTIONS", str(resolved))

    def run(knees=None, comparison=None):
        knees = lo_knee_frame() if knees is None else knees
        lo_work = work / "lo2022_walking" / LABEL
        knees.write_parquet(lo_work / "frame.parquet")
        coding = LEDGER.items["exposure.yes_without_amount_as"].value
        values = {
            "exposure.yes_without_amount_as": coding,
            "model.covariates": ["age", "sex", "kl0"],
            "model.kl_covariate": "factor",
            "model.corstr": "exchangeable",
        }
        (lo_work / "assumptions.resolved.json").write_text(
            json.dumps({"assumptions": {k: {"value": v} for k, v in values.items()}})
        )
        lo_results = base / "lo2022_walking" / LABEL
        if comparison is None:
            comparison = pl.DataFrame(
                {"metric": ["t2.new_pain.or_adj", "t1.age"], "ours": ["1", "2"]}
            )
        comparison.write_csv(lo_results / "comparison.csv")
        pl.DataFrame({"outcome": ["new_pain"]}).write_csv(lo_results / "table2.csv")
        runpy.run_path(str(ANALYSIS / "build_cohort.py"), run_name="__main__")
        capsys.readouterr()

    run.frames, run.results = frames, results
    return run


def written(folder: Path) -> list[str]:
    return sorted(p.name for p in folder.iterdir())


def test_cohort_step_writes_the_frames_results_and_flow(cohort):
    cohort()
    assert written(cohort.frames) == [
        "device.parquet",
        "frame.parquet",
        "lo_knees.parquet",
        "lo_model.json",
    ]
    assert written(cohort.results) == [
        "flow.csv", "lo2022_t2.csv", "lo2022_table2.csv", "metrics_cohort.csv",
    ]  # fmt: skip
    assert pl.read_csv(cohort.results / "lo2022_t2.csv")["metric"].to_list() == [
        "t2.new_pain.or_adj"
    ]
    # Lo cohort 1, 2, 4, 5, 7; of them 1, 2, 5 answered the item; of those 1, 2 have a device wave
    assert pl.read_csv(cohort.results / "flow.csv").rows() == [
        ("answered_walking_item", 5),
        ("with_valid_device_wave", 3),
        ("lo2022_cohort", 5),
        ("lo2022_answered_item", 3),
        ("lo2022_answered_with_device", 2),
    ]
    metrics = dict(pl.read_csv(cohort.results / "metrics_cohort.csv").iter_rows())
    assert metrics["sample.validation.persons"] == 3 and metrics["sample.lo_subset.persons"] == 2
    # of the Lo participants who did not answer (4 and 7) only 4 has a valid device wave
    assert metrics["flow.lo2022_unanswered_with_device"] == 1
    persons = pl.read_parquet(cohort.frames / "frame.parquet")
    assert persons["ID"].to_list() == [1, 2, 3] and persons["in_lo"].to_list() == [
        True,
        True,
        False,
    ]
    assert persons["n_waves"].to_list() == [2, 1, 1]


@pytest.mark.parametrize(
    ("what", "message"),
    [
        ("empty_table_2", "no t2.* rows"),
        ("missing_column", "lacks column kl0"),
        ("null_walker", "1 Lo 2022 participant has no walker code"),
    ],
)
def test_a_failed_check_leaves_no_partial_outputs(cohort, what, message):
    knees = lo_knee_frame()
    comparison = None
    if what == "empty_table_2":
        comparison = pl.DataFrame({"metric": ["t1.age"], "ours": ["61"]})
    elif what == "missing_column":
        knees = knees.drop("kl0")
    else:
        knees = knees.with_columns(
            walker=pl.when(pl.col("ID") == 2).then(None).otherwise(pl.col("walker"))
        )
    with pytest.raises(CohortError, match=message):
        cohort(knees, comparison)
    assert written(cohort.frames) == ["device.parquet"]  # the step's input only
    assert written(cohort.results) == []
