# Walker models and the divergence rule. Synthetic data only.
skip_if_not_installed("nlme")
skip_if_not_installed("geepack")

periods <- list(before = c("00", "01"), at = "10", after = c("13", "14"))
period_of <- function(visit) {
  c(`00` = "before", `01` = "before", `10` = "at", `13` = "after", `14` = "after")[visit]
}
visits <- c("00", "01", "10", "13", "14")

# One row per person and visit; `gap` is the true Walker difference in each period, named.
sim_gaussian <- function(n, gap, walker_share = 0.5) {
  id <- rep(seq_len(n), each = length(visits))
  walker <- rep(stats::rbinom(n, 1, walker_share) == 1, each = length(visits))
  age <- rep(stats::rnorm(n, 60, 8), each = length(visits))
  person <- rep(stats::rnorm(n, 0, 8), each = length(visits))
  visit <- rep(visits, n)
  value <- 50 + match(visit, visits) + 0.3 * (age - 60) + person +
    walker * unname(gap[period_of(visit)]) + stats::rnorm(n * length(visits), 0, 5)
  data.frame(ID = id, visit = visit, value = value, walker_yes = walker, age = age)
}

# Correlated within person, with a logistic margin at each visit, so the odds ratio given is the
# marginal one a GEE estimates.
sim_binary <- function(n, or) {
  id <- rep(seq_len(n), each = length(visits))
  walker <- rep(stats::rbinom(n, 1, 0.5) == 1, each = length(visits))
  person <- rep(stats::rnorm(n), each = length(visits))
  visit <- rep(visits, n)
  linear <- -0.4 + 0.1 * match(visit, visits) + walker * log(unname(or[period_of(visit)]))
  latent <- sqrt(0.4) * person + sqrt(0.6) * stats::rnorm(n * length(visits))
  data.frame(ID = id, visit = visit, value = as.integer(latent < stats::qnorm(stats::plogis(linear))),
             walker_yes = walker, age = stats::rnorm(n * length(visits), 60, 8))
}

constant <- function(x) c(before = x, at = x, after = x)

test_that("gaussian overall recovers a true difference of 10", {
  set.seed(101)
  d <- sim_gaussian(400, constant(10))
  r <- walker_model(d, "age", "overall", "gaussian", periods)
  expect_equal(nrow(r), 1L)
  expect_equal(r$term, "overall")
  expect_equal(r$scale, "difference")
  expect_true(r$converged)
  expect_lt(abs(r$estimate - 10), 2)
  expect_lt(r$lo, 10)
  expect_gt(r$hi, 10)
  expect_lt(r$p, 0.001)
  expect_equal(r$n_people, 400L)
  expect_equal(r$n_obs, 2000L)
})

test_that("binomial overall recovers a true OR of 2", {
  set.seed(102)
  d <- sim_binary(800, constant(2))
  r <- walker_model(d, "age", "overall", "binomial", periods)
  expect_equal(r$scale, "or")
  expect_true(r$converged)
  expect_lt(r$lo, 2)
  expect_gt(r$hi, 2)
  expect_gt(r$estimate, 1.4)
  expect_lt(r$estimate, 2.8)
  expect_lt(r$p, 0.001)
})

test_that("period test separates a changing gap from a constant one", {
  set.seed(103)
  changing <- sim_gaussian(300, c(before = 5, at = 10, after = 15))
  constant_gap <- sim_gaussian(300, constant(10))
  expect_lt(attr(walker_model(changing, "age", "period", "gaussian", periods), "period_test"), 0.05)
  expect_gt(attr(walker_model(constant_gap, "age", "period", "gaussian", periods), "period_test"), 0.05)

  binary_changing <- sim_binary(800, c(before = 1.2, at = 2, after = 4))
  binary_constant <- sim_binary(800, constant(2))
  expect_lt(attr(walker_model(binary_changing, "age", "period", "binomial", periods), "period_test"), 0.05)
  expect_gt(attr(walker_model(binary_constant, "age", "period", "binomial", periods), "period_test"), 0.05)
})

