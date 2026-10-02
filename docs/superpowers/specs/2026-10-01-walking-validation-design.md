# Walking Validation Study — Design

**Date:** 2026-10-01
**Status:** Implemented (see §15 Amendments)
**Builds on:**
- `2026-09-30-assumptions-and-lo2022-replication-design.md`
- `2026-09-30-reporting-module-and-lo2022-comparison-design.md`
- `docs/reference/oai-activity-agreement-analysis-plan.md` §1–9

## 1. Purpose

Lo et al. 2022 (Arthritis Rheumatol 74:1660–7) found that walking for exercise was associated with less new frequent knee pain and less structural worsening. Its exposure is the 96-month Historical Physical Activity Survey item "walked for exercise since age 50". Zhang et al. 2024 reused the same item. Neither paper validated it.

This study asks two questions:
1. Does the item rank and classify people consistently with OAI accelerometry?
2. Is its misclassification differential by knee status or by outcome, and how far could that misclassification move the published odds ratios?

PASE serves as a benchmark. The full PASE agreement analysis (Bland–Altman, κ, cutpoint) is a later paper and stays out of scope.

## 2. Background and novelty

PubMed review, October 2026:
- **No full paper validates any OAI self-report against OAI accelerometry.** The only near-overlap is an ACR 2012 abstract (Ahn, Dunlop et al.; n = 1,555; PASE total; correlations only). It was never published as a paper.
- **The walking item has never been validated against a device.**
  - Lo 2022: PMID 35673832.
  - Zhang 2024: PMID 38206636.
  - The source instrument (Kriska 1988, PMID 3358406) has test–retest data only.
- **Non-OAI PASE-versus-device validations are small** (n ≤ 160; ρ 0.06–0.49).
- **Few OAI papers use both measures.** Of 42 OAI physical-activity papers, only one used both PASE and accelerometry (Budarick 2021, PMID 34802082).

Before submission:
- confirm with the OAI accelerometry investigators that Ahn 2012 was never written up;
- check the van der Zee-Neuen 2019 tables (PMID 31248586).

## 3. Data facts (local release, verified 2026-10-01)

**Device**
- ActiGraph GT1M, hip-worn, 7 days, 60-second epochs, counts only. There are no steps in the release or in NDA's `oai_accel*01` structures.
- Two waves:

| Wave | Eligible | Valid (≥4 days of ≥10 h) |
|---|---|---|
| 48 months (V06) | 2,712 | 1,927 |
| 72 months (V08) | 1,797 | 1,394 |

  1,343 people are valid at both waves.
- Release processing: non-wear is ≥90 minutes of zeros with ≤2 interrupting minutes under 100 counts. Bouts use an 8-of-10-minute rule.
- Files: summary, day-level and minute-level. The minute files have 20.6M rows (V06) and 14.9M (V08). Device start is a median of 1 day after the clinic visit.

**Walking item (V10)**
- `V10WLKAR4`: walked for exercise ≥20 minutes per day, ≥10 times, at age 50 or older. 2,582 answered (2,049 yes).
- Amounts are banded: `V10WKYRAR4` (years), `V10WKMOAR4` (months per year), `V10WKTMAR4` (times per month).
- 62–64% of answers fall in the top months and times categories.

**PASE**
- Collected at V00, V01, V03, V05, V06, V08 and V10.
- Walking subscore from `VxxPASE2` (days) × `VxxPASE2HR` (hours per day).

**Overlaps**
- Walking item × either valid wave: 1,566.
- Lo 2022 cohort (1,188 persons) × answered the walking item × either valid wave: 767 (599 walkers, 168 non-walkers; see amendment 10).

## 4. Key decisions

