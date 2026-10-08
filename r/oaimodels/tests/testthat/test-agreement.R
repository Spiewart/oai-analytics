test_that("answer_levels treats codes outside the answers as no level", {
  # the last walker has no code at all: a "yes" with no amount, under walker coding
  walker <- c(FALSE, TRUE, TRUE, TRUE, NA, TRUE)
  code <- c(NA, 2, 88, 3, 1, NA)
  lv <- answer_levels(walker, code, n_codes = 3)
  expect_equal(levels(lv), c("none", "1", "2", "3"))
  expect_equal(as.character(lv), c("none", "2", NA, "3", NA, NA))
})

test_that("level_shares gives each level's share with Wilson intervals, in factor order", {
  ref <- c(TRUE, FALSE, TRUE, TRUE, FALSE, NA)
  lv <- factor(c("b", "a", "b", "a", "a", "b"), levels = c("b", "a", "c"))
  s <- level_shares(ref, lv)
  expect_equal(s$level, c("b", "a", "c"))
  expect_equal(s$k, c(2, 1, 0))
  expect_equal(s$n, c(2, 3, 0))
  expect_equal(s$estimate[1:2], c(1, 1 / 3))
  expect_true(is.na(s$estimate[3]))
  w <- wilson(1, 3)
  expect_equal(s$lo[2], unname(w[["lo"]]))
  expect_error(level_shares(ref, as.character(lv)), "factor")
})

test_that("youden_ci is Se + Sp - 1 with a reproducible bootstrap interval", {
  test <- c(rep(TRUE, 8), rep(FALSE, 2), rep(TRUE, 3), rep(FALSE, 7))
  ref <- c(rep(TRUE, 10), rep(FALSE, 10))
  j <- youden_ci(test, ref, reps = 200, seed = 1)
  expect_equal(j[["estimate"]], 0.8 + 0.7 - 1)
  expect_equal(j[["n"]], 20)
  expect_true(j[["lo"]] <= j[["estimate"]] && j[["estimate"]] <= j[["hi"]])
  expect_identical(j, youden_ci(test, ref, reps = 200, seed = 1))
  expect_true(is.na(youden_ci(test, rep(TRUE, 20), reps = 10)[["estimate"]]))
  empty <- youden_ci(logical(0), logical(0), reps = 10)
  expect_true(is.na(empty[["estimate"]]))
  expect_equal(empty[["n"]], 0)
})

test_that("youden_ci and kappa_ci leave the caller's random-number stream alone", {
  test <- c(rep(TRUE, 8), rep(FALSE, 2), rep(TRUE, 3), rep(FALSE, 7))
  ref <- c(rep(TRUE, 10), rep(FALSE, 10))
  set.seed(42)
  before <- get(".Random.seed", envir = globalenv())
  youden_ci(test, ref, reps = 20, seed = 5)
  expect_identical(get(".Random.seed", envir = globalenv()), before)
  kappa_ci(test, ref, reps = 20, seed = 5)
  expect_identical(get(".Random.seed", envir = globalenv()), before)
})

test_that("kappa_ci matches a hand-computed Cohen's kappa", {
  a <- c(rep(TRUE, 20), rep(TRUE, 5), rep(FALSE, 10), rep(FALSE, 15))
  b <- c(rep(TRUE, 20), rep(FALSE, 5), rep(TRUE, 10), rep(FALSE, 15))
  # agreement 35/50 = 0.7; chance 0.5 * 0.6 + 0.5 * 0.4 = 0.5; kappa = (0.7 - 0.5) / 0.5 = 0.4
  k <- kappa_ci(a, b, reps = 200, seed = 1)
  expect_equal(k[["estimate"]], 0.4)
  expect_equal(k[["n"]], 50)
  expect_true(k[["lo"]] < 0.4 && k[["hi"]] > 0.4)
})

