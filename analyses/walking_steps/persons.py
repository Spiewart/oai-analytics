"""Step `persons`: person-wave device measures, count-based and step-based, at 48 and 72 months.

Participant-level, so they go to OAI_FRAME_DIR/device.parquet, never to results. The step
writes only an aggregate count of persons per wave to device_flow.csv.
"""

import os
from pathlib import Path

import polars as pl
from devices import device_rules, person_wave

from oai.assumptions import current
from oai.derive.accel import read_minutes

A = current()
rules = device_rules(A)
cadences = [int(c) for c in A["reference.step_cadences"]]
frames, results = Path(os.environ["OAI_FRAME_DIR"]), Path(os.environ["OAI_RESULTS_DIR"])
waves, flow = [], []
for visit in ("06", "08"):
    p = person_wave(
        read_minutes(visit, steps=True), rules, cadences, int(A["sample.min_step_days"])
    ).with_columns(pl.lit(visit).alias("wave"))
    waves.append(p)
    flow.append(
        {
            "wave": visit,
            "persons": p.height,
            "valid_persons": p.filter("valid").height,
            "valid_with_step_measures": p.filter(
                pl.col("valid") & pl.col("steps").is_not_null()
            ).height,
        }
    )
    print(f"wave {visit}: {flow[-1]}")
pl.concat(waves, how="diagonal").write_parquet(frames / "device.parquet")
pl.DataFrame(flow).write_csv(results / "device_flow.csv")
