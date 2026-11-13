# Brief report: construct validity of the OAI walking question

Date: 2026-11-05. Status: draft for the user's approval. Nothing here has been built.

## Intent

Write the PASE work up as a Brief Report of Original Research in *Osteoarthritis and Cartilage*.
The reader should come away knowing how far the 96-month question, "walked for exercise since age
50" (`V10WLKAR4`), holds up as a measure of a long-term walking habit in the OAI. The question has
been used as an exposure (Lo 2022), and no full paper has validated it.

The user set the claim as construct validity of the OAI questionnaire. The OARSI 2027 abstract
(`abstract_pase.qmd`, as submitted) is the starting point. The paper adds what a journal reader
will ask for, organized as the facets of construct validity: convergent validity with measures of
the same construct, divergent validity from measures of other constructs, and discriminative
validity across knee OA severity. PASE is a comparison measure, not a reference standard, so the
manuscript says "convergent validity with PASE", not "validated against".

## Decisions

**By the user**

- Journal format as the user pasted it: main text up to 2,000 words, structured abstract up to 250
  words, at most 2 tables and figures combined, typically 15 references.
- Main claim: construct validity of the walking question, with convergent, divergent and
  discriminative evidence as its facets. The conclusion is worded by which facets hold.
- PASE-based, with no accelerometer results. This was decided after the case for a short device
  paragraph had been made; do not reopen it.
- Add a comparison on non-walking PASE items.
- Knee disease enters as a sensitivity analysis.
- A longitudinal model is preferred to separate per-visit comparisons alone.
- Add WOMAC, KOOS and the 20-meter walk as validators, with KOOS sport and recreation and the
  non-walking PASE items as divergent evidence.
- Look at discriminative validity across KL grade, with KL 4 alone only if numbers allow.
- Both KL comparisons are computed; which one goes in Table 1 is fixed before computing.
- Multiplicity is handled by facet of construct validity.
- The manuscript must state why the 400-meter walk was excluded, in terms a reviewer who knows the
  OAI will accept (see "The 400-meter walk").
- Divergent validity on the PASE items is judged by an effect-size rule fixed before computing (see "Analyses", item 2).
- The mentor approves the scope and expectations before any new comparison is computed by walker
  group. This is a hard stop in the plan.
- Everyone stays in the main analysis, with a sensitivity analysis limited to visits at age 50 or
  older (see "Analyses", item 6).

**By Claude, for the user to check while reading**

- A limitations sentence says both main measures are self-report and that this report makes no
  device comparison. It gives no device results.
- The expectations in "Analyses", including which facet each measure falls under and the unscored
  sitting item having no prediction.
- Display items, model forms and the worse-knee rule below.

## Goals, non-goals, anti-goals

**Goals**

- A submission-ready draft within the format limits, every number computed from the run.
- Expectations recorded in the ledger before any new comparison is computed by walker group.
- A Word copy for the mentor's edits, as with the abstract.

**Non-goals**

- Accelerometer analysis, step data and the Northwestern work.
- Lo 2022 sensitivity analysis or re-analysis.
- Results split by subcohort. Subcohort is an adjustment only; controls number 104.
- Changing the submitted abstract's text, figures or paste file.

**Anti-goals: a failure even if it runs**

- Dropping or reframing an unfavorable validator after seeing it. If Walkers score higher on
  everything, the report says so and the conclusion narrows.
- Presenting function differences as confirming the walking history. They can run either way:
  walking may protect, or better knees may allow walking.
- Implying individual-level accuracy from group differences. 79% answered yes and 60% of the
  others reported short-term walking at 96 months.
- Using "bias", "correction" or "corrected", the existing framing rule for these documents.

## Data, as checked on 2026-11-05 in the 2,582-person PASE frame

No comparison by walker group has been computed for any new measure below.

| Measure | Variables | Visits (months) | Notes |
|---|---|---|---|
| PASE total | `VxxPASE` | 0–96, 168 | As in the abstract |
| PASE walking | `VxxPASE2`, `VxxPASE2HR` | 0–96, 168, 192 | As in the abstract |
| Other leisure items | `VxxPASE1`, `VxxPASE3`–`6` and `HR` | 0–96, 168 | 1 sitting (unscored), 3 light, 4 moderate, 5 strenuous, 6 muscle |
| Household items | `VxxHOUACT1`–`6` | 0–96, 168 | Yes/no: light and heavy housework, repairs, yard, garden, caring |
| Work | `VxxWORK7`, `VxxWKHR7CV`, `VxxWORKAMT` | 0–96, 168 | Scored only when `WORKAMT` > 1 |
| WOMAC function | `VxxWOMADLR`, `VxxWOMADLL` | 0–96, 168, 192 | Per knee; higher is worse |
| WOMAC walking difficulty | `VxxDIRKN6`, `VxxDILKN6` | 0–96, 168, 192 | Per knee, 0–4. Items 16 and 17 are heavy and light chores |
| KOOS sport and recreation | `VxxKOOSFSR` | 0–96 | One score a person; 2,001 of 2,582 at enrollment, reason unknown |
| 20-meter walk pace | `Vxx20MPACE` | 0–96 | About 384 at 168 months, so not used there |
| KL grade | `V00XRKL` in `kxr_sq_bu:00` | 0 | Reading project 15, as in `oai.derive.knee.xray_readings`. Worse knee: KL 0 784, KL 1 435, KL 2 758, KL 3 434, KL 4 143 (2,554 people). If non-walkers were spread alike, about 30 would be KL 4; the actual split has not been computed |
| Knee pain | `VxxWOMKPR`, `VxxWOMKPL` | 0–96, 168, 192 | Enrollment for the main sensitivity analysis |
| Subcohort | `V00COHORT` | 0 | 616 progression, 1,862 incidence, 104 control |

