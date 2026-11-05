# Step `construct_validity`: the walking question's construct validity, by facet. Fits nothing until
# a co-author has approved the scope: with construct.scope_approved anything but true it writes
# construct_status.csv (awaiting_review), reads no data and stops with success. Once approved:
#   construct_contrasts.csv  Each measure's Walker contrast under each model. p and p_holm appear
#                            only where a claim rests on them: base overall rows of the primary and
#                            other convergent measures, each facet its own Holm family. Every other
#                            row reports a CI only. period_test is on the base overall PASE total row.
#   construct_rule.csv       The divergent measures judged by size (base overall), and the narrowing.
#   construct_kl.csv         Walker share by KL (person-level, adjusted; a likelihood-ratio p for the
#                            KL term, repeated on its rows), the contrasts within each KL group
#                            (CIs only), and the walker x KL tests. The share p and the two tests are
#                            one Holm family. n_people is the model's, on every row.
#   construct_dose.csv       At 96 months, walking_any by each amount level against not-Walkers
#                            (adjusted ORs with CIs) and a Cochran-Armitage trend, as pase_walking.R.
#   construct_attrition.csv  Who had a PASE total at 96 and at 168 months, and enrollment
#                            characteristics of those with one at 96 months, with and without one at
#                            168. No p-values.
# A model that fails leaves a row with converged FALSE and the reason in fit_note; other measures go on.
A <- oaimodels::assumptions()
out_dir <- Sys.getenv("OAI_RESULTS_DIR")
out_path <- function(name) file.path(out_dir, paste0("construct_", name, ".csv"))
write_out <- function(rows, name) utils::write.csv(rows, out_path(name), row.names = FALSE)

# Nothing left from an earlier run can pass for this one's results
unlink(out_path(c("status", "contrasts", "rule", "kl", "dose", "attrition")))

# The gate. Keep this above anything that touches the frame.
if (!isTRUE(A[["construct.scope_approved"]])) {
  write_out(data.frame(status = "awaiting_review"), "status")
  cat("construct_validity: awaiting review (construct.scope_approved is not true); nothing fitted\n")
  quit(save = "no", status = 0)
}

covariates <- unlist(A[["pase_walking.covariates"]])
sensitivity <- lapply(A[["construct.sensitivity_covariates"]], unlist)
periods <- lapply(A[["construct.periods"]], unlist)
facets <- unlist(A[["construct.facets"]])
expected <- unlist(A[["construct.expected"]])
continuous <- unlist(A[["construct.continuous_measures"]])
corstr <- A[["construct.gee_corstr"]]
sd_reference <- A[["construct.sd_reference"]]
age_min <- A[["construct.age_sensitivity_min"]]
kl_measures <- c("total", "walking_any")
amount_columns <- c(times = "amount_times", years = "amount_years")
answer_labels <- lapply(A[["components.answer_labels"]], unlist)

frame <- oaimodels::read_frame(
  file.path(Sys.getenv("OAI_FRAME_DIR"), "construct_frame.parquet"),
  required = c("ID", "visit", "measure", "value", "walker_yes", "walk_item", "amount_times", "amount_years",
               "age", "sex", "bmi", "age_at_visit", "kl_max0", "kl_group0", covariates, unlist(sensitivity))
)
if (!nrow(frame)) stop("construct_frame.parquet has no rows", call. = FALSE)
unknown <- setdiff(unique(frame$measure), names(facets))
if (length(unknown)) {
  stop("measures not in construct.facets: ", paste(unknown, collapse = ", "), call. = FALSE)
}
frame$visit <- as.character(frame$visit)
family_of <- function(measure) if (measure %in% continuous) "gaussian" else "binomial"
scale_of <- function(family) if (family == "gaussian") "difference" else "or"

# ---- Models ----------------------------------------------------------------------------------
# Disease and cohort are categories; the pain scores stay numeric
person_factors <- intersect(c("kl_group0", "cohort"), unlist(sensitivity))
frame[person_factors] <- lapply(frame[person_factors], function(x) factor(as.character(x)))

