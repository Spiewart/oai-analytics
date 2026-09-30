# Assumptions

Every analysis records its analytic choices in `analyses/<name>/assumptions.toml`, so
results are transparent and sensitivity analyses are a flag away.

## The file

```toml
[cohort.survey_start]              # key: cohort.survey_start
value = "2012-09-12"               # scalar, array or inline table (dates as strings)
status = "assumed"                 # confirmed | assumed | open
source = "Lo 2022 p.1662"          # where the choice comes from (required)
rationale = "Visit-date cutoff"    # optional
alternatives = ["none"]            # optional, documentation only
# choices = ["a", "b"]             # optional, ENFORCED: variants and --set must pick one

[variants.missing_as_walkers]      # named override set for a sensitivity analysis
description = "Supplementary Table 3"
set = { "cohort.impute_missing_walking" = "walker" }
```

- **confirmed:** stated by the source (paper, protocol, data documentation).
- **assumed:** our reading, ideally checked against a published number.
- **open:** not stated anywhere; a sensitivity variant should cover it.

Give enumerated settings `choices`, so a typo such as `--set model.corstr=exchangable`
fails before any step runs instead of silently taking an `else` branch.

## Running with variants and overrides

```bash
oai run lo2022_walking                                    # label: default
oai run lo2022_walking --variant missing_as_walkers       # label: missing_as_walkers
oai run lo2022_walking --set model.corstr=independence    # label: default+custom-<hash>
```

- **Where outputs go:** each label has its own folders, `$OAI_WORK_DIR/<analysis>/<label>/`
  and `$OAI_RESULTS_DIR/<analysis>/<label>/`, so runs never overwrite each other.
- **Provenance:** both folders get `assumptions.resolved.json`, recording every value used
  and whether it came from the default, the variant or an override.
- **Validation:** unknown keys, unknown variants and type mismatches fail before any step
  runs.
- **Reading values in steps:**
  - Python: `from oai.assumptions import current; A = current(); A["model.corstr"]`
  - R: `A <- oaimodels::assumptions(); A[["model.corstr"]]`

## The ledger

`oai assumptions NAME` prints the ledger grouped by status, and `--write` saves it as
`ASSUMPTIONS.md` next to the TOML. A test fails if a committed ledger is stale.
