# Crepitus and incident symptomatic OA beyond 48 months: design

**Date:** 2026-10-21
**Builds on:** `analyses/lo2018_crepitus` (S2, replicated) and `analyses/exam_crepitus_soa` (exam crepitus), both of which stop at 48 months because Lo 2018 did and because their KL readings come from Project 15.

## What the release offers after 48 months

| Source | Covers | Documented? |
|---|---|---|
| Project 15 (`kxr_sq_bu`, READPRJ 15) | KL and JSN, baseline to 48 mo, every knee with ≥ 2 X-ray visits | Yes (`kXR_SQ_BU_Descrip.pdf`) |
| Project 37 (READPRJ 37, and 42 to be recoded as 37) | 72 and 96 mo (baseline and 48 mo re-read) for (a) knees still able to develop ROA (KL 0–1 at baseline, no KL ≥ 2 with JSN at 48 mo), (b) knees that developed ROA by 48 mo, (c) a random 246 baseline KL 2–3 knees. 3,834 knees, 2,314 people | Yes: "with Project 15, complete data for incidence of radiographic OA over 96 months" |
| Project 43 (READPRJ 43) | baseline, 48, 72, 96, 120 mo; 3,842 knees, 2,051 people, baseline KL 0–4 | No description in the release folder |
| OUTCOMES99 `V99E{R,L}XIOA` / `XIOAN` / `XNOA` | Earliest visit with KL ≥ 2 (or KL ≥ 2 with JSN), and last visit without ROA, combining projects; codes run to "incident at 120/132 mo" | Yes: the documentation recommends these over merging projects by hand |
| Frequent pain, visit days | Every visit (V08, V10, V12 checked) | — |
| KOOS S2 | Every visit to V12 | — |
| Exam crepitus | V00, V01, V03, V05, V06, V12 only (none at V08, V10) | — |

Project 37 re-reads changed 67 knees' ROA status. OUTCOMES99 records the earliest incident visit from either project, so knees that "wobble" back to KL < 2 later still count as ROA from their first incident visit (Appendix A.3).

**Coverage of our cohort** (right knees, Lo 2018 cohort with a baseline exam, 3,477 people):
- **Project 37:** reads 1,759 of them, but only 80 of the 1,106 with ROA and no frequent pain, the subgroup that carries the crepitus signal. That is by design: their ROA is already established and needs no re-reading.
- **Project 43:** reads 1,705, including 274 of those 1,106.

**Preview** (people without SOA at 48 months): 241 new SOA cases by 96 months and 326 by 120 months, against 655 by 48 months. By baseline exam: 97 of 930 exposed vs 144 of 1,892 unexposed by 96 months.

## Decisions

1. **ROA by visit from OUTCOMES99** (`outcomes.roa_source = "outcomes99"`). A knee has ROA at visit *v* if `V99E{side}XIOA` is "KL ≥ 2 at baseline" or an incident visit at or before *v*. This is the documented, project-combined status, and it is carried forward.
   - The `"readings"` source (Project 15, same visit) stays the default for Lo 2018. It is refused for any horizon past 48 months.
   - `outcomes.roa_definition`: `kl2` (`XIOA`, default) or `kl2_jsn` (`XIOAN`).
2. **Horizon** (`periods.horizon`):
   - `"10"` (96 months) is primary, where the documentation says incidence data are complete;
   - `"12"` (120 months) is a sensitivity analysis, because Project 43's selection is undocumented;
   - `"06"` reproduces the 48-month analyses.
3. **Periods:** exposure → outcome pairs are V00→V01, V01→V03, V03→V05, V05→V06, V06→V08, V08→V10 and V10→V12, cut at the horizon. The later periods are two years long, not one, so the one-period GEE gains a period factor (`model.period_term = "factor"`). `"none"` reproduces Lo.
4. **Exam exposure after 48 months:** there is no exam at V08 or V10.
   - `exposure.exam_after_48m = "carry_v06"` (default) uses the V06 exam for the V06→V08 period (its own visit), and carries it forward to V08→V10 and V10→V12.
   - `"none"` ends exam periods at V08.
   - S2 uses each period's own visit.
5. **Three models per measure**, each unadjusted / adjusted for age, sex, BMI / and, for exam, also adjusted for S2:
   - **L1, time-varying exposure, one period ahead:** Lo's design extended, GEE with a period factor.
   - **L2, baseline exposure, discrete-time hazard:** person-periods with the baseline measure fixed, GEE with a period factor. It handles loss to follow-up without counting dropouts as non-events.
   - **L3, by-horizon logistic:** baseline exposure; SOA by the horizon among people whose outcome is known at the horizon or who became cases earlier. Comparable to Lo's four-year table.
   - **L4:** L2 by baseline subgroup, with the exposure × subgroup test. Also for both measures together and their interaction.
6. **Regression anchor:** with `periods.horizon = "06"`, `outcomes.roa_source = "readings"` and `model.period_term = "none"`, the frames and the one-period and four-year ORs must equal those of `exam_crepitus_soa` (exam) and `lo2018_crepitus` (S2).
7. **Coverage report:**
   - outcomes observed per visit;
   - Projects 37 and 43 reads by subgroup;
   - how ROA status at 48 months differs between Project 15 readings and OUTCOMES99.

## Out of scope

Patellofemoral outcomes, structural progression, TKR as a separate outcome, and activity and accelerometry. These are later analyses that can reuse the same horizon machinery.
