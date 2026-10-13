# Figures for the walking question against PASE (abstract_pase.qmd), from the pase_walking step:
# PASE at every visit by the 96-month answer, and any PASE walking at 96 months by amount. Each
# star marks a group against "No", adjusted for age, sex and BMI (Holm, adj_p_holm). Source
# after report_setup.R and brief_figures.R (fig_stars, fig_with_stars, fig_colours).

pw_visit <- function(x) sprintf("%02d", as.integer(x))
pw_groups <- run$pase_walking_groups
pw_groups$visit <- pw_visit(pw_groups$visit)
pw_contrasts <- run$pase_walking_contrasts
pw_contrasts$visit <- pw_visit(pw_contrasts$visit)
pw_question_month <- 96  # the visit that asked the walking question (V10)
pw_colours <- c(No = "grey45", Yes = oaireport::brief_colours[["item"]])
pw_panels <- c(total = "PASE total score, median", walking_any = "Any PASE walking, % (95% CI)")

# The adjusted p of each group against "No", at each visit and outcome
pw_adjusted_p <- function(grouping, visit, outcome, level) {
  k <- pw_contrasts[pw_contrasts$grouping == grouping & pw_contrasts$visit == visit &
                      pw_contrasts$outcome == outcome & pw_contrasts$level == level, "adj_p_holm"]
  if (length(k) == 1) k else NA_real_
}

# Figure 1: PASE total and any PASE walking at each visit, No against any Yes
fig_pase_time <- function() {
  d <- pw_groups[pw_groups$grouping == "any" & pw_groups$outcome %in% names(pw_panels), ]
  d$answer <- factor(ifelse(d$level == "yes", "Yes", "No"), levels = c("No", "Yes"))
  share <- d$outcome == "walking_any"
  d[share, c("estimate", "lo", "hi")] <- 100 * d[share, c("estimate", "lo", "hi")]
  d[!share, c("lo", "hi")] <- NA  # a total's interquartile range is too wide to read
  d$panel <- factor(pw_panels[d$outcome], levels = unname(pw_panels))
  marks <- unique(d[c("visit", "month", "outcome", "panel")])
  marks$p <- mapply(pw_adjusted_p, "any", marks$visit, marks$outcome, "yes")
  marks$stars <- fig_stars(marks$p)
  marks$y <- mapply(function(v, o) max(c(d$estimate, d$hi)[c(d$visit, d$visit) == v & c(d$outcome, d$outcome) == o], na.rm = TRUE),
                    marks$visit, marks$outcome)
  # the label over the dashed line, in every panel; the line stops below it (at the panel's
  # highest point and star), so the two never cross
  asked <- data.frame(panel = factor(unname(pw_panels), levels = unname(pw_panels)), x = pw_question_month,
                      label = "walking question")
  asked$top <- vapply(names(pw_panels), function(o) {
    v <- c(d$estimate[d$outcome == o], d$hi[d$outcome == o])
    lo <- min(c(d$estimate[d$outcome == o], d$lo[d$outcome == o]), na.rm = TRUE)
    max(v, na.rm = TRUE) + 0.1 * (max(v, na.rm = TRUE) - lo)
  }, numeric(1))
  fig <- ggplot2::ggplot(d, ggplot2::aes(month, estimate, colour = answer)) +
    ggplot2::geom_segment(data = asked, ggplot2::aes(x = x, xend = x, y = -Inf, yend = top), inherit.aes = FALSE,
                          linetype = "dashed", colour = "grey65", linewidth = 0.4) +
    ggplot2::geom_text(data = asked, ggplot2::aes(x = x, y = Inf, label = label), inherit.aes = FALSE,
                       hjust = 0.5, vjust = 1.3, size = 2.4, colour = "grey45", family = oaireport::oai_font()) +
    ggplot2::geom_errorbar(data = d[!is.na(d$lo), ], ggplot2::aes(ymin = lo, ymax = hi), width = 3, linewidth = 0.3) +
    ggplot2::geom_line(linewidth = 0.6) +
    ggplot2::geom_point(size = 1.6) +
    ggplot2::geom_text(data = marks, ggplot2::aes(x = month, y = y, label = stars), inherit.aes = FALSE,
                       vjust = -0.6, size = 2.8, family = oaireport::oai_font()) +
    ggplot2::scale_colour_manual(values = pw_colours, name = "Walked for exercise since age 50 (asked at 96 months)") +
    ggplot2::scale_x_continuous(breaks = seq(0, 192, 24), limits = c(-4, 196)) +
    ggplot2::scale_y_continuous(expand = ggplot2::expansion(mult = c(0.08, 0.26))) +
    ggplot2::facet_wrap(~panel, scales = "free_y") +
    ggplot2::labs(x = "Months since enrolment", y = NULL) +
    oaireport::theme_oai(base_size = 8) +
    ggplot2::theme(legend.position = "bottom")
  fig_with_stars(fig, marks$stars)
}

# Figure 2: any PASE walking at 96 months by times a month and by years walked
fig_pase_dose <- function(visit = "10") {
  titles <- c(times = "Times a month", years = "Years walked")
  d <- pw_groups[pw_groups$visit == visit & pw_groups$outcome == "walking_any" & pw_groups$grouping %in% names(titles), ]
  d[c("estimate", "lo", "hi")] <- 100 * d[c("estimate", "lo", "hi")]
  d$p <- mapply(function(g, lv) if (lv == "no") NA_real_ else pw_adjusted_p(g, visit, "walking_any", lv), d$grouping, d$level)
  d$stars <- fig_stars(d$p)
  d$text <- trimws(paste(sprintf("%.0f%%", d$estimate), d$stars))
  d$label <- sub(" times/month$", "", d$label)  # the panel title gives the unit
  d$label <- sub(" years$", "", d$label)
  d$panel <- factor(titles[d$grouping], levels = unname(titles))
  d$key <- paste(d$grouping, d$level)
  d$key <- factor(d$key, levels = rev(unique(d$key)))
  d$fill <- ifelse(d$level == "no", "no", "yes")
  fig <- ggplot2::ggplot(d, ggplot2::aes(estimate, key, fill = fill)) +
    ggplot2::geom_col(width = 0.65) +
    ggplot2::geom_errorbar(ggplot2::aes(xmin = lo, xmax = hi), width = 0.25, linewidth = 0.3, orientation = "y") +
    ggplot2::geom_text(ggplot2::aes(x = hi, label = text), hjust = 0, nudge_x = 1.5, size = 2.6,
                       family = oaireport::oai_font()) +
    ggplot2::scale_fill_manual(values = c(no = "grey70", yes = oaireport::brief_colours[["item"]]), guide = "none") +
    ggplot2::scale_y_discrete(labels = stats::setNames(d$label, d$key)) +
    ggplot2::scale_x_continuous(labels = function(x) paste0(x, "%"), limits = c(0, 118), breaks = seq(0, 100, 25),
                                expand = c(0, 0)) +
    ggplot2::facet_wrap(~panel, scales = "free_y") +
    ggplot2::labs(x = sprintf("Any PASE walking at %s, %% (95%% CI)", wave(visit)), y = NULL) +
    oaireport::theme_oai(base_size = 8)
  fig_with_stars(fig, d$stars)
}
