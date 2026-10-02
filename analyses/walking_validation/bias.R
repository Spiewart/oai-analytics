# Step `bias`: how far could misclassification of the walking item move Lo 2022's odds ratios?
# (spec 7). Refits the replication's own models on reclassified exposure.
# OAI_R_CORES: worker processes for the draws. A positive integer; unset (or empty) means the
# detected cores minus one, at least 1. Checked first, so a bad value stops the step at once.
cores_setting <- Sys.getenv("OAI_R_CORES", "")
cores <- if (nzchar(cores_setting)) {
  n <- suppressWarnings(as.integer(cores_setting))
  if (!grepl("^[0-9]+$", cores_setting) || is.na(n) || n < 1L) {
    stop("OAI_R_CORES must be a positive integer, got '", cores_setting, "'", call. = FALSE)
  }
  n
} else {
  max(1L, parallel::detectCores() - 1L, na.rm = TRUE)
}
A <- oaimodels::assumptions()
frames <- Sys.getenv("OAI_FRAME_DIR")
out_dir <- Sys.getenv("OAI_RESULTS_DIR")
outcomes <- c("new_pain", "kl_worse", "jsn_worse", "improved_pain")
persons <- oaimodels::read_frame(required = c("ID", "walker", "device_walker", "in_lo", paste0(outcomes, "_any")))
model <- jsonlite::fromJSON(file.path(frames, "lo_model.json"))
models <- c(or_unadj = model$or_unadj, or_adj = model$or_adj)
base_covariates <- strsplit(model$covariates, ",")[[1]]
# every column knee_data() reads: the model's covariates and the four outcomes
knees_all <- oaimodels::read_frame(file.path(frames, "lo_knees.parquet"),
                                   required = c("ID", "walker", base_covariates, outcomes))
published <- utils::read.csv(file.path(out_dir, "lo2022_t2.csv"), na.strings = c("", "NA"))
replicated <- utils::read.csv(file.path(out_dir, "lo2022_table2.csv"))
iterations <- A[["bias.iterations"]]
seed <- A[["bias.seed"]]
validated <- persons[persons$in_lo & !is.na(persons$device_walker), ]

prior_row <- function(d, stratum) {
  se_k <- sum(d$walker & d$device_walker)
  se_n <- sum(d$device_walker)
  sp_k <- sum(!d$walker & !d$device_walker)
  sp_n <- sum(!d$device_walker)
  se <- oaimodels::beta_shapes(se_k, se_n)
  sp <- oaimodels::beta_shapes(sp_k, sp_n)
  data.frame(stratum = stratum, se1 = se[["shape1"]], se2 = se[["shape2"]], sp1 = sp[["shape1"]],
             sp2 = sp[["shape2"]], se_k = se_k, se_n = se_n, sp_k = sp_k, sp_n = sp_n)
}

knee_data <- function(o) {  # exactly as lo2022_walking/models.R prepares it
  d <- knees_all[!is.na(knees_all[[o]]), unique(c("ID", "walker", base_covariates, o))]
  names(d)[names(d) == o] <- "y"
  d$y <- as.integer(d$y)
  d <- d[stats::complete.cases(d), ]
  d[order(d$ID), ]
}

# A published odds ratio or count that is missing, absent or unreadable stops the step by name
published_count <- function(o, group, what) {
  metric <- sprintf("t2.%s.%s.%s", o, group, what)
  x <- suppressWarnings(as.numeric(published$published[published$metric == metric]))
  if (length(x) != 1 || is.na(x)) {
    stop("bias step: the published count ", metric, " in lo2022_t2.csv is missing or not a number",
         call. = FALSE)
  }
  x
}
published_or <- function(o, m) {
  metric <- paste0("t2.", o, ".", m)
  pub <- oaireport::parse_or(published$published[published$metric == metric])
  if (nrow(pub) != 1 || is.na(pub$or) || is.na(pub$sig)) {
    stop("bias step: the published odds ratio ", metric, " in lo2022_t2.csv is missing or not ",
         "readable as 'OR (lo-hi)' (found ", nrow(pub), " row(s))", call. = FALSE)
  }
  pub
}

