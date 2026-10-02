"""Step `compare`: grade device reproduction and sample sizes against expected.toml."""

import os
import tomllib
from pathlib import Path

import polars as pl
from wv import without_ungradable_device_rows

from oai.assumptions import current, load_assumptions
from oai.replication import grade, select_section, summarize

A = current()
results = Path(os.environ["OAI_RESULTS_DIR"])
expected = tomllib.loads(Path("expected.toml").read_text())
ledger = load_assumptions(Path.cwd())
variant_sets = {name: v.set for name, v in ledger.variants.items()}
section = select_section(expected, A.variant, A.values, variant_sets)
published, changed, omitted = without_ungradable_device_rows(
    expected[section], A.values, {key: item.value for key, item in ledger.items.items()}
)
ours: dict[str, float] = {}
for path in sorted(results.glob("metrics_*.csv")):
    for metric, value in pl.read_csv(path, null_values=["NA"]).iter_rows():
        if value is not None:
            ours[metric] = float(value)
statuses = {key: item.status for key, item in A.items.items()}
table = grade(published, ours, expected.get("related", {}), statuses)
table.write_csv(results / "comparison.csv")
print(summarize(table, section=section, label=A.label))
if omitted:
    print(
        f"\nNot graded: {len(omitted)} device.* rows ({', '.join(omitted)}), because this run "
        f"changes the device rules {', '.join(changed)}; they are the release's own counts"
    )
