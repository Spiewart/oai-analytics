# Clinical-Reader Version of the Walking-Validation Results — Design

**Date:** 2026-10-05
**Status:** Draft for review
**Builds on:** `2026-10-03-northwestern-brief-design.md` (the brief and the technical report), `2026-10-01-walking-validation-design.md`

## 1. Purpose

The brief is followed by the technical report, as the appendix. Readers found three problems with that combination:
- **Jargon.** The appendix reads heavy on biostatistics and computer-science terms that are uncommon in clinical research.
- **Tables.** The tables are dense, and they do not mark which findings are significant.
- **Mixed samples.** The validation analyses and the Lo et al. 2022 analyses are interleaved in the same tables.

The brief also refers to the bias analysis before introducing it.

This design adds a **clinical-reader version** of the results (`clinical.qmd`). It becomes the brief's appendix in the PDF that is sent. The technical report stays, unchanged, as the full record.

**Framing.** The original authors hold that the walking question and accelerometry measure different things. The new text must not read as an attack on the question or on Lo et al. 2022. It explores:
- how well the walking question and the PASE walking item agree with the device;
- how that agreement could bear on Lo et al. 2022's associations;
- what an accelerometry-based alternative assessment would look like.

The word "bias" stays out of the brief's and the clinical version's headings and main text. The technical report keeps its formal terms.

**Reusability.** Every new presentation feature lives in the shared report tooling, not in this analysis:
- technical-note superscripts with linked notes;
- significance bolding;
- the combined-document selection;
- PDF text checks.

Any analysis's documents can use them. See §6.

**Success.**
- A clinical researcher can read the appendix without a statistics glossary. Technical terms appear only in linked notes.
- Every table holds one sample, has at most five columns, and bolds results whose 95% CI excludes "no difference".
- Part 1 (validation) and Part 2 (Lo et al. 2022) are separate.
- Every number comes from the run.

## 2. What gets produced

`oai report walking_validation` writes:

| File | Content | Pages |
|---|---|---|
| `brief.pdf` | the brief, revised (§3) | 5 |
| `clinical.pdf` | new: results for clinical readers (§4) | ≤ 12 |
| `report.pdf` | the technical report; text unchanged | ≤ 18 |
| `walking_validation_brief.pdf` | **the file to send**: brief + clinical version; bookmarks "Brief" and "Appendix: results" | ≤ 17 |

`report.pdf` is rendered as before but is not part of the sent file. The brief says the full technical report is available on request.

## 3. The brief: changes

1. **New lead sentence on page 1.** It goes after the first sentence, and is neutral:
   "In Lo et al. 2022, walkers had about 40% lower odds of developing frequent knee pain; we also asked how sensitive that association is to how walkers are classified."
   The 40% is the published odds ratio, cited.
2. **The fourth sidebar result becomes the robustness result.**
   - The value is the count of tipping-point cells in which the new-frequent-knee-pain association's 95% interval excludes 1, out of the feasible cells (e.g. "65 of 65").
   - The label reads roughly: "plausible accuracy settings (sensitivity ≥ 0.80) in which Lo et al. 2022's walking–knee-pain association holds".
   - The count and the sensitivity floor are read from `bias_tipping.csv`.
   - The 1/J multiplier moves to page 3 only.
3. **Page 3.**
   - "Why it matters for Lo et al. 2022" becomes "**How sensitive is the Lo et al. 2022 association to classification?**".
   - Its text explains, in plain words, that allowing for misclassification divides the walking gap between outcome groups by J. So a small J makes a single re-estimate unsteady, and stricter definitions steady it.
   - Figure 4 (the multiplier) stays. Its caption says "how much a re-estimate depends on the walker definition".
   - No "bias" or "correction" in headings or main text.
4. **The timing paragraph** gains the constructs point:
   "The question also asks about a habit of walking for exercise since age 50, the device one week of current activity, so the two may measure different things."
5. **Appendix pointers** (the page-1 italic line and the page-5 line) read:
   "The appendix summarises every result for clinical readers; the full technical report is available on request."
6. **Page 1 still ends on the appendix pointer.** Figure 1's height shrinks as needed. The brief stays at 5 pages.

