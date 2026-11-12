# Step `models`: GT1M steps at 48 months (and their change to 72) and incident and progressive
# knee OA (forward), and new knee OA and later steps (reverse).
#   P1   incident ROA, discrete time by visit (periods_roa; by_horizon: horizon_roa)
#   P2   incident SOA, the same (periods_soa / horizon_soa); also within roa48 True and False
#        Each P model: linear (per_1000), step bands (band_*, vs the lowest band) and a
#        restricted cubic spline (nonlinear_p, and curve_p{1,2}.csv for m1)
#   S1   incident ROA and SOA after 72 months: steps_48 (baseline_adj) + steps_change (change)
#   S2   knee replacement in the incident-ROA knees: Cox if >= tkr.min_events, else band counts
#   S3   Cox replacement in knees with KL >= 2 at 48; KL and JSN worsening in read knees (GEE)
#   S3b  medial minimum JSW: progressor (logistic GEE) and change_mm (gaussian GEE), for
#        steps_48 and for steps_48 + steps_change
#   S4   P1 and P2 with MV minutes/day at 48 months (per 10 min/day)
#   R1   steps_72 ~ new OA 36->48 + steps_48     (person level, gaussian GEE, independence)
#   R2   steps_72 ~ new OA 48->72 + steps_48     (reverse.r2_kl_read: with KL worsening, read knees)
#   R3   mean and SD of steps_48 by the higher KL grade and by SOA at 48 months (descriptive)
# Every model runs as m1 (age, sex, BMI, wear at each wave) and m2 (+ the knee's KL and WOMAC
# pain at 48 for knee models; + the higher KL and the worse knee's pain for person models), on
# complete cases of its own terms. A fit error, or a band with fewer than MIN_EVENTS events,
# writes NA. Knee models: odds ratios (hazard ratios for Cox; mm for change_mm). Reverse models:
# the difference in steps_72 in 1,000 steps/day (ratio of steps_72 + 1 under steps.transform =
# "log"). Under "log", steps enter as log(steps + 1) and `per_1000` is named `per_log` (S4:
# `per_10min` becomes `per_log`). Bands and spline always use steps/day.
# Table columns: n is knees (persons for R); events is knees with the outcome (R1/R2: people
# with the exposure; R3: blank).

suppressPackageStartupMessages(library(survival))
A <- oaimodels::assumptions()
frame_dir <- Sys.getenv("OAI_FRAME_DIR")
out_dir <- Sys.getenv("OAI_RESULTS_DIR")
source("covariates.R")
source("shape.R")

models <- c("m1", "m2")
log_scale <- identical(A[["steps.transform"]], "log")
by_horizon <- identical(A[["incidence.model"]], "by_horizon")
corstr <- A[["model.corstr"]]
edges <- as.numeric(A[["steps.bands"]])
knot_q <- as.numeric(A[["steps.spline_knots"]])
min_tkr <- as.numeric(A[["tkr.min_events"]])
coding <- A[["reverse.coding"]]
risk_kl <- A[["progression.risk_kl"]]
MIN_EVENTS <- 5
CURVE_AT <- seq(2000, 14000, by = 500)
CURVE_REF <- 5000
lin_term <- if (log_scale) "per_log" else "per_1000"
mv_term <- if (log_scale) "per_log" else "per_10min"
TABLES <- c("p1", "p2", "s1", "s2", "s3", "s3b", "s4", "r1", "r2", "r3")

read <- function(name) {
  d <- oaimodels::read_frame(file.path(frame_dir, sprintf("%s.parquet", name)))
  d <- as.data.frame(d)
  scale <- function(v, unit) if (log_scale) log(v + 1) else v / unit
  d$x_steps <- scale(d$steps_48, 1000)
  d$x_steps72 <- scale(d$steps_72, 1000)
  d$x_change <- d$x_steps72 - d$x_steps
  d$x_mv <- scale(d$mv_min_48, 10)
  d$k_steps <- d$steps_48 / 1000  # spline scale: thousands of steps/day
  d[order(d$ID), , drop = FALSE]
}

# ------------------------------------------------------------------ bands
band_labels <- function(edges) {
  middle <- if (length(edges) > 1) sprintf("%d_%d", edges[-length(edges)], edges[-1] - 1) else character()
  c(sprintf("lt%d", edges[1]), middle, sprintf("ge%d", edges[length(edges)]))
}
BANDS <- band_labels(edges)
band_of <- function(steps) {
  factor(BANDS[findInterval(steps, edges) + 1], levels = BANDS)
}

