# Step `models`: palpable crepitus and incident SOA (Tables E1-E6) with the Lo 2018 design,
# and the Mahmoudian 2023 anchor ORs (Table M1). One-year models are repeated-measures GEE on
# person-periods (clustered on participant); four-year and anchor models are logistic.

A <- oaimodels::assumptions()
frame_dir <- Sys.getenv("OAI_FRAME_DIR")
out_dir <- Sys.getenv("OAI_RESULTS_DIR")
covariates <- A[["model.covariates"]]
subgroups <- c("roa_nosx", "noroa_sx", "noroa_nosx")

periods <- oaimodels::read_frame(file.path(frame_dir, "frame.parquet"),
                                 required = c("ID", "exam", "crep", "event", covariates, "subgroup"))
persons <- oaimodels::read_frame(file.path(frame_dir, "persons.parquet"),
                                 required = c("ID", "exam0", "crep0", "event", covariates, "subgroup"))
anchor <- oaimodels::read_frame(file.path(frame_dir, "anchor.parquet"),
                                required = c("ID", "exam0", "structural", "structural_sx",
                                             "age", "sex", "bmi", "kl0"))
periods$event <- as.integer(periods$event)
persons$event <- as.integer(persons$event)

gee <- function(d, rhs, term, outcome = "event") {
  oaimodels::fit_knee_gee(d, rhs, outcome = outcome, term = term, corstr = A[["model.corstr"]])
}
logit <- function(d, rhs, term, outcome = "event") {
  oaimodels::fit_logit(d, rhs, outcome = outcome, term = term)
}

metrics <- list()
put <- function(key, value) metrics[[key]] <<- value

# One group: cell counts, then unadjusted, adjusted and S2-adjusted ORs for the exam item.
fit_block <- function(d, prefix, exam, s2, fit, adjust, group) {
  d <- d[!is.na(d[[exam]]) & !is.na(d$event), , drop = FALSE]
  for (level in c("yes", "no")) {
    part <- d[d[[exam]] == (level == "yes"), , drop = FALSE]
    put(sprintf("%s.%s.cases", prefix, level), sum(part$event))
    put(sprintf("%s.%s.n", prefix, level), nrow(part))
  }
  models <- list(
    or_unadj = list(rhs = exam, needs = character()),
    or_adj = list(rhs = paste(c(exam, adjust), collapse = " + "), needs = adjust),
    or_adj_s2 = list(rhs = paste(c(exam, adjust, sprintf("factor(%s)", s2)), collapse = " + "),
                     needs = c(adjust, s2))
  )
  rows <- lapply(names(models), function(model) {
    dd <- d[stats::complete.cases(d[, c("event", exam, models[[model]]$needs), drop = FALSE]), ]
    dd <- dd[order(dd$ID), , drop = FALSE]
    est <- fit(dd, models[[model]]$rhs, exam)
    put(sprintf("%s.exam.%s", prefix, model), est[["or"]])
    put(sprintf("%s.exam.%s.lo", prefix, model), est[["lo"]])
    put(sprintf("%s.exam.%s.hi", prefix, model), est[["hi"]])
    data.frame(group = group, model = model, n = nrow(dd), events = sum(dd$event),
               exposed_n = sum(dd[[exam]] == 1), exposed_events = sum(dd$event[dd[[exam]] == 1]),
               or = est[["or"]], lo = est[["lo"]], hi = est[["hi"]])
  })
  do.call(rbind, rows)
}

write_table <- function(rows, name) {
  utils::write.csv(do.call(rbind, rows), file.path(out_dir, sprintf("table_%s.csv", name)),
                   row.names = FALSE)
}

# E1, E2: one-year, everyone and by baseline subgroup
write_table(list(fit_block(periods, "e1", "exam", "crep", gee, covariates, "all")), "e1")
write_table(lapply(subgroups, function(s) {
  fit_block(periods[periods$subgroup == s, , drop = FALSE], sprintf("e2.%s", s), "exam", "crep",
            gee, covariates, s)
}), "e2")

