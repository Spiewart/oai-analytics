# The brief's Figures 1-3 (walker definitions in ROC space; share of device-defined walkers by
# reported frequency; device bout minutes by PASE weekly walking), drawn from the run so the brief
# and the abstract draw the same figures. Source it after `run <- oaireport::load_results()$default`;
# each function returns a ggplot. With marks = TRUE a figure adds the components step's
# between-group marks (adjusted p-values; stars at components.star_levels): the abstract's copies.

fig_assumption <- function(key) run$assumptions$assumptions[[key]]$value
# The one row matching every condition; stops when there is none or several (a changed schema)
fig_row <- function(df, ...) {
  cond <- list(...)
  keep <- Reduce(`&`, Map(function(col, value) !is.na(df[[col]]) & df[[col]] == value, names(cond), cond))
  row <- df[keep, , drop = FALSE]
  if (nrow(row) != 1) {
    stop("expected one row for ", paste(names(cond), unlist(cond), sep = " = ", collapse = ", "),
         ", found ", nrow(row), call. = FALSE)
  }
  row
}
fig_pase <- function(v, component, comparator, level, statistic) {
  cp <- run$validity_components_pase
  cp$visit <- sprintf("%02d", as.integer(cp$visit))
  fig_row(cp, visit = v, component = component, comparator = comparator, level = level, statistic = statistic)
}
fig_item <- function(sample, component, level, statistic) {
  fig_row(run$validity_components_item, sample = sample, component = component, level = level, statistic = statistic)
}
# The star cut-offs, largest first (one star for each a p-value is below)
fig_star_levels <- function() sort(unlist(fig_assumption("components.star_levels")), decreasing = TRUE)
fig_stars <- function(p) oaireport::p_stars(p, levels = fig_star_levels())
# The distinct marks a figure shows, kept on the plot (attr "stars") for its caption's key
fig_with_stars <- function(fig, stars) {
  attr(fig, "stars") <- sort(unique(stars[stars != ""]))
  fig
}
# A caption's key for the marks shown, fewest stars first: "*p<0.05, ***p<0.001"
fig_star_key <- function(stars) {
  if (!length(stars)) return("")
  stars <- stars[order(nchar(stars))]
  levels <- fig_star_levels()
  paste(sprintf("%sp<%s", stars, format(levels[nchar(stars)], scientific = FALSE, drop0trailing = TRUE)), collapse = ", ")
}
fig_labels <- function() lapply(fig_assumption("components.answer_labels"), unlist)
fig_visits <- c("06", "08")
fig_wave_names <- c(`06` = "48 months", `08` = "72 months")
fig_colours <- oaireport::brief_colours

