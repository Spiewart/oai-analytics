# Assumptions Framework + Lo 2022 Replication — Design

**Date:** 2026-09-30
**Status:** Draft for review
**Builds on:** `docs/superpowers/specs/2026-09-30-oai-analytics-scaffold-design.md`
**Paper:** Lo GH, et al. *Association Between Walking for Exercise and Symptomatic and
Structural Progression in Individuals With Knee Osteoarthritis.* Arthritis Rheumatol
2022;74:1660–7 (doi:10.1002/art.42241), with supplement 0002 (grant analysis plan) and
0003 (Supplementary Tables 1–3).

## 1. Purpose

Before building original studies, test whether the suite reproduces a published OAI
analysis. Step 0 adds a general **assumptions framework**: every analysis keeps a
machine-readable, configurable ledger of the choices it makes, so results are
transparent and sensitivity analyses are one flag away. The replication of Lo 2022 is
the first analysis to use it.

## 2. Scope

**In scope:**
- the assumptions framework (all analyses);
- reusable knee-level derivations in `oai.derive.knee`;
- the `lo2022_walking` analysis: the cohort flow including Supplementary Table 1's
  exclusion groups, Table 1, Table 2 (GEE odds ratios), Table 3 (outcome frequencies by
  static alignment), the sensitivity variants matching Supplementary Tables 2–3, and a
  graded comparison against the published numbers.

**Out of scope:** the age-stratified analyses (reported only as "data not shown"), any
new science beyond the paper, and use of the adjudicated alignment file (it may later
serve as a gold-standard check; see §10).

## 3. Part 1a — Assumptions framework

### 3.1 File format: `analyses/<name>/assumptions.toml` (optional per analysis)

```toml
[exposure.walker_item]                 # key = dotted table path: "exposure.walker_item"
value = "V10WLKAR4"                    # any TOML scalar or array
status = "assumed"                     # confirmed | assumed | open
source = "Lo 2022 p.1662"              # where the choice comes from
rationale = "Only age-50+ walking item in AllClinical10"   # optional
alternatives = []                      # optional, documentation only

[variants.missing_as_walkers]
description = "Supplementary Table 3: missing walking data imputed as walkers"
set = { "cohort.impute_missing_walking" = "walker" }
```

An assumption is any table with a `value` key; its key is its dotted path. `variants`
is reserved. Validation (`AssumptionsError`, an `OAIError`):
- `status` must be one of the three values, and `source` must be non-empty;
- variant `set` keys must name existing assumptions;
- variant and `--set` values must match the TOML type of the default (int, float, str,
  bool, array).

### 3.2 Resolution and runtime access

- `oai run NAME [--variant V] [--set key=value ...]`. Each `--set` value is parsed as a
  TOML literal (`7`, `true`, `"x"`, `[1, 2]`), falling back to a bare string.
- **Run label:** `default`, `<variant>`, or `<variant or default>+custom-<8-hex hash of
  the overrides>`.
- Frames go to `OAI_WORK_DIR/<analysis>/<label>/` and results to
  `<results_dir>/<analysis>/<label>/`, so variants never overwrite each other.