# E3, E4: four-year (baseline exam), everyone and by subgroup
write_table(list(fit_block(persons, "e3", "exam0", "crep0", logit, covariates, "all")), "e3")
write_table(lapply(subgroups, function(s) {
  fit_block(persons[persons$subgroup == s, , drop = FALSE], sprintf("e4.%s", s), "exam0",
            "crep0", logit, covariates, s)
}), "e4")

# E5: interaction of the exam item with each covariate and S2 (four-year), not graded
interaction_p <- function(d, covariate) {
  others <- setdiff(c(covariates, "crep0"), covariate)
  rhs <- paste(c(sprintf("exam0 * %s", covariate), others), collapse = " + ")
  d <- d[stats::complete.cases(d[, c("event", "exam0", covariates, "crep0")]), ]
  model <- stats::glm(stats::as.formula(paste("event ~", rhs)), data = d, family = stats::binomial)
  summary(model)$coefficients[sprintf("exam0:%s", covariate), "Pr(>|z|)"]
}
e5 <- do.call(rbind, lapply(c("all", subgroups), function(g) {
  d <- if (g == "all") persons else persons[persons$subgroup == g, , drop = FALSE]
  data.frame(group = g, age = interaction_p(d, "age"), sex = interaction_p(d, "sex"),
             bmi = interaction_p(d, "bmi"), s2 = interaction_p(d, "crep0"))
}))
utils::write.csv(e5, file.path(out_dir, "table_e5.csv"), row.names = FALSE)

# E6: four-year by sex (adjusted for age, BMI) and age (adjusted for sex, BMI), as Lo 2018 Table 6
strata <- list(
  men = list(rows = persons$sex == 1, adjust = setdiff(covariates, "sex")),
  women = list(rows = persons$sex == 2, adjust = setdiff(covariates, "sex")),
  age_lt65 = list(rows = persons$age < 65, adjust = setdiff(covariates, "age")),
  age_ge65 = list(rows = persons$age >= 65, adjust = setdiff(covariates, "age"))
)
write_table(lapply(names(strata), function(s) {
  fit_block(persons[which(strata[[s]]$rows), , drop = FALSE], sprintf("e6.%s", s), "exam0",
            "crep0", logit, strata[[s]]$adjust, s)
}), "e6")

# M1: Mahmoudian 2023 anchor (one knee per subject), crude / age, sex, BMI / plus KL
m1 <- do.call(rbind, lapply(c("structural", "structural_sx"), function(outcome) {
  d <- anchor[!is.na(anchor[[outcome]]), , drop = FALSE]
  d[[outcome]] <- as.integer(d[[outcome]])
  rhs <- c(or_crude = "exam0", or_adj = "exam0 + age + sex + bmi",
           or_adj_kl = "exam0 + age + sex + bmi + factor(kl0)")
  do.call(rbind, lapply(names(rhs), function(model) {
    dd <- d[stats::complete.cases(d[, c(outcome, "exam0", "age", "sex", "bmi", "kl0")]), ]
    est <- logit(dd, rhs[[model]], "exam0", outcome = outcome)
    put(sprintf("m.%s.%s", outcome, model), est[["or"]])
    put(sprintf("m.%s.%s.lo", outcome, model), est[["lo"]])
    put(sprintf("m.%s.%s.hi", outcome, model), est[["hi"]])
    data.frame(outcome = outcome, model = model, n = nrow(dd), events = sum(dd[[outcome]]),
               or = est[["or"]], lo = est[["lo"]], hi = est[["hi"]])
  }))
}))
utils::write.csv(m1, file.path(out_dir, "table_m1.csv"), row.names = FALSE)

utils::write.csv(data.frame(metric = names(metrics), value = unlist(metrics)),
                 file.path(out_dir, "metrics_models.csv"), row.names = FALSE)
cat("Tables E1-E6 and M1 written to", out_dir, "\n")
