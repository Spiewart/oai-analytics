## Exploratory Agreement/Validation Analysis Plan

### OAI Self-Report (PASE, 96-month Walking Survey) vs. ActiGraph Accelerometer

## 1. Objective and framing

The primary objective is to quantify how well OAI self-reported activity measures — the Physical Activity Scale for the Elderly (PASE, collected at annual visits) and the 96-month Historical Physical Activity Survey walking-for-exercise item — track device-measured activity from the ActiGraph GT1M accelerometer substudy nested at the 48-month visit.

Because the self-report and device measures were largely **not** collected concurrently, the analysis is framed primarily as **convergent/construct validity** (rank-order concordance and systematic bias) rather than strict criterion validity, with a single temporally-matched comparison reserved as the closest approximation to concurrent criterion validity. Temporal mismatch attenuates correlations beyond the already weak-to-moderate agreement (ρ ≈ 0.14–0.58) typical even of concurrent PA-questionnaire-vs-accelerometer studies (Skender et al., BMC Public Health 2016).

**Three aims structure the plan:**

- **Aim 1 (primary):** Concurrent validity of the 48-month PASE against the 48-month accelerometer (the only truly overlapping pair).

- **Aim 2:** Construct validity / rank-order stability of PASE at other visits and of the 96-month walking-for-exercise item against the 48-month accelerometer.

- **Aim 3:** Guideline-attainment and cutpoint agreement (categorical), including whether a PASE threshold can classify accelerometer-defined (in)activity.

## 2. Design and analytic samples

Cross-sectional method-comparison study nested in the OAI, with the accelerometer substudy defining the analytic backbone. The accelerometer substudy enrolled participants attending the 48-month visit (August 2008–July 2010); of 2,127 consenting (78.4% of eligibles), ~1,908 had valid accelerometer estimates (Sun et al., Arthritis Care Res 2014). Applied analyses have retained 1,574–1,927 (Vina et al., Arthritis Care Res 2024).

Define three nested samples explicitly and report in a flow diagram:

| **Sample** | **Inclusion** | **Anchor comparison** |
|----|----|----|
| A (primary) | Valid 48-mo accelerometer + 48-mo PASE | Concurrent criterion validity |
| B | Valid 48-mo accelerometer + PASE at other visits (0/12/24/36 mo) | Rank-order stability over time |
| C | Valid 48-mo accelerometer + 96-mo walking-for-exercise item | Prospective device vs. retrospective recall |

Sample C is the weakest temporally (device at 48 months vs. lifetime recall reported at 96 months); interpret as a test of whether a retrospective habitual-walking report ranks people consistently with an earlier objective snapshot, not as validation in the usual sense (Lo et al., Arthritis Rheumatol 2022).

## 3. Variables and derivation

### Accelerometer (criterion measure)

Adopt established OAI processing conventions for comparability with the substudy literature (Song et al., Arthritis Care Res 2010; 2013):

- **Non-wear:** ≥90 consecutive minutes of zero counts (allowing up to 2 interrupted minutes \<100 counts) — the threshold validated for knee-OA populations, whose long sedentary bouts are misclassified by the general-population 60-minute rule.

- **Valid day:** ≥10 wear-hours. **Valid week:** 4–7 valid days; weekly totals summed for 7-day wearers, estimated as 7 × daily average for 4–6 valid days.

**Candidate device endpoints:**

- **MVPA (total, unbouted):** minutes/day with counts ≥2,020 cpm (Troiano/NCI cutpoint).

- **MVPA (bouted):** minutes in ≥10-minute bouts (≤2-minute drop-below allowance) — the legacy guideline metric.

- **Steps/day** and **average daily activity counts** as continuous volume measures.

- **Guideline attainment (3 levels):** meeting (≥150 bouted MV min/wk), insufficiently active (≥1 bout but \<150 min/wk), inactive (0 bouts).

