# Step `posthoc`: post hoc checks on P1 (user request 2026-11-12, after the primary results).
#   sex       steps x women interaction; P1 within men and within women (linear and >= top band)
#   injury    P1 with injury_48 (and baseline knee surgery) added; within uninjured and injured
#             knees; steps x injury interaction
#   read      odds of a later reading per 1,000 steps/day (per log unit under steps.transform = log) (logistic GEE): any reading, and
#             status known by the horizon
#   reweight  P1 weighted by the inverse probability of being read at each interval end
#             (stabilized), from a logistic model of the knees at risk entering the interval
#             (steps, the model's covariates, and posthoc.weight_predictors)
# Models are P1's: grouped-time cloglog GEE, factor(end_visit), offset(log(span)), independence,
# person-clustered SEs; m1 and m2 covariates as in models.R. Writes posthoc_p1.csv and
# posthoc_weights.csv (aggregate).

suppressPackageStartupMessages(library(geepack))
A <- oaimodels::assumptions()
frame_dir <- Sys.getenv("OAI_FRAME_DIR")
out_dir <- Sys.getenv("OAI_RESULTS_DIR")
aux <- A[["posthoc.weight_predictors"]]
known_aux <- c("interim_womac", "interim_freq_pain", "interim_missed")
if (length(setdiff(aux, known_aux))) stop("unknown posthoc.weight_predictors: ", setdiff(aux, known_aux))
edges <- as.numeric(A[["steps.bands"]])
INTERIM <- c("08" = "07", "10" = "09", "12" = "11")
log_scale <- identical(A[["steps.transform"]], "log")
lin_term <- if (log_scale) "per_log" else "per_1000"  # as in models.R

read <- function(name) {
  d <- as.data.frame(oaimodels::read_frame(file.path(frame_dir, sprintf("%s.parquet", name))))
  d$x <- if (log_scale) log(d$steps_48 + 1) else d$steps_48 / 1000
  d$women <- as.integer(d$sex == 2)
  d$band <- cut(d$steps_48, c(-Inf, edges, Inf), right = FALSE)
  levels(d$band) <- paste0("b", seq_along(levels(d$band)))
  d$key <- paste(d$ID, d$SIDE)
  d
}
p <- read("posthoc_periods")
p$event <- as.integer(p$event)
p$inj <- as.integer(p$injury_48)
p$surg <- as.integer(p$surgery_00)
h <- read("posthoc_read")
ENDS <- sort(unique(p$end_visit))
if (!all(ENDS %in% names(INTERIM))) stop("no interim visit for reading(s) ", setdiff(ENDS, names(INTERIM)))
TOP <- paste0("b", length(edges) + 1)

covs <- list(m1 = c("age", "women", "bmi", "wear_hr_48"),
             m2 = c("age", "women", "bmi", "wear_hr_48", "kl48", "womac48"))

fit <- function(d, rhs, periods = TRUE, weights = NULL) {
  vars <- unique(c("event", all.vars(stats::reformulate(rhs)), if (periods) c("end_visit", "span"),
                   weights))
  d <- d[stats::complete.cases(d[, vars, drop = FALSE]), , drop = FALSE]
  d <- d[order(d$ID), , drop = FALSE]
  d$cl_ <- match(d$ID, unique(d$ID))
  terms <- c(rhs, if (periods) c("factor(end_visit)", "offset(log(span))"))
  f <- stats::reformulate(terms, "event")
  fam <- if (periods) stats::binomial(link = "cloglog") else stats::binomial()
  d$w_ <- if (is.null(weights)) 1 else d[[weights]]
  g <- tryCatch(
    suppressWarnings(geeglm(f, id = cl_, data = d, family = fam, corstr = "independence",
                            weights = w_)),
    error = function(e) { message("fit failed: ", conditionMessage(e)); NULL })
  list(fit = g, n = nrow(unique(d[, c("ID", "SIDE")])), events = sum(d$event))
}

rows <- list()
record <- function(check, subset, model, term, res, coef = term) {
  est <- c(NA_real_, NA_real_, NA_real_, NA_real_)
  if (!is.null(res$fit)) {
    co <- summary(res$fit)$coefficients
    if (coef %in% rownames(co)) {
      b <- co[coef, "Estimate"]; se <- co[coef, "Std.err"]
      est <- c(exp(b), exp(b - 1.96 * se), exp(b + 1.96 * se), co[coef, "Pr(>|W|)"])
    }
  }
  rows[[length(rows) + 1]] <<- data.frame(check = check, subset = subset, model = model,
    term = term, n = res$n, events = res$events, estimate = est[1], lo = est[2], hi = est[3],
    p = est[4])
}
lin <- function(check, subset, model, d, cv, extra = character()) {
  record(check, subset, model, lin_term, fit(d, c("x", cv, extra)), "x")
}
top <- function(check, subset, model, d, cv, extra = character()) {
  record(check, subset, model, "band_top", fit(d, c("band", cv, extra)), paste0("band", TOP))
}

