# Device-measured walking and incident and progressive knee OA: design

**Question (user, 2026-11-12).** Does walking more protect knees, harm them, or neither? Do changes in walking predict later incidence or progression of knee OA? The reverse is also asked: does incident or progressing OA predict walking less afterwards? This direction also checks the forward result for reverse causation. If knees that are already worsening make people walk less, low steps would look harmful when the knee came first.

The analysis has the same shape as `analyses/crepitus_activity` (both directions, two device waves), with knee OA in place of crepitus. Name: `analyses/steps_oa`.

## Data

**Device.** GT1M at 48 months (V06) and 72 months (V08).
- Per-minute steps come from Northwestern (`OAI_STEPS_DIR`, never in the repo).
- Person-wave measures and device rules are `walking_steps`' (`oai.derive.devices.person_wave`). The `device.*`, `steps.day_rule` and `sample.min_step_days` ledger entries are copied verbatim, with the same identity test that crepitus_activity uses.
- Valid wear: 1,928 people at 48 months, 1,394 at 72 months, 1,343 at both.

**Radiographic OA.** OUTCOMES99 `V99E{R,L}XIOA` (earliest visit with KL ≥ 2) and `XNOA` (last visit known free of it), Projects 15, 37 and 43, coded by visit to V12 (120 months).
- Use the convention of `oai.derive.incident_soa.roa_from_outcomes99` and `crepitus_soa_longterm`: after `XNOA`, ROA is unknown, not absent.
- **Readings after 48 months cover subsets.** `KXR_SQ_BU` has 14,405 knee rows at V06, 7,041 at V08, 6,956 at V10 and 3,435 at V12. Who was read later depends on the reading project, so follow-up is selective. The flow must show it, and the write-up must state it.

**Symptomatic OA.** Frequent knee pain plus ROA, as in `incident_soa.soa_status`. A knee replacement counts as SOA.

**Knee replacement.** OUTCOMES99 `V99E{R,L}KDAYS` (via `oai.derive.knee.knee_replacement`). Its follow-up runs longer than the X-ray readings.

**Grades for progression.** `KXR_SQ_BU{06,08,10,12}`: `V##XRKL` and `V##XRJSM`/`XRJSL` per knee.

## Decisions (user, 2026-11-12)

1. **All three outcome families:** structural, symptomatic and knee replacement.
2. **Incidence leads; progression is secondary.**
3. **Within incidence:**
   - incident radiographic OA leads: a knee going from KL 0–1 at 48 months to KL ≥ 2;
   - incident symptomatic OA is **co-primary**;
   - knee replacement within incidence is secondary.
4. **Both directions** (from the original request).
5. **Follow-up loss in P1 and P2:**
   - **Primary:** a discrete-time model by visit (V08, V10), in which a knee contributes visits until it has the outcome or its readings stop.
   - **Companion check:** a logistic "outcome by V10" model.
6. **Progression readings are selective** (Project 37/42 read only some knees after 48 months):
   - **Primary (c):** KL and JSN progression are descriptive only, and knee replacement carries the progression family.
   - **Sensitivity (a):** models fitted in the knees that were read, with a clear description of who those knees are.
   - No inverse-probability weighting.
8. **Measured joint space width:**
   - **Modeled outcome:** medial minimum JSW (`kXR_QJSW_Duryea`, one project) is the modeled structural progression outcome. It is secondary, because incidence leads.
   - **Definition:** a loss of at least 0.7 mm from 48 to 96 months (the FNIH threshold) leads, with the continuous change in mm alongside.
   - **Why it can be modeled:** its follow-up is nearly complete for non-end-stage OA knees (about 2,050 of 2,900 KL 2–3 knees have both widths).
   - **Within the progression family:** semiquantitative KL and JSN stay descriptive (decision 6). Knee replacement still covers end-stage knees.
7. **MRI-based incidence and progression** are wanted as secondaries. They will come later, from a separate reusable MRI module (its own project). This analysis leaves a slot for them and does not build them.

## Design

### Unit and samples

