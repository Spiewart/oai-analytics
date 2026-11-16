d <- data.frame(ID = c(3, 1, 2, 1, 4), event = c(1, 0, 1, NA, 0), x = c(1, 0, 1, 1, 0),
                age = c(60, NA, 70, 65, 55), kl = c(1, 2, NA, 0, 1))

test_that("model_needs reads variables out of factor(), offset() and interactions", {
  expect_equal(model_needs(c("factor(x)", "age", "offset(log(span))")),
               c("event", "x", "age", "span"))
  expect_equal(model_needs("x * age", outcome = "y"), c("y", "x", "age"))
})

test_that("model_samples: per_model keeps each model's own complete cases, ordered by ID", {
  s <- model_samples(d, list(unadj = "x", adj = c("x", "age")))
  expect_equal(s$unadj$ID, c(1, 2, 3, 4))
  expect_equal(s$adj$ID, c(2, 3, 4))
})

test_that("model_samples: common fits every model on the complete cases of all", {
  s <- model_samples(d, c(unadj = "factor(x)", adj = "factor(x) + age + factor(kl)"), "common")
  expect_equal(s$unadj$ID, c(3, 4))
  expect_identical(s$unadj, s$adj)
})

test_that("level_events counts events per level, 0 for an empty requested level", {
  expect_equal(as.vector(level_events(d[!is.na(d$event), ], "x")), c(0, 2))
  expect_equal(level_events(d[!is.na(d$event), ], "x", levels = c(0, 1, 2)),
               c("0" = 0, "1" = 2, "2" = 0))
})

test_that("sparse_levels flags levels under the threshold and missing counts", {
  expect_equal(sparse_levels(c(a = 5, b = 4, c = NA), 5), c(a = FALSE, b = TRUE, c = TRUE))
})

test_that("discrete_time_terms: interval factor when it varies, log-span offset when given", {
  p <- data.frame(end_visit = c("05", "06"), span = 1)
  expect_equal(discrete_time_terms(p, "end_visit", "span"),
               c("factor(end_visit)", "offset(log(span))"))
  expect_equal(discrete_time_terms(p[1, ], "end_visit"), character())
})

test_that("fit_cluster_gee matches geeglm on integer clusters, whatever the row order", {
  skip_if_not_installed("geepack")
  set.seed(1)
  n <- 120
  g <- data.frame(ID = as.character(rep(100001 + 0:59, each = 2)), x = rbinom(n, 1, 0.5))
  g$event <- rbinom(n, 1, plogis(-0.5 + 0.8 * g$x))
  g$cl <- match(g$ID, unique(g$ID))
  ref <- geepack::geeglm(event ~ x, id = cl, data = g, family = stats::binomial,
                         corstr = "exchangeable")
  fit <- fit_cluster_gee(g[sample(n), ], "x", "event")
  expect_equal(stats::coef(fit), stats::coef(ref))
  expect_equal(summary(fit)$coefficients, summary(ref)$coefficients)
  cl <- fit_cluster_gee(g, "x", "event", stats::binomial(link = "cloglog"), "independence")
  expect_equal(cl$family$link, "cloglog")
})
