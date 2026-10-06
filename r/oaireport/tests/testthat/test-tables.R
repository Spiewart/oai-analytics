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

test_that("compare_table breaks across pages unless multipage = FALSE", {
  typst <- function(tab) tinytable::save_tt(tab, "typst")
  expect_match(typst(compare_table(comparison)), "set block(breakable: true)", fixed = TRUE)
  expect_match(typst(compare_table(comparison, multipage = FALSE)), "set block(breakable: false)",
               fixed = TRUE)
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
  expect_match(typst, "t2.\u200bnew\\_\u200bpain", fixed = TRUE)
  expect_match(typst, "walker\\_\u200brequires\\_\u200bamount", fixed = TRUE)
  expect_match(typst, "[0.82]", fixed = TRUE)
  expect_match(typst, "[Medial JSN]", fixed = TRUE)
})

style_keys <- function(tab) {
  out <- tinytable::save_tt(tab, output = "typst")
  sort(regmatches(out, gregexpr('"[0-9]+_[0-9]+"(?=: )', out, perl = TRUE))[[1]])
}

# The style-array entry a style key points to, e.g. "(bold: true,)". `key` is "row_col0".
style_at <- function(tab, key) {
  lines <- strsplit(tinytable::save_tt(tab, output = "typst"), "\n", fixed = TRUE)[[1]]
  dict <- regmatches(paste(lines, collapse = " "),
                     gregexpr('"[0-9]+_[0-9]+": [0-9]+', paste(lines, collapse = " ")))[[1]]
  index <- as.integer(sub(".*: ", "", dict[startsWith(dict, paste0('"', key, '"'))]))
  first <- grep("let style-array = (", lines, fixed = TRUE)
  after <- lines[(first + 1):length(lines)]
  entries <- after[seq_len(grep("^\\s*\\)\\s*$", after)[1] - 1)]
  trimws(grep("^\\s*\\(", entries, value = TRUE)[index + 1])
}

test_that("ci_excludes is TRUE only when both limits sit strictly on one side of the null", {
  expect_equal(ci_excludes(c(0.1, -0.5, -0.2, 0, NA), c(0.3, -0.1, 0.4, 0.2, 0.5)),
               c(TRUE, TRUE, FALSE, FALSE, FALSE))
  expect_equal(ci_excludes(c(0.4, 0.8, 1.1), c(0.9, 1.2, 1.5), null = 1), c(TRUE, FALSE, TRUE))
  expect_equal(ci_excludes(0.2, c(0.5, NA)), c(TRUE, FALSE))
  expect_error(ci_excludes("a", 1), "numeric")
})

test_that("compare_table bolds exactly the cells marked TRUE", {
  df <- data.frame(a = c("x", "y", "z"), b = c("1", "2", "3"))
  bold <- matrix(FALSE, 3, 2); bold[2, 2] <- TRUE
  tab <- compare_table(df, bold = bold)
  expect_equal(style_keys(tab), '"2_1"')  # header is Typst row 0
  expect_match(style_at(tab, "2_1"), "bold: true", fixed = TRUE)
  expect_equal(style_keys(compare_table(df)), character())
  expect_error(compare_table(df, bold = matrix(TRUE, 1, 2)), "bold")
  expect_error(compare_table(df, bold = matrix("x", 3, 2)), "bold")
})

test_that("bold lands on the right cell when groups add rows above it", {
  df <- data.frame(a = c("x", "y", "z"), b = c("1", "2", "3"))
  bold <- matrix(FALSE, 3, 2); bold[2, 2] <- TRUE; bold[3, 1] <- TRUE
  tab <- compare_table(df, bold = bold, groups = list(G = 1, H = 3), group_style = NULL)
  # rows: header 0, G 1, x 2, y 3, H 4, z 5
  expect_equal(style_keys(tab), c('"3_1"', '"5_0"'))
  expect_match(style_at(tab, "3_1"), "bold: true", fixed = TRUE)
  expect_match(style_at(tab, "5_0"), "bold: true", fixed = TRUE)
})