| Decision | Choice | Reason |
|---|---|---|
| Lead question | Validity of the Lo 2022 exposure | Most novel; never validated; bears on two papers |
| Payoff | Validity plus a quantitative bias analysis | Answers whether the published exposure can be trusted |
| Bias analysis | Record-level probabilistic analysis (main); summary-level correction (supplement) | Record level keeps clustering and adjustment. The supplement is reproducible from the paper |
| Device measure | Released counts now; steps and cadence added when obtained | Steps are not public (§3); the request runs in parallel (§11) |
| Waves | Mean over the valid waves each person has (primary); each wave alone (variants) | Habitual activity; the 72-month wave is closer to the survey |
| Where | New `analyses/walking_validation/` | `activity_agreement` stays for the PASE agreement paper |
| Shared code | Walking exposure → `oai.derive.walking`; GEE fit → `oaimodels::fit_knee_gee()` | One coding and one model for both analyses |

## 5. Measures

**Exposure (being validated).** The walking item, coded exactly as `lo2022_walking` codes it, through the shared `oai.derive.walking`:
- the binary walker;
- a 3-level amount: none, then the lower and upper halves of the lifetime-sessions total, which is years × months per year × times per month, using category midpoints as in Lo 2022.

**Device measures**, derived from the minute files by `oai.derive.accel`:
1. **Purposeful-walking proxy:** minutes per day in ≥10-minute bouts at ≥2,020 counts per minute.
2. **Total daily counts.**
3. **Light-intensity minutes per day** (100–2,019 counts per minute).

Each person's value is the mean over their valid waves. Per-wave values are kept for variants and for between-wave reliability.

**Device-defined habitual walker** (reference for sensitivity and specificity): bout-days per week is (valid days with ≥1 purposeful bout ÷ valid days) × 7 for each wave, then averaged over the person's valid waves. A person is a habitual walker if this is ≥2. Variants:
- any bout;
- ≥150 bouted minutes per week.

**Strata for differential misclassification:**
- KL grade of the worse knee at baseline;
- frequent knee pain at baseline in either knee;
- within the Lo subset, each outcome at person level (any knee with the event): new pain, KL worsening, JSN worsening, and pain resolution.

**Covariates (adjusted contrasts):** age, sex, BMI.

## 6. Validity analyses (`validity` step, R)

Samples:
- the validation sample (n ≈ 1,566);
- the Lo subset (n = 767), repeated where strata require it.

Analyses:
1. **Known groups.** Device measures by walker status: medians, Hodges–Lehmann differences, rank-biserial effect size, and median regression adjusted for the covariates.
2. **Dose–response.** Device measures across the 3 amount levels: Jonckheere–Terpstra test and adjusted median regression.
3. **Convergent ranking.** Among walkers, Spearman ρ between lifetime sessions and each device measure. Each ρ is also deattenuated using the between-wave ICC estimated in people valid at both waves.
4. **Classification.**
   - Sensitivity, specificity, PPV and NPV of walker status against the device habitual walker, with person-level bootstrap 95% CIs.
   - AUC of lifetime sessions for identifying the device walker.
5. **Differential misclassification.**
   - Sensitivity and specificity by stratum (§5), with CIs.
   - Logistic regression of correct classification on stratum, reporting the difference with its CI.
   - Labelled exploratory where cells are small.
6. **PASE benchmark.** Items 1, 3 and 4 for the PASE walking subscore at V06 and V08 (adjacent to the device weeks) and at V10 (same visit as the walking item).

**Framing in Methods:** the device measures current activity, while the item asks about walking since age 50. The device is therefore an imperfect reference. Sensitivity and specificity are convergent-validity estimates, and the bias analysis uses them as distributions, not as truth.

## 7. Bias analysis (`bias` step, R)

**Inputs.** Sensitivity and specificity in the Lo subset as Beta distributions: Beta(TP + 1, FN + 1) for sensitivity and Beta(TN + 1, FP + 1) for specificity.
- **Non-differential scenario:** one pooled pair.
- **Differential scenario:** one pair per level of the outcome being modelled, at person level.

