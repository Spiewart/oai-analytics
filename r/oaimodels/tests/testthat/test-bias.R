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

test_that("reclassify is the identity at perfect sensitivity and specificity", {
  d <- person_data()
  set.seed(3)
  out <- reclassify(d$persons, c(case = 1, noncase = 1), c(case = 1, noncase = 1))
  expect_equal(out, d$persons$observed)
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

test_that("differential priors must cover every stratum", {
  d <- person_data()
  bad <- data.frame(stratum = "case", se1 = 9, se2 = 2, sp1 = 9, sp2 = 2)
  expect_error(pba(d$persons, d$knees, glm_fit, bad, differential = TRUE, iterations = 2), "noncase")
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
  skip_if(Sys.getenv("OAI_SLOW") == "", "set OAI_SLOW=1 to run the simulation test")
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
