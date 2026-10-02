"""Step `cohort`: the person-level validation frame, the Lo 2022 subset, and its knee frame."""

import json
import os
from functools import partial
from pathlib import Path

import polars as pl
from wv import (
    LO2022,
    MEASURES,
    OUTCOMES,
    check_walker_coding,
    combine_waves,
    copy_lo_results,
    lo_model,
    person_outcomes,
    read_lo_frame,
    with_amount_level,
    with_device_walker,
)

from oai.assumptions import current
from oai.config import get_settings
from oai.derive.knee import find_col, frequent_knee_pain, xray_readings
from oai.derive.pase import score_pase
from oai.derive.walking import walker_status, walking_answers, walking_sessions
from oai.loader import read_table

A = current()
settings = get_settings()
frames, results = Path(os.environ["OAI_FRAME_DIR"]), Path(os.environ["OAI_RESULTS_DIR"])
results_base = Path(os.environ["OAI_RESULTS_BASE"])


def select(df: pl.DataFrame, **columns: str) -> pl.DataFrame:
    col = partial(find_col, df)
    return df.select([pl.col(col(src)).alias(dst) for dst, src in columns.items()])


answered = (
    walking_answers()
    .with_columns(
        walker_status(
            yes_without_amount_as=A["exposure.yes_without_amount_as"], missing_as="exclude"
        ),
        walking_sessions(A["exposure.category_midpoints"]),
    )
    .filter(pl.col("walker").is_not_null())
)
pase = None
for visit in ("06", "08", "10"):
    scored = score_pase(read_table("allclinical", visit), visit, A["pase.walking_scoring"]).select(
        "ID", pl.col("pase_walking").alias(f"pase_walking_{visit}")
    )
    pase = scored if pase is None else pase.join(scored, on="ID", how="full", coalesce=True)

people = select(read_table("enrollees"), ID="ID", sex="P02SEX").join(
    select(read_table("allclinical", "00"), ID="ID", age="V00AGE", bmi="P01BMI"),
    on="ID",
    how="left",
)
kl = (
    xray_readings(["00"], project=A["strata.reading_project"])
    .group_by("ID")
    .agg(pl.col("KL").max().alias("kl_max0"))
)
pain = (
    frequent_knee_pain("00", A["strata.pain_baseline_item"])
    .group_by("ID")
    .agg(
        pl.when(pl.col("frequent_pain").is_not_null().any())
        .then(pl.col("frequent_pain").fill_null(False).any())
        .alias("pain0_any")
    )
)
combined = combine_waves(pl.read_parquet(frames / "device.parquet"), A["device.wave_combination"])
# device_walker from the combined measures; device_walker_06/_08 from each wave's own (PASE pairing)
for wave in (None, "06", "08"):
    combined = with_device_walker(
        combined,
        A["reference.walker_rule"],
        A["reference.min_bout_days_per_week"],
        A["reference.min_bout_minutes_per_week"],
        wave=wave,
    )

label = A["bias.lo2022_label"]
lo_knees, lo_values = read_lo_frame(settings.work_dir, label, A["exposure.yes_without_amount_as"])
lo_people = person_outcomes(lo_knees).with_columns(pl.lit(True).alias("in_lo"))
check_walker_coding(answered, lo_people)

persons = (
    answered.join(combined, on="ID", how="inner")
    .join(people, on="ID", how="left")
    .join(kl, on="ID", how="left")
    .join(pain, on="ID", how="left")
    .join(pase, on="ID", how="left")
    .join(lo_people, on="ID", how="left")
    .with_columns(
        pl.col("in_lo").fill_null(False),
        pl.col("age").cast(pl.Float64),
        pl.col("bmi").cast(pl.Float64),
    )
)
persons = with_amount_level(persons).sort("ID")
persons.write_parquet(frames / "frame.parquet")

covariates = list(lo_values["model.covariates"])
keep = ["ID", "SIDE", "walker", *dict.fromkeys(["age", "sex", "bmi", *covariates]), *OUTCOMES]
lo_knees.select([c for c in keep if c in lo_knees.columns]).write_parquet(
    frames / "lo_knees.parquet"
)
(frames / "lo_model.json").write_text(json.dumps(lo_model(lo_values), indent=2))

# The runner points OAI_RESULTS_DIR at this run's own folder; the replication's results are in
# its sibling analysis under the configured results folder, OAI_RESULTS_BASE.
copy_lo_results(results_base / LO2022 / label, label, results)

lo_subset = persons.filter("in_lo")
flow = pl.DataFrame(
    [
        {"step": "answered_walking_item", "persons": answered.height},
        {"step": "with_valid_device_wave", "persons": persons.height},
        {"step": "lo2022_cohort", "persons": lo_people.height},
        {"step": "lo2022_with_device", "persons": lo_subset.height},
    ]
)
flow.write_csv(results / "flow.csv")
metrics = [
    ("sample.validation.persons", persons.height),
    ("sample.validation.walkers", persons["walker"].sum()),
    ("sample.validation.device_walkers", persons["device_walker"].sum()),
    ("sample.validation.two_waves", (persons["n_waves"] == 2).sum()),
    ("sample.lo_subset.persons", lo_subset.height),
    ("sample.lo_subset.walkers", lo_subset["walker"].sum()),
    ("sample.lo_subset.device_walkers", lo_subset["device_walker"].sum()),
]
pl.DataFrame(
    [(m, float(v)) for m, v in metrics], schema=["metric", "value"], orient="row"
).write_csv(results / "metrics_cohort.csv")
print(flow)
print(f"measures: {', '.join(MEASURES)}; outcomes: {', '.join(OUTCOMES)}")
