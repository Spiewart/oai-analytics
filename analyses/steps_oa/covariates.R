# Covariate sets for steps_oa's models, from the ledger: model.covariates for m1, and for m2
# also model.covariates_2_knee (knee-level forward models: the knee's KL grade and WOMAC pain at
# 48 months) or model.covariates_2_person (person-level reverse models: the higher KL grade and
# the worse knee's pain). `wear_hr` becomes one column per device wave the model spans.
covariates_for <- function(A, model, waves, level = c("knee", "person")) {
  level <- match.arg(level)
  base <- A[["model.covariates"]]
  wear <- if ("wear_hr" %in% base) sprintf("wear_hr_%s", waves) else character()
  out <- c(setdiff(base, "wear_hr"), wear)
  if (identical(model, "m2")) out <- c(out, A[[sprintf("model.covariates_2_%s", level)]])
  out
}
