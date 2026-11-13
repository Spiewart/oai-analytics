test_that("metrics_recorder keeps put order, replaces, removes and writes metrics_<name>.csv", {
  m <- metrics_recorder()
  m$put("b.n", 3L)
  m$put_est("a.or_adj", c(or = 1.5, lo = 1.1, hi = 2.0))
  m$put("gone", 1)
  m$put("gone", NULL)
  m$put("b.n", 4L)
  m$put_est("c", list(estimate = 0.2, lo = NA_real_, hi = 0.5), "estimate")
  expect_equal(names(m$values()), c("b.n", "a.or_adj", "a.or_adj.lo", "a.or_adj.hi",
                                    "c", "c.lo", "c.hi"))
  dir <- tempfile(); dir.create(dir)
  path <- m$write(dir)
  expect_equal(basename(path), "metrics_models.csv")
  got <- utils::read.csv(path)
  expect_equal(got$metric, names(m$values()))
  expect_equal(got$value, c(4, 1.5, 1.1, 2.0, 0.2, NA, 0.5))
  expect_equal(readLines(path)[1], '"metric","value"')
})

test_that("put_est takes a one-row data.frame", {
  m <- metrics_recorder()
  m$put_est("k", data.frame(or = 2, lo = 1, hi = 4))
  expect_equal(unlist(m$values()), c(k = 2, k.lo = 1, k.hi = 4))
})

test_that("write_rows binds a list of frames or writes one frame", {
  dir <- tempfile(); dir.create(dir)
  write_rows(list(data.frame(a = 1, b = "x"), data.frame(a = 2, b = "y")), "t1", dir)
  expect_equal(utils::read.csv(file.path(dir, "t1.csv")), data.frame(a = 1:2, b = c("x", "y")))
  write_rows(data.frame(a = 3), "t2", dir)
  expect_equal(utils::read.csv(file.path(dir, "t2.csv")), data.frame(a = 3L))
})

test_that("device_covariates expands wear time per wave and adds the m2 set", {
  A <- list("model.covariates" = c("age", "wear_hr", "bmi"), "model.covariates_2" = "kl",
            "model.covariates_2_person" = "kl_max")
  expect_equal(device_covariates(A, "m1", c("48", "72")), c("age", "bmi", "wear_hr_48", "wear_hr_72"))
  expect_equal(device_covariates(A, "m2", "48"), c("age", "bmi", "wear_hr_48", "kl"))
  expect_equal(device_covariates(A, "m2", "48", "model.covariates_2_person"),
               c("age", "bmi", "wear_hr_48", "kl_max"))
  expect_equal(device_covariates(list("model.covariates" = "age"), "m1", "48"), "age")
})
