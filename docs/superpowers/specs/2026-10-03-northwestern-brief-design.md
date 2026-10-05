# Walking Validation Brief for the Northwestern Accelerometry Group — Design

**Date:** 2026-10-03
**Status:** Implemented
**Builds on:**
- `2026-10-01-walking-validation-design.md` (including amendments 11–12)
- `2026-09-30-reporting-module-and-lo2022-comparison-design.md`

## 1. Purpose

The audience is the OAI accelerometry group at Northwestern, who hold the raw ActiGraph GT1M data. The aim is to persuade them to join a study as co-investigators.

GT1M step counts come from the device's step-detection algorithm, not a mechanical pedometer. That is a reason to bring in their expertise rather than only request files.

The deliverable is one send-ready PDF:
- **A brief** of 4–6 pages, written for accelerometry experts.
- **The full technical report** as its appendix, after a legibility pass.

Both are generated from the same `walking_validation` run. Every number comes from the run.

**The ask.** A joint study that:
- revalidates the 96-month walking item and PASE walking against walking-specific references defined with the group and pre-specified (steps/day, minutes at ≥100 steps/min, step-based bouts);
- redoes the Lo 2022 bias analysis on that footing.

**Success.**
- A reader grasps the problem, the key evidence and the ask from page 1.
- The figures read at a glance.
- Every number in the brief traces to the appendix.

## 2. Context that shapes the pitch

These findings come from a PubMed check on 2026-10-03.

- **OAI step and cadence data exist, but not in the public release.**
  - Lo et al. 2015 (PMID 26407008), with Song and Dunlop as co-authors, used steps/day.
  - Fenton et al. 2018 (PMID 29729332) used minutes per day by cadence band (0, 1–49, 50–100, >100 steps/min) in 1,925 OAI participants.
  - Master et al. 2021 (PMID 34175271) used steps/day and cadence bands.
  - Song et al. 2010 (PMID 20806273) set the OAI counts-processing standard.
  - The public release has counts only.
- **No one has validated OAI self-reported walking against those steps.** The step papers are mostly led by partner groups.
- **GT1M steps undercount slow gait.**
  - Abel 2008 (PMID 19088773): 64% of steps were counted at 54 m/min.
  - Storti 2008 (PMID 18091020): a 19% undercount below 0.8 m/s in older adults.
- **Cadence threshold.** 100 steps/min corresponds to about 3 METs in adults aged 61–85 (Tudor-Locke 2021, PMID 34556146). Those adults were ostensibly healthy; knee OA was not studied.
- **Questionnaires against device step counts** in older adults correlate at 0.40–0.57 for walking questions and 0.17–0.52 for overall-activity scores (checked against the abstracts on 2026-10-04):
  - Hagiwara 2008 (PMID 18821997);
  - Heesch 2011 (PMID 21276752);
  - Giles 2009 (PMID 19420400);
  - Harris 2009 (PMID 19516162).

## 3. The brief: content

The brief is 4–6 US-letter pages. Its figures are numbered 1, 2, …; the appendix's are numbered A1, A2, ….

### Page 1 — the case in one page

Layout chosen in the visual companion: A's opening paragraph, B's sidebar and C's figure.

**Title.** "Does reported walking measure accelerometer activity — or walking?"
**Subtitle.** "Validating self-reported walking in the OAI against accelerometry — a proposal for joint work". The author and contact line follows (§6.3).

**Opening paragraph.** Plain words, for a first-time reader, in this order:
1. The OAI asked participants whether they walked for exercise, and the answer predicts knee outcomes (Lo et al. 2022).
2. We checked that answer, and PASE walking, against the ActiGraph at 48 and 72 months in N participants (N read from the run).
3. Almost everyone says yes, so the question alone separates walkers poorly. *How often* people say they walk carries most of the signal.
4. Our device reference is built from activity counts, which cannot tell walking from other moderate activity. That is where their step and cadence data come in.

**Left sidebar (shaded).** "Key results", then:
- sensitivity and specificity of the item against the device walker (validation sample);
- Youden's J, any walker → the strictest times-per-month cut (validation sample);
- Youden's J for PASE, any walking → at least 3–4 days/week, at both visits;
- the bias-correction factor 1/J, any walker → the strictest cut (Lo subset);
- a boxed **The ask** with one sentence.

**Main column.** Figure 1 with a plain-language caption.

**Figure 1** plots sensitivity against 1 − specificity for every walker definition:
- the walking item's times-per-month cuts, validation sample, in blue;
- PASE days-per-week cuts at 48 and 72 months, in orange, solid and dashed.

Triangles mark the definitions in current use. Dashed lines show equal-J contours, with labels set off the lines. The figure has true axes from 0 to 1.

**Footer.** A pointer to the appendix.

