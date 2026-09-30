"""Step `cohort`: Lo 2022 knee frame, flow, Table 1 and Table 3 (with metrics for grading)."""

import os
from pathlib import Path

import polars as pl
from lo2022 import build, flow_metrics, table1, table3

from oai.assumptions import current

A = current()
built = build(A)
frames, results = Path(os.environ["OAI_FRAME_DIR"]), Path(os.environ["OAI_RESULTS_DIR"])
built.knees.write_parquet(frames / "frame.parquet")
built.flow.write_csv(results / "flow.csv")
t1, t3 = table1(built), table3(built)
t1.write_csv(results / "table1.csv")
t3.write_csv(results / "table3.csv")
pl.concat([flow_metrics(built), t1, t3]).write_csv(results / "metrics_cohort.csv")
print(built.flow)
print(f"{built.knees.height} knees, {built.knees['ID'].n_unique()} participants [{A.label}]")
