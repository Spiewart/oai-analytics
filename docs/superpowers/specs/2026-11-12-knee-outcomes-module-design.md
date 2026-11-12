# Shared knee-level incidence and progression outcomes: design

**Why (user, 2026-11-12).** Incidence and progression outcomes are rebuilt inside each analysis. The user wants one pluggable module that the next incidence or progression question can reuse, as the MRI outcomes module will be later. `analyses/steps_oa` is its first new user. Its spec, `2026-11-12-steps-oa-design.md`, is unchanged; only its Task 2 moves here.

## What exists today

| Piece | Where | State |
|---|---|---|
| `kl_progression`, `fnih_jsw_progressor` | `src/oai/derive/progression.py` | stubs (`NotImplementedError`) since the scaffold |
| `progression_definitions` | `analyses/progression_definitions` | stub analysis |
| `soa_status`, `roa_from_outcomes99` | `oai.derive.incident_soa` | built; one knee (`cohort.side`) per call; Lo 2018 person design |
| `for_side`, `roa_series`, `by_horizon` | `analyses/luyten_early_oa/luyten.py` | built; knee-level; anchored at baseline only |
| KL progression, incident ROA/SOA and TKR counts | `analyses/crepitus/crepitus.py` | built; its own rules |
| `xray_readings` | `oai.derive.knee` | one reading project per call; KL and JSM only |

TODO.md already asks to "consolidate progression derivations … so there is one way to compute KL/JSN progression".

## Goals

1. **One module, `oai.derive.knee_outcomes`.** It gives knee-level (both knees, `SIDE`) incidence and progression outcomes from any **anchor visit**: baseline for the Luyten design, 48 months for steps.
2. **It carries reading selection explicitly.** Every knee-visit says whether it was read and by which project, so every user can see and count selective follow-up. Readings after 48 months are by design (Project 37/42/43; `kXR_SQ_BU_Descrip.pdf`).
3. **It is configured by ledger keys, not by code.** The analysis's `assumptions.toml` holds the rules, under the existing `outcomes.*` names where they exist.
4. **It is proven by reproduction.** `luyten_early_oa` moves onto it, and its outputs stay byte-identical.

## Non-goals

- The person-level, one-knee Lo 2018 machinery (`incident_soa.build_cohort`, `crepitus_frame`, `schedule`) stays as it is. `lo2018_crepitus`, `exam_crepitus_soa` and `crepitus_soa_longterm` have published replication targets and are not touched. The module calls `soa_status` rather than re-deriving it.
- No WOMAC-based progression and no MRI. The module's shape leaves room for both as further outcome functions, but neither is built now (YAGNI). WOMAC goes to TODO.md; MRI is its own project.
- FNIH quantitative JSW **is** in scope (item 8; user, 2026-11-12).
- `analyses/crepitus/crepitus.py` keeps its own counts for now. Moving it onto the module is filed in TODO.md, because its rules (any visit to the horizon, Project 15 only) need a careful reproduction of their own.

## Anti-goals

- Any change to an existing analysis's results.
- A module that hides unread knees by treating them as non-events.

## Interface

All functions are pure on frames except `knee_status` and `replacement_times`, which read tables. Visits are two-character codes (`"00"`, `"06"`, …).

