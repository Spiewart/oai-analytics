test_that("default_covariates matches the plan's confounder block", {
  expect_equal(default_covariates(2), c("age0", "sex", "bmi0", "PC1", "PC2"))
  expect_equal(default_covariates(0), c("age0", "sex", "bmi0"))
})

test_that("model stubs point at the analysis plan", {
  expect_error(fit_progression_lmm(data.frame(), "y"), "section 11.1")
  expect_error(fit_tkr_cox(data.frame()), "section 11.4")
})
