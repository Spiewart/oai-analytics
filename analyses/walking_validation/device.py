"""Step `device`: person-wave device measures from the minute files (spec 5).

Participant-level measures go to OAI_FRAME_DIR/device.parquet, never to results. The aggregate
agreement with the release's own by-day files goes to device_reproduction.csv and
metrics_device.csv.
"""

import os
from pathlib import Path

import polars as pl

from oai.assumptions import current
from oai.derive.accel import (
    DeviceRules,
    daily_summary,
    person_summary,
    read_minutes,
    release_valid_persons,
    reproduction,
)

A = current()
rules = DeviceRules(
    nonwear_minutes=A["device.nonwear_minutes"],
    interrupt_minutes=A["device.interrupt_minutes"],
    interrupt_ceiling=A["device.interrupt_ceiling"],
    valid_day_hours=A["device.valid_day_hours"],
    max_valid_days=A["device.max_valid_days"],
    min_valid_days=A["device.min_valid_days"],
    mv_cutpoint=A["device.mv_cutpoint"],
    light_floor=A["device.light_floor"],
    bout_window=A["device.bout_window"],
    bout_need=A["device.bout_need"],
    bout_stop_below=A["device.bout_stop_below"],
    purposeful_bout_minutes=A["device.purposeful_bout_minutes"],
)
frames, results = Path(os.environ["OAI_FRAME_DIR"]), Path(os.environ["OAI_RESULTS_DIR"])
waves, rows, metrics = [], [], []
for visit in ("06", "08"):
    daily = daily_summary(read_minutes(visit), rules)
    persons = person_summary(daily, rules).with_columns(pl.lit(visit).alias("wave"))
    waves.append(persons)
    check = reproduction(daily, visit, rules)
    check["valid_persons"] = persons.filter("valid").height
    check["release_valid_persons"] = release_valid_persons(visit, rules.min_valid_days)
    rows.append({"wave": visit, **check})
    metrics += [(f"device.{visit}.{key}", float(value)) for key, value in check.items()]
    print(f"wave {visit}: {check}")
pl.concat(waves).write_parquet(frames / "device.parquet")
pl.DataFrame(rows).write_csv(results / "device_reproduction.csv")
pl.DataFrame(metrics, schema=["metric", "value"], orient="row").write_csv(
    results / "metrics_device.csv"
)