test_that("the period test is the same whichever rows are asked for", {
  set.seed(104)
  d <- sim_gaussian(100, c(before = 5, at = 10, after = 15))
  tests <- vapply(c("overall", "period", "visit"), function(s) {
    attr(walker_model(d, character(), s, "gaussian", periods), "period_test")
  }, numeric(1))
  expect_equal(tests[["overall"]], tests[["period"]])
  expect_equal(tests[["visit"]], tests[["period"]])
})

test_that("the gaussian period test is the likelihood ratio between ML fits", {
  set.seed(105)
  d <- sim_gaussian(150, c(before = 5, at = 10, after = 15))
  got <- attr(walker_model(d, "age", "overall", "gaussian", periods), "period_test")
  d$w <- as.numeric(d$walker_yes)
  d$w_at <- d$w * (period_of(d$visit) == "at")
  d$w_after <- d$w * (period_of(d$visit) == "after")
  null <- nlme::lme(value ~ w + factor(visit) + age, random = ~ 1 | ID, data = d, method = "ML")
  alt <- nlme::lme(value ~ w + w_at + w_after + factor(visit) + age, random = ~ 1 | ID, data = d,
                   method = "ML")
  expect_equal(got, stats::anova(null, alt)$`p-value`[2], tolerance = 1e-5)
})

test_that("per-period and per-visit gaussian rows are those periods' own contrasts", {
  # Balanced with everyone at every visit: the contrast is the plain difference in means, by hand.
  set.seed(106)
  d <- sim_gaussian(200, c(before = 5, at = 10, after = 15))
  by_period <- walker_model(d, character(), "period", "gaussian", periods)
  expect_equal(by_period$term, c("before", "at", "after"))
  for (p in names(periods)) {
    rows <- d[d$visit %in% periods[[p]], ]
    hand <- mean(rows$value[rows$walker_yes]) - mean(rows$value[!rows$walker_yes])
    expect_equal(by_period$estimate[by_period$term == p], hand, tolerance = 1e-6)
  }
  by_visit <- walker_model(d, character(), "visit", "gaussian", periods)
  expect_equal(by_visit$term, visits)
  for (v in visits) {
    rows <- d[d$visit == v, ]
    hand <- mean(rows$value[rows$walker_yes]) - mean(rows$value[!rows$walker_yes])
    expect_equal(by_visit$estimate[by_visit$term == v], hand, tolerance = 1e-6)
  }
})

test_that("per-period rows match the linear combination from a main-effect parameterization", {
  # Unbalanced and adjusted, so no plain mean difference applies: estimate and SE come from the
  # coefficients and variance-covariance matrix of the interaction parameterization.
  set.seed(107)
  d <- sim_gaussian(300, c(before = 5, at = 10, after = 15))
  d$value[stats::runif(nrow(d)) < 0.1 + 0.2 * (d$visit %in% c("13", "14"))] <- NA
  r <- walker_model(d, "age", "period", "gaussian", periods)

  f <- d[!is.na(d$value), ]
  f$w <- as.numeric(f$walker_yes)
  f$w_at <- f$w * (period_of(f$visit) == "at")
  f$w_after <- f$w * (period_of(f$visit) == "after")
  ref <- nlme::lme(value ~ w + w_at + w_after + factor(visit) + age, random = ~ 1 | ID, data = f,
                   method = "ML")
  b <- nlme::fixef(ref)
  v <- stats::vcov(ref)
  for (p in c("at", "after")) {
    term <- paste0("w_", p)
    hand <- b[["w"]] + b[[term]]
    hand_se <- sqrt(v["w", "w"] + v[term, term] + 2 * v["w", term])
    row <- r[r$term == p, ]
    expect_equal(row$estimate, hand, tolerance = 1e-4)
    # The interval's half width over the normal quantile; n is large enough for t to be near it.
    expect_equal((row$hi - row$lo) / (2 * stats::qnorm(0.975)), hand_se, tolerance = 0.01)
  }
  expect_equal(r$estimate[r$term == "before"], b[["w"]], tolerance = 1e-4)
  expect_equal(r$n_obs[1], nrow(f))
})

