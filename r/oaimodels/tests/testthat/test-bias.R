person_data <- function(n = 400, seed = 1) {
  set.seed(seed)
  persons <- data.frame(ID = seq_len(n), observed = stats::runif(n) < 0.5)
  y <- stats::rbinom(n, 1, stats::plogis(-0.5 + 0.4 * persons$observed))
  persons$stratum <- ifelse(y == 1, "case", "noncase")
  knees <- data.frame(ID = persons$ID, y = y, walker = persons$observed)
  list(persons = persons, knees = knees)
}
glm_fit <- function(k) {
  co <- summary(stats::glm(y ~ walker, data = k, family = stats::binomial))$coefficients
  c(log_or = co["walkerTRUE", "Estimate"], se = co["walkerTRUE", "Std. Error"])
}

test_that("prevalence and reclassification algebra", {
  expect_equal(beta_shapes(8, 10), c(shape1 = 9, shape2 = 3))
  expect_equal(true_prevalence(0.5, 1, 1), 0.5)
  p <- reclass_probs(0.5, 1, 1)
  expect_equal(c(p$ppv, p$fom), c(1, 0))
  expect_equal(correct_or_2x2(10, 20, 30, 40, 1, 1), (10 * 40) / (20 * 30))
  expect_equal(correct_or_2x2(100, 100, 100, 300, 0.8, 0.9), 44 / 9, tolerance = 1e-6)
})

test_that("correct_or_2x2 discards draws with Se + Sp <= 1 in either outcome stratum", {
  # crude OR is 1.222; worse-than-chance classification must not be 'corrected' into 0.333
  expect_true(is.na(correct_or_2x2(50, 50, 45, 55, 0.4, 0.4)))
  # case-stratum violation only (control stratum is valid)
  expect_true(is.na(correct_or_2x2(50, 50, 45, 55, 0.4, 0.4, se_ctrl = 0.9, sp_ctrl = 0.9)))
  # control-stratum violation only
  expect_true(is.na(correct_or_2x2(50, 50, 45, 55, 0.9, 0.9, se_ctrl = 0.4, sp_ctrl = 0.4)))
  # Se + Sp exactly 1 is also no information
  expect_true(is.na(correct_or_2x2(50, 50, 45, 55, 0.5, 0.5)))
})

test_that("reclassify is the identity at perfect sensitivity and specificity", {
  d <- person_data()
  set.seed(3)
  out <- reclassify(d$persons, c(case = 1, noncase = 1), c(case = 1, noncase = 1))
  expect_equal(out, d$persons$observed)
})

test_that("reclassify keeps perfect-classification draws despite floating-point rounding", {
  # (p_obs + 1 - 1) / 1 is not exactly p_obs for many proportions (14 of the 54 below), so
  # ppv = p / p_obs can come out 1 + 2.2e-16: a strict ppv <= 1 check would discard a valid
  # Se = Sp = 1 draw
  for (n in c(7, 10, 13)) {
    for (k in 1:(n - 1)) {
      case <- c(rep(TRUE, k), rep(FALSE, n - k))
      noncase <- c(rep(TRUE, n - k), rep(FALSE, k + 3))
      persons <- data.frame(
        ID = seq_len(length(case) + length(noncase)),
        observed = c(case, noncase),
        stratum = rep(c("case", "noncase"), c(length(case), length(noncase)))
      )
      out <- reclassify(persons, c(case = 1, noncase = 1), c(case = 1, noncase = 1))
      expect_false(is.null(out), info = sprintf("n = %d, k = %d", n, k))
      expect_identical(out, persons$observed)
    }
  }
})

test_that("reclassify still discards impossible probabilities", {
  persons <- data.frame(ID = 1:10, observed = rep(c(TRUE, FALSE), 5), stratum = "all")
  # Se + Sp <= 1
  expect_null(reclassify(persons, c(all = 0.5), c(all = 0.5)))
  expect_null(reclassify(persons, c(all = 0.4), c(all = 0.3)))
  # observed prevalence 0.5 < 1 - Sp: negative true prevalence
  expect_null(reclassify(persons, c(all = 0.9), c(all = 0.3)))
  # observed prevalence 0.5 > Se: true prevalence above 1
  expect_null(reclassify(persons, c(all = 0.4), c(all = 0.9)))
  # a valid draw is reclassified, not discarded
  expect_length(reclassify(persons, c(all = 0.9), c(all = 0.9)), 10)
})

