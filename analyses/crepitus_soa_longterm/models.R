# Step `models`: S2 and exam crepitus -> incident SOA to the horizon (Tables L1-L4).
#   L1  measure at each period's start visit, one period ahead (GEE; Lo 2018's design extended)
#   L2  baseline measure on every at-risk period: discrete-time hazard (GEE)
#   L3  baseline measure, SOA by the horizon among people whose outcome there is known (logistic)
#   L4  L2 by baseline subgroup with the measure x subgroup Wald test, and both measures together
# Periods after 48 months are two years long; model.period_term = "factor" adds factor(period).

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

metrics <- list()
put <- function(key, value) metrics[[key]] <<- value

fit_table <- function(table, measure, kind, d, group, fit, with_period) {
  e <- exposure(measure, kind)
  extra <- if (with_period) period_term else character()
  models <- list(or_unadj = c(e$rhs, extra), or_adj = c(e$rhs, extra, covariates))
  if (measure == "exam") models$or_adj_s2 <- c(e$rhs, extra, covariates, sprintf("factor(%s)", e$s2))
  rows <- list()
  for (model in names(models)) {
    needs <- unique(c("event", e$col, covariates[covariates %in% models[[model]]],
                      if (model == "or_adj_s2") e$s2, if (with_period && length(period_term)) "period"))
    dd <- d[stats::complete.cases(d[, needs, drop = FALSE]), , drop = FALSE]
    for (term in names(e$terms)) {
      est <- fit(dd, paste(models[[model]], collapse = " + "), e$terms[[term]])
      key <- sprintf("%s.%s.%s.%s.%s", table, measure, group, term, model)
      put(key, est[["or"]]); put(paste0(key, ".lo"), est[["lo"]]); put(paste0(key, ".hi"), est[["hi"]])
      rows[[length(rows) + 1]] <- data.frame(measure = measure, group = group, model = model,
                                             term = term, n = nrow(dd), events = sum(dd$event),
                                             or = est[["or"]], lo = est[["lo"]], hi = est[["hi"]])
    }
  }
  do.call(rbind, rows)
}

write_table <- function(rows, name) {
  utils::write.csv(do.call(rbind, rows), file.path(out_dir, sprintf("table_%s.csv", name)),
                   row.names = FALSE)
}

measures <- c("s2", "exam")
write_table(lapply(measures, function(m) {
  fit_table("l1", m, "periods", frames[[m]]$periods, "all", gee, TRUE)
}), "l1")
write_table(lapply(measures, function(m) {
  fit_table("l2", m, "hazard", frames[[m]]$hazard, "all", gee, TRUE)
}), "l2")
write_table(lapply(measures, function(m) {
  fit_table("l3", m, "horizon", frames[[m]]$horizon, "all", logit, FALSE)
}), "l3")

# L4: L2 within each baseline subgroup; Wald test of measure x subgroup; both measures together
wald_interaction <- function(d, e) {
  base <- paste(c(e$rhs, "subgroup", period_term, covariates), collapse = " + ")
  d <- d[stats::complete.cases(d[, c("event", e$col, "subgroup", covariates)]), ]
  d <- d[order(d$ID), ]
  fit0 <- geepack::geeglm(stats::as.formula(paste("event ~", base)), id = ID, data = d,
                          family = stats::binomial, corstr = A[["model.corstr"]])
  fit1 <- geepack::geeglm(stats::as.formula(paste("event ~", base, "+", e$rhs, ": subgroup")),
                          id = ID, data = d, family = stats::binomial, corstr = A[["model.corstr"]])
  stats::anova(fit1, fit0)[["P(>|Chi|)"]][1]
}
l4 <- list()
for (m in measures) {
  d <- frames[[m]]$hazard
  e <- exposure(m, "hazard")
  for (s in subgroups) {
    l4[[length(l4) + 1]] <- fit_table("l4", m, "hazard", d[d$subgroup == s, , drop = FALSE], s, gee, TRUE)
  }
  p <- wald_interaction(d, e)
  put(sprintf("l4.%s.interaction_p", m), p)
  l4[[length(l4) + 1]] <- data.frame(measure = m, group = "all", model = "x_subgroup",
                                     term = "wald_p", n = nrow(d), events = sum(d$event),
                                     or = NA, lo = NA, hi = p)
}
# Both measures in one hazard model (exam frame), with their interaction (exam x any S2)
joint <- local({
  d <- frames$exam$hazard
  d <- d[stats::complete.cases(d[, c("event", "exam0", "crep0", covariates)]), ]
  d <- d[order(d$ID, d$period), ]
  rhs <- paste(c("exam0", "factor(crep0)", "exam0:I(crep0 >= 1)", period_term, covariates),
               collapse = " + ")
  rows <- lapply(c(exam = "exam0", interaction = "exam0:I(crep0 >= 1)TRUE"), function(term) {
    est <- gee(d, rhs, term)
    data.frame(measure = "both", group = "all", model = "joint_adj", term = term, n = nrow(d),
               events = sum(d$event), or = est[["or"]], lo = est[["lo"]], hi = est[["hi"]])
  })
  out <- do.call(rbind, rows)
  out$term <- c("exam", "exam_x_any_s2")
  for (i in seq_len(nrow(out))) {
    key <- sprintf("l4.both.joint.%s", out$term[i])
    put(key, out$or[i]); put(paste0(key, ".lo"), out$lo[i]); put(paste0(key, ".hi"), out$hi[i])
  }
  out
})
l4[[length(l4) + 1]] <- joint
write_table(l4, "l4")

utils::write.csv(data.frame(metric = names(metrics), value = unlist(metrics)),
                 file.path(out_dir, "metrics_models.csv"), row.names = FALSE)
cat("Tables L1-L4 written to", out_dir, "\n")
