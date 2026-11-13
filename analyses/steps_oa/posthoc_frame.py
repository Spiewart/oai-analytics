"""Step `posthoc_frame`: frames for the post hoc P1 checks (posthoc_p1.py), and the read share.

Frames (participant-level, OAI_FRAME_DIR only):
  posthoc_periods  periods_roa with injury_48 and surgery_00 (P1 rows)
  posthoc_read     horizon_roa (the P1 sample at 48 months) with read flags, injury and the
                   interim-visit knee pain that the reading weights use
Aggregate (OAI_RESULTS_DIR): posthoc_read_share.csv, by step band.
"""

import os
from pathlib import Path

import polars as pl
from persons import KEYS, band_labels
from posthoc_p1 import (
    INJURY_VISITS,
    INTERIM_BEFORE,
    injury_flags,
    interim_pain,
    read_flags,
    read_share,
)

from oai.assumptions import current
from oai.derive.knee import find_col
from oai.loader import read_table

A = current()
if A["posthoc.injury"] != "baseline_or_interim":
    raise SystemExit(f"posthoc.injury {A['posthoc.injury']!r} is not implemented")
frames, results = Path(os.environ["OAI_FRAME_DIR"]), Path(os.environ["OAI_RESULTS_DIR"])
SIDES = ("R", "L")


def per_side(visit: str, columns: dict[str, str]) -> pl.DataFrame:
    """One row per person and knee from `allclinical<visit>`; columns maps output -> template
    with {side}."""
    t = read_table("allclinical", visit)
    where = f"allclinical{visit}"
    return pl.concat(
        [
            t.select(
                pl.col(find_col(t, "ID")).cast(pl.Int64).alias("ID"),
                pl.lit(side).alias("SIDE"),
                *(
                    pl.col(find_col(t, tpl.format(side=side), where=where)).alias(name)
                    for name, tpl in columns.items()
                ),
            )
            for side in SIDES
        ]
    )


raw = per_side("00", {"inj_ever": "P01INJ{side}", "surg_ever": "P01KSURG{side}"})
for v in INJURY_VISITS:
    raw = raw.join(per_side(v, {f"inj12_{v}": f"V{v}INJ{{side}}12"}), on=KEYS, how="left")
injury = injury_flags(raw)

periods = pl.read_parquet(frames / "periods_roa.parquet")
horizon = pl.read_parquet(frames / "horizon_roa.parquet")
ends = sorted(periods["end_visit"].unique().to_list())
pain = pl.concat(
    per_side(v, {"womac": f"V{v}WOMKP{{side}}", "freq_pain": f"V{v}KP{{side}}12CV"}).select(
        *KEYS,
        pl.lit(v).alias("visit"),
        pl.col("womac").cast(pl.Float64),
        (pl.col("freq_pain") == 1).alias("freq_pain"),
    )
    for v in (INTERIM_BEFORE[e] for e in ends if e in INTERIM_BEFORE)
)
periods.join(injury, on=KEYS, how="left").write_parquet(frames / "posthoc_periods.parquet")
flags = read_flags(horizon, periods).join(injury, on=KEYS, how="left")
flags.join(interim_pain(pain), on=KEYS, how="left").write_parquet(frames / "posthoc_read.parquet")
read_share(flags, band_labels([int(e) for e in A["steps.bands"]])).write_csv(
    results / "posthoc_read_share.csv"
)
