# Agreement between a self-report and the device (spec amendment 12): answer levels, shares by
# level, classification at cuts with Youden's J, Cohen's kappa, paired differences, weekly bins and
# aggregate hexagonal cells for a scatter.

#' Levels of an amount answer: "none" for non-walkers, the band code for walkers who gave one
#'
#' A walker whose code is outside 1..n_codes (88, don't know; or missing) has no level (NA).
answer_levels <- function(walker, code, n_codes) {
  band <- ifelse(!is.na(code) & code %in% seq_len(n_codes), code, NA)
  level <- ifelse(is.na(walker), NA, ifelse(!walker, "none", ifelse(is.na(band), NA, as.character(band))))
  factor(level, levels = c("none", as.character(seq_len(n_codes))))
}

#' Share of `reference` TRUE at each level of the factor `level`, with Wilson 95% intervals
level_shares <- function(reference, level) {
  if (!is.factor(level)) stop("level_shares(): level must be a factor (its levels give the order)", call. = FALSE)
  ok <- !is.na(reference) & !is.na(level)
  r <- as.logical(reference[ok])
  l <- level[ok]
  do.call(rbind, lapply(levels(level), function(lv) {
    k <- sum(r[l == lv])
    n <- sum(l == lv)
    w <- wilson(k, n)
    data.frame(level = lv, estimate = w[["estimate"]], lo = w[["lo"]], hi = w[["hi"]], k = k, n = n)
  }))
}

#' Youden's J (Se + Sp - 1) with a person-level percentile bootstrap interval
youden_ci <- function(test, reference, reps = 1000, seed = 1) {
  ok <- !is.na(test) & !is.na(reference)
  t <- as.logical(test[ok])
  r <- as.logical(reference[ok])
  j <- function(t, r) if (!any(r) || all(r)) NA_real_ else mean(t[r]) + mean(!t[!r]) - 1
  if (!length(t)) return(c(estimate = NA_real_, lo = NA_real_, hi = NA_real_, n = 0))
  boots <- with_seed(seed, replicate(reps, {
    i <- sample.int(length(t), replace = TRUE)
    j(t[i], r[i])
  }))
  q <- if (all(is.na(boots))) c(NA_real_, NA_real_) else stats::quantile(boots, c(0.025, 0.975), na.rm = TRUE, names = FALSE)
  c(estimate = j(t, r), lo = q[1], hi = q[2], n = length(t))
}

#' Cohen's kappa for two binary ratings, with a person-level percentile bootstrap interval
kappa_ci <- function(a, b, reps = 1000, seed = 1) {
  ok <- !is.na(a) & !is.na(b)
  a <- as.logical(a[ok])
  b <- as.logical(b[ok])
  kappa <- function(a, b) {
    pe <- mean(a) * mean(b) + mean(!a) * mean(!b)
    if (!length(a) || pe == 1) NA_real_ else (mean(a == b) - pe) / (1 - pe)
  }
  if (!length(a)) return(c(estimate = NA_real_, lo = NA_real_, hi = NA_real_, n = 0))
  boots <- with_seed(seed, replicate(reps, {
    i <- sample.int(length(a), replace = TRUE)
    kappa(a[i], b[i])
  }))
  q <- if (all(is.na(boots))) c(NA_real_, NA_real_) else stats::quantile(boots, c(0.025, 0.975), na.rm = TRUE, names = FALSE)
  c(estimate = kappa(a, b), lo = q[1], hi = q[2], n = length(a))
}

#' Classification of `reference` by `code >= cut`, at each cut: Se, Sp, PPV, NPV (Wilson) and J
cut_classification <- function(code, reference, cuts, reps = 1000, seed = 1) {
  do.call(rbind, lapply(cuts, function(cut) {
    test <- code >= cut
    cl <- classification(test, reference)
    j <- youden_ci(test, reference, reps = reps, seed = seed)
    rbind(
      data.frame(cut = cut, measure = cl$measure, estimate = cl$estimate, lo = cl$lo, hi = cl$hi, n = cl$n),
      data.frame(cut = cut, measure = "j", estimate = j[["estimate"]], lo = j[["lo"]], hi = j[["hi"]], n = j[["n"]])
    )
  }))
}

#' Paired agreement in the same units: the median of the differences x - y with a person-level
#' percentile bootstrap 95% interval (seeded by `seed`, leaving the caller's random-number stream
#' alone), and the 2.5th and 97.5th percentiles of x - y (limits of agreement, without assuming
#' normal differences). Pairs whose difference is not finite (a missing value, or Inf) are dropped.
#'
#' The median rather than the Hodges-Lehmann estimate, because a Wilcoxon interval drops zero
#' differences while the Hodges-Lehmann estimate keeps them, and exact zeros are common here (people
#' who walk none, with no device minutes): the estimate could fall outside its own interval. The
#' bootstrap interval is for the very median reported.
paired_agreement <- function(x, y, reps = 1000, seed = 1) {
  d <- x - y
  d <- d[is.finite(d)]
  if (length(d) < 2) {
    return(c(estimate = NA_real_, lo = NA_real_, hi = NA_real_, loa_lo = NA_real_, loa_hi = NA_real_, n = length(d)))
  }
  boots <- with_seed(seed, replicate(reps, stats::median(d[sample.int(length(d), replace = TRUE)])))
  q <- stats::quantile(boots, c(0.025, 0.975), names = FALSE)
  loa <- stats::quantile(d, c(0.025, 0.975), names = FALSE)
  c(estimate = stats::median(d), lo = q[1], hi = q[2], loa_lo = loa[1], loa_hi = loa[2], n = length(d))
}

