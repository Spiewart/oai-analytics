#' The columns a model needs: the outcome and every variable in its right-hand side
#'
#' `factor(kl)`, `offset(log(span))` and `crep0 * age` contribute `kl`, `span`, `crep0` and `age`.
#'
#' @param rhs Right-hand side as one string or a character vector of terms (joined with `+`).
#' @param outcome Outcome column.
model_needs <- function(rhs, outcome = "event") {
  rhs <- paste(rhs, collapse = " + ")
  unique(c(outcome, all.vars(stats::as.formula(paste("~", rhs)))))
}

#' Each model's fitting sample: complete cases of what it needs, ordered by `id`
#'
#' `sample = "per_model"` fits each model on the complete cases of its own terms, so an
#' unadjusted model keeps rows missing a covariate. `"common"` fits every model on the complete
#' cases of all of them, so the unadjusted and adjusted estimates share one sample. Each analysis
#' records its rule as the ledger item `model.sample`.
#'
#' @param d Rows to fit.
#' @param models Named list (or named character vector) of right-hand sides.
#' @param sample "per_model" or "common".
#' @param outcome Outcome column.
#' @param id Cluster column the rows are ordered by (a stable order, so rows already ordered by
#'   `id` and then by period keep that order).
#' @return Named list of data.frames, one per model.
model_samples <- function(d, models, sample = c("per_model", "common"), outcome = "event",
                          id = "ID") {
  sample <- match.arg(sample)
  needs <- lapply(models, model_needs, outcome = outcome)
  if (sample == "common") needs[] <- list(unique(unlist(needs, use.names = FALSE)))
  lapply(needs, function(v) {
    dd <- d[stats::complete.cases(d[, v, drop = FALSE]), , drop = FALSE]
    dd[order(dd[[id]]), , drop = FALSE]
  })
}

#' Events in each level of `variable`
#'
#' @param levels All levels to report, in order; a level with no rows counts 0. NULL reports
#'   the levels `tapply` finds (an unused factor level is NA).
level_events <- function(d, variable, outcome = "event", levels = NULL) {
  counts <- tapply(as.numeric(d[[outcome]]), d[[variable]], sum)
  if (is.null(levels)) return(counts)
  out <- stats::setNames(as.numeric(counts[as.character(levels)]), levels)
  out[is.na(out)] <- 0
  out
}

#' Which levels have too few events to estimate (fewer than `min_events`, or none counted)
#'
#' The ledger item `model.min_events` sets the threshold. A level that is too sparse is written
#' as NA rather than fitted; when the reference level is too sparse the whole term is NA.
sparse_levels <- function(counts, min_events) is.na(counts) | counts < min_events
