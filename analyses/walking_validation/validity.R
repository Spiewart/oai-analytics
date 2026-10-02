# Step `validity`: does the walking item rank and classify people like the device? (spec 6)
A <- oaimodels::assumptions()
measures <- c("purposeful_min", "counts_per_day", "light_min")
outcomes <- c("new_pain", "kl_worse", "jsn_worse", "improved_pain")
# Every column the step reads, so a frame without one stops here and names it
persons <- oaimodels::read_frame(required = c(
  "ID", "walker", "amount_level", "sessions", "device_walker", "in_lo", "n_waves", "age", "sex",
  "bmi", "kl_max0", "pain0_any", measures, paste0(measures, "_06"), paste0(measures, "_08"),
  "device_walker_06", "device_walker_08", paste0("pase_walking_", c("06", "08", "10")),
  paste0(outcomes, "_any")
))
out_dir <- Sys.getenv("OAI_RESULTS_DIR")
reps <- A[["validity.bootstrap_reps"]]
perms <- A[["validity.jt_permutations"]]
seed <- A[["bias.seed"]]
se_method <- A[["validity.median_regression_se"]]
pase_threshold <- A[["pase.walker_threshold"]]
adjust <- "age + sex + bmi"
levels_amount <- c("none", "lower", "upper")
samples <- list(validation = rep(TRUE, nrow(persons)), lo_subset = persons$in_lo)
q <- function(x, p) unname(stats::quantile(x, p, na.rm = TRUE))
bind <- function(rows) do.call(rbind, rows)
# Between-wave Spearman correlation of a device measure among everyone valid at both waves: the
# single-wave reliability used to deattenuate the convergent correlations (both benchmarks).
between_wave <- function(m) {
  a <- persons[[paste0(m, "_06")]]
  b <- persons[[paste0(m, "_08")]]
  both <- !is.na(a) & !is.na(b)
  list(r = stats::cor(a[both], b[both], method = "spearman"), n = sum(both))
}

