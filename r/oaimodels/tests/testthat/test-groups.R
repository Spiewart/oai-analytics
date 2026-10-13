make_groups <- function() {
  set.seed(5)
  n <- 240
  group <- factor(sample(c("no", "a", "b"), n, replace = TRUE), levels = c("no", "a", "b"))
  age <- stats::rnorm(n, 65, 8)
  sex <- sample(1:2, n, replace = TRUE)
  shift <- c(no = 0, a = 10, b = 30)[as.character(group)]
  y <- pmax(0, stats::rnorm(n, 100 + shift - 0.8 * (age - 65), 25))
  y[c(3, 7)] <- NA
  list(y = y, group = group, covariates = data.frame(age = age, sex = sex))
}

test_that("group_summaries gives medians and quartiles, or shares with Wilson intervals", {
  d <- make_groups()
  s <- group_summaries(d$y, d$group)
  expect_equal(s$level, c("no", "a", "b"))
  no <- d$y[d$group == "no" & !is.na(d$y)]
  expect_equal(s$n[1], length(no))
  expect_equal(c(s$estimate[1], s$lo[1], s$hi[1]), unname(stats::quantile(no, c(0.5, 0.25, 0.75))))
  b <- group_summaries(d$y > 100, d$group)
  k <- sum(d$y[d$group == "a"] > 100, na.rm = TRUE); m <- sum(!is.na(d$y[d$group == "a"]))
  expect_equal(c(b$estimate[2], b$lo[2], b$hi[2]), unname(wilson(k, m)))
})

test_that("group_contrasts compares each level with the first: Hodges-Lehmann, Wilcoxon, Holm", {
  d <- make_groups()
  out <- group_contrasts(d$y, d$group, se = "nid")
  expect_equal(out$level, c("a", "b"))
  expect_equal(out$effect, rep("median_difference", 2))
  hl <- hodges_lehmann(d$y[d$group == "b"], d$y[d$group == "no"])
  expect_equal(c(out$estimate[2], out$lo[2], out$hi[2]), unname(hl))
  marks <- vs_reference(d$y, d$group, test = "wilcoxon")
  expect_equal(out$p, marks$p)
  expect_equal(out$p_holm, marks$p_adj)
  expect_true(all(is.na(out$adj_estimate)))  # no covariates, no adjusted contrast
})

test_that("group_contrasts adjusts numeric outcomes by median regression on every level at once", {
  skip_if_not_installed("quantreg")
  d <- make_groups()
  out <- group_contrasts(d$y, d$group, covariates = d$covariates, se = "nid")
  data <- data.frame(y = d$y, group = d$group, d$covariates)
  fit <- suppressWarnings(quantreg::rq(y ~ group + age + sex, tau = 0.5, data = stats::na.omit(data)))
  expect_equal(out$adj_estimate, unname(stats::coef(fit)[c("groupa", "groupb")]))
  expect_equal(out$adj_effect, rep("median_difference", 2))
  se <- (out$adj_hi - out$adj_lo) / (2 * 1.96)
  expect_equal(out$adj_p, 2 * stats::pnorm(-abs(out$adj_estimate / se)))
  expect_equal(out$adj_p_holm, stats::p.adjust(out$adj_p, "holm"))
  expect_equal(out$adj_n, rep(nrow(stats::na.omit(data)), 2))
})

test_that("group_contrasts gives risk differences and adjusted odds ratios for a yes/no outcome", {
  d <- make_groups()
  y <- d$y > 110
  out <- group_contrasts(y, d$group, covariates = d$covariates)
  a <- y[d$group == "a" & !is.na(y)]; r <- y[d$group == "no" & !is.na(y)]
  expect_equal(c(out$estimate[1], out$lo[1], out$hi[1]),
               unname(newcombe_diff(sum(a), length(a), sum(r), length(r))))
  expect_equal(out$effect, rep("risk_difference", 2))
  expect_equal(out$p, vs_reference(y, d$group, test = "fisher")$p)
  fit <- stats::glm(y ~ group + age + sex, family = stats::binomial(),
                    data = data.frame(y = y, group = d$group, d$covariates))
  expect_equal(out$adj_estimate, unname(exp(stats::coef(fit)[c("groupa", "groupb")])))
  expect_equal(out$adj_effect, rep("odds_ratio", 2))
  expect_equal(out$adj_p, unname(summary(fit)$coefficients[c("groupa", "groupb"), 4]))
})

test_that("group_contrasts gives NA for an empty level and rejects bad input", {
  skip_if_not_installed("quantreg")
  d <- make_groups()
  group <- factor(as.character(d$group), levels = c("no", "a", "b", "empty"))
  out <- group_contrasts(d$y, group, covariates = d$covariates, se = "nid")
  expect_equal(out$level, c("a", "b", "empty"))
  expect_true(is.na(out$estimate[3]) && is.na(out$p[3]) && is.na(out$adj_estimate[3]))
  expect_equal(out$n[3], 0L)
  expect_error(group_contrasts(d$y, as.character(d$group)), "factor")
  expect_error(group_contrasts(as.character(d$y), d$group), "numeric or logical")
  expect_error(group_contrasts(d$y, d$group, covariates = d$covariates[1:5, ]), "rows")
})