test_that("per-visit binomial rows are each visit's own odds ratio", {
  # An independence working correlation with no covariates reproduces each visit's 2 x 2 table.
  set.seed(108)
  d <- sim_binary(500, c(before = 1.2, at = 2, after = 4))
  r <- walker_model(d, character(), "visit", "binomial", periods, corstr = "independence")
  expect_equal(r$term, visits)
  for (v in visits) {
    rows <- d[d$visit == v, ]
    a <- sum(rows$walker_yes & rows$value == 1)
    b <- sum(rows$walker_yes & rows$value == 0)
    c <- sum(!rows$walker_yes & rows$value == 1)
    e <- sum(!rows$walker_yes & rows$value == 0)
    expect_equal(r$estimate[r$term == v], (a / b) / (c / e), tolerance = 1e-5)
  }
})

test_that("per-period binomial rows and the Wald test match a main-effect parameterization", {
  set.seed(109)
  d <- sim_binary(600, c(before = 1.2, at = 2, after = 4))
  r <- walker_model(d, "age", "period", "binomial", periods)
  d$w <- as.numeric(d$walker_yes)
  d$w_at <- d$w * (period_of(d$visit) == "at")
  d$w_after <- d$w * (period_of(d$visit) == "after")
  d <- d[order(d$ID, d$visit), ]
  ref <- geepack::geeglm(value ~ w + w_at + w_after + factor(visit) + age, id = ID, data = d,
                         family = stats::binomial, corstr = "exchangeable")
  null <- geepack::geeglm(value ~ w + factor(visit) + age, id = ID, data = d,
                          family = stats::binomial, corstr = "exchangeable")
  b <- stats::coef(ref)
  v <- ref$geese$vbeta
  dimnames(v) <- list(names(b), names(b))
  hand <- b[["w"]] + b[["w_after"]]
  hand_se <- sqrt(v["w", "w"] + v["w_after", "w_after"] + 2 * v["w", "w_after"])
  row <- r[r$term == "after", ]
  expect_equal(r$scale, rep("or", 3))
  expect_equal(row$estimate, exp(hand), tolerance = 1e-5)
  expect_equal(row$lo, exp(hand - stats::qnorm(0.975) * hand_se), tolerance = 1e-4)
  expect_equal(row$hi, exp(hand + stats::qnorm(0.975) * hand_se), tolerance = 1e-4)
  expect_equal(row$p, 2 * stats::pnorm(-abs(hand / hand_se)), tolerance = 1e-3)
  expect_equal(attr(r, "period_test"), stats::anova(ref, null)$`P(>|Chi|)`[1], tolerance = 1e-3)
})

test_that("TRUE against FALSE is the contrast direction, for logical and 0/1 walker_yes", {
  set.seed(110)
  d <- sim_gaussian(100, constant(10))
  logical_fit <- walker_model(d, character(), "overall", "gaussian", periods)
  expect_gt(logical_fit$estimate, 0)
  d$walker_yes <- as.integer(d$walker_yes)
  expect_equal(walker_model(d, character(), "overall", "gaussian", periods)$estimate,
               logical_fit$estimate)
})

test_that("a null value or covariate drops the row and the counts say what was fitted", {
  set.seed(111)
  d <- sim_gaussian(50, constant(10))
  d$value[d$ID == 1] <- NA
  d$age[d$ID == 2 & d$visit == "00"] <- NA
  r <- walker_model(d, "age", "overall", "gaussian", periods)
  expect_equal(r$n_people, 49L)
  expect_equal(r$n_obs, 244L)
  # The extra covariate is what removes the row: without it the same person's row stays
  expect_equal(walker_model(d, character(), "overall", "gaussian", periods)$n_obs, 245L)
})

