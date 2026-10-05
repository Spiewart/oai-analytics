test_that("tech_notes letters notes in order of first reference and links both ways", {
  notes <- tech_notes(c(alpha = "First #note.", beta = "Second."), defaults = character())
  expect_equal(notes$ref("beta"), "`#super[#link(<tn-beta>)[a]]<tn-ref-beta>`{=typst}")
  expect_equal(notes$ref("alpha", raw = FALSE), "#super[#link(<tn-alpha>)[b]]<tn-ref-alpha>")
  expect_equal(notes$ref("beta", raw = FALSE), "#super[#link(<tn-beta>)[a]]")
  expect_equal(notes$keys(), c("beta", "alpha"))
  out <- paste(notes$list(), collapse = "\n")
  expect_match(out, "#heading(level: 1, numbering: none)[Technical notes]", fixed = TRUE)
  expect_match(out, '#text(weight: "bold")[a] #h(0.3em) Second. #link(<tn-ref-beta>)[↑]] <tn-beta>', fixed = TRUE)
  expect_match(out, "First \\#note.", fixed = TRUE)
  expect_lt(regexpr("<tn-beta>", out, fixed = TRUE), regexpr("<tn-alpha>", out, fixed = TRUE))
  expect_error(notes$list(), "once")
})

test_that("tech_notes rejects unknown keys and bad names, and lists only referenced notes", {
  notes <- tech_notes(c(alpha = "A."), defaults = c(beta = "B."))
  expect_error(notes$ref("gamma"), "unknown note")
  notes$ref("alpha")
  out <- paste(notes$list(), collapse = "\n")
  expect_false(grepl("<tn-beta>", out, fixed = TRUE))
  expect_error(tech_notes(c(`bad key` = "x"), defaults = character()), "key")
  expect_error(tech_notes(c("unnamed"), defaults = character()), "named")
  expect_equal(tech_notes(defaults = character())$list(), character())
})

test_that("entries override defaults, and letters continue past z", {
  expect_equal(note_letter(c(1, 26, 27, 28, 52, 53)), c("a", "z", "aa", "ab", "az", "ba"))
  notes <- tech_notes(c(kappa = "Mine."))
  notes$ref("kappa")
  out <- paste(notes$list(), collapse = "\n")  # expect_match evaluates its argument twice
  expect_match(out, "Mine.", fixed = TRUE)
})

test_that("standard_tech_notes covers the common methods with plain sentences", {
  std <- standard_tech_notes()
  expect_true(all(c("median_difference", "median_regression", "wilson_ci", "bootstrap_ci", "trend_test",
                    "rank_correlation", "sensitivity_specificity", "predictive_values", "youden_j", "kappa",
                    "limits_of_agreement", "misclassification_simulation", "tipping_point",
                    "nondifferential") %in% names(std)))
  expect_true(all(nzchar(std)) && all(grepl("\\.$", std)))
})
