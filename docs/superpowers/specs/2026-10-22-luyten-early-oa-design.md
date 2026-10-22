# Crepitus in Luyten early-stage knee OA: design

**Question.** Among knees with early-stage OA by the Luyten 2018 classification criteria, does crepitus (on examination, and self-reported) enrich for progression to radiographic OA (KL ≥ 2) and to symptomatic OA (SOA) by 48 and 96 months?

**Why.** The crepitus analyses so far split baseline knees by frequent pain and radiographic OA (`roa_nosx`, `noroa_sx`, `noroa_nosx`). The early-OA criteria cut across those groups: KL 0–1 knees with KOOS symptoms and a clinical sign, whether or not the pain is frequent. Mahmoudian 2021 built this group in OAI and showed it enriches for progressors, but did not test crepitus alone.

## Part 1: replicate the early-OA group (Mahmoudian 2021)

Mahmoudian A, Lohmander LS, Jafari H, Luyten FP. *Semin Arthritis Rheum* 2021;51:285–91 ([doi:10.1016/j.semarthrit.2020.11.002](https://doi.org/10.1016/j.semarthrit.2020.11.002)). The full text is not open access, so the targets come from the abstract until the PDF is in hand.

- **Unit:** knees (both knees of all 4,796 enrollees). The abstract counts knees.
- **Early-stage OA (Luyten 2018):** all three of:
  - baseline tibiofemoral KL 0–1;
  - KOOS ≤ 85 in at least two of four subscales: pain, symptoms, function in daily living, knee-related quality of life;
  - at least one of joint-line tenderness or crepitus on examination.
- **Controls:** KL 0–1 knees that do not meet the criteria.
- **OAI sources:**
  - KOOS pain `V00KOOSKP{R,L}`, symptoms `V00KOOSYM{R,L}`, quality of life `V00KOOSQOL` (one value per person).
  - The release has no KOOS daily-living subscale. It equals WOMAC function rescaled, `100 − V00WOMADL{R,L} × 100 / 68` (assumed).
  - Exam crepitus `V00{R,L}KPFCRE`; joint-line tenderness `V00{R,L}KMTTPN` (medial) and `V00{R,L}KLTTPN` (lateral).
  - KL from the Project 15 baseline reading (assumed; OUTCOMES99 as a variant).
- **Targets (abstract):**
  - 1,315 knees meet the criteria (27% of KL 0–1 knees);
  - mean age 59.2 vs 60.2 (early OA vs controls);
  - mean BMI 28.3 vs 26.8.
  - The ORs are reported only as ranges (structural 1.1–1.4, clinical 2.1–2.5 at 48 and 96 months), with undefined outcomes. They are reported beside ours, not graded.
- **Preview (2026-10-22 scratch count):** 1,098 knees (22% of 5,028 KL 0–1 knees). The gap goes to the ledger as open choices with variants.

## Part 2: crepitus within early OA

- **Framing 1, full Luyten group:** exam crepitus present (alone or with tenderness) vs tenderness only. Every knee in the group has one of the two signs, so the reference is tenderness, not "no sign". A knee with tenderness and a missing crepitus exam is not in Framing 1.
- **Framing 2, KL 0–1 with the KOOS criterion, no sign requirement:** exam crepitus present vs absent.
- **Self-reported crepitus (KOOS S2, `V00KSX{R,L}KN2`)** is not one of the criteria, so it is tested in both framings: any (at least rarely) vs never (assumed; five levels as a variant). The S2 model is adjusted for exam crepitus.
- **Outcomes:**
  - incident ROA, KL ≥ 2, by 48 and by 96 months, from OUTCOMES99 (`V99E{R,L}XIOA`), unknown after the knee's last reading without ROA (`V99E?XNOA`), as in `crepitus_soa_longterm`;
  - incident SOA (frequent pain plus ROA, or a knee replacement) by 48 and by 96 months, from `oai.derive.incident_soa.soa_status` run for each knee's side.
  - A knee is in a horizon's model when its outcome at the horizon is known, or it became a case earlier (`horizon.selection = "known_or_case"`, the long-term analysis's rule; `"complete"` as a variant).
- **Models:**
  - logistic GEE on knees (clustered within person, exchangeable);
  - Model 1: exposure + age, sex, BMI;
  - Model 2: Model 1 + the other crepitus measure.
- **Enrichment check:** early-OA group vs controls for the same four outcomes, crude and adjusted for age, sex and BMI.

## Out of scope

Effusion and Heberden's nodes (Mahmoudian's extended criteria), the CREDO and EsSKOA criteria, MRI outcomes, and time-varying exposure.
