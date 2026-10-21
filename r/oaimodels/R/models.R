#' Confounder block shared by every model in the analysis plan (section 11)
#' @param n_pcs Number of ancestry principal components.
default_covariates <- function(n_pcs = 10) {
  c("age0", "sex", "bmi0", if (n_pcs > 0) paste0("PC", seq_len(n_pcs)))
}

not_implemented <- function(section) {
  stop("Not implemented yet: see docs/reference/oai-activity-agreement-analysis-plan.md, section ",
       section, call. = FALSE)
}

#' Continuous progression: lmer(outcome ~ time * exposure + covariates + (time | ID/SIDE)) (11.1)
fit_progression_lmm <- function(frame, outcome, exposure = "geno_add",
                                covariates = default_covariates()) {
  not_implemented("11.1")
}

#' KL-grade transition: clmm(kl ~ time * exposure + covariates + (1 | ID/SIDE)) (11.2)
fit_kl_clmm <- function(frame, outcome = "kl_grade", exposure = "geno_add",
                        covariates = default_covariates()) {
  not_implemented("11.2")
}

#' Binary progressor: geeglm(progressor ~ exposure + covariates, id = ID, exchangeable) (11.3)
fit_progressor_gee <- function(frame, outcome = "progressor", exposure = "geno_add",
                               covariates = default_covariates()) {
  not_implemented("11.3")
}

#' KL4/TKR: coxph(Surv(time, event) ~ exposure + covariates + frailty(ID)) (11.4)
fit_tkr_cox <- function(frame, time = "time_to_event", event = "event", exposure = "geno_add",
                        covariates = default_covariates()) {
  not_implemented("11.4")
}

#' Logistic regression with one row per person (Lo 2018 four-year models)
#'
#' @param data Rows with the outcome and the right-hand-side variables.
#' @param rhs Right-hand side, e.g. "factor(crep0) + age + sex + bmi".
#' @param outcome Binary outcome column: 0/1 or logical.
#' @param term Coefficient whose odds ratio is returned.
#' @return Named numeric: or, lo, hi (95% Wald), log_or, se.
fit_logit <- function(data, rhs, outcome = "y", term) {
  if (!outcome %in% names(data)) stop("fit_logit(): data has no column ", outcome, call. = FALSE)
  model <- stats::glm(stats::as.formula(paste(outcome, "~", rhs)), data = data,
                      family = stats::binomial)
  coefs <- summary(model)$coefficients
  if (!term %in% rownames(coefs)) {
    stop("term ", term, " is not in the model (", paste(rownames(coefs), collapse = ", "), ")",
         call. = FALSE)
  }
  b <- coefs[term, "Estimate"]
  se <- coefs[term, "Std. Error"]
  c(or = exp(b), lo = exp(b - 1.96 * se), hi = exp(b + 1.96 * se), log_or = b, se = se)
}