### Page 2 — what the counts already show

**Figure 2.** Horizontal bars of the share of people who are device walkers, by reported frequency, with 95% CI whiskers and direct labels. There are two panels:
- the walking item's times per month (non-walkers; 1–3, 4–8, ≥9 per month), validation sample;
- PASE days walked in the past week (never; 1–2; 3–4; 5–7), at 48 months.

The caption gives the 72-month PASE range.

**A paragraph on weekly walking.** PASE days × hours ranks people modestly against device bout minutes. Give:
- the ρ at both visits;
- the median self-report − device difference;
- κ at 150 min/week.

Place these against the published correlations (0.40–0.57 for walking questions, 0.17–0.52 for overall-activity scores); ours sit below the walking-question range and in the lower part of the overall-activity range.

**Figure 3.** Calibration: device purposeful-bout minutes per week (median and IQR) by band of estimated weekly walking. Both visits, with n labels.

### Page 3 — why counts aren't enough, and what steps add

- **Amber "weak link" box.** A purposeful bout is any run of at least `device.purposeful_bout_minutes` minutes at ≥ `device.mv_cutpoint` counts/min. Other moderate activity can form a bout, while slow walking may not reach the cut-point. The device walker is therefore a proxy, so part of the low specificity may belong to the reference, not the question. All values come from the run's assumptions.
- **"Why it matters for Lo 2022".** A record-level correction divides by J.
  - **Figure 4:** the correction factor 1/J with its interval, for each times-per-month definition (Lo subset). Draw it as bars; an unbounded upper limit is drawn as an arrow.
- **Blue box: what steps and cadence add.**
  - The walking-specific references: steps/day, minutes at ≥100 steps/min (Tudor-Locke 2021), and step-based bouts.
  - OAI cadence bands already exist (Fenton 2018).
- **Amber box: an open question for their expertise.** GT1M undercounting at slow gait (Abel 2008; Storti 2008). How should slow walkers with knee OA be handled?

### Page 4 — the proposed joint study

- **Aim.** One sentence (§1).
- **Roles table: "You bring" / "We bring".**

  | You bring | We bring |
  |---|---|
  | Step and cadence data, and how they were derived | Item and PASE coding; an open, reproducible pipeline |
  | Step-algorithm expertise and slow-gait handling | Validation statistics; the Lo 2022 bias analysis |
  | Co-design of the reference definitions | Drafting; shared code; aggregate-only outputs |

- **What we'd need.**
  - the existing daily step and cadence-band summaries at 48 and 72 months;
  - per-minute steps, if available;
  - a short description of how the steps were derived.
  - The brief also asks which files hold the steps, since the public release has counts only.
- **Blue box: "Already built".** The pipeline reproduces the OAI release's day-level files exactly. Quote the run's match counts. A step-based reference therefore drops into the same validation and bias steps.
- **Outputs.** A joint paper or papers, and shared code.

### Page 5 — references, and the appendix

- **References** in AMA style: Lo 2015, Lo 2022, Fenton 2018, Master 2021, Song 2010, Abel 2008, Storti 2008, Tudor-Locke 2021, and the four self-report-versus-steps papers.
- **One line on the appendix:** what it contains and that it comes from the same run.

## 4. Visual design (agreed in the visual companion)

- **Type and size.** Arial, 10–11 pt body. The page-1 lead paragraph is 11 pt (11.5 pt did not fit page 1 with Figure 1). Headings are in navy `#0b2e59`.
- **Colour.** The walking item is blue `#0072B2` and PASE is orange `#D55E00`, in every figure of both documents (the existing `oai_palette`). Muted tints show reference groups such as non-walkers and never.
- **Callouts.**
  - Blue left-rule boxes for points in our favour and for the ask.
  - Amber left-rule boxes (`#E69F00` rule) for limitations and open questions.
  - A shaded sidebar on page 1 only.
- **Figure 2.** Horizontal bars with CI whiskers and direct value labels. The roles table appears as a table on page 4.
- **Figures.** Drawn from the run's CSVs with `ggplot2` and the `oaireport` theme, and saved as PDF/PNG beside the report's figures. A figure and its caption stay on one page.
- **Legend rule.** Spec amendment 11 applies to the brief too: every figure and table defines its labels, populations and abbreviations.

## 5. The appendix: legibility pass on `report.qmd`

The report stays a neutral scientific record for the study team.

1. **A reading guide on one page at the front.**
   - Contents with page numbers.
   - One box defining the item walker, the device walker and the PASE walker, so later legends can refer to it.
   - One line on estimate and CI notation.
