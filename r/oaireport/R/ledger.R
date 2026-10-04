# The assumptions ledger (ASSUMPTIONS.md, written by `oai assumptions NAME --write`) for a report.

#' The assumptions ledger as Markdown lines for a `results: asis` chunk
#'
#' Drops the title and the generated-by comment (the report has its own headings) and makes the
#' keys wrap in narrow table cells: any span in backticks that looks like an identifier (a letter,
#' then letters, digits, "_", ".", "{" or "}") becomes plain text, with break points after "." and
#' "_". That covers keys, identifiers named in a source, and identifier-like values such as
#' `walker_requires_amount`, `mean` or `boot`, which lose their code formatting. Other values, such
#' as numbers, JSON or `non-walker` (a hyphen), stay code spans, untouched. The key of a variant's
#' `key = value` span gets the same break points while the span stays code.
#'
#' Pandoc takes a pipe table's column widths from the dashes of its separator row. `widths` sets
#' them: each table's separator row is rewritten to dashes in the proportions given (at least
#' three a column; alignment colons are not kept). A table whose column count differs from the
#' widths is an error, as is `widths` with no table to apply to, so a ledger whose layout changes
#' fails loudly instead of silently losing its widths.
#'
#' @param path The ledger file; `ASSUMPTIONS.md` in the report's folder by default.
#' @param widths Relative column widths: `NULL` (leave the separator rows as written), a numeric
#'   vector (every table must have that many columns), or a list of numeric vectors of different
#'   lengths (each table takes the vector whose length is its column count, for a ledger whose
#'   tables differ in shape: the status tables and the Variants table).
#' @return The lines, to be written with `cat(lines, sep = "\n")`.
ledger_markdown <- function(path = "ASSUMPTIONS.md", widths = NULL) {
  ledger <- readLines(path, warn = FALSE)
  ledger <- ledger[!grepl("^# |^<!--", ledger)]
  identifiers <- gregexpr("`[A-Za-z][A-Za-z0-9_.{}]*`", ledger)
  regmatches(ledger, identifiers) <- lapply(regmatches(ledger, identifiers), function(x) {
    breakable_ids(gsub("`", "", x))
  })
  sets <- gregexpr("`[A-Za-z][A-Za-z0-9_.{}]* = [^`]*`", ledger)
  regmatches(ledger, sets) <- lapply(regmatches(ledger, sets), function(x) {
    vapply(x, function(span) {
      part <- regmatches(span, regexec("^`([^ ]+)( = .*)`$", span))[[1]]
      paste0("`", breakable_ids(part[2]), part[3], "`")
    }, character(1), USE.NAMES = FALSE)
  })
  if (is.null(widths)) ledger else ledger_widths(ledger, widths)
}

# Rewrite each pipe table's separator row (|---|---|) to dashes in the proportions of `widths`
ledger_widths <- function(lines, widths) {
  shapes <- if (is.list(widths)) widths else list(widths)
  if (!length(shapes) || !all(vapply(shapes, function(w) {
    is.numeric(w) && length(w) > 0 && all(is.finite(w)) && all(w > 0)
  }, logical(1)))) {
    stop("ledger_markdown(): widths must be positive numbers (or a list of vectors of them)", call. = FALSE)
  }
  if (anyDuplicated(lengths(shapes))) {
    stop("ledger_markdown(): the vectors in a list of widths must have different lengths", call. = FALSE)
  }
  is_separator <- grepl("^\\|(\\s*:?-{3,}:?\\s*\\|)+\\s*$", lines)
  if (!any(is_separator)) stop("ledger_markdown(): widths given, but the ledger has no table", call. = FALSE)
  for (i in which(is_separator)) {
    columns <- lengths(regmatches(lines[i], gregexpr("|", lines[i], fixed = TRUE))) - 1L
    shape <- shapes[lengths(shapes) == columns]
    if (!length(shape)) {
      stop(sprintf("ledger_markdown(): a table has %d columns but widths gives %s (no entry of length %d)",
                   columns, paste(unique(lengths(shapes)), collapse = " or "), columns), call. = FALSE)
    }
    lines[i] <- paste0("|", paste(strrep("-", separator_dashes(shape[[1]])), collapse = "|"), "|")
  }
  lines
}

# Dashes for relative widths: the fewest (three or more for the narrowest column) that keep every
# column within 2% of its share, so 5:5:9:4 stays 5, 5, 9, 4
separator_dashes <- function(widths) {
  relative <- widths / min(widths)
  for (scale in 3:100) {
    dashes <- round(relative * scale)
    if (all(abs(dashes / (relative * scale) - 1) <= 0.02)) return(as.integer(dashes))
  }
  as.integer(round(relative * 100))
}
