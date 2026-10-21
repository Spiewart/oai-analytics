"""Step `cohort`: Lo 2018 flow, person-period observations, four-year frame and cohort metrics."""

import os
from pathlib import Path

from lo2018 import build_cohort, cohort_metrics, crepitus_frame, four_year, periods, soa_status

from oai.assumptions import current

A = current()
frames, results = Path(os.environ["OAI_FRAME_DIR"]), Path(os.environ["OAI_RESULTS_DIR"])
soa = soa_status(A)
cohort = build_cohort(A, soa)
crepitus = crepitus_frame(A)
frame, counts = periods(A, cohort, soa, crepitus)
persons = four_year(cohort, soa, crepitus)
frame.write_parquet(frames / "frame.parquet")
persons.write_parquet(frames / "persons.parquet")
cohort.flow.write_csv(results / "flow.csv")
cohort_metrics(cohort, frame, counts, persons).write_csv(results / "metrics_cohort.csv")
print(cohort.flow)
print(f"{frame.height} observations, {persons.height} persons [{A.label}]")
