"""Step `compare`: grade this run's metrics against the paper (published.toml)."""

import os
import tomllib
from pathlib import Path

import polars as pl

from oai.assumptions import current, load_assumptions
from oai.replication import grade, select_section, summarize

A = current()
results = Path(os.environ["OAI_RESULTS_DIR"])
published = tomllib.loads(Path("published.toml").read_text())
variant_sets = {name: v.set for name, v in load_assumptions(Path.cwd()).variants.items()}
section = select_section(published, A.variant, A.values, variant_sets)
ours: dict[str, float] = {}
for path in sorted(results.glob("metrics_*.csv")):
    for metric, value in pl.read_csv(path, null_values=["NA"]).iter_rows():  # R writes NA
        if value is not None:
            ours[metric] = float(value)
statuses = {key: item.status for key, item in A.items.items()}
table = grade(published[section], ours, published.get("related", {}), statuses)
table.write_csv(results / "comparison.csv")
print(summarize(table, section=section, label=A.label))
