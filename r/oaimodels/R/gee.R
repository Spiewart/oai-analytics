#' Knee-level logistic GEE clustered on participant (the Lo 2022 Table 2 model)
#'
#' @param data Knee rows with the outcome, `id` and the right-hand-side variables.
#' @param rhs Right-hand side, e.g. "walker + age + sex + factor(kl0)".
#' @param outcome Binary outcome column: 0/1 or logical (missing values are dropped by the
#'   model frame).
#' @param term Coefficient whose odds ratio is returned.
#' @param corstr Working correlation (geepack).
#' @param id Cluster column, with no missing values; rows are ordered by it before fitting.
#' @return Named numeric: or, lo, hi (95% Wald), log_or, se.
fit_knee_gee <- function(data, rhs, outcome = "y", term = "walkerTRUE",
                         corstr = "exchangeable", id = "ID") {
  if (!requireNamespace("geepack", quietly = TRUE)) {
    stop("fit_knee_gee() needs the geepack package", call. = FALSE)
  }
  for (column in c(outcome, id)) {
    if (!column %in% names(data)) stop("fit_knee_gee(): data has no column ", column, call. = FALSE)
  }
  missing_id <- sum(is.na(data[[id]]))
  if (missing_id) {
    stop("fit_knee_gee(): ", missing_id, " rows have no ", id, "; drop them before fitting",
         call. = FALSE)
  }
  y <- data[[outcome]]
  if (!(is.numeric(y) || is.logical(y)) || !all(y[!is.na(y)] %in% c(0, 1))) {
    stop("fit_knee_gee(): outcome ", outcome, " must be 0/1", call. = FALSE)
  }
  data <- data[order(data[[id]]), , drop = FALSE]
  # geeglm() reads `id` from `data`, so the cluster gets a column name no existing column has
  cluster <- make.unique(c(names(data), ".cluster"))[ncol(data) + 1L]
  data[[cluster]] <- data[[id]]
  model <- eval(bquote(geepack::geeglm(.(stats::as.formula(paste(outcome, "~", rhs))),
                                       id = .(as.name(cluster)), data = data,
                                       family = stats::binomial, corstr = corstr)))
  coefs <- summary(model)$coefficients
  if (!term %in% rownames(coefs)) {
    stop("term ", term, " is not in the model (", paste(rownames(coefs), collapse = ", "), ")",
         call. = FALSE)
  }
  b <- coefs[term, "Estimate"]
  se <- coefs[term, "Std.err"]
  c(or = exp(b), lo = exp(b - 1.96 * se), hi = exp(b + 1.96 * se), log_or = b, se = se)
}
