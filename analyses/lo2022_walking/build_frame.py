"""Step `cohort`: build the Lo 2022 knee frame and flow (Table 1/3 are added in Task 9)."""

import os
from pathlib import Path

from lo2022 import build

from oai.assumptions import current

A = current()
built = build(A)
frames, results = Path(os.environ["OAI_FRAME_DIR"]), Path(os.environ["OAI_RESULTS_DIR"])
built.knees.write_parquet(frames / "frame.parquet")
built.flow.write_csv(results / "flow.csv")
print(built.flow)