test_that("cut_classification matches hand-computed tables at each cut", {
  code <- c(0, 1, 2, 3, 3, 0, 1, 2, NA)
  ref <- c(FALSE, FALSE, TRUE, TRUE, TRUE, FALSE, TRUE, FALSE, TRUE)
  cc <- cut_classification(code, ref, cuts = c(1, 3), reps = 50, seed = 1)
  at <- function(cut, m) cc[cc$cut == cut & cc$measure == m, ]
  # cut 1: TP 4, FP 2, FN 0, TN 2
  expect_equal(at(1, "se")$estimate, 1)
  expect_equal(at(1, "sp")$estimate, 0.5)
  expect_equal(at(1, "ppv")$estimate, 4 / 6)
  expect_equal(at(1, "npv")$estimate, 1)
  expect_equal(at(1, "j")$estimate, 0.5)
  expect_equal(at(1, "se")$n, 4)
  expect_equal(at(1, "ppv")$n, 6)
  # cut 3: TP 2, FP 0, FN 2, TN 4
  expect_equal(at(3, "se")$estimate, 0.5)
  expect_equal(at(3, "sp")$estimate, 1)
  expect_equal(at(3, "npv")$estimate, 4 / 6)
  expect_equal(at(3, "j")$estimate, 0.5)
})

test_that("paired_agreement gives the median difference, a bootstrap interval and percentile limits", {
  x <- c(10, 12, 15, 20, 30)
  y <- c(8, 11, 10, 25, 20)
  d <- x - y  # 2, 1, 5, -5, 10
  a <- paired_agreement(x, y, reps = 200, seed = 1)
  expect_named(a, c("estimate", "lo", "hi", "loa_lo", "loa_hi", "n"))
  expect_equal(a[["estimate"]], stats::median(d))
  expect_equal(a[["loa_lo"]], unname(stats::quantile(d, 0.025)))
  expect_equal(a[["loa_hi"]], unname(stats::quantile(d, 0.975)))
  expect_equal(a[["n"]], 5)
  expect_true(a[["lo"]] <= a[["estimate"]] && a[["estimate"]] <= a[["hi"]])
  expect_true(is.na(paired_agreement(1, NA)[["estimate"]]))
  expect_equal(paired_agreement(1, NA)[["n"]], 0)
  one <- paired_agreement(c(1, NA), c(0, 3))
  expect_true(all(is.na(one[c("estimate", "lo", "hi", "loa_lo", "loa_hi")])))
  expect_equal(one[["n"]], 1)
})

test_that("paired_agreement's interval holds its estimate when most differences are exactly zero", {
  # 60 people agree exactly and 40 report more than the device: the median is 0, which a
  # Wilcoxon interval (it drops zero differences) would not contain
  x <- c(rep(0, 60), 1:40)
  y <- rep(0, 100)
  a <- paired_agreement(x, y, reps = 200, seed = 1)
  expect_equal(a[["estimate"]], 0)
  expect_true(a[["lo"]] <= a[["estimate"]] && a[["estimate"]] <= a[["hi"]])
  expect_equal(a[["n"]], 100)
})

test_that("paired_agreement is reproducible and leaves the caller's random-number stream alone", {
  x <- c(10, 12, 15, 20, 30, 7, 9)
  y <- c(8, 11, 10, 25, 20, 7, 12)
  expect_identical(paired_agreement(x, y, reps = 100, seed = 3), paired_agreement(x, y, reps = 100, seed = 3))
  set.seed(42)
  before <- get(".Random.seed", envir = globalenv())
  paired_agreement(x, y, reps = 100, seed = 3)
  expect_identical(get(".Random.seed", envir = globalenv()), before)
})

test_that("paired_agreement drops pairs whose difference is not finite", {
  a <- paired_agreement(c(1, 2, 3, Inf, Inf, NA), c(0, 1, 1, Inf, 0, 1), reps = 50)
  expect_equal(a[["n"]], 3)  # Inf - Inf is NaN and Inf - 0 is Inf: both dropped
  expect_equal(a[["estimate"]], 1)
})

test_that("weekly_bins puts zero in its own bin and is left-closed", {
  b <- weekly_bins(c(0, 0.75, 2, 4.5, 5, 9.99, 10, 30, NA), c(0, 2, 5, 10))
  expect_equal(levels(b), c("0", "<2", "2–5", "5–10", "10+"))
  expect_equal(as.character(b), c("0", "<2", "2–5", "2–5", "5–10", "5–10", "10+", "10+", NA))
  expect_error(weekly_bins(1, c(1, 2)), "start at 0")
})

test_that("weekly_bins stops on edges that do not increase", {
  expect_error(weekly_bins(1, c(0, 5, 2)), "weekly_bins\\(\\): edges must be increasing")
  expect_error(weekly_bins(1, c(0, 2, 2, 5)), "weekly_bins\\(\\): edges must be increasing")
})

