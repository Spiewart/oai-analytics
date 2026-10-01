#' Knee-level logistic GEE clustered on participant (the Lo 2022 Table 2 model)
#'
#' @param data Knee rows with the outcome, `id` and the right-hand-side variables.
#' @param rhs Right-hand side, e.g. "walker + age + sex + factor(kl0)".
#' @param outcome Binary (0/1) outcome column.
#' @param term Coefficient whose odds ratio is returned.
#' @param corstr Working correlation (geepack).
#' @param id Cluster column; rows are ordered by it before fitting.
#' @return Named numeric: or, lo, hi (95% Wald), log_or, se.
fit_knee_gee <- function(data, rhs, outcome = "y", term = "walkerTRUE",
                         corstr = "exchangeable", id = "ID") {
  if (!requireNamespace("geepack", quietly = TRUE)) {
    stop("fit_knee_gee() needs the geepack package", call. = FALSE)
  }
  data <- data[order(data[[id]]), , drop = FALSE]
  data$.cluster <- data[[id]]
  model <- geepack::geeglm(stats::as.formula(paste(outcome, "~", rhs)), id = .cluster,
                           data = data, family = stats::binomial, corstr = corstr)
  coefs <- summary(model)$coefficients
  if (!term %in% rownames(coefs)) {
    stop("term ", term, " is not in the model (", paste(rownames(coefs), collapse = ", "), ")",
         call. = FALSE)
  }
  b <- coefs[term, "Estimate"]
  se <- coefs[term, "Std.err"]
  c(or = exp(b), lo = exp(b - 1.96 * se), hi = exp(b + 1.96 * se), log_or = b, se = se)
}
