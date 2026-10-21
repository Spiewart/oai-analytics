"""Step `cohort`: the Lo 2018 cohort with exam-crepitus person-periods and four-year frame."""

import os
from pathlib import Path

from exam_soa import exposure_metrics, require_for

from oai.assumptions import current
from oai.derive.incident_soa import build_cohort, crepitus_frame, four_year, periods, soa_status

A = current()
frames, results = Path(os.environ["OAI_FRAME_DIR"]), Path(os.environ["OAI_RESULTS_DIR"])
require = require_for(A)
soa = soa_status(A)
cohort = build_cohort(A, soa)
crepitus = crepitus_frame(A)
frame, counts = periods(A, cohort, soa, crepitus, require=require)
persons = four_year(cohort, soa, crepitus, require=require)
frame.write_parquet(frames / "frame.parquet")
persons.write_parquet(frames / "persons.parquet")
cohort.flow.write_csv(results / "flow.csv")
exposure_metrics(cohort, frame, counts, persons).write_csv(results / "metrics_cohort.csv")
print(cohort.flow)
print(f"{frame.height} observations, {persons.height} persons, require={require} [{A.label}]")