2. **One number style.** Every estimate is written "0.89 (0.86–0.91)". This shortens wrapping cells.
3. **The deferred presentation minors.**
   - Split the cut table into a PASE table and a walking-item table, each kept on its page.
   - Resize the tipping grid so pages 6–7 lose their blank space. The report is 18 pages (§7).
   - Move the ROC J labels off their lines.
   - Define n in the item legend and drop the "(walkers since age 50)" block title.
   - Give the PASE-walker n in the weekly legend.
   - Word the disclosure as "prompted by" and say the PASE-frequency rows are not confirmatory.
   - Generate "(48 or 72 months)" instead of typing it.
   - Close the figure group properly when there are no hex cells.
4. **Pre-specified results now shown.**
   - The Jonckheere–Terpstra trend across weekly bins (12a).
   - Guideline PPV and NPV (12a).
   - Lo-subset item shares by level and their trend (12b).
5. **Shared style.** Use the brief's fonts, colours and callouts through one `oaireport` style helper.
6. **Numbering.** Tables and figures are A1, A2, …. The footer reads "Technical report — page n". The brief's reads "Brief — page n".

The 12c months-per-year correction rows stay in TODO (out of scope here).

## 6. Tooling

### 6.1 Multiple documents per analysis

- `analysis.toml` `[report]` gains four optional keys:
  - `documents = ["brief.qmd", "report.qmd"]`: rendered in that order;
  - `combined = "walking_validation_brief.pdf"`: joins them in that order;
  - `part_titles = ["Brief", "Appendix: technical report"]`: one bookmark title per document in `combined`;
  - `local_assets = ["brief.local.yml"]`: untracked files copied next to the documents when present.
- `entry` keeps working on its own, so lo2022_walking is unchanged.
- **Validation.** With `documents`:
  - every file must be a `.qmd` directly in the analysis folder;
  - there are no duplicates;
  - `combined` must end in `.pdf` and requires `documents`;
  - `part_titles` needs `combined` and one title per document;
  - there are no duplicates in assets or local assets;
  - `combined` may not collide with a document's PDF or an asset.
  - `entry` and `documents` together is an error.

### 6.2 Rendering

`oai report <analysis> [--run]` renders each document with Quarto/Typst into `<results>/<analysis>/report/`, using the same results, assets and egress rules as today.

When `combined` is set, it joins the PDFs with `pypdf`, a new pure-Python dev dependency (report rendering is local-only). The combined PDF gets one top-level bookmark per part: "Brief" and "Appendix: technical report". It prints the path of every PDF.

### 6.3 Author and contact block

- The brief reads `analyses/walking_validation/brief.local.yml` with R's `yaml`, which is already in the report profile. The keys are `authors` (name, affiliation) and `contact` (name, email).
- `.gitignore` gains `*.local.yml`, so the file is never committed.
- Without the file, the brief prints a neutral placeholder: "Authors and contact to be added".
- YAML replaces the TOML mentioned in discussion, because R reads YAML without a new package.
- The `oai report` copy step treats the local file as an optional asset. It is copied if present and never required.
- The local file holds names only, no participant data. Egress rules are unchanged.

### 6.4 References

- `analyses/walking_validation/references.bib`, cited with Quarto citations.
- Typst's built-in american-medical-association style is used, so no CSL file is committed.

### 6.5 Shared style

`oaireport` gains a style helper, used by both documents:
- callout boxes (blue and amber);
- the page-1 sidebar;
- the reading-guide box;
- consistent figure sizing.

`.superpowers/` is git-ignored. This was done during brainstorming.

## 7. Testing

- **Unit tests (Python).**
  - The manifest accepts `documents`/`combined` and still accepts `entry` alone.
  - It rejects unknown files, duplicates, `combined` without `documents`, and `entry` together with `documents`.
  - The joiner's page count equals the sum of its parts, and its bookmarks exist.
  - A missing `brief.local.yml` gives the placeholder.
- **Unit tests (R, `oaireport`).** The style helpers produce the expected Typst blocks.
- **Real-data test.**
  - `oai report walking_validation` renders `brief.pdf`, `report.pdf` and the combined PDF.
  - The brief is ≤ 6 pages.
  - The combined page count is the sum of the two.
  - Neither PDF's text contains "NA", "NaN", "Inf" or an unrendered `` `r `` chunk.
  - Egress reports 0 problems.
  - The report is ≤ 18 pages.
- **Visual check.** Read every page as an image. Nothing overflows the right margin: check `pdftotext -bbox` xMax ≤ 547.2 pt.

## 8. Out of scope

- **New analyses.** Steps are not in hand.
- **Changes to the lo2022_walking report.**
- **The 12c months-per-year correction rows** (stay in TODO).
- **A slide deck.**
- **Sending the document.** The user sends it.

## 9. Open questions (for the user, not blocking)

- Which files hold the OAI step data? Master 2018 calls its step data public, but the public release has counts only. The brief asks the group directly.
- The author and contact details go into the local file before sending.
