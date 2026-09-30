The Osteoarthritis Initiative (OAI) public dataset is documented at the variable level in the official OAI Data Users Guides distributed with each data release; the peer-reviewed literature confirms the high-level architecture and specific table names but does not reproduce the full data dictionary. What follows synthesizes the dataset's structure as described in OAI methods papers that name specific tables and reading projects, supplemented by the organizing conventions from the official OAI documentation (flagged as such where the literature does not itself carry them). The authoritative per-variable reference remains the Data Users Guide and contents listings that accompany each release on the NIMH Data Archive (NDA).

## Where the Data Live and How a "Release" Is Structured

OAI data are publicly available and were originally distributed through the UCSF coordinating-center site (oai.ucsf.edu / oai.epi-ucsf.org) and are now hosted on the NIMH Data Archive (nda.nih.gov/oai; data-archive.nimh.nih.gov/oai) (Deng et al., *Sci Rep* 2024; Eckstein, Kwoh, and Link, *Ann Rheum Dis* 2014; Lo et al., *Arthritis Rheumatol* 2024). Data are versioned — for example, published analyses cite "OAI clinical dataset version 0.2.3" — so any table summary is release-specific (Vincent et al., *Sci Rep* 2023). Files were historically provided as SAS and delimited text; the NDA additionally exposes them as defined data structures with study DOIs (e.g., the baseline clinical/demographic collection carries doi:10.15154/1519056) (Nelson et al., *PLoS One* 2021).

The overall content divides into five families: (1) clinical/questionnaire datasets, (2) central image-assessment ("reading project") datasets, (3) raw image inventory/availability datasets, (4) the biospecimen repository inventory, and (5) accelerometer/physical-activity ancillary data (Deng et al., *Sci Rep* 2024; Eckstein, Kwoh, and Link, *Ann Rheum Dis* 2014; Emery et al., *Nat Rev Rheumatol* 2019). Underlying all of them is the cohort structure — 4,796 participants (progression n≈1,390; incidence n≈3,284; control n≈122) enrolled 2004–2006 at four clinical sites, which defines the participant universe every table is keyed to (Nelson et al., *PLoS One* 2021).

## Visit/Time-Point Coding — the Single Most Important Convention

Every longitudinal table encodes the visit in both the table-name suffix and the variable prefix, and the mapping is not simply months ÷ 12 — this is the most common source of merge errors. Clinic (imaging) visits occurred at baseline and 12, 24, 36, and 48 months, then biennially at 72 and 96 months; interim telephone contacts fall on the intervening odd codes (Schiratti et al., *Arthritis Res Ther* 2021; Lo et al., *Arthritis Rheumatol* 2022; Collins, Neogi, and Losina, *Arthritis Care Res* 2021). The conventional mapping used across OAI documentation and papers is:

| **Code (suffix/prefix)** | **Time point**        | **Contact type** |
|--------------------------|-----------------------|------------------|
| 00 / V00                 | Baseline (enrollment) | Clinic + imaging |
| 01 / V01                 | 12 months             | Clinic + imaging |
| 02 / V02                 | 18 months             | Telephone        |
| 03 / V03                 | 24 months             | Clinic + imaging |
| 04 / V04                 | 30 months             | Telephone        |
| 05 / V05                 | 36 months             | Clinic + imaging |
| 06 / V06                 | 48 months             | Clinic + imaging |
| 07 / V07                 | 60 months             | Telephone        |
| 08 / V08                 | 72 months             | Clinic + imaging |
| 09 / V09                 | 84 months             | Telephone        |
| 10 / V10                 | 96 months             | Clinic + imaging |

(Collins, Neogi, and Losina, *Arthritis Care Res* 2021; Vincent et al., *Sci Rep* 2023; Schiratti et al., *Arthritis Res Ther* 2021; Lo et al., *Arthritis Rheumatol* 2022.)