Pre-specify and report the cutpoint and epoch (1-minute), with an alternative cutpoint as a sensitivity analysis (cutpoint choice swings guideline-attainment prevalence dramatically; Migueles et al., Sports Med 2017).

### PASE (index self-report)

Score the 12-item PASE across leisure, household, and occupational domains using the standard weighted algorithm; derive the **total score** and the isolated **walking subscore** (the closest self-report analogue to ambulatory output). Analyze PASE continuously and in tertiles (consistent with prior OAI usage, e.g., Bricca et al., Arthritis Care Res 2019).

### 96-month walking-for-exercise

Derive the hierarchical walking variable: the yes/no screen ("walked for exercise ≥10 times at age ≥50"), the ≥20-minute duration filter, and the ordinal years / months-per-year / times-per-month responses, from which an estimated lifetime walking-bout total is computed using category medians (Lo et al., Arthritis Rheumatol 2022).

## 4. Temporal-alignment strategy

Temporal mismatch is the central threat to validity and should be handled by design:

- Use the **48-month PASE** as the primary comparator (only self-report contemporaneous with device wear).

- Report the exact interval (in days) between each participant's PASE administration and accelerometer wear window; include it as a covariate/stratifier in sensitivity analyses.

- For Sample C, explicitly report the ~48-month gap and frame findings as rank-order stability.

## 5. Statistical analysis plan

PA data are right-skewed and often zero-inflated: use medians/IQRs and Wilcoxon signed-rank tests, not means/t-tests (Akram et al., IJBNPA 2023).

**Layer 1 — Relative validity (rank-order).** Spearman ρ between each self-report and device variable, with 95% CIs (primary continuous metric given non-normality). Interpret against benchmarks (≤0.30 poor, 0.31–0.40 fair, 0.41–0.60 moderate, 0.61–0.80 substantial). Report deattenuated correlations where a reliability estimate is available. Realistic prior: PASE-vs-accelerometer counts r ≈ 0.36–0.64 in general older adults, as low as 0.06–0.45 in OA/arthroplasty samples.

**Layer 2 — Absolute agreement and bias.** Bland-Altman (difference vs. mean) with mean bias and 95% limits of agreement, after log-transformation given expected heteroscedasticity. Test **fixed bias** (mean-difference CI excludes zero) and **proportional bias** (regression of difference on mean; report β, R², p). Strong prior: over-reporting of MVPA, under-capture of light walking. Pre-specify a clinically acceptable difference so LOA are interpreted against a threshold. Consider the Taffé method as a supplement where method precisions differ.

**Layer 3 — Categorical agreement.** Cross-classify guideline attainment (self-report vs. accelerometer); compute Cohen's κ (dichotomous ≥150 min/wk) and weighted κ (3-level ordinal). Report sensitivity, specificity, PPV, NPV of the self-report classification against the accelerometer reference. Expect fair agreement at best (κ ≈ 0.26–0.34).

**Layer 4 — Cutpoint determination.** ROC to identify the PASE (total and walking-subscore) threshold best discriminating accelerometer-defined inactive vs. active participants. Report AUC with 95% CI; select cutpoint by Youden index, with Index of Union / Euclidean-distance methods as sensitivity checks and bootstrapped CIs. Prior work discriminating inactivity via PASE achieved AUC ≈ 0.72.

**Layer 5 — Predictors of reporting bias.** Regress the individual bias score (self-report minus device, log/standardized scale) on accelerometer activity level, age, sex, BMI, WOMAC pain, and KL grade to characterize *who* over- or under-reports. For modeling skewed activity outcomes themselves, prefer gamma or negative-binomial GLMs, or two-part (hurdle) models for zero-inflation.

## 6. Power and precision

Agreement/validation studies estimate a parameter, so the relevant metric is **CI width at the available sample sizes**, not classical power. With PASE administered at the 48-month visit, essentially the entire valid-accelerometer sample has a concurrent PASE, so **Sample A ≈ 1,900**; **Sample C ≈ 1,000–1,500** after 48-to-96-month attrition.