test_that("weekly_bins stops on edges with no cut and on negative hours", {
  expect_error(weekly_bins(1, 0), "at least two")
  expect_error(weekly_bins(1, numeric(0)), "at least two")
  expect_error(weekly_bins(c(1, -0.5, NA), c(0, 2)), "negative")
  b <- weekly_bins(c(0, 1, 2, 7, NA), c(0, 2))  # a single cut still works
  expect_equal(levels(b), c("0", "<2", "2+"))
  expect_equal(as.character(b), c("0", "<2", "2+", "2+", NA))
})

test_that("hex_cells keeps only cells with at least min_count points", {
  set.seed(3)
  x <- c(rep(1, 40), stats::runif(30, 0, 10))
  y <- c(rep(1, 40), stats::runif(30, 0, 10))
  cells <- hex_cells(x, y, bins = 10, min_count = 10)
  expect_named(cells, c("x", "y", "count", "dx", "dy"))
  expect_true(nrow(cells) >= 1)
  expect_true(all(cells$count >= 10))
  expect_true(sum(cells$count) <= length(x))
  expect_true(any(abs(cells$x - 1) < 1 & abs(cells$y - 1) < 1))
  expect_true(all(cells$dx > 0 & cells$dy > 0))
  expect_equal(nrow(hex_cells(1:5, 1:5, bins = 10, min_count = 10)), 0)
  expect_named(hex_cells(1:5, 1:5, bins = 10, min_count = 10), c("x", "y", "count", "dx", "dy"))
})

test_that("hex_cells puts every point in exactly one cell", {
  set.seed(3)
  x <- c(rep(1, 40), stats::runif(30, 0, 10), NA)
  y <- c(rep(1, 40), stats::runif(30, 0, 10), 5)
  all_cells <- hex_cells(x, y, bins = 10, min_count = 0)
  expect_equal(sum(all_cells$count), 70)  # the row with an NA is left out
  expect_equal(anyDuplicated(all_cells[c("x", "y")]), 0)
  expect_true(all(all_cells$count >= 1))
})

test_that("hex_cells puts identical points in a single cell, however few distinct values there are", {
  one <- hex_cells(rep(1, 40), rep(1, 40), bins = 10, min_count = 10)
  expect_equal(nrow(one), 1)
  expect_equal(one$count, 40)
  expect_true(one$dx > 0 && one$dy > 0)
  set.seed(3)
  x <- c(rep(1, 40), stats::runif(30, 0, 10))
  y <- c(rep(1, 40), stats::runif(30, 0, 10))
  cells <- hex_cells(x, y, bins = 10, min_count = 0)
  nearest <- which.min((cells$x - 1)^2 + (cells$y - 1)^2)
  expect_true(cells$count[nearest] >= 40)
})

test_that("hex_cells matches a hand-checked three-point case", {
  # Both axes round to 0..10 over 10 bins, so one data unit is one lattice unit. In lattice units the rows
  # are sqrt(3) / 2 apart, so the centres are (0, 0) and (10, 6 * sqrt(3)):
  #   (0, 0) and (0.1, 0.1) are within 0.15 of (0, 0), the nearest centre of either lattice
  #   (10, 10) is 0.39 from (10, 6 * sqrt(3)) and 0.69 from (10.5, 11 * sqrt(3) / 2)
  cells <- hex_cells(c(0, 0.1, 10), c(0, 0.1, 10), bins = 10, min_count = 0)
  expect_equal(nrow(cells), 2)
  cells <- cells[order(cells$x), ]
  expect_equal(cells$count, c(2, 1))
  expect_equal(cells$x, c(0, 10))
  expect_equal(cells$y, c(0, 6 * sqrt(3)))
  expect_equal(cells$dx, c(0.5, 0.5))
  expect_equal(cells$dy, rep(1 / (2 * sqrt(3)), 2))
  expect_equal(hex_cells(c(0, 0.1, 10), c(0, 0.1, 10), bins = 10, min_count = 2)$count, 2)
})

test_that("hex_cells half-sizes follow each axis's own span", {
  # x spans 10 and y spans 100 over 10 bins: a cell is 1 wide and 10 tall in data units
  cells <- hex_cells(c(0, 10), c(0, 100), bins = 10, min_count = 0)
  expect_equal(cells$dx, c(0.5, 0.5))
  expect_equal(cells$dy, rep(10 / (2 * sqrt(3)), 2))
})

