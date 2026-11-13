"""Steps against activity counts within a wear minute (the Northwestern group's Q1).

Pure functions over the analysis minutes from share.analysis_minutes(): count bins with each
bin's steps quartiles and step-band shares, and hexagonal cells of counts x steps. Outputs are
shares (or minutes in thousands), never raw minute totals.
"""

from __future__ import annotations

import numpy as np
import polars as pl
from share import band_labels


def count_bin_labels(edges: list[int]) -> list[str]:
    """'0-99', ..., '2020-5998', '5999+' for lower edges [0, 100, ..., 2020, 5999]."""
    return [f"{a}-{b - 1}" for a, b in zip(edges, edges[1:], strict=False)] + [f"{edges[-1]}+"]


def check_count_edges(edges: list[int], light_floor: float, mv_cutpoint: float) -> None:
    """Fail unless the edges start at 0, increase strictly and include both device cutpoints."""
    if edges[0] != 0:
        raise ValueError(f"relation.count_bin_edges must start at 0, not {edges[0]}")
    if any(b <= a for a, b in zip(edges, edges[1:], strict=False)):
        raise ValueError(f"relation.count_bin_edges must increase strictly: {edges}")
    for name, cut in (("device.light_floor", light_floor), ("device.mv_cutpoint", mv_cutpoint)):
        if cut not in edges:
            raise ValueError(f"relation.count_bin_edges {edges} lacks {name} = {cut}")


def intensity_of(
    edges: list[int], light_floor: float, mv_cutpoint: float, vigorous: int
) -> dict[str, str]:
    """Count bin label -> sedentary / light / moderate / vigorous, by each bin's lower edge."""

    def kind(lo: int) -> str:
        if lo < light_floor:
            return "sedentary"
        if lo < mv_cutpoint:
            return "light"
        return "moderate" if lo < vigorous else "vigorous"

    return dict(zip(count_bin_labels(edges), (kind(e) for e in edges), strict=True))


def with_bins(w: pl.DataFrame, count_edges: list[int], band_edges: list[int]) -> pl.DataFrame:
    """Add String columns count_bin (by counts) and band (by steps, as share.cadence_bands)."""
    return w.with_columns(
        pl.col("cnt")
        .cut([e - 0.5 for e in count_edges[1:]], labels=count_bin_labels(count_edges))
        .cast(pl.String)
        .alias("count_bin"),
        pl.col("steps")
        .cut([e - 0.5 for e in band_edges], labels=band_labels(band_edges))
        .cast(pl.String)
        .alias("band"),
    )


def bin_quantiles(w: pl.DataFrame, count_edges: list[int]) -> pl.DataFrame:
    """Per count bin (all bins, in order): minutes, share of minutes, steps quartiles."""
    labels = count_bin_labels(count_edges)
    binned = with_bins(w, count_edges, [1])
    per = binned.group_by("count_bin").agg(
        pl.len().alias("minutes"),
        pl.col("steps").quantile(0.25, "linear").alias("steps_q1"),
        pl.col("steps").quantile(0.5, "linear").alias("steps_median"),
        pl.col("steps").quantile(0.75, "linear").alias("steps_q3"),
    )
    return (
        pl.DataFrame({"count_bin": labels})
        .join(per, on="count_bin", how="left")
        .with_columns(pl.col("minutes").fill_null(0))
        .select(
            "count_bin",
            (pl.col("minutes") / 1000).round(1).alias("minutes_thousands"),
            (pl.col("minutes") / pl.col("minutes").sum()).alias("share_of_minutes"),
            "steps_q1",
            "steps_median",
            "steps_q3",
        )
    )


def band_shares(w: pl.DataFrame, count_edges: list[int], band_edges: list[int]) -> pl.DataFrame:
    """Full count_bin x band grid: share of each count bin's minutes in each step band."""
    grid = pl.DataFrame({"count_bin": count_bin_labels(count_edges)}).join(
        pl.DataFrame({"band": band_labels(band_edges)}), how="cross"
    )
    per = with_bins(w, count_edges, band_edges).group_by("count_bin", "band").len("minutes")
    return (
        grid.join(per, on=["count_bin", "band"], how="left")
        .with_columns(pl.col("minutes").fill_null(0))
        .with_columns(
            (pl.col("minutes") / pl.col("minutes").sum().over("count_bin"))
            .fill_nan(0.0)
            .fill_null(0.0)
            .alias("share")
        )
        .select("count_bin", "band", "share")
    )


def hex_cells(
    cnt: np.ndarray,
    steps: np.ndarray,
    quantile: float,
    gridsize: int,
    ymax: float = 200.0,
    min_count: int = 1,
) -> tuple[pl.DataFrame, dict[str, float]]:
    """Hexagonal cells of counts (x) by steps (y), on matplotlib's hexbin lattice.

    The x-axis stops at the `quantile` of `cnt`; minutes beyond it are left out of the cells and
    reported as share_beyond. Cells with fewer than `min_count` minutes are dropped, as the
    sibling hexbin in walking_validation drops small cells, and reported as share_suppressed.
    Each cell's share is its minutes over all minutes passed in, so the shares plus share_beyond
    plus share_suppressed sum to 1. hex_dx and hex_dy size the hexagons for drawing.
    """
    if len(steps) and float(np.max(steps)) > ymax:
        raise ValueError(f"steps above {ymax:.0f}/min fall outside the hexbin y-axis")
    xcap = float(np.quantile(cnt, quantile))
    keep = cnt <= xcap
    ny = round(gridsize / np.sqrt(3))
    sx = xcap / gridsize if xcap > 0 else 1.0
    sy = ymax / ny
    ix, iy = cnt[keep] / sx, steps[keep] / sy
    i1, j1 = np.round(ix), np.round(iy)  # lattice 1: (i * sx, j * sy)
    i2, j2 = np.floor(ix) + 0.5, np.floor(iy) + 0.5  # lattice 2: offset by half a cell
    first = (ix - i1) ** 2 + 3 * (iy - j1) ** 2 <= (ix - i2) ** 2 + 3 * (iy - j2) ** 2
    cells = (
        pl.DataFrame({"x": np.where(first, i1, i2) * sx, "y": np.where(first, j1, j2) * sy})
        .group_by("x", "y")
        .len("minutes")
        .with_columns((pl.col("minutes") / len(cnt)).alias("share"))
    )
    small = cells.filter(pl.col("minutes") < min_count)["share"].sum()
    cells = cells.filter(pl.col("minutes") >= min_count).select("x", "y", "share").sort("x", "y")
    meta = {
        "xcap": xcap,
        "share_beyond": float((~keep).sum() / len(cnt)),
        "share_suppressed": float(small),
        "hex_dx": sx,
        "hex_dy": sy,
    }
    return cells, meta
