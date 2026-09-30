# Reference documents

Literature syntheses that define the analyses in this repo. The `.docx` files are the originals; the `.md` copies are generated with `uv run scripts/docx_to_md.py` for reading and diffing on GitHub. Regenerate after editing a `.docx`.

| Document | What it covers |
|---|---|
| [Dataset table structure](oai-dataset-table-structure.md) | Table families, visit-code mapping, keys (`ID`, `SIDE`) and record grain of the public OAI release |
| [Progression definitions review](oai-progression-definitions-review.md) | Radiographic, MRI, symptomatic, functional and hard-endpoint progression definitions used with OAI |
| [Progression definition crosswalk](oai-progression-definition-crosswalk.md) | Each progression definition mapped to its OAI table stem and variables |
| [Activity agreement analysis plan](oai-activity-agreement-analysis-plan.md) | PASE vs. accelerometer agreement (Aims 1–3) and the per-genotype progression arm (§10–12) |

Variable names in these documents are representative; verify them against the release's `*_Contents.pdf` files in `OAI_DATA_DIR`.
