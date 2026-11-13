# Step `models`: crepitus and device-measured activity at 48 and 72 months, both directions.
#   A1  activity ~ crepitus count at the same wave (48: exam, S2; 72: S2)
#   A2  activity at 72 ~ crepitus count at 48 + activity at 48 (exam, S2, then both)
#   A3  activity at 72 ~ crepitus change (S2 48->72 concurrent; exam and S2 36->48 preceding)
#       + the earlier count + activity at 48
#   B1  S2 count at 72 ~ activity at 48 (+ its change to 72) + S2 count at 48   (proportional odds)
#   B2  S2 count at 96 ~ activity at 48 + its change + S2 count at 72          (proportional odds)
#   B3  new exam crepitus at 120 (knees free of it at 48) ~ activity at 48 (+ change)  (logistic GEE)
# A models are gaussian GEE on persons (independence; sandwich SEs). Model m1 adjusts for age,
# sex, BMI and wear hours at every device wave the model spans (both waves in A2, A3 and the
# change models); m2 adds the higher KL grade and the worse knee's WOMAC pain. Activity
# is per 1,000 steps/day or per 10 min/day (ratios under activity.transform = "log").
# B terms: `baseline` = activity at 48 in the model without change (everyone valid at 48);
# `baseline_adj` and `change` = the model with the 48->72 change (valid at both waves).

A <- oaimodels::assumptions()
frame_dir <- Sys.getenv("OAI_FRAME_DIR")
out_dir <- Sys.getenv("OAI_RESULTS_DIR")
measures <- A[["activity.measures"]]
log_scale <- identical(A[["activity.transform"]], "log")
source("covariates.R")
models <- c("m1", "m2")
# Covariates for a model spanning these device waves (wear time at each of them)
covs <- function(model, waves) covariates_for(A, model, waves)
both_waves <- c("48", "72")
unit <- c(steps = 1000, mv_min = 10, light_min = 10)
MIN_LEVEL <- 5

persons <- oaimodels::read_frame(file.path(frame_dir, "persons.parquet"))
knees <- oaimodels::read_frame(file.path(frame_dir, "knees120.parquet"))
scale_activity <- function(d) {
  for (m in measures) {
    for (suffix in c("48", "72")) {
      col <- sprintf("%s_%s", m, suffix)
      d[[col]] <- if (log_scale) log(d[[col]] + 1) else d[[col]] / unit[[m]]
    }
    d[[sprintf("%s_change", m)]] <- d[[sprintf("%s_72", m)]] - d[[sprintf("%s_48", m)]]
  }
  d[order(d$ID), , drop = FALSE]
}
persons <- scale_activity(persons)
knees <- scale_activity(knees)

rows <- list()
metrics <- oaimodels::metrics_recorder()
na_est <- c(estimate = NA_real_, lo = NA_real_, hi = NA_real_)
record <- function(table, activity, crepitus, term, model, n, est) {
  rows[[length(rows) + 1]] <<- data.frame(table = table, activity = activity, crepitus = crepitus,
                                          term = term, model = model, n = n,
                                          estimate = est[["estimate"]], lo = est[["lo"]],
                                          hi = est[["hi"]])
  key <- sprintf("%s.%s.%s.%s.%s", table, activity, crepitus, term, model)
  metrics$put_est(key, est, "estimate")
  metrics$put(paste0(key, ".n"), n)
}
complete <- function(d, vars) d[stats::complete.cases(d[, unique(vars), drop = FALSE]), , drop = FALSE]
sparse <- function(d, factor_var) {
  if (is.null(factor_var)) return(FALSE)
  counts <- table(d[[factor_var]])
  length(counts) < 2 || any(counts < MIN_LEVEL)
}

# Gaussian GEE on persons: difference (or ratio under log) per unit of each named term
fit_linear <- function(d, outcome, rhs, terms) {
  fit <- tryCatch(geepack::geeglm(stats::as.formula(paste(outcome, "~", paste(rhs, collapse = " + "))),
                                  id = ID, data = d, family = stats::gaussian, corstr = "independence"),
                  error = function(e) NULL)
  lapply(terms, function(term) {
    if (is.null(fit)) return(na_est)
    co <- summary(fit)$coefficients
    if (!term %in% rownames(co)) return(na_est)
    b <- co[term, "Estimate"]; se <- co[term, "Std.err"]
    est <- c(estimate = b, lo = b - 1.96 * se, hi = b + 1.96 * se)
    if (log_scale) exp(est) else est
  })
}

# Proportional odds on the 0/1/2 crepitus count: odds ratio per unit of each named term
fit_ordinal <- function(d, outcome, rhs, terms) {
  d$y_ <- factor(d[[outcome]], levels = 0:2, ordered = TRUE)
  fit <- tryCatch(MASS::polr(stats::as.formula(paste("y_ ~", paste(rhs, collapse = " + "))),
                             data = d, Hess = TRUE),
                  error = function(e) NULL)
  lapply(terms, function(term) {
    if (is.null(fit)) return(na_est)
    co <- summary(fit)$coefficients
    if (!term %in% rownames(co)) return(na_est)
    b <- co[term, "Value"]; se <- co[term, "Std. Error"]
    exp(c(estimate = b, lo = b - 1.96 * se, hi = b + 1.96 * se))
  })
}

