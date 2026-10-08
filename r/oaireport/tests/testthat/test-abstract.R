test_that("char_budget counts each section with spaces, a Unicode symbol as one character", {
  b <- char_budget(c(Title = "AB C", Purpose = "≥ 2 – ρ"), limit = 100)
  expect_equal(b$part, c("Title", "Purpose", "Total", "Limit", "Margin"))
  expect_equal(b$characters, c(4L, 7L, 11L, 100L, 89L))
})

test_that("char_budget charges each image and lists the charge", {
  b <- char_budget(c(Body = "abc"), images = 2, per_image = 560, limit = 5000)
  expect_equal(b$part, c("Body", "Images (2 × 560)", "Total", "Limit", "Margin"))
  expect_equal(b$characters, c(3L, 1120L, 1123L, 5000L, 3877L))
})

test_that("char_budget allows a total exactly at the limit and stops one over, naming the overage", {
  expect_equal(tail(char_budget(c(Body = strrep("x", 10)), limit = 10)$characters, 1), 0L)
  expect_error(char_budget(c(Body = strrep("x", 11)), limit = 10),
               "11 characters, 1 over the limit of 10")
  expect_error(char_budget(c(Body = "x"), images = 1, per_image = 560, limit = 500),
               "561 characters, 61 over the limit of 500")
})

test_that("char_budget rejects unnamed, duplicated or missing sections and bad numbers", {
  expect_error(char_budget("text"), "named")
  expect_error(char_budget(c(A = "x", A = "y")), "unique")
  expect_error(char_budget(c(A = NA_character_)), "missing")
  expect_error(char_budget(c(A = "x"), images = -1), "images")
  expect_error(char_budget(c(A = "x"), images = 1.5), "images")
  expect_error(char_budget(c(A = "x"), limit = NA), "limit")
  expect_error(char_budget(character()), "at least one")
  expect_error(char_budget(c(A = 12345)), "character")
  expect_error(char_budget(list(A = c("x", "y"))), "one string")
})

test_that("char_budget takes a list of single strings as well as a character vector", {
  expect_equal(char_budget(list(A = "ab", B = "c"), limit = 10)$characters, c(2L, 1L, 3L, 10L, 7L))
})

test_that("p_stars marks each p-value below each level, and nothing for NA or larger p", {
  expect_equal(p_stars(c(0.0004, 0.001, 0.009, 0.01, 0.049, 0.05, 0.2, NA)),
               c("***", "**", "**", "*", "*", "", "", ""))
  expect_equal(p_stars(c(0.02, 0.07, 0.2), levels = c(0.1, 0.05)), c("**", "*", ""))
  expect_error(p_stars(0.1, levels = c(0.05, NA)), "levels")
})
