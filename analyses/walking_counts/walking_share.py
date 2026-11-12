"""Step `share`: how much of the GT1M activity counts fall in walking minutes, at 48 and 72 months.

Reads the release's minute counts with the non-public per-minute steps (oai.steps). Writes
aggregates only: flow.csv, walking_share.csv, cadence_bands.csv and WALKING_SHARE.md.
"""

import os
from pathlib import Path

import polars as pl
from share import analysis_minutes, cadence_bands, shares

from oai.assumptions import current
from oai.derive.accel import DeviceRules, read_minutes

A = current()
if A["steps.day_rule"] != "complete":  # the only rule oai.derive.accel implements
    raise ValueError(f"steps.day_rule {A['steps.day_rule']!r} is not implemented")
rules = DeviceRules(
    **{
        key.removeprefix("device."): A[key]
        for key in (
            "device.nonwear_minutes",
            "device.interrupt_minutes",
            "device.interrupt_ceiling",
            "device.valid_day_hours",
            "device.max_valid_days",
            "device.min_valid_days",
            "device.mv_cutpoint",
            "device.light_floor",
            "device.bout_window",
            "device.bout_need",
            "device.bout_stop_below",
            "device.purposeful_bout_minutes",
        )
    }
)
cadences = [int(c) for c in A["walking.cadences"]]
primary = int(A["walking.primary_cadence"])
if primary not in cadences:
    raise ValueError(f"walking.primary_cadence {primary} is not in walking.cadences")
results = Path(os.environ["OAI_RESULTS_DIR"])

flows, share_frames, band_frames = [], [], []
for visit in ("06", "08"):
    w, flow = analysis_minutes(
        read_minutes(visit, steps=True), rules, int(A["sample.min_step_days"])
    )
    flows.append({"visit": visit, **flow})
    share_frames.append(shares(w, cadences).with_columns(pl.lit(visit).alias("visit")))
    bands = cadence_bands(w, [int(e) for e in A["walking.band_edges"]], rules.mv_cutpoint)
    band_frames.append(bands.with_columns(pl.lit(visit).alias("visit")))
    print(f"visit {visit}: {flow}")

flow = pl.DataFrame(flows)
share_table = pl.concat(share_frames).select("visit", pl.exclude("visit"))
band_table = pl.concat(band_frames).select("visit", pl.exclude("visit"))
flow.write_csv(results / "flow.csv")
share_table.write_csv(results / "walking_share.csv")
band_table.write_csv(results / "cadence_bands.csv")


def pct(x: float | None) -> str:
    return "" if x is None else f"{100 * x:.0f}%"


def md(df: pl.DataFrame) -> str:
    head = "| " + " | ".join(df.columns) + " |\n|" + "---|" * len(df.columns) + "\n"
    return head + "".join("| " + " | ".join(str(v) for v in r) + " |\n" for r in df.iter_rows())


LABELS = {
    "wear_counts_in_walking": "Wear counts in walking minutes",
    "mv_minutes_walking": "MV minutes that are walking",
    "mv_bout_minutes_walking": "MV-bout minutes that are walking",
    "light_minutes_walking": "Light minutes that are walking",
    "wear_minutes_walking": "Wear minutes that are walking",
    "walking_minutes_reaching_mv": "Walking minutes that reach MV",
}
pooled = (
    share_table.with_columns(pl.col("pooled").map_elements(pct, return_dtype=pl.String))
    .pivot(on="cadence_ge", index=["measure", "visit"], values="pooled")
    .with_columns(pl.col("measure").replace_strict(LABELS))
)
pooled.columns = ["Measure", "Visit", *(f">= {c}" for c in cadences)]
head = share_table.filter(pl.col("cadence_ge") == primary)


def headline(measure: str) -> str:
    vals = head.filter(pl.col("measure") == measure).sort("visit")["pooled"].to_list()
    return " and ".join(pct(v) for v in vals)


bands_md = band_table.select(
    "visit",
    pl.col("band").alias("steps/min"),
    pl.col("share_of_minutes").map_elements(pct, return_dtype=pl.String).alias("wear minutes"),
    pl.col("share_of_counts").map_elements(pct, return_dtype=pl.String).alias("counts"),
    pl.col("share_minutes_mv").map_elements(pct, return_dtype=pl.String).alias("minutes at MV"),
    pl.col("median_counts_per_min").round(0).cast(pl.Int64).alias("median counts/min"),
)
text = f"""# How much of the activity counts is walking [{A.label}]

A walking minute is a wear minute with at least the given steps per minute. Shares are pooled
over every analysis minute; walking_share.csv also has per-person quartiles.

At >= {primary} steps/min (48 and 72 months): {headline("wear_counts_in_walking")} of wear counts,
{headline("mv_minutes_walking")} of MV minutes and {headline("mv_bout_minutes_walking")} of
MV-bout minutes fall in walking minutes; {headline("walking_minutes_reaching_mv")} of walking
minutes reach the MV cut-point ({rules.mv_cutpoint} counts/min).

## Sample

{md(flow)}
## Pooled shares by walking threshold (steps/min)

{md(pooled.sort(["Measure", "Visit"]))}
## Cadence bands

{md(bands_md)}"""
(results / "WALKING_SHARE.md").write_text(text)