### Expected precision — Spearman (Bonett/Fisher-z; half-width = 1.96 × 1.03/√(n−3), back-transformed)

| **Analytic sample**             | **n**  | **True ρ** | **Approx. 95% CI** |
|---------------------------------|--------|------------|--------------------|
| A (concurrent PASE)             | ~1,900 | 0.30       | 0.26–0.34          |
| A                               | ~1,900 | 0.45       | 0.41–0.49          |
| C (96-mo walking)               | ~1,000 | 0.30       | 0.24–0.36          |
| Subgroup (e.g., sex-stratified) | ~400   | 0.30       | 0.21–0.39          |
| Small subgroup                  | ~150   | 0.30       | 0.14–0.44          |

In the full samples, even a "poor" ρ ≈ 0.30 is estimated to ±0.04 — clearly distinguishable from zero and from "moderate." Precision degrades only in small stratified subgroups (report CIs; interpret cautiously, e.g., documented r = 0.45 in men vs. 0.06 in women).

### Expected precision — Cohen's kappa (Shoukri–Donner CI-width)

A κ ≈ 0.30 with balanced marginals (p ≈ 0.5) at n ≈ 1,900 gives a 95% CI half-width ~0.043 (κ ≈ 0.26–0.34); at n ≈ 1,574, ~0.047. Because guideline-attainment marginals are skewed (self-report ≈50% vs. accelerometer ≈15% meeting), the realistic half-width is closer to ±0.05–0.06. Use the kappaSize R package (Rotondi & Donner) to finalize once observed marginals are known; use exact/bootstrap CIs for any small subgroup.

### Recommendations

No sample inflation needed for primary aims (±0.04–0.06 precision on ρ and κ). Reserve formal precision calculations for the ROC cutpoint CI and subgroups with n \< ~400. Report deattenuated correlations, since single-occasion accelerometer wear caps observable ρ regardless of sample size.

## 7. Sensitivity analyses

- 60-minute non-wear threshold (NHANES-harmonized) alongside the primary 90-minute rule

- Alternative MVPA cutpoint

- Restriction to ≥5 or 7 valid days

- Stratification by the PASE-accelerometer time gap

- Sex-stratified agreement

## 8. Key pitfalls

1.  **Temporal mismatch** attenuates every correlation — do not read as poor questionnaire performance per se.

2.  **Construct non-equivalence:** the hip-worn uniaxial GT1M misses cycling, swimming, upper-body/load-bearing activity that PASE and the walking survey capture, so some disagreement is "correct."

3.  **Processing-decision sensitivity:** non-wear threshold, valid-day rule, epoch, and intensity cutpoint each materially move device estimates — pre-register and vary all.

4.  **Correlation-only reporting is inadequate:** ρ can be moderate while Bland-Altman reveals large proportional bias — always pair a correlation with an agreement plot.

5.  **Skew and zero-inflation** invalidate means/t-tests/linear models — use nonparametric or GLM/two-part approaches.

6.  **PASE measurement error and poor responsiveness** cap achievable agreement.

7.  **96-month recall bias:** the walking item was ascertained after outcomes — a further limit on Sample C.

## 9. Suggested deliverables

- Participant-flow/CONSORT diagram across Samples A–C

- Descriptive table of device and self-report distributions (medians/IQR)

- Correlation matrix (Spearman, with deattenuated values)

- Bland-Altman plots with fixed/proportional bias statistics for each key pair

- κ / sensitivity-specificity table for guideline attainment

- ROC output with optimal PASE cutpoint and its CI

- Full reporting of device processing (device, epoch, non-wear algorithm, valid-day/week criteria, cutpoints) to current accelerometry standards

## 10. Per-Genotype Progression Analysis (genetic arm)

### 10.1 Central framing

