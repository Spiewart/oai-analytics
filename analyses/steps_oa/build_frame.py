"""Step `cohort`: person and knee frames (OAI_FRAME_DIR), aggregate flow and descriptives.

Frames (participant-level, OAI_FRAME_DIR only):
  persons              persons.person_frame + reverse_exposures + soa48 (people valid at 48 mo)
  periods_{roa,soa}    discrete-time rows from V06 to periods.horizon (P1, P2)
  periods_{roa,soa}_72 the same from V08, knees still at risk at V08 (S1)
  horizon_{roa,soa}    outcome by periods.horizon (companion model)
  progression          KL and JSN worsening, V06 KL in progression.risk_kl (S3, read knees)
  jsw                  medial minimum JSW change, same knees (S3b)
  tkr                  time to knee replacement from V06 (S2, S3)
  jsw_72, tkr_72       the same from V08 (72 months), for the models with the 48 -> 72 change
Every knee frame carries kl48, womac48, roa48, sx48 and the person columns.
"""

import os
from pathlib import Path

import polars as pl
from persons import (
    ANCHOR,
    KEYS,
    PERSON_COLUMNS,
    descriptives,
    frame_flow,
    incidence_sample,
    jsw_frame,
    knee_base,
    person_frame,
    progression_frame,
    replacement_frame,
    reverse_exposures,
    risk_grades,
    selection_flow,
    soa_person,
    with_person,
)
from persons import agreement as agreement_rows

from oai.assumptions import current
from oai.derive import knee_outcomes as ko
from oai.derive.accel import read_minutes
from oai.derive.devices import covariates_48, device_rules, person_wave
from oai.derive.knee import find_col, xray_readings
from oai.loader import read_table

# person_wave also builds step-bout measures at these cadences; this analysis does not use them
UNUSED_BOUT_CADENCES = [100]
FIRST_VISIT = "05"  # the 36 -> 48 month window of the reverse exposure R1

A = current()
frames, results = Path(os.environ["OAI_FRAME_DIR"]), Path(os.environ["OAI_RESULTS_DIR"])
horizon = A["periods.horizon"]
selection = A["horizon.selection"]
risk = risk_grades(A["progression.risk_kl"])

# ---------------------------------------------------------------- persons
rules = device_rules(A)
waves = []
for visit in ("06", "08"):
    wave = person_wave(
        read_minutes(visit, steps=True), rules, UNUSED_BOUT_CADENCES, int(A["sample.min_step_days"])
    )
    waves.append(
        wave.select("ID", "valid", "steps", "mv_min", "wear_hr").with_columns(
            pl.col("ID").cast(pl.Int64), pl.lit(visit).alias("wave")
        )
    )
device = pl.concat(waves)
persons = person_frame(device, covariates_48(int(A["cohort.reading_project"])), A)

# ---------------------------------------------------------------- knees
# every scheduled visit from V05 to the horizon (by_horizon and periods refuse gaps)
visits = [v for v in ko.SCHEDULE if FIRST_VISIT <= v <= horizon]
status = ko.knee_status(A, visits, ANCHOR)
p15 = xray_readings([FIRST_VISIT, ANCHOR], project=int(A["cohort.reading_project"])).select(
    pl.col("ID").cast(pl.Int64), "SIDE", "visit", pl.col("KL").alias("kl_p15")
)
reverse = reverse_exposures(status.join(p15, on=[*KEYS, "visit"], how="left"), A)
soa48 = soa_person(status)
persons_out = persons.join(reverse, on="ID", how="left").join(soa48, on="ID", how="left")

clin = read_table("allclinical", ANCHOR)
womac = pl.concat(
    [
        clin.select(
            pl.col(find_col(clin, "ID")).cast(pl.Int64).alias("ID"),
            pl.lit(side).alias("SIDE"),
            pl.col(find_col(clin, f"V{ANCHOR}WOMKP{side}", where=f"allclinical{ANCHOR}"))
            .cast(pl.Float64)
            .alias("womac"),
        )
        for side in ko.SIDES
    ]
)
base = knee_base(status, womac)
people = persons.select(PERSON_COLUMNS)
device_ids = people.select("ID")

samples = {o: incidence_sample(status, o, ANCHOR, A) for o in ko.OUTCOMES}
samples_72 = {o: incidence_sample(status, o, "08", A) for o in ko.OUTCOMES}
out = {}
for o in ko.OUTCOMES:
    out[f"periods_{o}"] = with_person(
        ko.periods(status, o, ANCHOR, horizon).join(samples[o], on=KEYS, how="semi"), base, people
    )
    out[f"periods_{o}_72"] = with_person(
        ko.periods(status, o, "08", horizon).join(samples_72[o], on=KEYS, how="semi"), base, people
    )
    out[f"horizon_{o}"] = with_person(
        ko.by_horizon(status, o, ANCHOR, horizon, selection).join(samples[o], on=KEYS, how="semi"),
        base,
        people,
    )

progression_all = progression_frame(status, horizon, risk, A)
out["progression"] = with_person(progression_all, base, people)

jsw_all = (
    ko.jsw_change(A, ANCHOR, horizon)
    .with_columns(pl.col("ID").cast(pl.Int64))
    .join(progression_all.select(KEYS), on=KEYS, how="semi")
)
out["jsw"] = with_person(jsw_all, base, people)
# change models take the outcome from 72 months: JSW 72 -> horizon, same knees
out["jsw_72"] = jsw_frame(ko.jsw_change(A, "08", horizon), progression_all, base, people)

