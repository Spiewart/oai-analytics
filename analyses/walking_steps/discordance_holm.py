"""Step `discordance_holm`: stage 2's Holm adjustment, small-cell rule and DISCORDANCE.md.

Reads the raw model rows that discordance_trends.R wrote to OAI_FRAME_DIR. Each measure's group x
visit p (`p_interaction`) is Holm-adjusted across measures, one family per comparison and
replacement rule (`censored`); a measure whose model failed, and every row that did not converge,
keeps a null. A visit whose contrast rests on fewer than [egress] min_cell people in either "Yes"
group has its estimate nulled. Writes discordance_trends.csv to results, and DISCORDANCE.md (this
step is its only writer) with stage 1 (discordance_screen.csv) and stage 2 together.
"""

import os
from pathlib import Path

import discordance as d
import polars as pl

from oai.assumptions import current
from oai.config import load_settings

A = current()
frames, results = Path(os.environ["OAI_FRAME_DIR"]), Path(os.environ["OAI_RESULTS_DIR"])
min_cell = int(load_settings().project["egress"]["min_cell"])
if A["discordance.multiplicity"] != "holm":
    raise ValueError(f"discordance.multiplicity = {A['discordance.multiplicity']!r}; only 'holm'")
covariates = list(A["discordance.trend_covariates"])
visits = list(A["discordance.trend_visits"])
alpha = float(A["discordance.trend_alpha"])
FAMILY = ["comparison", "censored"]

raw = pl.read_csv(
    frames / "discordance_trends_raw.csv",
    schema_overrides={"visit": pl.String, "fit_note": pl.String, "test_note": pl.String},
)

# --- Holm across measures: one p per measure, from its model's group x visit test
per_measure = raw.group_by([*FAMILY, "measure"], maintain_order=True).agg(
    pl.col("p_interaction").first(), pl.col("converged").any()
)
adjusted = d.holm_by(per_measure, FAMILY, "p_interaction", "p_interaction_holm").select(
    *FAMILY, "measure", "p_interaction_holm"
)
trends = raw.join(adjusted, on=[*FAMILY, "measure"], how="left").with_columns(
    pl.when(pl.col("converged")).then(pl.col("p_interaction_holm")).alias("p_interaction_holm")
)

# --- small cells: persons per Yes group with a value and the covariates at each visit
groups = pl.read_parquet(frames / "discordance_groups.parquet").filter(
    pl.col("group").is_in(d.GROUPS[:2])
)
long = pl.read_parquet(frames / "discordance_long.parquet").filter(
    pl.col("value").is_not_null() & pl.col("visit").is_in(visits)
)
fixed = pl.read_parquet(frames / "discordance_fixed.parquet")
complete = (
    fixed.filter(pl.col("comparison").is_null() & pl.col("measure").is_in(covariates))
    .group_by("ID")
    .agg(pl.col("value").is_not_null().sum().alias("k"))
    .filter(pl.col("k") == len(covariates))
    .select("ID")
)
cells = (
    long.join(complete, on="ID")
    .join(groups, on="ID")
    .group_by("comparison", "censored", "measure", "visit", "group")
    .agg(pl.col("ID").n_unique().alias("p"))
    .group_by("comparison", "censored", "measure", "visit")
    .agg(pl.col("p").min().alias("smallest"), pl.len().alias("groups_present"))
)
trends = trends.join(cells, on=["comparison", "censored", "measure", "visit"], how="left")
small = (pl.col("groups_present").fill_null(0) < 2) | (pl.col("smallest").fill_null(0) < min_cell)
small = small & pl.col("visit").is_not_null() & pl.col("estimate").is_not_null()
note = pl.lit("fewer than the release threshold of people in a Yes group at this visit")
trends = trends.with_columns(
    *[pl.when(small).then(None).otherwise(pl.col(c)).alias(c) for c in ("estimate", "lo", "hi")],
    pl.when(small).then(note).otherwise(pl.col("fit_note")).alias("fit_note"),
).with_columns(
    # a failed group x visit test says why
    pl.when(pl.col("fit_note").is_null() & pl.col("test_note").is_not_null())
    .then(pl.lit("group x visit test: ") + pl.col("test_note"))
    .otherwise(pl.col("fit_note"))
    .alias("fit_note")
)
print(f"small-cell rule nulled {trends.filter(small).height} visit estimates")

order = {v: i for i, v in enumerate(visits)}
names = list(A["discordance.comparisons"])
trends = (
    trends.select(
        "comparison",
        "censored",
        "measure",
        "kind",
        "visit",
        "estimate",
        "lo",
        "hi",
        "scale",
        "p_interaction",
        "p_interaction_holm",
        "persons_model",
        "converged",
        "fit_note",
    )
    .with_columns(
        pl.col("comparison").replace_strict({n: i for i, n in enumerate(names)}).alias("_c"),
        pl.col("visit").replace_strict(order, default=len(order)).alias("_v"),
    )
    .sort("_c", "censored", "measure", "_v")
    .drop("_c", "_v")
)
trends.write_csv(results / "discordance_trends.csv")
summary = (
    trends.group_by("comparison", "censored")
    .agg(
        pl.col("measure").n_unique().alias("measures"),
        pl.col("measure")
        .filter(pl.col("p_interaction_holm").is_not_null())
        .n_unique()
        .alias("tested"),
        pl.col("measure")
        .filter(pl.col("p_interaction_holm") < alpha)
        .n_unique()
        .alias("holm_below_alpha"),
    )
    .sort("comparison", "censored")
)
print(summary)

# --- DISCORDANCE.md with both stages
screen = pl.read_csv(
    results / "discordance_screen.csv",
    schema_overrides={"start_used": pl.String, "end_used": pl.String, "band": pl.String},
)
# the same gap as discordance_screen: all groups, the whole long table
gaps = d.coverage_gaps(
    d.kl_coverage(
        pl.read_parquet(frames / "discordance_groups.parquet"),
        pl.read_parquet(frames / "discordance_long.parquet"),
    )
)
self_report = list(A["discordance.self_report_context"])
text = d.render_markdown(
    screen,
    trends,
    coverage_gap=gaps,
    label=A.label,
    threshold=float(A["discordance.kl_coverage_gap"]),
    self_report_measures={
        name: self_report if pro_id.startswith("pase") else []
        for name, (pro_id, _, _) in A["discordance.comparisons"].items()
    },
    alpha=alpha,
)
(results / "DISCORDANCE.md").write_text(text)