known <- list(); dose <- list(); convergent <- list(); classes <- list(); strata <- list()
for (sample in names(samples)) {
  d <- persons[samples[[sample]], ]
  for (m in measures) {
    w <- d[[m]][d$walker]
    nw <- d[[m]][!d$walker]
    hl <- oaimodels::hodges_lehmann(w, nw)
    adj <- oaimodels::median_regression(stats::as.formula(paste(m, "~ walker +", adjust)), d, "walkerTRUE",
                                       se = se_method, reps = reps, seed = seed)
    known[[length(known) + 1]] <- data.frame(
      sample = sample, measure = m, n_walkers = sum(!is.na(w)), n_nonwalkers = sum(!is.na(nw)),
      median_walkers = q(w, 0.5), q25_walkers = q(w, 0.25), q75_walkers = q(w, 0.75),
      median_nonwalkers = q(nw, 0.5), q25_nonwalkers = q(nw, 0.25), q75_nonwalkers = q(nw, 0.75),
      hl = hl[["estimate"]], hl_lo = hl[["lo"]], hl_hi = hl[["hi"]],
      rank_biserial = oaimodels::rank_biserial(w, nw),
      adj_diff = adj[["estimate"]], adj_lo = adj[["lo"]], adj_hi = adj[["hi"]]
    )
    level <- factor(d$amount_level, levels = levels_amount)
    # n behind each median: participants at that level with the measure. Walkers with no amount
    # level (they answered only some of the amount items, so have no lifetime sessions; under
    # walker coding, also a "yes" with no amount at all) are in no level and so are left out of the
    # lower/upper groups.
    n_at <- function(lv) sum(level %in% lv & !is.na(d[[m]]))
    jt <- oaimodels::jonckheere(d[[m]], level, permutations = perms, seed = seed)
    dd <- d[!is.na(level), ]
    dd$amount_level <- factor(dd$amount_level, levels = levels_amount)
    form <- stats::as.formula(paste(m, "~ amount_level +", adjust))
    lower <- oaimodels::median_regression(form, dd, "amount_levellower", se = se_method, reps = reps, seed = seed)
    upper <- oaimodels::median_regression(form, dd, "amount_levelupper", se = se_method, reps = reps, seed = seed)
    dose[[length(dose) + 1]] <- data.frame(
      sample = sample, measure = m,
      median_none = q(d[[m]][level %in% "none"], 0.5), median_lower = q(d[[m]][level %in% "lower"], 0.5),
      median_upper = q(d[[m]][level %in% "upper"], 0.5),
      n_none = n_at("none"), n_lower = n_at("lower"), n_upper = n_at("upper"),
      n_walkers_no_level = sum(d$walker & is.na(level), na.rm = TRUE),
      jt = jt[["statistic"]], jt_p = jt[["p"]],
      adj_lower = lower[["estimate"]], adj_lower_lo = lower[["lo"]], adj_lower_hi = lower[["hi"]],
      adj_upper = upper[["estimate"]], adj_upper_lo = upper[["lo"]], adj_upper_hi = upper[["hi"]]
    )
    walkers <- d[d$walker & !is.na(d$sessions), ]
    rho <- oaimodels::spearman_ci(walkers$sessions, walkers[[m]])
    waves <- between_wave(m)
    reliability <- oaimodels::wave_reliability(waves$r, mean(walkers$n_waves == 2))
    convergent[[length(convergent) + 1]] <- data.frame(
      sample = sample, measure = m, n = rho[["n"]], rho = rho[["rho"]], lo = rho[["lo"]], hi = rho[["hi"]],
      between_wave_rho = waves$r, n_both_waves = waves$n, reliability = reliability,
      rho_deattenuated = oaimodels::deattenuate(rho[["rho"]], reliability_y = reliability)
    )
  }
  cl <- oaimodels::classification(d$walker, d$device_walker)
  score <- ifelse(d$walker, d$sessions, 0)
  auc <- oaimodels::auc_ci(score, d$device_walker, reps = reps, seed = seed)
  cl <- rbind(cl, data.frame(measure = "auc", estimate = auc[["estimate"]], lo = auc[["lo"]],
                             hi = auc[["hi"]], k = NA, n = sum(!is.na(score) & !is.na(d$device_walker))))
  cl$sample <- rep(sample, nrow(cl))
  classes[[length(classes) + 1]] <- cl
  by <- list(
    kl = as.character(cut(d$kl_max0, c(-Inf, 1, 2, Inf), labels = c("KL 0-1", "KL 2", "KL 3-4"))),
    pain = ifelse(d$pain0_any, "frequent pain", "no frequent pain")
  )
  if (sample == "lo_subset") {
    for (o in outcomes) by[[o]] <- ifelse(d[[paste0(o, "_any")]], "event", "no event")
  }
  for (v in names(by)) {
    s <- oaimodels::classification_by_stratum(d$walker, d$device_walker, by[[v]])
    s$sample <- rep(sample, nrow(s))  # rep(): a zero-row frame (all-missing input) takes no scalar
    s$variable <- rep(v, nrow(s))
    strata[[length(strata) + 1]] <- s
  }
}