## 4. The clinical version (`analyses/walking_validation/clinical.qmd`)

- **Title:** "Walking question and accelerometry in the OAI: results". Subtitle: "Appendix to the brief: every result in plain language. The full technical report is available on request."
- **Numbering:** tables and figures are A1, A2, … (it is the appendix).
- **Footer:** "Appendix — page n".
- **Style:** the brief's fonts, colours and navy headings.

### 4.1 Front page

- **Key points.** Four or five plain bullets, with numbers from the run.
- **"Words used in this appendix".** A boxed list, using `reading_guide()`:
  - walker (by the question);
  - device-defined walker;
  - PASE walker;
  - sensitivity and specificity, as shares ("of the people the device calls walkers, the share who said they walk"; "of those it calls non-walkers, the share who said they don't");
  - positive and negative predictive value;
  - Youden's J ("sensitivity + specificity − 1; 0 = no better than chance, 1 = perfect");
  - 95% confidence interval;
  - the bold rule.
- **Who is in each part.** A two-row table:
  - Part 1: the 1,567 participants with a walking answer and device data.
  - Part 2: the 767 of them in the Lo et al. 2022 cohort.

### 4.2 Part 1 — Does the walking question agree with the device? (validation sample only)

1. **Who was studied (Table).** Answered the question, with device data, walkers and non-walkers, device-defined walkers. From `flow.csv` and `metrics`.
2. **Do people who say they walk move more? (Table + Figure).**
   - The table: device measure, median for walkers (n), median for non-walkers (n), difference (95% CI), and difference adjusted for age, sex and BMI (95% CI). From `validity_known_groups` (validation rows).
   - The figure: the technical report's known-groups figure, reused.