**Each iteration** (default 2,000 per outcome; seeded):
1. Draw sensitivity and specificity. Discard draws that imply a negative true prevalence in any stratum.
2. Compute each person's probability of being a true walker given their observed answer and stratum (PPV and NPV from sensitivity, specificity and the observed prevalence).
3. Redraw walker status for all 1,188 persons. Knees inherit the person's draw.
4. Refit the unadjusted and adjusted GEE models with `oaimodels::fit_knee_gee()` (exchangeable correlation, covariates as in Lo 2022).
5. Add random error by drawing log-OR from Normal(estimate, SE).

**Outputs** per outcome × model × scenario:
- median bias-adjusted OR;
- 95% simulation intervals, for systematic error only and for systematic plus random error;
- the share of iterations in which the published conclusion holds (same direction, and an interval that excludes 1 when the published result was significant);
- the number of discarded draws.

**Tipping-point grid.** Fixed sensitivity 0.60–1.00 × specificity 0.40–1.00 in steps of 0.05, non-differential. For each cell, the bias-adjusted OR (median of 200 iterations) and whether its interval still excludes 1. This does not depend on the device being a valid reference.

**Summary-level supplement.** The same draws applied to the published Table 2 walker and non-walker event counts with the standard misclassification-correction formulas, giving corrected unadjusted ORs.

**Exposure coding.**
- **Primary:** `exposure.yes_without_amount_as = "non-walker"`, which reproduces the published 887 walkers.
- **Variant:** the replication's current default coding.

If the original authors confirm their coding, the primary becomes "as published", with no other change.

## 8. Implementation in the suite

**Analysis folder `analyses/walking_validation/`:**

| Step | Lang | Output |
|---|---|---|
| `device` | Python | Person-wave device measures, in the work directory (frame; never in results) |
| `cohort` | Python | Validation sample, Lo subset, exposure, strata and outcomes (frame); `flow.csv` |
| `validity` | R | `validity_*.csv`, `metrics_validity.csv` |
| `bias` | R | `bias_pba.csv`, `bias_tipping.csv`, `bias_summary_level.csv`, `metrics_bias.csv` |
| `compare` | Python | `comparison.csv`: device-reproduction checks (§9) and sample sizes, graded by `oai.replication` |

- **Inputs:** `[inputs]` declares:
  - `accelerometry:06`, `accelerometry:08`;
  - `acceldatabymin:06`, `acceldatabymin:08`;
  - `acceldatabyday:06`, `acceldatabyday:08`;
  - `allclinical:00`, `allclinical:06`, `allclinical:08`, `allclinical:10`;
  - `kxr_sq_bu:00`;
  - `enrollees`.
- **Lo cohort and outcomes come from the replication's frame.** The `cohort` step reads `OAI_WORK_DIR/lo2022_walking/<label>/frame.parquet`, where `<label>` is the replication run matching the exposure coding (`walker_requires_amount` for the primary). If that frame is missing, it stops with "run `oai run lo2022_walking` first" for the default label, or "run `oai run lo2022_walking --variant <label>` first" for any other. This reuses the replication's cohort, knee-level outcomes and covariates exactly, rather than rebuilding them. The shared `oai.derive.walking` is still needed, for the wider validation sample (every walking-item respondent).
- **Report:** `[report]` → `report.qmd`, using `oaireport`. Figures:
  - forest plot of bias-adjusted ORs beside the published and replicated ORs, per scenario;
  - sensitivity and specificity by stratum;
  - tipping-point heatmap (sequential blue);
  - known-groups distributions.

**Shared code**
- **`oai.derive.walking`:** the walking-exposure coding moves here from `analyses/lo2022_walking/lo2022.py`. A regression test requires the replication's `comparison.csv` (`default` and `walker_requires_amount`) to be identical before and after.
- **`oai.derive.accel`:**
  - lazy minute-file reader;
  - non-wear detection (threshold minutes; interruption count and ceiling);
  - valid days (minimum wear hours);
  - bouts (minimum length; tolerance as either an "8 of 10" rule or a maximum drop-below);
  - daily and person-wave summaries.

  All parameters are arguments, set from the assumptions ledger.