at_visit <- periods$at[1]
after_visit <- periods$after[1]
completers <- function(d) {
  has <- d[!is.na(d$value), , drop = FALSE]
  intersect(has$ID[has$visit == at_visit], has$ID[has$visit == after_visit])
}
every_measure <- function(d) TRUE
all_rows <- function(d) d
models <- list(
  base = list(covariates = covariates, structures = c("overall", "period", "visit"),
              applies = every_measure, keep = all_rows),
  enroll_disease = list(covariates = c(covariates, sensitivity$enroll_disease),
                        structures = c("overall", "period"), applies = every_measure, keep = all_rows),
  time_pain = list(covariates = c(covariates, sensitivity$time_pain), structures = c("overall", "period"),
                   applies = every_measure, keep = all_rows),
  age50 = list(covariates = covariates, structures = c("overall", "period"), applies = every_measure,
               keep = function(d) d[!is.na(d$age_at_visit) & d$age_at_visit >= age_min, , drop = FALSE]),
  completers_168 = list(covariates = covariates, structures = "period", only_term = "after",
                        applies = function(d) length(completers(d)) > 0L,
                        keep = function(d) d[d$ID %in% completers(d), , drop = FALSE])
)

# The rows a model fits, without factor levels those rows lack
fitted_rows <- function(d, adjust) {
  droplevels(d[stats::complete.cases(d[c("ID", "visit", "value", "walker_yes", adjust)]), , drop = FALSE])
}

# A failed fit's message, on the rows it left
with_notes <- function(rows) {
  failed <- !rows$converged & is.na(rows$fit_note)
  if (!is.null(attr(rows, "fit_error"))) rows$fit_note[failed] <- attr(rows, "fit_error")
  rows
}

run_model <- function(d, measure, model, structure) {
  spec <- models[[model]]
  family <- family_of(measure)
  wants_period_test <- model == "base" && structure == "overall" && measure == "total"
  rows <- tryCatch({
    data <- fitted_rows(spec$keep(d), spec$covariates)
    fit <- oaimodels::walker_model(data, spec$covariates, structure, family,
                                   periods = if (structure == "period" || wants_period_test) periods,
                                   corstr = corstr)
    out <- with_notes(fit)
    if (wants_period_test && !is.null(attr(fit, "period_test_error"))) {
      out$fit_note <- paste("period test:", attr(fit, "period_test_error"))
    }
    out$std_diff <- if (family == "gaussian") {
      oaimodels::standardized_difference(out$estimate, data, sd_reference)
    } else {
      NA_real_
    }
    out$period_test <- if (wants_period_test) attr(fit, "period_test") else NA_real_
    out$dropped_visits <- paste(attr(fit, "dropped_visits"), collapse = " ")
    out
  }, error = function(e) {
    data.frame(term = if (structure == "overall") "overall" else NA_character_,
               estimate = NA_real_, lo = NA_real_, hi = NA_real_, p = NA_real_, scale = scale_of(family),
               n_people = NA_integer_, n_obs = NA_integer_, converged = FALSE,
               fit_note = conditionMessage(e), std_diff = NA_real_, period_test = NA_real_,
               dropped_visits = "")
  })
  if (!is.null(spec$only_term)) {
    rows <- rows[is.na(rows$term) | rows$term == spec$only_term, , drop = FALSE]
    rows$term <- rep(spec$only_term, nrow(rows))
  }
  cbind(data.frame(measure = rep(measure, nrow(rows)), model = rep(model, nrow(rows))), rows,
        row.names = NULL)
}

