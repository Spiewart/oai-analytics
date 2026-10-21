# Step `models`: Lo 2018 Tables 1-6. One-year models are repeated-measures GEE on the
# person-period frame (clustered on participant); four-year models are logistic regression
# with one row per person. Settings come from assumptions.toml.

A <- oaimodels::assumptions()
frame_dir <- Sys.getenv("OAI_FRAME_DIR")
out_dir <- Sys.getenv("OAI_RESULTS_DIR")
covariates <- A[["model.covariates"]]
levels <- c("never", "rarely", "sometimes", "often", "always")
subgroups <- c("roa_nosx", "noroa_sx", "noroa_nosx")

periods <- oaimodels::read_frame(file.path(frame_dir, "frame.parquet"),
                                 required = c("ID", "period", "crep", "event", covariates, "subgroup"))
persons <- oaimodels::read_frame(file.path(frame_dir, "persons.parquet"),
                                 required = c("ID", "crep0", "event", covariates, "subgroup"))
periods$event <- as.integer(periods$event)
persons$event <- as.integer(persons$event)

gee <- function(d, rhs, term) {
  oaimodels::fit_knee_gee(d, rhs, outcome = "event", term = term, corstr = A[["model.corstr"]])
}
logit <- function(d, rhs, term) oaimodels::fit_logit(d, rhs, outcome = "event", term = term)

trend_p <- function(d, crep, fit, adjust) {
  if (identical(A[["model.trend"]], "cochran_armitage")) {
    tab <- vapply(0:4, function(k) c(sum(d$event[d[[crep]] == k]), sum(d[[crep]] == k)), numeric(2))
    return(suppressWarnings(stats::prop.trend.test(tab[1, ], tab[2, ])$p.value))
  }
  est <- fit(d, paste(c(crep, adjust), collapse = " + "), crep)  # ordinal term, adjusted
  2 * stats::pnorm(-abs(est[["log_or"]] / est[["se"]]))
}

metrics <- list()
put <- function(key, value) metrics[[key]] <<- value

# One table block: cases and n per level, unadjusted and adjusted ORs for levels 1-4.
fit_block <- function(d, prefix, crep, fit, adjust, group) {
  d <- d[stats::complete.cases(d[, c("event", crep, adjust)]), , drop = FALSE]
  d <- d[order(d$ID), , drop = FALSE]
  rows <- list()
  rhs <- c(or_unadj = sprintf("factor(%s)", crep),
           or_adj = paste(c(sprintf("factor(%s)", crep), adjust), collapse = " + "))
  for (k in 0:4) {
    level <- levels[k + 1]
    part <- d[d[[crep]] == k, , drop = FALSE]
    put(sprintf("%s.%s.cases", prefix, level), sum(part$event))
    put(sprintf("%s.%s.n", prefix, level), nrow(part))
    row <- data.frame(group = group, level = level, cases = sum(part$event), n = nrow(part))
    for (model in names(rhs)) {
      est <- if (k == 0) c(or = 1, lo = NA, hi = NA) else {
        fit(d, rhs[[model]], sprintf("factor(%s)%d", crep, k))
      }
      if (k > 0) {
        put(sprintf("%s.%s.%s", prefix, level, model), est[["or"]])
        put(sprintf("%s.%s.%s.lo", prefix, level, model), est[["lo"]])
        put(sprintf("%s.%s.%s.hi", prefix, level, model), est[["hi"]])
      }
      row[[model]] <- est[["or"]]
      row[[paste0(model, ".lo")]] <- est[["lo"]]
      row[[paste0(model, ".hi")]] <- est[["hi"]]
    }
    rows[[k + 1]] <- row
  }
  out <- do.call(rbind, rows)
  out$p_trend <- trend_p(d, crep, fit, adjust)
  out
}

write_table <- function(rows, n) {
  utils::write.csv(do.call(rbind, rows), file.path(out_dir, sprintf("table%d.csv", n)),
                   row.names = FALSE)
}

# Table 1: one-year, everyone
write_table(list(fit_block(periods, "t1", "crep", gee, covariates, "all")), 1)

# Table 2: one-year, by baseline ROA / symptom subgroup
t2 <- lapply(subgroups, function(s) {
  d <- periods[periods$subgroup == s, , drop = FALSE]
  put(sprintf("t2.%s.persons", s), length(unique(d$ID)))
  put(sprintf("t2.%s.obs", s), nrow(d))
  put(sprintf("t2.%s.cases", s), sum(d$event))
  fit_block(d, sprintf("t2.%s", s), "crep", gee, covariates, s)
})
write_table(t2, 2)

# Table 3: four-year, everyone
write_table(list(fit_block(persons, "t3", "crep0", logit, covariates, "all")), 3)

# Table 4: four-year, by subgroup
write_table(lapply(subgroups, function(s) {
  fit_block(persons[persons$subgroup == s, , drop = FALSE], sprintf("t4.%s", s), "crep0", logit,
            covariates, s)
}), 4)

# Table 5: interaction of numeric crepitus with each covariate (four-year model), not graded
interaction_p <- function(d, covariate) {
  rhs <- paste(c(sprintf("crep0 * %s", covariate), setdiff(covariates, covariate)), collapse = " + ")
  model <- stats::glm(stats::as.formula(paste("event ~", rhs)), data = d, family = stats::binomial)
  coefs <- summary(model)$coefficients
  coefs[sprintf("crep0:%s", covariate), "Pr(>|z|)"]
}
t5 <- do.call(rbind, lapply(c("all", subgroups), function(g) {
  d <- if (g == "all") persons else persons[persons$subgroup == g, , drop = FALSE]
  data.frame(group = g, age = interaction_p(d, "age"), sex = interaction_p(d, "sex"),
             bmi = interaction_p(d, "bmi"))
}))
utils::write.csv(t5, file.path(out_dir, "table5.csv"), row.names = FALSE)

# Table 6: four-year, by sex (adjusted for age and BMI) and age (adjusted for sex and BMI)
strata <- list(
  men = list(rows = persons$sex == 1, adjust = setdiff(covariates, "sex")),
  women = list(rows = persons$sex == 2, adjust = setdiff(covariates, "sex")),
  age_lt65 = list(rows = persons$age < 65, adjust = setdiff(covariates, "age")),
  age_ge65 = list(rows = persons$age >= 65, adjust = setdiff(covariates, "age"))
)
write_table(lapply(names(strata), function(s) {
  d <- persons[which(strata[[s]]$rows), , drop = FALSE]
  put(sprintf("t6.%s.persons", s), nrow(d))
  put(sprintf("t6.%s.cases", s), sum(d$event))
  fit_block(d, sprintf("t6.%s", s), "crep0", logit, strata[[s]]$adjust, s)
}), 6)

utils::write.csv(data.frame(metric = names(metrics), value = unlist(metrics)),
                 file.path(out_dir, "metrics_models.csv"), row.names = FALSE)
cat("Tables 1-6 written to", out_dir, "\n")
