test_that("hodges_lehmann and rank_biserial measure a shift", {
  hl <- hodges_lehmann(1:10 + 5, 1:10)
  expect_equal(hl[["estimate"]], 5, tolerance = 1e-6)
  expect_true(hl[["lo"]] < 5 && hl[["hi"]] > 5)
  expect_equal(rank_biserial(11:20, 1:10), 1)
  expect_equal(rank_biserial(1:10, 1:10), 0)
})

test_that("jonckheere detects an increasing trend and not a decreasing one", {
  g <- factor(rep(c("none", "lower", "upper"), each = 3), levels = c("none", "lower", "upper"))
  up <- jonckheere(1:9, g, permutations = 999, seed = 1)
  down <- jonckheere(9:1, g, permutations = 999, seed = 1)
  expect_equal(up[["statistic"]], 27)
  expect_lt(up[["p"]], 0.05)
  expect_gt(down[["p"]], 0.9)
})

test_that("median_regression returns the median difference", {
  skip_if_not_installed("quantreg")
  d <- data.frame(y = c(rep(c(1, 2, 3), 10), rep(c(4, 5, 6), 10)), group = rep(c(0, 1), each = 30))
  est <- median_regression(y ~ group, d, "group")
  expect_equal(est[["estimate"]], 3, tolerance = 1e-6)
  expect_error(median_regression(y ~ group, d, "other"), "other")
  expect_no_warning(median_regression(y ~ group, d, "group"))
})

test_that("median_regression se = 'boot' is reproducible, warning-free and uses the bootstrap SE", {
  skip_if_not_installed("quantreg")
  d <- data.frame(y = c(rep(c(1, 2, 3), 10), rep(c(4, 5, 6), 10)), group = rep(c(0, 1), each = 30))
  est <- median_regression(y ~ group, d, "group", se = "boot", reps = 200, seed = 1)
  expect_equal(est[["estimate"]], 3, tolerance = 1e-6)
  # the interval is +/- 1.96 of quantreg's xy-bootstrap SE under the same seed, and is not empty
  fit <- quiet_nonunique(quantreg::rq(y ~ group, tau = 0.5, data = d))
  set.seed(1)
  boot_se <- quiet_nonunique(summary(fit, se = "boot", bsmethod = "xy", R = 200))$coefficients[
    "group", "Std. Error"
  ]
  expect_gt(boot_se, 0)
  expect_equal(est[["lo"]], 3 - 1.96 * boot_se, tolerance = 1e-6)
  expect_equal(est[["hi"]], 3 + 1.96 * boot_se, tolerance = 1e-6)
  expect_no_warning(median_regression(y ~ group, d, "group", se = "boot", reps = 200, seed = 1))
  expect_identical(est, median_regression(y ~ group, d, "group", se = "boot", reps = 200, seed = 1))
  expect_error(median_regression(y ~ group, d, "group", se = "iid"), "should be one of")
})

test_that("median_regression se = 'boot' is warning-free and finite on a zero-inflated outcome", {
  skip_if_not_installed("quantreg")
  set.seed(3)
  z <- data.frame(y = c(rep(0, 80), stats::rexp(20)), g = rep(c(0, 1), 50), a = stats::rnorm(100))
  expect_no_warning(est <- median_regression(y ~ g + a, z, "g", se = "boot", reps = 200, seed = 1))
  expect_true(all(is.finite(est)))
})

test_that("spearman_ci, deattenuate and wave_reliability", {
  s <- spearman_ci(c(1, 2, 3, 4, 5, 6), c(2, 1, 4, 3, 6, 5))
  expect_equal(s[["rho"]], stats::cor(c(1, 2, 3, 4, 5, 6), c(2, 1, 4, 3, 6, 5), method = "spearman"))
  expect_equal(s[["n"]], 6)
  expect_true(s[["lo"]] < s[["rho"]] && s[["hi"]] > s[["rho"]])
  expect_equal(deattenuate(0.3, reliability_y = 0.36), 0.5)
  expect_equal(deattenuate(0.9, reliability_y = 0.25), 1)
  expect_equal(wave_reliability(0.6, 1), 2 * 0.6 / 1.6)
  expect_equal(wave_reliability(0.6, 0), 0.6)
  expect_equal(wave_reliability(0.6, 0.5), 0.6 / (0.6 + 0.4 * 0.75))
})

test_that("wilson and classification", {
  w <- wilson(5, 10)
  expect_equal(unname(w), c(0.5, 0.2366, 0.7634), tolerance = 1e-4)
  test <- c(TRUE, TRUE, TRUE, FALSE, TRUE, FALSE, FALSE, FALSE)
  ref <- c(TRUE, TRUE, TRUE, TRUE, FALSE, FALSE, FALSE, FALSE)
  cl <- classification(test, ref)
  expect_equal(cl$measure, c("se", "sp", "ppv", "npv"))
  expect_equal(cl$estimate, c(3 / 4, 3 / 4, 3 / 4, 3 / 4))
  expect_equal(cl$k, c(3, 3, 3, 3))
  expect_equal(cl$n, c(4, 4, 4, 4))
})