1. **`knee_status(A, visits) -> pl.DataFrame`.** One row per ID × SIDE × visit, with columns `ID, SIDE, visit, roa, sx, soa, replaced, kl, jsm, jsl, read, readprj`.
   - `roa`, `sx`, `soa` and `replaced` come from `soa_status` called per side (the `for_side` pattern moves here).
   - Under `outcomes.roa_replacement = "event"`, a replaced knee has `roa` True; under `"ignore"` (luyten's existing value name), OUTCOMES99 ROA as is.
   - `kl`, `jsm`, `jsl`, `read` and `readprj` come from `xray_readings`. The projects used depend on the visit:
     - **Before the anchor:** Project `cohort.reading_project` (15).
     - **At and after the anchor, when the anchor is V06 or later:** the projects named by `readings.followup_project`:
       - `"latest"` = 43, then 37;
       - `"p37"` = 37 only.

       Either way, base and follow-up grades come from the same reading project, so a reader difference is not counted as change. Project 37/42 readers re-read V06 and could revise Project 15's grades.
     - **When the anchor is V00:** Project 15 throughout, as luyten uses now.
   - **Anchor-reading variant:** `readings.anchor_project = "p15"` takes the anchor grade from Project 15 instead. The default is `"followup"`. This replaces steps_oa's `kl48.source`.
   - **READPRJ 42** is recoded to 37, as `kXR_SQ_BU_Descrip.pdf` instructs.
   - `xray_readings` gains `JSL`, `READPRJ` and a list of projects, in preference order. Single-project calls are unchanged.
2. **`at_risk(status, outcome, anchor) -> pl.DataFrame`.** `ID, SIDE` for knees whose `outcome` is known False at `anchor` and that are not replaced at `anchor`. `outcome` ∈ {`roa`, `soa`}.
3. **`by_horizon(status, outcome, anchor, horizon, selection) -> pl.DataFrame`.** `ID, SIDE, event`. This is luyten's `by_horizon`, generalised from baseline to `anchor` and keyed by knee. Its semantics are unchanged: a knee prevalent at the anchor is null; `known_or_case` and `complete` work as before.
4. **`periods(status, outcome, anchor, horizon) -> pl.DataFrame`.** `ID, SIDE, period, end_visit, span, event`. These are discrete-time rows between consecutive visits after `anchor` at which `outcome` is known.
   - `span` = the number of scheduled follow-up visits the period covers.
   - Rows stop after the first event.
   - Only knees in `at_risk` are included.
5. **`progression(status, measure, anchor, horizon, risk) -> pl.DataFrame`.** `ID, SIDE, base, event, read_at_horizon`.
   - `measure` ∈ {`kl`, `jsm`, `jsl`}.
   - **Event:** any read visit after the anchor, up to the horizon, is at least one whole grade above `base`, i.e. `floor(follow-up) ≥ floor(base) + 1`. This handles the follow-up JSM/JSL within-grade decimals such as 1.2.
   - **Variant:** `progression.jsn_rule = "within_grade"` counts any rise.
   - It is null when no visit is read and no worsening was seen.
   - `risk` is a set of base grades, from `progression.risk_kl` for KL.
   - This replaces `kl_progression`; `progression.py`'s stubs are removed and `tests/test_analyses.py` is updated.
6. **`replacement_times(A, anchor, censor) -> pl.DataFrame`.** `ID, SIDE, time_yr, event`.
   - Time runs from the anchor visit day to the replacement day.
   - **Censoring:** under `tkr.censor = "last_visit"`, a knee is censored at the latest `V##VISDYS` across AllClinical visits after the anchor (V14 included).
   - **A replacement after that day** is still an event at its own day, because OUTCOMES99 adjudicated it.
   - **A counted replacement with a blank day** is excluded and counted in the module's flow output.
   - **Knees replaced at or before the anchor** are excluded.
8. **`jsw_change(A, anchor, horizon) -> pl.DataFrame`.** `ID, SIDE, base_mm, end_mm, change_mm, years, progressor`.
   - **Source:** medial minimum JSW (`V##MCMJSW`) from `kXR_QJSW_Duryea`.
     - It has one reading project (16) at every visit through V10 (96 months); there is no V12.
     - Project 16 measured every knee with ROA up to 48 months, the non-exposed controls and many knees without ROA (some chosen at random). It followed them at 72 and 96 months unless they were end-stage (JSN 3) by 48 months.
     - Of about 2,900 KL 2–3 knees at 48 months, about 2,050 have a measured width at both 48 and 96 months.
   - **Change:** `change_mm` = end − base, so a loss is negative.
   - **Progressor (user, 2026-11-12):** `progressor` = a loss of at least `jsw.threshold_mm` (0.7, the FNIH threshold; Eckstein 2015). The continuous `change_mm` is also reported.
     - Under `jsw.middle = "keep"` (default) every other knee is a non-progressor.
     - Under `"exclude"`, knees losing more than `jsw.nonprogressor_mm` (0.5) but less than 0.7 are null, as in FNIH's non-progressor definition.
   - **Missing widths:** null where either width is missing.
   - **Horizon:** a horizon beyond V10 falls back to V10, and that fallback is recorded in the analysis's flow.
   - **Replaces** the `fnih_jsw_progressor` stub.
   - **Window caveat:** FNIH set the 0.7 mm threshold for 24–48 months from baseline, not for a four-year window. The README of any analysis using it says so.
9. **`selection_counts(status, anchor, visits) -> pl.DataFrame`.** `visit, knees_at_risk, read, unread, by_project`, for any analysis's flow.

## Ledger keys the module reads

The analysis carries these. Defaults are noted where an analysis's ledger may omit a key (the `incident_soa.setting` pattern).

| Key | Default | Notes |
|---|---|---|
| existing `outcomes.*` and `cohort.reading_project` | — | inherited from the outcome-defining analysis |
| `outcomes.roa_replacement` | `"ignore"` | Luyten sets `"event"`; the value names are luyten's |
| `readings.anchor_project` | `"followup"` | variant `"p15"` |
| `progression.jsn_rule` | `"whole_grade"` | variant `"within_grade"` |
| `readings.followup_project` | `"latest"` | `open`, everywhere it appears |
| `tkr.censor` | `"last_visit"` | |
| `jsw.threshold_mm` | 0.7 | FNIH |
| `jsw.middle` | `"keep"` | variant `"exclude"` (FNIH 0.5–0.7 mm middle as null) |
| `jsw.nonprogressor_mm` | 0.5 | |

## Proof

- `luyten_early_oa` calls `knee_status` and `by_horizon(anchor="00")`; its local `for_side`, `roa_series` and `by_horizon` are deleted.
- Before and after, `oai run luyten_early_oa` gives byte-identical aggregate outputs (default and every variant), and the knee frame `DataFrame.equals`.
- The module's own tests use inline frames for every function in items 2–5 and 7. They cover:
  - the unknown middle visit (span 2);
  - a replacement as the event;
  - an unread knee giving a null, not False;
  - project preference.

## Builder's calls (mine, for the user to check)

- **Module name:** `oai.derive.knee_outcomes`. `progression.py` is removed rather than kept as an alias.
- **The defaults** in the ledger-key table above.
- **The anchor grade comes from the follow-up reading project.** This is the one call most worth checking.
  - Default: base and follow-up from one reading project.
  - Variant: Project 15 base.
- **Whole-grade JSN** is the default.
- **Replacement after the last visit** counts as an event.
- **READPRJ 42 → 37.**
- **`analyses/progression_definitions`** stays a stub. Its README points to the module, and its endpoints step will be the module's showcase once FNIH and WOMAC are added (TODO.md).
