# Future study ideas

Candidate OAI analyses that are not started. Each entry records the question, what is
already published, what OAI can add, and what to settle before building. When one
starts, it gets its own `analyses/<name>/` folder with an assumptions ledger, and its
entry here links to it.

---

## Regression to the mean in knee pain at trial-style entry thresholds

_Added 2026-10-28. Status: idea, not started._

### Question

How much of the pain improvement seen after people enter a knee OA trial is regression to
the mean (RTM), and does the classic formula predict it? Specifically: in OAI, does the
truncated-normal prediction, using test–retest correlation over the trial interval and
the share of the cohort an entry cutoff excludes, match the change actually observed
after people first meet that cutoff? And how do common design features change the
answer: the height of the threshold, choosing the worse knee, requiring the threshold
at both screening and baseline, and the follow-up interval?

### Background

Under a bivariate-normal model, people selected above a cutoff `c` are expected to move
back toward the mean by

    E[RTM] = (1 − ρ) · σ · φ(z) / (1 − Φ(z)),   z = (c − μ) / σ

where ρ is the correlation between the two measurements over the interval of interest,
σ the population SD, and Φ(z) the share of the population the cutoff excludes (Davis
1976; Chinn & Heller 1981, doi 10.1093/oxfordjournals.aje.a113260; McMahan 1987 for
two-stage selection, doi 10.1093/oxfordjournals.aje.a114609). Equivalently, RTM is the
fraction (1 − ρ) of the selected group's baseline excess over the population mean.

What exists for knee OA (checked in PubMed 2026-10-28):

| Study | Data | Approach | What it leaves open |
| --- | --- | --- | --- |
| Englund & Turkiewicz 2023, *Lancet Rheumatol* 5:e309–11 (doi 10.1016/S2665-9913(23)00090-5) | "Pain in clinical trials for knee OA: estimation of RTM"; no abstract in PubMed, presumably OAI | Presumably empirical | **Read first.** It may already cover the observed pain RTM in OAI. |
| Englund & Turkiewicz 2025, *Osteoarthritis Cartilage* 33:391–5 (doi 10.1016/j.joca.2024.11.006) | OAI years 1–8; 547 people meeting typical trial criteria (age 40–79, symptomatic KL 2–3, frequent pain medication, NRS 4–9) | Empirical: change after the first visit at which criteria are met | WOMAC function and KOOS QOL only; no formula prediction; one threshold. Function improved 2.5 points at 1 year and 3.1 at 2 years; QOL 2.7 and 4.2. |
| Bihlet et al. 2018, *BMC Musculoskelet Disord* 19:17 (doi 10.1186/s12891-018-1938-5) | Placebo arms of two phase 3 tanezumab trials, 771 target knees | Barnett formula, within-person variance from screening and baseline visits | Variance from an already-selected trial population, so the share excluded has no population denominator. |
| Kamerman & Vollert 2022, *Pain* 163:e748–58 (doi 10.1097/j.pain.0000000000002468) | Simulated chronic-pain trials, not OA | Threshold 3–5/10, ρ 0.19–0.44 | Not OA-specific; parameters assumed, not estimated. |
| Chen et al. 2026, *Arthritis Care Res* 78:31–7 (doi 10.1002/acr.25636) | Methods review | Lists run-in, ANCOVA, reliability-based correction, regression discontinuity, shrinkage | No data. |

Counterpoint to keep in view: Zhang 2008 (doi 10.1136/ard.2008.092015) found untreated
control arms barely improved (ES 0.03, 14 arms), and Searle 2025 (doi
10.1002/jeo2.70537) read flat placebo/physiotherapy arms in injection trials as no
evident RTM. A formula-vs-observed comparison could help reconcile these with the OAI
findings.

### What OAI adds

- An unselected denominator: the whole cohort's pain distribution defines σ and the share
  each cutoff excludes, which trial data cannot.
