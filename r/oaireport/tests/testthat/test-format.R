test_that("fmt_num, fmt_count and fmt_pct format with separators and a true minus", {
  expect_equal(fmt_num(c(-1234.5, 0.256), 1), c("−1,234.5", "0.3"))
  expect_equal(fmt_num(-0.5, minus = FALSE), "-0.50")
  expect_equal(fmt_count(c(12345, 7)), c("12,345", "7"))
  expect_equal(fmt_pct(0.256), "26%")
  expect_equal(fmt_pct(-0.0125, 1), "−1.2%")
  expect_equal(fmt_pct(0.5, minus = FALSE), "50%")
  expect_equal(lower_first(c("At least", "x")), c("at least", "x"))
})

test_that("one_value and one_row stop unless exactly one match", {
  expect_equal(one_value(2, "k"), 2)
  expect_error(one_value(c(1, 2), "k"), "no single value for k")
  expect_error(one_value(NA, "k"), "no single value for k")
  expect_error(one_value(NULL, "k"), "no single value for k")
  df <- data.frame(g = c("a", "a", "b", NA), m = c("x", "y", "x", "x"), v = 1:4)
  expect_equal(one_row(df, g = "a", m = "y")$v, 2)
  expect_error(one_row(df, m = "x"), "expected one row for m = x, found 3")
  expect_error(one_row(df, g = "c"), "found 0")
})

test_that("run_assumption and run_metric read a loaded run", {
  run <- list(metrics = c(a = 1, b = NA),
              assumptions = list(assumptions = list(k = list(value = "mean"))))
  expect_equal(run_assumption(run, "k"), "mean")
  expect_equal(run_metric(run, "a"), 1)
  expect_error(run_metric(run, "b"), "no single value for b")
  expect_error(run_metric(run, "zz"), "no single value for zz")
})