# Figure 1: each walker definition by sensitivity and 1 - specificity. Marks: the stricter
# definitions' change in Youden's J from any walking, in the same people (adjusted p).
fig_definitions <- function(marks = FALSE) {
  cuts <- c("cut1", "cut2", "cut3")
  pase_any_is_walker <- fig_assumption("pase.walker_threshold") == 0
  # p: the stricter definition's change in J from any walking (adjusted); only read with marks
  item_pts <- do.call(rbind, lapply(cuts, function(k) data.frame(
    source = "Walking item (times per month)", cut = k,
    se = fig_item("validation", "times", k, "se")$estimate,
    fpr = 1 - fig_item("validation", "times", k, "sp")$estimate,
    current = k == "cut1",
    p = if (marks && k != "cut1") fig_item("validation", "times", k, "p_adj_j_diff")$estimate else NA_real_)))
  pase_pts <- do.call(rbind, lapply(fig_visits, function(v) do.call(rbind, lapply(cuts, function(k) data.frame(
    source = sprintf("PASE days per week, %s", fig_wave_names[[v]]), cut = k,
    se = fig_pase(v, "frequency", "device_walker", k, "se")$estimate,
    fpr = 1 - fig_pase(v, "frequency", "device_walker", k, "sp")$estimate,
    current = k == "cut1" && pase_any_is_walker,
    p = if (marks && k != "cut1") fig_pase(v, "frequency", "device_walker", k, "p_adj_j_diff")$estimate else NA_real_)))))
  pts <- rbind(item_pts, pase_pts)
  pts$source <- factor(pts$source, levels = unique(pts$source))
  # One source per row (a single row is wider than the column); keys show the line, solid or dashed
  source_key <- ggplot2::guide_legend(ncol = 1, order = 1, override.aes = list(shape = NA),
                                      theme = ggplot2::theme(legend.key.width = ggplot2::unit(2, "lines")))
  fig <- ggplot2::ggplot(pts, ggplot2::aes(fpr, se, colour = source, linetype = source)) +
    oaireport::youden_contours() +
    ggplot2::geom_line(linewidth = 0.6) +
    # Filled markers with a white outline, item drawn last: its triangle sits just below PASE's
    ggplot2::geom_point(data = pts[rev(seq_len(nrow(pts))), ], ggplot2::aes(shape = current, fill = source),
                        size = 2.6, colour = "white", stroke = 0.6)
  stricter_label <- "Stricter, frequency-based"
  used <- character()
  if (marks) {
    pts$stars <- fig_stars(pts$p)
    used <- pts$stars
    # Each series' stars on its own side, on a white ground so lines never cut them: the walking
    # question to the right, PASE at 72 months (up and left of 48's) to the left, at 48 months below
    side <- ifelse(grepl("^Walking item", pts$source), "right", ifelse(grepl("72", pts$source), "left", "below"))
    pts$hjust <- c(right = -0.3, left = 1.3, below = 0.5)[side]
    pts$vjust <- c(right = 0.5, left = 0.5, below = 1.5)[side]
    fig <- fig +
      ggplot2::geom_label(data = pts[pts$stars != "", , drop = FALSE],
                          ggplot2::aes(label = stars, hjust = hjust, vjust = vjust), fill = "white",
                          border.colour = NA, label.padding = ggplot2::unit(0.08, "lines"),
                          size = 3.2, show.legend = FALSE, family = oaireport::oai_font())
  }
  fig <- fig +
    ggplot2::scale_colour_manual(values = c(fig_colours[["item"]], fig_colours[["pase"]], fig_colours[["pase"]]), name = NULL) +
    ggplot2::scale_linetype_manual(values = c("solid", "solid", "dashed"), name = NULL) +
    ggplot2::scale_fill_manual(values = c(fig_colours[["item"]], fig_colours[["pase"]], fig_colours[["pase"]]), name = NULL) +
    ggplot2::scale_shape_manual(values = c(`TRUE` = 24, `FALSE` = 21), name = NULL,
                                labels = c(`TRUE` = "Definition in use", `FALSE` = stricter_label)) +
    ggplot2::coord_equal(xlim = c(0, 1), ylim = c(0, 1), clip = "off") +
    ggplot2::labs(x = "1 − specificity", y = "Sensitivity") +
    ggplot2::guides(colour = source_key, linetype = source_key, fill = source_key,
                    shape = ggplot2::guide_legend(order = 2, ncol = if (marks) 1 else NULL, override.aes = list(fill = "black"))) +
    oaireport::theme_oai(base_size = 8) +
    ggplot2::theme(legend.position = "bottom", legend.box = "vertical",
                   legend.spacing.y = ggplot2::unit(2, "pt"), legend.key.spacing.y = ggplot2::unit(0, "pt"),
                   legend.margin = ggplot2::margin(0, 0, 0, 0), legend.box.spacing = ggplot2::unit(4, "pt"),
                   plot.margin = ggplot2::margin(14, 8, 4, 4))
  # The marked copy is drawn wider (two columns), legend at the right, so the stars have room
  if (marks) fig <- fig + ggplot2::theme(legend.position = "right", legend.justification = "left")
  fig_with_stars(fig, used)
}

