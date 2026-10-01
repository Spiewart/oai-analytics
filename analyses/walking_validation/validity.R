# Step `validity`: does the walking item rank and classify people like the device? (spec 6)
A <- oaimodels::assumptions()
persons <- oaimodels::read_frame(required = c(
  "ID", "walker", "amount_level", "sessions", "device_walker", "in_lo", "n_waves", "age", "sex",
  "bmi", "kl_max0", "pain0_any", "purposeful_min", "counts_per_day", "light_min"
))
out_dir <- Sys.getenv("OAI_RESULTS_DIR")
measures <- c("purposeful_min", "counts_per_day", "light_min")
outcomes <- c("new_pain", "kl_worse", "jsn_worse", "improved_pain")
reps <- A[["validity.bootstrap_reps"]]
perms <- A[["validity.jt_permutations"]]
seed <- A[["bias.seed"]]
adjust <- "age + sex + bmi"
levels_amount <- c("none", "lower", "upper")
samples <- list(validation = rep(TRUE, nrow(persons)), lo_subset = persons$in_lo)
q <- function(x, p) unname(stats::quantile(x, p, na.rm = TRUE))
bind <- function(rows) do.call(rbind, rows)

known <- list(); dose <- list(); convergent <- list(); classes <- list(); strata <- list()
for (sample in names(samples)) {
  d <- persons[samples[[sample]], ]
  for (m in measures) {
    w <- d[[m]][d$walker]
    nw <- d[[m]][!d$walker]
    hl <- oaimodels::hodges_lehmann(w, nw)
    adj <- oaimodels::median_regression(stats::as.formula(paste(m, "~ walker +", adjust)), d, "walkerTRUE")
    known[[length(known) + 1]] <- data.frame(
      sample = sample, measure = m, n_walkers = sum(!is.na(w)), n_nonwalkers = sum(!is.na(nw)),
      median_walkers = q(w, 0.5), q25_walkers = q(w, 0.25), q75_walkers = q(w, 0.75),
      median_nonwalkers = q(nw, 0.5), q25_nonwalkers = q(nw, 0.25), q75_nonwalkers = q(nw, 0.75),
      hl = hl[["estimate"]], hl_lo = hl[["lo"]], hl_hi = hl[["hi"]],
      rank_biserial = oaimodels::rank_biserial(w, nw),
      adj_diff = adj[["estimate"]], adj_lo = adj[["lo"]], adj_hi = adj[["hi"]]
    )
    level <- factor(d$amount_level, levels = levels_amount)
    jt <- oaimodels::jonckheere(d[[m]], level, permutations = perms, seed = seed)
    dd <- d[!is.na(level), ]
    dd$amount_level <- factor(dd$amount_level, levels = levels_amount)
    form <- stats::as.formula(paste(m, "~ amount_level +", adjust))
    lower <- oaimodels::median_regression(form, dd, "amount_levellower")
    upper <- oaimodels::median_regression(form, dd, "amount_levelupper")
    dose[[length(dose) + 1]] <- data.frame(
      sample = sample, measure = m,
      median_none = q(d[[m]][level %in% "none"], 0.5), median_lower = q(d[[m]][level %in% "lower"], 0.5),
      median_upper = q(d[[m]][level %in% "upper"], 0.5), jt = jt[["statistic"]], jt_p = jt[["p"]],
      adj_lower = lower[["estimate"]], adj_lower_lo = lower[["lo"]], adj_lower_hi = lower[["hi"]],
      adj_upper = upper[["estimate"]], adj_upper_lo = upper[["lo"]], adj_upper_hi = upper[["hi"]]
    )
    walkers <- d[d$walker & !is.na(d$sessions), ]
    rho <- oaimodels::spearman_ci(walkers$sessions, walkers[[m]])
    a <- persons[[paste0(m, "_06")]]
    b <- persons[[paste0(m, "_08")]]
    both <- !is.na(a) & !is.na(b)
    r_waves <- stats::cor(a[both], b[both], method = "spearman")
    reliability <- oaimodels::wave_reliability(r_waves, mean(walkers$n_waves == 2))
    convergent[[length(convergent) + 1]] <- data.frame(
      sample = sample, measure = m, n = rho[["n"]], rho = rho[["rho"]], lo = rho[["lo"]], hi = rho[["hi"]],
      between_wave_rho = r_waves, n_both_waves = sum(both), reliability = reliability,
      rho_deattenuated = oaimodels::deattenuate(rho[["rho"]], reliability_y = reliability)
    )
  }
  cl <- oaimodels::classification(d$walker, d$device_walker)
  auc <- oaimodels::auc_ci(ifelse(d$walker, d$sessions, 0), d$device_walker, reps = reps, seed = seed)
  cl <- rbind(cl, data.frame(measure = "auc", estimate = auc[["estimate"]], lo = auc[["lo"]],
                             hi = auc[["hi"]], k = NA, n = sum(!is.na(d$device_walker))))
  cl$sample <- sample
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
    s$sample <- sample
    s$variable <- v
    strata[[length(strata) + 1]] <- s
  }
}

pase <- list()
for (visit in c("06", "08", "10")) {
  p <- persons[[paste0("pase_walking_", visit)]]
  for (m in measures) {
    rho <- oaimodels::spearman_ci(p, persons[[m]])
    pase[[length(pase) + 1]] <- data.frame(visit = visit, measure = m, statistic = "rho",
                                           estimate = rho[["rho"]], lo = rho[["lo"]], hi = rho[["hi"]], n = rho[["n"]])
  }
  cl <- oaimodels::classification(p > 0, persons$device_walker)
  cl <- cl[cl$measure %in% c("se", "sp"), ]
  pase[[length(pase) + 1]] <- data.frame(visit = visit, measure = "device_walker", statistic = cl$measure,
                                         estimate = cl$estimate, lo = cl$lo, hi = cl$hi, n = cl$n)
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
