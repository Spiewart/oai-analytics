test_that("typst_text escapes Typst markup characters", {
  expect_equal(typst_text("a #b $c *d* _e_ [f] <g> @h ~i `j` \\k l/m"),
               "a \\#b \\$c \\*d\\* \\_e\\_ \\[f\\] \\<g\\> \\@h \\~i \\`j\\` \\\\k l\\/m")
  expect_equal(typst_text("  two   spaces \n newline "), "two spaces newline")
  expect_error(typst_text(1), "character")
})

test_that("fmt_ci joins limits with an en dash, or 'to' when a limit is negative", {
  expect_equal(fmt_ci(0.891, 0.862, 0.913), "0.89 (0.86–0.91)")
  expect_equal(fmt_ci(105, -153, 1080, digits = 0), "105 (-153 to 1,080)")
  expect_equal(fmt_ci(NA, 1, 2), "–")
  expect_equal(fmt_ci(0.5, NA, 0.6), "0.50")
  expect_equal(fmt_ci(c(0.1, 0.2), c(0.05, -0.1), c(0.2, 0.3)),
               c("0.10 (0.05–0.20)", "0.20 (-0.10 to 0.30)"))
  expect_equal(fmt_ci(c(0.1, 0.2), 0.05, 0.3), c("0.10 (0.05–0.30)", "0.20 (0.05–0.30)"))
  expect_equal(fmt_ci(0.5, c(0.1, 0.2), c(0.6, 0.7)), c("0.50 (0.10–0.60)", "0.50 (0.20–0.70)"))
})

test_that("callout emits one raw Typst block with escaped text, a title and citations", {
  note <- callout("Counts can't tell #walking from cycling", kind = "warn", title = "The weak link.",
                  cite = c("abel2008", "storti2008"))
  body <- paste(note, collapse = "\n")
  expect_equal(sum(grepl("^```", note)), 2)
  expect_match(body, "```{=typst}", fixed = TRUE)
  expect_match(body, "rgb(\"#E69F00\")", fixed = TRUE)
  expect_match(body, "The weak link.", fixed = TRUE)
  expect_match(body, "\\#walking", fixed = TRUE)
  expect_match(body, "@abel2008 @storti2008", fixed = TRUE)
  expect_match(paste(callout("ok"), collapse = "\n"), "rgb(\"#0072B2\")", fixed = TRUE)
  expect_error(callout("x", kind = "other"))
  expect_error(callout("x", cite = "bad key"), "cite")
})

test_that("sidebar_figure lays out key results and the ask beside the figure", {
  side <- sidebar_figure(data.frame(value = c("0.88 / 0.25", "7.7 → 3.9"), label = c("Se / Sp", "factor")),
                         ask = "A joint study.", image = "figures/f.png", caption = "Caption.")
  text <- paste(side, collapse = "\n")
  expect_match(text, "#grid(columns: (31%, 1fr)", fixed = TRUE)
  expect_match(text, "#image(\"figures/f.png\", width: 100%)", fixed = TRUE)
  expect_match(text, "7.7 → 3.9", fixed = TRUE)
  expect_match(text, "0.88 \\/ 0.25", fixed = TRUE)
  expect_match(text, "The ask.", fixed = TRUE)
  expect_match(text, "KEY RESULTS", fixed = TRUE)
  expect_error(sidebar_figure(data.frame(x = 1), "a", "i", "c"), "value and label")
})

test_that("reading_guide lists each term in bold, then the notation line", {
  guide <- reading_guide(c(`Item walker` = "answered yes.", `Device walker` = "2 days a week."),
                         "Notation: 0.89 (0.86–0.91).")
  text <- paste(guide, collapse = "\n")
  expect_match(text, "#text(weight: \"bold\")[Item walker:] answered yes.", fixed = TRUE)
  expect_match(text, "Notation: 0.89", fixed = TRUE)
  expect_match(text, "How to read this report", fixed = TRUE)
  expect_error(reading_guide(c("no names"), "n"), "named")
})

test_that("numberer counts tables and figures separately", {
  lab <- numberer("A")
  expect_equal(c(lab("Table"), lab("Figure"), lab("Table")), c("Table A1.", "Figure A1.", "Table A2."))
  expect_equal(numberer()("Figure"), "Figure 1.")
  expect_error(lab("Chart"))
})

test_that("author_block reads names and contact, or gives the placeholder", {
  expect_equal(author_block(tempfile(fileext = ".yml")), "Authors and contact to be added")
  path <- withr::local_tempfile(fileext = ".yml")
  writeLines(c("authors:", "  - name: A. Person", "    affiliation: Somewhere", "  - name: B. Person",
               "contact:", "  name: A. Person", "  email: a@example.org"), path)
  expect_equal(author_block(path),
               "A. Person (Somewhere), B. Person · Contact: A. Person, a@example.org")
  writeLines("authors: []", path)
  expect_error(author_block(path), "needs `authors`")
  writeLines(c("authors:", "  - name: A", "contact:", "  name: A"), path)
  expect_error(author_block(path), "without an `email`")
})

test_that("youden_contours draws a dashed line per J and labels each above the top edge", {
  layers <- youden_contours(c(0, 0.2))
  expect_length(layers, 2)
  expect_equal(layers[[1]]$data$se, c(0, 1, 0.2, 1))
  expect_equal(layers[[2]]$data$fpr, c(1, 0.8))
  expect_equal(layers[[2]]$data$label, c("0", "J = 0.2"))
  expect_error(youden_contours(1), "j must")
})