# ------------------------------------------------------------------ recording
rows <- list()
metrics <- list()
na_est <- c(estimate = NA_real_, lo = NA_real_, hi = NA_real_)
record <- function(table, exposure, outcome, term, model, n, events, est) {
  rows[[length(rows) + 1]] <<- data.frame(
    table = table, exposure = exposure, outcome = outcome, term = term, model = model, n = n,
    events = events, estimate = unname(est[["estimate"]]), lo = unname(est[["lo"]]),
    hi = unname(est[["hi"]])
  )
  key <- sprintf("%s.%s.%s.%s.%s", table, exposure, outcome, term, model)
  metrics[[key]] <<- unname(est[["estimate"]])
  metrics[[paste0(key, ".lo")]] <<- unname(est[["lo"]])
  metrics[[paste0(key, ".hi")]] <<- unname(est[["hi"]])
  metrics[[paste0(key, ".n")]] <<- n
  metrics[[paste0(key, ".events")]] <<- events
}
complete <- function(d, vars) d[stats::complete.cases(d[, unique(vars), drop = FALSE]), , drop = FALSE]
knees_n <- function(d) nrow(unique(d[, c("ID", "SIDE")]))
events_n <- function(d, outcome) sum(as.logical(d[[outcome]]))

# `factor(v)` when v has at least two values in d, else nothing (a constant adds no term)
fac <- function(d, v) if (length(unique(d[[v]])) >= 2) sprintf("factor(%s)", v) else character()
period_terms <- function(d) {
  if (!all(c("end_visit", "span") %in% names(d))) return(character())
  c(fac(d, "end_visit"), fac(d, "span"))
}
period_vars <- function(d) intersect(c("end_visit", "span"), names(d))
# Knees in a level of a factor term (kl48 as a factor, end_visit, span) with no events or no
# non-events are perfectly predicted by that level: the logistic fit's other coefficients are those
# of the fit without them, but geeglm diverges instead of converging there. They are dropped
# (with a message), so the model is fitted where it can be.
drop_separated <- function(d, outcome, factors, label) {
  repeat {
    y <- as.logical(d[[outcome]])
    bad <- rep(FALSE, nrow(d))
    for (v in factors) {
      if (length(unique(d[[v]])) < 2) next
      ev <- tapply(y, d[[v]], sum); n <- tapply(y, d[[v]], length)
      levels_bad <- names(ev)[ev == 0 | ev == n]
      if (length(levels_bad)) {
        message(sprintf("%s: dropping %d rows at %s = %s (no events or no non-events)", label,
                        sum(as.character(d[[v]]) %in% levels_bad), v, paste(levels_bad, collapse = ", ")))
        bad <- bad | as.character(d[[v]]) %in% levels_bad
      }
    }
    if (!any(bad)) return(d)
    d <- d[!bad, , drop = FALSE]
  }
}
factor_vars <- function(d, kl_factor) c(if (kl_factor) "kl48", period_vars(d))

# Covariates as model terms: kl48 enters as a factor (kl_factor) or as its grade (0/1 for ROA)
cov_terms <- function(d, covs, kl_factor) {
  out <- character()
  for (v in covs) {
    out <- c(out, if (v == "kl48" && kl_factor) fac(d, "kl48") else v)
  }
  out
}

