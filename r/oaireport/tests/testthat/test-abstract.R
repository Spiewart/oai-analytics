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
})
