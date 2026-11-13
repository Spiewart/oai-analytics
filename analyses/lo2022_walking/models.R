# Step `models`: knee-level GEE logistic models (Lo 2022 Table 2 and Supplementary Tables 2-3).
# Knees are clustered on participant; settings come from assumptions.toml.

A <- oaimodels::assumptions()
outcomes <- c("new_pain", "kl_worse", "jsn_worse", "improved_pain")
base_covariates <- A[["model.covariates"]]
frame <- oaimodels::read_frame(required = unique(c("ID", "walker", base_covariates, outcomes)))
out_dir <- Sys.getenv("OAI_RESULTS_DIR")
kl_term <- if (identical(A[["model.kl_covariate"]], "factor")) "factor(kl0)" else "kl0"
covariates <- sub("^kl0$", kl_term, base_covariates)
formulas <- list(or_unadj = "walker", or_adj = paste(c("walker", covariates), collapse = " + "))

fit_or <- function(d, rhs) {
  oaimodels::fit_knee_gee(d, rhs, corstr = A[["model.corstr"]])[c("or", "lo", "hi")]
}

metrics <- oaimodels::metrics_recorder()
rows <- list()
for (o in outcomes) {
  d <- frame[!is.na(frame[[o]]), unique(c("ID", "walker", base_covariates, o))]
  names(d)[names(d) == o] <- "y"
  d$y <- as.integer(d$y)
  d <- d[stats::complete.cases(d), ]
  d <- d[order(d$ID), ]
  for (g in c("walkers", "nonwalkers")) {
    part <- d[d$walker == (g == "walkers"), ]
    metrics$put(sprintf("t2.%s.%s.events", o, g), sum(part$y))
    metrics$put(sprintf("t2.%s.%s.n", o, g), nrow(part))
  }
  for (name in names(formulas)) {
    est <- fit_or(d, formulas[[name]])
    metrics$put_est(sprintf("t2.%s.%s", o, name), est)
    rows[[length(rows) + 1]] <- data.frame(
      outcome = o, model = name, n = nrow(d), events = sum(d$y),
      or = est[["or"]], lo = est[["lo"]], hi = est[["hi"]]
    )
  }
}
oaimodels::write_rows(rows, "table2", out_dir)
metrics$write(out_dir)
cat("Table 2 written to", out_dir, "\n")