Thus AllClinical00 is baseline and kxr_sq_bu06 is the 48-month Boston University X-ray reading. Note that radiographs were centrally read annually through 48 months plus years 6 and 8, whereas the MRI reading projects were generally limited to baseline and selected follow-ups (Schiratti et al., *Arthritis Res Ther* 2021; Collins, Neogi, and Losina, *Arthritis Care Res* 2021). Confirm the exact code-to-month mapping against the Data Users Guide for your release, since telephone-contact codes vary.

## Keys and Record Grain

Tables are keyed on the participant identifier (ID in the classic files; src_subject_id on NDA). Person-level tables carry one row per participant per visit; knee-/joint-level tables (most imaging readings) add a laterality field (SIDE, 1 = right, 2 = left) and hold one row per knee per visit (McCabe et al., *PLoS One* 2024; Chang et al., *Arthritis Rheumatol* 2025). Merging clinical and imaging data therefore requires joining on ID (and SIDE where applicable), as illustrated by McCabe et al., who merged AllClinical00 to kxr_sq_bu00 on subject ID to attach baseline Kellgren–Lawrence grades to clinical predictors (McCabe et al., *PLoS One* 2024).

## Clinical / Questionnaire Datasets

The clinical family is dominated by the AllClinical00–AllClinical10 tables, each a wide per-visit master file combining subject characteristics, risk factors, medical history, anthropometry, symptoms, and the patient-reported instruments (McCabe et al., *PLoS One* 2024). Alongside these sit stand-alone per-visit or cumulative tables:

| **Dataset (typical stem)** | **Contents** |
|----|----|
| Enrollees | One row/participant: cohort assignment (progression/incidence/control), eligibility, baseline demographics |
| AllClinicalXX | Master per-visit clinical file: demographics, medical history, symptoms, WOMAC, KOOS, exam, anthropometry |
| Outcomes99 | Cumulative outcome events across follow-up: death, hospitalization, knee replacement/arthroplasty |
| MedicationsXX / Medical history forms | Prescription and non-prescription medication inventories; comorbidity forms |
| Nutrition (Block Brief 2000 FFQ) | Food-frequency questionnaire, baseline (and repeat) |
| PhysExamXX | Physical examination, performance measures (20-m and 400-m walk, 5× sit-to-stand, isometric knee strength, grip) |
| Biospecimens | Inventory of serum, plasma, urine, DNA aliquots |

(Nelson et al., *PLoS One* 2021; Øiestad et al., *Arthritis Care Res* 2016; Kim et al., *Arthritis Care Res* 2022; Deng et al., *Sci Rep* 2024; Eckstein, Kwoh, and Link, *Ann Rheum Dis* 2014; Emery et al., *Nat Rev Rheumatol* 2019; McCabe et al., *PLoS One* 2024.)

The patient-reported instruments captured within these files include the WOMAC (pain/stiffness/function, right and left knee separately), KOOS, ICOAP (intermittent and constant pain, added at 48 months), SF-12, PASE (physical activity), and CES-D (depression) (Emery et al., *Nat Rev Rheumatol* 2019; Löffler et al., *Arthritis Res Ther* 2025; Clearfield and Segal, *J Investig Med* 2023; Kreutzinger et al., *Sci Rep* 2025). Performance tests (20-m walk, 5× sit-to-stand) were collected annually through 84 months except at the 60- and 84-month visits (Øiestad et al., *Arthritis Care Res* 2016). Variable names concatenate the visit prefix, an instrument code, and often a laterality suffix — e.g., baseline WOMAC pain for the right knee is V00WOMKPR, and KL grade in the X-ray reading table is V00XRKL (McCabe et al., *PLoS One* 2024; Kreutzinger et al., *Sci Rep* 2025).

## Central Image-Assessment ("Reading Project") Datasets

These are the tables most relevant to standard progression definitions, and they follow a consistent naming grammar: joint + modality + method + reading site/investigator + visit. Each was produced by a specific central reading group and is tracked internally by a numbered reading project ID (e.g., Projects 22, 46, 47, 48, and 65 appear in published analyses) (Deng et al., *Sci Rep* 2024; Chang et al., *Arthritis Rheumatol* 2025).

