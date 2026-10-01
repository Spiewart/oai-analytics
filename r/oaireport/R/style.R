# ACR journal style (Arthritis & Rheumatology, Arthritis Care & Research): Arial or a
# sans fallback at 7-9 pt, classic axes, legend at the bottom.

# Okabe-Ito colours in fixed source order: published, ours, variant 1, variant 2.
# Never cycled: a fifth source is a facet or a separate figure.
oai_palette <- c("#0072B2", "#D55E00", "#009E73", "#E69F00")

# Verdict colours. Always shown with a symbol and a word, never colour alone.
oai_status <- c(replicated = "#0ca30c", drift = "#fab219", missing = "#d03b3b")

oai_font <- function() {
  if ("Arial" %in% systemfonts::system_fonts()$family) "Arial" else "sans"
}

theme_oai <- function(base_size = 8) {
  ggplot2::theme_classic(base_size = base_size, base_family = oai_font()) +
    ggplot2::theme(
      axis.text = ggplot2::element_text(size = base_size - 1, colour = "grey15"),
      axis.title = ggplot2::element_text(size = base_size),
      strip.background = ggplot2::element_blank(),
      strip.text = ggplot2::element_text(size = base_size, face = "bold"),
      legend.position = "bottom",
      legend.title = ggplot2::element_blank(),
      legend.text = ggplot2::element_text(size = base_size - 1),
      legend.key.size = ggplot2::unit(0.8, "lines"),
      plot.margin = ggplot2::margin(4, 6, 4, 4)
    )
}
