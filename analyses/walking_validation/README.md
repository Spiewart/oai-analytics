# walking_validation

Validity of the 96-month walking-for-exercise item, the exposure in Lo et al. 2022 (Arthritis
Rheumatol 74:1660-7), against the OAI accelerometer waves at 48 and 72 months. Includes a
record-level probabilistic bias analysis of the paper's odds ratios.
Spec: [docs/superpowers/specs/2026-10-01-walking-validation-design.md](../../docs/superpowers/specs/2026-10-01-walking-validation-design.md).

| Step | Lang | Output |
|---|---|---|
| `device` | Python | device measures per person and wave (frame); agreement with the release (`device_reproduction.csv`) |
| `cohort` | Python | validation frame, Lo 2022 subset and knee frame (frames); `flow.csv`; Lo Table 2 copies |
| `validity` | R | known groups, dose-response, convergent ranking, Se/Sp, strata, PASE benchmark |
| `components` | R | answer-level sub-analyses (spec amendment 12): PASE item 2's days and hours answers, alone and as weekly walking (`validity_components_pase.csv`); the item's amount answers as walker definitions, with their correction factors (`validity_components_item.csv`); hexagonal cells of the agreement figure (`validity_components_hex.csv`) |
| `bias` | R | probabilistic bias analysis, tipping-point grid, summary-level correction |
| `compare` | Python | `comparison.csv`: device reproduction and sample sizes against `expected.toml` |

Needs the replication's frame for the matching exposure coding:
`oai run lo2022_walking --variant walker_requires_amount` (primary) or `oai run lo2022_walking`
(variant `exposure_replication_coding`). R steps run under the `report` renv profile (`[r]`).

## Running it

`oai run walking_validation` takes about 8 minutes on a laptop.

`OAI_R_CORES` sets how many cores the `bias` step uses for its draws (each refits the replication's GEE models). It must be a positive integer, otherwise the step stops with `OAI_R_CORES must be a positive integer, got ...`. Unset, it defaults to the detected cores minus one (at least 1). Results do not depend on it: each iteration seeds its own random numbers (`bias.seed`).

## Sending the brief

`uv run oai report walking_validation` writes four PDFs to `<results>/walking_validation/report/`, where `<results>` is the results folder (`$OAI_RESULTS_DIR`). It needs a finished run: add `--run` to run it first. The PDFs are:

- `brief.pdf`: the 4–6 page brief to the accelerometry group;
- `report.pdf`: the technical report, kept as the full record and available on request;
- `clinical.pdf`: the main results for clinical readers, in plain language, with technical terms in linked notes;
- `walking_validation_brief.pdf`: the brief and the clinical version joined, the clinical version as the brief's appendix, with a bookmark for each part. **This is the file to send.**

The brief's author and contact line comes from `brief.local.yml`, which is git-ignored. Copy `brief.local.example.yml` to `brief.local.yml` and fill it in. Without the file, the brief prints a placeholder. After filling it in, re-render and check that page 1 still ends with the appendix pointer: a long author line can push it onto page 2.

Run `uv run oai check-egress <results>/walking_validation/report` before sending.