| **Table stem** | **Modality / method** | **Reading group** | **Key variables** |
|----|----|----|----|
| kXR_SQ_BU (kxr_sq_buXX) | Knee X-ray, semiquantitative | Boston University | KL grade, OARSI JSN, osteophytes, sclerosis (per compartment) |
| kXR_QJSW (Duryea) | Knee X-ray, quantitative joint space width | Duryea (BWH) | Fixed-location JSW, medial minimum JSW |
| kMRI_SQ_MOAKS_BICL | Knee MRI, semiquantitative MOAKS | Boston Imaging Core Lab (Guermazi/Roemer) | Cartilage (2-digit), BMLs, meniscus, effusion-/Hoffa-synovitis, osteophytes |
| kMRI_QCart_Eckstein | Knee MRI, quantitative cartilage morphometry | Chondrometrics (Eckstein/Wirth) | Cartilage thickness/volume by subregion (e.g., cMFTC) |
| MRI T2 (compositional) | Knee MRI, T2 relaxometry | UCSF/BU cores | Cartilage T2 by region/layer |
| Bone shape/area | Knee MRI, 3D bone morphometry | iMorphics | Bone shape vectors, subchondral area |
| hXR (hand) | Hand X-ray, semiquantitative | Central hand reading | KL, OARSI JSN/osteophyte per joint |

(Wirth et al., *Arthritis Care Res* 2023; Deng et al., *Sci Rep* 2024; Eckstein, Kwoh, and Link, *Ann Rheum Dis* 2014; Schiratti et al., *Arthritis Res Ther* 2021; McCabe et al., *PLoS One* 2024; Wirth et al., *Sci Rep* 2016; Eaton et al., *Arthritis Rheumatol* 2022.)

Two practical points: first, MRI reading projects usually cover only the knee (right knee, or left when right is unavailable) and only selected participants/visits (e.g., the FNIH Biomarkers subcohort of 600 knees, or Projects 22/46/47/48), so denominators differ sharply from the full 4,796 (Chang et al., *Arthritis Rheumatol* 2025; Wirth et al., *Arthritis Care Res* 2023). Second, because multiple projects read overlapping tissues with different systems (WORMS vs. BLOKS vs. MOAKS over time), users must select the project matching their intended definition (Wirth et al., *Arthritis Care Res* 2023; Eckstein, Kwoh, and Link, *Ann Rheum Dis* 2014).

## Raw Image, Biospecimen, and Accelerometer Datasets

Separate inventory tables index the actual DICOM image files (X-ray and 3T MRI acquisitions: sagittal 3D DESS, coronal and sagittal 2D IW-TSE ± fat suppression), linking image barcodes to participant/visit/series for download (Wirth et al., *Arthritis Care Res* 2023; Schiratti et al., *Arthritis Res Ther* 2021). The biospecimen repository is catalogued in its own inventory of serum, plasma, urine, and DNA aliquots by visit (Deng et al., *Sci Rep* 2024; Eckstein, Kwoh, and Link, *Ann Rheum Dis* 2014).

The accelerometer / physical-activity ancillary data form a distinct dataset: hip-worn uniaxial ActiGraph GT1M monitoring introduced at the 48-month visit for a large subset, delivered as its own table(s) of activity counts and derived intensity metrics rather than folded into AllClinical (Emery et al., *Nat Rev Rheumatol* 2019).

## Summary and Caveats

The public OAI is best understood as a relational collection — one enrollment table plus per-visit clinical master files, a set of separately produced central image-reading tables named by joint/modality/method/site/visit, raw-image and biospecimen inventories, and an accelerometer ancillary — all joined on participant ID (and SIDE for knee-level data), with the visit encoded redundantly in table suffix and variable prefix (Deng et al., *Sci Rep* 2024; Vincent et al., *Sci Rep* 2023; McCabe et al., *PLoS One* 2024). The two recurring pitfalls are the non-linear V-code-to-month mapping and the mismatched denominators across reading projects. Because the medical-literature record confirms the architecture and specific table names but not the exhaustive variable dictionary, the definitive per-table and per-variable documentation for a specific release should be taken from the OAI Data Users Guide and NDA data-structure listings that accompany that download.