# ------------------------------------------------------------------ fitting
gee_fit <- function(d, outcome, rhs, family) {
  d <- d[order(d$ID), , drop = FALSE]
  if (identical(family, "binomial")) d[[outcome]] <- as.integer(as.logical(d[[outcome]]))
  d$cluster_ <- match(d$ID, unique(d$ID))
  f <- stats::as.formula(paste(outcome, "~", paste(rhs, collapse = " + ")))
  fam <- if (identical(family, "binomial")) stats::binomial else stats::gaussian
  cs <- if (identical(family, "gaussian_person")) "independence" else corstr
  tryCatch(
    geepack::geeglm(f, id = cluster_, data = d, family = fam, corstr = cs),
    error = function(e) {
      message("fit failed (", outcome, " ~ ", paste(rhs, collapse = " + "), "): ", conditionMessage(e))
      NULL
    }
  )
}
# Estimate and 95% CI for `term`; `ratio` exponentiates
coef_est <- function(fit, term, ratio) {
  if (is.null(fit)) return(na_est)
  co <- summary(fit)$coefficients
  if (!term %in% rownames(co)) return(na_est)
  b <- co[term, "Estimate"]; se <- co[term, "Std.err"]
  if (!is.finite(b) || !is.finite(se)) return(na_est)
  est <- c(estimate = b, lo = b - 1.96 * se, hi = b + 1.96 * se)
  if (ratio) exp(est) else est
}
coef_p <- function(fit, term) {
  if (is.null(fit)) return(NA_real_)
  co <- summary(fit)$coefficients
  if (!term %in% rownames(co)) return(NA_real_)
  p <- co[term, "Pr(>|W|)"]
  if (is.finite(p)) p else NA_real_
}

# ------------------------------------------------------------------ forward (knee level)
# Linear, band and spline models of `outcome` (0/1 `event` column) on steps at 48 months
forward_shapes <- function(table, d, outcome, model, kl_factor, curve = NULL) {
  covs <- covariates_for(A, model, "48", "knee")
  dd <- complete(d, c("event", "steps_48", covs, period_vars(d)))
  dd <- drop_separated(dd, "event", factor_vars(dd, kl_factor && "kl48" %in% covs),
                     paste(table, outcome, model))
  rhs_rest <- c(period_terms(dd), cov_terms(dd, covs, kl_factor))
  n <- knees_n(dd); ev <- events_n(dd, "event")

  fit <- gee_fit(dd, "event", c("x_steps", rhs_rest), "binomial")
  record(table, "steps_48", outcome, lin_term, model, n, ev, coef_est(fit, "x_steps", TRUE))

  # Bands: lowest band is the reference; NA for a band (all bands if the reference) with too few
  dd$band <- band_of(dd$steps_48)
  band_events <- tapply(as.logical(dd$event), dd$band, sum)
  band_events[is.na(band_events)] <- 0
  fit_b <- if (band_events[[BANDS[1]]] >= MIN_EVENTS) gee_fit(dd, "event", c("band", rhs_rest), "binomial")
  for (b in BANDS) {
    db <- dd[dd$band == b, , drop = FALSE]
    est <- if (b == BANDS[1]) {
      if (is.null(fit_b)) na_est else c(estimate = 1, lo = NA_real_, hi = NA_real_)
    } else if (band_events[[b]] < MIN_EVENTS) na_est else coef_est(fit_b, paste0("band", b), TRUE)
    record(table, "steps_48", outcome, paste0("band_", b), model, knees_n(db), events_n(db, "event"), est)
  }

  # Restricted cubic spline, knots at quantiles of steps_48 in this model's sample
  knots <- unname(stats::quantile(dd$k_steps, knot_q))
  B <- rcs_basis(dd$k_steps, knots)
  dd$rcs1 <- B[, 1]; dd$rcs2 <- B[, 2]
  fit_s <- gee_fit(dd, "event", c("rcs1", "rcs2", rhs_rest), "binomial")
  record(table, "steps_48", outcome, "nonlinear_p", model, n, ev,
         c(estimate = coef_p(fit_s, "rcs2"), lo = NA_real_, hi = NA_real_))
  if (!is.null(curve)) {
    cv <- if (is.null(fit_s)) {
      data.frame(or = NA_real_, lo = NA_real_, hi = NA_real_)[rep(1, length(CURVE_AT)), ]
    } else {
      terms <- c("rcs1", "rcs2")
      rcs_curve(stats::coef(fit_s)[terms], stats::vcov(fit_s)[terms, terms], knots,
                CURVE_AT / 1000, CURVE_REF / 1000)
    }
    utils::write.csv(data.frame(steps = CURVE_AT, or = cv$or, lo = cv$lo, hi = cv$hi),
                     file.path(out_dir, sprintf("curve_%s.csv", curve)), row.names = FALSE)
  }
}

