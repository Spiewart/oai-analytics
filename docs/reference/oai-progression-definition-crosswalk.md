A practical crosswalk linking each operational definition of knee osteoarthritis (OA) progression used in the Osteoarthritis Initiative (OAI) to the public dataset table(s) and variable(s) required to compute it. It is a companion to the two earlier documents in this series (the progression-definitions review and the dataset table-structure summary).

## How to read this crosswalk

Each row states (1) the progression definition and its threshold, (2) the OAI table stem where the source data live, (3) the representative variable(s) needed, and (4) the anchoring literature. Three conventions govern every entry:

- **Visit coding.** The visit is encoded both in the table-name suffix and the variable prefix (V00 = baseline, V01 = 12 mo, V03 = 24 mo, V05 = 36 mo, V06 = 48 mo, V08 = 72 mo, V10 = 96 mo; odd codes are interim telephone contacts). Progression is almost always a **change** score, so each definition requires the variable at two or more visits.

- **Record grain and keys.** Clinical tables are person-level (one row per participant per visit, keyed on ID / src_subject_id). Imaging reading-project tables are knee-level (add SIDE, 1 = right, 2 = left). Computing a knee-level structural endpoint against a person-level symptom endpoint requires joining on ID and handling SIDE explicitly.

- **Variable-name caveat.** The **table stems** below are confirmed by the OAI methods literature. The **exact variable strings** vary by data release and reading-project version; those shown here are representative and must be verified against the OAI Data Users Guide and the NDA data-structure (variable) listings for your specific release before analysis.

## 1. Radiographic (plain-film) definitions

All plain-film definitions draw on the two knee X-ray reading families: the Boston University semiquantitative reading (kXR_SQ_BU) and the Duryea quantitative joint-space-width reading (kXR_QJSW). Both are knee-level tables requiring SIDE.

