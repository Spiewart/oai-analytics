#!/usr/bin/env bash
# Run the enclave stage of analysis "@@ANALYSIS@@" from this bundle.
# Needs: python3 >= 3.11, R >= 4.2 with renv (if env/renv.lock exists), sha256sum,
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
  if [ -d vendor/r ]; then export RENV_CONFIG_REPOS_OVERRIDE="file://$HERE/vendor/r"; fi
  Rscript -e 'renv::restore(project = ".", lockfile = "env/renv.lock", library = ".rlib", prompt = FALSE)'
  R CMD INSTALL --no-test-load --library=.rlib code/oaimodels_*.tar.gz
  export R_LIBS="$HERE/.rlib"
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
