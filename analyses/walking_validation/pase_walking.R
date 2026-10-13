# Step `pase_walking`: the 96-month walking question against PASE at every visit. Everyone with a
# walking answer (pase_frame.parquet, from the cohort step) is grouped by the answer: "No" (the
# reference), any "Yes", and "Yes" by amount (times a month, years walked); a sensitivity
# grouping uses Lo et al. 2022's walker (a yes with at least one amount). At each PASE visit
# three outcomes are compared with "No": the PASE total, any walking outside the home (item 2,
# days > 0) and estimated walking hours a week (item 2 days x hours a day at the scoring
# midpoints). Crude and adjusted contrasts come from oaimodels::group_contrasts(); trends across
# ordered amount levels from Jonckheere-Terpstra (numbers) and Cochran-Armitage (yes/no).
A <- oaimodels::assumptions()
visits <- unlist(A[["pase.all_visits"]])
amounts <- unlist(A[["pase_walking.amounts"]])
covariates <- unlist(A[["pase_walking.covariates"]])
scoring <- A[["pase.walking_scoring"]]
reps <- A[["validity.bootstrap_reps"]]
se_method <- A[["validity.median_regression_se"]]
perms <- A[["validity.jt_permutations"]]
seed <- A[["bias.seed"]]
p_adjust <- A[["pase_walking.p_adjust"]]
labels <- lapply(A[["components.answer_labels"]], unlist)
amount_columns <- c(times = "amount_times", months = "amount_months", years = "amount_years")
if (length(bad <- setdiff(amounts, names(amount_columns)))) {
  stop("unknown pase_walking.amounts: ", paste(bad, collapse = ", "), call. = FALSE)
}
frame <- oaimodels::read_frame(file.path(Sys.getenv("OAI_FRAME_DIR"), "pase_frame.parquet"),
                               required = c("ID", "walk_item", "walker", unname(amount_columns[amounts]), covariates))
out_dir <- Sys.getenv("OAI_RESULTS_DIR")

# Groupings: a factor per grouping, its first level the reference
said_yes <- frame$walk_item == 1
amount_group <- function(column) {
  code <- frame[[column]]
  g <- ifelse(frame$walk_item == 0, "no", ifelse(said_yes & !is.na(code), as.character(code), NA))
  factor(g, levels = c("no", sort(unique(stats::na.omit(as.character(code))))))
}
groupings <- c(
  list(any = factor(ifelse(said_yes, "yes", "no"), levels = c("no", "yes")),
       any_lo = factor(ifelse(frame$walker, "walker", "non_walker"), levels = c("non_walker", "walker"))),
  stats::setNames(lapply(amount_columns[amounts], amount_group), amounts)
)
level_label <- function(grouping, level) {
  fixed <- c(no = "No", yes = "Yes (any)", non_walker = "Non-walker (Lo et al. coding)", walker = "Walker (Lo et al. coding)")
  amount <- if (grouping %in% names(labels)) labels[[grouping]][suppressWarnings(as.integer(level))] else level
  unname(ifelse(level %in% names(fixed), fixed[level], amount))
}

# Outcomes at a visit: whichever the visit has
outcomes_at <- function(v) {
  out <- list()
  total <- paste0("pase_total_", v)
  if (total %in% names(frame)) out$total <- as.numeric(frame[[total]])
  days <- frame[[paste0("pase_days_", v)]]
  if (!is.null(days)) {
    hours <- frame[[paste0("pase_hours_", v)]]
    out$walking_any <- ifelse(is.na(days), NA, days > 0)
    week <- unlist(scoring$days)[days + 1] * unlist(scoring$hours)[hours]
    out$walking_hours <- ifelse(is.na(days), NA, ifelse(days == 0, 0, week))
  }
  out
}

summaries <- list(); contrasts <- list(); trends <- list()
cov_frame <- frame[covariates]
for (v in visits) {
  for (outcome in names(ys <- outcomes_at(v))) {
    y <- ys[[outcome]]
    for (grouping in names(groupings)) {
      g <- groupings[[grouping]]
      base <- data.frame(grouping = grouping, visit = v, outcome = outcome)
      s <- oaimodels::group_summaries(y, g)
      summaries[[length(summaries) + 1]] <- cbind(base, s, label = level_label(grouping, s$level))
      k <- oaimodels::group_contrasts(y, g, covariates = cov_frame, se = se_method, reps = reps,
                                      seed = seed, adjust = p_adjust)
      contrasts[[length(contrasts) + 1]] <- cbind(base, k, label = level_label(grouping, k$level))
      if (grouping %in% amounts) {
        ok <- !is.na(y) & !is.na(g)
        p <- if (is.logical(y)) {
          tab <- table(factor(g[ok], levels = levels(g)), factor(y[ok], levels = c(FALSE, TRUE)))
          stats::prop.trend.test(tab[, "TRUE"], rowSums(tab))$p.value
        } else {
          oaimodels::jonckheere(y[ok], droplevels(g[ok]), permutations = perms, seed = seed)[["p"]]
        }
        trends[[length(trends) + 1]] <- cbind(
          base, test = if (is.logical(y)) "cochran_armitage" else "jonckheere_terpstra", p = p, n = sum(ok))
      }
    }
  }
}

# The month of each visit, as the cohort step's PASE counts give it
months <- utils::read.csv(file.path(out_dir, "pase_visits.csv"), colClasses = c(visit = "character"))
months <- unique(months[c("visit", "month")])
with_month <- function(rows) {
  df <- do.call(rbind, rows)
  df$month <- months$month[match(df$visit, months$visit)]
  df[c("grouping", "visit", "month", setdiff(names(df), c("grouping", "visit", "month")))]
}
utils::write.csv(with_month(summaries), file.path(out_dir, "pase_walking_groups.csv"), row.names = FALSE)
utils::write.csv(with_month(contrasts), file.path(out_dir, "pase_walking_contrasts.csv"), row.names = FALSE)
utils::write.csv(with_month(trends), file.path(out_dir, "pase_walking_trend.csv"), row.names = FALSE)
cat(sprintf("pase_walking: %d group summaries, %d contrasts, %d trend tests over %d visits\n",
            sum(vapply(summaries, nrow, integer(1))), sum(vapply(contrasts, nrow, integer(1))),
            length(trends), length(visits)))