| **Definition** | **Threshold** | **Table stem** | **Representative variable(s)** | **Source** |
|----|----|----|----|----|
| Kellgren–Lawrence (KL) progression | Increase ≥1 KL grade (baseline→48 mo); many exclude 0→1 | kXR_SQ_BU | V##XRKL (per SIDE), compared across visits | Joo et al., *Knee Surg Sports Traumatol Arthrosc* 2022 |
| Incident radiographic OA | Cross from KL \<2 to KL ≥2 | kXR_SQ_BU | V##XRKL | Sharma et al., *Arthritis Rheumatol* 2017 |
| OARSI JSN progression | ≥1 grade increase (partial or whole), medial or lateral | kXR_SQ_BU | V##XRJSM (medial JSN), V##XRJSL (lateral JSN) | Hu et al., *Arthritis Care Res* 2022 |
| Quantitative JSW loss (FNIH) | Medial minimum JSW loss ≥0.7 mm (baseline→24/36/48 mo); non-progressor ≤0.5 mm both knees | kXR_QJSW | Medial minimum JSW and fixed-location JSW (e.g., V##MCMJSW , fixed-location fields at x=0.250) | Eckstein et al., *Arthritis Rheumatol* 2015 |
| Fixed-location / height-standardized / % JSW | Continuous or anchored thresholds | kXR_QJSW | Fixed-location JSW array; standardize against height in clinical file | Ratzlaff et al., *Osteoarthritis Cartilage* 2018; Paixao et al., *Osteoarthritis Cartilage* 2020 |
| Accelerated knee OA (AKOA) | KL \<2 → KL ≥3 within 48 mo | kXR_SQ_BU | V##XRKL trajectory over ≤48 mo | Driban et al., *Arthritis Rheumatol* 2019; Harkey et al., *BMC Musculoskelet Disord* 2020 |
| JSW trajectory groups | 3-group (8-yr) or 7-group (2-yr) latent trajectories | kXR_QJSW | Repeated medial JSW across all imaging visits, fed to group-based trajectory model | Collins et al., *Arthritis Care Res* 2021; Bartlett et al., *Arthritis Care Res* 2011 |

Note that KL grade is also carried, at baseline, within the clinical master file as a convenience variable (commonly V00XRKL), which is why McCabe et al. could attach KL to clinical predictors by joining AllClinical00 to kXR_SQ_BU00; for longitudinal readings use the reading-project table itself (McCabe et al., *PLoS One* 2024).

## 2. MRI-based definitions

MRI endpoints span three reading families plus composite frameworks. All are knee-level and, critically, cover only selected participants/visits (e.g., the FNIH Biomarkers subcohort of ~600 knees), so denominators differ sharply from the full 4,796.

| **Definition** | **Threshold** | **Table stem** | **Representative variable(s)** | **Source** |
|----|----|----|----|----|
| Quantitative cartilage thickness loss | Medial femorotibial (MFTC) thickness change worse than SDD −111 μm over 24 mo | kMRI_QCart_Eckstein | MFTC / central-MFTC thickness fields (e.g., V##MCMFTHC -type subregion thickness) | Eckstein et al., *Arthritis Rheumatol* 2015 |
| Ordered-value (OV) thinning | Rank of subregion thinning, location-independent | kMRI_QCart_Eckstein | 16 subregion thickness fields, ranked | Wirth et al., *Osteoarthritis Cartilage* 2017 |
| Widespread full-thickness cartilage loss | MOAKS full-thickness score ≥2 | kMRI_SQ_MOAKS_BICL | Cartilage two-digit area/depth fields per subregion | Dório et al., *Osteoarthritis Cartilage* 2020 |
| MOAKS feature worsening (BMLs, effusion-/Hoffa-synovitis, meniscus, osteophytes) | Any increase, incl. within-grade 0.5 worsening | kMRI_SQ_MOAKS_BICL | BML size/number, effusion-synovitis, Hoffa, meniscal morphology/extrusion, osteophyte fields | Collins et al., *Arthritis Rheumatol* 2016; Moradi et al., *Radiology* 2024 |
| WORMS / BLOKS scoring (legacy) | Feature-specific change | Legacy kMRI_SQ_WORMS / kMRI_SQ_BLOKS reading projects | Cartilage 0–6 (WORMS, 14 regions); BLOKS meniscal/BML fields | Felson et al. & Lynch et al., *Osteoarthritis Cartilage* 2010 |
| Compositional MRI (T2) | Highest tibiofemoral T2 quartile; MDC ~12–14% | Cartilage T2 reading project (UCSF/BU) | Regional/layer T2 relaxation fields | Kretzschmar et al., *Osteoarthritis Cartilage* 2019; Chalian et al., *Radiology* 2021 |
| Bone shape / area | 3D bone-shape vector change | iMorphics bone-morphometry reading project | Bone-shape vector, subchondral area fields | Eckstein, Kwoh & Link, *Ann Rheum Dis* 2014 |
| Composite MRI frameworks (cumulative damage / disease activity; OA-COM; FNIH multivariable) | Summed indices; C-statistic 0.740 for combined endpoint | kMRI_SQ_MOAKS_BICL (± kMRI_QCart_Eckstein ) | Derived sums of cartilage, BML, effusion-synovitis, meniscus fields | Driban et al., *Arthritis Care Res* 2022; Hunter et al., *Arthritis Care Res* 2022 |
| MRI OA definitions (Hunter/Delphi; Liew) | Feature-count definitions of OA presence | kMRI_SQ_MOAKS_BICL | Cartilage, osteophyte, BML, meniscus flags | Chang et al., *Arthritis Rheumatol* 2025 |

## 3. Clinical / symptomatic (WOMAC-based) definitions

All WOMAC and related patient-reported outcomes live inside the per-visit clinical master files (AllClinical00–AllClinical10). These are person-level but WOMAC is scored **per knee** (right/left), so the variable carries a side suffix.

| **Definition** | **Threshold** | **Table stem** | **Representative variable(s)** | **Source** |
|----|----|----|----|----|
| FNIH pain progression | WOMAC pain (0–100 normalized) increase ≥9, sustained ≥2 time points (24–60 mo) | AllClinical## | WOMAC pain per knee, e.g., V##WOMKPR / V##WOMKPL (0–20 raw; normalize to 0–100) | Eckstein et al., *Arthritis Rheumatol* 2015; Collins et al., *Arthritis Rheumatol* 2016 |
| Sustained pain worsening | ≥9-pt increase with ≥80% maintained | AllClinical## | WOMAC pain across serial visits | Collins et al., *Osteoarthritis Cartilage* 2023 |
| WOMAC function MCID worsening | WOMAC function (0–68) ≥6-unit increase over 2 yr | AllClinical## | WOMAC function/ADL per knee (e.g., V##WOMADLR ) | Ruhdorfer et al., *Arthritis Rheumatol* 2016 |
| Consecutive-visit progression | WOMAC pain (0–20) increase \>2 between consecutive visits | AllClinical## | V##WOMKP\* raw | Wink et al., *Arthritis Care Res* 2019 |
| Clinically important worsening | WOMAC total ≥20% increase (or ≥2 if baseline 0) | AllClinical## | WOMAC total per knee (e.g., V##WOMTSR ) | Driban et al., *Arthritis Rheumatol* 2026 |
| Inverse OARSI-OMERACT | Composite worsening in pain + function + patient global | AllClinical## | WOMAC pain, WOMAC function, patient global assessment fields | Driban et al., *J Rheumatol* 2021 |
| Pain / ICOAP trajectories & phenotypes | Latent trajectory or class membership | AllClinical## (ICOAP added at 48 mo, V06 +) | Serial WOMAC pain; ICOAP intermittent/constant fields | Collins et al., *Osteoarthritis Cartilage* 2014; Ye et al., *BMC Musculoskelet Disord* 2024 |

WOMAC subscales concatenate the visit prefix, instrument code, and side suffix (R/L) — e.g., baseline right-knee WOMAC pain is commonly V00WOMKPR. Confirm whether your release stores WOMAC as raw subscale sums (pain 0–20, stiffness 0–8, function 0–68) or normalized 0–100 before applying the 9-point FNIH threshold (Kreutzinger et al., *Sci Rep* 2025).

## 4. Functional / performance-based definitions

The 20-m walk, 400-m walk, and 5-times sit-to-stand were collected annually through 84 months **except** at the 60- and 84-month visits, and are stored within the clinical master files (sometimes exposed as a physical-exam/performance block).

| **Definition** | **Threshold** | **Table stem** | **Representative variable(s)** | **Source** |
|----|----|----|----|----|
| Gait speed trajectory (fast decline) | 5-group (4-yr) / 3-group (8-yr) latent trajectories | AllClinical## (performance block) | 20-m walk time/pace fields (e.g., V##400MTIM , 20-m pace), converted to m/s | White et al., *Arthritis Care Res* 2013; Liu et al., *Sci Rep* 2023 |
| Gait speed decline as endpoint | Decline ≥0.1 m/s over 2 yr; important difference ~0.068–0.115 m/s | AllClinical## | 20-m walk speed across visits | Driban et al., *J Rheumatol* 2021; Gilbert et al., *Arthritis Care Res* 2021 |
| Incident slow gait | Onset of gait \<1.0 m/s | AllClinical## | 20-m walk speed thresholded | Sharma et al., *Ann Rheum Dis* 2019 |
| Sit-to-stand functional limitation | 5× chair-stand \>12 s (often with gait \<1.22 m/s) | AllClinical## | 5× sit-to-stand time field | Master et al., *J Rheumatol* 2021; Hiyama, *Rheumatol Int* 2026 |
| Physical-function trajectory | Longitudinal course of performance measures | AllClinical## | Combined 20-m walk + chair-stand across visits | Øiestad et al., *Arthritis Care Res* 2016 |

## 5. Accelerometer / physical-activity definitions

The physical-activity ancillary substudy was added at the **48-month visit** (V06), using hip-worn uniaxial ActiGraph GT1M monitors worn for 7 days, and is delivered as its **own dataset** rather than folded into AllClinical. Self-reported activity (PASE) is separately available within the clinical files at multiple visits.

| **Definition** | **Threshold** | **Table stem** | **Representative variable(s)** | **Source** |
|----|----|----|----|----|
| MVPA guideline attainment | ≥150 min/week moderate-vigorous activity | Accelerometer ancillary dataset ( V06 ) | Daily/weekly MVPA minutes, activity counts | Song et al., *Arthritis Care Res* 2010 |
| Sedentary behavior → function loss | Per-10% sedentary increment | Accelerometer ancillary dataset | Sedentary time, activity-count intensity bins | Semanik et al., *Am J Public Health* 2015 |
| Activity-pattern / threshold predictors | Low MVPA counts, isotemporal substitution | Accelerometer ancillary dataset | Intensity-classified minutes, wear-time fields | Fenton et al., *Osteoarthritis Cartilage* 2018; Tore et al., *Osteoarthritis Cartilage* 2025 |
| Activity-count decline with symptom worsening | Symptom group = WOMAC increase \>10 | Accelerometer ancillary + AllClinical## (WOMAC) | Total/time-of-day activity counts joined to WOMAC change | Kushioka et al., *Sensors* 2026 |
| Self-reported activity (PASE) | Continuous score | AllClinical## | V##PASE composite | Kreutzinger et al., *Sci Rep* 2025 |

## 6. Biomechanical definitions (ancillary)

The OAI had no cohort-wide 3D gait laboratory. The one within-OAI biomechanical progression variable is **varus thrust** by visual gait observation at the 12-month visit; other biomechanical predictors (knee adduction moment, knee flexion moment) come from OAI-adjacent gait-lab cohorts, not the public OAI tables.

| **Definition** | **Threshold** | **Table stem** | **Representative variable(s)** | **Source** |
|----|----|----|----|----|
| Varus thrust | Visually observed thrust during gait (12-mo visit, V01 ) | AllClinical01 (gait-observation block) | Varus-thrust observation field | Sharma et al., *Arthritis Rheumatol* 2017 |
| Knee adduction / flexion moment | Gait-lab kinetics | Not in public OAI tables (external gait-lab cohorts) | — | Hatfield et al., *Arthritis Care Res* 2015; D'Souza et al., *Osteoarthritis Cartilage* 2022 |

## 7. Hard endpoints: TKR and composite trial outcomes

Total knee replacement is captured as a cumulative outcome event in the dedicated outcomes file (Outcomes99), which spans follow-up rather than a single visit. Composite endpoints combine Outcomes99 (TKR), kXR_QJSW / kXR_SQ_BU (structure), and AllClinical## (WOMAC).

| **Definition** | **Threshold** | **Table stem(s)** | **Representative variable(s)** | **Source** |
|----|----|----|----|----|
| TKR alone | Total knee replacement event | Outcomes99 | Knee-replacement outcome + date fields (per knee) | Collins et al., *Arthritis Care Res* 2016 |
| FNIH composite | JSW loss ≥0.7 mm + WOMAC pain ≥9 | kXR_QJSW + AllClinical## | Medial min JSW change + WOMAC pain change | Collins et al., *Osteoarthritis Cartilage* 2026 |
| End-stage KOA (esKOA) | KL 4 + moderate-intense pain, or severe pain + limited mobility/instability | kXR_SQ_BU + AllClinical## | V##XRKL + WOMAC pain + mobility/instability items | Driban et al., *Semin Arthritis Rheum* 2023 |
| Composite KOA symptom outcome (CKOASO) | Composite symptom worsening | AllClinical## (± Outcomes99 ) | WOMAC-derived composite | Collins et al., *Osteoarthritis Cartilage* 2026 |
| Time-to-event composite | First TKR or crossing WOMAC severity thresholds | Outcomes99 + AllClinical## | TKR event + WOMAC threshold crossing | Kim et al., *Arthritis Care Res* 2022 |

## Practical assembly notes

- **Change scores, not single visits.** Every definition above is longitudinal; pull the source variable at each relevant visit and compute the delta before applying thresholds.

- **Join discipline.** Merge knee-level imaging (kXR\_\*, kMRI\_\*) to person-level clinical (AllClinical##) on ID **and** SIDE; the FNIH composite specifically requires aligning the analysis knee across the structural and symptomatic tables.

- **Denominator awareness.** MRI reading projects and the accelerometer ancillary cover subcohorts, not the full 4,796; report the applicable denominator with any MRI or accelerometer endpoint.

- **Release verification.** Table stems here are literature-confirmed; the exact variable names, normalization (raw vs. 0–100 WOMAC), and visit availability must be confirmed against the OAI Data Users Guide and the NDA data-structure listings for your download version.

*Citations in this document are given in MLA-style prose. Bracketed reference numbers used in the on-screen chat answers are not carried into downloadable artifacts; consult the chat view for the full numbered reference list.*