Treat **susceptibility genetics and progression genetics as distinct questions.** Loci discovered by case-control GWAS of OA *presence* largely do not transfer to progression endpoints: the IMI-APPROACH cohort found none of 30 validated OA-presence SNPs, nor a 30-SNP polygenic risk score (PRS), associated with 2-year minimum-JSW or KOOS-pain progression (Bentvelzen et al., PLoS One 2024). Conversely, a GO-consortium susceptibility PRS predicted progression selectively toward *end-stage* disease in the Rotterdam Study (higher ORs for incident-severe and progressive-severe OA than for early incident OA; Sedaghati-Khayat et al., Arthritis Rheumatol 2022). **A priori hypothesis:** susceptibility variants may drive progression to end-stage (TKR/KL4) but not short-interval structural change.

Three pre-specified arms:

1.  **Candidate-locus arm** — curated established loci tested against each progression endpoint (primary, adequately powered).

2.  **PRS arm** — a susceptibility PRS and, exploratorily, a progression-weighted score (small number of pre-specified scores).

3.  **Hypothesis-free GWAS arm** — underpowered in OAI alone; discovery-only, labeled as such.

### 10.2 Data access and structure

OAI genotype data are **controlled-access via dbGaP**, requested separately from the phenotype data (OAI/NDA portal), each under its own data-use agreement. Participants were genotyped on the **Illumina HumanOmni2.5M-Quad BeadChip (~2.44M SNPs)** at TGen; genotype data exist for **n = 4,129** (3,366 White, 763 Black/African-American). Raw files are hg18 (Build 36) and require liftover to hg19/hg38 before imputation. **There is no OAI-distributed imputed dataset** — investigators impute themselves; prior OAI work used 1000 Genomes (Minimac; BEAGLE5). For a new analysis, re-impute to **TOPMed** (well-imputes r² \> 0.8 to MAF ~0.35% on the Omni 2.5M array; improves the African-ancestry subset) (Muthuirulan et al., Nat Commun 2021; Yau et al., Arthritis Rheumatol 2017; Hanks et al., Am J Hum Genet 2022).

### 10.3 Analytic sample and ancestry handling

- Primary analysis in the **European-ancestry subset (n = 3,366)** with **≥10 principal components** (computed after LD-pruning, MAF \> 5% filtering).

- Analyze the **African-ancestry subset (n = 763) separately** as exploratory replication — supports only large effects, hypothesis-generating.

- Sample QC (Yau et al. pipeline): call rate \< 95%, sex discordance, cryptic relatedness (≤ second-degree), chromosomal-abnormality exclusions. SNP filters: MAF ≥ 1%, imputation Rsq ≥ 0.3, HWE P \> 1×10⁻⁴ in controls.

- **Winner's-curse caveat:** OAI was a discovery cohort for the Yau radiographic-OA GWAS and the Bonakdari progression ML models, so candidate SNPs drawn from those analyses (GDF5, FTO, TP63, SUPT3H, DUS4L) are subject to inflated effect estimates on re-testing. Disclose and, ideally, validate externally (e.g., Tasmanian, MOST cohorts).

### 10.4 Genotype exposure definition

Curate the candidate panel by evidence tier; pre-register **additive coding (allele dosage 0/1/2) as primary**, with dominant/recessive/genotypic codings as secondary under a model-selection framework (Bi et al., Methods 2018; pgainsim, Scherer et al., Bioinformatics 2021) — ~25% of complex-trait loci deviate from additivity (Guindo-Martínez et al., Nat Commun 2021).

