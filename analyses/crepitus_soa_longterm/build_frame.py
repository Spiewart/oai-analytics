"""Step `cohort`: frames for S2 and exam crepitus to the horizon, cohort metrics and coverage."""

import os
from pathlib import Path

from longterm import build, cohort_metrics, coverage, frames_for

from oai.assumptions import current

A = current()
frames_dir, results = Path(os.environ["OAI_FRAME_DIR"]), Path(os.environ["OAI_RESULTS_DIR"])
base = build(A)
frames = {
    "s2": frames_for(A, "koos_s2", base),
    "exam": frames_for(A, "exam_crepitus", base),
}
for short, (periods, hazard, horizon, _) in frames.items():
    periods.write_parquet(frames_dir / f"{short}_periods.parquet")
    hazard.write_parquet(frames_dir / f"{short}_hazard.parquet")
    horizon.write_parquet(frames_dir / f"{short}_horizon.parquet")
base.cohort.flow.write_csv(results / "flow.csv")
cohort_metrics(base, frames).write_csv(results / "metrics_cohort.csv")
coverage(A, base).write_csv(results / "coverage.csv")
print(base.cohort.flow)
for short, (periods, _hazard, horizon, _) in frames.items():
    print(
        f"{short}: {periods.height} periods ({periods['event'].sum()} cases), "
        f"{horizon.height} people to the horizon ({horizon['event'].sum()} cases) [{A.label}]"
    )
