# oai-analytics

An analysis suite for [Osteoarthritis Initiative](https://nda.nih.gov/oai) (OAI) data. Python loads and derives; R fits models. Analyses that need controlled-access genotypes (dbGaP GeCKO, [phs000955](https://www.ncbi.nlm.nih.gov/projects/gap/cgi-bin/study.cgi?study_id=phs000955.v1.p1)) are exported as self-contained bundles that run inside a NIST SP 800-171–compliant enclave. Only egress-checked aggregate results come back out.

> **No data lives in this repository.** OAI phenotype data (NDA) and genotype data (dbGaP) are covered by data-use agreements. Source data, derived frames, caches and bundles all live outside the repo. A pre-commit hook and CI block anything that looks like participant data.

## Setup

Requirements: [uv](https://docs.astral.sh/uv/), git, and R ≥ 4.4 for model steps (the lockfile is built with R 4.5.2).

```bash
uv sync
uv run pre-commit install
cp .env.example .env                  # set OAI_DATA_DIR and OAI_WORK_DIR
(cd r && Rscript -e 'renv::restore()')
uv run oai catalog                    # sanity check: lists the tables in your release
```

## Configuration

Settings resolve in this order: environment → `.env` → `[paths]` in `config/oai.toml` → error.

| Variable | Meaning |
|---|---|
| `OAI_DATA_DIR` | Raw OAI release (pipe-delimited `.txt`), read-only |
| `OAI_WORK_DIR` | Parquet cache, derived frames, bundles, export log. **Must be outside the repo.** |
| `OAI_RESULTS_DIR` | Aggregate outputs (default `$OAI_WORK_DIR/results`) |
| `OAI_GENO_DIR` | Enclave only. Genotypes and everything derived from them. Destroyed at close-out. |

`config/oai.toml` holds the visit-code map and the egress rules.

## Commands

| Command | Does |
|---|---|
| `oai catalog` | List tables × visits found in `OAI_DATA_DIR` |
| `oai analyses` | List analyses and validate their `analysis.toml` |
| `oai run NAME [--stage local\|enclave] [--step ID]` | Run an analysis's steps in order |
| `oai run NAME --variant V` / `--set key=value` | Run with a named sensitivity variant or ad-hoc overrides ([docs/assumptions.md](docs/assumptions.md)) |
| `oai assumptions NAME [--write]` | Show or write an analysis's assumptions ledger |
| `oai export NAME` | Build an enclave bundle (`OAI_WORK_DIR/bundles/NAME-<utc>.tar.gz`) |
| `oai missing TABLE [VISIT] [--csv FILE]` | Show each missing-value code per column: label, count and what it became |
| `oai check-egress DIR` | Fail on identifiers or individual-level data; warn on small cells ([docs/egress.md](docs/egress.md)) |

## Python API

```python
from oai.loader import read_table, codebook
from oai.visits import to_long, time_years

kxr = read_table("kxr_sq_bu", "00", columns=["ID", "SIDE", "V00XRKL"])  # typed polars frame
codebook("kxr_sq_bu", "00").labels["SIDE"]                               # {'1': 'Right', '2': 'Left'}
long = time_years(to_long(read_table("allclinical", "03")))              # ID, visit, ..., time_years
```

Coded cells (`1: Right`) load as their code, with labels in the codebook. Missing codes (`.: Missing Form/…`) currently all become null; `oai missing TABLE [VISIT]` shows what was nulled, and [docs/missing-values.md](docs/missing-values.md) explains the codes and how to change the policy. `V##` is **not** elapsed months (V06 = 48 mo), so always use `oai.visits`.

## Analyses

| Analysis | Runs | Reference |
|---|---|---|
| `activity_agreement` | local | [analysis plan §1–9](docs/reference/oai-activity-agreement-analysis-plan.md) |
| `progression_definitions` | local | [crosswalk](docs/reference/oai-progression-definition-crosswalk.md) |
| `genetics_progression` | local → enclave | [analysis plan §10–12](docs/reference/oai-activity-agreement-analysis-plan.md) |

Each folder's `analysis.toml` declares its input tables, ordered steps (`lang = python|r`, `stage = local|enclave`), the columns it exports and its aggregate outputs.

## Enclave workflow

1. `oai export genetics_progression` runs the local steps and packages code, lockfiles, the column-restricted frame, `run.sh` and checksums. The export is appended to `OAI_WORK_DIR/export_log.jsonl`.
2. Move the tarball with your institution's approved transfer method and extract it **inside** `$OAI_GENO_DIR`.
3. `bash run.sh` verifies checksums, installs, runs the `enclave` steps, then runs `oai check-egress`.
4. Only results that pass the egress check leave the enclave.
5. At close-out, destroy `$OAI_GENO_DIR`.

Each bundle's `README_ENCLAVE.md` covers offline installation and containers.

## Development

```bash
uv run pytest                    # unit tests on synthetic fixtures
uv run pytest -m realdata        # smoke tests against your OAI_DATA_DIR
uv run pytest -m slow            # builds a real wheel
(cd r && Rscript -e 'testthat::test_local("oaimodels")')
uv run python scripts/check_no_data.py
```

## Repository layout

```
config/oai.toml      visit map, egress rules
src/oai/             Python package (catalog, loader, visits, manifest, runner, export/)
r/                   renv project + oaimodels R package
analyses/<name>/     analysis.toml + step scripts
docs/reference/      source documents (.docx) with Markdown copies
scripts/             leak guard, docx→md converter
tests/               pytest (synthetic fixtures only)
```

## Data use

You need your own approved access to OAI (NIMH Data Archive) and, for the genetic arm, dbGaP phs000955. Follow the acknowledgment and publication requirements in your data use certifications, and cite the accession numbers.

## License

MIT. See [LICENSE](LICENSE).
