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

test_that("fit_knee_gee honours non-default id, outcome, corstr and term", {
  skip_if_not_installed("geepack")
  d <- clustered()
  default <- fit_knee_gee(d, "walker + age")
  renamed <- d
  names(renamed)[names(renamed) == "ID"] <- "person"
  names(renamed)[names(renamed) == "y"] <- "event"
  expect_equal(fit_knee_gee(renamed, "walker + age", outcome = "event", id = "person"), default)

  # corstr only matters with a covariate that varies within a cluster
  set.seed(2)
  d$knee_kl <- stats::rbinom(nrow(d), 3, 0.4)
  d$y <- stats::rbinom(nrow(d), 1, stats::plogis(-1 + 0.5 * d$walker + 0.4 * d$knee_kl))
  independence <- fit_knee_gee(d, "walker + knee_kl", corstr = "independence")
  direct <- geepack::geeglm(y ~ walker + knee_kl, id = ID, data = d, family = stats::binomial,
                            corstr = "independence")
  co <- summary(direct)$coefficients["walkerTRUE", ]
  expect_equal(independence[["log_or"]], co[["Estimate"]])
  expect_equal(independence[["se"]], co[["Std.err"]])
  exchangeable <- fit_knee_gee(d, "walker + knee_kl")
  expect_false(isTRUE(all.equal(independence[["log_or"]], exchangeable[["log_or"]])))

  kl <- fit_knee_gee(d, "walker + knee_kl", term = "knee_kl")
  direct <- geepack::geeglm(y ~ walker + knee_kl, id = ID, data = d, family = stats::binomial,
                            corstr = "exchangeable")
  expect_equal(kl[["log_or"]], summary(direct)$coefficients["knee_kl", "Estimate"])
})

test_that("fit_knee_gee leaves a .cluster column alone and clusters on id", {
  skip_if_not_installed("geepack")
  d <- clustered()
  expected <- fit_knee_gee(d, "walker + age")
  # one cluster for every row would change the sandwich SE if fit_knee_gee clustered on it
  d$.cluster <- 1L
  expect_equal(fit_knee_gee(d, "walker + age"), expected)
  # a covariate called .cluster is still the caller's column, not the cluster id
  d$.cluster <- stats::rnorm(nrow(d))
  direct <- geepack::geeglm(y ~ walker + .cluster, id = ID, data = d, family = stats::binomial,
                            corstr = "exchangeable")
  expect_equal(fit_knee_gee(d, "walker + .cluster")[["log_or"]],
               summary(direct)$coefficients["walkerTRUE", "Estimate"])
})

test_that("fit_knee_gee uses no undeclared global variables", {
  skip_if_not_installed("codetools")
  found <- character()
  codetools::checkUsage(fit_knee_gee, all = TRUE, report = function(x) found <<- c(found, x))
  expect_false(any(grepl("no visible binding", found)), info = paste(found, collapse = "\n"))
})

test_that("fit_knee_gee rejects a non-0/1 outcome and missing ids", {
  skip_if_not_installed("geepack")
  d <- clustered()
  counts <- d
  counts$y[1] <- 2
  expect_error(fit_knee_gee(counts, "walker"), "y must be 0/1")
  labels <- d
  labels$y <- ifelse(labels$y == 1, "yes", "no")
  expect_error(fit_knee_gee(labels, "walker"), "y must be 0/1")
  no_id <- d
  no_id$ID[c(3, 10)] <- NA
  expect_error(fit_knee_gee(no_id, "walker"), "2 rows have no ID")
  expect_error(fit_knee_gee(d, "walker", outcome = "event"), "no column event")
  expect_error(fit_knee_gee(d, "walker", id = "person"), "no column person")
  # a logical 0/1 outcome and missing outcomes (dropped by the model frame) are accepted
  logical_y <- d
  logical_y$y <- logical_y$y == 1
  expect_equal(fit_knee_gee(logical_y, "walker"), fit_knee_gee(d, "walker"))
  some_na <- d
  some_na$y[5] <- NA
  expect_no_error(fit_knee_gee(some_na, "walker"))
})
