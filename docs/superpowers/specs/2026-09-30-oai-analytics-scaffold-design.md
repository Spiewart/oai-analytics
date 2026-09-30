# OAI Analytics — Scaffold Design

**Date:** 2026-09-30
**Status:** Draft for review
**Repo:** `Spiewart/oai-analytics` (public, MIT)

## 1. Purpose

An analytic suite for Osteoarthritis Initiative (OAI) data. It must:

1. Keep all source data **outside** the repository, located via configuration.
2. Run analyses **locally** against the public OAI phenotype release.
3. **Export** analyses that need controlled-access genotype data (dbGaP GeCKO,
   `phs000955.v1.p1`) to a secure, NIST SP 800-171–compliant institutional
   enclave, and bring back only aggregate results.

Initial analyses (from `docs/reference/`): activity agreement (PASE vs.
ActiGraph), progression-definition derivations, and the per-genotype
progression arm.

## 2. Scope of this pass

**In scope:** directory structure, Python and R packaging, configuration,
data-leak guards, CI, and a *working, tested* core — catalog, loader, visit
map, analysis runner, export bundle, egress check. Analyses get manifests and
stub steps only.

**Out of scope:** any analysis logic (PASE scoring, accelerometer processing,
progression endpoints, models), offline dependency vendoring, container
builds, genotype QC/imputation pipelines.

## 3. Key decisions

| Decision | Choice | Reason |
|---|---|---|
| Languages | Python for data, R for models | Analysis plan specifies lme4 / ordinal::clmm / geepack / survival frailty / LSKAT; no Python equivalents for clmm or Cox shared frailty. |
| Python tooling | uv, Python ≥ 3.11, package `oai`, CLI `oai` | Matches existing user tooling. |
| DataFrame library | polars | By-minute accelerometer files are 580–790 MB; lazy scanning needed. `.to_pandas()` available. |
| R tooling | renv project in `r/`, R package `oaimodels` | Package gives namespace + testthat and installs from a source tarball offline. |
| Python→R interchange | Parquet, read in R with `nanoparquet` | Zero-dependency; compiles cleanly on an offline enclave (unlike `arrow`). |
| Orchestration | Minimal sequential runner driven by `analysis.toml` | YAGNI; Snakemake/targets can be adopted later without changing manifests much. |
| Export target | Self-contained tarball; worst-case assumptions | dbGaP best practices require restricted outbound access; enclave rules unknown. |

## 4. Repository layout

```
oai-analytics/
├── README.md
├── LICENSE                         # MIT
├── pyproject.toml
├── uv.lock
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── config/
│   └── oai.toml                    # non-secret defaults: visit map, egress rules
├── docs/
│   ├── reference/                  # the four .docx + generated .md copies
│   └── superpowers/specs/          # design docs
├── src/oai/
│   ├── __init__.py
│   ├── config.py                   # settings resolution
│   ├── catalog.py                  # index of tables in OAI_DATA_DIR
│   ├── loader.py                   # read_table(), codebook(), missing-code policy
│   ├── visits.py                   # visit map, to_long(), time derivation
│   ├── manifest.py                 # analysis.toml parsing/validation
│   ├── runner.py                   # `oai run`
│   ├── derive/                     # stubs: pase.py, accel.py, progression.py
│   ├── export/
│   │   ├── bundle.py               # `oai export`
│   │   └── egress.py               # `oai check-egress`
│   └── cli.py                      # typer app
├── r/
│   ├── renv.lock
│   ├── .Rprofile
│   └── oaimodels/                  # DESCRIPTION, NAMESPACE, R/, tests/testthat/
├── analyses/
│   ├── activity_agreement/         # analysis.toml, README.md, steps
│   ├── progression_definitions/
│   └── genetics_progression/
├── scripts/
│   └── check_no_data.py            # leak guard (pre-commit + CI)
├── tests/
│   ├── fixtures/                   # synthetic pipe-delimited tables
│   └── test_*.py
└── .github/workflows/ci.yml
```

## 5. Configuration

Resolution order, first hit wins: **process env → `.env` → `config/oai.toml` →
error**. No silent default for data locations.

| Key | Meaning | Where set |
|---|---|---|
| `OAI_DATA_DIR` | Raw OAI phenotype tables (read-only) | Local & enclave |
| `OAI_WORK_DIR` | Derived individual-level files, Parquet cache, export log. Must be outside the repo; `config.py` refuses a path inside the repo. | Local & enclave |
| `OAI_GENO_DIR` | Genotype data and all genotype-derived intermediates — the single directory destroyed at close-out | Enclave only |
| `OAI_RESULTS_DIR` | Aggregate outputs (defaults to `OAI_WORK_DIR/results`) | Optional |

`.env.example` documents all keys; `.env` is git-ignored.

## 6. Data-leak protection

The repo is public; OAI (NDA) and dbGaP data are covered by data-use
agreements. Derived individual-level data is treated as source data.

1. **`.gitignore`**: `.env`, `*.parquet`, `*.feather`, `*.txt` outside
   `docs/`, `work/`, `results/`, `bundles/`, `*.tar.gz`, `.DS_Store`.
