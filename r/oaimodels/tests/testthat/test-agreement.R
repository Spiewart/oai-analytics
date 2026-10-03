test_that("answer_levels treats codes outside the answers as no level", {
  walker <- c(FALSE, TRUE, TRUE, TRUE, NA)
  code <- c(NA, 2, 88, 3, 1)
  lv <- answer_levels(walker, code, n_codes = 3)
  expect_equal(levels(lv), c("none", "1", "2", "3"))
  expect_equal(as.character(lv), c("none", "2", NA, "3", NA))
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

test_that("paired_agreement gives the Hodges-Lehmann difference and percentile limits", {
  x <- c(10, 12, 15, 20, 30)
  y <- c(8, 11, 10, 25, 20)
  d <- x - y  # 2, 1, 5, -5, 10
  walsh <- outer(d, d, "+") / 2
  # n = 5 is too few for a 95% Wilcoxon interval, and wilcox.test() says so; that one warning is
  # expected here (paired_agreement() lets it surface), any other still fails the test
  a <- muffle_warning(paired_agreement(x, y), "conf.level not achievable")
  expect_equal(a[["estimate"]], stats::median(walsh[upper.tri(walsh, diag = TRUE)]))
  expect_equal(a[["loa_lo"]], unname(stats::quantile(d, 0.025)))
  expect_equal(a[["loa_hi"]], unname(stats::quantile(d, 0.975)))
  expect_equal(a[["n"]], 5)
  expect_true(a[["lo"]] <= a[["estimate"]] && a[["estimate"]] <= a[["hi"]])
  expect_true(is.na(paired_agreement(1, NA)[["estimate"]]))
})

test_that("weekly_bins puts zero in its own bin and is left-closed", {
  b <- weekly_bins(c(0, 0.75, 2, 4.5, 5, 9.99, 10, 30, NA), c(0, 2, 5, 10))
  expect_equal(levels(b), c("0", "<2", "2–5", "5–10", "10+"))
  expect_equal(as.character(b), c("0", "<2", "2–5", "2–5", "5–10", "5–10", "10+", "10+", NA))
  expect_error(weekly_bins(1, c(1, 2)), "start at 0")
})

test_that("hex_cells keeps only cells with at least min_count points", {
  skip_if_not_installed("hexbin")
  set.seed(3)
  x <- c(rep(1, 40), stats::runif(30, 0, 10))
  y <- c(rep(1, 40), stats::runif(30, 0, 10))
  cells <- hex_cells(x, y, bins = 10, min_count = 10)
  expect_true(nrow(cells) >= 1)
  expect_true(all(cells$count >= 10))
  expect_true(sum(cells$count) <= length(x))
  expect_true(any(abs(cells$x - 1) < 1 & abs(cells$y - 1) < 1))
  expect_true(all(cells$dx > 0 & cells$dy > 0))
  expect_equal(nrow(hex_cells(1:5, 1:5, bins = 10, min_count = 10)), 0)
})
