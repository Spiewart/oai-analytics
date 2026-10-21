# Crepitus in the OAI: literature ledger

Searched 2026-10-21; updated the same day with a second pass on crepitus as a predictor of incident OA. This ledger records what each source says about crepitus, how it was read, and what is still unconfirmed. Entries marked **A** were read as a PubMed abstract, **F** were read as full text through an automated fetch that returned only the passages asked for (so unreported detail is unknown, not absent), **L** are known from a listing or search snippet only.

## The OAI measures

Variables were checked against every visit's AllClinical header (see `README.md`).

| Measure | Variables | Visits (month) |
|---|---|---|
| Examiner-rated patello-femoral crepitus, yes/no | `V##RKPFCRE`, `V##LKPFCRE` | V00 (0), V01 (12), V03 (24), V05 (36), V06 (48), V12 (120) |
| Examiner-rated painful or tender patellar grind, yes/no | `V##RKPGDPN`, `V##LKPGDPN` | V00, V01, V03, V05, V06 |
| KOOS S2, grinding or clicking or other noise when the knee moves, last 7 days (0 never to 4 always) | `V##KSXRKN2`, `V##KSXLKN2` | V00 through V12 (every visit code, including phone and remote contacts) |

WOMAC has no crepitus item. V13 and V14 carry none of the three.

## OAI studies

