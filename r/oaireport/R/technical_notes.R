# Technical notes for a plain-language document: a technical term in the text carries a
# superscript letter linked to its note at the end, and each note links back to the term's first
# use. Letters are given in order of first reference; notes never referenced are left out.

#' Default note texts for common methods; a document overrides or extends them
standard_tech_notes <- function() c(
  median_difference = "Median difference: the Hodges–Lehmann estimate, the median of all differences between a member of one group and a member of the other; it is robust to skewed data.",
  median_regression = "Adjusted difference: from median (quantile) regression of the measure on the group and the listed covariates.",
  wilson_ci = "95% CI for a proportion: the Wilson score interval, which stays within 0 to 1 and behaves well for shares near either end.",
  bootstrap_ci = "Bootstrap 95% CI: participants are resampled with replacement, the estimate is recomputed each time, and the middle 95% of the results forms the interval.",
  trend_test = "Test for trend: the Jonckheere–Terpstra test of whether a measure rises across ordered groups, with a permutation p-value.",
  rank_correlation = "Rank correlation: Spearman's correlation between the ranks of two measures, from −1 to 1.",
  sensitivity_specificity = "Sensitivity: of the people the reference calls positive, the share the test also calls positive. Specificity: of the people the reference calls negative, the share the test also calls negative.",
  predictive_values = "Predictive values: of the people the test calls positive, the share the reference also calls positive (PPV); of those it calls negative, the share the reference also calls negative (NPV).",
  youden_j = "Youden's J: sensitivity + specificity − 1; 0 means the test is no better than chance and 1 means it is perfect.",
  kappa = "Agreement beyond chance: Cohen's kappa, 0 for the agreement expected by chance and 1 for perfect agreement.",
  limits_of_agreement = "Limits of agreement: the 2.5th and 97.5th percentiles of the differences between two measures (Bland–Altman).",
  misclassification_simulation = "Simulation of misclassification: a probabilistic bias analysis that repeatedly draws plausible sensitivity and specificity values, reclassifies each participant accordingly and refits the model; a simulation that implies a negative number of participants in a group is impossible and is set aside.",
  tipping_point = "Tipping-point analysis: the model is refitted over a grid of assumed sensitivity and specificity values to show where, if anywhere, the conclusion would change.",
  nondifferential = "Non-differential misclassification: misclassification that is the same in people with and without the outcome; it tends to pull an association toward no effect."
)

# a, b, …, z, aa, ab, …
note_letter <- function(i) {
  vapply(i, function(n) {
    s <- ""
    while (n > 0) {
      r <- (n - 1) %% 26
      s <- paste0(letters[r + 1], s)
      n <- (n - 1) %/% 26
    }
    s
  }, character(1))
}

#' A registry of technical notes for one document
#'
#' `entries` (named character: key = note text) override `defaults`. `$ref(key)` gives the
#' superscript marker, as inline raw Typst for Markdown prose (`raw = FALSE` for a raw Typst
#' block); use markers in body prose only, never in table cells or legends (they are escaped).
#' `$list()` writes the notes once, in order of first reference.
tech_notes <- function(entries = character(), defaults = standard_tech_notes()) {
  named_text <- function(x, what) {
    if (!is.character(x) || (length(x) && (is.null(names(x)) || any(!nzchar(names(x)))))) {
      stop("tech_notes(): ", what, " must be a named character vector", call. = FALSE)
    }
  }
  named_text(entries, "entries"); named_text(defaults, "defaults")
  notes <- defaults
  notes[names(entries)] <- entries
  bad <- names(notes)[!grepl("^[A-Za-z][A-Za-z0-9_]*$", names(notes))]
  if (length(bad)) stop("tech_notes(): key must be letters, digits and _: ", paste(bad, collapse = ", "), call. = FALSE)
  state <- new.env(parent = emptyenv())
  state$order <- character()
  state$listed <- FALSE
  ref <- function(key, raw = TRUE) {
    if (!is.character(key) || length(key) != 1 || !key %in% names(notes)) {
      stop("tech_notes(): unknown note \"", paste(key, collapse = ", "), "\"", call. = FALSE)
    }
    first <- !key %in% state$order
    if (first) state$order <- c(state$order, key)
    code <- sprintf("#super[#link(<tn-%s>)[%s]]%s", key, note_letter(match(key, state$order)),
                    if (first) sprintf("<tn-ref-%s>", key) else "")
    if (raw) sprintf("`%s`{=typst}", code) else code
  }
  list_notes <- function(title = "Technical notes") {
    if (state$listed) stop("tech_notes(): the notes are already listed; write them once", call. = FALSE)
    state$listed <- TRUE
    if (!length(state$order)) return(character())
    items <- vapply(seq_along(state$order), function(i) {
      key <- state$order[[i]]
      sprintf('#block(below: 0.6em)[#text(weight: "bold")[%s] #h(0.3em) %s #link(<tn-ref-%s>)[↑]] <tn-%s>',
              note_letter(i), typst_text(notes[[key]]), key, key)
    }, character(1))
    c("", "```{=typst}", sprintf("#heading(level: 1, numbering: none)[%s]", typst_text(title)),
      "#block[", "#set text(size: 8.5pt)", items, "]", "```", "")
  }
  list(ref = ref, list = list_notes, keys = function() state$order)
}