| **Locus (lead SNP)** | **Susceptibility effect** | **Progression evidence** |
|----|----|----|
| GDF5 (rs143383) | Knee OA OR 1.18 | β=0.05 KL severity; ML progression driver |
| SMAD3 (rs3825977/rs12901071) | OA OR 1.08 | β=0.19 total JSN; OR 1.47 for ≥5 joints |
| TGFA (rs3771501) | OA OR 0.94 | β=−0.07 mJSW endophenotype |
| FTO (rs8044769) | Near-GWS arcOGEN | 37% error-impact in OAI ML progression model |
| TP63 (rs12107036) | Near-GWS arcOGEN | OR 1.67 rapid progression with mtDNA haplogroup Uk |
| SUPT3H (rs10948172) | Near-GWS; mJSW | Optimum OAI ML progression model component |
| DUS4L/COG5 (7q22) | GWS knee OA | ML progression driver |
| PLCL2 / CDYL2 | Not GWS for presence | GWS for minJSW decrease (progression-specific, unreplicated) |
| Arthrotest panel (rs2073508 +7) | N/A | AUC 0.78–0.82 for KL4/TKR at 8 yr |

**PRS arm:** susceptibility PRS from GO-consortium/Hatzikotoulas weights; exploratory IMI-APPROACH 19-SNP progression PRS and Arthrotest panel (both unreplicated). Consider **mtDNA haplogroups (H, J, T, U, K)** and the TP63 × haplogroup-Uk mitonuclear interaction (among the strongest OAI progression signals; Durán-Sotuela et al., Osteoarthritis Cartilage 2024).

### 10.5 Progression outcomes (harmonized to prior review definitions)

- **Symptomatic:** WOMAC pain/function trajectory; dichotomous OARSI-OMERACT progressor; KOOS for APPROACH comparability.

- **Radiographic:** medial JSN / minimum-JSW loss (continuous, mm/yr); ordinal KL-grade transition; binary progression to KL4/TKR (the end-stage phenotype).

- **MRI:** quantitative cartilage thickness/volume loss, cartilage T2; semiquantitative MOAKS/WORMS worsening.

- **Functional:** accelerometer- and biomechanics-based measures (Sections 1–9), treated as continuous progression outcomes.

Pre-register each endpoint as continuous slope, ordinal transition, or time-to-event, because the model depends on it.

## 11. Model specifications by endpoint

**Common confounder block (all models):** age at baseline (age0), sex, baseline BMI (bmi0), ≥10 ancestry PCs (PC1–PC10). European- and African-ancestry subsets modeled **separately**. Genotype term (geno_add) is imputed allele dosage 0/1/2 (primary); dominant/recessive/genotypic as secondary codings. For PRS analyses, replace geno_add with the standardized PRS (mean 0, SD 1) and report effect per SD.

### 11.1 Continuous endpoints — minimum JSW, medial JSN, cartilage thickness/volume, cartilage T2, WOMAC/KOOS

Linear mixed-effects model, random intercept + random slope, knee nested within participant. Effect of interest = **time:geno_add** (per-allele difference in annual progression rate).

\# lme4\
lmer(outcome ~ time \* geno_add + age0 + sex + bmi0 +\
PC1 + PC2 + ... + PC10 +\
(time \| participant/knee),\
data = df, REML = TRUE)

- **Coding:** time in years from baseline (continuous); geno_add = 0/1/2 dosage.

- **Primary coefficient:** time:geno_add (mm/yr, or unit/yr, per allele), with 95% CI.

- **Joint 2-df test:** likelihood-ratio test of geno_add + time:geno_add together (Benke et al., Genet Epidemiol 2013) — recovers power when a variant shifts both baseline level and slope.

- **Floor/ceiling in WOMAC/KOOS:** consider a censored (tobit) mixed model if a large fraction sit at the score floor.

- **Baseline-value adjustment:** because the outcome is modeled longitudinally, do *not* additionally adjust for the baseline outcome (collider/regression-to-mean risk); if a single-change-score model is used instead, include baseline as a covariate.

### 11.2 Ordinal endpoint — KL-grade transition

Cumulative-link mixed model (proportional-odds); test the proportional-odds assumption and fall back to a partial-proportional-odds or multinomial transition model if violated.

