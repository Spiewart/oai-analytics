"""Step `anchor`: the Mahmoudian 2023 cohort, its structural outcomes and count metrics."""

import os
from pathlib import Path

from mahmoudian import anchor_frame, anchor_metrics

from oai.assumptions import current

A = current()
frames, results = Path(os.environ["OAI_FRAME_DIR"]), Path(os.environ["OAI_RESULTS_DIR"])
frame = anchor_frame(A)
frame.write_parquet(frames / "anchor.parquet")
metrics = anchor_metrics(frame)
metrics.write_csv(results / "metrics_anchor.csv")
print(metrics)