- An explicitly set `OAI_FRAME_DIR` (a bundle's `run.sh`) is used as-is, without a label
  subfolder. `oai export` runs and reads the `default` label.
- Existing analyses keep working; their outputs simply move under `default/`.
- The runner writes `assumptions.resolved.json` into both directories. It holds each
  key's value, its status and source, where the value came from
  (`default|variant|override`), and the label, variant and overrides.
- Steps receive `OAI_ASSUMPTIONS` (the path to the JSON) and `OAI_RUN_LABEL`.
- **Python:** `oai.assumptions.current() -> Resolved` (mapping-style access, e.g.
  `A["exposure.walker_item"]`) reads `OAI_ASSUMPTIONS`.
- **R:** `oaimodels::assumptions()` returns a named list (via `jsonlite`, which is added
  to `r/renv.lock`).
- An analysis without `assumptions.toml` still gets an empty resolved file, and the
  `default` label.
- `oai export` copies the analysis folder, so assumptions travel with bundles; the enclave
  resolves them at run time.

### 3.3 Ledger

- `oai assumptions NAME` prints the ledger: counts per status, then one table per
  status (key, value, source, rationale), then the variants.
- `oai assumptions NAME --write` writes `analyses/<name>/ASSUMPTIONS.md` (generated,
  committed).
- A test fails if a committed `ASSUMPTIONS.md` differs from what `--write` would produce.

## 4. Part 1b — Reusable derivations: `oai.derive.knee`

All return polars frames keyed on `ID` (Int64) and `SIDE` (`"R"`/`"L"`; release codes
1 = Right, 2 = Left). Column lookups are case-insensitive, because the release mixes
`READPRJ`/`readprj`.

| Function | Returns |
|---|---|
| `xray_readings(visits, *, project=15)` | `ID, SIDE, visit, KL, JSM` from `kxr_sq_bu<VV>` restricted to `READPRJ == project`. JSM keeps within-grade decimals (e.g. 1.2). |
| `frequent_knee_pain(visit)` | `ID, SIDE, visit, frequent_pain` (bool). Baseline uses `P01KP[R/L]12CV`; follow-ups use `V<VV>KP[R/L]12CV`. |
| `knee_replacement(by_days)` | `ID, SIDE, replaced_at_baseline, replaced_by` from OUTCOMES99: `V99E[RL]KBLRP`, `V99E[RL]KDAYS <= by_days` (`by_days` may be a per-participant frame of visit days). |
| `knee_alignment(*, source="cooke", visits=("01","03","05","06"), pick="earliest")` | `ID, SIDE, visit, hka` (degrees; negative = varus) from `flxr_kneealign_<source>`, one film per knee. |
| `with_fallback(primary, fallback, on)` | `primary` rows, with missing values filled from `fallback`, plus a `source_visit` column. |

## 5. Part 2 — `analyses/lo2022_walking/`

### 5.1 Steps (all `stage = "local"`)

| Step | Lang | Outputs (aggregate only) |
|---|---|---|
| `cohort` → `build_frame.py` | python | `frame.parquet` (knee-level, in the frame dir); `flow.csv`; `table1.csv`; `table3.csv` |
| `models` → `models.R` | r | `table2.csv` |
| `compare` → `compare.py` | python | `comparison.csv`; a printed verdict summary |

### 5.2 Cohort flow (persons; knees where noted). Paper targets are in brackets.

1. All enrollees [4,796].
2. Age ≥ `cohort.min_age` [4,247].
3. Has a baseline Project-15 reading for ≥ 1 knee [3,980].
4. Radiographic OA: ≥ 1 native knee with baseline KL ≥ 2 [2,356].
5. Exclude `V10FVDATE < cohort.survey_start` [417 excluded → 1,939; S1: 644 knees].
6. Exclude no 96-month visit (`V10FVDATE` missing) [346 → 1,593; S1: 553 knees].
7. Exclude participants who answered no survey item (`cohort.survey_completed_items`)
   [337 → 1,256; S1: 513 knees].
8. Exclude participants with no follow-up reading (V06, else V05) for any included knee
   [44 → 1,212; S1: 73 knees].

**Included knees:** native at baseline, baseline KL ≥ 2, with a follow-up reading
[1,808].

### 5.3 Exposure

- Walker if `exposure.walker_item` == 1; non-walker if 0.
- Survey respondents with the item missing are coded `exposure.missing_walking_as`
  [n = 17 → non-walker].
- `exposure.walking_times` = years × months/year × times/month, using the category
  midpoints in `exposure.category_midpoints`. It is descriptive only (Table 1 quantiles).

### 5.4 Outcomes (knee-level, baseline → V06, else V05)

- **KL worsening:** follow-up KL > baseline KL, or the knee was replaced by follow-up if
  `outcomes.replacement_is_structural_worsening`.
- **Medial JSN worsening:** follow-up JSM > baseline JSM (including within-grade), or
  replaced (same flag).
- **New frequent pain:** among knees without baseline frequent pain, follow-up frequent
  pain.
- **Improved frequent pain:** among knees with baseline frequent pain, no follow-up
  frequent pain.
- **Replaced knees in the pain outcomes:** handled per `outcomes.replaced_knee_pain`
  (`keep` | `exclude`).

### 5.5 Models (R, geepack)

`geeglm(outcome ~ walker [+ age + sex + kl0], id = ID, family = binomial, corstr =
model.corstr)`, on data sorted by `ID`. `kl0` is a factor or numeric per
`model.kl_covariate`. The step reports n, events, unadjusted and adjusted ORs, and Wald
95% CIs.

### 5.6 Static alignment (Table 1 rows, Table 3)

- Varus if `hka <= alignment.varus_max` (−2); valgus if `hka >= alignment.valgus_min`
  (2); otherwise neutral. The film is chosen by `alignment.pick`.
- Table 3 is counts only (walker × outcome × alignment). The paper fit no models here.

### 5.7 Published numbers and comparison

- `published.toml` holds the paper's values, keyed by variant (`default`,
  `missing_as_nonwalkers`, `missing_as_walkers`): flow steps, S1 group persons/knees and
  sex, Table 1 rows, Table 2 and S2/S3 prevalences and ORs, and the Table 3 cells. Each
  row lists the assumption keys that bear on it.
- `compare.py` joins the run's outputs to the matching variant's published values. Each
  row is marked **replicated** when:
  - a count is within max(3% of the published value, 2);
  - a mean is within 0.5;
  - an OR is within 0.1 of the published (rounded) value, with the same significance
    (95% CI excludes 1).

  Otherwise the row is marked **drift**, with the related assumption keys and their
  statuses. A published row we cannot produce is marked **missing**.
- The verdict summary gives counts by status, lists the drift rows, and names the
  assumptions most often implicated.

### 5.8 Variants

