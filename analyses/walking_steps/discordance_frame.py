"""Step `discordance_frame`: the person-level frames for the discordance comparison.

For each ledger comparison (self-report, device walker definition, device basis), the groups
"Yes, step walker", "Yes, not a step walker" and "No"; the long table of time-varying measures
(discordance.long_table); and the fixed measures, with the device-week descriptors over each
comparison's device basis. Person-level, so all three go to OAI_FRAME_DIR, never to results,
with discordance_measures.parquet (each measure's kind) for the stage-2 R step.
"""

import os
from pathlib import Path

import discordance as d
import polars as pl
from devices import device_inputs, device_waves
from pro import self_reports

from oai.assumptions import current
from oai.derive.walking import walking_answers
from oai.loader import read_table

A = current()
frames = Path(os.environ["OAI_FRAME_DIR"])
anchor = A["discordance.anchor_visit"]
comparisons = A["discordance.comparisons"]

# --- groups: the same self-reports and device walkers as pro_validity
definitions, measures = device_inputs(A)
device = pl.read_parquet(frames / "device.parquet")
waves = device_waves(device, definitions, measures)
pros = self_reports(A)
groups = pl.concat(
    d.assign_groups(pros[pro_id][2], waves[key], definition).select(
        pl.lit(name).alias("comparison"), pl.col("ID").cast(pl.Int64), "group"
    )
    for name, (pro_id, definition, key) in comparisons.items()
).sort("comparison", "group", "ID")
sizes = groups.group_by("comparison", "group").agg(pl.len().alias("persons")).sort("comparison")
print(sizes)
primary = dict(sizes.filter(pl.col("comparison") == "primary").select("group", "persons").rows())
expected = {d.GROUPS[0]: 341, d.GROUPS[1]: 910, d.GROUPS[2]: 314}
if A.label == "default" and primary != expected:
    raise ValueError(f"primary group sizes {primary} differ from the 2x2 already sent {expected}")

# --- time-varying measures
long = d.long_table(A)


# --- fixed person measures
def fixed_long(df: pl.DataFrame) -> pl.DataFrame:
    return df.unpivot(index="ID", variable_name="measure", value_name="value").select(
        pl.col("ID").cast(pl.Int64), "measure", pl.col("value").cast(pl.Float64)
    )


enrollees = read_table("enrollees")
ac0 = read_table("allclinical", "00")
sites = sorted(enrollees["V00SITE"].drop_nulls().unique().to_list())
person = [
    fixed_long(
        enrollees.select(
            "ID",
            (pl.col("P02SEX") == 2).cast(pl.Float64).alias("sex"),  # 1 female, 0 male
            pl.col("P02RACE").alias("race"),
            pl.col("V00COHORT").alias("subcohort"),
            # site letters A..E as codes 1..5
            pl.col("V00SITE")
            .replace_strict({s: i + 1 for i, s in enumerate(sites)}, default=None)
            .alias("site"),
        )
    ),
    fixed_long(
        ac0.select(
            "ID",
            pl.col("V00AGE").alias("age0"),
            pl.col("V00EDCV").alias("education"),
            pl.col("V00INCOME").alias("income"),
            pl.when(pl.col("V00MARITST").is_not_null())
            .then(pl.col("V00MARITST") == 1)
            .cast(pl.Float64)
            .alias("married"),
        )
    ),
    fixed_long(
        read_table("allclinical", anchor).select("ID", pl.col(f"V{anchor}AGE").alias("age"))
    ),
]
amounts = fixed_long(
    walking_answers().select("ID", "amount_years", "amount_months", "amount_times")
)

# --- device-week descriptors over each comparison's device basis
calendar = pl.concat(d.device_calendar(read_table("acceldatabyday", w), w) for w in ("06", "08"))
fixed = [pl.concat(person).with_columns(pl.lit(None, dtype=pl.String).alias("comparison"))]
for name, (pro_id, _, key) in comparisons.items():
    desc = d.device_descriptors(device, calendar, key)
    fixed.append(fixed_long(desc).with_columns(pl.lit(name).alias("comparison")))
    if pro_id == "item96":  # the item's own amount answers describe the item comparisons only
        fixed.append(amounts.with_columns(pl.lit(name).alias("comparison")))
fixed = (
    pl.concat(fixed)
    .select("comparison", "ID", "measure", "value")
    .sort("comparison", "measure", "ID", nulls_last=False)
)

groups.write_parquet(frames / "discordance_groups.parquet")
long.write_parquet(frames / "discordance_long.parquet")
fixed.write_parquet(frames / "discordance_fixed.parquet")
# each measure's kind, for the stage-2 R step (which cannot read discordance.MEASURES)
pl.DataFrame(
    {"measure": list(d.MEASURES), "kind": [spec[1] for spec in d.MEASURES.values()]}
).write_parquet(frames / "discordance_measures.parquet")
print(f"long {long.shape}, fixed {fixed.shape}")
