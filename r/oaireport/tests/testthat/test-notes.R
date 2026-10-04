note_text <- function(note) paste(note, collapse = "\n")

test_that("table_note wraps the text in small type, as raw Typst around Markdown", {
  note <- table_note("Se is the share of device walkers who answered yes.")
  text <- note_text(note)
  expect_match(text, "Se is the share of device walkers who answered yes.", fixed = TRUE)
  expect_match(text, "```{=typst}", fixed = TRUE)
  expect_match(text, "size: 8pt", fixed = TRUE)
  # one block opens before the text and the same block closes after it
  opening <- grep("size: 8pt", note)
  closing <- grep("^\\]$", note)
  text_line <- grep("Se is the share", note)
  expect_length(opening, 1)
  expect_length(closing, 1)
  expect_true(opening < text_line && text_line < closing)
})

test_that("table_note takes a size", {
  expect_match(note_text(table_note("x", size = 7)), "size: 7pt", fixed = TRUE)
  expect_error(table_note("x", size = "big"), "size")
  expect_error(table_note("x", size = c(7, 8)), "size")
})

test_that("table_note escapes Markdown, so a label such as k_n or [a] is shown as written", {
  note <- table_note("p_adj *star* [a] <b> #1 $5 a~b c^d `x` 1\\2")
  line <- note[grep("adj", note, fixed = TRUE)]
  expect_equal(line, "p\\_adj \\*star\\* \\[a\\] \\<b\\> \\#1 \\$5 a\\~b c\\^d \\`x\\` 1\\\\2")
})

test_that("table_note leaves ordinary punctuation and symbols alone, and joins lines", {
  note <- table_note("  Se + Sp − 1 ≥ 0 (95% CI);\n k / n  ")
  expect_true("Se + Sp − 1 ≥ 0 (95% CI); k / n" %in% note)
})

test_that("table_note refuses anything but one non-empty string", {
  expect_error(table_note(character()), "one string")
  expect_error(table_note(c("a", "b")), "one string")
  expect_error(table_note(NA_character_), "one string")
  expect_error(table_note(1), "one string")
  expect_error(table_note("   "), "one string")
})

test_that("a figure and its legend share one block", {
  open <- figure_group()
  expect_true("#block(breakable: false)[" %in% open)
  expect_equal(sum(grepl("```{=typst}", open, fixed = TRUE)), 1)
  grouped <- table_note("Legend.", close_group = TRUE)
  alone <- table_note("Legend.")
  # the legend block closes, then the group's block closes after it
  expect_equal(length(grouped), length(alone) + 4)
  expect_equal(tail(grouped, 4), c("```{=typst}", "]", "```", ""))
  expect_equal(sum(grepl("^\\]$", grouped)), 2)
  expect_equal(sum(grepl("^\\]$", alone)), 1)
})

test_that("table_note puts an unescaped bold label before the escaped text", {
  lines <- table_note("Some *text*.", label = "Table A1.")
  expect_true("**Table A1.** Some \\*text\\*." %in% lines)
  expect_false(any(grepl("\\*\\*", table_note("Plain."))))
  expect_error(table_note("x", label = c("a", "b")), "label")
})
