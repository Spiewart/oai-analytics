comparison <- data.frame(
  metric = c("a", "b", "c", "d"),
  published = c("1", "2", "3", "4"),
  ours = c("1", "3", NA, "4"),
  verdict = c("replicated", "drift", "missing", NA)
)

test_that("format_verdicts turns verdicts into symbols and words", {
  out <- format_verdicts(comparison)
  expect_equal(out$verdict, c("✓ replicated", "△ drift", "– missing", ""))
  expect_equal(out$metric, comparison$metric)
  expect_equal(format_verdicts(comparison, compact = TRUE)$verdict,
               c("✓", "△", "–", ""))
})

test_that("format_verdicts formats every verdict* column and rejects unknown verdicts", {
  two <- transform(comparison, verdict_alt = rev(comparison$verdict))
  expect_equal(format_verdicts(two)$verdict_alt, c("", "– missing", "△ drift", "✓ replicated"))
  expect_error(format_verdicts(data.frame(verdict = "maybe")), "unknown verdict\\(s\\): maybe")
})

test_that("compare_table returns a tinytable and checks widths", {
  expect_s4_class(compare_table(comparison), "tinytable")
  expect_s4_class(compare_table(comparison, widths = c(2, 1, 1, 1.5), compact = TRUE), "tinytable")
  expect_s4_class(compare_table(data.frame(x = 1)), "tinytable")
  expect_error(compare_table(comparison, widths = c(1, 1)), "one value per column")
})