\# ordinal package\
clmm(kl_grade_ordered ~ time \* geno_add + age0 + sex + bmi0 +\
PC1 + ... + PC10 + (1 \| participant/knee),\
data = df, link = "logit")

- **Primary coefficient:** time:geno_add — per-allele OR for advancing one KL grade per unit time.

### 11.3 Binary progressor — dichotomous OARSI-OMERACT responder/progressor

GEE logistic with exchangeable working correlation, clustered on participant (accounts for two knees), or a mixed logistic model.

\# geepack\
geeglm(progressor ~ geno_add + age0 + sex + bmi0 +\
PC1 + ... + PC10,\
id = participant, family = binomial, corstr = "exchangeable",\
data = df)

- **Primary coefficient:** geno_add — per-allele OR of being classified a progressor over the defined interval.

### 11.4 Time-to-event — progression to KL4 or TKR

Cox proportional hazards with shared frailty (or robust cluster-sandwich) for bilateral knees. **This is the model in which the susceptibility PRS is hypothesized to perform best** (Rotterdam end-stage findings).

\# survival package\
coxph(Surv(time_to_event, event) ~ geno_add + age0 + sex + bmi0 +\
PC1 + ... + PC10 + frailty(participant),\
data = df)\
\# PRS variant:\
coxph(Surv(time_to_event, event) ~ prs_z + age0 + sex + bmi0 +\
PC1 + ... + PC10 + frailty(participant), data = df)

- **Primary estimate:** per-allele (or per-SD-PRS) **HR** with 95% CI.

- **Check** proportional-hazards assumption (Schoenfeld residuals); if violated, time-stratified or time-varying-coefficient Cox.

- **Left-truncation/survivorship:** OAI enrolls prevalent OA; fast progressors reaching TKR early are under-captured — acknowledge as a bias on progression-rate estimates.

### 11.5 Mitonuclear interaction — rapid-progressor phenotype

Logistic (binary rapid-progressor) or Cox (time-to-rapid-progression) including the **TP63 × haplogroup-Uk** product term.

glm(rapid_progressor ~ tp63_geno \* haplo_Uk + age0 + sex + bmi0 +\
PC1 + ... + PC10, family = binomial, data = df)

- **Primary estimate:** the tp63_geno:haplo_Uk interaction OR (Durán-Sotuela et al. reported OR 1.67 for rapid progression).

### 11.6 Hypothesis-free arm — longitudinal SNP-set

Replace per-SNP models with **LSKAT** (longitudinal sequence-kernel association test; Wang et al., Genet Epidemiol 2017), more powerful than baseline-only or averaged-outcome analyses and robust to mixed-direction effects. Genome-wide threshold P \< 5×10⁻⁸; accompany with Manhattan/QQ plots and genomic-inflation λ (qqman). Label discovery-only.

### 11.7 Multiplicity and reporting

- **Candidate arm:** FDR control across the curated SNP set, reported **per progression domain** (do not pool across symptomatic/structural/end-stage — genotype effects differ by endpoint).

- **PRS arm:** small number of pre-specified scores; report each.

- **GWAS arm:** genome-wide threshold; discovery-only.

- Report per-allele/per-SD effect (β/OR/HR), 95% CI, model/coding, and FDR-q per endpoint.

### 11.8 Power and precision (genetic arm)

- **Candidate + PRS arms:** with ~3,366 European-ancestry participants (realistic structural-progressor subset on the order of n ≈ 901, 276 progressors in prior OAI ML work), detectable per-allele effects are ~OR 1.4–1.6 or ~0.2 SD on a continuous slope at α = 0.05 for common variants (MAF ≥ 0.20). Adequately powered.

- **Underpowered** for OR 1.02–1.19 GWAS-locus effects at genome-wide significance (Yau et al. found no GWS hits with 3,898 radiographic-OA cases).

- **Recessive tests** lose power sharply at low MAF — interpret cautiously.

- **African-ancestry subset (n = 763):** large effects only; hypothesis-generating.