test_that("row order, ID type and covariate names do not change the fit", {
  set.seed(122)
  d <- sim_binary(200, constant(2))
  sorted <- walker_model(d, "age", "period", "binomial", periods)
  shuffled <- d[sample(nrow(d)), ]
  expect_equal(walker_model(shuffled, "age", "period", "binomial", periods), sorted)
  # geepack alone would read a character ID as NA
  labelled <- transform(d, ID = paste0("P", ID))
  expect_equal(walker_model(labelled, "age", "period", "binomial", periods)$estimate, sorted$estimate)
  expect_equal(walker_model(labelled, "age", "period", "binomial", periods)$n_people, rep(200L, 3))

  g <- sim_gaussian(100, constant(10))
  plain <- walker_model(g, "age", "overall", "gaussian", periods)
  odd <- g
  names(odd)[names(odd) == "age"] <- "age at visit"
  expect_equal(walker_model(odd, "age at visit", "overall", "gaussian", periods)$estimate, plain$estimate)
  # A character ID fits the gaussian model the same way
  expect_equal(walker_model(transform(g, ID = paste0("P", ID)), "age", "overall", "gaussian", periods)$estimate,
               plain$estimate, tolerance = 1e-5)
  expect_equal(walker_model(g[sample(nrow(g)), ], "age", "overall", "gaussian", periods)$estimate,
               plain$estimate, tolerance = 1e-5)
})

test_that("sensitivity covariates change the model, and groups of a covariate work", {
  set.seed(123)
  d <- sim_gaussian(200, constant(10))
  # A covariate that moves with Walker status takes part of the crude gap
  d$kl <- ifelse(d$walker_yes, stats::rbinom(nrow(d), 1, 0.8), stats::rbinom(nrow(d), 1, 0.2))
  d$value <- d$value + 8 * d$kl
  crude <- walker_model(d, character(), "overall", "gaussian", periods)
  adjusted <- walker_model(d, "kl", "overall", "gaussian", periods)
  expect_gt(crude$estimate, adjusted$estimate + 2)
  d$site <- rep(c("A", "B", "C", "D"), length.out = nrow(d))
  expect_true(walker_model(d, c("kl", "site"), "overall", "gaussian", periods)$converged)
})

test_that("with no periods overall and visit rows still fit, with an NA period test", {
  set.seed(124)
  d <- sim_gaussian(50, constant(10))
  d$visit <- paste0("v", d$visit)
  for (s in c("overall", "visit")) {
    r <- walker_model(d, character(), s, "gaussian")
    expect_true(all(r$converged))
    expect_true(is.na(attr(r, "period_test")))
  }
})

test_that("input lacking the after visits returns no after row and no error", {
  set.seed(112)
  d <- sim_gaussian(100, constant(10))
  d <- d[!d$visit %in% periods$after, ]
  r <- walker_model(d, "age", "period", "gaussian", periods)
  expect_equal(r$term, c("before", "at"))
  expect_true(all(r$converged))
  expect_false(is.na(attr(r, "period_test")))
})

test_that("visits with every value null count as absent", {
  set.seed(113)
  d <- sim_gaussian(100, constant(10))
  d$value[d$visit %in% periods$after] <- NA
  r <- walker_model(d, character(), "period", "gaussian", periods)
  expect_equal(r$term, c("before", "at"))
  expect_equal(r$n_obs, c(300L, 300L))
})

test_that("only one period present gives NA period_test, and one visit still fits", {
  set.seed(114)
  d <- sim_gaussian(100, constant(10))
  one_period <- d[d$visit %in% periods$before, ]
  r <- walker_model(one_period, character(), "period", "gaussian", periods)
  expect_equal(r$term, "before")
  expect_true(is.na(attr(r, "period_test")))

  one_visit <- d[d$visit == "10", ]
  for (family_data in list(list("gaussian", one_visit),
                           list("binomial", transform(one_visit, value = as.integer(value > 55))))) {
    r <- walker_model(family_data[[2]], character(), "period", family_data[[1]], periods)
    expect_equal(r$term, "at")
    expect_true(r$converged)
    expect_true(is.na(attr(r, "period_test")))
  }
})

