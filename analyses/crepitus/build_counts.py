"""Step `counts`: crepitus availability, retention and at-risk / event counts by cohort."""

import os
from pathlib import Path

import polars as pl
from crepitus import (
    ALL,
    availability,
    event_table,
    knee_table,
    measures_long,
    paired_exam_s2,
    participants,
    retention,
    s2_distribution,
)

from oai.assumptions import current

A = current()
results = Path(os.environ["OAI_RESULTS_DIR"])
threshold = A["measures.s2_positive_threshold"]

people = participants()
long, coverage = measures_long()

avail = availability(long, people, coverage, threshold)
avail.write_csv(results / "availability.csv")
s2_distribution(long, people).write_csv(results / "s2_distribution.csv")
paired_exam_s2(long, people, threshold).write_csv(results / "paired_exam_s2.csv")
retention(long, people).write_csv(results / "retention.csv")

events = event_table(knee_table(A), threshold)
events.write_csv(results / "at_risk_events.csv")


def md_table(df: pl.DataFrame) -> str:
    head = "| " + " | ".join(df.columns) + " |\n|" + "---|" * len(df.columns) + "\n"
    rows = "".join(
        "| " + " | ".join("" if v is None else str(v) for v in r) + " |\n" for r in df.iter_rows()
    )
    return head + rows


collected = avail.filter(pl.col("collected") & (pl.col("cohort") == ALL))
lines = [
    f"# Crepitus sample sizes [{A.label}]\n",
    f"KOOS S2 counted as present at response >= {threshold}. Cohort = Enrollees V00COHORT. "
    "`persons` has a non-missing value in at least one knee; `knees` counts non-missing knees.\n",
]
for measure in collected["measure"].unique(maintain_order=True):
    wide = (
        avail.filter((pl.col("measure") == measure) & pl.col("collected"))
        .select("visit", "month", "contact", "cohort", "persons", "knees", "knees_positive")
        .pivot(
            on="cohort",
            index=["visit", "month", "contact"],
            values=["persons", "knees", "knees_positive"],
        )
        .sort("visit")
    )
    lines += [f"## {measure}\n", md_table(wide), "\n"]
lines += ["## Retention (persons)\n", md_table(retention(long, people)), "\n"]
lines += [
    "## Events among at-risk knees (exposure not required)\n",
    md_table(
        events.filter(pl.col("exposure").str.starts_with("(")).select(
            "outcome",
            "cohort",
            "persons_at_risk",
            "knees_at_risk",
            "knees_ascertained",
            "events_total",
        )
    ),
]
(results / "SAMPLE_SIZES.md").write_text("\n".join(lines))
print(f"wrote {results}/SAMPLE_SIZES.md [{A.label}]")
