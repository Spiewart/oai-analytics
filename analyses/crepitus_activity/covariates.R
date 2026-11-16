# Covariate sets for crepitus_activity's models, from the ledger (model.covariates, and
# model.covariates_2 for m2), with wear time at each device wave the model spans.
covariates_for <- function(A, model, waves) oaimodels::device_covariates(A, model, waves)
