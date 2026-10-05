# Verdict tables (tinytable, Typst-ready). Verdicts come from oai.replication:
# replicated / drift / missing. Each shows a symbol and a word on a light status tint, so
# the table reads in greyscale. Long tables break across pages (theme_typst multipage); put
# their title in a heading, not a caption.

verdict_words <- c(replicated = "✓ replicated", drift = "△ drift", missing = "– missing")
verdict_symbols <- c(replicated = "✓", drift = "△", missing = "–")
verdict_tints <- c(replicated = "#e2f4e2", drift = "#fdf0d0", missing = "#f8e0e0")
verdict_note <- paste(
  "✓ replicated · △ drift · – missing.",
  "Counts replicate within 3% or 2, means within 0.5, odds ratios within 0.1 with the same significance."
)

format_verdicts <- function(df, compact = FALSE) {
  text <- if (compact) verdict_symbols else verdict_words
  for (j in grep("^verdict", names(df))) {
    v <- as.character(df[[j]])
    given <- !is.na(v) & nzchar(v)
    unknown <- setdiff(unique(v[given]), names(text))
    if (length(unknown)) {
      stop("unknown verdict(s): ", paste(unknown, collapse = ", "), call. = FALSE)
    }
    df[[j]] <- ifelse(given, unname(text[v]), "")
  }
  df
}

# Identifiers such as "t2.new_pain" or "walker_requires_amount" get zero-width break
# opportunities after "." and "_", so they wrap inside narrow cells instead of overflowing.
breakable_ids <- function(x) {
  ids <- !is.na(x) & grepl("^[A-Za-z][A-Za-z0-9]*([._][A-Za-z0-9]+)+$", x)
  x[ids] <- gsub("([._])", "\\1\u200b", x[ids])
  x
}

#' A tinytable comparison table
#'
#' @param df Data frame of cell text; verdict columns are found by their names (`verdict*`).
#' @param widths Relative column widths, one per column.
#' @param compact Show verdicts as symbols only.
#' @param labels Display headers, one per column.
#' @param multipage `FALSE` keeps a short table in one piece: it moves to the next page rather
#'   than splitting across two.
#' @param bold Logical matrix with `df`'s shape; cells marked TRUE are set in bold.
#' @param groups Named list like `tinytable::group_tt(i =)`: each group title goes before the
#'   data row its value names. With `groups`, the grouping is applied inside, so bold lands on
#'   the right cells; callers must not call `group_tt` on a table that has `bold`.
compare_table <- function(df, widths = NULL, compact = FALSE, labels = NULL, multipage = TRUE,
                          bold = NULL, groups = NULL) {
  df <- as.data.frame(df)
  if (!is.null(widths) && length(widths) != ncol(df)) {
    stop("widths needs one value per column (", ncol(df), ")", call. = FALSE)
  }
  if (!is.null(labels) && length(labels) != ncol(df)) {
    stop("labels needs one value per column (", ncol(df), ")", call. = FALSE)
  }
  if (!is.null(bold)) {
    bold <- as.matrix(bold)
    if (!is.logical(bold) || !identical(dim(bold), dim(df))) {
      stop("compare_table(): bold must be a logical matrix with the table's shape (",
           nrow(df), " x ", ncol(df), ")", call. = FALSE)
    }
  }
  verdict_cols <- grep("^verdict", names(df))
  shown <- format_verdicts(df, compact)
  for (j in seq_along(shown)) {
    if (is.character(shown[[j]])) shown[[j]] <- breakable_ids(shown[[j]])
  }
  if (!is.null(labels)) names(shown) <- labels
  args <- list(shown)
  if (length(verdict_cols)) args$notes <- verdict_note
  if (!is.null(widths)) args$width <- widths
  tab <- tinytable::theme_typst(do.call(tinytable::tt, args), multipage = multipage)
  # Cell text such as "0.6 (0.4-0.8) *" or "t2.new_pain" is Typst markup unless escaped.
  tab <- tinytable::format_tt(tab, escape = TRUE)
  for (j in verdict_cols) {
    for (verdict in names(verdict_tints)) {
      i <- which(df[[j]] == verdict)
      if (length(i)) tab <- tinytable::style_tt(tab, i = i, j = j, background = verdict_tints[[verdict]])
    }
  }
  if (!is.null(groups)) tab <- tinytable::group_tt(tab, i = groups)
  if (!is.null(bold)) {
    # tinytable keys styles by Typst row (header = 0) and does not shift styles made before
    # group_tt, so bold goes on after grouping, each data row moved down by the group rows above
    starts <- if (is.null(groups)) integer() else unlist(groups)
    cells <- which(bold & !is.na(bold), arr.ind = TRUE)
    for (k in seq_len(nrow(cells))) {
      row <- cells[k, 1]
      tab <- tinytable::style_tt(tab, i = row + sum(starts <= row), j = cells[k, 2], bold = TRUE)
    }
  }
  tab
}
