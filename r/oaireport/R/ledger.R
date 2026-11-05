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
#' @param exclude_prefixes Keys starting with any of these are left out of the status tables, and
#'   the counts in the headings and the summary line follow what is left. The Variants table stays
#'   whole, since it lists variants, not keys.
#' @return The lines, to be written with `cat(lines, sep = "\n")`.
ledger_markdown <- function(path = "ASSUMPTIONS.md", widths = NULL, exclude_prefixes = character()) {
  ledger <- readLines(path, warn = FALSE)
  ledger <- ledger[!grepl("^# |^<!--", ledger)]
  if (length(exclude_prefixes)) ledger <- ledger_without(ledger, exclude_prefixes)
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

# The ledger without the rows of keys starting with a prefix, its counts following what is left.
ledger_without <- function(lines, prefixes) {
  counted <- "^## ([A-Za-z]+) \\(([0-9]+)\\)$"
  summary_line <- grepl("^[0-9]+ [a-z]+( \u00b7 [0-9]+ [a-z]+)*$", lines)
  keys <- ifelse(grepl("^\\| *`", lines), sub("^\\| *`([^`]*)`.*$", "\\1", lines), NA_character_)
  section_starts <- grep("^## ", lines)
  section <- findInterval(seq_along(lines), section_starts)
  drop <- rep(FALSE, length(lines))
  for (i in seq_along(section_starts)) {
    heading <- lines[section_starts[i]]
    if (!grepl(counted, heading)) next
    here <- section == i & !is.na(keys) &
      Reduce(`|`, lapply(prefixes, function(prefix) startsWith(ifelse(is.na(keys), "", keys), prefix)))
    drop <- drop | here
    status <- sub(counted, "\\1", heading)
    left <- as.integer(sub(counted, "\\2", heading)) - sum(here)
    lines[section_starts[i]] <- sprintf("## %s (%d)", status, left)
    lines[summary_line] <- sub(paste0("[0-9]+ ", tolower(status)), paste(left, tolower(status)),
                               lines[summary_line])
  }
  lines[!drop]
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
