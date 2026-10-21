# Reviewing the PASE abstract

`abstract_pase.pdf` is a draft conference abstract on the 96-month walking-for-exercise question
against the Physical Activity Scale for the Elderly (PASE) at every visit. This guide lists the
code behind it, in reading order. Most of this folder belongs to the accelerometer validation
(the brief, clinical version, technical report and accelerometer abstract), which is still in
use but is not needed to review this abstract (see [Not needed](#not-needed-for-this-abstract)).

Line numbers are for the commit this guide was last updated with; if they drift, the function
names still hold.

## How a number gets into the abstract

No number in the abstract is typed by hand. Each one is computed from the OAI release and read
from a results table when the abstract renders:

```
OAI release
  → build_cohort.py      one row per person: the walking answer, covariates, PASE at every visit
  → pase_walking.R       per visit: group summaries, comparisons, trend tests, hours bands (CSV)
  → abstract_pase.qmd    the text, reading those tables; pase_figures.R draws the figures
```

Every analysis choice (visits, scoring, covariates, p-value adjustment) is an entry in
[assumptions.toml](assumptions.toml), which the code reads rather than hard-coding.

## Read in this order

| # | File | Lines | What to check |
|---|---|---|---|
| 1 | [abstract_pase.qmd](abstract_pase.qmd) | [80–200](abstract_pase.qmd#L80-L200) | The text: Purpose [110](abstract_pase.qmd#L110), Methods [112–121](abstract_pase.qmd#L112-L121), Results [123–169](abstract_pase.qmd#L123-L169) (the weekly-hours sentence at [135–161](abstract_pase.qmd#L135-L161)), Conclusions [171](abstract_pase.qmd#L171), figure captions [173–186](abstract_pase.qmd#L173-L186). Each `sprintf` slot is filled from the results tables by the helpers at [48–59](abstract_pase.qmd#L48-L59) and [81–106](abstract_pase.qmd#L81-L106). |
| 2 | [pase_walking.R](pase_walking.R) | whole file | All the statistics: the groups [35–51](pase_walking.R#L35-L51), the outcomes at each visit [53–66](pase_walking.R#L53-L66), then for every visit × outcome × grouping the summaries [76–77](pase_walking.R#L76-L77), comparisons [78–85](pase_walking.R#L78-L85), hours bands [86–96](pase_walking.R#L86-L96) and their comparisons [97–105](pase_walking.R#L97-L105), and trend tests [107–117](pase_walking.R#L107-L117); after every visit, the p-value adjustment across visits [122–129](pase_walking.R#L122-L129). |
| 3 | [r/oaimodels/R/groups.R](../../r/oaimodels/R/groups.R) | [1–115](../../r/oaimodels/R/groups.R#L1-L115) | The two functions behind every comparison: `group_summaries()` (each group's mean or share with its 95% CI) and `group_contrasts()` (walkers against non-walkers, crude and adjusted). |
| 4 | [pase_figures.R](pase_figures.R) | whole file | Figures 1 and 2, both drawn by `pw_point_figure()` [63–101](pase_figures.R#L63-L101). |
| 5 | [build_cohort.py](build_cohort.py) | [45–69](build_cohort.py#L45-L69), [120–170](build_cohort.py#L120-L170) | Who is included and where the walking answer, covariates and PASE come from. The rest of the file builds the accelerometer cohort. |
| 6 | [assumptions.toml](assumptions.toml) | see below | The analysis choices, each with its source. |

## Definitions

- **Walker / non-walker.** The answer to `V10WLKAR4` at 96 months: walked for exercise at least
  20 minutes a day, at least 10 times, since age 50 (read in
  [src/oai/derive/walking.py](../../src/oai/derive/walking.py#L16-L31)). Walkers answered yes,
  whether or not they gave an amount; non-walkers answered no ([pase_walking.R:43](pase_walking.R#L43)).
  A sensitivity grouping, `any_lo`, uses Lo et al. 2022's coding, in which a yes without an
  amount counts as a non-walker. It is computed but not reported in the abstract.
- **Frequency and years walked** (the dose sentence): `V10WKTMAR4` and `V10WKYRAR4`, by answer
  category ([pase_walking.R:37–41](pase_walking.R#L37-L41)).
- **PASE total**: the score as released (`VxxPASE`), not recomputed
  ([src/oai/derive/pase.py:57](../../src/oai/derive/pase.py#L57)).
- **Any PASE walking**: item 2 (walking outside the home in the past 7 days) answered with any
  days, i.e. days > 0 ([pase_walking.R:61](pase_walking.R#L61)).
- **Weekly walking hours**: item 2's days × hours a day at each answer category's midpoint
  ([pase_walking.R:62–63](pase_walking.R#L62-L63); midpoints in `pase.walking_scoring`), in the
  bands of `components.pase_weekly_hours_bins` (0, <2, 2–5, 5–10, 10+ hours a week). Used for
  the "5 or more hours a week" result and the Results sentence on weekly walking hours.
- **Covariates**: age and BMI at enrollment (`V00AGE`, `P01BMI`) and sex (`P02SEX`)
  ([build_cohort.py:65–69](build_cohort.py#L65-L69)).
- **Visits**: every visit with PASE. The total is released at 0–96 and 168 months; at 192 months
  only item 2 was asked, so that visit has any walking but no total (`pase.all_visits`).

## Statistics

Each visit is analyzed on its own, with no longitudinal model across visits. At each visit:

| Outcome | Each group (figures) | Walkers vs non-walkers, crude | Adjusted (age, sex, BMI; stars and text) |
|---|---|---|---|
| PASE total | mean, t-based 95% CI | difference in means, Welch 95% CI and p | linear regression coefficient, 95% CI and p |
| Any PASE walking | share, Wilson 95% CI | risk difference, Newcombe 95% CI, Fisher p | logistic regression odds ratio, Wald 95% CI and p |
| Each band of weekly hours but 0: in it or not | share of the group in the band | risk difference, Newcombe 95% CI, Fisher p | logistic regression odds ratio of being in the band, Wald 95% CI and p |

The code is in [groups.R: crude means 58–60, adjusted means 88–93, logistic 94–98](../../r/oaimodels/R/groups.R#L58-L98).
The step also writes medians (Hodges–Lehmann and median regression), which the abstract does not
use. Trends across frequency and years walked use Cochran–Armitage for any walking
([pase_walking.R:109–111](pase_walking.R#L109-L111)).

**Multiple comparisons.** p-values are Holm-adjusted (`pase_walking.p_adjust`) within one
family per grouping, outcome and estimator, spanning every visit and level
(`pase_walking.p_adjust_family`; [pase_walking.R:122–129](pase_walking.R#L122-L129)). Walkers
against non-walkers is one comparison a visit, so the PASE total is adjusted across its 8 visits,
any walking across its 9 and each hours band (outcomes `band <2` to `band 10+`) across its 9;
the frequency groups, for example, across 3 levels × 9 visits. The
variant `pase_p_within_visit` adjusts only across a grouping's levels at each visit.

**Stars** in both figures mark the adjusted p after that adjustment (`adj_p_holm`;
`components.star_levels`: `*` < 0.05, `**` < 0.01, `***` < 0.001)
([pase_figures.R:21–26](pase_figures.R#L21-L26)), one above each visit. The plotted CIs
are each group's own, so whether two intervals overlap is not the test.

## Claims and where they come from

| Claim in the abstract | Results table | Computed at |
|---|---|---|
| How many answered, and how many said yes | `metrics_pase.csv` | [pase_walking.R:140–144](pase_walking.R#L140-L144) |
| n with a PASE total at enrollment and at 168 months; n in the figures | `pase_walking_groups.csv` (`n`) | [pase_walking.R:76](pase_walking.R#L76) |
| Mean PASE total, walkers vs non-walkers, and the adjusted difference | `pase_walking_groups.csv` (`mean`), `pase_walking_contrasts.csv` (estimator `mean`) | [groups.R:88–93](../../r/oaimodels/R/groups.R#L88-L93) |
| Any walking, % and adjusted odds ratio | `pase_walking_groups.csv` (`estimate`), `pase_walking_contrasts.csv` (estimator `share`) | [groups.R:94–98](../../r/oaimodels/R/groups.R#L94-L98) |
| 5 or more hours a week; the % in a band at 96 months | `pase_walking_bands.csv` | [pase_walking.R:86–96](pase_walking.R#L86-L96) |
| Bands in which walkers differ (every visit, some visits, none) and the band's odds ratio | `pase_walking_contrasts.csv` (outcomes `band <2` to `band 10+`) | [pase_walking.R:97–105](pase_walking.R#L97-L105); worded at [abstract_pase.qmd:135–161](abstract_pase.qmd#L135-L161) |
| "Both differed at every visit" | every adjusted p (`adj_p_holm`, adjusted across visits) < 0.05 in `pase_walking_contrasts.csv` | [abstract_pase.qmd:86–91](abstract_pase.qmd#L86-L91) |
| Dose sentence (odds by frequency and years walked, trend p) | `pase_walking_contrasts.csv` (groupings `times`, `years`), `pase_walking_trend.csv` | [pase_walking.R:107–117](pase_walking.R#L107-L117) |

## Analysis choices (assumptions.toml)

| Entry | Line | What it sets |
|---|---|---|
| `pase.all_visits` | [125](assumptions.toml#L125) | The visits analyzed |
| `pase.walking_scoring` | [115](assumptions.toml#L115) | Item 2's day and hour midpoints (Washburn et al. 1993) |
| `components.pase_weekly_hours_bins` | [200](assumptions.toml#L200) | The weekly-hours bands |
| `pase_walking.amounts` | [256](assumptions.toml#L256) | The amount groupings: times a month, years walked |
| `pase_walking.covariates` | [261](assumptions.toml#L261) | Adjustment: age, sex, BMI |
| `pase_walking.p_adjust` | [266](assumptions.toml#L266) | Holm |
| `pase_walking.p_adjust_family` | [272](assumptions.toml#L272) | Which p-values are adjusted together: across visits |
| `components.answer_labels` | [225](assumptions.toml#L225) | Answer categories, from the OAI formats file |
| `components.star_levels` | [251](assumptions.toml#L251) | Star thresholds |
| `exposure.yes_without_amount_as` | [88](assumptions.toml#L88) | Lo et al. coding of a yes without an amount (affects only the sensitivity grouping here) |

## Shared helpers

- [report_setup.R](report_setup.R): loads the run's results ([line 6](report_setup.R#L6)) and
  formats numbers (`num`, `count`, `pct`, [8–10](report_setup.R#L8-L10)). The rest is for the
  accelerometer documents.
- [brief_figures.R](brief_figures.R): only the star helpers at [28–41](brief_figures.R#L28-L41)
  are used here. The rest draws the accelerometer brief's figures.
- [r/oaireport](../../r/oaireport): plot theme, figure saving, the star formatter and the
  character budget (`char_budget()`).

## Not needed for this abstract

These files are the accelerometer validation, still in use for the poster and paper:
`brief.qmd`, `clinical.qmd`, `report.qmd`, `abstract.qmd`, `validity.R`, `components.R`,
`device.py`, `wv.py`, `bias.R`, `compare.py`, `expected.toml`.

## Running it

Running needs access to the OAI release (see [README.md](README.md)):

```bash
uv run oai run walking_validation
uv run oai report walking_validation
```

The cohort step also runs the accelerometer `device` step, because it builds both cohorts.
Reviewers without the data can read the code and the PDF.
