#!/usr/bin/env bash
# Run the enclave stage of analysis "@@ANALYSIS@@" from this bundle.
# Needs: python3 >= 3.11, R >= 4.4 (ideally the lockfile's version) if env/renv.lock exists, sha256sum,
# and OAI_GENO_DIR pointing at the controlled-access genotype directory.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANALYSIS="@@ANALYSIS@@"
cd "$HERE"

: "${OAI_GENO_DIR:?Set OAI_GENO_DIR to the controlled-access genotype directory}"

echo "==> Verifying bundle checksums"
sha256sum --quiet -c SHA256SUMS

echo "==> Python environment"
PIP_OPTS=()
if [ -d vendor/wheels ]; then PIP_OPTS=(--no-index --find-links vendor/wheels); fi
python3 -m venv .venv
.venv/bin/pip install --quiet ${PIP_OPTS[@]+"${PIP_OPTS[@]}"} -r env/requirements.txt
.venv/bin/pip install --quiet ${PIP_OPTS[@]+"${PIP_OPTS[@]}"} --no-deps code/*.whl

if [ -f env/renv.lock ]; then
  echo "==> R packages"
  mkdir -p .rlib
  export R_LIBS="$HERE/.rlib"
  export OAI_R_REPOS="https://cloud.r-project.org"
  if [ -d vendor/r ]; then
    export OAI_R_REPOS="file://$HERE/vendor/r"
    export RENV_CONFIG_REPOS_OVERRIDE="$OAI_R_REPOS"
  fi
  # Bootstrap renv (from vendor/r when offline), then warn if R differs from the lockfile's.
  Rscript -e 'if (!requireNamespace("renv", quietly = TRUE)) install.packages("renv", repos = Sys.getenv("OAI_R_REPOS"), lib = ".rlib")'
  Rscript -e 'want <- renv::lockfile_read("env/renv.lock")$R$Version
    have <- paste(R.version$major, R.version$minor, sep = ".")
    if (!identical(package_version(have)[, 1:2], package_version(want)[, 1:2]))
      warning(sprintf("R %s here but the lockfile was built with R %s; some packages may need compiling", have, want), call. = FALSE)'
  Rscript -e 'renv::restore(project = ".", lockfile = "env/renv.lock", library = ".rlib", prompt = FALSE)'
  R CMD INSTALL --no-test-load --library=.rlib code/oaimodels_*.tar.gz
fi

export OAI_CONFIG="$HERE/config/oai.toml"
export OAI_ANALYSES_DIR="$HERE/code/analyses"
export OAI_FRAME_DIR="$HERE/data"
export OAI_WORK_DIR="${OAI_WORK_DIR:-$OAI_GENO_DIR/work}"
export OAI_RESULTS_DIR="${OAI_RESULTS_DIR:-$OAI_GENO_DIR/results}"

echo "==> Running enclave steps"
.venv/bin/oai run "$ANALYSIS" --stage enclave

echo "==> Egress check"
.venv/bin/oai check-egress "$OAI_RESULTS_DIR/$ANALYSIS"
echo "Done. Only files that passed the egress check may leave the enclave."