3. **More reported walking, more recorded activity? (Table).** Device measure by amount band (none / lower / upper) with the test for trend. From `validity_dose` (validation rows).
4. **How well does "yes" pick out device-defined walkers? (Table).** Sensitivity, specificity, PPV, NPV and J, each with its 95% CI. From `validity_classification` (validation).
5. **Does asking how often help? (Table + Figure + Table).**
   - Frequency cuts: definition, sensitivity, specificity, J. Walking question (times per month, validation) and PASE days (48 and 72 months).
   - The frequency-cut figure (the technical report's ROC figure), reused.
   - Weekly walking: rank correlation, median difference (minutes per week), and agreement at 150 minutes per week (kappa), per visit.
6. **How does PASE compare? (Table).** The PASE walker against the device walker per visit: sensitivity, specificity, J; and the rank correlation with device minutes. From `validity_pase`.

### 4.3 Part 2 — What the agreement means for Lo et al. 2022 (Lo 2022 participants with device data)

1. **Agreement in these participants (Table + Figure).**
   - The table: sensitivity, specificity, PPV, NPV, J. From `validity_classification` (lo_subset).
   - The figure: a Lo-subset-only version of the subgroup figure (KL grade, frequent pain, outcome event). It is drawn in `clinical.qmd` from `validity_strata`, with the brief's colours.
2. **Two ways to read low agreement (text).**
   - Imperfect recall or reporting.
   - Different constructs: a habit of walking for exercise since age 50, against one week of current activity of any kind recorded years earlier, and activity counts that are not walking-specific.
   - Activity counts cannot separate the two. A walking-specific device measure could.
3. **Lo et al. 2022's results, replicated (Table).** Outcome, published odds ratio (95% CI), our odds ratio (95% CI), adjusted model. From `lo2022_t2.csv` (metrics `t2.<outcome>.or_adj`, columns `published` and `ours`, parsed with `oaireport::parse_or()`).
4. **How sensitive is the association to classification? (text + Figure + Tables).**
   - **The idea.** Plain text with the worked example: the walking gap between outcome groups, re-estimated by dividing by J. Its numbers come from the run (published Table 2 counts; a grid cell; the Lo-subset accuracy).
   - **The tipping-point grid (Figure).** The technical report's tipping figure, reused. Its caption leads with the result:
     - for new frequent knee pain, the association holds in every feasible setting;
     - for KL-grade worsening, it holds at lower assumed accuracy, not near perfect accuracy;
     - assumes misclassification is the same in people with and without the outcome.
   - **Why activity counts cannot anchor a single re-estimate (Table).**
     - The table: outcome, share of simulations giving impossible values (misclassification the same in both groups), and the same share when it differs by group. From `bias_pba` (adjusted model).
     - The text says no reliable single re-estimate exists against this reference. That is a limit of the reference, and the technical report has the full simulation results.
   - **Steadier with stricter definitions (Table).** Walker definition, sensitivity, specificity, J and the multiplier 1/J. From the Lo-subset correction rows.
5. **An accelerometry-based alternative: the proposal (text).**
   - Define a device walking exposure with the accelerometry group: steps per day, minutes at ≥ 100 steps per minute, step-based bouts.
   - Refit Lo et al. 2022's models with it, and compare with the results from the question.
   - This tests directly whether the two measure the same thing.
   - Computing a counts-based version now is out of scope (§9).

### 4.4 Methods in brief, and Technical notes

- **Methods in brief.** One page in plain words: samples, device processing (valid days, bouts), the statistics named plainly. It ends with a pointer to the technical report.
- **Technical notes.** The linked notes (§5.3), in order of first reference.

## 5. Writing rules for the clinical version

### 5.1 Tables

- One sample per table, at most five columns. Group sizes go in headers, not their own column.
- Cell formats:
  - estimates are written `0.89 (0.86–0.91)` with `fmt_ci()`;
  - minutes are whole numbers;
  - counts have thousands separators.
- **Bold.** An estimate is bold when its 95% CI excludes "no difference": 0 for differences, correlations, kappa and J; 1 for odds ratios. A test for trend is bold when p < 0.05. Sensitivity, specificity, PPV and NPV are never bold. A CI limit exactly at the null is not "excluding". A missing CI is never bold.
- **Legends.** Two or three plain sentences: who is included, what the columns mean, and the bold rule.

### 5.2 Language

These terms appear only in Technical notes, never in the main text (headings, body, tables, legends):
- Hodges–Lehmann; rank-biserial; Jonckheere–Terpstra; permutation;
- bootstrap; Wilson; Spearman–Brown; deattenuated; limits of agreement;
- non-differential; differential misclassification;
- probabilistic bias analysis; bias analysis; draws; discarded;
- device wave; purposeful bout; MV.

Plain replacements:

| Technical term | Plain replacement |
|---|---|
| Hodges–Lehmann difference | median difference |
| Jonckheere–Terpstra | test for trend |
| Spearman ρ | rank correlation |
| 95% CI (bootstrap/Wilson) | 95% CI |
| device wave | accelerometer visit |
| purposeful bout | a bout of 10 or more minutes of moderate-to-vigorous activity (defined once) |
| non-differential | the same in people with and without the outcome |
| probabilistic bias analysis | simulation of misclassification |
| draws discarded | simulations that gave impossible values |

### 5.3 Technical notes (superscript links)

- **Marker.** A technical term gets a superscript **letter** (a, b, c, …) at its first use in each part. Letters keep the notes apart from the numbered reference citations.
- **Links.** The marker is a hyperlink to its note in the "Technical notes" list at the end. Each note links back to the term's first marker.
- **Content.** A note names the technical method and states it in two or three sentences, with the run's settings where they matter (e.g. the number of bootstrap resamples).

## 6. Reusable tooling

Nothing in this section is specific to walking validation.

### 6.1 `oaireport` (R)

1. **Technical notes.**
   - `tech_notes(entries)` creates a note registry from a named character vector `c(key = "note text", …)`.
   - It returns an object with:
     - `$ref(key)`: the superscript marker for a key. Letters are assigned in order of first reference. The first reference of each key carries a Typst label, so the note can link back to it.
     - `$list(title = "Technical notes")`: the notes block, as lines for a `results: asis` chunk, in order of first reference.
   - `$ref()` on an unknown key is an error. Notes never referenced are left out of `$list()`.
   - Markers render as Typst `#super[#link(<tn-key>)[a]]`, with stable, escaped labels.
   - `standard_tech_notes()` returns default note texts for common methods, which an analysis can override or extend:
     - Hodges–Lehmann median difference; Wilson CI; bootstrap CI; test for trend (Jonckheere–Terpstra, permutation);
     - Spearman rank correlation; sensitivity/specificity; PPV/NPV; Youden's J; Cohen's kappa;
     - limits of agreement; median regression adjustment; misclassification simulation (probabilistic bias analysis); tipping-point analysis.
2. **Significance.**
   - `ci_excludes(lo, hi, null)` returns a logical vector, TRUE when both limits are strictly on one side of `null`, and FALSE for a missing limit.
   - `compare_table()` gains `bold = NULL`: a logical matrix of the table's shape. Cells marked TRUE are set in bold (tinytable cell style).
3. **Reused as is:** `fmt_ci`, `reading_guide`, `numberer`, `callout`, `figure_group`, `table_note`, `brief_colours`.

### 6.2 `oai` (Python)

1. **Combined document selection.** `[report]` gains an optional `combined_documents = [...]`.
   - It must be a non-empty list of documents listed in `documents`, with no duplicates.
   - `combined` joins them in that order.
   - `part_titles` must then have one title per combined document.
   - Without the key, `combined` joins every document, as now.
2. **PDF text checks** (`src/oai/pdfcheck.py`, used by tests; any analysis can use them):
   - `max_right_edge(pdf)`: the largest word right edge, via `pdftotext -bbox`. It returns None when `pdftotext` is unavailable.
   - `find_terms(pdf, terms, stop_heading=None)`: each term that occurs in the PDF's text before `stop_heading`, with its page. Matching is case-insensitive and on whole words. The real-data test uses it for the jargon check with `stop_heading="Technical notes"`.

### 6.3 Shared setup for this analysis

`analyses/walking_validation/report_setup.R` holds what `report.qmd`'s opening chunks define and both documents need:
- result loading and the assumption accessor;
- number formatters and name maps;
- the result lookups (`cp_get`, `ci_get`, `pick` and similar);
- the walker and device definitions.

`report.qmd` and `clinical.qmd` source it. It joins `[report] assets`. After the move, `report.pdf`'s text must be identical to before (a `pdftotext` diff).

## 7. Testing

- **Python unit tests:**
  - `combined_documents` — valid subset, unknown document, duplicates, title count, default unchanged;
  - `render_report` joins only the selected documents;
  - `pdfcheck` — right edge on a PDF built in the test, `find_terms` with and without `stop_heading`, whole-word matching.
- **R unit tests (`oaireport`):**
  - `tech_notes`:
    - letters follow first-reference order;
    - repeated references reuse the letter;
    - an unknown key errors;
    - unreferenced notes are omitted;
    - labels are escaped;
    - the list's back-link targets the first marker.
  - `ci_excludes` edge cases: a limit on the null, NA, odds ratios with null 1.
  - `compare_table(bold =)`: a shape mismatch errors, and TRUE cells are bold in the Typst output.
- **Real-data test** (`test_walking_validation_report_renders`):
  - PDFs and pages:
    - `brief.pdf`, `clinical.pdf`, `report.pdf` and the combined PDF all exist;
    - the brief is ≤ 6 pages, `clinical.pdf` ≤ 12 and `report.pdf` ≤ 18;
    - the combined PDF's pages = brief + clinical;
    - its bookmarks are "Brief" and "Appendix: results".
  - Text and margins:
    - no NA, NaN or Inf text;
    - right edges within the margins, via `pdfcheck`;
    - no §5.2 term in `clinical.pdf` before "Technical notes", via `pdfcheck.find_terms`;
    - egress shows 0 problems.
- **Technical report unchanged:** the `report.pdf` text diff before and after the shared-setup move is empty.
- **Visual check:** read every page of the brief and of the clinical version as images.

## 8. Wording rules (public repository)

Public text names no individuals except as cited authors, and describes no personal relationships. It says "the original authors" or "the study team". Every number comes from the run. Literature values are cited.

## 9. Out of scope

- Computing a counts-based accelerometry exposure in Lo et al. 2022's models. That will be a later, pre-specified analysis amendment.
- Changes to the technical report's text or numbering.
- The lo2022_walking report. It can adopt the §6 tooling later.
- New analyses of any kind.