measures <- intersect(names(facets), unique(frame$measure))
contrast_rows <- list()
for (measure in measures) {
  d <- frame[frame$measure == measure, , drop = FALSE]
  for (model in names(models)) {
    if (!models[[model]]$applies(d)) next
    for (structure in models[[model]]$structures) {
      contrast_rows[[length(contrast_rows) + 1L]] <- run_model(d, measure, model, structure)
    }
  }
}
contrasts <- do.call(rbind, contrast_rows)
contrasts$facet <- unname(facets[contrasts$measure])
contrasts$expected <- unname(expected[contrasts$measure])

# ---- p-values: only where a claim rests on one, one Holm family a facet ----------------------
base_overall <- contrasts$model == "base" & contrasts$term %in% "overall"
contrasts$p[!(base_overall & contrasts$facet %in% c("primary", "convergent"))] <- NA_real_
contrasts$p_holm <- NA_real_
for (family in c("primary", "convergent")) {
  claim <- which(base_overall & contrasts$facet == family)
  contrasts$p_holm[claim] <- stats::p.adjust(contrasts$p[claim], method = "holm")
}
write_out(contrasts[c("facet", "measure", "model", "term", "estimate", "lo", "hi", "p", "p_holm", "scale",
                      "std_diff", "n_people", "n_obs", "converged", "expected", "period_test", "fit_note",
                      "dropped_visits")], "contrasts")

# ---- The divergence rule ---------------------------------------------------------------------
rule <- list(or_little = A[["construct.rule.or_little"]], or_moderate = A[["construct.rule.or_moderate"]],
             d_little = A[["construct.rule.d_little"]], d_moderate = A[["construct.rule.d_moderate"]],
             narrow_items = unlist(A[["construct.rule.narrow_items"]]),
             narrow_min_items = A[["construct.rule.narrow_min_items"]])
judged <- oaimodels::apply_divergence_rule(
  contrasts[base_overall, c("measure", "estimate", "scale", "std_diff", "lo", "hi"), drop = FALSE], rule
)
divergent <- judged[facets[judged$measure] == "divergent",
                    c("measure", "estimate", "scale", "std_diff", "band", "relative_met", "lo", "hi"),
                    drop = FALSE]
divergent$narrows <- rep(attr(judged, "narrows"), nrow(divergent))
divergent$narrow_count <- rep(attr(judged, "narrow_count"), nrow(divergent))
divergent$narrow_evaluable <- rep(attr(judged, "narrow_evaluable"), nrow(divergent))
write_out(divergent, "rule")

# ---- Discriminative validity across KL -------------------------------------------------------
person <- frame[!duplicated(frame$ID), , drop = FALSE]
kl_grades <- lapply(A[["construct.kl_groups"]], unlist)
kl_names <- names(kl_grades)
top_two <- utils::tail(kl_names, 2L)
top_alone <- sum(person$kl_group0 %in% top_two[2] & person$walker_yes %in% FALSE) >=
  A[["construct.kl4_min_nonwalkers"]]
merged <- paste0(min(unlist(kl_grades[top_two])), "-", max(unlist(kl_grades[top_two])))
kl_used <- if (top_alone) kl_names else c(setdiff(kl_names, top_two), merged)
use_kl <- function(x) {
  x <- as.character(x)
  if (!top_alone) x[x %in% top_two] <- merged
  x
}
frame$kl_used <- use_kl(frame$kl_group0)
person$kl_used <- use_kl(person$kl_group0)

kl_row <- function(analysis, group = NA_character_, measure = NA_character_, term = NA_character_,
                   estimate = NA_real_, lo = NA_real_, hi = NA_real_, p = NA_real_, n_people = NA_integer_,
                   fit_note = NA_character_) {
  data.frame(analysis = analysis, group = group, measure = measure, term = term, estimate = estimate,
             lo = lo, hi = hi, p = p, n_people = n_people, fit_note = fit_note)
}

