# Scope for review: construct validity of the OAI walking question

**What I need from you.** Please approve or change the scope below before any new comparison is run by walker group. The expectations and the decision rule are being fixed first, so they cannot follow the results. No new results have been computed, and none appear here.

## Aim

The brief report asks how far the 96-month question, "walked for exercise since age 50," holds up as a measure of a long-term walking habit in the OAI. The question has been used as an exposure (Lo 2022: lower odds of new frequent knee pain in people with knee OA), and no full paper has examined it. As in the submitted abstract, we frame this as construct validity, in three facets: convergent (does the question agree with measures of the same construct), divergent (does it stay apart from measures of other constructs) and discriminative (does it differ across knee OA severity). PASE is a comparison measure, not a reference standard, so we say "convergent validity with PASE." Both main measures are self-report, and this report makes no device comparison. Groups ("Walkers for Exercise" versus not) and the analysis population are as in the abstract.

## Measures by facet, with the expectation for each

| Facet | Measure | Expectation |
|---|---|---|
| Convergent (primary) | PASE total; short-term walking (PASE walking item, yes/no) | Higher in Walkers |
| Convergent | Walking 5 or more hours a week; WOMAC walking difficulty; 20-meter walk pace | Favor Walkers |
| Between convergent and divergent, held with convergent | WOMAC function (a broad score across many activities) | Favors Walkers, more weakly |
| Divergent | PASE total minus the walking subscore | No prediction, judged by the bands |
| Divergent | Light, moderate and strenuous recreation; muscle strength | Moderate link |
| Divergent | Light and heavy housework, home repairs, yard work, gardening, caring for others, work | Little or no link |
| Divergent | Long sitting (PASE sitting item, more than 4 hours a day) | No prediction |
| Divergent | KOOS sport and recreation | Some link, smaller than for WOMAC walking difficulty |
| Discriminative | Walker share across KL groups (Table 1): adjusted odds ratio of being a Walker vs KL 0-1, with each group's crude share and counts | No direction predicted |
| Discriminative | Walker contrast on PASE total and short-term walking within each KL group (supplement) | Reported either way |

WOMAC measures use the worse knee at each visit; KOOS sport and recreation is one score per person per visit, not per knee. Function differences can run either way: walking may protect, or better knees may allow walking.

## The decision rule

Effect size decides, not p-values, because at this sample size even tiny gaps reach significance. The standardized difference is the adjusted difference over the pooled SD at the measure's first visit. For each measure, an adjusted odds ratio under about 1.44 (standardized difference under 0.2) means little or no link, and 1.44 to 2.47 (0.2 to 0.5) means a moderate link. The cutoffs come from Chinn 2000, which converts a log odds ratio to an effect size by dividing by 1.81. If at least four of the seven household and work items reach an odds ratio of 1.44 in the Walker direction, the conclusion narrows to "generally active people, or people who report more activity, and not specific to walking." Function and walk-test results do not trigger the rule; they are reported by size and direction. If Walkers score higher on everything, the report says so.

## Models and p-values

Repeated-measures models use every visit: a linear mixed model for continuous measures and a logistic GEE model for yes/no measures, with visit and covariates. The overall Walker contrast comes from a model without an interaction. The contrasts before the survey (0 to 72 months), at it (96 months) and after it (168 months, and 192 for walking outcomes) come from a model with Walker by period. Enrollment is also reported on its own, as the visit furthest from recall. Whether the gap differs by period is one pre-stated test, on the PASE total, which is how we ask whether current activity coloring recall explains it; period rows for other measures are descriptive. Dose is also descriptive: trends by times a month and years walked, at 96 months, as in the abstract. P-value adjustment (Holm) is by facet and applies only to claims that rest on a p-value. Divergent measures make no significance claims; they get effect sizes with confidence intervals, and a wide interval under the cutoff is not read as evidence of no link.

## Discriminative validity by KL grade

People are grouped by worse-knee enrollment KL: 0-1 (1,219 people), 2-3 (1,192) and 4 (143). KL 4 is shown alone only if it has at least 20 non-walkers; otherwise it is combined with 2-3 as KL 2-4. Both analyses are run. The Walker share across groups, adjusted for age, sex and BMI, goes in Table 1; the Walker contrasts within each group, with a test for Walker by KL, go in the supplement. This is fixed now, whatever the results. We predict no direction for Walker share, since walking may affect OA and severe knees may have stopped people walking.

## Covariates and sensitivity analyses

Covariates are age, sex and BMI. BMI stays in, as you kept it in the abstract, and an age-and-sex-only version is also run. The sensitivity analyses run on every measure.

- Enrollment KL, enrollment WOMAC pain and subcohort added to the main models.
- Secondary, labeled as such: time-varying WOMAC pain. Later pain may lie on the path from walking (Lo 2022), so adjusting for it may remove part of the signal.
- Visits at age 50 or older only. The question asks about "since age 50," but 340 people (13.2%) were under 50 at enrollment, and none were from 72 months. The main analysis keeps everyone.
- Attrition: the 168-month contrast among people with data at both 96 and 168 months, and a description of who left. Everyone answered at 96 months, so earlier visits include only people who stayed that long.

## The 400-meter walk

We do not use it. It was given only at 0, 24, 48 and 96 months. At 96 months, 663 of 2,582 people (25.7%) have no recorded time, and the recorded time is the time at 400 meters or at stopping, so times of people who stopped early are not comparable with those who finished. It is an endurance measure and could be argued to be closer to a walking habit than 20-meter pace; the reason is schedule, follow-up and comparability, not relevance. We compute nothing for it by walker group. We use 20-meter walk pace instead.

## Questions for you

1. Do the facet assignments and expectations in the table look right? I would value your view on where WOMAC function belongs.
2. Is KOOS sport and recreation reasonable as divergent evidence? About 22.5% of people have no score at enrollment. Running and jumping are blank for about half, and we infer a score requires three of the five items, but we do not know why those items are blank. People who do not run or jump may be systematically missing, which could limit this measure. Do you know why they were left blank?
3. Do you agree with the two KL analyses, given that no direction is predicted for Walker share?
4. Is the effect-size rule acceptable?
5. Are you comfortable keeping BMI as a covariate?