test_that("a period or visit with only one walker group gets no row", {
  set.seed(115)
  d <- sim_gaussian(150, constant(10))
  # At the after visits only non-Walkers remain
  no_walkers_after <- d[!(d$visit %in% periods$after & d$walker_yes), ]
  r <- walker_model(no_walkers_after, "age", "period", "gaussian", periods)
  expect_equal(r$term, c("before", "at"))
  expect_true(all(r$converged))
  expect_equal(r$n_obs[1], nrow(no_walkers_after))
  expect_false(is.na(attr(r, "period_test")))
  # And only Walkers remain, which would be collinear with the visit terms if given a coefficient
  only_walkers_after <- d[!(d$visit %in% periods$after & !d$walker_yes), ]
  r <- walker_model(only_walkers_after, "age", "period", "gaussian", periods)
  expect_equal(r$term, c("before", "at"))
  expect_true(all(r$converged))

  one_visit_short <- d[!(d$visit == "14" & d$walker_yes), ]
  r <- walker_model(one_visit_short, "age", "visit", "gaussian", periods)
  expect_equal(r$term, c("00", "01", "10", "13"))
  # The after period still has both groups at 13
  r <- walker_model(one_visit_short, "age", "period", "gaussian", periods)
  expect_equal(r$term, c("before", "at", "after"))

  set.seed(116)
  b <- sim_binary(400, constant(2))
  b <- b[!(b$visit %in% periods$after & b$walker_yes), ]
  r <- walker_model(b, "age", "period", "binomial", periods)
  expect_equal(r$term, c("before", "at"))
  expect_true(all(r$converged))
})

test_that("a model that cannot be fitted returns converged FALSE with NA estimates", {
  set.seed(117)
  g <- sim_gaussian(50, constant(10))
  g$walker_yes <- FALSE
  b <- sim_binary(50, constant(2))
  b$walker_yes <- FALSE
  for (s in c("overall", "period", "visit")) {
    r <- expect_no_error(walker_model(g, "age", s, "gaussian", periods))
    expect_equal(nrow(r), 1L)
    expect_false(r$converged)
    expect_true(all(is.na(c(r$estimate, r$lo, r$hi, r$p))))
    expect_equal(r$scale, "difference")
    expect_type(attr(r, "fit_error"), "character")
    expect_true(is.na(attr(r, "period_test")))

    r <- expect_no_error(walker_model(b, "age", s, "binomial", periods))
    expect_false(r$converged)
    expect_true(is.na(r$estimate))
    expect_equal(r$scale, "or")
    expect_type(attr(r, "fit_error"), "character")
  }
})

test_that("an error from the model itself is caught, with its message", {
  set.seed(118)
  g <- sim_gaussian(50, constant(10))
  g$twin <- g$age * 2 # collinear with age
  r <- expect_no_error(walker_model(g, c("age", "twin"), "overall", "gaussian", periods))
  expect_false(r$converged)
  expect_true(is.na(r$estimate))
  expect_gt(nchar(attr(r, "fit_error")), 0)

  b <- sim_binary(100, constant(2))
  b$twin <- b$age * 2
  r <- expect_no_error(walker_model(b, c("age", "twin"), "overall", "binomial", periods))
  expect_false(r$converged)
  expect_true(is.na(r$estimate))
  expect_gt(nchar(attr(r, "fit_error")), 0)
})

test_that("a GEE that does not converge reports it", {
  # Nobody has the outcome at one visit, so the per-visit log odds run away
  set.seed(125)
  b <- sim_binary(300, constant(2))
  b$value[b$visit == "13"] <- 0L
  by_visit <- walker_model(b, character(), "visit", "binomial", periods)
  expect_false(by_visit$converged)
  expect_true(is.na(by_visit$estimate))
  expect_match(attr(by_visit, "fit_error"), "converge")
})