- **Framing:** OA PRS explains only ~6–21% of heritability and adds little beyond age/sex/BMI — frame PRS results mechanistically, not as clinical prediction (Sedaghati-Khayat et al. 2022; Yau & Loughlin, Arthritis Rheumatol 2022).

### 11.9 Deliverables (genetic arm)

dbGaP/QC/imputation methods section; participant-flow diagram (genotyped → ancestry subset → QC-passed → per-endpoint analytic samples); candidate-SNP results table (per-allele effect, CI, model, FDR-q per domain); PRS association across KL-transition stages (paralleling the Rotterdam stage-dependent figure); mixed-model trajectory plots by genotype for key continuous endpoints; Manhattan/QQ plots with λ if the discovery GWAS is run.

## 12. Appendix — Variable mapping (model term → public OAI / dbGaP source)

**How to read this appendix.** Each model term in Sections 11.1–11.6 is mapped to (a) the OAI **table stem** that holds it, (b) a **representative variable name**, and (c) the **visit(s)** required. Table stems are literature-confirmed and stable across releases; **exact variable strings are representative and version-dependent** — verify every string against the *OAI Data Users Guide* and the NDA data-structure listings for your specific release before coding. Genotype/dosage terms live outside the clinical portal (dbGaP, controlled-access) and are joined via a bridging ID file (see 12.4).

### 12.1 Master crosswalk

