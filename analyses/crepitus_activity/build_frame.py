"""Step `cohort`: person and knee frames (OAI_FRAME_DIR), aggregate flow and descriptives."""

import os
from pathlib import Path

import polars as pl
from activity import (
    covariates_48,
    crepitus_counts,
    crepitus_knees,
    exam120_knees,
    flow_and_descriptives,
    person_frame,
)

from oai.assumptions import current
from oai.derive.accel import read_minutes
from oai.derive.devices import device_rules, person_wave

# person_wave also builds step-bout measures at these cadences; this analysis does not use them
UNUSED_BOUT_CADENCES = [100]

A = current()
frames, results = Path(os.environ["OAI_FRAME_DIR"]), Path(os.environ["OAI_RESULTS_DIR"])
rules = device_rules(A)
device = pl.concat(
    [
        person_wave(
            read_minutes(visit, steps=True),
            rules,
            UNUSED_BOUT_CADENCES,
            int(A["sample.min_step_days"]),
        )
        .select("ID", "valid", "steps", "mv_min", "light_min", "wear_hr")
        .with_columns(pl.col("ID").cast(pl.Int64), pl.lit(visit).alias("wave"))
        for visit in ("06", "08")
    ]
)
knees = crepitus_knees().with_columns(pl.col("ID").cast(pl.Int64))
persons = person_frame(device, crepitus_counts(knees, A), covariates_48(), A)
knees120 = exam120_knees(knees, persons)
persons.write_parquet(frames / "persons.parquet")
knees120.write_parquet(frames / "knees120.parquet")
flow, descriptives = flow_and_descriptives(persons, knees120, A)
flow.write_csv(results / "flow.csv")
descriptives.write_csv(results / "descriptives.csv")
print(flow)