2. **`scripts/check_no_data.py`** (pre-commit hook and CI step) fails if any
   tracked or staged file:
   - has a pipe-delimited first line starting with `ID|`, or
   - contains a 7-digit token matching `\b9\d{6}\b` (OAI participant IDs), or
   - is a binary data format (`.parquet`, `.sas7bdat`, `.feather`, `.rds`).
   An allowlist file (`scripts/leak_allowlist.txt`) exempts specific paths.
3. **Test fixtures** use fake IDs `1000001…` so they never match the pattern.
4. `config.py` rejects `OAI_WORK_DIR` / `OAI_RESULTS_DIR` inside the repo.

## 7. Python core

### 7.1 `catalog.py`

Scans `OAI_DATA_DIR/*.txt` once and builds `Catalog: dict[(table, visit), Path]`.

- **Normalization:** stem lower-cased; a trailing two-digit suffix is the visit
  code (`AllClinical10` → `("allclinical", "10")`, `ALLCLINICAL13` →
  `("allclinical", "13")`).
- **No suffix** (e.g. `Enrollees`, `Clinical_FNIH`) → visit `None`.
- **Cumulative codes** `97` (`COVIDQ97`) and `99` (`OUTCOMES99`) are recorded
  with `kind = "cumulative"`, not as visits.
- Files ending `_Formats` are excluded (format dictionaries, not data).
- Case-variant collisions for the same key raise an error listing both paths.
- `oai catalog` prints tables × visits as a grid.

### 7.2 `loader.py`

```python
read_table(name: str, visit: str | None = None, *, columns: list[str] | None = None,
           lazy: bool = False) -> pl.DataFrame | pl.LazyFrame
codebook(name: str, visit: str | None = None) -> dict[str, dict[int | str, str]]
```

- Reads pipe-delimited text via polars (`separator="|"`, all columns as `Utf8`
  initially).
- **Coded cells** (`"1: Right"`, `"0: 0"`): the value before the first `": "`
  becomes the cell value (cast to numeric when every non-missing value in the
  column is numeric); the label goes into the table's codebook.
- **Missing-value codes** (cells starting with `.`, e.g.
  `".: Missing Form/Incomplete Workbook"`, `".A: …"`) are handled by a single
  function, `resolve_missing(raw: str) -> MissingResolution`. **The policy is a
  user-authored decision** (null everything vs. keep reason codes in a sidecar
  column).
- **Parquet cache:** first read writes
  `OAI_WORK_DIR/cache/<table><visit>.parquet`, keyed on source size + mtime;
  stale caches are rebuilt.
- Column names are preserved exactly as released (`V00XRKL`, `ID`, `SIDE`).

### 7.3 `visits.py`

The visit map lives in `config/oai.toml`:

```toml
[visits]
V00 = { month = 0,  contact = "clinic", verified = true }
V01 = { month = 12, contact = "clinic", verified = true }
V02 = { month = 18, contact = "phone",  verified = true }
# … V03–V10 per docs/reference table …
V11 = { verified = false }   # month/contact omitted until confirmed from release PDFs
# … V12–V14 likewise …
```

- `nominal_month(code)` raises `UnverifiedVisitError` for `verified = false`
  (TOML has no null, so unverified entries simply omit `month`).
- `to_long(df, id_cols=("ID",) | ("ID","SIDE"))` melts `V##<VAR>` columns into
  rows keyed on id columns + `visit`, with the variable stem as column name.
- `time_years(df)` uses `V##VISDYS / 365.25` where available, falling back to
  `nominal_month / 12`, and records which source was used in a `time_source`
  column.

### 7.4 `manifest.py` and `runner.py`

`analyses/<name>/analysis.toml`:

```toml
name = "genetics_progression"
description = "Per-genotype progression models (dbGaP phs000955)"

[inputs]
tables = ["allclinical:00", "enrollees", "kxr_qjsw_duryea:*", "outcomes:99"]

[[steps]]
id = "frame"
lang = "python"
stage = "local"          # runs on the laptop
entry = "build_frame.py"

[[steps]]
id = "models"
lang = "r"
stage = "enclave"        # runs only where OAI_GENO_DIR is set
entry = "models.R"
needs = ["frame"]

[export]
frame = "frame.parquet"
columns = ["ID", "SIDE", "visit", "time_years", "age0", "sex", "bmi0"]

[outputs]
aggregate = ["results/*.csv", "figures/*.png"]
```

- Input syntax: `"<table>"` (no visit), `"<table>:<VV>"` (one visit), or
  `"<table>:*"` (every visit present in the catalog for that table).
- Validation: unique step ids, `needs` refer to earlier steps, `lang` ∈
  {python, r}, `stage` ∈ {local, enclave}, inputs resolvable in the catalog
  (checked at run time, not parse time).
- `oai run <analysis> [--stage local|enclave] [--step ID]` executes matching
  steps in declared order via subprocess (`uv run python …` / `Rscript …`),
  passing `OAI_FRAME_DIR` (= `OAI_WORK_DIR/<analysis>`) and `OAI_RESULTS_DIR`.
