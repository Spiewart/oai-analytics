# Who says they walk but doesn't walk by steps: design

## Intent

Self-reported walking agrees poorly with step-measured walking in OAI. This holds for the 96-month walking item (specificity about 0.23–0.25 against step bouts) and for PASE item 2 (about 0.24–0.25). The user has no ready explanation.

Almost all the disagreement is one kind. About 80% answer "yes", but only 24–37% are device walkers. The analysis therefore compares the two groups among people who said yes:

- **Yes, step walker:** answered yes and meets the device walking definition.
- **Yes, not a step walker:** answered yes and does not.

The aim is to find out whether these groups differ systematically on other OAI measures: demographics, knee disease, general health and mood, self-reported activity, and the device week itself. The comparison covers their level at the device visit and their trajectories over time. This is hypothesis-generating work for the user and collaborators (the original investigator and the Northwestern accelerometry group).

## Goals

1. **Stage 1, screen.** A descriptive comparison of the two "yes" groups across a broad set of measures:
   - the level at 48 months;
   - change from baseline to 48 months;
   - change from 48 to 96 months.

   Differences are standardized effect sizes, with no p-values.
2. **Stage 2, trajectories.** For every time-varying measure, a longitudinal model over the visits from baseline to 96 months with a group × visit term. It asks whether the groups' paths diverge before, during or after the device weeks, with correction across measures.
3. **Replication.** Repeat both stages for PASE item 2 at 48 months ("any walking") against its own device week, and for the count-based MV bout definition, to see whether the same measures stand out.

## Non-goals

- **No predictive model of disagreement.** That is approach 2, which was considered and dropped (see Approaches).
- **No correction of the self-reports or of earlier results.** Nothing here feeds back into the Lo 2022 or PASE analyses.
- **No new device definitions.** The definitions are the existing `walking_steps` ones.

## Anti-goals

- **Wording.** Language must not imply that the "yes, not a step walker" group misreports. The user's settled framing applies: the item and the device may measure different things. Documents avoid "bias", "over-report", "false positive", "correction" and "misclassification of the respondent". Groups are named neutrally.
- **Data leaving the machine.** Results hold aggregates only, and small cells follow the repo's egress rules.
- **Unplanned comparisons.** No measure is added after looking at stage-1 results without a ledger entry saying so.

## Constraints

- **Sample and coding.** The sample and device classification are those of `walking_steps` Part 2 (`persons` and `pro_validity`). Valid waves, step-complete days and `exposure.yes_without_amount_as = "non-walker"` are reused, so the group sizes match the 2×2 tables already sent: 341 vs 910 for the item with step bouts, and 424 vs 1,069 for PASE at 48 months.
- **Data.** The per-minute steps stay in `OAI_STEPS_DIR`. Person-level frames go to `OAI_WORK_DIR`, never to results.
- **Names.** Collaborators are referred to by role in anything committed.
- **Measure names.** Every measure is checked against the release's `*_Contents.pdf` before it is coded.

## Approaches

1. **A descriptive comparison at the device visit, plus change scores.** Fast and readable. Change scores use only two points, and a broad set means many comparisons, so this can only point to leads.
2. **One logistic model predicting "yes, not a step walker" from the whole set.** It gives mutually adjusted estimates. With dozens of correlated measures, though, the estimates are unstable and hard to read, which suits an open search poorly.
3. **Mixed models of each time-varying measure by group over all visits.** These use every visit and answer the longitudinal question directly.

**Chosen by the user: 1 for everything, then 3 for the time-varying measures.** Approach 2 was dropped because a broad set makes it fragile. It could follow later if a few measures stand out.

## Decided

### By the user

- **Groups:** "yes, step walker" against "yes, not a step walker".
- **Measures:** a broad set from all three areas (knee disease, how people answer questionnaires, the device week).
- **Time:** include longitudinal trends. This mirrors the `crepitus_activity` analysis (level at a visit, change before, change during), whose results were null.

### By Claude (the user can correct these)

**Primary comparison.**
- The 96-month item against step bouts at ≥100 steps/min on ≥2 days a week, over the mean of valid waves (`steps_100:bout_days`).
- This is the step-based reference already shown to the collaborators.

**Replications.** Each repeats both stages:
- the same item against the count MV bout (`counts_mv:bout_days`);
- PASE item 2, any walking at 48 months, against the 48-month wave's step bouts.

**Reference column.** Stage 1 also shows the "no" group as a third column (about 314 people for the item). It is for context only and gets no effect sizes. It shows whether the "yes, not a step walker" group looks more like the "no" group or like the step walkers.

**Visits.**
- Stage 1: level at 48 months (the first device wave); change from baseline (00) to 48 months; change from 48 to 96 months.
- Stage 2: every visit with the measure, from 00 to 96 months.
- The 96-month item is asked at 96 months, so the 48→96 change covers the period up to the answer.

**Measures.** Every name must be verified against the Contents PDFs. TV means time-varying.

- **Demographics and context (fixed):**
  - age at 48 months, sex, race (`P02RACE`);
  - education (`V00EDCV`) and income (`V00INCOME`);
  - marital status (`V00MARITST`) and employment (`V##CEMPLOY`, TV);
  - OAI subcohort (`V00COHORT`) and clinic site.