test_that("pba with fixed perfect classification returns the observed OR", {
  d <- person_data()
  observed <- glm_fit(d$knees)
  draws <- pba(d$persons, d$knees, glm_fit, data.frame(stratum = "all", se = 1, sp = 1),
               iterations = 20, seed = 1)
  expect_false(any(draws$discarded))
  expect_equal(draws$log_or, rep(observed[["log_or"]], 20))
  s <- summarise_pba(draws, direction = sign(observed[["log_or"]]), significant = FALSE)
  expect_equal(s$or, exp(observed[["log_or"]]))
  expect_equal(s$conclusion_share, 1)
})

test_that("impossible priors are discarded, not fatal", {
  d <- person_data()
  # worse than chance (Se + Sp <= 1), and a negative true prevalence (observed < 1 - Sp)
  for (fixed in list(c(0.3, 0.3), c(0.9, 0.3))) {
    draws <- pba(d$persons, d$knees, glm_fit, data.frame(stratum = "all", se = fixed[1], sp = fixed[2]),
                 iterations = 5, seed = 1)
    expect_true(all(draws$discarded))
    s <- summarise_pba(draws)
    expect_true(is.na(s$or))
    expect_equal(s$discarded, 1)
  }
})

test_that("a draw that leaves a single exposure level is discarded, not fatal", {
  # p_obs = 0.5 in both outcome strata with Se = 0.9 and Sp just above 0.5: the implied true
  # prevalence (2.5e-9) passes reclassify()'s feasibility check, but every knee comes out a
  # non-walker, and the model cannot estimate a walker coefficient from a constant exposure
  n <- 40
  persons <- data.frame(ID = seq_len(n), observed = rep(c(TRUE, FALSE), n / 2),
                        stratum = rep(c("case", "noncase"), each = n / 2))
  knees <- data.frame(ID = persons$ID, y = as.integer(persons$stratum == "case"),
                      walker = persons$observed)
  priors <- data.frame(stratum = "all", se = 0.9, sp = 0.5 + 1e-9)
  for (cores in if (.Platform$OS.type == "windows") 1 else c(1, 2)) {
    draws <- pba(persons, knees, glm_fit, priors, iterations = 4, seed = 1, cores = cores)
    expect_equal(nrow(draws), 4)
    expect_true(all(draws$discarded))
    s <- summarise_pba(draws)
    expect_true(is.na(s$or))
    expect_equal(s$discarded, 1)
    expect_equal(s$n, 4)
  }
})

test_that("differential priors must cover every stratum", {
  d <- person_data()
  bad <- data.frame(stratum = "case", se1 = 9, se2 = 2, sp1 = 9, sp2 = 2)
  expect_error(pba(d$persons, d$knees, glm_fit, bad, differential = TRUE, iterations = 2), "noncase")
})

test_that("a fit that returns non-finite values is discarded, not fatal", {
  d <- person_data()
  priors <- data.frame(stratum = "all", se = 0.9, sp = 0.9)
  # NA on every call: every draw is discarded and the summary degrades to NA
  na_fit <- function(k) c(log_or = NA_real_, se = NA_real_)
  draws <- pba(d$persons, d$knees, na_fit, priors, iterations = 6, seed = 1)
  expect_true(all(draws$discarded))
  expect_true(all(is.na(draws$log_or) & is.na(draws$se) & is.na(draws$log_or_total)))
  s <- summarise_pba(draws)
  expect_true(is.na(s$or))
  expect_equal(s$discarded, 1)
  # a finite log_or with a non-finite se is also unusable
  inf_fit <- function(k) c(log_or = 0.1, se = Inf)
  expect_true(all(pba(d$persons, d$knees, inf_fit, priors, iterations = 3, seed = 1)$discarded))
  # NA on odd calls only: the kept draws still summarise
  calls <- new.env()
  calls$n <- 0
  odd_na_fit <- function(k) {
    calls$n <- calls$n + 1
    if (calls$n %% 2 == 1) c(log_or = NA_real_, se = NA_real_) else glm_fit(k)
  }
  draws <- pba(d$persons, d$knees, odd_na_fit, priors, iterations = 10, seed = 1)
  expect_equal(sum(draws$discarded), 5)
  expect_equal(draws$discarded, rep(c(TRUE, FALSE), 5))
  s <- summarise_pba(draws, direction = 1, significant = FALSE)
  expect_true(is.finite(s$or))
  expect_equal(s$discarded, 0.5)
  expect_equal(s$n, 10)
})