test_that("a failed fit for the period test alone leaves the rows and says why", {
  set.seed(126)
  d <- sim_gaussian(50, constant(10))
  real_fit <- walker_fit
  local_mocked_bindings(walker_fit = function(frame, covariates, structure, family, corstr) {
    if (structure == "period") stop("period fit failed", call. = FALSE)
    real_fit(frame, covariates, structure, family, corstr)
  })
  r <- walker_model(d, character(), "overall", "gaussian", periods)
  expect_true(r$converged)
  expect_false(is.na(r$estimate))
  expect_true(is.na(attr(r, "period_test")))
  expect_equal(attr(r, "period_test_error"), "period fit failed")
  expect_null(attr(r, "fit_error"))
})

test_that("no fitted rows at all is a failed fit, not an error", {
  set.seed(119)
  g <- sim_gaussian(10, constant(10))
  g$value <- NA_real_
  r <- expect_no_error(walker_model(g, character(), "overall", "gaussian", periods))
  expect_false(r$converged)
  expect_equal(r$n_obs, 0L)
  expect_equal(r$n_people, 0L)
})

test_that("argument errors stop", {
  set.seed(120)
  d <- sim_gaussian(10, constant(10))
  expect_error(walker_model(d[setdiff(names(d), "walker_yes")], character(), "overall", "gaussian", periods),
               "walker_yes")
  expect_error(walker_model(d, "absent", "overall", "gaussian", periods), "absent")
  expect_error(walker_model(d, character(), "overall", "poisson", periods))
  expect_error(walker_model(d, character(), "period", "gaussian"), "periods")
  expect_error(walker_model(d, character(), "overall", "binomial", periods), "0/1")
  bad <- d
  bad$walker_yes <- 2L
  expect_error(walker_model(bad, character(), "overall", "gaussian", periods), "walker_yes")
  bad <- d
  bad$ID[1] <- NA
  expect_error(walker_model(bad, character(), "overall", "gaussian", periods), "ID")
  expect_error(walker_model(d, "value", "overall", "gaussian", periods), "value")
})

test_that("a visit outside the period mapping is an error", {
  set.seed(121)
  d <- sim_gaussian(10, constant(10))
  short <- list(before = c("00", "01"), at = "10", after = "13")
  for (s in c("overall", "period", "visit")) {
    expect_error(walker_model(d, character(), s, "gaussian", short), "14")
  }
  # Even when the row would have been dropped for a null value
  d$value[d$visit == "14"] <- NA
  expect_error(walker_model(d, character(), "period", "gaussian", short), "14")
  expect_error(walker_model(d, character(), "period", "gaussian", list(a = "00", b = "00")), "00")
})

test_that("standardized_difference uses the pooled within-group SD at the earliest visit", {
  d <- data.frame(ID = 1:6, visit = "01", value = c(1, 2, 3, 10, 14, 18),
                  walker_yes = c(TRUE, TRUE, TRUE, FALSE, FALSE, FALSE))
  later <- transform(d, visit = "10", value = value * 100)
  pooled <- sqrt((2 * stats::var(c(1, 2, 3)) + 2 * stats::var(c(10, 14, 18))) / 4)
  expect_equal(standardized_difference(5, rbind(later, d)), 5 / pooled)
  # Pooled within groups, so not the SD of all the values together
  expect_false(isTRUE(all.equal(pooled, stats::sd(d$value))))
  # A visit with no values yet is not the earliest: KOOS sport is missing at enrollment
  empty <- transform(d, visit = "00", value = NA_real_)
  expect_equal(standardized_difference(5, rbind(empty, later, d)), 5 / pooled)
  # 0/1 walker_yes works; several estimates give several answers; NA passes through
  coded <- transform(d, walker_yes = as.integer(walker_yes))
  expect_equal(standardized_difference(c(5, -10, NA), coded), c(5, -10, NA) / pooled)
})