- **Body and general health (TV):**
  - BMI (`P01BMI` at baseline, then `V##BMI`);
  - comorbidity score (`V##COMORB`);
  - SF-12 physical and mental summaries (`V##HSPSS`, `V##HSMSS`);
  - CES-D depression score (`V##CESD`).
- **Knee disease (TV):**
  - worse-knee KL grade, from the existing reading-project rules (`oai.derive.knee` / `knee_outcomes`);
  - worse-knee WOMAC pain (`construct.womac_pain`), function and walking difficulty (`construct` measures);
  - frequent knee pain in either knee;
  - KOOS sport score;
  - 20-m walk pace (`V##20MPACE`) and 400-m walk time (`V##400MTIM`);
  - any knee replacement by the visit.
- **Self-reported activity (TV):**
  - PASE total, and total minus walking;
  - the PASE component items in `oai.derive.construct.MEASURES`.
- **The walking item's own amount answers (fixed, item analysis only):** years, months a year and times a month walked. These describe the "yes" answers and are not compared over time.
- **The device week (fixed per wave):**
  - valid days, wear hours a day, and season of the monitoring week;
  - weekday/weekend balance of valid days.
  - Steps/day and MV minutes/day are shown for context but labelled as part of the group definition, not as findings.

**Stage 1 statistics.**
- Continuous measures: means (SD) or medians (IQR) by group, with a standardized mean difference (pooled SD) and a bootstrap 95% CI.
- Binary or categorical measures: shares by group, with Cohen's h or the categorical SMD.
- A pre-fixed reading rule, recorded in the ledger before computing:
  - |SMD| < 0.1 is negligible;
  - 0.1–0.2 is small;
  - ≥ 0.2 is a lead worth looking at.
- No p-values.

**Stage 2 statistics.**
- **Model:** for each TV measure, measure ~ group × visit (visit categorical) + age at baseline + sex, with a random intercept per person.
  - Continuous measures use a linear mixed model.
  - Binary measures use a logistic GEE (exchangeable correlation), as in `walking_validation`'s construct models.
- **Reported per measure:** the adjusted group difference at each visit, and the group × visit interaction test.
- **Correction:** Holm across measures within each comparison (primary and each replication).
- **All TV measures go into stage 2, chosen in advance, not only stage-1 leads.** This keeps stage 2 from depending on what stage 1 found.

**Knee replacement (the user's choice).** After a replacement, knee-level measures keep their recorded values: worse-knee WOMAC pain, function and walking difficulty, and frequent pain. KL for that knee is set to 4, as `progression.replacement_as_kl4` does. A sensitivity analysis censors the replaced knee from the replacement visit on. It is reported beside the main result for every knee-level measure in both stages.

**Device week and anchor (after the builder check).**
- Groups come from the mean over valid waves, as in `pro_validity`, so people whose only valid wave is 72 months stay in.
- Clinical measures are anchored at the 48-month clinic visit for everyone, whatever their device validity at that wave.
- Device-week descriptors (valid days, wear hours, season, weekday/weekend balance, steps and MV minutes for context) are averaged over the same valid waves that define the group. The replication on PASE at 48 months uses the 48-month wave only.

**Measures missing at an anchor visit (after the builder check).** A stage-1 window uses the nearest visit where the measure was collected, and the screen table reports the visits actually used. This is expected for the 400-m walk at baseline and for KOOS or 20-m pace at some visits. If no visit within one scheduled visit of the anchor has the measure, that window is left blank for that measure. The rule is recorded in the ledger before computing.

**KL coverage (after the builder check).** KL comes from the reading projects, which cover only selected people. It is used as is. Coverage by group and visit is reported alongside the results. If coverage differs between the groups by more than 10 percentage points, KL results carry that caveat and are not listed as a lead.

**Missing data.** Each measure uses everyone with a value. Stage 1 reports the n for every cell. Stage 2 uses all available visits per person, with no imputation. Attrition by group is reported.

**Where it lives.** New steps in `analyses/walking_steps`, which already holds the self-report and device classifications:
- `discordance_frame`: Python; builds the person-level frame and the long visit table, both written to `OAI_WORK_DIR`.
- `discordance_screen`: Python; stage 1.
- `discordance_trends`: R; stage 2, reusing the `walking_validation` LME/GEE helpers where they fit.
- A new report section, or a separate short report document. That is the builder's call, matching the existing report style.

**Group names in outputs:** "Yes, step walker", "Yes, not a step walker" and "No".

## Outputs (`$OAI_RESULTS_DIR/walking_steps/<label>/`)

- `discordance_flow.csv`: people per group, per comparison and per visit.
- `discordance_screen.csv`: per comparison and measure (level at 48 months, change from 00 to 48, change from 48 to 96), giving the n, the summaries per group (including "No") and the SMD with its CI.
- `discordance_trends.csv`: per comparison, measure and visit, the adjusted group difference (95% CI), plus the interaction p and its Holm-adjusted p.
- `DISCORDANCE.md`: the leads by the pre-fixed rule, in neutral wording.

## Left to the builder

- Wiring: the step entries, tests on synthetic frames, and README and ledger entries (one ledger entry per decided item above, with sources).
- Exact R helper reuse, and figure design. A forest-style plot of SMDs and small-multiple trajectory plots are suggested.
- Season coding (meteorological seasons from the monitoring start date) and site coding (from enrollment).
