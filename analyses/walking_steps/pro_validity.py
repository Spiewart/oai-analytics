"""Step `pro_validity`: self-reported walking against count-based and step-based device walking.

Self-reports: the 96-month walking-for-exercise item, and PASE item 2 (walking outside the home)
at 48, 72 and 96 months as 'any walking' and as 'walking on at least 3-4 days'. Each is compared
with every device walker definition (devices.walker_definitions), and with every continuous
device measure (AUC; Spearman for the PASE walking subscore).

Every comparison uses the same people for every device definition: a valid device wave (or, for
the combined measures, at least one) with step measures. Aggregates only.
"""

import os
from pathlib import Path

import polars as pl
from devices import COUNT_MEASURES, combine, either_week, step_bout_measures, walker_definitions
from pro import accuracy, auc_with_ci, spearman

from oai.assumptions import current
from oai.derive.pase import pase_visit
from oai.derive.walking import walker_status, walking_answers
from oai.loader import read_table
from oai.results import md_table
from oai.visits import nominal_month

A = current()
frames, results = Path(os.environ["OAI_FRAME_DIR"]), Path(os.environ["OAI_RESULTS_DIR"])
cadences = [int(c) for c in A["reference.step_cadences"]]
step_measures = ["steps", "peak_cadence"]
step_measures += [f"cadence{c}_min" for c in cadences]
step_measures += [m for c in cadences for m in step_bout_measures(c)]
measures = COUNT_MEASURES + step_measures
definitions = walker_definitions(
    A["reference.min_bout_days_per_week"], A["reference.min_bout_minutes_per_week"], cadences
)
missing = set(A["validity.auc_measures"]) - set(measures)
if missing:
    raise ValueError(f"validity.auc_measures has measures this step does not build: {missing}")

device = pl.read_parquet(frames / "device.parquet")


def with_walkers(df: pl.DataFrame) -> pl.DataFrame:
    common = df.filter(pl.col("steps").is_not_null())  # the same people for every definition
    return common.with_columns(expr.alias(name) for name, _, expr in definitions)


wave = {
    w: with_walkers(device.filter(pl.col("valid") & (pl.col("wave") == w))) for w in ("06", "08")
}
wave["mean"] = with_walkers(combine(device, measures))
# Either week: a device walker when any valid wave meets the definition (for the self-reports
# paired with the mean of both waves). Same people as "mean": the combined step measures exist.
names = [name for name, _, _ in definitions]
wave["either"] = either_week(pl.concat([wave["06"], wave["08"]], how="diagonal"), names).join(
    wave["mean"].select("ID"), on="ID", how="semi"
)
DEVICE_LABEL = {
    "06": "48-month wave",
    "08": "72-month wave",
    "mean": "mean of valid waves",
    "either": "either valid wave",
}

# --- self-reports: ID, yes (Boolean), score (PASE walking subscore; null for the item)
answered = walking_answers().with_columns(
    walker_status(yes_without_amount_as=A["exposure.yes_without_amount_as"], missing_as="exclude")
)
pros = [
    (
        "item96",
        "Walked for exercise since age 50 (96-month item)",
        "10",
        answered.filter(pl.col("walker").is_not_null()).select(
            "ID", pl.col("walker").alias("yes"), pl.lit(None, dtype=pl.Float64).alias("score")
        ),
    )
]
for v in A["pase.visits"]:
    p = pase_visit(read_table("allclinical", v), v, A["pase.walking_scoring"])
    score, days = pl.col(f"pase_walking_{v}"), pl.col(f"pase_days_{v}")
    month = nominal_month(v)
    pros += [
        (
            f"pase{v}_any",
            f"PASE walking, any ({month} months)",
            v,
            p.filter(score.is_not_null()).select(
                "ID", (score > A["pase.walker_threshold"]).alias("yes"), score.alias("score")
            ),
        ),
        (
            f"pase{v}_frequent",
            f"PASE walking, 3+ days a week ({month} months)",
            v,
            p.filter(days.is_not_null()).select(
                "ID", (days >= A["pase.frequent_days_code"]).alias("yes"), score.alias("score")
            ),
        ),
    ]


