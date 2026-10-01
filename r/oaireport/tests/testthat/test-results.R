write_run <- function(root, label, finished = '"2026-09-30T12:00:00+00:00"') {
  dir <- file.path(root, label)
  dir.create(dir, recursive = TRUE)
  writeLines(sprintf('{"label": "%s", "finished_utc": %s}', label, finished),
             file.path(dir, "run_info.json"))
  utils::write.csv(data.frame(step = "all", persons = 10), file.path(dir, "flow.csv"),
                   row.names = FALSE)
  utils::write.csv(data.frame(metric = c("a", "b"), value = c(1, NA)),
                   file.path(dir, "metrics_one.csv"), row.names = FALSE)
  utils::write.csv(data.frame(metric = "c", value = 3), file.path(dir, "metrics_two.csv"),
                   row.names = FALSE)
  writeLines('{"label": "x", "assumptions": {"k": {"value": 1, "origin": "default"}}}',
             file.path(dir, "assumptions.resolved.json"))
  dir
}

test_that("load_results reads every CSV, merged metrics, assumptions and run info", {
  root <- withr::local_tempdir()
  write_run(root, "default")
  write_run(root, "alt")
  runs <- load_results(root, c("default", "alt"))
  expect_named(runs, c("default", "alt"))
  expect_equal(runs$alt$flow$persons, 10)
  expect_equal(runs$default$metrics, c(a = 1, b = NA, c = 3))
  expect_equal(runs$default$assumptions$assumptions$k$value, 1)
  expect_equal(runs$alt$run_info$label, "alt")
})

test_that("load_results takes its defaults from the oai report environment", {
  root <- withr::local_tempdir()
  write_run(root, "default")
  write_run(root, "alt")
  withr::local_envvar(OAI_RESULTS_ROOT = root, OAI_REPORT_RUNS = "default,alt")
  expect_named(load_results(), c("default", "alt"))
  withr::local_envvar(OAI_RESULTS_ROOT = "")
  expect_error(load_results(), "no results root")
})

test_that("load_results names the missing or unfinished run and how to produce it", {
  root <- withr::local_tempdir()
  write_run(root, "default", finished = "null")
  expect_error(load_results(root, "default"), "run 'default' did not finish.*oai report")
  expect_error(load_results(root, "alt"), "no run 'alt'.*--variant alt")
})

test_that("load_results refuses CSVs that shadow its own parts", {
  root <- withr::local_tempdir()
  dir <- write_run(root, "default")
  utils::write.csv(data.frame(x = 1), file.path(dir, "metrics.csv"), row.names = FALSE)
  expect_error(load_results(root, "default"), "metrics.csv")
})

test_that("parse_or reads graded odds-ratio text", {
  out <- parse_or(c("0.6 (0.4-0.8) *", "0.82 (0.62-1.10)", NA, "n/a"))
  expect_equal(out$or, c(0.6, 0.82, NA, NA))
  expect_equal(out$lo, c(0.4, 0.62, NA, NA))
  expect_equal(out$hi, c(0.8, 1.10, NA, NA))
  expect_equal(out$sig, c(TRUE, FALSE, NA, NA))
  expect_equal(nrow(parse_or(character())), 0)
})
