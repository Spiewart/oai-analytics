# Step `models`: S2 and exam crepitus -> incident SOA to the horizon (Tables L1-L4).
#   L1  measure at each period's start visit, one period ahead (GEE; Lo 2018's design extended)
#   L2  baseline measure on every at-risk period: discrete-time hazard (GEE)
#   L3  baseline measure, SOA by the horizon among people whose outcome there is known (logistic)
#   L4  L2 by baseline subgroup with the measure x subgroup Wald test, and both measures together
# Periods after 48 months are two years long; model.period_term = "factor" adds factor(period).
# L2 and L4 are logistic (odds ratios per period, model.link); steps_oa's discrete-time models use
# a complementary log-log link with a log(span) offset (hazard ratios). Both fit with
# oaimodels::fit_cluster_gee.

A <- oaimodels::assumptions()
frame_dir <- Sys.getenv("OAI_FRAME_DIR")
out_dir <- Sys.getenv("OAI_RESULTS_DIR")
covariates <- A[["model.covariates"]]
period_term <- if (identical(A[["model.period_term"]], "factor")) "factor(period)" else character()
subgroups <- c("roa_nosx", "noroa_sx", "noroa_nosx")
levels <- c("never", "rarely", "sometimes", "often", "always")

read <- function(name) {
  d <- oaimodels::read_frame(file.path(frame_dir, sprintf("%s.parquet", name)))
  d$event <- as.integer(d$event)
  ord <- if ("period" %in% names(d)) order(d$ID, d$period) else order(d$ID)
  d[ord, , drop = FALSE]
}
frames <- list(
  s2 = list(periods = read("s2_periods"), hazard = read("s2_hazard"), horizon = read("s2_horizon")),
  exam = list(periods = read("exam_periods"), hazard = read("exam_hazard"),
              horizon = read("exam_horizon"))
)
# The exposure column and its model terms, per measure and frame kind
exposure <- function(measure, kind) {
  col <- if (measure == "s2") c(periods = "crep", hazard = "crep0", horizon = "crep0")[[kind]]
         else c(periods = "exam", hazard = "exam0", horizon = "exam0")[[kind]]
  rhs <- if (measure == "s2") sprintf("factor(%s)", col) else col
  terms <- if (measure == "s2") setNames(sprintf("factor(%s)%d", col, 1:4), levels[-1])
           else c(exam = col)
  s2_col <- c(periods = "crep", hazard = "crep0", horizon = "crep0")[[kind]]
  list(col = col, rhs = rhs, terms = terms, s2 = s2_col)
}

gee <- function(d, rhs, term) {
  oaimodels::fit_knee_gee(d, rhs, outcome = "event", term = term, corstr = A[["model.corstr"]])
}
logit <- function(d, rhs, term) oaimodels::fit_logit(d, rhs, outcome = "event", term = term)

metrics <- oaimodels::metrics_recorder()
put <- metrics$put

fit_table <- function(table, measure, kind, d, group, fit, with_period) {
  e <- exposure(measure, kind)
  extra <- if (with_period) period_term else character()
  models <- list(or_unadj = c(e$rhs, extra), or_adj = c(e$rhs, extra, covariates))
  if (measure == "exam") models$or_adj_s2 <- c(e$rhs, extra, covariates, sprintf("factor(%s)", e$s2))
  samples <- oaimodels::model_samples(d, models, A[["model.sample"]])
  rows <- list()
  for (model in names(models)) {
    dd <- samples[[model]]
    for (term in names(e$terms)) {
      est <- fit(dd, paste(models[[model]], collapse = " + "), e$terms[[term]])
      key <- sprintf("%s.%s.%s.%s.%s", table, measure, group, term, model)
      metrics$put_est(key, est)
      rows[[length(rows) + 1]] <- data.frame(measure = measure, group = group, model = model,
                                             term = term, n = nrow(dd), events = sum(dd$event),
                                             or = est[["or"]], lo = est[["lo"]], hi = est[["hi"]],
                                             p = NA_real_)
    }
  }
  do.call(rbind, rows)
}


