# Enclave bundle: @@ANALYSIS@@

This bundle runs the `enclave` stage of the `@@ANALYSIS@@` analysis next to
controlled-access dbGaP genotype data (GeCKO, phs000955). It contains no genotype data.

## Contents

| Path | What |
|---|---|
| `code/` | `oai` wheel, `oaimodels` R source package, the analysis folder |
| `env/` | `requirements.txt` (hash-pinned), `renv.lock` |
| `data/` | phenotype frame, restricted to the columns declared in `analysis.toml` |
| `config/oai.toml` | project config (visit map, egress rules) |
| `SHA256SUMS`, `MANIFEST.json` | checksums; git commit, row/column counts, timestamp |

## Run

1. Transfer the `.tar.gz` using your institution's approved method.
2. Extract it **inside** `$OAI_GENO_DIR`, so every intermediate lives in the directory destroyed at close-out.
3. `export OAI_GENO_DIR=/secure/path/to/geno` then `bash run.sh`.
4. Only the results directory, and only after `oai check-egress` passes, may leave the enclave. Review figures listed as `REVIEW` by eye.

## Offline enclaves

If the enclave has no internet access, populate `vendor/` on a connected Linux x86_64 machine before transfer:

```bash
# Python wheels
pip download -r env/requirements.txt --platform manylinux2014_x86_64 \
  --python-version 3.11 --only-binary=:all: -d vendor/wheels
# R sources as a local CRAN-like repo (renv honors RENV_CONFIG_REPOS_OVERRIDE)
Rscript -e 'pkgs <- c("renv", names(renv::lockfile_read("env/renv.lock")$Packages));
  dir.create("vendor/r/src/contrib", recursive = TRUE);
  download.packages(pkgs, destdir = "vendor/r/src/contrib", type = "source",
                    repos = "https://cloud.r-project.org");
  tools::write_PACKAGES("vendor/r/src/contrib", type = "source")'
```
`SHA256SUMS` does not need regenerating: it covers only the original bundle files, not `vendor/`.

## Containers (alternative)

Where Apptainer is available, build a `linux/amd64` image on a connected machine
(`docker buildx build --platform linux/amd64 ...` from a `rocker/r-ver` base with Python ≥ 3.11),
convert it with `apptainer build image.sif docker-archive://image.tar`, and run `run.sh` inside it.

## Close-out

At project termination, destroy `$OAI_GENO_DIR` (including this bundle, `.venv`, `.rlib`,
work and results) following your institution's media-sanitization procedure, per the NIH
Security Best Practices for Controlled-Access Data.
