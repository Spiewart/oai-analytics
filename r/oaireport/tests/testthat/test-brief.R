test_that("typst_text escapes Typst markup characters", {
  expect_equal(typst_text("a #b $c *d* _e_ [f] <g> @h ~i `j` \\k l/m"),
               "a \\#b \\$c \\*d\\* \\_e\\_ \\[f\\] \\<g\\> \\@h \\~i \\`j\\` \\\\k l\\/m")
  expect_equal(typst_text("  two   spaces \n newline "), "two spaces newline")
  expect_error(typst_text(1), "character")
})

test_that("typst_text escapes a list or heading marker that opens the text, and only there", {
  expect_equal(typst_text("- x"), "\\- x")
  expect_equal(typst_text("+ x"), "\\+ x")
  expect_equal(typst_text("= x"), "\\= x")
  expect_equal(typst_text("== x"), "\\== x")
  expect_equal(typst_text("1. x"), "1\\. x")
  expect_equal(typst_text("12. x"), "12\\. x")
  expect_equal(typst_text("  - x  "), "\\- x")  # the marker opens the line once the text is trimmed
  expect_equal(typst_text("-"), "\\-")
  expect_equal(typst_text("1."), "1\\.")
  # the same characters mid-text, or without the space that makes them markup, are left alone
  expect_equal(typst_text("a - b + c = d 1. e"), "a - b + c = d 1. e")
  expect_equal(typst_text("-x +x =x 1.5 a1. x"), "-x +x =x 1.5 a1. x")
  expect_equal(typst_text("x\n- y"), "x - y")  # a newline is squeezed to a space, so nothing opens a line
  expect_equal(typst_text(c("- a", "b - c")), c("\\- a", "b - c"))
})

test_that("typst_text refuses NA, which would print as the word NA", {
  expect_error(typst_text(NA_character_), "typst_text\\(\\): x has NA values")
  expect_error(typst_text(c("a", NA)), "x has NA values")
  expect_equal(typst_text(character()), character())
})