**PASE scoring check.** With Washburn weights and the ledger's midpoints, the item-level
reconstruction matches the released total within 1 point for 99.8% at enrollment and 99.9% at 96
months (correlation 0.9995 at both). This holds only when work is counted for `WORKAMT` > 1 and at
`21 × WKHR7CV / 7`, which implies `WKHR7CV` is hours a week. Both readings are inferred from this
match; confirm them from `formats.pdf` and the codebook.

## Analyses

Keep the abstract's analysis population, groups ("Walkers for Exercise" vs not; any yes), and the
covariates age, sex and BMI. Keep the `pase_without_bmi` variant. All new choices become ledger
entries in `analyses/walking_validation/assumptions.toml`, with variants where a choice matters.

1. **Convergent validity, the main analysis: repeated PASE.**
   - PASE total: linear mixed model with walker, visit as categories and walker × visit, plus
     covariates, with a random intercept per person.
   - Short-term walking and walking 5 or more hours a week: GEE logistic on the same terms, by
     person (`oaimodels` has `gee.R`).
   - Report the overall Walker contrast, then contrasts for three periods: before the survey
     (0–72), at it (96), after it (168, and 192 for the walking outcomes), and a test of whether
     the gap differs by period. Enrollment is reported on its own as well, as the visit furthest
     from recall.
   - The abstract's per-visit contrasts stay as the descriptive results.

2. **Divergent validity: other PASE content.** PASE total minus the walking subscore, through the same
   mixed model. Then each other PASE item through a GEE model, and each scored domain summarized
   in the supplement. Expectations recorded before computing:
   - moderate link: light, moderate and strenuous recreation, muscle strength;
   - little or no link: housework, repairs, yard, garden, caring, work;
   - sitting: reported with no prediction.
   Any participation is the outcome for each item, since most are skewed; the builder chooses a
   documented dichotomy for sitting, which nearly everyone reports.

   **Decision rule, fixed before computing.** Effect size decides, not p-values, since at this
   sample size even tiny gaps reach significance. Judge each overall Walker contrast by its
   estimate:
   - little or no link: adjusted OR under about 1.44, or standardized difference under 0.2;
   - moderate link: OR about 1.44 to 2.47, or standardized difference 0.2 to 0.5;
   - PASE total minus walking is judged by the same standardized-difference bands and reported
     with the rule's result.
   If at least half of the seven household and work items (four or more) reach OR 1.44, the
   conclusion narrows: the question marks generally active people, or people who report more
   activity, and is not specific to walking. The ORs correspond to the standardized differences
   under the usual logistic conversion (Chinn 2000); check that citation before using it. Function
   and walk-test results do not trigger this rule. They are reported by size and direction.

3. **Function and measured walking.** All through the mixed model; per-knee measures use the worse
   knee at each visit. Investigate why KOOS sport is missing at enrollment and state it.
   - Convergent: WOMAC walking difficulty and 20-meter pace, expected to favor Walkers.
   - Between the two: WOMAC function, a broad score across many activities.
   - Divergent: KOOS sport and recreation. It is about knee difficulty with higher-demand activity,
     so some link is plausible. The expectation is relative: a smaller standardized difference than
     for WOMAC walking difficulty, not zero.

4. **Discriminative validity across KL grade.** Person-level, by worse-knee enrollment KL: KL 0–1
   (1,219), KL 2–3 (1,192), and KL 4 (143) shown alone only with a wide-interval caveat, otherwise
   combined as KL 2–4. Both comparisons are computed:
   - Walker share across KL groups, adjusted for age, sex and BMI. No direction is predicted; the
     text states why (walking may affect OA, and severe knees may have stopped people walking).
   - The Walker contrast on PASE total and short-term walking within each KL group, with a walker ×
     KL test.
   **Reporting (Claude's call, fixed before computing, so the choice can't follow the results):**
   Walker share goes in Table 1 and the contrasts within KL go in the supplement, whatever they
   show. If no supplement is allowed, the contrasts get one sentence in Results.

5. **Dose.** Trends by times a month and years walked, as in the abstract.

