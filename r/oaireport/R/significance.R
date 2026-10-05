#' Whether a 95% CI excludes a null value
#'
#' TRUE when both limits sit strictly on one side of `null` (0 for differences and correlations,
#' 1 for odds ratios); FALSE when a limit equals the null or is missing. Recycled to a common
#' length.
ci_excludes <- function(lo, hi, null = 0) {
  if (!is.numeric(lo) && !all(is.na(lo)) || !is.numeric(hi) && !all(is.na(hi)) || !is.numeric(null)) {
    stop("ci_excludes(): lo, hi and null must be numeric", call. = FALSE)
  }
  n <- max(length(lo), length(hi))
  lo <- rep_len(as.numeric(lo), n); hi <- rep_len(as.numeric(hi), n)
  !is.na(lo) & !is.na(hi) & (lo > null | hi < null)
}
