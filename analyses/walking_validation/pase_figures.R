# Figures for the walking question against PASE (abstract_pase.qmd), from the pase_walking step:
# the PASE total (Figure 1) and any PASE walking (Figure 2) at every visit, non-walkers (who
# answered no to the 96-month question) against walkers (any yes). Visits are not continuous
# time, so each sits at its own position with no line between them. Each star marks walkers
# against non-walkers, adjusted for age, sex and BMI (Holm, adj_p_holm). Source after
# report_setup.R and brief_figures.R (fig_stars, fig_with_stars).

pw_visit <- function(x) sprintf("%02d", as.integer(x))
pw_groups <- run$pase_walking_groups
pw_groups$visit <- pw_visit(pw_groups$visit)
pw_contrasts <- run$pase_walking_contrasts
pw_contrasts$visit <- pw_visit(pw_contrasts$visit)
pw_bands <- run$pase_walking_bands
pw_bands$visit <- pw_visit(pw_bands$visit)
pw_question_visit <- "10"  # the visit that asked the walking question (96 months)
# Its label over the dashed line at that visit
pw_question_label <- "Walker for Exercise Question"
# Each answer's name in the figures, in legend order, and its colour (points, intervals and n)
pw_labels <- c(no = "Not Walkers for Exercise", yes = "Walkers for Exercise")
pw_colours <- stats::setNames(c("grey45", oaireport::brief_colours[["item"]]), pw_labels)

# The adjusted p of walkers against non-walkers at a visit, for an outcome and estimator
pw_adjusted_p <- function(visit, outcome, estimator, grouping = "any", level = "yes") {
  k <- pw_contrasts[pw_contrasts$grouping == grouping & pw_contrasts$visit == visit &
                      pw_contrasts$outcome == outcome & pw_contrasts$estimator == estimator &
                      pw_contrasts$level == level, "adj_p_holm"]
  if (length(k) == 1) k else NA_real_
}

# Visits as evenly spaced positions labelled by month, from the groups table
pw_positions <- function(visits) {
  months <- vapply(visits, function(v) unique(pw_groups$month[pw_groups$visit == v])[1], numeric(1))
  data.frame(visit = visits, month = months, x = seq_along(visits))
}

# Rows of n at the foot of the panel, one per group in its colour, each labelled "n" at the right
# end (the left is the y axis's; the colour names the group); and the label over the question's
# visit, with a dashed line that stops below it
pw_n_rows <- function(n_frame, y_rows, last_x) {
  list(
    ggplot2::geom_text(data = n_frame, ggplot2::aes(x = x, y = y_rows[answer], label = count(n)),
                       inherit.aes = FALSE, size = 2.3, colour = pw_colours[n_frame$answer],
                       family = oaireport::oai_font()),
    ggplot2::geom_text(data = data.frame(answer = names(y_rows), y = unname(y_rows)),
                       ggplot2::aes(x = last_x + 0.42, y = y, label = "n"),
                       inherit.aes = FALSE, hjust = 0, size = 2.3, colour = pw_colours[names(y_rows)],
                       family = oaireport::oai_font()))
}
pw_question <- function(x, from, to, label_y, resume = NULL, label_bottom = NULL, headroom = 0) {
  # a second dash from above the star (`resume`) to just below the label, so the line reads as
  # one marker passing behind the star; the label rises from `label_y`, and `headroom` above it
  # keeps its lines inside the plot
  second <- if (!is.null(resume)) ggplot2::annotate("segment", x = x, xend = x, y = resume, yend = label_bottom,
                                                    linetype = "dashed", colour = "grey65", linewidth = 0.4)
  list(
    ggplot2::annotate("segment", x = x, xend = x, y = from, yend = to, linetype = "dashed",
                      colour = "grey65", linewidth = 0.4),
    second,
    ggplot2::annotate("text", x = x, y = label_y, label = pw_question_label, size = 2.4, vjust = 0,
                      lineheight = 0.95, colour = "grey45", family = oaireport::oai_font()),
    ggplot2::geom_blank(data = data.frame(x = x, y = label_y + headroom), ggplot2::aes(x = x, y = y), inherit.aes = FALSE))
}