walker_share <- function() {
  term <- paste0("or_vs_", kl_used[1])
  tryCatch({
    people <- person[stats::complete.cases(person[c("walker_yes", "kl_used", covariates)]), , drop = FALSE]
    people$kl_used <- factor(people$kl_used, levels = intersect(kl_used, people$kl_used))
    null <- stats::glm(stats::reformulate(covariates, "walker_yes"), family = stats::binomial, data = people)
    fit <- stats::update(null, . ~ . + kl_used)
    lr_p <- stats::pchisq(stats::deviance(null) - stats::deviance(fit),
                          stats::df.residual(null) - stats::df.residual(fit), lower.tail = FALSE)
    coefs <- summary(fit)$coefficients
    levels_shown <- levels(people$kl_used)[-1]
    at <- paste0("kl_used", levels_shown)
    half_width <- stats::qnorm(0.975) * coefs[at, "Std. Error"]
    kl_row("walker_share", levels_shown, "walker_yes", term, exp(coefs[at, "Estimate"]),
           exp(coefs[at, "Estimate"] - half_width), exp(coefs[at, "Estimate"] + half_width), lr_p,
           nrow(people))
  }, error = function(e) kl_row("walker_share", measure = "walker_yes", term = term,
                                fit_note = conditionMessage(e)))
}

within_kl <- function(measure, level) {
  tryCatch({
    d <- frame[frame$measure == measure & frame$kl_used %in% level, , drop = FALSE]
    fit <- with_notes(oaimodels::walker_model(fitted_rows(d, covariates), covariates, "overall",
                                              family_of(measure), corstr = corstr))
    # a CI only: no significance is claimed within a KL group
    kl_row("within_kl", level, measure, "overall", fit$estimate, fit$lo, fit$hi, NA_real_, fit$n_people,
           fit$fit_note)
  }, error = function(e) kl_row("within_kl", level, measure, "overall", fit_note = conditionMessage(e)))
}

walker_x_kl <- function(measure) {
  tryCatch({
    d <- frame[frame$measure == measure, , drop = FALSE]
    p <- oaimodels::walker_interaction_test(d, covariates, "kl_used", family_of(measure), corstr)
    kl_row("walker_x_kl", measure = measure, term = "walker_x_kl", p = as.numeric(p),
           n_people = attr(p, "n_people"),
           fit_note = if (is.null(attr(p, "test_error"))) NA_character_ else attr(p, "test_error"))
  }, error = function(e) kl_row("walker_x_kl", measure = measure, term = "walker_x_kl",
                                fit_note = conditionMessage(e)))
}

present_kl <- intersect(kl_measures, measures)
kl <- rbind(
  walker_share(),
  do.call(rbind, lapply(present_kl, function(m) do.call(rbind, lapply(kl_used, function(lv) within_kl(m, lv))))),
  do.call(rbind, lapply(present_kl, walker_x_kl))
)
# One family: the share's p counts once, however many KL groups its rows show
kl$p_holm <- NA_real_
tested <- which(kl$analysis != "within_kl" & !duplicated(kl[c("analysis", "measure")]))
kl$p_holm[tested] <- stats::p.adjust(kl$p[tested], method = "holm")
share_rows <- kl$analysis == "walker_share"
kl$p_holm[share_rows] <- kl$p_holm[share_rows][1]
kl$kl_groups_used <- paste(kl_used, collapse = ",")
kl$reporting <- ifelse(kl$analysis == A[["construct.reporting.kl_table"]], "table", "supplement")
write_out(kl[c("analysis", "group", "measure", "term", "estimate", "lo", "hi", "p", "p_holm", "n_people",
               "kl_groups_used", "reporting", "fit_note")], "kl")

