# Covariate sets for crepitus_activity's models, from the ledger (model.covariates, and
# model.covariates_2 for m2). `wear_hr` becomes one column per device wave the model spans, so a
# model with activity at both 48 and 72 months adjusts for wear time at both.
covariates_for <- function(A, model, waves) {
  base <- A[["model.covariates"]]
  wear <- if ("wear_hr" %in% base) sprintf("wear_hr_%s", waves) else character()
  out <- c(setdiff(base, "wear_hr"), wear)
  if (identical(model, "m2")) out <- c(out, A[["model.covariates_2"]])
  out
}