| **Model term (Section 11)** | **Role** | **OAI source table (stem)** | **Representative variable(s)** | **Visit / level** |
|----|----|----|----|----|
| time | Continuous years from baseline | Visit metadata / any per-visit table | Visit code V## + assessment date ( V##ACDATE /version date); convert code→months (see 12.3) | Person × visit |
| outcome — minimum JSW / medial JSN | Continuous structural | kXR_QJSW## | V##MCMJSW (medial compartment min JSW), fixed-flexion | Knee × visit |
| outcome — KL grade | Ordinal structural | kXR_SQ_BU## | V##XRKL | Knee × visit |
| outcome — cartilage thickness/volume | Continuous MRI | kMRI_QCart_Eckstein## | e.g. V##MCMFTHCTH (medial femorotibial ThCtAB) | Knee × visit |
| outcome — cartilage T2 | Continuous MRI | kMRI_QCart T2 project table | T2 region variables (per release) | Knee × visit |
| outcome — MOAKS/WORMS worsening | Semiquant MRI | kMRI_SQ_MOAKS_BICL## | MOAKS cartilage/BML sub-scores | Knee × visit |
| outcome — WOMAC pain / function | Continuous symptomatic | AllClinical## | V##WOMKP\[R/L\] (pain), V##WOMADL\[R/L\] (function), V##WOMTS\[R/L\] (total) | Person × visit, side-specific |
| outcome — KOOS (if used) | Continuous symptomatic | AllClinical## | V##KOOS... domain scores | Person × visit, side-specific |
| progressor — OARSI-OMERACT / FNIH | Binary | Derived from kXR_QJSW## + AllClinical## | composite of JSW loss + WOMAC pain | Knee-level derived |
| time_to_event , event — KL4 / TKR | Time-to-event | Outcomes99 (+ kXR_SQ_BU## for KL4) | knee-replacement date/flag; KL=4 transition | Knee × cumulative |
| age0 | Covariate | AllClinical00 | V00AGE | Person, baseline |
| sex | Covariate | Enrollees.txt | P02SEX | Person, fixed |
| bmi0 | Covariate | AllClinical00 | V00BMI (or height/weight V00HEIGHT / V00WEIGHT ) | Person, baseline |
| PC1–PC10 | Ancestry covariates | **Derived** from dbGaP genotypes | principal components you compute post-QC | Person |
| geno_add | Exposure (0/1/2 dosage) | **dbGaP** imputed VCF (controlled) | per-SNP dosage ( DS ) from your imputation | Person |
| haplo_Uk (11.5) | mtDNA haplogroup | **dbGaP** genotypes / mtDNA calls | haplogroup assignment you derive | Person |
| prs_z | Standardized PRS | **Derived** from dbGaP dosages | PRS you compute, then z-standardize | Person |
| Accelerometer endpoints (functional) | Continuous | Physical-activity accelerometer ancillary | count/MVPA/step variables (48-mo substudy) | Person, 48-mo |
| PASE | Self-report activity | AllClinical## | V##PASE | Person × visit |

### 12.2 Keys and join discipline

- **Person-level key:** ID (participant). **Knee-level key:** ID + SIDE (1 = right, 2 = left). All imaging (kXR\_\*, kMRI\_\*) and side-specific WOMAC are **knee-level**; PASE, accelerometer, age, sex, BMI, PCs, and genotype are **person-level** and must be broadcast to both knees on join.

- **Long-format assembly:** stack each per-visit table (AllClinical00…10, kXR_QJSW00…, etc.) into one long table keyed on ID(+SIDE)+visit, so time and the repeated outcome align row-for-row for the mixed models in 11.1–11.2.

- **Composite endpoints (FNIH/esKOA):** merge kXR_QJSW## (knee-level JSW) to AllClinical## (person-level WOMAC) on ID+SIDE, being explicit that WOMAC is stored per side — confirm you are pairing the correct knee's pain with the correct knee's JSW.

- **TKR endpoint:** Outcomes99 is cumulative/adjudicated; derive time_to_event as (event date − baseline date) and censor at last known contact, then attach to the knee-level analytic frame on ID+SIDE.

### 12.3 Visit-code → month mapping (a recurring pitfall)

The V## code is **not** linear in months — the annual imaging/clinical visits skip the interleaved telephone contacts:

| **Code** | **Nominal month** | **Type**                        |
|----------|-------------------|---------------------------------|
| V00      | 0 (baseline)      | Clinic                          |
| V01      | 12                | Clinic                          |
| V03      | 24                | Clinic                          |
| V05      | 36                | Clinic                          |
| V06      | 48                | Clinic (accelerometer substudy) |
| V08      | 72                | Clinic                          |
| V10      | 96                | Clinic (walking survey)         |

(V02/V04/V07/V09 are telephone contacts.) Build time from the actual assessment **date** where available rather than assuming the nominal month, and never treat the numeric part of V## as elapsed months.

### 12.4 Genotype access and the ID bridge

Genotype, PRS, PC, and mtDNA terms are **not** in the OAI clinical/NDA download. They are obtained under a separate **dbGaP** controlled-access application; the delivered genotype sample IDs are linked to the OAI ID through the **dbGaP-provided subject-sample mapping (bridging) file**. Workflow: (1) liftover raw hg18 calls → hg19/hg38; (2) QC + impute (TOPMed recommended); (3) extract per-SNP dosage (DS) for the candidate panel and compute PRS/PCs; (4) merge to the phenotype frame on ID via the bridge. Keep genotype-derived fields in a separately governed file per the dbGaP data-use agreement.

*Prepared as an exploratory analysis plan. Key methodological references: Song et al. (Arthritis Care Res 2010, 2013); Sun et al. (2014); Lo et al. (Arthritis Rheumatol 2022); Skender et al. (BMC Public Health 2016); Migueles et al. (Sports Med 2017); Rotondi & Donner (J Clin Epidemiol 2012); Glover et al. (Qual Life Res 2026); Bentvelzen et al. (PLoS One 2024); Sedaghati-Khayat et al. (Arthritis Rheumatol 2022); Yau et al. (Arthritis Rheumatol 2017); Bonakdari et al. (BMC Med 2022); Durán-Sotuela et al. (Osteoarthritis Cartilage 2024); Benke et al. (Genet Epidemiol 2013); Wang et al. (Genet Epidemiol 2017).*