- `stage = "enclave"` steps refuse to run unless `OAI_GENO_DIR` is set.

## 8. R side

- `r/` is an renv project. Initial lockfile: `nanoparquet`, `lme4`, `ordinal`,
  `geepack`, `survival`, `testthat`.
- `oaimodels` exports:
  - `read_frame(path)` — working; reads Parquet via nanoparquet, returns a
    data.frame, and asserts required columns.
  - `fit_progression_lmm()`, `fit_kl_clmm()`, `fit_progressor_gee()`,
    `fit_tkr_cox()` — stubs whose signatures and roxygen docs mirror §11.1–11.4
    of the analysis plan; bodies `stop("not implemented")`.
- testthat tests cover `read_frame()` against a small Parquet fixture.

## 9. Export and egress

### 9.1 `oai export <analysis> [--out DIR] [--vendor]`

1. Runs all `stage = "local"` steps.
2. Selects only `[export].columns` from the frame; fails if a declared column is
   missing.
3. Builds `bundles/<analysis>-<timestamp>.tar.gz` (in `OAI_WORK_DIR`)
   containing:
   ```
   code/   oai-<ver>-py3-none-any.whl, oaimodels_<ver>.tar.gz, analyses/<analysis>/
   env/    requirements.txt (from uv.lock, with hashes), renv.lock
   data/   <frame>.parquet
   run.sh  README_ENCLAVE.md  MANIFEST.json
   ```
4. `MANIFEST.json`: SHA-256 of every file, git commit (refuses to export from a
   dirty tree unless `--allow-dirty`), `oai` version, analysis name, frame row
   and column counts, UTC timestamp.
5. Appends a record to `OAI_WORK_DIR/export_log.jsonl` (copy tracking per NIH
   Security Best Practices).
6. `--vendor`: **stub** — prints the documented procedure for downloading
   `linux/x86_64` wheels and R source tarballs. A `linux/amd64` Dockerfile →
   Apptainer path is documented in `README_ENCLAVE.md`, not built.

`run.sh` (enclave): verifies manifest checksums, installs the wheel and R
package (online or from a vendored directory if present), sets `OAI_FRAME_DIR`
to the bundle's `data/`, runs `oai run <analysis> --stage enclave`, then runs
`oai check-egress` on the results directory.

### 9.2 `oai check-egress <dir>`

Scans CSV/TSV/Parquet/JSON files in `<dir>`; non-text outputs (PNG/PDF) are
listed for manual review. Fails if any file:

- has a column named like an identifier (`ID`, `src_subject_id`, `SUBJID`,
  `sample_id`, case-insensitive), or
- contains a `\b9\d{6}\b` token, or
- has a count-like column (`n`, `count`, `n_*`) with a value between 1 and
  the configured minimum cell size. **The threshold and rule are a
  user-authored decision** (`config/oai.toml [egress] min_cell`).

Exit code non-zero on failure with a per-file report.

## 10. Testing and CI

- **pytest** with synthetic fixtures in `tests/fixtures/` (tiny pipe-delimited
  tables mimicking real headers, coded cells, and missing codes; IDs
  `1000001…`). Covers config resolution, catalog normalization and collisions,
  loader parsing/caching, visit map and `to_long`, manifest validation, runner
  step selection, bundle contents + manifest checksums, egress failures.
- **`@pytest.mark.realdata`**: smoke tests against the real release (catalog
  builds; `Enrollees`, `AllClinical00`, `kxr_sq_bu00` load); run only when
  `OAI_DATA_DIR` is set, skipped in CI.
- **testthat** for `oaimodels`.
- **GitHub Actions** (`ci.yml`): ruff, pytest on Python 3.11 and 3.13, R tests
  via `r-lib/actions`, and `scripts/check_no_data.py` across the tree.

## 11. User-authored decision points

1. `loader.resolve_missing()` — missing-value code policy.
2. `egress` small-cell rule — threshold and which columns count.

## 12. Open questions (tracked, not blocking)

- Nominal months for V11–V14: confirm from `AllClinical13_ReleaseComments_Yr14.pdf`
  / `AllClinical14_ReleaseComments_Y16.pdf` and the Data Users Guide.
- Genotype build: dbGaP lists GeCKO as hg37; the analysis plan says hg18 with
  liftover. Resolve on data receipt.
- Enclave capabilities (internet, containers, R/Python versions) — determines
  whether `--vendor` or the Apptainer path gets implemented.

## 13. Success criteria

- `uv run pytest` and R testthat pass; CI green on GitHub.
- With `OAI_DATA_DIR` set, `oai catalog` lists every data file (156 files /
  43 tables in the current release; the two `_Formats` files are excluded) with
  no collisions, and realdata smoke tests pass.
- `oai export` on a toy analysis produces a bundle whose manifest checksums
  verify, and `oai check-egress` rejects a planted ID column.
- `scripts/check_no_data.py` passes on the repo and fails on a planted
  `ID|…` file.
- Public repo `Spiewart/oai-analytics` exists with no data files in history.
