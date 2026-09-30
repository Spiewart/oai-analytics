test_that("assumptions() returns key -> value from the resolved JSON", {
  path <- tempfile(fileext = ".json")
  writeLines('{"analysis": "demo", "label": "default", "variant": null, "overrides": {},
    "assumptions": {
      "model.corstr": {"value": "exchangeable", "status": "open", "source": "x", "origin": "default"},
      "model.covariates": {"value": ["age", "sex", "kl0"], "status": "confirmed", "source": "x", "origin": "default"},
      "alignment.varus_max": {"value": -2.0, "status": "confirmed", "source": "x", "origin": "default"}}}', path)
  a <- assumptions(path)
  expect_equal(a[["model.corstr"]], "exchangeable")
  expect_equal(a[["model.covariates"]], c("age", "sex", "kl0"))
  expect_equal(a[["alignment.varus_max"]], -2)
})

test_that("assumptions() explains how to get a resolved file", {
  expect_error(assumptions(""), "oai run")
})