def paired_wave(visit: str) -> str:
    if A["pase.device_pairing"] == "two_wave_mean" or visit not in ("06", "08"):
        return "mean"
    return visit


acc_rows, auc_rows, rho_rows, flow_rows = [], [], [], []
for i, (pro_id, pro_label, visit, frame) in enumerate(pros):
    w = paired_wave(visit)
    joined = frame.join(wave[w], on="ID", how="inner")
    base = {"pro": pro_id, "pro_label": pro_label, "device": DEVICE_LABEL[w]}
    flow_rows.append({**base, "pro_answers": frame.height, "with_device": joined.height})
    for name, family, _ in definitions:
        a = accuracy(joined["yes"], joined[name])
        acc_rows.append({**base, "definition": name, "family": family, **a})
    for j, m in enumerate(A["validity.auc_measures"]):
        seed = int(A["validity.seed"]) + 1000 * i + j
        r = auc_with_ci(joined[m], joined["yes"], int(A["validity.bootstrap_reps"]), seed)
        auc_rows.append({**base, "measure": m, **r})
        if pro_id.endswith("_any"):  # the subscore is the same for both PASE codings
            rho_rows.append({**base, "measure": m, **spearman(joined["score"], joined[m])})

    if w == "mean":  # the same self-report, crediting a walker from either valid wave
        either = frame.join(wave["either"], on="ID", how="inner")
        eb = {**base, "device": DEVICE_LABEL["either"]}
        for name, family, _ in definitions:
            acc_rows.append(
                {
                    **eb,
                    "definition": name,
                    "family": family,
                    **accuracy(either["yes"], either[name]),
                }
            )

acc = pl.DataFrame(acc_rows)
acc.write_csv(results / "pro_accuracy.csv")
pl.DataFrame(auc_rows).write_csv(results / "pro_auc.csv")
pl.DataFrame(rho_rows).write_csv(results / "pro_spearman.csv")
flow = pl.DataFrame(flow_rows)
flow.write_csv(results / "pro_flow.csv")
print(flow)


# --- readable summary: sensitivity and specificity, bout-days rule, every family
def fmt(x: float | None) -> str:
    return "" if x is None else f"{x:.2f}"


def summary(rule: str) -> str:
    rows = acc.filter(pl.col("definition").str.ends_with(f":{rule}")).with_columns(
        (
            pl.col("sensitivity").map_elements(fmt, return_dtype=pl.String)
            + " / "
            + pl.col("specificity").map_elements(fmt, return_dtype=pl.String)
        ).alias("se_sp")
    )
    wide = rows.pivot(on="family", index=["pro_label", "device", "n"], values="se_sp")
    return md_table(wide.rename({"pro_label": "Self-report", "device": "Device"}))


text = f"""# Self-reported walking against device walking [{A.label}]

Sensitivity / specificity of each self-report against device walkers defined by count-based MV
bouts (`counts_mv`, as in walking_validation) and by step walking bouts at
{", ".join(str(c) for c in cadences)} steps/min (`steps_<c>`). Every definition in a row uses the
same people. Full statistics, with 95% CIs, PPV, NPV, agreement and kappa: pro_accuracy.csv;
AUC: pro_auc.csv; Spearman with the PASE walking subscore: pro_spearman.csv.

## Device walker = bout on >= {A["reference.min_bout_days_per_week"]:g} days a week

{summary("bout_days")}
## Device walker = any bout

{summary("any_bout")}
## Device walker = >= {A["reference.min_bout_minutes_per_week"]:g} bout minutes a week

{summary("bout_minutes")}"""
(results / "PRO_VALIDITY.md").write_text(text)