# One knee-level GEE (logistic, or gaussian for change_mm): coefficients `x` recorded as `labels`
knee_logit <- function(table, exposure, d, outcome_col, outcome, model, waves, x, labels, kl_factor,
                       extra = character(), family = "binomial") {
  covs <- covariates_for(A, model, waves, "knee")
  raw <- c(outcome_col, "steps_48", if ("x_change" %in% x) c("steps_change", "steps_72"),
           if ("x_mv" %in% x) "mv_min_48", covs, extra, period_vars(d))
  dd <- complete(d, raw)
  if (family == "binomial") {
    dd <- drop_separated(dd, outcome_col, factor_vars(dd, kl_factor && "kl48" %in% covs),
                         paste(table, outcome, model, paste(labels, collapse = "+")))
  }
  rhs <- c(x, period_terms(dd), cov_terms(dd, covs, kl_factor), extra)
  fit <- gee_fit(dd, outcome_col, rhs, family)
  ev <- if (family == "binomial") events_n(dd, outcome_col) else NA_integer_
  ratio <- family == "binomial"
  for (i in seq_along(x)) {
    record(table, exposure, outcome, labels[[i]], model, knees_n(dd), ev, coef_est(fit, x[[i]], ratio))
  }
}

# Cox model of knee replacement, clustered by person; band counts below the event minimum
knee_cox <- function(table, d, outcome, model, kl_factor) {
  covs <- covariates_for(A, model, "48", "knee")
  dd <- complete(d, c("time_yr", "event", "steps_48", covs))
  n <- knees_n(dd); ev <- events_n(dd, "event")
  record(table, "steps_48", outcome, "events", model, n, ev, na_est)
  if (ev >= min_tkr) {
    rhs <- c("x_steps", cov_terms(dd, covs, kl_factor))
    dd$event_ <- as.integer(as.logical(dd$event))
    f <- stats::as.formula(paste("survival::Surv(time_yr, event_) ~", paste(rhs, collapse = " + ")))
    fit <- tryCatch(survival::coxph(f, data = dd, cluster = ID), error = function(e) {
      message("cox failed (", outcome, "): ", conditionMessage(e)); NULL
    })
    est <- if (is.null(fit) || !"x_steps" %in% names(stats::coef(fit))) na_est else {
      b <- stats::coef(fit)[["x_steps"]]; se <- sqrt(stats::vcov(fit)["x_steps", "x_steps"])
      if (is.finite(se)) exp(c(estimate = b, lo = b - 1.96 * se, hi = b + 1.96 * se)) else na_est
    }
    record(table, "steps_48", outcome, lin_term, model, n, ev, est)
  } else {
    dd$band <- band_of(dd$steps_48)
    for (b in BANDS) {
      db <- dd[dd$band == b, , drop = FALSE]
      record(table, "steps_48", outcome, paste0("band_", b), model, knees_n(db), events_n(db, "event"), na_est)
    }
  }
}

# ------------------------------------------------------------------ frames
incidence <- if (by_horizon) c(roa = "horizon_roa", soa = "horizon_soa") else c(roa = "periods_roa", soa = "periods_soa")
f_roa <- read(incidence[["roa"]])
f_soa <- read(incidence[["soa"]])
f_roa72 <- read("periods_roa_72")
f_soa72 <- read("periods_soa_72")
tkr <- read("tkr")
progression <- read("progression")
jsw <- read("jsw")
persons <- read("persons")
risk <- if (identical(risk_kl, "1-3")) 1:3 else 2:3

