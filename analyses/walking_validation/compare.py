"""Step `compare`: grade device reproduction and sample sizes against expected.toml."""

import os
import tomllib
from pathlib import Path

import polars as pl

from oai.assumptions import current, load_assumptions
from oai.replication import grade, select_section, summarize

A = current()
results = Path(os.environ["OAI_RESULTS_DIR"])
expected = tomllib.loads(Path("expected.toml").read_text())
variant_sets = {name: v.set for name, v in load_assumptions(Path.cwd()).variants.items()}
section = select_section(expected, A.variant, A.values, variant_sets)
ours: dict[str, float] = {}
for path in sorted(results.glob("metrics_*.csv")):
    for metric, value in pl.read_csv(path, null_values=["NA"]).iter_rows():
        if value is not None:
            ours[metric] = float(value)
statuses = {key: item.status for key, item in A.items.items()}
table = grade(expected[section], ours, expected.get("related", {}), statuses)
table.write_csv(results / "comparison.csv")
print(summarize(table, section=section, label=A.label))
