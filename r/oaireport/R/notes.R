# Notes under tables and figures: a legend in small type that defines the labels above it.

#' A legend for a table or figure, as Markdown lines for a `results: asis` chunk
#'
#' The text is set in small type (8 pt by default) in a block directly under the table or figure,
#' which stays on one page. It is plain text: Markdown and Typst characters in it are escaped, and
#' line breaks become spaces. Build the text in R from the run's assumptions and results, so the
#' numbers it quotes are the run's own.
#'
#' A figure is not a block that can hold its legend, so a chunk that draws one keeps the two
#' together with `figure_group()` before the figure and `close_group = TRUE` here.
#'
#' @param text One string.
#' @param size Type size in points.
#' @param close_group Also close the block opened by `figure_group()`.
#' @return The lines, to be written with `cat(lines, sep = "\n")`.
table_note <- function(text, size = 8, close_group = FALSE) {
  if (!is.character(text) || length(text) != 1 || is.na(text) || !nzchar(trimws(text))) {
    stop("table_note(): text must be one string, not empty", call. = FALSE)
  }
  if (!is.numeric(size) || length(size) != 1 || is.na(size) || size <= 0) {
    stop("table_note(): size must be one positive number of points", call. = FALSE)
  }
  text <- gsub("\\s+", " ", trimws(text))
  text <- gsub("([\\\\*_`\\[\\]<>#$~^])", "\\\\\\1", text, perl = TRUE)
  note <- c("", "```{=typst}",
            "#block(above: 0.45em, below: 1.1em, breakable: false)[",
            sprintf("#set text(size: %spt, fill: luma(50))", format(size)),
            "#set par(justify: false, leading: 0.5em)",
            "```", "", text, "", "```{=typst}", "]", "```", "")
  if (close_group) note <- c(note, "```{=typst}", "]", "```", "")
  note
}

#' Open a block that keeps a figure and its legend on one page
#'
#' Write these lines before the chunk draws the figure, and end with
#' `table_note(text, close_group = TRUE)`.
#'
#' @return The lines, to be written with `cat(lines, sep = "\n")`.
figure_group <- function() {
  c("", "```{=typst}", "#block(breakable: false)[", "```", "")
}