test_that("bind_runs refuses to return fewer iterations than requested", {
  row <- function(i) {
    data.frame(iter = i, log_or = 0, se = 1, log_or_total = 0, discarded = FALSE)
  }
  ok <- bind_runs(list(row(1), row(2), row(3)), 3)
  expect_equal(nrow(ok), 3)
  expect_error(bind_runs(list(row(1), NULL, row(3)), 3), "1 of 3")
  expect_error(bind_runs(list(row(1), row(2)), 3), "3 iterations")
})

test_that("pba is identical across core counts", {
  skip_on_os("windows")
  d <- person_data()
  priors <- data.frame(stratum = "all", se1 = 90, se2 = 10, sp1 = 80, sp2 = 20)
  one <- pba(d$persons, d$knees, glm_fit, priors, iterations = 8, seed = 4, cores = 1)
  two <- pba(d$persons, d$knees, glm_fit, priors, iterations = 8, seed = 4, cores = 2)
  expect_equal(one, two)
})

test_that("pba recovers a true OR under known non-differential misclassification", {
  set.seed(11)
  n <- 4000
  truth <- stats::runif(n) < 0.5
  y <- stats::rbinom(n, 1, stats::plogis(-0.5 + log(0.6) * truth))
  observed <- ifelse(truth, stats::runif(n) < 0.85, stats::runif(n) < 0.25)  # Se 0.85, Sp 0.75
  persons <- data.frame(ID = seq_len(n), observed = observed, stratum = ifelse(y == 1, "case", "noncase"))
  knees <- data.frame(ID = seq_len(n), y = y, walker = observed)
  true_or <- exp(glm_fit(data.frame(y = y, walker = truth))[["log_or"]])
  priors <- data.frame(stratum = "all", se1 = 851, se2 = 151, sp1 = 751, sp2 = 251)
  s <- summarise_pba(pba(persons, knees, glm_fit, priors, iterations = 300, seed = 2))
  expect_lt(abs(s$or - true_or), 0.05)
})

test_that("reclassify and pba look Se and Sp up by stratum name, not position", {
  d <- person_data()
  # numeric strata 1 and 3: by position, se[[3]] would be out of bounds
  persons <- d$persons
  persons$stratum <- ifelse(persons$stratum == "case", 3, 1)
  perfect <- c("1" = 1, "3" = 1)
  expect_identical(reclassify(persons, perfect, perfect), persons$observed)
  # logical strata: by position, se[[FALSE]] selects nothing
  persons$stratum <- persons$stratum == 3
  perfect <- c("FALSE" = 1, "TRUE" = 1)
  expect_identical(reclassify(persons, perfect, perfect), persons$observed)
  # numeric strata listed in the opposite order from the priors
  persons$stratum <- ifelse(persons$stratum, 2, 1)
  observed <- glm_fit(d$knees)
  priors <- data.frame(stratum = c(1, 2), se = c(1, 1), sp = c(1, 1))
  draws <- pba(persons, d$knees, glm_fit, priors, differential = TRUE, iterations = 3, seed = 1)
  expect_equal(draws$log_or, rep(observed[["log_or"]], 3))
})

test_that("pba rejects missing observed values and knees without a person", {
  d <- person_data()
  priors <- data.frame(stratum = "all", se = 0.9, sp = 0.9)
  missing_observed <- d$persons
  missing_observed$observed[c(4, 9)] <- NA
  expect_error(pba(missing_observed, d$knees, glm_fit, priors, iterations = 2),
               "2 persons have no observed exposure")
  orphan <- d$knees
  orphan$ID[1:3] <- orphan$ID[1:3] + 10000
  expect_error(pba(d$persons, orphan, glm_fit, priors, iterations = 2),
               "3 knees have an ID that is not in persons")
})

test_that("pba needs at least one whole iteration", {
  d <- person_data()
  priors <- data.frame(stratum = "all", se = 0.9, sp = 0.9)
  for (bad in list(0, -1, 2.5, NA, c(2, 3))) {
    expect_error(pba(d$persons, d$knees, glm_fit, priors, iterations = bad),
                 "iterations must be a whole number >= 1")
  }
})

test_that("pba's iterations error shows what was passed, with its class", {
  d <- person_data()
  priors <- data.frame(stratum = "all", se = 0.9, sp = 0.9)
  shown <- function(bad) {
    tryCatch(pba(d$persons, d$knees, glm_fit, priors, iterations = bad),
             error = function(e) conditionMessage(e))
  }
  # a string "3" must not read like the number 3
  expect_match(shown("3"), 'got "3" (character)', fixed = TRUE)
  expect_match(shown(2.5), "got 2.5 (numeric)", fixed = TRUE)
  expect_match(shown(c(2, 3)), "got c(2, 3) (numeric)", fixed = TRUE)
  expect_match(shown(NA), "got NA (logical)", fixed = TRUE)
})

