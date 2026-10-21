"""KOOS S2 x exam crepitus: combined-exposure coding and 2 x 2 counts."""

import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analyses" / "lo2018_crepitus"))

import dual  # noqa: E402


def coded(cut):
    df = pl.DataFrame(
        {"s2": [0, 2, 0, 4, None, 1], "exam": [0, 0, 1, 1, 1, 0]},
        schema={"s2": pl.Int64, "exam": pl.Int64},
    )
    return df.select(dual.combo(pl.col("s2"), pl.col("exam"), cut).alias("c"))["c"].to_list()


def test_combo_levels():
    assert coded(3) == ["neither", "neither", "exam_only", "both", None, "neither"]
    assert coded(1) == ["neither", "s2_only", "exam_only", "both", None, "s2_only"]


def test_dual_counts_cells_sum_to_frame():
    persons = pl.DataFrame(
        {
            "ID": [1, 2, 3, 4, 5],
            "crep0": [0, 3, 0, 4, None],
            "exam0": [0, 0, 1, 1, 1],
            "event": [False, True, True, True, False],
            "subgroup": ["roa_nosx", "roa_nosx", "noroa_sx", "noroa_nosx", "roa_nosx"],
            "cohort": ["Incidence"] * 4 + ["Progression"],
        }
    )
    out = dual.dual_counts("persons", persons, "crep0", "exam0", cuts=[1, 3])
    overall = out.filter((pl.col("grouping") == "all") & (pl.col("cut") == 3))
    assert overall["n"].sum() == 4  # person 5 has no S2
    assert overall["events"].sum() == 3
    assert dict(zip(overall["combo"], overall["n"], strict=True)) == {
        "neither": 1,
        "s2_only": 1,
        "exam_only": 1,
        "both": 1,
    }
    sub = out.filter((pl.col("grouping") == "subgroup") & (pl.col("cut") == 1))
    assert sub.filter(pl.col("group") == "roa_nosx")["n"].sum() == 2
    assert set(out["grouping"]) == {"all", "subgroup", "cohort"}
    assert set(out["frame"]) == {"persons"}
