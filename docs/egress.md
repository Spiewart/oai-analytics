# Egress: what may leave the enclave

`oai check-egress DIR` runs at the end of every bundle's `run.sh` and should be run on
anything you intend to copy out of the secure enclave. It is a safety net, not a
substitute for looking at your results.

## What blocks release (always)

Individual-level data and identifiers. These are what the NDA and dbGaP data use
certifications prohibit, so these checks always fail the run:

- columns named like identifiers: `ID`, `IID`, `FID`, `src_subject_id`, `SUBJID`,
  `subject_id`, `sample_id`, `SAMPID`, `dbGaP_Subject_ID`, `participant_id` (any case);
- values or column headers that look like OAI participant IDs (a 7-digit number starting
  with 9, including forms like `ID_ID` or `OAI` + ID). Decimal fractions don't match,
  and columns or JSON keys listed in `ignore_id_pattern_columns` (e.g. GWAS base-pair
  `POS`, `run_info.json`'s `git_commit`) are skipped;
- file types the check cannot read (it fails closed). Figures (PNG/PDF/JPG) are listed
  for manual review, and HTML/SVG are both scanned and listed, because they can embed data.

## Small cells: advisory by default

A count column (`n`, `count`, `n_*`, `*_n`, `*_count`) holding values from 1 to
`min_cell - 1` is reported. By default it is a **warning** that does not block release.

Why advisory:

- Neither the OAI/NIMH Data Archive terms nor dbGaP set a minimum cell size
  ([NDA Data Use Certification](https://s3.amazonaws.com/nda.nih.gov/cms/prod/NDA-Data-Access-Request-DUC-FINAL.pdf),
  [NDA policy](https://s3.amazonaws.com/nda.nih.gov/Documents/NIMH+Data+Archive+Policy.pdf)).
- NIH treats aggregate genomic summary results as releasable with unrestricted access
  for most studies ([NOT-OD-19-023](https://grants.nih.gov/grants/guide/notice-files/NOT-OD-19-023.html)).
- The OAI is a de-identified public resource, and strict suppression (e.g. CMS's
  threshold of 11) would routinely block standard reporting such as rare-genotype counts.

Settings (`config/oai.toml`):

```toml
[egress]
small_cell = "warn"  # off | warn | fail
min_cell = 5         # counts 1..min_cell-1 are flagged
ignore_id_pattern_columns = ["POS", "BP", "position", "git_commit"]
```

Switch to `small_cell = "fail"` (and raise `min_cell`) if a journal, collaborator or
future data use agreement requires suppression. `--min-cell N` overrides the threshold
for a single run.