# Figure 2: the share who are device-defined walkers at each reported frequency, the walking item
# (validation sample) and PASE at 48 months. Marks: each level against the lowest (adjusted p).
fig_shares <- function(marks = FALSE) {
  labels <- fig_labels()
  pct <- function(x) paste0(formatC(100 * x, format = "f", digits = 0, big.mark = ","), "%")
  level_rows <- function(get, levels, names, question, fill) {
    do.call(rbind, lapply(seq_along(levels), function(i) {
      r <- get(levels[[i]], "share")
      p <- if (marks && i > 1) get(levels[[i]], "p_adj_vs_ref")$estimate else NA_real_
      data.frame(question = question, answer = names[[i]], estimate = r$estimate, lo = r$lo, hi = r$hi,
                 fill = if (i == 1) paste0(fill, "_ref") else fill, p = p)
    }))
  }
  # PASE days answer levels 0 to length(labels) - 1: level i is labels$pase_days[i + 1]
  pase_levels <- as.character(seq_along(labels$pase_days) - 1)
  bars <- rbind(
    level_rows(function(l, stat) fig_item("validation", "times", l, stat),
               c("none", as.character(seq_along(labels$times))), c("Non-walkers", labels$times),
               "Walking item: times per month", "item"),
    level_rows(function(l, stat) fig_pase("06", "frequency", "device_walker", l, stat),
               pase_levels, labels$pase_days, "PASE: days walked last week (48 months)", "pase"))
  bars$answer <- factor(bars$answer, levels = rev(unique(bars$answer)))
  bars$question <- factor(bars$question, levels = unique(bars$question))
  bars$label <- if (marks) trimws(paste(pct(bars$estimate), fig_stars(bars$p))) else pct(bars$estimate)
  x_top <- min(1, max(bars$hi, na.rm = TRUE) + if (marks) 0.2 else 0.15)
  fig <- ggplot2::ggplot(bars, ggplot2::aes(estimate, answer, fill = fill)) +
    ggplot2::geom_col(width = 0.65) +
    ggplot2::geom_errorbar(ggplot2::aes(xmin = lo, xmax = hi), width = 0.25, linewidth = 0.3, orientation = "y") +
    # A fixed gap after the whisker; with marks the labels differ in width, so hjust would not do
    ggplot2::geom_text(ggplot2::aes(x = hi, label = label), hjust = if (marks) 0 else -0.25,
                       nudge_x = if (marks) 0.012 else 0, size = 2.6, family = oaireport::oai_font()) +
    ggplot2::scale_fill_manual(values = c(item_ref = fig_colours[["muted"]], item = fig_colours[["item"]],
                                          pase_ref = fig_colours[["pase_muted"]], pase = fig_colours[["pase"]]),
                               guide = "none") +
    ggplot2::scale_x_continuous(labels = function(x) paste0(100 * x, "%"), limits = c(0, x_top), expand = c(0, 0)) +
    ggplot2::facet_wrap(~question, scales = "free_y") +
    ggplot2::labs(x = "Share who are device-defined walkers (95% CI)", y = NULL) +
    oaireport::theme_oai(base_size = 8)
  fig_with_stars(fig, if (marks) fig_stars(bars$p) else character())
}

# Figure 3: device bout minutes a week (median, interquartile range) in each band of PASE weekly
# walking, at both visits. Marks: each band against 0 hours (adjusted p).
fig_weekly <- function(marks = FALSE) {
  cp <- run$validity_components_pase
  cp$visit <- sprintf("%02d", as.integer(cp$visit))
  count <- function(x) formatC(x, format = "d", big.mark = ",")
  cal <- cp[cp$component == "weekly" & cp$comparator == "purposeful_week" & cp$statistic == "median", ]
  cal$level <- factor(cal$level, levels = unique(cal$level))  # the step writes the bins in order
  cal$visit_name <- fig_wave_names[cal$visit]
  fig <- ggplot2::ggplot(cal, ggplot2::aes(level, estimate)) +
    ggplot2::geom_pointrange(ggplot2::aes(ymin = lo, ymax = hi), colour = fig_colours[["pase"]], size = 0.3) +
    ggplot2::geom_text(ggplot2::aes(y = hi, label = paste0("n = ", count(n))), vjust = -0.6, size = 2.2,
                       colour = "grey35", family = oaireport::oai_font())
  used <- character()
  if (marks) {
    first <- levels(cal$level)[1]
    cal$p <- vapply(seq_len(nrow(cal)), function(i) {
      if (as.character(cal$level[i]) == first) NA_real_ else
        fig_pase(cal$visit[i], "weekly", "purposeful_week", as.character(cal$level[i]), "p_adj_vs_ref")$estimate
    }, numeric(1))
    cal$stars <- fig_stars(cal$p)
    used <- cal$stars
    fig <- fig + ggplot2::geom_text(data = cal, ggplot2::aes(y = hi, label = stars), vjust = -1.6, size = 3,
                                    family = oaireport::oai_font())
  }
  fig <- fig +
    ggplot2::scale_y_continuous(expand = ggplot2::expansion(mult = c(0.05, if (marks) 0.22 else 0.15))) +
    ggplot2::facet_wrap(~visit_name) +
    ggplot2::labs(x = "Estimated weekly walking from PASE (hours per week)",
                  y = "Device purposeful-bout\nminutes per week") +
    oaireport::theme_oai(base_size = 8)
  fig_with_stars(fig, used)
}