fit_gee_logit <- function(d, rhs, terms) {
  lapply(terms, function(term) {
    est <- tryCatch(oaimodels::fit_knee_gee(d, paste(rhs, collapse = " + "), outcome = "event",
                                            term = term, corstr = A[["model.corstr"]]),
                    error = function(e) NULL)
    if (is.null(est)) na_est else c(estimate = est[["or"]], lo = est[["lo"]], hi = est[["hi"]])
  })
}

# A: crepitus count as linear (per_knee) and as a factor (k1, k2 vs 0)
count_terms <- function(table, d, m, crepitus, outcome, count, extra, wave, model) {
  vars <- c(outcome, count, extra, covs(model, wave))
  dd <- complete(d, vars)
  est <- fit_linear(dd, outcome, c(count, extra, covs(model, wave)), count)
  record(table, m, crepitus, "per_knee", model, nrow(dd), est[[1]])
  dd$count_f <- factor(dd[[count]], levels = 0:2)
  est <- if (sparse(dd, "count_f")) list(na_est, na_est) else
    fit_linear(dd, outcome, c("count_f", extra, covs(model, wave)), c("count_f1", "count_f2"))
  record(table, m, crepitus, "k1", model, nrow(dd), est[[1]])
  record(table, m, crepitus, "k2", model, nrow(dd), est[[2]])
}

for (m in measures) {
  a48 <- sprintf("%s_48", m); a72 <- sprintf("%s_72", m); change <- sprintf("%s_change", m)
  for (model in models) {
    # A1
    count_terms("a1", persons, m, "exam", a48, "exam_48", character(), "48", model)
    count_terms("a1", persons, m, "s2", a48, "s2_48", character(), "48", model)
    count_terms("a1", persons, m, "s2_at72", a72, "s2_72", character(), "72", model)
    # A2
    count_terms("a2", persons, m, "exam", a72, "exam_48", a48, both_waves, model)
    count_terms("a2", persons, m, "s2", a72, "s2_48", a48, both_waves, model)
    dd <- complete(persons, c(a72, "exam_48", "s2_48", a48, covs(model, both_waves)))
    est <- fit_linear(dd, a72, c("exam_48", "s2_48", a48, covs(model, both_waves)), c("exam_48", "s2_48"))
    record("a2", m, "both_exam", "per_knee", model, nrow(dd), est[[1]])
    record("a2", m, "both_s2", "per_knee", model, nrow(dd), est[[2]])
    # A3
    a3 <- list(s2_48_72 = c("s2_change_48_72", "s2_48"), s2_36_48 = c("s2_change_36_48", "s2_36"),
               exam_36_48 = c("exam_change_36_48", "exam_36"))
    for (crepitus in names(a3)) {
      rhs <- c(a3[[crepitus]], a48, covs(model, both_waves))
      dd <- complete(persons, c(a72, rhs))
      record("a3", m, crepitus, "change", model, nrow(dd), fit_linear(dd, a72, rhs, a3[[crepitus]][1])[[1]])
    }
    # B1, B2: S2 count at 72 and at 96 months
    b <- list(b1 = list(outcome = "s2_72", prior = "s2_48"), b2 = list(outcome = "s2_96", prior = "s2_72"))
    for (table in names(b)) {
      outcome <- b[[table]]$outcome; prior <- sprintf("factor(%s)", b[[table]]$prior)
      base_rhs <- c(a48, prior, covs(model, "48"))
      dd <- complete(persons, c(outcome, a48, b[[table]]$prior, covs(model, "48")))
      record(table, m, "s2", "baseline", model, nrow(dd), fit_ordinal(dd, outcome, base_rhs, a48)[[1]])
      dd <- complete(persons, c(outcome, a48, change, b[[table]]$prior, covs(model, both_waves)))
      est <- fit_ordinal(dd, outcome, c(a48, change, prior, covs(model, both_waves)), c(a48, change))
      record(table, m, "s2", "baseline_adj", model, nrow(dd), est[[1]])
      record(table, m, "s2", "change", model, nrow(dd), est[[2]])
    }
    # B3: new exam crepitus at 120 months, knee level
    dd <- complete(knees, c("event", a48, covs(model, "48")))
    record("b3", m, "exam", "baseline", model, nrow(dd),
           fit_gee_logit(dd, c(a48, covs(model, "48")), a48)[[1]])
    dd <- complete(knees, c("event", a48, change, covs(model, both_waves)))
    est <- fit_gee_logit(dd, c(a48, change, covs(model, both_waves)), c(a48, change))
    record("b3", m, "exam", "baseline_adj", model, nrow(dd), est[[1]])
    record("b3", m, "exam", "change", model, nrow(dd), est[[2]])
  }
}

all_rows <- do.call(rbind, rows)
for (table in unique(all_rows$table)) {
  utils::write.csv(all_rows[all_rows$table == table, ], file.path(out_dir, sprintf("table_%s.csv", table)),
                   row.names = FALSE)
}
metrics$write(out_dir)
cat("Tables A1-A3 and B1-B3 written to", out_dir, "\n")