# ---- Dose at 96 months -----------------------------------------------------------------------
at_96 <- frame[frame$measure == "walking_any" & frame$visit == at_visit & !is.na(frame$value), , drop = FALSE]
dose_rows <- lapply(names(amount_columns), function(grouping) {
  tryCatch({
    if (!nrow(at_96)) return(NULL)
    code <- at_96[[amount_columns[[grouping]]]]
    level <- ifelse(at_96$walk_item == 0, "no", ifelse(at_96$walk_item == 1 & !is.na(code), as.character(code), NA))
    g <- factor(level, levels = c("no", sort(unique(stats::na.omit(as.character(code))))))
    y <- at_96$value == 1
    k <- oaimodels::group_contrasts(y, g, covariates = at_96[covariates], adjust = "none")
    ok <- !is.na(y) & !is.na(g)
    tab <- table(factor(g[ok], levels = levels(g)), factor(y[ok], levels = c(FALSE, TRUE)))
    data.frame(grouping = grouping, level = k$level,
               label = answer_labels[[grouping]][as.integer(k$level)], n = k$n, n_ref = k$n_ref,
               estimate = k$adj_estimate, lo = k$adj_lo, hi = k$adj_hi, adj_n = k$adj_n,
               trend_p = stats::prop.trend.test(tab[, "TRUE"], rowSums(tab))$p.value, fit_note = NA_character_)
  }, error = function(e) {
    data.frame(grouping = grouping, level = NA_character_, label = NA_character_, n = NA_integer_,
               n_ref = NA_integer_, estimate = NA_real_, lo = NA_real_, hi = NA_real_, adj_n = NA_integer_,
               trend_p = NA_real_, fit_note = conditionMessage(e))
  })
})
dose <- do.call(rbind, dose_rows)
if (is.null(dose)) {
  dose <- data.frame(grouping = character(), level = character(), label = character(), n = integer(),
                     n_ref = integer(), estimate = numeric(), lo = numeric(), hi = numeric(), adj_n = integer(),
                     trend_p = numeric(), fit_note = character())
}
write_out(dose, "dose")

# ---- Who left: described, not tested ---------------------------------------------------------
total <- frame[frame$measure == "total" & !is.na(frame$value), , drop = FALSE]
has_96 <- unique(total$ID[total$visit == at_visit])
has_168 <- unique(total$ID[total$visit == after_visit])
total_at_enrollment <- total[total$visit == "00", , drop = FALSE]
person$pase_total_enrollment <- total_at_enrollment$value[match(person$ID, total_at_enrollment$ID)]

attrition_row <- function(group, characteristic, statistic, value, n) {
  data.frame(group = group, characteristic = characteristic, statistic = statistic, value = value, n = n)
}
numeric_rows <- function(group, characteristic, x) {
  x <- x[!is.na(x)]
  rbind(attrition_row(group, characteristic, "mean", if (length(x)) mean(x) else NA_real_, length(x)),
        attrition_row(group, characteristic, "sd", if (length(x) > 1L) stats::sd(x) else NA_real_, length(x)))
}
share_row <- function(group, characteristic, x) {
  x <- x[!is.na(x)]
  attrition_row(group, characteristic, "share", if (length(x)) mean(x) else NA_real_, length(x))
}
describe <- function(group, ids) {
  who <- person[person$ID %in% ids, , drop = FALSE]
  rbind(attrition_row(group, "people", "n", nrow(who), nrow(who)),
        numeric_rows(group, "age", who$age),
        share_row(group, "female", who$sex == 2),
        numeric_rows(group, "bmi", who$bmi),
        share_row(group, "kl_2plus", who$kl_max0 >= 2),
        numeric_rows(group, "pase_total_enrollment", who$pase_total_enrollment),
        share_row(group, "walker", who$walker_yes))
}
write_out(rbind(attrition_row("all", "pase_total_96", "n", length(has_96), length(has_96)),
                attrition_row("all", "pase_total_168", "n", length(has_168), length(has_168)),
                describe("with_168", intersect(has_96, has_168)),
                describe("without_168", setdiff(has_96, has_168))),
          "attrition")

# Last, so a run that stopped part way never says computed
write_out(data.frame(status = "computed"), "status")
cat(sprintf("construct_validity: %d contrast rows over %d measures, %d not converged; KL groups %s\n",
            nrow(contrasts), length(measures), sum(!contrasts$converged), paste(kl_used, collapse = ",")))