test_that("fmt_ci joins limits with an unbreakable en dash, or 'to' when a limit is negative", {
  # U+2060 (word joiner) follows the en dash and U+00A0 surrounds "to", so a cell breaks only at the
  # space before "("; negative numbers print a true minus (U+2212)
  expect_equal(fmt_ci(0.891, 0.862, 0.913), "0.89 (0.86\u2013\u20600.91)")
  expect_equal(fmt_ci(105, -153, 1080, digits = 0), "105 (\u2212153\u00a0to\u00a01,080)")
  expect_equal(fmt_ci(NA, 1, 2), "\u2013")
  expect_equal(fmt_ci(0.5, NA, 0.6), "0.50")
  expect_equal(fmt_ci(-0.5, NA, NA), "\u22120.50")
  expect_equal(fmt_ci(-0.1, 0.05, 0.2), "\u22120.10 (0.05\u2013\u20600.20)")
  expect_equal(fmt_ci(c(0.1, 0.2), c(0.05, -0.1), c(0.2, 0.3)),
               c("0.10 (0.05\u2013\u20600.20)", "0.20 (\u22120.10\u00a0to\u00a00.30)"))
  expect_equal(fmt_ci(c(0.1, 0.2), 0.05, 0.3),
               c("0.10 (0.05\u2013\u20600.30)", "0.20 (0.05\u2013\u20600.30)"))
  expect_equal(fmt_ci(0.5, c(0.1, 0.2), c(0.6, 0.7)),
               c("0.50 (0.10\u2013\u20600.60)", "0.50 (0.20\u2013\u20600.70)"))
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

# Text holding every character typst_text escapes, with more closing than opening brackets, so a
# single unescaped bracket unbalances the generated Typst
nasty <- "# $ * _ ` < > @ ~ [ ] / \\ ] ] ["
# The same text as typst_text() must give it, written out so that the box tests below do not
# check an escape against the function that made it
nasty_typst <- "\\# \\$ \\* \\_ \\` \\< \\> \\@ \\~ \\[ \\] \\/ \\\\ \\] \\] \\["

test_that("typst_text escapes every character of the nasty text, as written out", {
  expect_equal(typst_text(nasty), nasty_typst)
})

test_that("the typst_text helper's bracket check catches a stray bracket, and ignores escaped ones", {
  expect_true(typst_balanced("#block(a: (b: 1))[text #text[inner]]"))
  expect_true(typst_balanced("a \\[ b \\( c"))
  expect_false(typst_balanced("#text[a [ b]"))
  expect_false(typst_balanced("#text(a]"))
  expect_false(typst_balanced("[(])"))
})

test_that("callout keeps its brackets balanced and its text escaped, with or without a title", {
  titled <- callout(nasty, title = nasty, cite = "abel2008")
  untitled <- callout(nasty, kind = "warn")
  expect_typst_balanced(titled)
  expect_typst_balanced(untitled)
  count <- function(note) {
    text <- paste(note, collapse = "\n")
    lengths(regmatches(text, gregexpr(nasty_typst, text, fixed = TRUE)))
  }
  expect_equal(count(titled), 2)    # the title and the text
  expect_equal(count(untitled), 1)  # the text
})

test_that("a callout without a title does not start its text as a list, a heading or a numbered item", {
  # each line is found by its content, not by its position in the block
  expect_match(line_with(callout("- not a list"), "not a list"), "^\\\\- not a list$")
  expect_match(line_with(callout("1. not numbered"), "not numbered"), "^1\\\\\\. not numbered$")
  # with a title the text follows it on the same line; the escape is harmless there (it prints "-")
  expect_match(line_with(callout("- x", title = "T."), "[T.]"), "\\[T\\.\\] \\\\- x$")
})

test_that("callout refuses NA text", {
  expect_error(callout(NA_character_), "NA")
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

test_that("sidebar_figure escapes every text field and keeps its brackets balanced", {
  side <- sidebar_figure(data.frame(value = nasty, label = nasty), ask = nasty, image = "figures/f.png",
                         caption = nasty, caption_title = nasty, heading = nasty)
  expect_typst_balanced(side)
  text <- paste(side, collapse = "\n")
  # the value, label, ask, caption, caption title and heading, each in escaped form
  expect_equal(lengths(regmatches(text, gregexpr(typst_text(nasty), text, fixed = TRUE))), 6)
  expect_match(text, "\\# \\$ \\* \\_ \\` \\< \\> \\@ \\~ \\[ \\] \\/ \\\\ \\] \\] \\[", fixed = TRUE)
})

test_that("sidebar_figure refuses NA text and an image path that would break the #image string", {
  results <- data.frame(value = "1", label = "a")
  expect_error(sidebar_figure(data.frame(value = NA_character_, label = "a"), "ask", "f.png", "c"),
               "NA values")
  expect_error(sidebar_figure(results, "ask", "f.png", NA_character_), "NA values")
  expect_error(sidebar_figure(results, "ask", "figures/a\"b.png", "c"), "image")
  expect_error(sidebar_figure(results, "ask", "figures\\a.png", "c"), "image")
  expect_error(sidebar_figure(results, "ask", c("a.png", "b.png"), "c"), "image")
  expect_error(sidebar_figure(results, "ask", NA_character_, "c"), "image")
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

test_that("reading_guide escapes terms, definitions and notation and keeps its brackets balanced", {
  guide <- reading_guide(stats::setNames(nasty, nasty), notation = nasty, title = nasty)
  expect_typst_balanced(guide)
  text <- paste(guide, collapse = "\n")
  expect_equal(lengths(regmatches(text, gregexpr(nasty_typst, text, fixed = TRUE))), 4)
  expect_match(text, paste0("[", nasty_typst, ":]"), fixed = TRUE)
})

test_that("a notation line that starts like a list item stays text", {
  expect_equal(line_with(reading_guide(c(a = "b"), "- one 1. two"), "one 1. two"), "\\- one 1. two")
  expect_equal(line_with(reading_guide(c(a = "b"), "2. two"), "two"), "2\\. two")
})

test_that("cut_labels names each cut by the answer at or above its level", {
  item <- c("1\u20133 times/month", "4\u20138 times/month", "9 or more times/month")
  expect_equal(cut_labels(c(1, 2, 3), item),
               c(cut1 = "At least 1\u20133 times/month", cut2 = "At least 4\u20138 times/month",
                 cut3 = "9 or more times/month"))
  # PASE days run from level 0 (Never), so the first level is 0 and cut 1 is "at least 1-2 days"
  pase <- c("Never", "1\u20132 days", "3\u20134 days", "5\u20137 days")
  expect_equal(cut_labels(c(1, 2, 3), pase, first_level = 0),
               c(cut1 = "At least 1\u20132 days", cut2 = "At least 3\u20134 days", cut3 = "5\u20137 days"))
  expect_equal(cut_labels(c(2, 3), item), c(cut1 = "At least 4\u20138 times/month", cut2 = "9 or more times/month"))
  expect_length(cut_labels(c(2, 3), item), 2)
  expect_equal(cut_labels(2L, item), c(cut1 = "At least 4\u20138 times/month"))  # integers; a cut below the top
  expect_equal(cut_labels(3, item), c(cut1 = "9 or more times/month"))
})

test_that("cut_labels takes the prefix of a cut below the top and one for the top cut", {
  item <- c("1\u20133 times/month", "4\u20138 times/month", "9 or more times/month")
  expect_equal(cut_labels(c(1, 2, 3), item, prefix = "Walker, at least", top_prefix = "Walker,"),
               c(cut1 = "Walker, at least 1\u20133 times/month", cut2 = "Walker, at least 4\u20138 times/month",
                 cut3 = "Walker, 9 or more times/month"))
  expect_equal(cut_labels(c(1, 3), item, prefix = "From"), c(cut1 = "From 1\u20133 times/month",
                                                              cut2 = "9 or more times/month"))
  # `top` names the level that reads as its label alone (the last level by default)
  expect_equal(cut_labels(c(1, 2), item, top = 2),
               c(cut1 = "At least 1\u20133 times/month", cut2 = "4\u20138 times/month"))
  expect_error(cut_labels(1, item, top = 4), "top")
})

test_that("cut_labels refuses cuts that are empty, fractional, repeated, unordered or out of range", {
  item <- c("1\u20133 times/month", "4\u20138 times/month", "9 or more times/month")
  pase <- c("Never", "1\u20132 days", "3\u20134 days", "5\u20137 days")
  expect_error(cut_labels(numeric(0), item), "cuts.*empty")
  expect_error(cut_labels(NULL, item), "cuts")
  expect_error(cut_labels(c(1, 1.5), item), "whole numbers")
  expect_error(cut_labels(c(1, NA), item), "whole numbers")
  expect_error(cut_labels("1", item), "whole numbers")
  expect_error(cut_labels(c(2, 3, 3), item), "strictly increasing")
  expect_error(cut_labels(c(3, 2), item), "strictly increasing")
  expect_error(cut_labels(4, item), "outside the answer levels 1 to 3")
  expect_error(cut_labels(c(1, 4), item), "outside the answer levels 1 to 3")
  expect_error(cut_labels(0, item), "outside the answer levels 1 to 3")
  # level 0 is the lowest level and everyone is at or above it: PASE cut 0 would read "At least Never"
  expect_error(cut_labels(c(0, 1), pase, first_level = 0), "lowest level")
  expect_error(cut_labels(0, pase, first_level = 0), "At least Never")
  # the item's level 1 is not the lowest: non-walkers sit below it, so a cut there is a real cut
  expect_equal(cut_labels(1, item), c(cut1 = "At least 1\u20133 times/month"))
  expect_error(cut_labels(1, character()), "labels")
  expect_error(cut_labels(1, NA_character_), "labels")
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

test_that("author_block joins several affiliations and names a file that is not a mapping", {
  path <- withr::local_tempfile(fileext = ".yml")
  writeLines(c("authors:", "  - name: A. Person", "    affiliation: [Here, There]"), path)
  expect_equal(author_block(path), "A. Person (Here; There)")
  writeLines("just a line", path)
  expect_error(author_block(path), paste0(path, " must be a YAML mapping"), fixed = TRUE)
})

test_that("author_block looks keys up exactly: name_full is not name, nor affiliation_x an affiliation", {
  path <- withr::local_tempfile(fileext = ".yml")
  writeLines(c("authors:", "  - name_full: A. Person"), path)
  expect_error(author_block(path), "needs `authors`")
  writeLines(c("authors:", "  - name: A. Person", "    affiliation_long: Somewhere"), path)
  expect_equal(author_block(path), "A. Person")
  writeLines(c("authors_list:", "  - name: A. Person"), path)  # `authors` is not a prefix match for `authors_list`
  expect_error(author_block(path), "needs `authors`")
  writeLines(c("authors:", "  - name: A. Person", "contact_info:", "  email: a@example.org"), path)
  expect_equal(author_block(path), "A. Person")
  writeLines(c("authors:", "  - name: A. Person", "contact:", "  email_address: a@example.org"), path)
  expect_error(author_block(path), "without an `email`")
  writeLines(c("authors:", "  - name: A. Person", "contact:", "  name_full: B. Person", "  email: a@example.org"), path)
  expect_equal(author_block(path), "A. Person \u00b7 Contact: a@example.org")
})

test_that("an empty affiliation counts as none", {
  path <- withr::local_tempfile(fileext = ".yml")
  for (empty in c("[]", "\"\"", "''", "~", "[\"\"]")) {
    writeLines(c("authors:", "  - name: A. Person", paste("    affiliation:", empty),
                 "  - name: B. Person", "    affiliation: Here"), path)
    expect_equal(author_block(path), "A. Person, B. Person (Here)", info = empty)
  }
  writeLines(c("authors:", "  - name: A. Person", "    affiliation: [Here, \"\", There]"), path)
  expect_equal(author_block(path), "A. Person (Here; There)")
})

test_that("youden_contours draws a dashed line per J and labels each above the top edge", {
  layers <- youden_contours(c(0, 0.2))
  expect_length(layers, 2)
  expect_equal(layers[[1]]$data$se, c(0, 1, 0.2, 1))
  expect_equal(layers[[2]]$data$fpr, c(1, 0.8))
  expect_equal(layers[[2]]$data$label, c("0", "J = 0.2"))
  # the largest label is right-justified so it ends near its line and clears the next label
  expect_equal(layers[[2]]$data$hjust, c(0.5, 0.85))
  expect_equal(rlang::as_label(layers[[2]]$mapping$hjust), "hjust")
  # the mappings name columns through the .data pronoun, so R CMD check sees no free variables
  mapped <- function(layer) vapply(layer$mapping, function(m) rlang::expr_text(rlang::quo_get_expr(m)), character(1))
  expect_equal(unname(mapped(layers[[1]])), c(".data$fpr", ".data$se", ".data$j"))
  expect_equal(unname(mapped(layers[[2]])), c(".data$fpr", ".data$se", ".data$label", ".data$hjust"))
  expect_error(youden_contours(1), "j must")
})