test_that("standardized_difference is NA when the SD is zero or undefined", {
  flat <- data.frame(ID = 1:4, visit = "00", value = 3, walker_yes = c(TRUE, TRUE, FALSE, FALSE))
  expect_true(is.na(standardized_difference(5, flat)))
  singletons <- data.frame(ID = 1:2, visit = "00", value = 1:2, walker_yes = c(TRUE, FALSE))
  expect_true(is.na(standardized_difference(5, singletons)))
  one_group <- data.frame(ID = 1:4, visit = "00", value = 1:4, walker_yes = TRUE)
  expect_true(is.na(standardized_difference(5, one_group)))
  none <- data.frame(ID = 1:2, visit = "00", value = NA_real_, walker_yes = c(TRUE, FALSE))
  expect_true(is.na(standardized_difference(5, none)))
  expect_error(standardized_difference(5, flat, reference = "last_visit"))
  expect_error(standardized_difference(5, flat[c("ID", "visit")]), "value")
})

rule <- list(or_little = 1.44, or_moderate = 2.47, d_little = 0.2, d_moderate = 0.5,
             narrow_min_items = 4,
             narrow_items = c("light_housework", "heavy_housework", "home_repairs", "yard", "garden",
                              "caring", "work_active"))
contrasts_of <- function(measure, estimate, scale = "or", std_diff = NA_real_) {
  data.frame(measure = measure, scale = scale, estimate = estimate, std_diff = std_diff)
}

test_that("bands follow the OR cutoffs, with 1.44 and 2.47 both moderate", {
  ors <- c(1, 1.2, 1.4399, 1.44, 2, 2.47, 2.4701)
  r <- apply_divergence_rule(contrasts_of(paste0("m", seq_along(ors)), ors), rule)
  expect_equal(r$band, c("little_or_none", "little_or_none", "little_or_none", "moderate", "moderate",
                         "moderate", "larger"))
  expect_equal(r$measure, paste0("m", seq_along(ors)))
})

test_that("an inverse association is banded by its magnitude", {
  r <- apply_divergence_rule(contrasts_of(c("a", "b", "c"), 1 / c(1.2, 2, 3)), rule)
  expect_equal(r$band, c("little_or_none", "moderate", "larger"))
})

test_that("bands follow standardized differences on the difference scale", {
  d <- c(0, 0.19, 0.2, -0.2, 0.5, -0.5, 0.51, -0.51)
  # Estimates that would band otherwise if read as ORs, so the wrong column fails
  r <- apply_divergence_rule(contrasts_of(paste0("m", seq_along(d)), 100, "difference", d), rule)
  expect_equal(r$band, c("little_or_none", "little_or_none", "moderate", "moderate", "moderate",
                         "moderate", "larger", "larger"))
})

test_that("an NA estimate or an NA standardized difference gives an NA band", {
  r <- apply_divergence_rule(rbind(contrasts_of("a", NA_real_),
                                   contrasts_of("b", NA_real_, "difference", NA_real_),
                                   contrasts_of("c", 5, "difference", NA_real_),
                                   contrasts_of("d", NA_real_, "difference", 0.3)), rule)
  expect_true(all(is.na(r$band)))
})

test_that("four of seven listed items at 1.5 narrow, three do not", {
  four <- apply_divergence_rule(contrasts_of(rule$narrow_items, c(1.5, 1.5, 1.5, 1.5, 1.1, 1.1, 1.1)), rule)
  expect_true(attr(four, "narrows"))
  expect_equal(attr(four, "narrow_evaluable"), 7L)
  three <- apply_divergence_rule(contrasts_of(rule$narrow_items, c(1.5, 1.5, 1.5, 1.1, 1.1, 1.1, 1.1)), rule)
  expect_false(attr(three, "narrows"))
  expect_equal(attr(three, "narrow_evaluable"), 7L)
})

test_that("only listed items count toward narrowing, and at the or_little boundary", {
  others <- contrasts_of(c("light_sport", "muscle", "moderate_sport", "strenuous_sport"), 3)
  listed <- contrasts_of(rule$narrow_items[1:7], c(1.44, 1.44, 1.44, 1.1, 1.1, 1.1, 1.1))
  expect_false(attr(apply_divergence_rule(rbind(others, listed), rule), "narrows"))
  listed$estimate[4] <- 1.44
  expect_true(attr(apply_divergence_rule(listed, rule), "narrows"))
})

