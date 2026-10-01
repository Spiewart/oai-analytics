clustered <- function(seed = 1) {
  set.seed(seed)
  n <- 200
  d <- data.frame(ID = rep(seq_len(n), each = 2), walker = rep(stats::runif(n) < 0.6, each = 2),
                  age = rep(stats::rnorm(n, 60, 8), each = 2))
  d$y <- stats::rbinom(nrow(d), 1, stats::plogis(-1 + 0.5 * d$walker))
  d
}

test_that("fit_knee_gee matches a direct geeglm fit", {
  skip_if_not_installed("geepack")
  d <- clustered()
  est <- fit_knee_gee(d, "walker + age")
  direct <- geepack::geeglm(y ~ walker + age, id = ID, data = d, family = stats::binomial,
                            corstr = "exchangeable")
  co <- summary(direct)$coefficients["walkerTRUE", ]
  expect_equal(est[["log_or"]], co[["Estimate"]])
  expect_equal(est[["se"]], co[["Std.err"]])
  expect_equal(est[["or"]], exp(co[["Estimate"]]))
  expect_equal(est[["lo"]], exp(co[["Estimate"]] - 1.96 * co[["Std.err"]]))
  expect_equal(est[["hi"]], exp(co[["Estimate"]] + 1.96 * co[["Std.err"]]))
})

test_that("fit_knee_gee orders clusters itself and names a missing term", {
  skip_if_not_installed("geepack")
  d <- clustered()
  shuffled <- d[sample(nrow(d)), ]
  expect_equal(fit_knee_gee(shuffled, "walker"), fit_knee_gee(d, "walker"))
  expect_error(fit_knee_gee(d, "age"), "walkerTRUE")
})
