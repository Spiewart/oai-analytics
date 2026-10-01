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

test_that("compare_table escapes Typst markup in cell text", {
  typst <- tinytable::save_tt(
    compare_table(data.frame(metric = "t2.new_pain.or_adj", published = "0.6 (0.4-0.8) *")),
    "typst"
  )
  expect_match(typst, "0.8) \\*", fixed = TRUE)
})

test_that("compare_table shows display labels as headers", {
  typst <- tinytable::save_tt(
    compare_table(comparison, labels = c("Metric", "Published", "Ours", "R1")), "typst"
  )
  expect_match(typst, "[R1]", fixed = TRUE)
  expect_false(grepl("[verdict]", typst, fixed = TRUE))
  two <- transform(comparison, verdict_alt = comparison$verdict)
  expect_s4_class(compare_table(two, labels = c("M", "P", "O", "Verdict", "Verdict")), "tinytable")
  expect_error(compare_table(comparison, labels = "x"), "labels needs one value per column")
})

test_that("compare_table lets identifiers break after dots and underscores", {
  typst <- tinytable::save_tt(compare_table(data.frame(
    metric = "t2.new_pain", run = "walker_requires_amount", value = "0.82", text = "Medial JSN"
  )), "typst")
  expect_match(typst, "t2.​new\\_​pain", fixed = TRUE)
  expect_match(typst, "walker\\_​requires\\_​amount", fixed = TRUE)
  expect_match(typst, "[0.82]", fixed = TRUE)
  expect_match(typst, "[Medial JSN]", fixed = TRUE)
})