#' Bins of weekly hours from edges c(0, e2, ..., eK): "0", "<e2", "e2–e3", ..., "eK+" (left-closed)
weekly_bins <- function(hours, edges) {
  if (length(edges) < 2) stop("weekly_bins(): edges need at least two values, 0 and the first cut", call. = FALSE)
  if (edges[1] != 0) stop("weekly_bins(): edges must start at 0", call. = FALSE)
  if (any(hours < 0, na.rm = TRUE)) stop("weekly_bins(): hours must not be negative", call. = FALSE)
  inner <- edges[-1]
  fmt <- function(x) format(x, trim = TRUE, drop0trailing = TRUE)
  labels <- c("0", paste0("<", fmt(inner[1])), if (length(inner) > 1) paste0(fmt(utils::head(inner, -1)), "–", fmt(inner[-1])),
              paste0(fmt(utils::tail(inner, 1)), "+"))
  idx <- ifelse(is.na(hours), NA, ifelse(hours == 0, 1L, findInterval(hours, c(0, inner)) + 1L))
  factor(labels[idx], levels = labels)
}

#' Hexagonal cells of a scatter, as aggregate counts: centres (x, y), count and the hexagon's
#' half-width (dx) and vertex height (dy). Cells with fewer than `min_count` points are dropped,
#' so no cell describes fewer participants than that.
#'
#' Pointy-top regular hexagons on a plane where each axis runs between rounded bounds,
#' range(pretty(v, n = bins)), and is scaled so that those bounds span `bins` units: a cell is one
#' unit wide there and there are about `bins` cells across each range. The cell size and the lattice
#' therefore come from rounded bounds only; no participant's own minimum or maximum is recoverable
#' from them (an axis whose bounds have no spread gets unit 1). The centres lie on two offset
#' lattices, even rows at (i, sqrt(3) * j) and odd rows at (i + 1/2, sqrt(3) * (j + 1/2)), and each
#' point goes to the nearer of its two candidate centres, which is the hexagon that contains it. In
#' data units a cell is 2 * dx wide, and its vertices lie at (ox * dx, oy * dy) from the centre for
#' ox = c(1, 0, -1, -1, 0, 1) and oy = c(1, 2, 1, -1, -2, -1). Rows with a missing or infinite x or
#' y are left out.
hex_cells <- function(x, y, bins = 30, min_count = 10) {
  empty <- data.frame(x = numeric(), y = numeric(), count = integer(), dx = numeric(), dy = numeric())
  ok <- is.finite(x) & is.finite(y)
  x <- x[ok]
  y <- y[ok]
  if (!length(x) || length(x) < min_count) return(empty)
  bx <- range(pretty(x, n = bins))
  by <- range(pretty(y, n = bins))
  unit <- function(bounds) {
    span <- diff(bounds) / bins
    if (is.finite(span) && span > 0) span else 1
  }
  w <- unit(bx)
  h <- unit(by)
  u <- (x - bx[1]) / w
  v <- (y - by[1]) / h
  s <- sqrt(3) / 2
  # lattice A, even rows: centre (ia, 2 s ja); lattice B, odd rows: centre (ib + 1/2, s (2 jb + 1))
  ia <- round(u)
  ja <- round(v / (2 * s))
  ib <- floor(u)
  jb <- floor(v / (2 * s))
  near_a <- (u - ia)^2 + (v - 2 * s * ja)^2 <= (u - (ib + 0.5))^2 + (v - s * (2 * jb + 1))^2
  key <- paste(near_a, ifelse(near_a, ia, ib), ifelse(near_a, ja, jb))
  counts <- table(factor(key, levels = unique(key)))
  first <- match(names(counts), key)
  cu <- ifelse(near_a, ia, ib + 0.5)[first]
  cv <- ifelse(near_a, 2 * s * ja, s * (2 * jb + 1))[first]
  cells <- data.frame(x = bx[1] + cu * w, y = by[1] + cv * h, count = as.integer(counts),
                      dx = 0.5 * w, dy = h / (2 * sqrt(3)))
  cells <- cells[order(cells$y, cells$x), , drop = FALSE]
  rownames(cells) <- NULL
  cells[cells$count >= min_count, , drop = FALSE]
}