- Repeated pain measures at several intervals, so ρ can be estimated for the interval a
  trial actually uses, not a days-apart validation ICC (median WOMAC pain test–retest
  ICC ≥ 0.70 in Gandek 2015, doi 10.1002/acr.22415, likely far higher than the 12-month
  ρ). Both measures exist at V00–V12 (0–120 months), including the 18-, 30-, 60- and
  84-month phone visits, so 6-, 12- and 24-month intervals are available:
  - NRS knee pain, past 7 days, 0–10: `V##P7RKRCV`, `V##P7LKRCV`
  - WOMAC pain, 0–20: `V##WOMKPR`, `V##WOMKPL` (also at V13, V14)
- Both knees, so the effect of picking the worse knee as the target knee can be measured.

### Proposed design

1. **Replicate first.** Reproduce Englund & Turkiewicz 2025 (547 people; function and
   QOL changes at 1 and 2 years) with a `published.toml` and compare step, as for
   `lo2022_walking` and `lo2018_crepitus`. Then reproduce the 2023 pain estimate if the
   letter reports one.
2. **Predicted RTM.** For each cutoff (NRS ≥ 3, 4, 5, 6; WOMAC pain thresholds to be
   chosen), estimate μ, σ and ρ for the 12- and 24-month intervals in the full cohort at
   the same visits, and compute the formula prediction. Report it next to the
   prediction using a validation-study ICC to show how much the choice of ρ matters.
3. **Observed RTM.** Change from the first qualifying visit to 12 and 24 months later,
   in the same people.
4. **Design features**, each as a separate comparison of predicted and observed:
   - threshold height (dose–response);
   - target knee = worse knee versus a fixed knee;
   - two-stage entry (cutoff met at two visits 6 or 12 months apart, like a
     screening + baseline run-in), against McMahan's two-stage prediction;
   - first qualifying visit among many (each person has several chances to qualify,
     which selects on peaks) versus a single fixed visit.
5. **Non-normality.** Pain scores are bounded and skewed. Compare the normal formula with
   an empirical (nonparametric) prediction and the bivariate-t or general bivariate
   extensions (Umair, Khan & Olivier 2024, doi 10.1177/09622802241267808; Khan & Olivier
   2025, doi 10.1093/biomtc/ujaf033).
6. **Separate RTM from real change.** Cohort-wide secular trend in pain, knee
   replacement and death or dropout after selection, and new analgesic or injection use
   all move the observed change. Options: subtract the change in a comparison group
   just below the cutoff (regression discontinuity at the threshold), and censor at knee
   replacement with a sensitivity variant.

### Ledger entries to seed (`assumptions.toml`, mostly `open`)

- Pain measure and cutoffs; scale of WOMAC pain (0–20 vs 0–100).
- Population for μ, σ, ρ: whole cohort, or people with KL ≥ 2 only (the entry criteria
  other than pain define the "population" the cutoff truncates).
- Interval for ρ (6, 12, 24 months) and whether phone and clinic visits are pooled.
- Knee selection: worse knee, right knee, or both knees with clustering.
- Qualifying visit: first qualifying visit vs a fixed visit; visits allowed (Englund &
  Turkiewicz used years 1–8).
- Handling of knee replacement, missing visits and death after selection.

### Notes from reviewing the source summary (2026-10-28)

The idea came from a literature summary pasted into a session. Corrections and checks:

- The summary said no separate OAI analysis of RTM for pain could be found. Englund &
  Turkiewicz 2023 (*Lancet Rheumatol*, above) is titled as exactly that, so the gap is
  narrower than stated: likely the formula-vs-observed comparison, the design features
  and the non-normal methods, not the observed pain RTM itself.
- Its worked examples are right: ρ = 0.5 with 50% excluded gives 0.40 SD, and with 84%
  excluded 0.76 SD.
- Its statement that RTM "grows faster than in proportion to the cutoff" is loose. The
  selected group's excess, σ·φ(z)/(1 − Φ(z)), rises with the cutoff but by less than
  one SD per SD of cutoff; RTM stays the fraction (1 − ρ) of that excess. What rises
  steeply is RTM as the share excluded approaches 100%.
- The reliability of 0.48–0.61 attributed to Bihlet 2018 was the summary's own
  calculation from their variance table; recheck it against the paper before citing.
- The other citations were confirmed in PubMed (Bihlet 2018, Kamerman 2022,
  Englund & Turkiewicz 2025, Collins 2023, Chen 2026, Khan & Olivier 2025).