for (model in models) {
  # P1, P2 (and P2 within ROA at 48 months)
  forward_shapes("p1", f_roa, "roa", model, kl_factor = FALSE, curve = if (model == "m1") "p1")
  forward_shapes("p2", f_soa, "soa", model, kl_factor = TRUE, curve = if (model == "m1") "p2")
  forward_shapes("p2", f_soa[f_soa$roa48 %in% TRUE, ], "soa_roa48", model, kl_factor = TRUE)
  forward_shapes("p2", f_soa[f_soa$roa48 %in% FALSE, ], "soa_noroa48", model, kl_factor = TRUE)

  # S4: MV minutes/day
  knee_logit("s4", "mv_min_48", f_roa, "event", "roa", model, "48", "x_mv", mv_term, FALSE)
  knee_logit("s4", "mv_min_48", f_soa, "event", "soa", model, "48", "x_mv", mv_term, TRUE)

  # S1: change in steps, incidence after 72 months
  knee_logit("s1", "steps_48", f_roa72, "event", "roa", model, c("48", "72"),
             c("x_steps", "x_change"), c("baseline_adj", "change"), FALSE)
  knee_logit("s1", "steps_48", f_soa72, "event", "soa", model, c("48", "72"),
             c("x_steps", "x_change"), c("baseline_adj", "change"), TRUE)

  # S2: replacement in the incident-ROA knees
  knee_cox("s2", tkr[tkr$at_risk_roa %in% TRUE, ], "tkr_incidence", model, kl_factor = FALSE)

  # S3: replacement in knees with KL >= 2; KL and JSN worsening in the read knees
  knee_cox("s3", tkr[tkr$progression_tkr %in% TRUE, ], "tkr_progression", model, kl_factor = TRUE)
  read_kl <- progression[progression$kl_read %in% TRUE, ]
  knee_logit("s3", "steps_48", read_kl, "kl_any", "kl_any_read", model, "48", "x_steps", lin_term, TRUE)
  knee_logit("s3", "steps_48", read_kl[read_kl$base_kl %in% 2:3, ], "kl_to_4", "kl_to_4_read", model,
             "48", "x_steps", lin_term, TRUE)
  knee_logit("s3", "steps_48", progression, "jsn_event", "jsn_read", model, "48", "x_steps", lin_term, TRUE)

  # S3b: measured JSW in the progression risk grades
  j <- jsw[jsw$kl48 %in% risk, ]
  extra <- if (model == "m2") "base_mm" else character()
  for (spec in list(list(col = "progressor", family = "binomial"), list(col = "change_mm", family = "gaussian"))) {
    knee_logit("s3b", "steps_48", j, spec$col, spec$col, model, "48", "x_steps", lin_term, TRUE,
               extra, spec$family)
    knee_logit("s3b", "steps_48", j, spec$col, spec$col, model, c("48", "72"),
               c("x_steps", "x_change"), c("baseline_adj", "change"), TRUE, extra, spec$family)
  }

  # R1, R2: person level, steps at 72 months
  r_exposure <- list(
    r1 = if (coding == "count") "new_oa_count_36_48" else "new_oa_36_48",
    r2 = if (isTRUE(A[["reverse.r2_kl_read"]])) {
      if (coding == "count") NA_character_ else "new_oa_read_48_72"
    } else if (coding == "count") "new_oa_count_48_72" else "new_oa_48_72"
  )
  covs <- covariates_for(A, model, c("48", "72"), "person")
  for (table in names(r_exposure)) {
    expo <- r_exposure[[table]]
    if (is.na(expo)) {
      message(table, ": no count column for the read-knee exposure; NA")
      record(table, "new_oa_read_48_72", "steps_72", coding, model, NA_integer_, NA_integer_, na_est)
      next
    }
    dd <- complete(persons, c("steps_72", expo, "steps_48", covs))
    dd$expo_ <- as.numeric(dd[[expo]])
    fit <- gee_fit(dd, "x_steps72", c("expo_", "x_steps", covs), "gaussian_person")
    record(table, expo, "steps_72", coding, model, nrow(dd), sum(dd$expo_ > 0),
           coef_est(fit, "expo_", log_scale))
  }
}

# R3: steps/day at 48 months by the higher KL grade and by SOA at 48 months
for (group in c("kl_max", "soa48")) {
  dd <- complete(persons, c("steps_48", group))
  for (level in sort(unique(dd[[group]]))) {
    v <- dd$steps_48[dd[[group]] == level]
    term <- sprintf("%s_%s", group, level)
    record("r3", "steps_48", group, term, "mean", length(v), NA_integer_,
           c(estimate = mean(v), lo = NA_real_, hi = NA_real_))
    record("r3", "steps_48", group, term, "sd", length(v), NA_integer_,
           c(estimate = stats::sd(v), lo = NA_real_, hi = NA_real_))
  }
}

all_rows <- do.call(rbind, rows)
for (table in TABLES) {
  utils::write.csv(all_rows[all_rows$table == table, , drop = FALSE],
                   file.path(out_dir, sprintf("table_%s.csv", table)), row.names = FALSE)
}
utils::write.csv(data.frame(metric = names(metrics), value = unlist(metrics)),
                 file.path(out_dir, "metrics_models.csv"), row.names = FALSE)
cat("Tables", paste(TABLES, collapse = ", "), "written to", out_dir, "\n")