# Everything the loop reads from the frames and the published table, built and checked for every
# outcome first, so a missing or inconsistent value stops the step before any PBA runs.
inputs <- lapply(stats::setNames(outcomes, outcomes), function(o) {
  k <- knee_data(o)
  first <- !duplicated(k$ID)
  person <- data.frame(ID = k$ID[first], observed = k$walker[first])
  person$stratum <- ifelse(person$ID %in% k$ID[k$y == 1], "case", "noncase")
  v <- validated[!is.na(validated[[paste0(o, "_any")]]), ]
  # The priors come from the validated Lo participants with this outcome observed (case if any knee
  # had the event), as bias.prior_population says. That admits a participant the complete-case model
  # frame drops for a missing covariate, who then feeds the priors only: such people are counted
  # (a metric) and not an error. Everyone who is in the model frame must be in the same group
  # there as in the priors, because the pba draws reclassify the model's persons by group name.
  prior_group <- ifelse(v[[paste0(o, "_any")]], "case", "noncase")
  model_group <- person$stratum[match(v$ID, person$ID)]
  inside <- !is.na(model_group)
  if (any(prior_group[inside] != model_group[inside])) {
    stop("bias step: ", sum(prior_group[inside] != model_group[inside]), " validated participant(s) are in ",
         "a different ", o, " case/noncase group in the priors (", o, "_any, from all knees) than in ",
         "the complete-case model frame", call. = FALSE)
  }
  a <- published_count(o, "walkers", "events")
  b <- published_count(o, "nonwalkers", "events")
  list(
    k = k, person = person, v = v, outside = sum(!inside),
    # the summary-level correction's 2x2 counts
    counts = list(a = a, b = b, c0 = published_count(o, "walkers", "n") - a,
                  d0 = published_count(o, "nonwalkers", "n") - b),
    or = stats::setNames(lapply(names(models), function(m) published_or(o, m)), names(models))
  )
})

