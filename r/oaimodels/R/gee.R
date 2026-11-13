#' Knee-level logistic GEE clustered on participant (the Lo 2022 Table 2 model)
#'
#' @param data Knee rows with the outcome, `id` and the right-hand-side variables.
#' @param rhs Right-hand side, e.g. "walker + age + sex + factor(kl0)".
#' @param outcome Binary outcome column: 0/1 or logical (missing values are dropped by the
#'   model frame).
#' @param term Coefficient whose odds ratio is returned.
#' @param corstr Working correlation (geepack).
#' @param id Cluster column of any type, with no missing values; rows are ordered by it before
#'   fitting.
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
  model <- fit_cluster_gee(data, rhs, outcome, stats::binomial, corstr, id)
  coefs <- summary(model)$coefficients
  if (!term %in% rownames(coefs)) {
    stop("term ", term, " is not in the model (", paste(rownames(coefs), collapse = ", "), ")",
         call. = FALSE)
  }
  b <- coefs[term, "Estimate"]
  se <- coefs[term, "Std.err"]
  c(or = exp(b), lo = exp(b - 1.96 * se), hi = exp(b + 1.96 * se), log_or = b, se = se)
}

#' A GEE clustered on `id`, returned as the geeglm fit
#'
#' Rows are ordered by `id` (a stable order, so rows ordered by `id` and then period keep that
#' order) and the cluster is an integer column: geepack finds clusters from
#' diff(as.numeric(id)), so a character ID that does not parse as a number becomes NA and every
#' such row joins one cluster, with only a coercion warning and a wrong (often near-zero or NaN)
#' standard error.
#'
#' @param data Rows with the outcome, `id` and the right-hand-side variables.
#' @param rhs Right-hand side as one string or a character vector of terms (joined with `+`).
#' @param outcome Outcome column.
#' @param family A family object or function: `stats::binomial` (logit),
#'   `stats::binomial(link = "cloglog")` (grouped-time proportional hazards on a periods frame),
#'   `stats::gaussian()`.
#' @param corstr Working correlation (geepack).
#' @param id Cluster column, with no missing values.
fit_cluster_gee <- function(data, rhs, outcome, family = stats::binomial, corstr = "exchangeable",
                            id = "ID") {
  if (!requireNamespace("geepack", quietly = TRUE)) {
    stop("fit_cluster_gee() needs the geepack package", call. = FALSE)
  }
  data <- data[order(data[[id]]), , drop = FALSE]
  # geeglm() reads `id` from `data`, so the cluster gets a column name no existing column has.
  cluster <- make.unique(c(names(data), ".cluster"))[ncol(data) + 1L]
  data[[cluster]] <- match(data[[id]], unique(data[[id]]))
  f <- stats::as.formula(paste(outcome, "~", paste(rhs, collapse = " + ")))
  eval(bquote(geepack::geeglm(.(f), id = .(as.name(cluster)), data = data, family = .(family),
                              corstr = .(corstr))))
}

#' Discrete-time terms for a frame with one row per person (or knee) and follow-up interval
#'
#' An intercept per interval (`factor(<interval>)`, left out when the frame has one interval) and,
#' with `span`, `offset(log(<span>))`: an interval covering two visits carries twice one visit's
#' cumulative hazard under a complementary log-log link. Fit them with `fit_cluster_gee()`; the
#' link is the analysis's ledger choice (steps_oa `incidence.link`; crepitus_soa_longterm
#' `model.link`).
discrete_time_terms <- function(d, interval, span = NULL) {
  as.character(c(if (length(unique(d[[interval]])) >= 2) sprintf("factor(%s)", interval),
                 if (!is.null(span)) sprintf("offset(log(%s))", span)))
}