- **`oaimodels::fit_knee_gee(data, outcome, rhs, corstr)`:** extracted from `lo2022_walking/models.R`. It returns OR, lower and upper bounds, and the log-OR SE, and the replication's `models.R` calls it.

**Assumptions ledger** (`assumptions.toml`)
- Device rules: non-wear minutes (90); interruption allowance (2 minutes under 100 counts); valid-day hours (10); minimum valid days (4); MVPA cutpoint (2,020); bout minimum (10); bout tolerance.
- Measures: habitual-walker definition; wave combination; amount split.
- Exposure coding: `exposure.yes_without_amount_as`, as in `lo2022_walking`.
- Bias analysis: iterations, seed, and how the priors are built.

Variants: `wave48`, `wave72`, `walker_any_bout`, `walker_150min`, `nonwear60`, `exposure_replication_coding`.

**Disclosure.** Participant-level device measures stay in frames under `OAI_WORK_DIR`. Results are aggregate, and the egress check must pass.

## 9. Testing

- **Device derivation, synthetic.** Minute fixtures with known non-wear blocks, interruption edge cases, valid and invalid days, and bouts under each tolerance rule. Exact expected minutes.
- **Device derivation, real data (`realdata`).** With the release's rules, `oai.derive.accel` reproduces:
  - the valid-person counts (1,927 and 1,394);
  - per person-day wear hours and Troiano MV minutes in the by-day files (exact, or within 1 minute where the release rounds);
  - the summary file's `VxxANVDAYS`.

  These are also graded rows in `comparison.csv`.
- **Shared exposure refactor.** The replication's outputs are byte-identical before and after (`realdata`). Existing unit tests still pass.
- **Bias analysis, unit tests:**
  - with sensitivity and specificity fixed at 1, every iteration returns the observed OR;
  - with fixed values below 1 on a small synthetic cohort, the summary-level correction matches the closed-form result.
- **Bias analysis, simulation test (runs by default; about a second).** Generate a cohort with known true OR and known non-differential misclassification. The probabilistic analysis's median adjusted OR is within 0.05 of the truth over a fixed seed.
- **Validity statistics.** Small synthetic datasets with known Spearman, sensitivity and specificity, and Hodges–Lehmann values.
- **Report.** Renders end to end (`realdata`), and egress passes.

## 10. Precision

| Estimate | n | Approx. 95% CI half-width |
|---|---|---|
| Sensitivity, specificity (validation sample) | ~1,566 | ±0.02–0.04 |
| Sensitivity (Lo subset) | 240 device walkers | ±0.04 |
| Specificity (Lo subset) | 527 device non-walkers | ±0.04 |
| Specificity, per outcome stratum | | ±0.10–0.20 |
| Spearman ρ | ~1,200 walkers | ±0.06 |

The probabilistic bias analysis carries the imprecision of specificity within outcome strata. The tipping-point grid shows results regardless of it.

## 11. External dependencies and sequencing

- **Step data (optional upgrade).** GT1M steps (ideally per minute, for cadence) are not public. The processed step data appears to be held by the OAI accelerometry ancillary-study team at Northwestern. The authors of Lo et al. 2015 (Arthritis Rheumatol 67:2897–904, which used OAI step counts) are the natural route for the request.
  - When received, the data goes under the planned data root's `external/` folder (separate design).
  - `oai.derive.accel` gains steps per day and minutes at ≥100 steps per minute as an alternative criterion (new ledger variant).
- **Exposure coding.** Depends on the original authors' answer about "yes" walkers with no amount answers (already in `TODO.md`).
- **Build order:**
  1. Shared-derivation refactor.
  2. Device derivation, reproducing the release.
  3. Cohort and validity.
  4. Bias analysis.
  5. Report.

## 12. Error handling

- Missing minute files or tables raise an `OAIError` naming the table. This is the same fail-fast behaviour as the planned `[inputs]` check.
- A person with no valid wave is excluded and counted in `flow.csv`.
- Bias-analysis draws that imply negative prevalence are discarded and counted. If more than 10% of draws in a cell are discarded, the cell is flagged in the output.

