"""steps_oa post hoc P1 checks on inline data (analyses/steps_oa/posthoc_p1.py)."""

import importlib.util
from pathlib import Path

import polars as pl

from oai.assumptions import load_assumptions

ANALYSIS = Path(__file__).resolve().parents[1] / "analyses" / "steps_oa"
_spec = importlib.util.spec_from_file_location("steps_oa_posthoc", ANALYSIS / "posthoc_p1.py")
H = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(H)


def test_injury_flag_baseline_or_any_interim_yes():
    raw = pl.DataFrame(
        {
            "ID": [1, 2, 3, 4, 5, 6],
            "SIDE": ["R"] * 6,
            "inj_ever": [1, 0, 0, None, None, 0],
            "surg_ever": [0, 1, 0, None, 0, 0],
            "inj12_01": [0, 0, 0, 0, 1, None],
            "inj12_03": [0, 0, 1, 0, None, None],
            "inj12_05": [0, 0, None, 0, None, None],
            "inj12_06": [0, None, 0, 0, None, None],
        }
    )
    out = H.injury_flags(raw).sort("ID")
    # 1: baseline yes; 2: no (a missed 48-month answer counts as none); 3: 24-month yes;
    # 4: blank baseline, no later yes -> unknown; 5: blank baseline, 12-month yes -> injured;
    # 6: baseline no, every interim visit missed -> no
    assert out["injury_48"].to_list() == [True, False, True, None, True, False]
    assert out["surgery_00"].to_list() == [False, True, False, None, False, False]


def test_read_flags_follow_the_periods_rows():
    horizon = pl.DataFrame(
        {
            "ID": [1, 1, 2, 3],
            "SIDE": ["R", "L", "R", "R"],
            "event": [True, False, None, None],
        }
    )
    periods = pl.DataFrame(
        {
            "ID": [1, 1, 1, 2],
            "SIDE": ["R", "L", "L", "R"],
            "end_visit": ["08", "08", "10", "10"],
            "span": [1, 1, 1, 2],
            "event": [True, False, False, False],
        }
    )
    out = H.read_flags(horizon, periods).sort("ID", "SIDE")
    # (1, L), (1, R), (2, R), (3, R)
    assert out["read_08"].to_list() == [True, True, False, False]
    assert out["read_10"].to_list() == [True, False, True, False]
    assert out["event_08"].to_list() == [False, True, False, False]
    assert out["any_read"].to_list() == [True, True, True, False]
    assert out["known"].to_list() == [True, True, False, False]


def test_read_share_by_band_in_band_order():
    flags = pl.DataFrame(
        {
            "steps_band": ["ge10000", "lt5000", "lt5000", None],
            "any_read": [True, True, False, False],
            "known": [True, True, False, False],
            "event": [False, True, None, None],
            "sex": [1, 2, 2, 2],
            "injury_48": [True, False, None, False],
            "kl48": [1.0, 0.0, 1.0, 0.0],
            "age": [60.0, 70.0, 72.0, 80.0],
            "bmi": [25.0, 30.0, 28.0, 27.0],
        }
    )
    out = H.read_share(flags, ["lt5000", "5000_7499", "ge10000"])
    assert out["steps_band"].to_list() == ["lt5000", "ge10000"]
    low = out.row(0, named=True)
    assert low["knees"] == 2
    assert low["share_read"] == 0.5
    assert low["incidence_known"] == 1.0
    assert low["share_injury"] == 0.0  # the unknown flag is left out of the share


def test_interim_pain_is_wide_by_visit():
    long = pl.DataFrame(
        {
            "ID": [1, 1, 2],
            "SIDE": ["R", "R", "R"],
            "visit": ["07", "09", "09"],
            "womac": [2.0, 3.0, 0.0],
            "freq_pain": [True, False, False],
        }
    )
    out = H.interim_pain(long).sort("ID")
    assert out["womac_07"].to_list() == [2.0, None]
    assert out["womac_09"].to_list() == [3.0, 0.0]
    assert out["freq_pain_07"].to_list() == [True, None]


def test_ledger_entries_match_the_code():
    A = load_assumptions(ANALYSIS).resolve("steps_oa", None, {})
    assert A["posthoc.injury"] == "baseline_or_interim"
    assert set(A["posthoc.weight_predictors"]) <= {
        "interim_womac",
        "interim_freq_pain",
        "interim_missed",
    }
    assert H.INTERIM_BEFORE == {"08": "07", "10": "09"}
