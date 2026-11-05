import polars as pl
import pytest

from oai.derive.construct import MEASURES, kl_group, visit_measures, worse_knee
from oai.derive.pase import pase_rebuilt


def clinical(rows: int = 1, **overrides) -> pl.DataFrame:
    """A V00 AllClinical stub. Items 2-6 all 'never' except where overridden."""
    base = {"ID": list(range(1, rows + 1))}
    for item in range(2, 7):
        base[f"V00PASE{item}"] = [0] * rows
        base[f"V00PASE{item}HR"] = [None] * rows
    for k in range(1, 7):
        base[f"V00HOUACT{k}"] = [0] * rows
    base.update(
        {
            "V00PASE": [100] * rows,
            "V00PASE1": [3] * rows,
            "V00PASE1HR": [4] * rows,
            "V00WORK7": [1] * rows,
            "V00WORKAMT": [2] * rows,
            "V00WKHR7CV": [14] * rows,
        }
    )
    base.update({k: v for k, v in overrides.items()})
    return pl.DataFrame(base, schema_overrides={c: pl.Int64 for c in base if c != "ID"})


def test_pase_rebuilt_counts_work_only_when_not_mainly_sitting():
    df = clinical(2, V00WORKAMT=[1, 2], V00WKHR7CV=[14, 14])
    out = pase_rebuilt(df, "00").sort("ID")["pase_rebuilt_00"].to_list()
    assert out[1] - out[0] == pytest.approx(21 * 14 / 7)


def test_pase_rebuilt_is_null_when_a_component_is_unanswered():
    df = clinical(2, V00PASE3=[0, None])
    out = pase_rebuilt(df, "00").sort("ID")["pase_rebuilt_00"].to_list()
    assert out[0] is not None and out[1] is None


def test_pase_rebuilt_weights_the_items():
    df = clinical(1, V00PASE2=[3], V00PASE2HR=[4], V00HOUACT3=[1], V00WORK7=[0], V00WORKAMT=[None])
    # walking 20 * 6/7 * 5, repairs 30
    assert pase_rebuilt(df, "00")["pase_rebuilt_00"][0] == pytest.approx(20 * 6 / 7 * 5 + 30)


def test_worse_knee_uses_the_available_knee():
    df = pl.DataFrame(
        {"r": [3, None, None], "l": [1, 2, None]}, schema=dict.fromkeys("rl", pl.Int64)
    )
    got = df.select(worse_knee(pl.col("r"), pl.col("l")))["r"].to_list()
    assert got == [3, 2, None]
    low = (
        pl.DataFrame({"r": [3], "l": [1]})
        .select(worse_knee(pl.col("r"), pl.col("l"), higher_is_worse=False))["r"]
        .to_list()
    )
    assert low == [1]


def test_kl_group_groups_the_worse_knee_grade():
    df = pl.DataFrame({"kl": [0.0, 1.0, 2.0, 3.0, 4.0, None]})
    groups = {"0-1": [0, 1], "2-3": [2, 3], "4": [4]}
    assert df.select(kl_group(pl.col("kl"), groups).alias("g"))["g"].to_list() == [
        "0-1",
        "0-1",
        "2-3",
        "2-3",
        "4",
        None,
    ]


def test_visit_measures_skips_measures_the_visit_lacks():
    df = clinical(2)
    out = visit_measures(df, "00", MEASURES)
    assert out.columns == ["ID", "visit", "measure", "value"]
    assert out.schema["value"] == pl.Float64
    assert "koos_sport" not in out["measure"].unique().to_list()
    assert "total" in out["measure"].unique().to_list()
    with_koos = clinical(2, V00KOOSFSR=[50, 60])
    assert "koos_sport" in visit_measures(with_koos, "00", MEASURES)["measure"].to_list()


def test_visit_measures_leaves_out_pace_at_visit_13():
    df = clinical(2).rename({c: c.replace("V00", "V13") for c in clinical().columns if c != "ID"})
    df = df.with_columns(pl.Series("V1320MPACE", [1.0, 1.1]))
    assert "pace_20m" not in visit_measures(df, "13", MEASURES)["measure"].to_list()


def test_sitting_long_is_false_for_people_who_never_sit():
    df = clinical(3, V00PASE1=[0, 3, 3], V00PASE1HR=[None, 4, 2])
    out = visit_measures(df, "00", MEASURES).filter(pl.col("measure") == "sitting_long").sort("ID")
    assert out["value"].to_list() == [0.0, 1.0, 0.0]


def test_work_active_is_unknown_when_the_amount_is_unknown():
    df = clinical(4, V00WORK7=[0, 1, 1, 1], V00WORKAMT=[None, 1, 2, None])
    out = visit_measures(df, "00", MEASURES).filter(pl.col("measure") == "work_active").sort("ID")
    assert out["value"].to_list() == [0.0, 0.0, 1.0, None]


def test_walking_measures_follow_the_item_two_scoring():
    df = clinical(
        4,
        V00PASE2=[0, 1, 3, 3],
        V00PASE2HR=[None, 1, 4, None],
    )
    got = visit_measures(df, "00", MEASURES, hours_threshold=5.0)
    any_ = got.filter(pl.col("measure") == "walking_any").sort("ID")["value"].to_list()
    five = got.filter(pl.col("measure") == "hours_5plus").sort("ID")["value"].to_list()
    assert any_ == [0.0, 1.0, 1.0, 1.0]
    # 3 days code 3 = 6 days x 5 h = 30 h; code 1 x 0.5 h = 0.75 h; unanswered hours stay unknown
    assert five == [0.0, 0.0, 1.0, None]


def test_total_minus_walking_is_the_released_total_less_item_two():
    df = clinical(1, V00PASE2=[3], V00PASE2HR=[2], V00PASE=[100])
    out = visit_measures(df, "00", MEASURES).filter(pl.col("measure") == "total_minus_walking")
    assert out["value"][0] == pytest.approx(100 - 20 * 6 / 7 * 1.5)


def test_item_measures_treat_other_codes_as_unanswered():
    df = clinical(
        3,
        V00PASE1=[None, 3, 3],
        V00PASE1HR=[4, 4, 4],
        V00PASE3=[88, 0, 2],
        V00HOUACT1=[88, 0, 1],
    )
    got = visit_measures(df, "00", MEASURES)

    def values(name):
        return got.filter(pl.col("measure") == name).sort("ID")["value"].to_list()

    assert values("sitting_long") == [None, 1.0, 1.0]
    assert values("light_sport") == [None, 0.0, 1.0]
    assert values("light_housework") == [None, 0.0, 1.0]
