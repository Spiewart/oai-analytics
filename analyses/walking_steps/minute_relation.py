"""Step `relation`: per-minute steps against activity counts at 48 and 72 months (Q1).

Uses the same analysis minutes as step `share`. Writes aggregates only: relation_hex.csv
(hexagonal cells of counts x steps), relation_hex_meta.csv (axis cut-off, share beyond it and
hexagon size), relation_bins.csv (steps quartiles by count bin) and relation_bands.csv (share of
each step band within each count bin).
"""

import os
from pathlib import Path

import polars as pl
from devices import device_rules
from relation import (
    band_shares,
    bin_quantiles,
    check_count_edges,
    count_bin_labels,
    hex_cells,
    intensity_of,
)
from share import analysis_minutes

from oai.assumptions import current
from oai.derive.accel import read_minutes

A = current()
if A["steps.day_rule"] != "complete":  # the only rule oai.derive.accel implements
    raise ValueError(f"steps.day_rule {A['steps.day_rule']!r} is not implemented")
rules = device_rules(A)
count_edges = [int(e) for e in A["relation.count_bin_edges"]]
check_count_edges(count_edges, rules.light_floor, rules.mv_cutpoint)
band_edges = [int(e) for e in A["walking.band_edges"]]
intensity = intensity_of(count_edges, rules.light_floor, rules.mv_cutpoint, count_edges[-1])
results = Path(os.environ["OAI_RESULTS_DIR"])

hexes, metas, bins, bands = [], [], [], []
for visit in ("06", "08"):
    w, _ = analysis_minutes(read_minutes(visit, steps=True), rules, int(A["sample.min_step_days"]))
    if w["steps"].null_count():
        raise ValueError(f"visit {visit}: analysis minutes have null steps")
    tag = pl.lit(visit).alias("visit")
    cells, meta = hex_cells(
        w["cnt"].to_numpy(),
        w["steps"].to_numpy(),
        w["ID"].to_numpy(),
        float(A["relation.hex_x_quantile"]),
        int(A["relation.hex_gridsize"]),
        min_people=int(A["relation.hex_min_people"]),
    )
    hexes.append(cells.with_columns(tag))
    metas.append({"visit": visit, **meta})
    bins.append(bin_quantiles(w, count_edges).with_columns(tag))
    bands.append(band_shares(w, count_edges, band_edges).with_columns(tag))
    print(f"visit {visit}: {w.height} minutes, x cut-off {meta['xcap']:.0f} counts/min")


def tagged(frames: list[pl.DataFrame]) -> pl.DataFrame:
    df = pl.concat(frames)
    if "count_bin" in df.columns:
        df = df.with_columns(
            pl.col("count_bin").replace_strict(intensity).alias("intensity")
        ).select("visit", "count_bin", "intensity", pl.exclude("visit", "count_bin", "intensity"))
    else:
        df = df.select("visit", pl.exclude("visit"))
    return df


tagged(hexes).write_csv(results / "relation_hex.csv")
pl.DataFrame(metas).write_csv(results / "relation_hex_meta.csv")
tagged(bins).write_csv(results / "relation_bins.csv")
tagged(bands).write_csv(results / "relation_bands.csv")
assert count_bin_labels(count_edges) == bins[0]["count_bin"].to_list()
