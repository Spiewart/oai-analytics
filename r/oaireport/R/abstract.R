#' Character budget for a conference abstract
#'
#' Counts each named section's characters as a submission portal does: spaces included, and a
#' symbol such as ≥, – or ρ counted once. Each image (a table counts as one) is charged
#' `per_image`, the most a portal deducts for it. Returns a data.frame with columns `part` and
#' `characters`: one row per section, an images row when `images > 0`, then Total, Limit and
#' Margin. Stops, naming the overage, when the total is over `limit`.
char_budget <- function(sections, images = 0, per_image = 560, limit = 5000) {
  if (!length(sections)) stop("char_budget(): give at least one section", call. = FALSE)
  if (is.null(names(sections)) || any(!nzchar(names(sections)))) {
    stop("char_budget(): every section must be named", call. = FALSE)
  }
  if (anyDuplicated(names(sections))) stop("char_budget(): section names must be unique", call. = FALSE)
  if (is.list(sections)) {
    if (!all(vapply(sections, function(x) is.character(x) && length(x) == 1, logical(1)))) {
      stop("char_budget(): each section must be one string", call. = FALSE)
    }
    sections <- unlist(sections)
  }
  if (!is.character(sections)) stop("char_budget(): sections must be character strings", call. = FALSE)
  if (any(is.na(sections))) stop("char_budget(): sections must not be missing (NA)", call. = FALSE)
  whole <- function(x) is.numeric(x) && length(x) == 1 && !is.na(x) && x >= 0 && x == round(x)
  if (!whole(images)) stop("char_budget(): images must be a whole number, 0 or more", call. = FALSE)
  if (!whole(per_image)) stop("char_budget(): per_image must be a whole number, 0 or more", call. = FALSE)
  if (!whole(limit) || limit == 0) stop("char_budget(): limit must be a whole number above 0", call. = FALSE)
  counts <- nchar(sections, type = "chars")
  parts <- names(sections)
  if (images > 0) {
    counts <- c(counts, images * per_image)
    parts <- c(parts, sprintf("Images (%d × %d)", as.integer(images), as.integer(per_image)))
  }
  total <- sum(counts)
  if (total > limit) {
    stop(sprintf("char_budget(): %d characters, %d over the limit of %d", as.integer(total),
                 as.integer(total - limit), as.integer(limit)), call. = FALSE)
  }
  data.frame(part = c(parts, "Total", "Limit", "Margin"),
             characters = as.integer(c(counts, total, limit, limit - total)))
}
