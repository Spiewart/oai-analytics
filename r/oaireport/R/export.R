# Figures at journal column widths: a vector PDF (cairo, so fonts embed) and a 300 dpi PNG.

figure_widths <- c("1col" = 3.5, "2col" = 7)
max_figure_height <- 9

# `oai report` sets OAI_REPORT_DIR; outside a report, figures go to a temporary directory.
figure_dir <- function() {
  report_dir <- Sys.getenv("OAI_REPORT_DIR")
  if (nzchar(report_dir)) file.path(report_dir, "figures") else tempdir()
}

save_figure <- function(plot, name, width = c("1col", "2col"), height = NULL, dir = figure_dir()) {
  if (!grepl("^[A-Za-z0-9_-]+$", name)) {
    stop("figure name must use only letters, digits, '_' or '-': ", name, call. = FALSE)
  }
  width <- match.arg(width)
  w <- figure_widths[[width]]
  h <- min(if (is.null(height)) 0.75 * w else height, max_figure_height)
  dir.create(dir, recursive = TRUE, showWarnings = FALSE)
  pdf_path <- file.path(dir, paste0(name, ".pdf"))
  ggplot2::ggsave(pdf_path, plot, width = w, height = h, units = "in",
                  device = grDevices::cairo_pdf)
  ggplot2::ggsave(file.path(dir, paste0(name, ".png")), plot, width = w, height = h,
                  units = "in", dpi = 300, device = ragg::agg_png)
  invisible(pdf_path)
}
