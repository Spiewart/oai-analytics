# Facts confirmed for the brief report (2026-11-05)

Each fact: value, source, page. "Unconfirmed" means it could not be checked and must not be stated as fact.
No count below uses walker status. Counts are among the 2,582 people in `pase_frame.parquet` (IDs only).

## Codes and units

| Fact | Source | Page |
|---|---|---|
| `WORKAMT` (format JOBCAT): 1 Sitting; 2 Sitting/standing/walking; 3 Walking/handling <50 lbs; 4 Walking/handling >50 lbs; 88 Don't know. Code 1 is sitting. | `formats.pdf` | 128 |
| `WKHR7CV` label: "Occupational activities: number of hours worked, past 7 days (calc)", so hours a week. | `AllClinical00_Contents.pdf` | 56 |
| `V00400MCMP` (format PERFCOMP): 1 Completed test without stopping; 2 Completed test with one or more rests; 3 Attempted, unable to complete; 4 Not attempted, excluded; 5 Not attempted, other; 77 Not attempted, refused | `formats.pdf` | 178 |

Both expected readings (WORKAMT 1 = sitting, WKHR7CV = hours a week) hold.

## 400-meter walk

- Given at 0, 24, 48, 96 months (files 00, 03, 06, 10); no 400-m variables in the other cached AllClinical tables.
- Why a person was not tested: `400EXCL` is derived by `400MTRExcG.sas` (AllClinical00_Comments.pdf p.145) in this order: 1 could not complete the 20-m walk; 2 heart rate; 3 systolic BP; 4 diastolic BP; 5 other reason (SUPPO2); 6 walker or quad cane; 7 angina or shortness of breath needing a doctor; 8 recent hospitalization, surgery or cardiovascular event; 9 did not feel safe. Only the first reason is usually captured. Refused is .R, other and not-done reasons carry through, "no reason" is .D. (p.142 header comment.)
- Unconfirmed: numeric cutoffs. Variable names (HR110/HR135, SYS180/SYS199, DIAS100/DIAS109) suggest 110 or 135 bpm and BP limits, and the SAS code tests heart rate before the walk above 110 (p.145), but the protocol text was not reachable (oai.ucsf.edu connection refused; operations manual not in the release folder). TODO item added.
- Counts (completion status `V..400MCMP`; recorded time `V..400MTIM`), n = 2,582:

| Visit (months) | 1 | 2 | 3 | 4 | 5 | no status | time recorded | no time |
|---|---|---|---|---|---|---|---|---|
| 0 | 2,411 | 8 | 18 | 60 | 1 | 84 | 2,437 | 145 |
| 24 | 2,112 | 4 | 16 | 141 | 3 | 306 | 2,132 | 450 |
| 48 | 2,025 | 3 | 29 | 185 | 8 | 332 | 2,056 | 526 |
| 96 | 1,853 | 9 | 58 | 235 | 0 | 427 | 1,919 | 663 |

- Spec figures match: time recorded 2,437 at enrollment and 1,919 at 96 months; code 4 is 60 and 235.
- **For the draft sentence: 663 of 2,582 (25.7%) have no recorded 400MTIM at 96 months.** Breakdown: 235 not attempted and excluded (code 4); 427 with no completion status at all (344 of them also have no 20-m pace, so probably no clinic walk data; 83 have a 20-m pace but no 400-m status, reason unknown); 1 completer with no time.
- 96-month exclusion reasons among the 235: could not do 20-m walk 18; heart rate 21; systolic BP 8; diastolic BP 11; walker or cane 18; angina or shortness of breath 65; hospitalization, surgery or cardiovascular 64; felt unsafe 30. (Other reason 0.) Sum 235.
- "Times for those who stopped early" applies to code 3 (attempted, unable to complete): 58 people at 96 months, 57 of whom have a time at the stop point (2.2% of 2,582). Code 2 (rests) completed.
- Not checked: why 427 have no status (missed visit versus form not filled); inferred only.

## KOOS sport and recreation (`V00KOOSFSR`) at enrollment

- Missing for 581 of 2,582 (22.5%); present for 2,001. Items `V00KOOSFX1`-`FX5` (squatting, running, jumping, twisting/pivoting, kneeling; labels in AllClinical00_Contents.pdf p.38).
- Item-level pattern (overall, no walker status): the score is present for every person with at most 2 of 5 items blank (908 + 408 + 685 = 2,001) and missing for every person with 3 or more blank (336 + 186 + 59 = 581). So the score needs at least 3 of 5 answered. This is read from the pattern; KOOSG.sas is named in the release comments but its code is not printed there.
- Blank counts by item (of 2,582): squatting 362, running 1,326 (51%), jumping 1,432 (55%), twisting/pivoting 445, kneeling 260. Running is blank for 36% of those reporting no squatting difficulty and 85% of those with squatting blank, so blankness is not simply tied to severity. By enrollment year the score is missing for 25%, 23% and 18% (2004, 2005, 2006), so no sign of a form change. KOOS right-knee pain is present for everyone whose sport score is missing.
- **Why running and jumping are blank: unconfirmed.** The release comments give no reason. Not confirmed as a skip pattern or "cannot do" rule. TODO item added; the manuscript should say the reason is not documented.

## Journal limits (Osteoarthritis and Cartilage)

Unconfirmed. The guide for authors (sciencedirect.com, oarsijournal.com/authorinfo) returned HTTP 403 to automated and browser-pane fetches; no bypass was attempted. A web search returned only other journals' limits, not used. The spec's limits (2,000 words, 250-word abstract, 15 references, 2 display items, supplement permission, abstract headings) remain the user's pasted figures. TODO item added.

## Citations (PubMed records read 2026-11-05)

- Chinn S. A simple method for converting an odds ratio to effect size for use in meta-analysis. Stat Med 2000;19(22):3127-31. PMID 11113947, doi 10.1002/1097-0258(20001130)19:22<3127::AID-SIM784>3.0.CO;2-M. Abstract: "a ln(odds ratio) can be converted to effect size by dividing by 1.81". Check: exp(0.2 x 1.81) = 1.436 and exp(0.5 x 1.81) = 2.472, so about 1.44 and 2.47.
- Washburn RA, Smith KW, Jette AM, Janney CA. The Physical Activity Scale for the Elderly (PASE): development and evaluation. J Clin Epidemiol 1993;46(2):153-62. PMID 8437031, doi 10.1016/0895-4356(93)90053-4.
- Lo GH, Vinod S, Richard MJ, Harkey MS, McAlindon TE, Kriska AM, Rockette-Wagner B, Eaton CB, Hochberg MC, Jackson RD, Kwoh CK, Nevitt MC, Driban JB. Association between walking for exercise and symptomatic and structural progression in individuals with knee osteoarthritis: data from the Osteoarthritis Initiative cohort. Arthritis Rheumatol 2022;74(10):1660-7. PMID 35673832, doi 10.1002/art.42241. Existing bib entry matches the record.
- What Lo 2022 reports (abstract): among 1,212 participants with knee OA, walkers for exercise had lower odds of new frequent knee pain (OR 0.6, 95% CI 0.4-0.8) and of medial joint space narrowing progression (OR 0.8, 0.6-1.0), baseline to 48 months; walking survey at 96 months. The spec's phrase "linked walking to less frequent knee pain" is consistent, but more precisely it is less development of new frequent knee pain, in people with knee OA, measured over 0-48 months. Full text was not read.
