test_that("theme_oai is a bottom-legend classic theme in the report font", {
  theme <- theme_oai()
  expect_s3_class(theme, "theme")
  expect_equal(theme$legend.position, "bottom")
  expect_equal(theme$text$family, oai_font())
  expect_equal(theme$text$size, 8)
  expect_equal(theme_oai(9)$text$size, 9)
})

test_that("palette and status colours are fixed", {
  expect_equal(oai_palette, c("#0072B2", "#D55E00", "#009E73", "#E69F00"))
  expect_equal(oai_status, c(replicated = "#0ca30c", drift = "#fab219", missing = "#d03b3b"))
  expect_true(oai_font() %in% c("Arial", "sans"))
})