for (m in names(covs)) {
  cv <- covs[[m]]
  lin("p1", "all", m, p, cv)
  top("p1", "all", m, p, cv)

  # ---- sex
  record("sex", "all", m, "steps_x_women", fit(p, c("x", cv, "x:women")), "x:women")
  for (s in c(men = 1, women = 2)) {
    ds <- p[p$sex == s, , drop = FALSE]
    label <- names(c(men = 1, women = 2))[c(men = 1, women = 2) == s]
    lin("sex", label, m, ds, setdiff(cv, "women"))
    top("sex", label, m, ds, setdiff(cv, "women"))
  }

  # ---- knee injury by 48 months
  pk <- p[!is.na(p$inj), , drop = FALSE]
  lin("injury", "flag_known", m, pk, cv)
  r <- fit(pk, c("x", cv, "inj"))
  record("injury", "adjusted", m, lin_term, r, "x")
  record("injury", "adjusted", m, "injury_48", r, "inj")
  lin("injury", "adjusted_surgery", m, pk, cv, c("inj", "surg"))
  top("injury", "adjusted", m, pk, cv, "inj")
  lin("injury", "uninjured", m, pk[pk$inj == 0, , drop = FALSE], cv)
  lin("injury", "injured", m, pk[pk$inj == 1, , drop = FALSE], cv)
  record("injury", "all", m, "steps_x_injury", fit(pk, c("x", cv, "inj", "x:inj")), "x:inj")

  # ---- being read (one row per knee; logistic)
  hk <- h
  hk$event <- as.integer(hk$any_read)
  record("read", "any_reading", m, lin_term, fit(hk, c("x", cv), periods = FALSE), "x")
  hk$event <- as.integer(hk$known)
  record("read", "status_known", m, lin_term, fit(hk, c("x", cv), periods = FALSE), "x")
}

# ---- reweighting: stabilized inverse probability of being read at each interval end
weights_rows <- list()
for (m in names(covs)) {
  cv <- covs[[m]]
  w_all <- list()
  for (v in ENDS) {
    iv <- INTERIM[[v]]
    r <- h[!h[[paste0("prior_event_", v)]], , drop = FALSE]
    r$o <- as.integer(r[[paste0("read_", v)]])
    r$aux_womac <- r[[paste0("womac_", iv)]]
    r$aux_missed <- as.integer(is.na(r$aux_womac))
    r$aux_womac[is.na(r$aux_womac)] <- 0
    r$aux_freq <- as.integer(r[[paste0("freq_pain_", iv)]] %in% TRUE)
    predictors <- c("steps_48", cv,
                    c(interim_womac = "aux_womac", interim_freq_pain = "aux_freq",
                      interim_missed = "aux_missed")[aux])
    r <- r[stats::complete.cases(r[, c("o", predictors)]), , drop = FALSE]
    g <- stats::glm(stats::reformulate(predictors, "o"), family = stats::binomial(), data = r)
    ph <- stats::fitted(g)
    w <- mean(r$o) / ph
    b <- stats::coef(g)[["steps_48"]] * 1000
    se <- sqrt(stats::vcov(g)["steps_48", "steps_48"]) * 1000
    weights_rows[[length(weights_rows) + 1]] <- data.frame(
      model = m, interval_end = v, at_risk = nrow(r), read = sum(r$o),
      or_per_1000 = exp(b), lo = exp(b - 1.96 * se), hi = exp(b + 1.96 * se),
      weight_min = min(w[r$o == 1]), weight_max = max(w[r$o == 1]))
    w_all[[v]] <- data.frame(key = r$key, end_visit = v, w = w)
  }
  W <- do.call(rbind, w_all)
  pw <- merge(p, W, by = c("key", "end_visit"))
  n_p1 <- sum(stats::complete.cases(p[, c("x", cv)]))
  if (nrow(pw) != n_p1) message("reweight ", m, ": ", n_p1 - nrow(pw), " P1 rows without a weight")
  record("reweight", "weighted", m, lin_term, fit(pw, c("x", cv), weights = "w"), "x")
  record("reweight", "weighted", m, "band_top",
         fit(pw, c("band", cv), weights = "w"), paste0("band", TOP))
}

utils::write.csv(do.call(rbind, rows), file.path(out_dir, "posthoc_p1.csv"), row.names = FALSE)
utils::write.csv(do.call(rbind, weights_rows), file.path(out_dir, "posthoc_weights.csv"),
                 row.names = FALSE)