test_that("newcombe_diff reproduces Newcombe's (1998) worked example", {
  d <- newcombe_diff(56, 70, 48, 80)
  expect_equal(unname(d), c(0.2000, 0.0524, 0.3339), tolerance = 1e-4)
  expect_equal(names(d), c("estimate", "lo", "hi"))
  expect_true(all(is.na(newcombe_diff(3, 0, 48, 80))))
  expect_true(all(is.na(newcombe_diff(56, 70, 0, 0))))
})

test_that("classification handles empty cells", {
  cl <- classification(c(TRUE, TRUE), c(TRUE, TRUE))
  expect_true(is.na(cl$estimate[cl$measure == "sp"]))
  expect_equal(cl$n[cl$measure == "sp"], 0)
  s <- classification_by_stratum(c(TRUE, TRUE, FALSE), c(TRUE, TRUE, TRUE), c("a", "b", "b"))
  expect_true(all(is.na(s$estimate[s$measure == "sp"])))
})

test_that("auc_ci and classification_by_stratum", {
  a <- auc_ci(c(1, 2, 3, 4), c(FALSE, FALSE, TRUE, TRUE), reps = 200, seed = 1)
  expect_equal(a[["estimate"]], 1)
  set.seed(2)
  ref <- rep(c(TRUE, FALSE), 100)
  stratum <- rep(c("a", "b"), each = 100)
  test <- ifelse(stratum == "a", ref, stats::runif(200) < 0.5)
  s <- classification_by_stratum(test, ref, stratum)
  expect_setequal(unique(s$stratum), c("a", "b"))
  expect_equal(s$estimate[s$measure == "se" & s$stratum == "a"], 1)
  expect_lt(s$p_differs[s$measure == "se"][1], 0.001)
  expect_true(is.na(s$difference[s$measure == "se" & s$stratum == "a"]))
  expect_lt(s$difference[s$measure == "se" & s$stratum == "b"], 0)
  expect_true(all(c("difference", "difference_lo", "difference_hi") %in% names(s)))
})

test_that("hodges_lehmann's estimate is the median of the pairwise differences", {
  # x - y over all pairs: -1, 1, 2, 4, 7, 9, so the median is (2 + 4) / 2 = 3 exactly
  # (wilcox.test's root-finding estimate is 2.958)
  hl <- hodges_lehmann(c(1, 4, 9, NA), c(0, 2))
  expect_identical(hl[["estimate"]], 3)
  w <- stats::wilcox.test(c(1, 4, 9), c(0, 2), conf.int = TRUE, exact = FALSE)
  expect_equal(unname(hl[c("lo", "hi")]), unname(w$conf.int[1:2]))
  # zero-inflated groups: most pairwise differences are exactly 0
  hl0 <- hodges_lehmann(c(rep(0, 8), 5, 9), c(rep(0, 7), 1, 2, 3))
  expect_identical(hl0[["estimate"]], 0)
})

test_that("only wilcox.test's exact/ties warnings are muffled", {
  expect_no_warning(quiet_exact_ties(warning("cannot compute exact p-value with ties")))
  expect_no_warning(quiet_exact_ties(warning("cannot compute exact confidence intervals with ties")))
  expect_warning(quiet_exact_ties(warning("something else")), "something else")
  expect_identical(quiet_exact_ties(42), 42)
  # a confidence interval that cannot be computed is not hidden
  expect_warning(
    quiet_exact_ties(warning("cannot compute confidence interval when all observations are tied")),
    "all observations are tied"
  )
})

test_that("jonckheere takes a factor or integer-valued groups and rejects anything else", {
  x <- c(3, 1, 2, 6, 5, 4, 9, 8, 7)
  f <- factor(rep(c("none", "lower", "upper"), each = 3), levels = c("none", "lower", "upper"))
  by_factor <- jonckheere(x, f, permutations = 199, seed = 1)
  expect_equal(by_factor[["statistic"]], 27)
  expect_identical(jonckheere(x, rep(c(0, 1, 2), each = 3), permutations = 199, seed = 1), by_factor)
  expect_identical(jonckheere(x, rep(c(10L, 20L, 30L), each = 3), permutations = 199, seed = 1),
                   by_factor)
  expect_error(jonckheere(x, as.character(f)), "factor or integer-valued")
  expect_error(jonckheere(x, rep(c(0.5, 1, 1.5), each = 3)), "factor or integer-valued")
  expect_error(jonckheere(x, rep(c(TRUE, FALSE, TRUE), each = 3)), "factor or integer-valued")
})

