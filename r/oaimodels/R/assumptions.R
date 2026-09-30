#' Resolved assumptions for the current run
#'
#' `oai run` writes `assumptions.resolved.json` and points `OAI_ASSUMPTIONS` at it.
#' @param path Resolved JSON file.
#' @return Named list: assumption key -> value.
assumptions <- function(path = Sys.getenv("OAI_ASSUMPTIONS")) {
  if (!nzchar(path) || !file.exists(path)) {
    stop("No resolved assumptions found: run this step via `oai run`", call. = FALSE)
  }
  resolved <- jsonlite::fromJSON(path, simplifyVector = TRUE)
  lapply(resolved$assumptions, function(entry) entry$value)
}