| Outcome area | Source | Crepitus measure | n | Result | Read |
|---|---|---|---|---|---|
| Incident symptomatic OA | Lo GH et al., *Arthritis Care Res* 2018;70:53. [doi](https://doi.org/10.1002/acr.23246) | KOOS S2 at baseline, 12, 24, 36 months | 3,495 participants without baseline symptomatic OA | Adjusted ORs for incident symptomatic OA were 1.5, 1.8, 2.2, 3.0 for rarely, sometimes, often, always versus never (trend p < 0.0001). Over 75% of cases arose in knees with radiographic OA but no frequent pain. Patellofemoral OA was not assessed. | A |
| Incident symptomatic OA (precursor) | Lo GH et al., ACR 2016 abstract 308, "Crepitus as a risk factor for symptomatic knee osteoarthritis". [link](https://acrabstracts.org/?p=15727) | KOOS S2 at baseline | Right knee only (per the web summary) | Same question, earlier cut. | L |
| Incident radiographic and symptomatic OA (precursor) | Lo GH et al., OARSI 2014 abstract, "Subjective crepitus predicts subsequent development of radiographic and symptomatic tibiofemoral osteoarthritis: data from the Osteoarthritis Initiative". *Osteoarthritis Cartilage* 22(S). [link](https://www.oarsijournal.com/article/S1063-4584(14)00371-9/fulltext) | KOOS S2 | Right knees without radiographic OA at baseline | Concludes S2 strongly predicts later radiographic and symptomatic tibiofemoral OA; sample size and estimates not retrieved. | L |
| Cross-sectional (exam crepitus) | Mahmoudian A et al., EULAR 2023 (POS1374) and OARSI 2024 abstracts | Exam crepitus and effusion | Symptomatic knees without joint-space narrowing | Crepitus and effusion associated with possible tibiofemoral osteophytes. Not longitudinal. | L |
| TKR | Pazzinatto MF et al., *Braz J Phys Ther* 2019;23:329. [doi](https://doi.org/10.1016/j.bjpt.2018.09.009) | "Knee crepitus" (the abstract does not name the variable) | 4,566 | Baseline crepitus did not predict TKR at 36 months (p = 0.58 right, 0.67 left). Extension strength declined about 2% more with crepitus. No effect on quality of life or performance. | A |
| Pain, function, quality of life | Pazzinatto MF et al., *Braz J Phys Ther* 2019;23:491. [doi](https://doi.org/10.1016/j.bjpt.2018.11.001) | "Knee crepitus" (variable not named) | 584 matched pairs; 361 with crepitus in one knee only | Small effects: crepitus group had lower self-reported function and quality of life and more pain (3 to 11%, effect 0.17 to 0.41). No difference in 20 m walk or chair stand. | A |
| Structural and clinical progression | Mahmoudian A et al., *Semin Arthritis Rheum* 2021;51:285. [doi](https://doi.org/10.1016/j.semarthrit.2020.11.002) | Crepitus or joint-line tenderness as one clinical criterion, with KOOS and KL 0 to 1 | 1,315 knees met the early-OA criteria (27%) | Enrichment for progressors at 48 and 96 months: structural OR 1.1 to 1.4, clinical OR 2.1 to 2.5. Adding effusion or Heberden's nodes raised ORs to 4.2 and 3.3. Crepitus was not tested alone. | A |
| Incident tibiofemoral OA (exam crepitus) | Mahmoudian A, Lohmander LS, Hawker G, Neogi T, Englund M, OARSI 2023 abstract 179, "Association of baseline knee crepitus with tibiofemoral osteoarthritis development in patients with knee symptoms but no or minimal radiographic osteoarthritis". *Osteoarthritis Cartilage* 31(S1):S214–5. [doi](https://doi.org/10.1016/j.joca.2023.01.194) | OAI exam crepitus at baseline (palm over the patella, passive flexion-extension, supine) | 576 subjects from the Progression and Incidence cohorts with KL 0–1 and frequent knee symptoms; one random knee if both eligible; 264 (45.8%) with crepitus; 60% women, age 58.9 (8.5), BMI 29.6 (4.9) | Outcome at 4 years: incident tibiofemoral JSN and/or more osteophytes in either compartment (310/576), and the same with persistent symptoms (153/576). ORs for crepitus, crude / adjusted for age, sex, BMI / plus KL: 1.3 (1.0–1.8), 1.2 (0.8–1.7), 1.2 (0.9–1.7); with symptoms 1.1 (0.8–1.7), 1.1 (0.7–1.6), 1.0 (0.7–1.5). Not associated. Abstract text and Table 1 supplied by the user, 2026-10-21. | A |
| MRI features, cross-sectional | Drummen SJJ et al., *Osteoarthritis Cartilage* 2026;34:918. [doi](https://doi.org/10.1016/j.joca.2026.02.015) | Crepitus is one input to the CREDO early-OA probability | 1,500 knees analyzed (KL < 2) | Early-stage OA by CREDO had higher prevalence of MRI abnormalities, for example BMLs PR 2.38 against no OA. | A |
| Synovitis worsening | Deng H et al., *Front Med* 2023. [PMC10495831](https://pmc.ncbi.nlm.nih.gov/articles/PMC10495831/) | Painful patellar grind (the exam item), baseline, 12, 24 months; "frequent" = positive at more than two visits | 1,119 knees, 161 with grind at baseline (14.3%) | Baseline grind: OR 1.67 (1.13 to 2.46) for synovitis worsening over 24 months, OR 2.47 in women, not significant in men. Crepitus itself is mentioned only as the hand placement technique. | F |
| Phenotyping | Keefe TH et al., *Osteoarthr Cartil Open* 2023. [PMC9932103](https://pmc.ncbi.nlm.nih.gov/articles/PMC9932103/) | `V00RKPFCRE`, `V00LKPFCRE`, `V00RKPGDPN`, `V00LKPGDPN` as AJIVE inputs | 6,265 knees | No variable-specific results. | F |
| Phenotyping | Nelson AE et al., *PLoS One* 2022. [PMC9129051](https://pmc.ncbi.nlm.nih.gov/articles/PMC9129051/) | Baseline patello-femoral crepitus and patellar grind as bicluster features | Bicluster 4 has 188 knees from 147 people | Crepitus separates biclusters 1 from 4 and 5 (direction not stated in the text read); patellar grind is more common in bicluster 4. No counts. | F |
| Accelerated radiographic OA | Price LL et al., *J Orthop Res* 2019. [PMC6778707](https://pmc.ncbi.nlm.nih.gov/articles/PMC6778707/) | Baseline crepitus from the clinical exam, a candidate predictor | Not given for crepitus | Not among the important variables in the CART models. | F |
| Pain, function and incidence prediction | Chen T et al., *Digit Health* 2023. [PMC10685797](https://pmc.ncbi.nlm.nih.gov/articles/PMC10685797/) | Patello-femoral crepitus, right knee, as an input | 3,200 | One of the top five inputs for at least one outcome in at least one year; which outcome and year could not be read. No effect size. | F |
| Accelerated KOA symptoms | Davis J et al., *Clin Rheumatol* 2017;36:1083. [doi](https://doi.org/10.1007/s10067-017-3564-2) | Individual KOOS symptoms and WOMAC items | Not given | Reported items: lying down, straightening the knee, walking. Whether S2 was tested is not in the abstract. | A |
| Pain phenotypes | Kittelson AJ et al., *Pain Med* 2021. [PMC7971470](https://pmc.ncbi.nlm.nih.gov/articles/PMC7971470/) | Unknown | Unknown | Appeared in a full-text search for OAI and crepitus; the page could not be fetched. | L |
| Early-OA criteria (no OAI analysis) | Luyten FP et al., *Semin Arthritis Rheum* 2018;47:457. [doi](https://doi.org/10.1016/j.semarthrit.2017.08.006) | Crepitus or joint-line tenderness | None | Consensus: KOOS at or below 85 in two subscales, one clinical sign, KL 0 to 1. | A |
| Early-OA candidate items (no analysis) | Mahmoudian A et al., *Osteoarthritis Cartilage* 2024 (EsSKOA Delphi). [PMC11302115](https://pmc.ncbi.nlm.nih.gov/articles/PMC11302115/) | "Self-reported crepitus", a candidate symptom item | None | To be tested in Phase 2. | F |

### OAI studies that do not use crepitus but bear on the questions

- Yang Y et al., *Front Med* 2025, stair-climbing volume and patellofemoral cartilage. [PMC12682809](https://pmc.ncbi.nlm.nih.gov/articles/PMC12682809/). Crepitus is not a variable; the authors name the patellar grind test as future work. **F**
- OAI accelerometry and symptom worsening, 782 participants over two years. [PMC12899396](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12899396/). No crepitus. **L**

## Outside the OAI (context for interpreting the two measures)

| Source | Finding | Read |
|---|---|---|
| Couch JL et al., *Osteoarthritis Cartilage* 2025;33:764. [doi](https://doi.org/10.1016/j.joca.2024.12.004) | After ACL reconstruction (n = 184), KOOS S2 "often" or "always" against a palpated three-squat exam: sensitivity 47%, specificity 73%, LR+ 1.75, LR- 0.72. | A |
| Couch JL et al., *Br J Sports Med* 2025;59:126. [doi](https://doi.org/10.1136/bjsports-2024-108866) | 103 studies: crepitus prevalence 41% in the general population, 81% in OA; OR 3.79 for radiographic OA; low to very low certainty. | A |
| Couch JL et al., *Arthritis Care Res* 2026;78:398. [doi](https://doi.org/10.1002/acr.25637) | After ACL reconstruction, self-reported crepitus at 1 year did not predict worsening MRI features by 5 years. | A |
| de Oliveira Silva D et al., *Phys Ther Sport* 2018. [doi](https://doi.org/10.1016/j.ptsp.2018.06.002) | In 165 women with patellofemoral pain, crepitus was unrelated to physical activity level. | A |
| Drum EE et al., *Musculoskelet Care* 2023. [doi](https://doi.org/10.1002/msc.1793) | Interviews (24): crepitus was of less concern than pain, but some changed how they exercised. | A |
| King LK et al., *Osteoarthritis Cartilage* 2025. [doi](https://doi.org/10.1016/j.joca.2025.05.008) | Crepitus was among the first symptoms in 42% of 92 people with knee OA. | A |
| Schiphof D et al., *Osteoarthritis Cartilage* 2014 (Rotterdam MRI sub-study), PMID 24583066 | Exam crepitus associated with patellofemoral (not tibiofemoral) MRI features, OR 2.61–5.49; cross-sectional. | A |
| Sayre EC et al., *PLoS One* 2021, PMID 34648543. [doi](https://doi.org/10.1371/journal.pone.0258451) | Vancouver early knee OA cohort (n = 122 longitudinal): rheumatologist-graded crepitus (none / fine / coarse) and MRI OA-COM progression over about 7.5 years. Coarse crepitus ORs 3.63 (0.80–16.35) and 6.48 (0.94–44.50) at the two upper cut-points; not significant. | F |
| de Klerk BM et al., *Ann Rheum Dis* 2011, PMID 22128077. [doi](https://doi.org/10.1136/annrheumdis-2011-200172) | Rotterdam: determinants of incident ROA in 623 people with knee complaints; whether crepitus was a candidate is not in the abstract and the full text was not reached. | A |
| Peat 2007 (PMID 17530679), Parsons 2017 (PMID 29101670) | Exam crepitus associated with prevalent radiographic OA; cross-sectional. | A |

## Coverage by outcome

| Outcome of interest | OAI evidence found | Gap |
|---|---|---|
| Incident symptomatic OA | Lo 2018 (KOOS S2) | Exam crepitus now tested in `analyses/exam_crepitus_soa` (unpublished): four-year adjusted OR 1.91 (1.60–2.28), 1.76 after adjusting for S2; the effect differs by baseline subgroup (p = 0.003): 1.81 with ROA and no frequent pain, no evidence of association without ROA (wide CIs). No patellofemoral definition. |
| Incident radiographic OA | Two abstracts only: Lo 2014 OARSI (S2, right knees without ROA; radiographic plus symptomatic outcome) and Mahmoudian 2023 OARSI (exam crepitus, 576 symptomatic KL 0–1 knees, JSN/osteophyte development; null, OR 1.2, 0.9–1.7). | No full paper. Exam crepitus against incident KL ≥ 2 in all at-risk knees, repeated measures, and S2 and exam together are all untested. |
| Progressive OA | Mahmoudian 2021 (composite criteria); Price 2019 (no signal); Chen 2023 (unclear) | Crepitus alone not tested for KL, JSW or MRI progression. |
| Knee replacement | Pazzinatto 2019 (36 months, null) | No longer follow-up, time-to-event or exam-versus-self-report comparison. |
| Activity levels | None | Open. |
| Weight loss and protective behaviors | None | Open. |
| Accelerometry | None | Open. Accelerometer data exist at V06 and V08, where the exam item (V06) and KOOS S2 (V06, V08) both exist. |

## Search log

- PubMed (title and abstract): "Osteoarthritis Initiative" with crepitus gave 8 papers; crepitus in the title with knee gave 35. I read the 22 most recent: 10 concerned crepitus after knee arthroplasty (implant design, patellar resurfacing) and were set aside; the 13 oldest (2016 and earlier) were not read. Combined queries on accelerometry, physical activity and weight loss returned nothing OAI-specific.
- Europe PMC full-text search, "Osteoarthritis Initiative" with crepitus or "grinding, hear clicking": 75 hits, which surfaced Deng 2023, Keefe 2023, Nelson 2022, Price 2019, Chen 2023, Davis 2017, Kittelson 2021 and Yang 2025. Many hits are incidental mentions.
- Web search (Google Scholar was not queried directly): ACR abstracts, OARSI supplements, accelerometry, weight loss and exercise. Found the Lo 2016 ACR abstract and the Mahmoudian 2023 OARSI title.
- Not searched: OARSI 2024 to 2026 supplements, ACR 2017 to 2025 abstract archives beyond the web results, dissertations, bioRxiv/medRxiv.

## To confirm

- Estimates and n in the Lo 2014 OARSI abstract (ask Grace).
- Whether de Klerk 2011 (Rotterdam) tested crepitus as a determinant of incident ROA.
- Which OAI variable Pazzinatto 2019 used (exam item or KOOS S2).
- Whether Davis 2017 and Kittelson 2021 analyzed the S2 item.
- Full-text methods and Table 2 of Chen 2023, to see which outcome crepitus supported.
