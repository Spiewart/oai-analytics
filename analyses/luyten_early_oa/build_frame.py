"""Step `cohort`: knees with the Luyten criteria and outcomes, flow, and cohort metrics."""

import os
from pathlib import Path

from luyten import all_knees, cohort_metrics, flow, knee_frame

from oai.assumptions import current

A = current()
frames_dir, results = Path(os.environ["OAI_FRAME_DIR"]), Path(os.environ["OAI_RESULTS_DIR"])
every = all_knees(A)
knees = knee_frame(A, every)
knees.write_parquet(frames_dir / "knees.parquet")
steps = flow(A, every)
steps.write_csv(results / "flow.csv")
metrics = cohort_metrics(knees)
metrics.write_csv(results / "metrics_cohort.csv")
print(steps)
m = dict(metrics.iter_rows())
print(
    f"early OA: {m['g.knees']:.0f} of {m['g.kl01']:.0f} KL 0-1 knees ({m['g.share']:.1%}); "
    f"KL 0-1 + KOOS: {m['g.kl01_koos']:.0f} [{A.label}]"
)
