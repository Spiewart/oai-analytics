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

compare_table <- function(df, widths = NULL, compact = FALSE) {
  df <- as.data.frame(df)
  if (!is.null(widths) && length(widths) != ncol(df)) {
    stop("widths needs one value per column (", ncol(df), ")", call. = FALSE)
  }
  verdict_cols <- grep("^verdict", names(df))
  args <- list(format_verdicts(df, compact))
  if (length(verdict_cols)) args$notes <- verdict_note
  if (!is.null(widths)) args$width <- widths
  tab <- tinytable::theme_typst(do.call(tinytable::tt, args), multipage = TRUE)
  for (j in verdict_cols) {
    for (verdict in names(verdict_tints)) {
      i <- which(df[[j]] == verdict)
      if (length(i)) tab <- tinytable::style_tt(tab, i = i, j = j, background = verdict_tints[[verdict]])
    }
  }
  tab
}