# The caller's stream after `f()` should be the stream it would have had without the call, and a
# caller without a seed should still have none afterwards.
expect_rng_untouched <- function(f) {
  set.seed(99)
  expected <- stats::runif(3)
  set.seed(99)
  f()
  expect_identical(stats::runif(3), expected)
  rm(".Random.seed", envir = globalenv())
  f()
  expect_false(exists(".Random.seed", envir = globalenv(), inherits = FALSE))
  set.seed(1)
}

test_that("seeded statistics leave the caller's random-number stream alone", {
  x <- c(3, 1, 2, 6, 5, 4, 9, 8, 7)
  g <- rep(c(0, 1, 2), each = 3)
  expect_rng_untouched(function() jonckheere(x, g, permutations = 50, seed = 5))
  score <- c(0.1, 0.4, 0.35, 0.8, 0.7, 0.2, 0.9)
  ref <- c(FALSE, FALSE, TRUE, TRUE, TRUE, FALSE, TRUE)
  expect_rng_untouched(function() auc_ci(score, ref, reps = 50, seed = 5))
  # the same seed still gives the same draws as set.seed(seed) followed by the computation
  set.seed(5)
  perm <- replicate(50, jt_statistic(sample(x), g))
  jt <- jonckheere(x, g, permutations = 50, seed = 5)
  expect_identical(jt[["p"]], (1 + sum(perm >= jt[["statistic"]])) / 51)
  expect_identical(jonckheere(x, g, permutations = 50, seed = 5), jt)
  expect_identical(auc_ci(score, ref, reps = 50, seed = 5), auc_ci(score, ref, reps = 50, seed = 5))
})

test_that("median_regression's bootstrap leaves the caller's random-number stream alone", {
  skip_if_not_installed("quantreg")
  d <- data.frame(y = c(rep(c(1, 2, 3), 10), rep(c(4, 5, 6), 10)), group = rep(c(0, 1), each = 30))
  expect_rng_untouched(function() median_regression(y ~ group, d, "group", se = "boot", reps = 20))
})

test_that("classification gets each measure's counts right on an asymmetric table", {
  # tp 4, fn 1, fp 2, tn 3
  test <- c(TRUE, TRUE, TRUE, TRUE, FALSE, TRUE, TRUE, FALSE, FALSE, FALSE)
  ref <- c(TRUE, TRUE, TRUE, TRUE, TRUE, FALSE, FALSE, FALSE, FALSE, FALSE)
  cl <- classification(test, ref)
  expect_equal(cl$k, c(4, 3, 4, 3))
  expect_equal(cl$n, c(5, 5, 6, 4))
  expect_equal(cl$estimate, c(4 / 5, 3 / 5, 4 / 6, 3 / 4))
  # Wilson's limits are the two roots of (k/n - p)^2 = 1.96^2 p (1 - p) / n
  score_gap <- function(p, k, n) (k / n - p)^2 - 1.96^2 * p * (1 - p) / n
  for (i in seq_len(nrow(cl))) {
    expect_equal(score_gap(c(cl$lo[i], cl$hi[i]), cl$k[i], cl$n[i]), c(0, 0), info = cl$measure[i])
    expect_true(cl$lo[i] < cl$estimate[i] && cl$estimate[i] < cl$hi[i], info = cl$measure[i])
  }
})

test_that("auc_ci's estimate and percentile interval on an asymmetric fixture", {
  score <- c(0.1, 0.4, 0.35, 0.8, 0.7, 0.2, 0.9, 0.35, 0.6)
  ref <- c(FALSE, FALSE, TRUE, TRUE, TRUE, FALSE, TRUE, FALSE, NA)
  a <- auc_ci(score, ref, reps = 300, seed = 7)
  # P(case score > non-case score) over the 4 x 4 pairs, ties counting one half
  pair_auc <- function(s, r) {
    if (!any(r) || all(r)) return(NA_real_)
    mean(outer(s[r], s[!r], ">") + 0.5 * outer(s[r], s[!r], "=="))
  }
  expect_equal(a[["estimate"]], 14.5 / 16)
  s <- score[1:8]
  r <- ref[1:8]
  set.seed(7)
  boots <- replicate(300, {
    i <- sample.int(8, replace = TRUE)
    pair_auc(s[i], r[i])
  })
  expected <- stats::quantile(boots, c(0.025, 0.975), na.rm = TRUE, names = FALSE)
  expect_equal(unname(a[c("lo", "hi")]), expected)
  expect_lt(a[["lo"]], a[["estimate"]])
})

