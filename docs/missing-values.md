# Missing values

OAI tables mark missing data with codes that start with a dot, e.g.
`.: Missing Form/Incomplete Workbook` or `.A: Not Expected`. The loader
(`oai.loader`) decides what those cells become through one function,
`resolve_missing`, and records what it did for every table.

## Current policy: every missing code becomes null

All codes become `null`, and no side columns are added. As a result:

- numeric columns stay numeric (Int64/Float64) and summary statistics work directly;
- the reason a cell is missing is not kept per cell, but it **is** recorded per column
  and per code, with counts (see below).

Blank cells (the release uses a single space) are also null. They are not
missing *codes*, so they don't appear in the missing-value records. Many instrument
scores use blanks rather than codes: at baseline, for example, `V00WOMKPR` has 3 null
cells and `V00PASE` has 29, and none of them carry a code. Use `df.null_count()` for
the full picture of missingness, and the records below for the reasons.

## Codes in the current release

Counted across all 156 tables with `missing_summary` (release on disk as of 2026-09-30):

| Code | Label | Cells | Tables |
|---|---|---:|---:|
| `.` | Missing Form/Incomplete Workbook | 4,938,524 | 50 |
| `.M` | Missing | 550,328 | 2 |
| `.A` | Not Expected | 236,026 | 2 |
| `.N` | Not Required/Not edited | 56,650 | 1 |
| `.T` | Technical Problems | 22,418 | 6 |
| `.F` | Not done, phone contact | 19,476 | 1 |
| `.X` | Don't Do | 3,978 | 1 |
| `.J` | Unassigned | 3,168 | 4 |
| `.P` | Prosthetic | 3,146 | 4 (hand X-ray readings `hxr_sq*` only) |
| `.R` | Refused | 3,118 | 1 |
| `.D` | Don't Know/Unknown/Uncertain | 785 | 2 |
| `.U` | Unable to examine | 224 | 4 |
| `.O` | Not done, other reason | 18 | 1 |

Some codes are informative rather than random. `.A` (not expected at that visit),
`.F` (a phone-only contact) and `.P` (a prosthetic joint) all explain *why* a value
cannot exist. Keep that in mind when choosing between complete-case analysis and
imputation. Knee replacement itself is recorded in `OUTCOMES99`, not as a missing code.

## Seeing what the policy did

Every table's codebook records, per column and per code, the label, how many cells
carried the code, and what `resolve_missing` returned:

```python
from oai.loader import codebook, missing_summary

cb = codebook("kxr_sq_bu", "06")
cb.missing["V06XRKL"]             # {'.': 'Missing Form/Incomplete Workbook'}
cb.missing_counts["V06XRKL"]      # {'.': 177}
cb.missing_resolution["V06XRKL"]  # {'.': {'value': None, 'reason': None}}

missing_summary("kxr_sq_bu", "06")  # one row per column x code:
                                    # table, column, code, label, n, value, reason
```

From the command line:

```bash
oai missing kxr_sq_bu 06                       # print the summary
oai missing allclinical 06 --csv missing.csv   # also save it
```

The same records are stored on disk next to each cached table, in
`$OAI_WORK_DIR/cache/<table>_<visit>.json`.

## Changing the policy

Edit `resolve_missing` in `src/oai/loader.py`. It receives the raw cell text, the
column name and the table key, and returns a `MissingResolution`:

| Return | Effect |
|---|---|
| `MissingResolution()` | cell becomes null (current policy) |
| `MissingResolution(reason="prosthetic")` | cell becomes null, and a `<column>__reason` column holds `"prosthetic"` for those rows |
| `MissingResolution(value="-9")` | cell holds the sentinel; a non-numeric sentinel turns the whole column into text |

Example: keep hand-joint prosthetics distinguishable from other missingness:

```python
def resolve_missing(raw, *, column, table):
    if table.startswith("hxr_sq") and raw.startswith(".P"):
        return MissingResolution(reason="prosthetic")
    return MissingResolution()
```

Any edit to `loader.py` (or a polars upgrade) changes the cache fingerprint, so every
table is re-parsed on its next read. Cached results never reflect an old policy.
