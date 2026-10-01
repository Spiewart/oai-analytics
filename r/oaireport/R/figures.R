# Figures for analysis reports, styled by theme_oai(): forest plots and cohort flow diagrams.

check_columns <- function(df, required, what) {
  missing <- setdiff(required, names(df))
  if (length(missing)) {
    stop(what, " is missing column(s): ", paste(missing, collapse = ", "), call. = FALSE)
  }
}

count_text <- function(x) formatC(x, format = "d", big.mark = ",")

# Odds ratios with 95% CIs, one row per outcome, sources dodged within a row.
# `estimates`: outcome, source, or, lo, hi (plus the `facet` column when given). Outcomes
# run top to bottom and facets left to right in order of first appearance; `sources` fixes
# the colour and shape order (default: order of first appearance). At most four sources.
forest_plot <- function(estimates, ref = 1, log_scale = TRUE, facet = NULL, sources = NULL) {
  check_columns(estimates, c("outcome", "source", "or", "lo", "hi", facet), "estimates")
  present <- unique(as.character(estimates$source))
  sources <- sources %||% present
  unlisted <- setdiff(present, sources)
  if (length(unlisted)) {
    stop("sources does not list: ", paste(unlisted, collapse = ", "), call. = FALSE)
  }
  if (length(sources) > length(oai_palette)) {
    stop("forest_plot shows at most ", length(oai_palette),
         " sources; split or facet the rest", call. = FALSE)
  }
  estimates$source <- factor(estimates$source, levels = sources)
  estimates$outcome <- factor(estimates$outcome, levels = rev(unique(estimates$outcome)))
  if (!is.null(facet)) {
    estimates[[facet]] <- factor(estimates[[facet]], levels = unique(estimates[[facet]]))
  }
  colours <- stats::setNames(oai_palette[seq_along(sources)], sources)
  shapes <- stats::setNames(c(16, 17, 15, 18)[seq_along(sources)], sources)
  p <- ggplot2::ggplot(estimates,
                       ggplot2::aes(x = or, y = outcome, colour = source, shape = source)) +
    ggplot2::geom_vline(xintercept = ref, linetype = "dashed", linewidth = 0.3, colour = "grey40") +
    ggplot2::geom_pointrange(ggplot2::aes(xmin = lo, xmax = hi),
                             position = ggplot2::position_dodge(width = 0.6, reverse = TRUE),
                             size = 0.3, linewidth = 0.5) +
    ggplot2::scale_colour_manual(values = colours, breaks = sources) +
    ggplot2::scale_shape_manual(values = shapes, breaks = sources) +
    ggplot2::labs(x = "Odds ratio (95% CI)", y = NULL) +
    theme_oai() +
    ggplot2::theme(panel.grid.major.x = ggplot2::element_line(colour = "grey90", linewidth = 0.25))
  if (log_scale) p <- p + ggplot2::scale_x_log10()
  if (!is.null(facet)) p <- p + ggplot2::facet_wrap(stats::as.formula(paste("~", facet)))
  p
}

# Cohort flow: a box per step with the participants remaining, and a side box for each
# later step that excluded anyone. `flow`: step, persons, excluded_persons, excluded_knees
# (as analyses write flow.csv). `labels` maps steps to text; unlisted steps show their name.
# `published` (named numeric, e.g. c(flow.roa.persons = 2356)) adds "[published]" after
# our count wherever a key flow.<step>.<column> exists. Save at about 0.8 in per step.
flow_diagram <- function(flow, labels, published = NULL) {
  check_columns(flow, c("step", "persons", "excluded_persons", "excluded_knees"), "flow")
  n <- nrow(flow)
  if (n == 0) stop("flow has no steps", call. = FALSE)
  count <- function(ours, step, column) {
    text <- count_text(ours)
    key <- paste("flow", step, column, sep = ".")
    if (key %in% names(published)) text <- sprintf("%s [%s]", text, count_text(published[[key]]))
    text
  }
  box_w <- 0.9
  side_w <- 0.8
  box_h <- 0.3
  y <- rev(seq_len(n)) - 1
  side_x <- box_w / 2 + 0.35 + side_w / 2
  main <- data.frame(x = 0, y = y, label = vapply(seq_len(n), function(i) {
    step <- flow$step[[i]]
    name <- if (step %in% names(labels)) labels[[step]] else step
    paste0(name, "\nn = ", count(flow$persons[[i]], step, "persons"))
  }, character(1)))
  ex <- which(flow$excluded_persons > 0 & seq_len(n) > 1)
  side <- data.frame(x = rep(side_x, length(ex)), y = y[ex] + 0.5, label = vapply(ex, function(i) {
    step <- flow$step[[i]]
    text <- paste("Excluded:", count(flow$excluded_persons[[i]], step, "excluded_persons"))
    if (flow$excluded_knees[[i]] > 0) {
      text <- sprintf("%s\n(%s knees)", text, count(flow$excluded_knees[[i]], step, "excluded_knees"))
    }
    text
  }, character(1)))
  boxes <- rbind(
    data.frame(xmin = -box_w / 2, xmax = box_w / 2, ymin = y - box_h, ymax = y + box_h),
    data.frame(xmin = rep(side_x - side_w / 2, nrow(side)), xmax = rep(side_x + side_w / 2, nrow(side)),
               ymin = side$y - 0.8 * box_h, ymax = side$y + 0.8 * box_h)
  )
  down <- data.frame(x = rep(0, n - 1), xend = rep(0, n - 1), y = y[-n] - box_h, yend = y[-1] + box_h)
  across <- data.frame(x = rep(0, nrow(side)), xend = rep(side_x - side_w / 2, nrow(side)),
                       y = side$y, yend = side$y)
  arrow <- grid::arrow(length = grid::unit(0.05, "in"), type = "closed")
  ink <- "grey20"
  ggplot2::ggplot() +
    ggplot2::geom_rect(data = boxes, ggplot2::aes(xmin = xmin, xmax = xmax, ymin = ymin, ymax = ymax),
                       fill = "white", colour = ink, linewidth = 0.3) +
    ggplot2::geom_segment(data = down, ggplot2::aes(x = x, y = y, xend = xend, yend = yend),
                          arrow = arrow, linewidth = 0.3, colour = ink) +
    ggplot2::geom_segment(data = across, ggplot2::aes(x = x, y = y, xend = xend, yend = yend),
                          arrow = arrow, linewidth = 0.3, colour = ink) +
    ggplot2::geom_text(data = main, ggplot2::aes(x = x, y = y, label = label),
                       size = 2.6, family = oai_font(), lineheight = 0.95) +
    ggplot2::geom_text(data = side, ggplot2::aes(x = x, y = y, label = label),
                       size = 2.5, family = oai_font(), lineheight = 0.95) +
    ggplot2::coord_cartesian(xlim = c(-box_w / 2 - 0.05, side_x + side_w / 2 + 0.05),
                             ylim = c(-box_h - 0.05, n - 1 + box_h + 0.05), expand = FALSE) +
    ggplot2::theme_void(base_family = oai_font())
}
