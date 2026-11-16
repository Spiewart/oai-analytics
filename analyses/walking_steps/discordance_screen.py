"""Step `discordance_screen`: stage 1, standardized differences between the two "Yes" groups.

Per comparison: each time-varying measure's level at the anchor visit and its change over each
ledger window (the nearest visit holding the measure, within discordance.nearest_visit_steps
scheduled visits of each endpoint, used and reported), and each fixed measure. Knee-level
measures are screened under both replacement rules (`censored`). Also the flow of persons per
group and visit, and KL coverage by group and visit. Aggregates only.
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
# ledger keys that record how this step works; each has one implemented value
IMPLEMENTED = {
    "discordance.visit_order": "trend_visits",
    "discordance.binary_change": "continuous",
    "discordance.season_coding": "first_valid_day_month",
    "discordance.weekend_days": "release_valid_days",
    "discordance.kl_gap_rule": "max_over_visits",
}
for key, value in IMPLEMENTED.items():
    if A[key] != value:
        raise ValueError(f"{key} = {A[key]!r} is not implemented; only {value!r}")
anchor = A["discordance.anchor_visit"]
steps = int(A["discordance.nearest_visit_steps"])
order = list(A["discordance.trend_visits"])  # the scheduled clinic visits, in time order
kinds = {m: spec[1] for m, spec in d.MEASURES.items()}
# PASE item 2 (walking outside the home) is the PASE comparison's self-report: its measures
# describe how the groups were formed, so DISCORDANCE.md shows them as context
SELF_REPORT_MEASURES = list(A["discordance.self_report_context"])
change_kinds = {m: "continuous" if k == "binary" else k for m, k in kinds.items()}

groups = pl.read_parquet(frames / "discordance_groups.parquet")
long = pl.read_parquet(frames / "discordance_long.parquet")
fixed = pl.read_parquet(frames / "discordance_fixed.parquet")

# --- per-person values for every window (comparison-independent for the long table)
level = d.nearest_values(long, anchor, steps, order).select(
    "ID",
    "measure",
    "censored",
    pl.lit(f"level_{anchor}").alias("window"),
    "value",
    pl.col("used").alias("start_used"),
    pl.col("used").alias("end_used"),
)
changes = [
    d.window_values(long, a, b, steps, order).select(
        "ID",
        "measure",
        "censored",
        pl.lit(f"change_{a}_{b}").alias("window"),
        pl.col("change").alias("value"),
        "start_used",
        "end_used",
    )
    for a, b in A["discordance.change_windows"]
]
tv = pl.concat([level, *changes])


def screen_one(name: str) -> pl.DataFrame:
    g = groups.filter(pl.col("comparison") == name).select("ID", "group")
    fx = fixed.filter(pl.col("comparison").is_null() | (pl.col("comparison") == name)).select(
        "ID",
        "measure",
        pl.lit(False).alias("censored"),
        pl.lit("fixed").alias("window"),
        "value",
        pl.lit(None, dtype=pl.String).alias("start_used"),
        pl.lit(None, dtype=pl.String).alias("end_used"),
    )
    values = pl.concat([tv, fx])
    out = []
    for censored in (False, True):
        v = values.filter(pl.col("censored") == censored).drop("censored")
        if v.height == 0:
            continue
        is_change = pl.col("window").str.starts_with("change_")
        # a change in a 0/1 measure is -1, 0 or 1: summarised and compared as continuous
        parts = [
            d.screen(g, v.filter(~is_change), kinds, A, min_cell=min_cell),
            d.screen(g, v.filter(is_change), change_kinds, A, min_cell=min_cell),
        ]
        s = pl.concat(parts).sort("measure", "window")
        out.append(
            s.with_columns(pl.lit(name).alias("comparison"), pl.lit(censored).alias("censored"))
        )
    return pl.concat(out)


names = list(A["discordance.comparisons"])
screen = pl.concat(screen_one(n) for n in names)
screen = screen.select(
    "comparison", "censored", *[c for c in screen.columns if c not in ("comparison", "censored")]
)
bad = set(screen["band"].unique().to_list()) - {"negligible", "small", "lead", ""}
if bad:
    raise ValueError(f"unexpected band values {bad}")
screen.write_csv(results / "discordance_screen.csv")


# --- flow: persons per group, and persons with any time-varying value at each visit
def suppress(name: str) -> pl.Expr:
    x = pl.col(name)
    return pl.when((x > 0) & (x < min_cell)).then(None).otherwise(x).alias(name)


attended = (
    long.filter(~pl.col("censored") & pl.col("value").is_not_null()).select("ID", "visit").unique()
)
per_visit = (
    groups.join(attended, on="ID")
    .group_by("comparison", "group", "visit")
    .agg(pl.len().alias("p"))
    .pivot(on="visit", index=["comparison", "group"], values="p", sort_columns=True)
)
per_visit = per_visit.rename({v: f"persons_v{v}" for v in order if v in per_visit.columns})
flow = (
    groups.group_by("comparison", "group")
    .agg(pl.len().alias("persons"))
    .join(per_visit, on=["comparison", "group"], how="left")
    .with_columns(suppress(c) for c in ["persons", *per_visit.columns[2:]])
    .with_columns(
        pl.col("group").replace_strict({g: i for i, g in enumerate(d.GROUPS)}).alias("_o")
    )
    .sort(pl.col("comparison").replace_strict({n: i for i, n in enumerate(names)}), "_o")
    .drop("_o")
)
flow.write_csv(results / "discordance_flow.csv")
print(flow)

# --- KL coverage by group and visit, and the caveat
# the gap from the unsuppressed shares; the CSV nulls shares resting on 1..min_cell-1 people
gaps = d.coverage_gaps(d.kl_coverage(groups, long))
d.kl_coverage(groups, long, min_cell).write_csv(results / "discordance_kl_coverage.csv")
print("KL coverage gap between the Yes groups:", gaps)

text = d.render_markdown(
    screen,
    pl.DataFrame(),
    coverage_gap=gaps,
    label=A.label,
    threshold=float(A["discordance.kl_coverage_gap"]),
    self_report_measures={
        name: SELF_REPORT_MEASURES if pro_id.startswith("pase") else []
        for name, (pro_id, _, _) in A["discordance.comparisons"].items()
    },
)
(results / "DISCORDANCE.md").write_text(text)