measures <- c("s2", "exam")
oaimodels::write_rows(lapply(measures, function(m) {
  fit_table("l1", m, "periods", frames[[m]]$periods, "all", gee, TRUE)
}), "table_l1", out_dir)
oaimodels::write_rows(lapply(measures, function(m) {
  fit_table("l2", m, "hazard", frames[[m]]$hazard, "all", gee, TRUE)
}), "table_l2", out_dir)
oaimodels::write_rows(lapply(measures, function(m) {
  fit_table("l3", m, "horizon", frames[[m]]$horizon, "all", logit, FALSE)
}), "table_l3", out_dir)

# L4: L2 within each baseline subgroup; Wald test of measure x subgroup; both measures together
wald_interaction <- function(d, e) {
  base <- paste(c(e$rhs, "subgroup", period_term, covariates), collapse = " + ")
  d <- d[stats::complete.cases(d[, c("event", e$col, "subgroup", covariates)]), ]
  fit0 <- oaimodels::fit_cluster_gee(d, base, "event", stats::binomial, A[["model.corstr"]])
  fit1 <- oaimodels::fit_cluster_gee(d, c(base, paste(e$rhs, ": subgroup")), "event",
                                     stats::binomial, A[["model.corstr"]])
  list(p = stats::anova(fit1, fit0)[["P(>|Chi|)"]][1], n = nrow(d), events = sum(d$event))
}
l4 <- list()
for (m in measures) {
  d <- frames[[m]]$hazard
  e <- exposure(m, "hazard")
  for (s in subgroups) {
    l4[[length(l4) + 1]] <- fit_table("l4", m, "hazard", d[d$subgroup == s, , drop = FALSE], s, gee, TRUE)
  }
  w <- wald_interaction(d, e)
  put(sprintf("l4.%s.interaction_p", m), w$p)
  l4[[length(l4) + 1]] <- data.frame(measure = m, group = "all", model = "x_subgroup",
                                     term = "wald", n = w$n, events = w$events,
                                     or = NA_real_, lo = NA_real_, hi = NA_real_, p = w$p)
}
# Both measures in one hazard model (exam frame) with exam x any-S2: the exam OR among knees
# with S2 never (exam0), and among S2 >= 1 (exam0 + the interaction, a linear combination)
joint <- local({
  d <- frames$exam$hazard
  d <- d[stats::complete.cases(d[, c("event", "exam0", "crep0", covariates)]), ]
  d <- d[order(d$ID, d$period), ]
  rhs <- paste(c("exam0", "factor(crep0)", "exam0:I(crep0 >= 1)", period_term, covariates),
               collapse = " + ")
  fit <- oaimodels::fit_cluster_gee(d, rhs, "event", stats::binomial, A[["model.corstr"]])
  b <- stats::coef(fit)
  V <- fit$geese$vbeta
  dimnames(V) <- list(names(b), names(b))
  combos <- list(exam_if_s2_never = c(exam0 = 1),
                 exam_if_s2_any = c(exam0 = 1, "exam0:I(crep0 >= 1)TRUE" = 1),
                 exam_x_any_s2 = c("exam0:I(crep0 >= 1)TRUE" = 1))
  out <- do.call(rbind, lapply(names(combos), function(name) {
    w <- combos[[name]]
    est <- sum(w * b[names(w)])
    se <- sqrt(as.numeric(t(w) %*% V[names(w), names(w), drop = FALSE] %*% w))
    data.frame(measure = "both", group = "all", model = "joint_adj", term = name, n = nrow(d),
               events = sum(d$event), or = exp(est), lo = exp(est - 1.96 * se),
               hi = exp(est + 1.96 * se), p = NA_real_)
  }))
  for (i in seq_len(nrow(out))) {
    key <- sprintf("l4.both.joint.%s", out$term[i])
    metrics$put_est(key, out[i, ])
  }
  out
})
l4[[length(l4) + 1]] <- joint
oaimodels::write_rows(l4, "table_l4", out_dir)

metrics$write(out_dir)
cat("Tables L1-L4 written to", out_dir, "\n")