# An outcome's estimate (95% CI) at each visit, non-walkers and walkers side by side, the star of
# the adjusted contrast over each visit and each group's n beneath. `cols` names the estimate and
# interval columns of the groups table; `scale` multiplies them (100 for a share as a percentage).
pw_point_figure <- function(outcome, estimator, cols, ylab, scale = 1, y_labels = ggplot2::waiver()) {
  d <- pw_groups[pw_groups$grouping == "any" & pw_groups$outcome == outcome, ]
  d$y <- scale * d[[cols[["y"]]]]
  d$y_lo <- scale * d[[cols[["lo"]]]]
  d$y_hi <- scale * d[[cols[["hi"]]]]
  pos <- pw_positions(sort(unique(d$visit)))
  d$answer <- factor(pw_labels[d$level], levels = pw_labels)
  d$x <- pos$x[match(d$visit, pos$visit)] + ifelse(d$level == "yes", 0.15, -0.15)
  stars <- data.frame(visit = pos$visit, x = pos$x)
  stars$p <- vapply(stars$visit, pw_adjusted_p, numeric(1), outcome = outcome, estimator = estimator)
  stars$stars <- fig_stars(stars$p)
  stars$y <- vapply(stars$visit, function(v) max(d$y_hi[d$visit == v]), numeric(1))
  bottom <- min(d$y_lo)
  span <- max(d$y_hi) - bottom
  y_rows <- stats::setNames(c(bottom - 0.16 * span, bottom - 0.27 * span), pw_labels)
  n_frame <- data.frame(x = pos$x[match(d$visit, pos$visit)], answer = as.character(d$answer), n = d$n)
  top <- max(stars$y) + 0.14 * span
  q <- pos$x[pos$visit == pw_question_visit]
  # the dashed line runs from above the rows of n to just below the visit's star
  star_y <- stars$y[stars$visit == pw_question_visit]
  fig <- ggplot2::ggplot(d, ggplot2::aes(x, y, colour = answer)) +
    pw_question(q, y_rows[[1]] + 0.07 * span, star_y + 0.01 * span, top + 0.055 * span,
                resume = star_y + 0.11 * span, label_bottom = top + 0.02 * span, headroom = 0.14 * span) +
    ggplot2::geom_errorbar(ggplot2::aes(ymin = y_lo, ymax = y_hi), width = 0.1, linewidth = 0.4) +
    ggplot2::geom_point(size = 2) +
    ggplot2::geom_text(data = stars, ggplot2::aes(x = x, y = y, label = stars), inherit.aes = FALSE,
                       vjust = -0.6, size = 2.8, family = oaireport::oai_font()) +
    pw_n_rows(n_frame, y_rows, max(pos$x)) +
    ggplot2::scale_colour_manual(values = pw_colours, name = NULL) +
    ggplot2::scale_x_continuous(breaks = pos$x, labels = pos$month, expand = ggplot2::expansion(add = 0.5)) +
    # ticks only over the data, not the rows of n beneath it
    ggplot2::scale_y_continuous(breaks = function(l) { b <- pretty(c(bottom, top), 5); b[b >= bottom - 1e-9 & b <= top] },
                                labels = y_labels) +
    ggplot2::coord_cartesian(clip = "off") +
    ggplot2::labs(x = "Months since enrollment", y = ylab) +
    oaireport::theme_oai(base_size = 8) +
    ggplot2::theme(legend.position = "top", plot.margin = ggplot2::margin(4, 46, 4, 4))
  fig_with_stars(fig, stars$stars)
}

# Figure 1: the PASE total, mean (95% CI)
fig_pase_total <- function() {
  pw_point_figure("total", "mean", c(y = "mean", lo = "mean_lo", hi = "mean_hi"),
                  "PASE total score, mean (95% CI)")
}

# Figure 2: short-term walking (any walking outside the home, PASE item 2, past 7 days), % (Wilson 95% CI)
fig_pase_walking <- function() {
  pw_point_figure("walking_any", "share", c(y = "estimate", lo = "lo", hi = "hi"),
                  "Short-term walking (PASE), % (95% CI)", scale = 100, y_labels = function(v) paste0(v, "%"))
}
