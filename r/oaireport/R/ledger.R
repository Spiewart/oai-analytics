# The assumptions ledger (ASSUMPTIONS.md, written by `oai assumptions NAME --write`) for a report.

zero_width_space <- "​"

# Zero-width break points after "." and "_", so a long identifier wraps inside a narrow table cell.
breakable_key <- function(x) gsub("([._])", paste0("\\1", zero_width_space), x)

#' The assumptions ledger as Markdown lines for a `results: asis` chunk
#'
#' Drops the title and the generated-by comment (the report has its own headings) and makes the
#' keys wrap in narrow table cells: an identifier in backticks becomes plain text with break
#' points after "." and "_", and the key of a variant's `key = value` span gets the same break
#' points while the span stays code. Values are left as they are.
#'
#' @param path The ledger file; `ASSUMPTIONS.md` in the report's folder by default.
#' @return The lines, to be written with `cat(lines, sep = "\n")`.
ledger_markdown <- function(path = "ASSUMPTIONS.md") {
  ledger <- readLines(path, warn = FALSE)
  ledger <- ledger[!grepl("^# |^<!--", ledger)]
  identifiers <- gregexpr("`[A-Za-z][A-Za-z0-9_.{}]*`", ledger)
  regmatches(ledger, identifiers) <- lapply(regmatches(ledger, identifiers), function(x) {
    breakable_key(gsub("`", "", x))
  })
  sets <- gregexpr("`[A-Za-z][A-Za-z0-9_.{}]* = [^`]*`", ledger)
  regmatches(ledger, sets) <- lapply(regmatches(ledger, sets), function(x) {
    vapply(x, function(span) {
      part <- regmatches(span, regexec("^`([^ ]+)( = .*)`$", span))[[1]]
      paste0("`", breakable_key(part[2]), part[3], "`")
    }, character(1), USE.NAMES = FALSE)
  })
  ledger
}
