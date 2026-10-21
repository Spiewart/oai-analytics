test_that("fit_logit recovers a known log odds ratio", {
  set.seed(1)
  n <- 5000
  d <- data.frame(x = stats::rbinom(n, 1, 0.5))
  d$y <- stats::rbinom(n, 1, stats::plogis(-1 + 0.7 * d$x))
  est <- fit_logit(d, "x", term = "x")
  expect_named(est, c("or", "lo", "hi", "log_or", "se"))
  expect_lt(abs(est[["log_or"]] - 0.7), 0.1)
  expect_true(est[["lo"]] < est[["or"]] && est[["or"]] < est[["hi"]])
})

test_that("fit_logit accepts a logical outcome column by name", {
  set.seed(2)
  d <- data.frame(x = stats::rbinom(500, 1, 0.5))
  d$event <- stats::runif(500) < stats::plogis(-1 + d$x)
  expect_silent(fit_logit(d, "x", outcome = "event", term = "x"))
})

test_that("fit_logit rejects an unknown term", {
  d <- data.frame(x = c(0, 1, 0, 1, 1, 0), y = c(0, 1, 0, 1, 0, 1))
  expect_error(fit_logit(d, "x", term = "z"), "not in the model")
})