# PASE benchmark (spec 6.6): items 1, 3 and 4 for the PASE walking subscore at each visit. A PASE
# walker has a subscore above the threshold. Long format; lo/hi are NA where a statistic has no CI.
# With pase.device_pairing = "adjacent_wave", PASE at 48 and 72 months is compared with that wave's
# own device measures and device walker, in persons valid at that wave, and a single wave's
# reliability is the between-wave rho itself; PASE at 96 months has no device wave of its own, so it
# (and every visit under "two_wave_mean") uses the combined measures, as the walking item does.
pairing <- A[["pase.device_pairing"]]
if (!pairing %in% c("adjacent_wave", "two_wave_mean")) {
  stop("unknown pase.device_pairing: ", pairing, call. = FALSE)
}
pase <- list()
pase_row <- function(visit, device_wave, measure, statistic, estimate, lo, hi, n) {
  data.frame(visit = visit, device_wave = device_wave, measure = measure, statistic = statistic,
             estimate = estimate, lo = lo, hi = hi, n = n)
}
for (visit in c("06", "08", "10")) {
  paired <- pairing == "adjacent_wave" && visit %in% c("06", "08")
  device_wave <- if (paired) visit else "combined"
  suffix <- if (paired) paste0("_", visit) else ""
  reference <- paste0("device_walker", suffix)
  score <- paste0("pase_walking_", visit)
  at_visit <- persons[!is.na(persons[[score]]) & !is.na(persons[[reference]]), ]
  p <- at_visit[[score]]
  at_visit$pase_walker <- p > pase_threshold
  pase_walkers <- at_visit[at_visit$pase_walker, ]
  visit_row <- function(...) pase_row(visit, device_wave, ...)
  for (m in measures) {
    col <- paste0(m, suffix)
    # Item 1: known groups
    w <- at_visit[[col]][at_visit$pase_walker]
    nw <- at_visit[[col]][!at_visit$pase_walker]
    n_groups <- sum(!is.na(w)) + sum(!is.na(nw))
    hl <- oaimodels::hodges_lehmann(w, nw)
    form <- stats::as.formula(paste(col, "~ pase_walker +", adjust))
    adj <- oaimodels::median_regression(form, at_visit, "pase_walkerTRUE", se = se_method, reps = reps,
                                        seed = seed)
    pase[[length(pase) + 1]] <- visit_row(m, "hl", hl[["estimate"]], hl[["lo"]], hl[["hi"]], n_groups)
    pase[[length(pase) + 1]] <- visit_row(m, "rank_biserial", oaimodels::rank_biserial(w, nw), NA, NA,
                                          n_groups)
    pase[[length(pase) + 1]] <- visit_row(m, "adj_diff", adj[["estimate"]], adj[["lo"]], adj[["hi"]],
                                          adj[["n"]])
    # Item 3: convergent ranking among PASE walkers, deattenuated like the walking item
    rho <- oaimodels::spearman_ci(pase_walkers[[score]], pase_walkers[[col]])
    share_two_waves <- if (paired) 0 else mean(pase_walkers$n_waves == 2)
    reliability <- oaimodels::wave_reliability(between_wave(m)$r, share_two_waves)
    pase[[length(pase) + 1]] <- visit_row(m, "rho", rho[["rho"]], rho[["lo"]], rho[["hi"]], rho[["n"]])
    pase[[length(pase) + 1]] <- visit_row(m, "rho_deattenuated",
                                          oaimodels::deattenuate(rho[["rho"]], reliability_y = reliability),
                                          NA, NA, rho[["n"]])
  }
  # Item 4: classification against the device walker
  cl <- oaimodels::classification(p > pase_threshold, at_visit[[reference]])
  auc <- oaimodels::auc_ci(p, at_visit[[reference]], reps = reps, seed = seed)
  pase[[length(pase) + 1]] <- visit_row("device_walker", cl$measure, cl$estimate, cl$lo, cl$hi, cl$n)
  pase[[length(pase) + 1]] <- visit_row("device_walker", "auc", auc[["estimate"]], auc[["lo"]],
                                        auc[["hi"]], nrow(at_visit))
}

classification_all <- bind(classes)
validation <- classification_all[classification_all$sample == "validation", ]
lo_subset <- classification_all[classification_all$sample == "lo_subset", ]
metrics <- data.frame(
  metric = c("validity.validation.se", "validity.validation.sp", "validity.validation.auc",
             "validity.lo_subset.se", "validity.lo_subset.sp"),
  value = c(validation$estimate[validation$measure == "se"], validation$estimate[validation$measure == "sp"],
            validation$estimate[validation$measure == "auc"], lo_subset$estimate[lo_subset$measure == "se"],
            lo_subset$estimate[lo_subset$measure == "sp"])
)
write <- function(df, name) utils::write.csv(df, file.path(out_dir, name), row.names = FALSE)
write(bind(known), "validity_known_groups.csv")
write(bind(dose), "validity_dose.csv")
write(bind(convergent), "validity_convergent.csv")
write(classification_all, "validity_classification.csv")
write(bind(strata), "validity_strata.csv")
write(bind(pase), "validity_pase.csv")
write(metrics, "metrics_validity.csv")
print(metrics)