test_that("verdict tints move with their rows when groups add rows above them", {
  df <- data.frame(a = c("x", "y", "z"), verdict = c("replicated", "drift", "missing"))
  plain <- compare_table(df)
  expect_equal(style_keys(plain), c('"1_1"', '"2_1"', '"3_1"'))
  expect_match(style_at(plain, "1_1"), verdict_tints[["replicated"]], fixed = TRUE)
  expect_match(style_at(plain, "3_1"), verdict_tints[["missing"]], fixed = TRUE)
  grouped <- compare_table(df, groups = list(G = 1, H = 3), group_style = NULL)
  # rows: header 0, G 1, x 2, y 3, H 4, z 5
  expect_equal(style_keys(grouped), c('"2_1"', '"3_1"', '"5_1"'))
  expect_match(style_at(grouped, "2_1"), verdict_tints[["replicated"]], fixed = TRUE)
  expect_match(style_at(grouped, "3_1"), verdict_tints[["drift"]], fixed = TRUE)
  expect_match(style_at(grouped, "5_1"), verdict_tints[["missing"]], fixed = TRUE)
})

test_that("compare_table styles the group-title rows and no data row", {
  df <- data.frame(a = c("x", "y", "z"), b = c("1", "2", "3"))
  # rows: header 0, G 1, x 2, y 3, H 4, z 5; the titles span both columns
  tab <- compare_table(df, groups = list(H = 3, G = 1))
  expect_equal(style_keys(tab), sort(c('"1_0"', '"1_1"', '"4_0"', '"4_1"')))
  for (key in c("1_0", "4_0")) {
    expect_match(style_at(tab, key), "bold: true", fixed = TRUE)
    expect_match(style_at(tab, key), "italic: true", fixed = TRUE)
  }
  # bold data cells keep their own style, without the titles' italic
  bold <- matrix(FALSE, 3, 2); bold[2, 2] <- TRUE
  both <- compare_table(df, bold = bold, groups = list(G = 1, H = 3))
  expect_equal(style_keys(both), sort(c('"1_0"', '"1_1"', '"3_1"', '"4_0"', '"4_1"')))
  expect_false(grepl("italic", style_at(both, "3_1"), fixed = TRUE))
  custom <- compare_table(df, groups = list(G = 1), group_style = list(italic = TRUE))
  expect_match(style_at(custom, "1_0"), "italic: true", fixed = TRUE)
  expect_false(grepl("bold", style_at(custom, "1_0"), fixed = TRUE))
  expect_equal(style_keys(compare_table(df, groups = list(G = 1), group_style = NULL)), character())
  expect_equal(style_keys(compare_table(df)), character())  # no groups, nothing styled
  expect_error(compare_table(df, groups = list(G = 1), group_style = list(TRUE)), "group_style")
  expect_error(compare_table(df, groups = list(G = 1), group_style = "bold"), "group_style")
})

test_that("compare_table checks groups", {
  df <- data.frame(a = c("x", "y", "z"), b = c("1", "2", "3"))
  expect_s4_class(compare_table(df, groups = list(G = 1, H = 3)), "tinytable")
  expect_error(compare_table(df, groups = list(1, 3)), "groups")        # unnamed
  expect_error(compare_table(df, groups = list(G = 1, 3)), "groups")     # partly named
  expect_error(compare_table(df, groups = list(G = "y")), "groups")      # not numeric
  expect_error(compare_table(df, groups = list(G = 0)), "groups")        # before the first row
  expect_error(compare_table(df, groups = list(G = 4)), "groups")        # past the last row
  expect_error(compare_table(df, groups = list(G = 1.5)), "groups")      # not a whole row
  expect_error(compare_table(df, groups = c(G = 1)), "groups")           # not a list
})