test_that("only the Walker direction counts toward narrowing, though bands use magnitude", {
  inverse <- apply_divergence_rule(contrasts_of(rule$narrow_items[1:4], 0.67), rule)
  expect_equal(inverse$band, rep("moderate", 4))
  expect_false(attr(inverse, "narrows"))
  expect_equal(attr(inverse, "narrow_count"), 0L)
  expect_equal(attr(inverse, "narrow_evaluable"), 4L)

  direct <- apply_divergence_rule(contrasts_of(rule$narrow_items[1:4], 1.5), rule)
  expect_equal(direct$band, rep("moderate", 4))
  expect_true(attr(direct, "narrows"))
  expect_equal(attr(direct, "narrow_count"), 4L)

  # Three in the Walker direction and one inverse fall short of four
  mixed <- apply_divergence_rule(contrasts_of(rule$narrow_items[1:4], c(1.5, 1.5, 1.5, 0.67)), rule)
  expect_false(attr(mixed, "narrows"))
  expect_equal(attr(mixed, "narrow_count"), 3L)
})

test_that("a narrow item on another scale stops, even with no estimate", {
  expect_error(apply_divergence_rule(contrasts_of("garden", 1.5, "difference", 0.3), rule), "garden")
  expect_error(apply_divergence_rule(contrasts_of("garden", NA_real_, "difference", NA_real_), rule), "garden")
  # A measure outside the list may be a difference
  expect_no_error(apply_divergence_rule(contrasts_of("koos_sport", 1, "difference", 0.3), rule))
})

test_that("items with NA estimates or not present are not evaluable and do not count", {
  r <- apply_divergence_rule(contrasts_of(rule$narrow_items[1:5], c(1.5, 1.5, 1.5, NA, NA)), rule)
  expect_false(attr(r, "narrows"))
  expect_equal(attr(r, "narrow_evaluable"), 3L)
})

test_that("the rule does not depend on p-values", {
  base <- contrasts_of(rule$narrow_items, rep(1.5, 7))
  r1 <- apply_divergence_rule(transform(base, p = 0.9), rule)
  r2 <- apply_divergence_rule(transform(base, p = 0.0001), rule)
  expect_equal(r1$band, r2$band)
  expect_equal(attr(r1, "narrows"), attr(r2, "narrows"))
})

test_that("relative_met compares KOOS sport with WOMAC walking by magnitude", {
  both <- rbind(contrasts_of("koos_sport", 1, "difference", -0.1),
                contrasts_of("womac_walk", 1, "difference", -0.3),
                contrasts_of("garden", 1.5))
  r <- apply_divergence_rule(both, rule)
  expect_identical(r$relative_met, c(TRUE, NA, NA))

  both$std_diff[1] <- 0.5
  expect_identical(apply_divergence_rule(both, rule)$relative_met, c(FALSE, NA, NA))
  # A tie is not smaller
  both$std_diff[1] <- 0.3
  expect_identical(apply_divergence_rule(both, rule)$relative_met, c(FALSE, NA, NA))
  both$std_diff[1] <- NA
  expect_identical(apply_divergence_rule(both, rule)$relative_met, c(NA, NA, NA))
  # Only one of the pair
  expect_identical(apply_divergence_rule(both[-2, ], rule)$relative_met, c(NA, NA))
})

test_that("apply_divergence_rule stops on bad arguments", {
  expect_error(apply_divergence_rule(data.frame(measure = "a"), rule), "scale")
  expect_error(apply_divergence_rule(contrasts_of("a", 1, "ratio"), rule), "scale")
  expect_error(apply_divergence_rule(contrasts_of(c("a", "a"), 1), rule), "a")
  expect_error(apply_divergence_rule(contrasts_of("a", -1), rule), "positive")
  expect_error(apply_divergence_rule(contrasts_of("a", 1), rule[-1]), "or_little")
})