6. **Sensitivity analyses.**
   - Main: add enrollment KL (worse knee), enrollment WOMAC pain (worse knee) and subcohort to the
     main models.
   - Secondary, labeled as such: add time-varying WOMAC pain. Later pain may lie on the path from
     walking, since Lo 2022 linked walking to less frequent knee pain, so this may remove part of
     the signal. No time-varying KL.
   - Attrition: the 168-month contrast among those with data at both 96 and 168 months, and a
     description of who left. The sample is conditioned on answering at 96 months, so earlier
     visits include only people who stayed that long.
   - Age: repeat the main models using only visits at age 50 or older. The question asks about
     "since age 50", but 340 people (13.2%) were under 50 at enrollment, then 260, 170, 111 and 37
     at 12, 24, 36 and 48 months, and none from 72 months. The main analysis keeps them, and the
     report reads the early gap as a stable habit, not as walking within the question's period. A
     Walker answering "1–5 years" may also not have started by the early visits; the text notes
     this, and no separate model addresses it.

**Multiplicity (the user's choice: by facet of construct validity).** Only claims that rest on a
p-value are adjusted, and each family holds one kind of claim:

| Facet | Tests | Handling |
|---|---|---|
| Primary | PASE total and short-term walking, overall Walker contrast | Holm across these 2 |
| Recall | Whether the PASE total gap differs by period | 1 pre-stated test, no family |
| Other convergent | 5+ hours of walking a week, WOMAC walking difficulty, 20-meter pace, WOMAC function | Holm across these 4 |
| Divergent | Non-walking PASE items, PASE total minus walking, KOOS sport | No significance claims; effect sizes with CIs, judged by the rule in item 2 or the relative expectation in item 3 |
| Discriminative | Walker share by KL, walker × KL tests | Holm across these |
| Descriptive | Period and per-visit estimates | CIs only; the abstract's across-visit adjustment stays as submitted |

Holm is not applied to divergent items because it makes "no link" easier to claim. A wide interval
that is under the cutoff is not evidence of no link, so the text reports the interval as well as
the estimate.

## The 400-meter walk

The manuscript's Methods must say in a sentence or two why the 400-meter walk is not used. The
reason must be true of the data and protocol, and must not rely on the walking group results.

Facts checked so far: it was given only at 0, 24, 48 and 96 months. Recorded time falls from 2,437
to 1,919 of 2,582 people; `400MTIM` is the time "at 400-m or at stop", so non-completers' times are
not comparable; and completion code 4 rises from 60 to 235 people between enrollment and 96 months.

Before drafting:
- Confirm what `PERFCOMP` codes 1–5 mean from `formats.pdf`.
- Confirm who was not eligible or not tested from the OAI protocol or operations manual.
- Do not call it uninformative. It is an endurance measure and could be argued to be closer to a
  walking habit than 20-meter pace; the honest case is schedule, follow-up and non-comparable or
  missing values, not lack of relevance.
- Record the choice in the ledger with this rationale, and compute nothing for it by walker group.

Draft, to be finalized once the two checks are done: "We used 20-meter walk pace rather than the
400-meter walk because the latter was administered at only four visits and, at 96 months, lacked a
recorded time for [n, %] of participants; times for those who stopped early were not comparable
with those who finished."

## Manuscript

Target limits are gates: 2,000 words of main text, 250-word abstract, 15 references, 2 display
items. Check the current O&C guide for authors for these, for whether supplementary material is
allowed and whether it counts toward them, and for the abstract's headings. The user pasted the
limits; they have not been confirmed against the journal.

- **Figure 1**, two panels: PASE total and short-term walking across visits by group, built from
  the abstract's figures.
- **Table 1**: model results grouped by facet of construct validity: convergent, divergent,
  discriminative.
- **Supplement**: participant characteristics, per-visit results, per-item results, dose, and all
  sensitivity analyses. If the journal does not allow one, participant characteristics move into
  Table 1 and the rest is cut to fit.
- **Discussion order**: the visits before the survey carry the argument, since current activity can
  color recall and the gap is largest at 96 months. Then divergent evidence, discriminative evidence,
  limitations.
- **Prior publication**: disclose the OARSI 2027 abstract at submission.
- American spelling; "Walkers for Exercise"; "short-term walking" for PASE item 2.

## Constraints from this repository

- No number typed by hand; prose and tables read from the run's results, as in `abstract_pase.qmd`.
- Add steps and a document to `analyses/walking_validation/analysis.toml`. The submitted abstract's
  outputs must stay byte-identical in text.
- The word gate fails the render if over, like the abstract's character budget.
- Word copies stay outside `report/`, since egress fails closed on `.docx`.
- Follow-ups go in `TODO.md`, with human-only items marked `<!-- skip -->`.

## Left to the builder

File and step names; table layout; the sitting dichotomy; the GEE working correlation, documented
in the ledger; how the `nlme` and `geepack` choices fit the `report` R profile; the Word copy's
script, reusing `~/oai-work/tools/abstract_pase_docx.js` where it fits.

## Open for the user and the mentor

- **The mentor's review comes first.** The plan's sequence is: write the expectations and decision rule
  into the ledger, build only what computes no comparison by walker group, send the mentor a short scope
  summary, then stop until she approves. She steered the abstract toward PASE and questioned the
  BMI adjustment; her view on the function measures, the decision rule and the KL analysis is not
  known. Any change she asks for at this stop goes into the ledger before computing.
- Authorship, and timing of submission relative to the April 2027 meeting.
