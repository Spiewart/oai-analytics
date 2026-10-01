# Step `bias`: how far could misclassification of the walking item move Lo 2022's odds ratios?
# (spec 7). Refits the replication's own models on reclassified exposure.
A <- oaimodels::assumptions()
frames <- Sys.getenv("OAI_FRAME_DIR")
out_dir <- Sys.getenv("OAI_RESULTS_DIR")
persons <- oaimodels::read_frame(required = c("ID", "walker", "device_walker", "in_lo"))
knees_all <- oaimodels::read_frame(file.path(frames, "lo_knees.parquet"), required = c("ID", "walker"))
model <- jsonlite::fromJSON(file.path(frames, "lo_model.json"))
published <- utils::read.csv(file.path(out_dir, "lo2022_t2.csv"), na.strings = c("", "NA"))
replicated <- utils::read.csv(file.path(out_dir, "lo2022_table2.csv"))
outcomes <- c("new_pain", "kl_worse", "jsn_worse", "improved_pain")
models <- c(or_unadj = model$or_unadj, or_adj = model$or_adj)
base_covariates <- strsplit(model$covariates, ",")[[1]]
cores <- as.integer(Sys.getenv("OAI_R_CORES", max(1L, parallel::detectCores() - 1L)))
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

pba_rows <- list(); prior_rows <- list(); tipping_rows <- list(); summary_rows <- list()
for (o in outcomes) {
  k <- knee_data(o)
  first <- !duplicated(k$ID)
  person <- data.frame(ID = k$ID[first], observed = k$walker[first])
  person$stratum <- ifelse(person$ID %in% k$ID[k$y == 1], "case", "noncase")
  v <- validated[!is.na(validated[[paste0(o, "_any")]]), ]
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
    pub <- oaireport::parse_or(published$published[published$metric == paste0("t2.", o, ".", m)])
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
  grid <- expand.grid(se = round(seq(0.6, 1, by = step), 6), sp = round(seq(0.4, 1, by = step), 6))
  for (g in seq_len(nrow(grid))) {
    draws <- oaimodels::pba(person, k, fit_adj, data.frame(stratum = "all", se = grid$se[g], sp = grid$sp[g]),
                            iterations = A[["bias.tipping_iterations"]], seed = seed, cores = cores)
    s <- oaimodels::summarise_pba(draws)
    tipping_rows[[length(tipping_rows) + 1]] <- data.frame(
      outcome = o, se = grid$se[g], sp = grid$sp[g], or = s$or, lo = s$lo_total, hi = s$hi_total,
      excludes_1 = !is.na(s$or) & (s$hi_total < 1 | s$lo_total > 1), discarded = s$discarded
    )
  }
  count <- function(group, what) {
    as.numeric(published$published[published$metric == sprintf("t2.%s.%s.%s", o, group, what)])
  }
  a <- count("walkers", "events")
  b <- count("nonwalkers", "events")
  c0 <- count("walkers", "n") - a
  d0 <- count("nonwalkers", "n") - b
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
      discarded = mean(is.na(ors))
    )
  }
}

pba_all <- do.call(rbind, pba_rows)
write <- function(df, name) utils::write.csv(df, file.path(out_dir, name), row.names = FALSE)
write(do.call(rbind, prior_rows), "bias_priors.csv")
write(pba_all, "bias_pba.csv")
write(do.call(rbind, tipping_rows), "bias_tipping.csv")
write(do.call(rbind, summary_rows), "bias_summary_level.csv")
write(data.frame(metric = sprintf("bias.%s.%s.%s.or", pba_all$outcome, pba_all$model,
                                  ifelse(pba_all$scenario == "differential", "diff", "nondiff")),
                 value = pba_all$or), "metrics_bias.csv")
print(pba_all[, c("outcome", "model", "scenario", "observed_or", "or", "lo_total", "hi_total", "conclusion_share")])