tkr_all, tkr_flow = ko.replacement_times(A, ANCHOR)
tkr_all = tkr_all.with_columns(pl.col("ID").cast(pl.Int64))
out["tkr"] = replacement_frame(tkr_all, base, people, ko.at_risk(status, "roa", ANCHOR))
# change models: knees not replaced by the 72-month visit, time from that visit
tkr72_all, tkr72_flow = ko.replacement_times(A, "08")
tkr72_all = tkr72_all.with_columns(pl.col("ID").cast(pl.Int64))
out["tkr_72"] = replacement_frame(tkr72_all, base, people, ko.at_risk(status, "roa", "08"))

persons_out.write_parquet(frames / "persons.parquet")
for name, frame in out.items():
    frame.write_parquet(frames / f"{name}.parquet")

# ---------------------------------------------------------------- flow (aggregates only)
flow = [
    {"sample": "persons", "step": "device_48", "n": device.filter(pl.col("wave") == "06").height},
    {"sample": "persons", "step": "valid_48", "n": persons.height},
    {"sample": "persons", "step": "steps_48", "n": persons["steps_48"].is_not_null().sum()},
    {"sample": "persons", "step": "valid_both", "n": persons["valid72"].sum()},
    {
        "sample": "persons",
        "step": "steps_both",
        "n": persons.filter(pl.col("steps_change").is_not_null()).height,
    },
]
for column in ("new_oa_36_48", "new_oa_48_72", "new_oa_read_48_72"):
    known = persons_out.filter(pl.col(column).is_not_null())
    flow += [
        {"sample": "persons", "step": f"{column}_known", "n": known.height},
        {"sample": "persons", "step": f"{column}_true", "n": int(known[column].sum())},
    ]
for o in ko.OUTCOMES:
    for label, sample in ((f"incident_{o}", samples[o]), (f"incident_{o}_72", samples_72[o])):
        flow.append({"sample": label, "step": "knees_all_people", "n": sample.height})
        flow.append(
            {
                "sample": label,
                "step": "knees_valid_48",
                "n": sample.join(device_ids, on="ID", how="semi").height,
            }
        )
progression_risk = status.filter(
    (pl.col("visit") == ANCHOR) & ~pl.col("replaced") & pl.col("kl").is_in(risk)
)
flow.append({"sample": "progression", "step": "knees_all_people", "n": progression_risk.height})
jsw_both = jsw_all.filter(pl.col("change_mm").is_not_null())
flow.append({"sample": "jsw", "step": "knees_both_widths_all_people", "n": jsw_both.height})
flow.append({"sample": "tkr", "step": "knees_all_people", "n": tkr_all.height})
for column in tkr_flow.columns:
    flow.append({"sample": "tkr", "step": column, "n": tkr_flow[column].item()})
flow.append({"sample": "tkr_72", "step": "knees_all_people", "n": tkr72_all.height})
for column in tkr72_flow.columns:
    flow.append({"sample": "tkr_72", "step": column, "n": tkr72_flow[column].item()})
jsw72_both = out["jsw_72"].filter(pl.col("change_mm").is_not_null())
flow.append({"sample": "jsw_72", "step": "knees_both_widths_valid_48", "n": jsw72_both.height})

events = {
    **{f"periods_{o}": "event" for o in ko.OUTCOMES},
    **{f"periods_{o}_72": "event" for o in ko.OUTCOMES},
    **{f"horizon_{o}": "event" for o in ko.OUTCOMES},
    "progression": "kl_event",
    "jsw": "progressor",
    "tkr": "event",
    "jsw_72": "progressor",
    "tkr_72": "event",
}
for name, event in events.items():
    flow += frame_flow(name, out[name], event)
flow += frame_flow("progression_jsn", out["progression"], "jsn_event")
flow += frame_flow("tkr_incidence", out["tkr"].filter("at_risk_roa"), "event")
flow += frame_flow("tkr_progression", out["tkr"].filter("progression_tkr"), "event")
flow += frame_flow("tkr_72_incidence", out["tkr_72"].filter("at_risk_roa"), "event")
flow += frame_flow("tkr_72_progression", out["tkr_72"].filter("progression_tkr"), "event")

after = [v for v in visits if v >= ANCHOR]
for label, knees in (("incident_roa", samples["roa"]), ("progression", progression_all)):
    chosen = status.join(knees.select(KEYS), on=KEYS, how="semi").join(
        device_ids, on="ID", how="semi"
    )
    flow += selection_flow(f"selection_{label}", ko.selection_counts(chosen, ANCHOR, after))

flow = pl.DataFrame(flow, schema={"sample": pl.String, "step": pl.String, "n": pl.Int64})
flow.write_csv(results / "flow.csv")

# ---------------------------------------------------------------- descriptives
transitions = with_person(progression_frame(status, horizon, None, A), base, people)
roa99 = ko.by_horizon(status, "roa", ANCHOR, horizon, selection).join(
    samples["roa"], on=KEYS, how="semi"
)
case_frames = {name: (out[name], event) for name, event in events.items()}
case_frames["progression_jsn"] = (out["progression"], "jsn_event")
case_frames["tkr_incidence"] = (out["tkr"].filter("at_risk_roa"), "event")
case_frames["tkr_progression"] = (out["tkr"].filter("progression_tkr"), "event")
table = descriptives(
    case_frames,
    persons,
    soa48,
    out["progression"],
    transitions,
    agreement_rows(transitions.select(*KEYS, "kl_incident"), roa99),
    A,
)
table.write_csv(results / "descriptives.csv")
with pl.Config(tbl_rows=-1):
    print(flow)