pba_rows <- list(); prior_rows <- list(); tipping_rows <- list(); summary_rows <- list()
for (o in outcomes) {
  k <- inputs[[o]]$k
  person <- inputs[[o]]$person
  v <- inputs[[o]]$v
  a <- inputs[[o]]$counts$a
  b <- inputs[[o]]$counts$b
  c0 <- inputs[[o]]$counts$c0
  d0 <- inputs[[o]]$counts$d0
  nondiff <- prior_row(v, "all")
  diff <- rbind(prior_row(v[v[[paste0(o, "_any")]], ], "case"),
                prior_row(v[!v[[paste0(o, "_any")]], ], "noncase"))
  prior_rows[[length(prior_rows) + 1]] <- rbind(
    cbind(outcome = o, scenario = "non-differential", nondiff),
    cbind(outcome = o, scenario = "differential", diff)
  )
  for (m in names(models)) {
    fit <- function(kn) oaimodels::fit_knee_gee(kn, models[[m]], corstr = model$corstr)[c("log_or", "se")]
    observed <- oaimodels::fit_knee_gee(k, models[[m]], corstr = model$corstr)
    rep_or <- replicated$or[replicated$outcome == o & replicated$model == m]
    if (length(rep_or) != 1 || abs(observed[["or"]] - rep_or) > 1e-8) {
      stop("bias step does not reproduce the replication's ", o, " ", m, " odds ratio", call. = FALSE)
    }
    pub <- inputs[[o]]$or[[m]]
    for (scenario in c("non-differential", "differential")) {
      priors <- if (scenario == "differential") diff else nondiff
      draws <- oaimodels::pba(person, k, fit, priors, differential = scenario == "differential",
                              iterations = iterations, seed = seed, cores = cores)
      s <- oaimodels::summarise_pba(draws, direction = sign(log(pub$or)), significant = pub$sig)
      pba_rows[[length(pba_rows) + 1]] <- data.frame(
        outcome = o, model = m, scenario = scenario, observed_or = observed[["or"]],
        published_or = pub$or, s, flagged = s$discarded > A[["bias.max_discard_share"]]
      )
    }
  }
  fit_adj <- function(kn) oaimodels::fit_knee_gee(kn, models[["or_adj"]], corstr = model$corstr)[c("log_or", "se")]
  step <- A[["bias.tipping_step"]]
  ticks <- function(from) sort(unique(round(c(seq(from, 1, by = step), 1), 6)))  # always ends at 1
  grid <- expand.grid(se = ticks(0.6), sp = ticks(0.4))
  first_tip <- length(tipping_rows) + 1
  for (g in seq_len(nrow(grid))) {
    draws <- oaimodels::pba(person, k, fit_adj, data.frame(stratum = "all", se = grid$se[g], sp = grid$sp[g]),
                            iterations = A[["bias.tipping_iterations"]], seed = seed, cores = cores)
    s <- oaimodels::summarise_pba(draws)
    tipping_rows[[length(tipping_rows) + 1]] <- data.frame(
      outcome = o, se = grid$se[g], sp = grid$sp[g], or = s$or, lo = s$lo_total, hi = s$hi_total,
      excludes_1 = if (is.na(s$or)) NA else (s$hi_total < 1 | s$lo_total > 1), discarded = s$discarded
    )
  }
  # Perfect classification must reproduce the observed adjusted OR (as the gate above does for pba)
  tip <- do.call(rbind, tipping_rows[first_tip:length(tipping_rows)])
  perfect <- tip$or[tip$se == 1 & tip$sp == 1]
  adjusted_or <- oaimodels::fit_knee_gee(k, models[["or_adj"]], corstr = model$corstr)[["or"]]
  if (length(perfect) != 1 || is.na(perfect) || abs(perfect - adjusted_or) > 1e-8) {
    stop("bias step: the Se = 1, Sp = 1 tipping cell does not reproduce the observed adjusted ", o,
         " odds ratio", call. = FALSE)
  }
  for (scenario in c("non-differential", "differential")) {
    set.seed(seed)
    ors <- replicate(iterations, {
      if (scenario == "non-differential") {
        se <- stats::rbeta(1, nondiff$se1, nondiff$se2)
        sp <- stats::rbeta(1, nondiff$sp1, nondiff$sp2)
        oaimodels::correct_or_2x2(a, b, c0, d0, se, sp)
      } else {
        oaimodels::correct_or_2x2(
          a, b, c0, d0,
          se_case = stats::rbeta(1, diff$se1[1], diff$se2[1]), sp_case = stats::rbeta(1, diff$sp1[1], diff$sp2[1]),
          se_ctrl = stats::rbeta(1, diff$se1[2], diff$se2[2]), sp_ctrl = stats::rbeta(1, diff$sp1[2], diff$sp2[2])
        )
      }
    })
    kept <- ors[!is.na(ors)]
    summary_rows[[length(summary_rows) + 1]] <- data.frame(
      outcome = o, scenario = scenario, crude_or = (a * d0) / (b * c0),
      or = if (length(kept)) stats::median(kept) else NA_real_,
      lo = if (length(kept)) unname(stats::quantile(kept, 0.025)) else NA_real_,
      hi = if (length(kept)) unname(stats::quantile(kept, 0.975)) else NA_real_,
      discarded = mean(is.na(ors)), n = iterations,
      flagged = mean(is.na(ors)) > A[["bias.max_discard_share"]]
    )
  }
}

pba_all <- do.call(rbind, pba_rows)
write <- function(df, name) utils::write.csv(df, file.path(out_dir, name), row.names = FALSE)
write(do.call(rbind, prior_rows), "bias_priors.csv")
write(pba_all, "bias_pba.csv")
write(do.call(rbind, tipping_rows), "bias_tipping.csv")
write(do.call(rbind, summary_rows), "bias_summary_level.csv")
# The bias ORs, then how many prior persons each outcome has outside its model frame
write(data.frame(
  metric = c(sprintf("bias.%s.%s.%s.or", pba_all$outcome, pba_all$model,
                     ifelse(pba_all$scenario == "differential", "diff", "nondiff")),
             sprintf("bias.%s.prior_persons_outside_model", outcomes)),
  value = c(pba_all$or, vapply(outcomes, function(o) as.numeric(inputs[[o]]$outside), numeric(1)))
), "metrics_bias.csv")
print(pba_all[, c("outcome", "model", "scenario", "observed_or", "or", "lo_total", "hi_total", "conclusion_share")])