- **Unit:** the knee, with two knees per person clustered by person (logistic GEE, exchangeable, as in crepitus_activity B3).
- **Incidence sample:** knees with KL 0–1 at 48 months (Project 15 V06 reading, agreeing with OUTCOMES99: not ROA at or before V06), not replaced at 48 months, in people with valid 48-month steps.
- **Incident SOA sample:** knees without SOA at 48 months, i.e. not (frequent pain and ROA). Knees with ROA but no frequent pain at 48 months stay in the sample.
- **Progression sample:** knees with KL ≥ 2 at 48 months, not replaced. The at-risk grades (`progression.risk_kl`) are `open` in `analyses/crepitus`. Carry the same entry here as `open`: default 2–3, variant 1–3. KL 4 knees can only progress by replacement.
- **Readings after 48 months were chosen by design** (`kXR_SQ_BU_Descrip.pdf`). Project 37/42 read the 72- and 96-month films for three groups:
  - knees still at risk of incident ROA;
  - knees that became ROA by 48 months;
  - a random selection of knees that were KL 2–3 at baseline.

  For incidence, the readings are complete by design. For progression they are not.
- **Which 48-month KL defines the samples (builder's call):** the reading OUTCOMES99 itself relies on, so that sample entry and outcome come from one source. Project 37 readers saw the Project 15 scores and could revise them. This becomes a ledger entry: `readings.anchor_project` in the shared knee-outcomes module (`2026-11-12-knee-outcomes-module-design.md`), with the Project 15-only reading as a variant.
- **Replacement in the progression family (builder's call):** the Cox model includes KL 2–4 knees, because replacement is the only way a KL 4 knee can progress. The KL and JSN outcomes keep the `progression.risk_kl` set.

### Exposures

- **E1:** steps/day at 48 months, mean over valid days, per 1,000.
- **E2:** the change in steps/day from 48 to 72 months, per 1,000, in a model that also holds steps at 48 months. People valid at both waves; wear at both waves adjusted, as crepitus_activity's final review settled.
- **Shape (builder's call, marked as such):** the primary estimate is linear per 1,000 steps/day. Beside it, each primary model reports:
  - steps in four fixed bands: < 5,000, 5,000–7,499, 7,500–9,999 and ≥ 10,000 (Tudor-Locke's bands), with < 5,000 as the reference;
  - a restricted cubic spline, 3 knots, with its test of non-linearity and a plotted curve.

  This lets either "protects" or "harms", or a U shape, show up without having to pick one in advance.

### Forward models (walking → OA)

**Primary, pre-named (two estimates):**
- **P1:** E1 → incident ROA by 96 months (V10), Model 1.
- **P2:** E1 → incident SOA by 96 months, Model 1.

The outcome counts by V08 or V10. 120 months (V12) is a provisional horizon variant, as in `crepitus_soa_longterm`.

**Secondary:**
- **S1, change in walking → incidence:** E1 + E2 → incident ROA and SOA at V10 (or V12, provisional), in knees still free of the outcome at 72 months.
- **S2:** E1 and E1 + E2 → knee replacement in the incidence sample.
  - Report the event count first.
  - Fit a model only if there are at least 20 events (builder's call). Otherwise give the counts by step band.
- **S3, progression** (decision 6: KL and JSN are descriptive; they are modeled only in the read-knees sensitivity analysis), in the progression sample:
  - KL worsening of ≥ 1 grade by V10;
  - medial or lateral JSN worsening of ≥ 1 grade by V10;
  - knee replacement: a Cox model over the full OUTCOMES99 follow-up from the 48-month visit, clustered by person (builder's call, because replacement follow-up is longer).

  Each is fitted for E1, and for E1 + E2 with the outcome after 72 months.
- **KL transitions (user, 2026-11-12).** Every progression table and the descriptives annotate the KL transition: 0–1 → 2+, 2–3 → 4, and any ≥ 1 grade.
  - 2–3 → 4 (with replacement counted as KL 4) is reported by step band. It is modeled only in the read-knees sensitivity analysis, because the readings are selective.
  - 0–1 → 2+ from the KL readings is shown beside P1's OUTCOMES99 incidence, as a check that the two agree.
- **S3b, measured JSW**, in the progression sample (KL 2–3 at 48 months, `progression.risk_kl`):
  - outcome: loss of at least 0.7 mm by 96 months (logistic GEE);
  - companion: the change in mm (gaussian GEE);
  - each fitted for E1, and for E1 + E2 (people valid at both waves);
  - Model 2 adds the base width.
- **S4:** MV minutes/day from counts as a second exposure for P1 and P2 only, reported in a supplementary table.

### Reverse models (OA → walking)

These use one row per person and linear models with sandwich SEs, as in crepitus_activity direction A.
- **R1, preceding:** a new ROA or KL worsening in either knee between 36 and 48 months → steps at 72 months, adjusted for steps at 48 months.
- **R2, concurrent:** a new ROA, KL worsening or knee replacement in either knee between 48 and 72 months → steps at 72 months, adjusted for steps at 48 months.
- **R3, cross-sectional and descriptive:** steps at 48 months by the higher KL grade and by SOA status at 48 months.

Each reverse exposure is coded as "any knee" (yes/no). A count of knees (0/1/2) is a variant, matching crepitus_activity.

**R2's exposure (builder's call).** R2 uses new ROA and knee replacement only. Both are complete by design. KL worsening is limited to the knees that were read, as variant `r2_kl_worsening_read`. Otherwise "missing → null" would drop every person with an unread knee and turn R2 into a mostly early-OA sample.

### Covariates

- **Model 1:** age, sex, BMI and wear hours/day at each exposure wave in the model.
- **Model 2:** Model 1 plus:
  - for the knee-level forward models, that knee's KL grade and that knee's WOMAC pain at 48 months. KL is 0 vs 1 for incident ROA and 2 vs 3 for progression. For incident SOA it is categorical, 0–4, because that sample keeps ROA knees without frequent pain (builder's call);
  - for the reverse models, as in crepitus_activity: the higher KL grade and the worse knee's WOMAC pain.

  Pain may be a confounder or a mediator, so both models are reported.

### Sensitivity variants (ledger)

- `horizon_120`: outcomes to V12 (provisional).
- `roa_kl2_jsn`: ROA = KL ≥ 2 with JSN (`XIOAN`).
- `exclude_baseline_pain`: drop knees with frequent knee pain at 48 months from P1 and S1. This guards against reverse causation from pain that has not reached an X-ray yet.
- `progression_kl_1_to_3`: as in `analyses/crepitus`.
- `log_steps`: log(steps + 1).

### Reporting

- **Flow per sample,** including how many knees have no later reading (the selective-reading caveat).
- **Primary estimates:** P1 and P2 lead the results, each with its band and spline displays.
- **P2 split by ROA at 48 months (builder's call, pre-specified):** P2 is also reported separately for knees with and without ROA at 48 months. The two groups become SOA by different routes: one through new pain, the other through new ROA. The pooled estimate could hide opposite effects in the two groups.
- **Secondary estimates** are grouped by family. As in crepitus_activity, the number whose 95% CI excludes the null is set beside the number expected by chance, with no p-value-driven selection.
- **Every estimate** shows n and the cases (forward) or the mean outcome (reverse) per level.
- **Neutral framing:** report "associated with", with no causal "protects" or "harms" in the results. The design limit is stated as in crepitus_activity: with two device waves, the analysis shows which measure moves first, not why.

### Before the write-up

Check PubMed for published OAI or MOST work on device-measured activity or steps and incident or progressive knee OA, and record it in the analysis README. The results should be read against whatever exists.

## Out of scope

- cadence and bout-based walking definitions;
- PASE and the Walking Question;
- MRI and quantitative JSW (FNIH);
- WOMAC-only symptomatic progression;
- latent trajectory models.

## Authorship note

The step data come from Northwestern. Its analyst, Jing, is to be a co-author on publications that use them, and the PARR group offers scientific input (memory: nw-step-data).