| Variant | Sets | Published target |
|---|---|---|
| `missing_as_nonwalkers` | `cohort.impute_missing_walking = "non-walker"` (adds participants excluded at flow steps 5–7 who have follow-up readings) | Supp. Table 2 |
| `missing_as_walkers` | same, imputed as `"walker"` | Supp. Table 3 |
| `replacement_not_worsening` | `outcomes.replacement_is_structural_worsening = false` | — (sensitivity) |
| `corstr_independence` | `model.corstr = "independence"` | — (sensitivity) |

## 6. Initial assumptions ledger (`analyses/lo2022_walking/assumptions.toml`)

| Key | Default | Status | Source / check |
|---|---|---|---|
| `cohort.min_age` | 50 | confirmed | p.1661 |
| `cohort.reading_project` | 15 | assumed | ref 11 (Project 15 reliability); check flow 3–4 |
| `cohort.survey_start` | "2012-09-12" | assumed | p.1662; check S1 417 persons / 644 knees |
| `cohort.survey_completed_items` | ["V10WLKAR1", "V10WLKAR2", "V10WLKAR3", "V10WLKAR4"] | assumed | check S1 337 persons; 17 missing-walking respondents |
| `cohort.impute_missing_walking` | "none" | confirmed | primary analysis excludes non-respondents |
| `knees.min_kl` | 2 | confirmed | p.1661; Table 1 |
| `exposure.walker_item` | "V10WLKAR4" | assumed | release item adds "≥ 20 min/day"; check 887 walkers |
| `exposure.missing_walking_as` | "non-walker" | confirmed | p.1662 |
| `exposure.category_midpoints` | years [3, 8, 15.5, 20]; months [2.5, 6.5, 10.5]; times [2, 6, 10] | open | check Table 1 quantiles: 20 × 10.5 × 10 reproduces the published max of 2,100; the published min of 13 is not yet explained |
| `outcomes.followup_visits` | ["06", "05"] | confirmed | p.1662 |
| `outcomes.pain_baseline_items` | "P01KP{side}12CV" | assumed | check 676/1,808 baseline frequent pain |
| `outcomes.pain_followup_items` | "V{visit}KP{side}12CV" | assumed | check 729/1,808 at 48 months |
| `outcomes.replacement_is_structural_worsening` | true | assumed | p.1663 rationale for keeping KL4/JSN3 |
| `outcomes.replaced_knee_pain` | "keep" | open | not stated |
| `outcomes.replacement_window` | "follow-up visit days" | assumed | check 77/1,808 replaced |
| `alignment.source` | "cooke" | assumed | refs 13–14; film counts by visit match p.1662 |
| `alignment.pick` | "earliest" | assumed | check 1,484 knees / 985 persons with films |
| `alignment.varus_max`, `alignment.valgus_min` | −2, 2 | confirmed | p.1662 |
| `model.covariates` | ["age", "sex", "kl0"] | confirmed | Table 2 footnote |
| `model.corstr` | "exchangeable" | open | not stated |
| `model.kl_covariate` | "factor" | open | not stated |

Supplement 0002 is the grant's general analysis plan. It confirms knee-level analysis
that accounts for within-person correlation, but it does not settle the `open` items.

## 7. Testing

- **Assumptions:** parsing, validation errors, variant and `--set` resolution with
  typing, run labels and directories, the resolved JSON, R access, ledger rendering, and
  the ledger-staleness test over every analysis.
- **Derivations:** the synthetic release is extended with Project-15/37 rows,
  mixed-case `readprj`, decimal JSM, 36- and 48-month pain and readings, OUTCOMES99
  replacement fields, and Cooke alignment files. Each function is tested on it.
- **Comparison:** tolerance and verdict rules on synthetic outputs.
- **Real data:** runs the default variant end to end and asserts that every output and
  a `comparison.csv` exist. It does **not** assert that the replication succeeds; that
  is the finding.

## 8. Success criteria

- `oai run lo2022_walking` produces flow, Tables 1–3 and Table 2 on the real release,
  plus a comparison with a verdict for every published row.
- The `missing_as_nonwalkers` and `missing_as_walkers` variants run and compare against
  S2/S3.
- `oai assumptions lo2022_walking` renders the ledger; `ASSUMPTIONS.md` is committed and
  in sync.
- All outputs pass `oai check-egress` (warnings allowed).
- The replication verdict is reported to the user as a finding, with each drift linked
  to its assumptions.

## 9. Error handling

- Unknown variant or `--set` key, type mismatch, or malformed `assumptions.toml` →
  `AssumptionsError` with the file and key.
- A missing required release table or column → `CatalogError` / a clear step failure
  naming the table and column.
- `compare.py` never fails because of drift; it fails only if outputs are missing or
  malformed.

## 10. Open questions (tracked, not blocking)

- The `open` assumptions above; sensitivity variants cover the two largest.
- Grace Lo's adjudicated alignment file could validate `alignment.*`; if obtained, it
  stays outside the repo (data) and is referenced via config.
