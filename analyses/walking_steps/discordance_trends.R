# Step `discordance_trends`: stage 2, each time-varying measure's trajectory in the two "Yes" groups.
# For each comparison, replacement rule (`censored`) and time-varying measure, one
# oaimodels::walker_model() fit over discordance.trend_visits, adjusted for
# discordance.trend_covariates: an LME with a random intercept per person for continuous measures, a
# GEE for 0/1 measures. walker_yes is "Yes, not a step walker", so each per-visit estimate is that
# group against "Yes, step walker" (a difference, or an OR). "No" is not modelled. With one period
# per visit, the model's period_test is the group x visit test (p_interaction).
# Writes discordance_trends_raw.csv to OAI_FRAME_DIR: raw p only, before the small-cell rule and
# Holm, which discordance_holm.py applies before anything reaches results. A fit that fails leaves a
# row with converged FALSE and the reason in fit_note; the other measures go on.
A <- oaimodels::assumptions()
frames <- Sys.getenv("OAI_FRAME_DIR")
out_path <- file.path(frames, "discordance_trends_raw.csv")
unlink(out_path)

visits <- as.character(unlist(A[["discordance.trend_visits"]]))
covariates <- as.character(unlist(A[["discordance.trend_covariates"]]))
corstr <- A[["discordance.gee_corstr"]]
lme_optimizer <- A[["discordance.lme_optimizer"]]
fit_timeout <- A[["discordance.fit_timeout"]]
comparisons <- names(A[["discordance.comparisons"]])
yes_not <- "Yes, not a step walker"
yes_step <- "Yes, step walker"

groups <- oaimodels::read_frame(file.path(frames, "discordance_groups.parquet"),
                                required = c("comparison", "ID", "group"))
long <- oaimodels::read_frame(file.path(frames, "discordance_long.parquet"),
                              required = c("ID", "visit", "measure", "value", "censored"))
fixed <- oaimodels::read_frame(file.path(frames, "discordance_fixed.parquet"),
                               required = c("comparison", "ID", "measure", "value"))
kinds <- oaimodels::read_frame(file.path(frames, "discordance_measures.parquet"),
                               required = c("measure", "kind"))
kind_of <- stats::setNames(kinds$kind, kinds$measure)

# Covariates: person-level fixed measures (comparison null), one column each
person <- fixed[is.na(fixed$comparison) & fixed$measure %in% covariates, , drop = FALSE]
missing_cov <- setdiff(covariates, unique(person$measure))
if (length(missing_cov)) stop("covariates not in discordance_fixed: ", paste(missing_cov, collapse = ", "))
cov <- data.frame(ID = unique(person$ID))
for (cv in covariates) {
  rows <- person[person$measure == cv, , drop = FALSE]
  cov[[cv]] <- rows$value[match(cov$ID, rows$ID)]
}

long$visit <- as.character(long$visit)
long <- long[long$visit %in% visits, , drop = FALSE]
unknown <- setdiff(unique(long$measure), names(kind_of))
if (length(unknown)) stop("measures without a kind: ", paste(unknown, collapse = ", "))
measures <- sort(unique(long$measure[kind_of[long$measure] %in% c("continuous", "binary")]))
skipped <- setdiff(unique(long$measure), measures)
if (length(skipped)) cat("not time-varying trends (categorical):", paste(skipped, collapse = ", "), "\n")

fit_one <- function(data, kind) {
  present <- intersect(visits, unique(data$visit[!is.na(data$value)]))
  data <- data[data$visit %in% present, , drop = FALSE]
  periods <- stats::setNames(as.list(present), present)
  family <- if (kind == "continuous") "gaussian" else "binomial"
  rows <- oaimodels::walker_model(data, covariates = covariates, structure = "visit", family = family,
                                  periods = periods, corstr = corstr, fit_timeout = fit_timeout,
                                  lme_optimizer = lme_optimizer)
  note <- rows$fit_note
  error <- attr(rows, "fit_error")
  if (!is.null(error)) note <- ifelse(is.na(note), paste("fit failed:", error), note)
  dropped <- attr(rows, "dropped_visits")
  out <- data.frame(visit = rows$term, estimate = rows$estimate, lo = rows$lo, hi = rows$hi,
                    p_visit = rows$p, scale = rows$scale, persons_model = rows$n_people,
                    observations_model = rows$n_obs, converged = rows$converged, fit_note = note,
                    p_interaction = attr(rows, "period_test"), stringsAsFactors = FALSE)
  test_error <- attr(rows, "period_test_error")
  out$test_note <- if (is.null(test_error)) NA_character_ else test_error
  if (length(dropped)) {
    # visits with no events or no non-events in both groups: a visible row, no estimate
    out <- rbind(out, data.frame(visit = dropped, estimate = NA_real_, lo = NA_real_, hi = NA_real_,
                                 p_visit = NA_real_, scale = out$scale[1],
                                 persons_model = out$persons_model[1],
                                 observations_model = out$observations_model[1], converged = FALSE,
                                 fit_note = "constant outcome at this visit",
                                 p_interaction = out$p_interaction[1], test_note = out$test_note[1],
                                 stringsAsFactors = FALSE))
  }
  out
}

started <- Sys.time()
results <- list()
for (comparison in comparisons) {
  g <- groups[groups$comparison == comparison & groups$group %in% c(yes_not, yes_step), , drop = FALSE]
  if (!nrow(g)) stop("no Yes groups for comparison ", comparison)
  people <- merge(data.frame(ID = g$ID, walker_yes = g$group == yes_not), cov, by = "ID", all.x = TRUE)
  for (censored in c(FALSE, TRUE)) {
    for (measure in measures) {
      rows <- long[long$measure == measure & long$censored == censored, c("ID", "visit", "value"), drop = FALSE]
      if (!nrow(rows)) next
      data <- merge(rows, people, by = "ID")
      kind <- kind_of[[measure]]
      if (kind == "binary") data$value <- as.numeric(data$value)
      out <- tryCatch(fit_one(data, kind), error = function(e) {
        data.frame(visit = NA_character_, estimate = NA_real_, lo = NA_real_, hi = NA_real_,
                   p_visit = NA_real_, scale = if (kind == "continuous") "difference" else "or",
                   persons_model = NA_integer_, observations_model = NA_integer_, converged = FALSE,
                   fit_note = paste("fit failed:", conditionMessage(e)), p_interaction = NA_real_,
                   test_note = NA_character_, stringsAsFactors = FALSE)
      })
      out <- cbind(data.frame(comparison = comparison, censored = censored, measure = measure,
                              kind = kind, stringsAsFactors = FALSE), out)
      results[[length(results) + 1L]] <- out
      cat(sprintf("%s censored=%s %s: %d rows, converged %d\n", comparison, censored, measure,
                  nrow(out), sum(out$converged, na.rm = TRUE)))
    }
  }
}
raw <- do.call(rbind, results)
utils::write.csv(raw, out_path, row.names = FALSE, na = "")
cat(sprintf("discordance_trends: %d rows in %.1f minutes\n", nrow(raw),
            as.numeric(difftime(Sys.time(), started, units = "mins"))))
