# genetics_progression

Per-genotype progression analysis (plan §10–12). Genotypes are controlled-access (dbGaP GeCKO, phs000955) and never leave the enclave.

| Step | Stage | Does |
|---|---|---|
| `frame` (`build_frame.py`) | local | Knee × visit phenotype frame: `ID, SIDE, visit, time_years, age0, sex, bmi0` (+ outcomes as they are implemented) |
| `models` (`models.R`) | enclave | Bridge-file join to genotype dosages; §11 models; egress-checked aggregate tables |

```bash
oai export genetics_progression   # on the laptop -> OAI_WORK_DIR/bundles/*.tar.gz
bash run.sh                       # in the enclave, inside $OAI_GENO_DIR
```

Open question: dbGaP lists the genotypes as hg37; the plan assumed hg18 + liftover. Confirm on receipt.

Status: stub.