test_that("median_regression's CI is the estimate +/- 1.96 quantreg standard errors", {
  skip_if_not_installed("quantreg")
  d <- data.frame(y = c(1, 1, 2, 3, 8, 2, 5, 9, 14, 30, 4, 6, 7, 20, 3),
                  group = c(0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 1, 1, 0))
  fit <- quiet_nonunique(quantreg::rq(y ~ group, tau = 0.5, data = d))
  nid <- quiet_nonunique(summary(fit, se = "nid"))$coefficients["group", ]
  est <- median_regression(y ~ group, d, "group")
  expect_equal(est[["estimate"]], nid[["Value"]])
  expect_equal(est[["lo"]], nid[["Value"]] - 1.96 * nid[["Std. Error"]])
  expect_equal(est[["hi"]], nid[["Value"]] + 1.96 * nid[["Std. Error"]])
})

test_that("median_regression's n is the complete-case frame it fits", {
  skip_if_not_installed("quantreg")
  d <- data.frame(y = c(1, 1, 2, 3, 8, 2, 5, 9, 14, 30, 4, 6, 7, 20, 3),
                  group = c(0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 1, 1, 0),
                  unused = NA)
  d$y[2] <- NA
  d$group[9] <- NA
  est <- median_regression(y ~ group, d, "group")
  expect_equal(est[["n"]], 13)
  complete <- d[-c(2, 9), c("y", "group")]
  fit <- quiet_nonunique(quantreg::rq(y ~ group, tau = 0.5, data = complete))
  expect_equal(est[["estimate"]], unname(stats::coef(fit)[["group"]]))
  expect_equal(est[["n"]], length(stats::residuals(fit)))
})

test_that("classification_by_stratum: difference CIs, and p_differs with an empty cell", {
  # stratum a (reference): Se 48/80, Sp 21/30; stratum b: Se 56/70 and no device non-walkers.
  # b - a is Newcombe's (1998) worked example: 0.2000 (0.0524, 0.3339).
  test <- c(rep(TRUE, 48), rep(FALSE, 32), rep(FALSE, 21), rep(TRUE, 9), rep(TRUE, 56), rep(FALSE, 14))
  ref <- c(rep(TRUE, 80), rep(FALSE, 30), rep(TRUE, 70))
  stratum <- rep(c("a", "b"), c(110, 70))
  s <- classification_by_stratum(test, ref, stratum)
  se_b <- s[s$measure == "se" & s$stratum == "b", ]
  expect_equal(c(se_b$difference, se_b$difference_lo, se_b$difference_hi), c(0.2000, 0.0524, 0.3339),
               tolerance = 1e-4)
  sp <- s[s$measure == "sp", ]
  expect_equal(sp$n, c(30, 0))
  expect_true(is.na(sp$estimate[sp$stratum == "b"]))
  expect_true(all(is.na(c(sp$difference, sp$difference_lo, sp$difference_hi))))
  # Sp cannot be compared across strata when one stratum has no device non-walkers
  expect_true(all(is.na(sp$p_differs)))
  # Se's p-value is the likelihood-ratio test of stratum on agreement among device walkers
  correct <- (test == ref)[ref]
  st <- factor(stratum[ref])
  lrt <- stats::anova(stats::glm(correct ~ 1, family = stats::binomial),
                      stats::glm(correct ~ st, family = stats::binomial), test = "LRT")[2, "Pr(>Chi)"]
  expect_equal(s$p_differs[s$measure == "se"], c(lrt, lrt))
})

test_that("classification_by_stratum returns an empty frame for all-missing input", {
  full <- classification_by_stratum(c(TRUE, FALSE, TRUE), c(TRUE, FALSE, FALSE), c("a", "a", "b"))
  empty <- classification_by_stratum(c(NA, TRUE), c(TRUE, NA), c("a", "b"))
  expect_equal(nrow(empty), 0)
  expect_identical(names(empty), names(full))
  expect_identical(vapply(empty, class, ""), vapply(full, class, ""))
  expect_equal(nrow(classification_by_stratum(c(TRUE, FALSE), c(TRUE, FALSE), c(NA, NA))), 0)
})

test_that("wilson takes one count of one total and checks it", {
  expect_true(all(is.na(wilson(0, 0))))
  expect_equal(names(wilson(0, 3)), c("estimate", "lo", "hi"))
  expect_error(wilson(6, 5), "0 <= k <= n")
  expect_error(wilson(-1, 5), "0 <= k <= n")
  expect_error(wilson(NA, 5), "0 <= k <= n")
  expect_error(wilson(1, -2), "0 <= k <= n")
  expect_error(wilson(c(1, 2), c(5, 5)), "one count")
  expect_error(newcombe_diff(8, 5, 1, 5), "0 <= k <= n")
})