## 13. Out of scope

- The full PASE agreement analysis (Bland–Altman, κ, PASE cutpoint): the later `activity_agreement` paper.
- Regression calibration of a continuous exposure.
- Validating other historical activities (running, cycling).
- The consolidated data-root change: a separate bounded design.

## 14. Open questions

- The exact habitual-walker threshold could be informed by the distribution of purposeful-bout days in the validation sample. The primary definition is fixed before outcomes are examined, as above.
- Whether a second paper should report the PASE agreement aims using the same device derivation (likely yes; `activity_agreement`).

## 15. Amendments (2026-10-01, from planning-time prototypes)

These supersede the sections they name.

1. **Device algorithm (§5, §9).** A prototype on both waves showed that the release's processing is reproduced exactly when two rules are applied together:
   - non-wear runs are found within each calendar day (`PAStudyDay`) and need ≥90 minutes, not >90;
   - an MV bout spans its start through its last minute at or above the cutpoint, including its interior below-cutpoint minutes.

   Results:

   | | 48 months | 72 months |
   |---|---|---|
   | Release person-days matched | 13,040 / 13,040 | 9,399 / 9,399 |
   | Wear minutes identical | 99.75% | 99.60% |
   | MV and bout minutes identical | 100% | 100% |
   | Valid persons (ours / release) | 1,928 / 1,927 | 1,394 / 1,394 |

   The §9 tests use these tolerances.
2. **Reclassification happens within outcome strata (§7).** PPV and NPV are always computed within outcome strata (person-level case and non-case). Reclassifying with the pooled prevalence would bias every scenario toward the null.
   - The non-differential scenario shares one sensitivity/specificity draw across strata. The differential scenario draws per stratum.
   - Draws with Se + Sp ≤ 1 are discarded and counted, along with those implying an impossible prevalence.
3. **Confidence intervals (§6).** Sensitivity, specificity, PPV and NPV use Wilson intervals: persons are independent rows, so a bootstrap adds nothing for a single proportion. The AUC keeps a percentile bootstrap.
4. **R environment (§8).** The R steps need `quantreg`, which is added only to the `report` renv profile. A new `analysis.toml` option, `[r] profile = "report"` (local-only), makes the runner set `RENV_PROFILE` for that analysis's R steps. The default `r/renv.lock` is unchanged.
5. **Replication link (§8).**
   - **Copied results:** the `cohort` step copies the replication's Table 2 rows (`comparison.csv` `t2.*`, `table2.csv`) into this analysis's results as `lo2022_t2.csv` and `lo2022_table2.csv`.
   - **Reproduction check:** before simulating, the `bias` step stops unless its observed odds ratios equal the replication's (|ΔOR| ≤ 1e-8).
   - **Coding check:** the `cohort` step stops if any Lo-cohort participant's walker coding differs between the two analyses.
6. **Report figures (§8).** The known-groups figure is drawn from aggregate quartiles, not participant-level points, so the PDF stays aggregate.
7. **Validation-sample coding (§5).** Participants who did not answer the walking item are excluded from the validation sample (`missing_as = "exclude"`). The Lo cohort keeps the replication's coding.
8. **PASE walking subscore (§6).** Computed with the Washburn et al. 1993 constants: days 0/1.5/3.5/6, hours 0.5/1.5/3/5, weight 20. The constants are ledgered.
9. **Parallelism (§7).** Bias-analysis iterations run with `parallel::mclapply`, using cores from `OAI_R_CORES`. Iteration i uses `set.seed(seed + i)`, so results do not depend on the core count.
10. **Lo validation subset (§3, §10).** The Lo 2022 participants used for validation and for the bias-analysis priors are those who answered the walking item and have a valid device wave: 767, not 784. The replication codes 18 participants who never answered the item as non-walkers; their answers cannot be validated, so they are excluded from the 2×2 counts but remain in the bias analysis as classified non-walkers.