test_that("differential pba uses each stratum's own draw", {
  d <- person_data()
  priors <- data.frame(stratum = c("noncase", "case"), se1 = c(90, 85), se2 = c(10, 15),
                       sp1 = c(75, 80), sp2 = c(25, 20))
  draws <- pba(d$persons, d$knees, glm_fit, priors, differential = TRUE, iterations = 3, seed = 7)
  expect_false(any(draws$discarded))
  # iteration i draws Se then Sp for the strata in persons' order, from set.seed(seed + i)
  strata <- unique(d$persons$stratum)
  rows <- priors[match(strata, priors$stratum), ]
  for (i in 1:3) {
    set.seed(7 + i)
    se <- stats::setNames(stats::rbeta(2, rows$se1, rows$se2), strata)
    sp <- stats::setNames(stats::rbeta(2, rows$sp1, rows$sp2), strata)
    knees <- d$knees
    knees$walker <- reclassify(d$persons, se, sp)[match(knees$ID, d$persons$ID)]
    est <- glm_fit(knees)
    expect_equal(draws$log_or[i], est[["log_or"]])
    expect_equal(draws$se[i], est[["se"]])
    expect_equal(draws$log_or_total[i], stats::rnorm(1, est[["log_or"]], est[["se"]]))
  }
  s <- summarise_pba(draws, direction = 1, significant = FALSE)
  expect_equal(s$or, exp(stats::median(draws$log_or)))
  expect_equal(s$n, 3)
})

test_that("summarise_pba's conclusion share with significant = TRUE", {
  draws <- data.frame(
    iter = 1:5,
    log_or = c(0.5, 0.5, -0.5, 0.1, NA),
    se = c(0.1, 0.5, 0.1, 0.01, NA),
    log_or_total = c(0.5, 0.4, -0.6, 0.1, NA),
    discarded = c(FALSE, FALSE, FALSE, FALSE, TRUE)
  )
  # kept draws: z = 5, 1, -5, 10; same direction as +1 and |z| > 1.96: draws 1 and 4
  expect_equal(summarise_pba(draws, direction = 1, significant = TRUE)$conclusion_share, 2 / 4)
  expect_equal(summarise_pba(draws, direction = 1, significant = FALSE)$conclusion_share, 3 / 4)
  expect_equal(summarise_pba(draws, direction = -1, significant = TRUE)$conclusion_share, 1 / 4)
  expect_true(is.na(summarise_pba(draws)$conclusion_share))
  expect_equal(summarise_pba(draws)$discarded, 1 / 5)
})

test_that("pba leaves the caller's random-number stream alone and repeats under a seed", {
  d <- person_data()
  priors <- data.frame(stratum = "all", se1 = 90, se2 = 10, sp1 = 80, sp2 = 20)
  set.seed(99)
  expected <- stats::runif(3)
  set.seed(99)
  first <- pba(d$persons, d$knees, glm_fit, priors, iterations = 4, seed = 3, cores = 1)
  expect_identical(stats::runif(3), expected)
  rm(".Random.seed", envir = globalenv())
  expect_identical(pba(d$persons, d$knees, glm_fit, priors, iterations = 4, seed = 3, cores = 1), first)
  expect_false(exists(".Random.seed", envir = globalenv(), inherits = FALSE))
  set.seed(1)
})

test_that("pba(cores = 2) restores the caller's random-number stream too", {
  skip_on_os("windows")  # mclapply forks; Windows runs on one core
  d <- person_data()
  priors <- data.frame(stratum = "all", se1 = 90, se2 = 10, sp1 = 80, sp2 = 20)
  run <- function() pba(d$persons, d$knees, glm_fit, priors, iterations = 4, seed = 3, cores = 2)
  set.seed(99)
  expected <- stats::runif(3)
  set.seed(99)
  first <- run()
  expect_identical(stats::runif(3), expected)
  # an absent .Random.seed stays absent, and the draws repeat
  rm(".Random.seed", envir = globalenv())
  expect_identical(run(), first)
  expect_false(exists(".Random.seed", envir = globalenv(), inherits = FALSE))
  set.seed(1)
})