test_that("hex_cells puts a point on an odd-row centre in its own cell, apart from the even-row cells around it", {
  # Both axes round to 0..10 over 10 bins, so u = x and v = y. The second point is exactly the centre of
  # an odd-row cell, (1/2, sqrt(3) / 2), which is 1 from the even-row centres (0, 0) and (1, 0).
  # Assigning everything to the even rows would merge it into the cell of the first point.
  cells <- hex_cells(c(0, 0.5, 10), c(0, sqrt(3) / 2, 10), bins = 10, min_count = 0)
  expect_equal(nrow(cells), 3)
  cells <- cells[order(cells$x), ]
  expect_equal(cells$count, c(1, 1, 1))
  expect_equal(cells$x, c(0, 0.5, 10))
  expect_equal(cells$y, c(0, sqrt(3) / 2, 6 * sqrt(3)))
})

test_that("hex_cells puts each point in the cell with the nearest centre on either lattice", {
  set.seed(7)
  n <- 2000
  bins <- 12
  x <- stats::runif(n, 3.37, 96.81)
  y <- exp(stats::rnorm(n, 3, 0.8))
  bx <- range(pretty(x, bins))
  by <- range(pretty(y, bins))
  w <- diff(bx) / bins
  h <- diff(by) / bins
  u <- (x - bx[1]) / w
  v <- (y - by[1]) / h
  s <- sqrt(3) / 2
  grid <- expand.grid(i = -1:(bins + 1), j = -1:(ceiling(bins / s) + 1))
  centres <- rbind(cbind(grid$i, 2 * s * grid$j), cbind(grid$i + 0.5, s * (2 * grid$j + 1)))
  d2 <- outer(u, centres[, 1], "-")^2 + outer(v, centres[, 2], "-")^2
  near <- d2 <= apply(d2, 1, min) + 1e-9           # the nearest centre of each point, with its ties
  strict <- colSums(near[rowSums(near) == 1, , drop = FALSE])
  loose <- colSums(near)
  cells <- hex_cells(x, y, bins = bins, min_count = 0)
  cu <- (cells$x - bx[1]) / w
  cv <- (cells$y - by[1]) / h
  idx <- vapply(seq_len(nrow(cells)), function(k) which.min((centres[, 1] - cu[k])^2 + (centres[, 2] - cv[k])^2), 1L)
  expect_true(all((centres[idx, 1] - cu)^2 + (centres[idx, 2] - cv)^2 < 1e-18))  # each cell is a lattice centre
  expect_equal(anyDuplicated(idx), 0)
  expect_equal(sum(cells$count), n)
  # a cell holds every point whose nearest centre it is, and no point that has a nearer one
  expect_true(all(cells$count >= strict[idx] & cells$count <= loose[idx]))
  expect_equal(sum(strict[-idx]), 0)
  expect_equal(sum(loose[-idx] > 0), 0)
  odd_row <- abs(cv / (2 * s) - round(cv / (2 * s))) > 0.25
  expect_true(any(odd_row) && any(!odd_row))        # both lattices are used
})

test_that("hex_cells sizes and anchors its cells on rounded bounds, not on the data's own extremes", {
  set.seed(5)
  x <- c(3.37, 96.81, stats::runif(200, 10, 90))
  y <- c(-12.43, 41.27, stats::runif(200, 0, 40))
  bins <- 10
  cells <- hex_cells(x, y, bins = bins, min_count = 0)
  bx <- range(pretty(x, bins))
  by <- range(pretty(y, bins))
  width <- unique(cells$dx) * 2 * bins
  height <- unique(cells$dy) * 2 * sqrt(3) * bins
  expect_length(width, 1)
  expect_equal(width, diff(bx))
  expect_equal(height, diff(by))
  expect_false(isTRUE(all.equal(width, diff(range(x)))))
  expect_false(isTRUE(all.equal(height, diff(range(y)))))
  # the centres sit on the lattice that starts at the rounded lower bounds
  cu <- (cells$x - bx[1]) / (diff(bx) / bins)
  cv <- (cells$y - by[1]) / (diff(by) / bins) / (sqrt(3) / 2)
  expect_true(all(abs(2 * cu - round(2 * cu)) < 1e-9))
  expect_true(all(abs(cv - round(cv)) < 1e-9))
})

test_that("vs_reference compares each level with the first, Holm-adjusted within the set", {
  group <- factor(rep(c("ref", "a", "b"), each = 40), levels = c("ref", "a", "b"))
  y <- c(rep(c(TRUE, FALSE), c(8, 32)), rep(c(TRUE, FALSE), c(10, 30)), rep(c(TRUE, FALSE), c(30, 10)))
  out <- vs_reference(y, group, test = "fisher")
  expect_equal(out$level, c("a", "b"))
  raw <- c(stats::fisher.test(table(group[group %in% c("ref", "a")] == "a", y[group %in% c("ref", "a")]))$p.value,
           stats::fisher.test(table(group[group %in% c("ref", "b")] == "b", y[group %in% c("ref", "b")]))$p.value)
  expect_equal(out$p, raw)
  expect_equal(out$p_adj, stats::p.adjust(raw, "holm"))
  expect_equal(out$n, c(80L, 80L))
})

test_that("vs_reference runs a Wilcoxon rank-sum test for numbers and drops missing values", {
  group <- factor(c(rep("0", 30), rep("x", 30)), levels = c("0", "x"))
  y <- c(seq(0, 29), seq(10, 39))
  y[c(1, 31)] <- NA
  out <- vs_reference(y, group, test = "wilcoxon", adjust = "none")
  ok <- !is.na(y)
  expected <- stats::wilcox.test(y[ok & group == "x"], y[ok & group == "0"], exact = FALSE)$p.value
  expect_equal(out$p, expected)
  expect_equal(out$p_adj, expected)
  expect_equal(out$n, 58L)
})

test_that("vs_reference gives NA for a level or reference too small to test, and rejects bad input", {
  group <- factor(c("r", "r", "a", "b", "b"), levels = c("r", "a", "b", "c"))
  out <- vs_reference(c(TRUE, FALSE, TRUE, NA, NA), group, test = "fisher")
  expect_equal(out$level, c("a", "b", "c"))
  expect_true(is.na(out$p[2]) && is.na(out$p[3]))
  expect_error(vs_reference(c(1, 2), factor(c("a", "b")), test = "fisher"), "logical")
  expect_error(vs_reference(c(TRUE, FALSE), c("a", "b")), "factor")
  expect_error(vs_reference(c(1, 2), factor(c("a", "b")), test = "t"), "test")
})

test_that("youden_diff is the paired change in J from the base cut, with a bootstrap Wald test", {
  set.seed(3)
  code <- sample(0:3, 400, replace = TRUE)
  reference <- stats::runif(400) < 0.15 + 0.15 * code
  out <- youden_diff(code, reference, cuts = c(1, 2, 3), reps = 300, seed = 7)
  expect_equal(out$cut, c(2, 3))
  j <- function(cut) { t <- code >= cut; mean(t[reference]) + mean(!t[!reference]) - 1 }
  expect_equal(out$estimate, c(j(2) - j(1), j(3) - j(1)))
  expect_equal(out$hi - out$estimate, out$estimate - out$lo)  # symmetric Wald interval
  z <- out$estimate / ((out$hi - out$lo) / (2 * stats::qnorm(0.975)))
  expect_equal(out$p, 2 * stats::pnorm(-abs(z)))
  expect_equal(out$p_adj, stats::p.adjust(out$p, "holm"))
  expect_equal(out$n, c(400L, 400L))
  # reproducible, and the caller's random-number stream is untouched
  set.seed(11); before <- stats::runif(1)
  set.seed(11); again <- youden_diff(code, reference, cuts = c(1, 2, 3), reps = 300, seed = 7); after <- stats::runif(1)
  expect_equal(again, out)
  expect_equal(before, after)
})

test_that("youden_diff drops missing pairs and needs at least two cuts", {
  code <- c(0, 1, 2, 3, NA, 2, 1, 0, 3, 2)
  reference <- c(FALSE, FALSE, TRUE, TRUE, TRUE, NA, FALSE, FALSE, TRUE, TRUE)
  expect_equal(youden_diff(code, reference, cuts = c(1, 2), reps = 50, seed = 1)$n, 8L)
  expect_error(youden_diff(code, reference, cuts = 1), "two cuts")
})
