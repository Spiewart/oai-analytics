# Step `dual_models`: KOOS S2 x exam crepitus on the Lo 2018 cohort (not graded).
# Concordance per exposure visit, and the predictive value of each measure and both for
# incident SOA, in the one-year (GEE) and four-year (logistic) frames.

A <- oaimodels::assumptions()
frame_dir <- Sys.getenv("OAI_FRAME_DIR")
out_dir <- Sys.getenv("OAI_RESULTS_DIR")
covariates <- A[["model.covariates"]]
cuts <- A[["dual.s2_cuts"]]
combos <- c("neither", "s2_only", "exam_only", "both")
exposure_visits <- c("00", "01", "03", "05")

periods <- oaimodels::read_frame(file.path(frame_dir, "dual_periods.parquet"))
persons <- oaimodels::read_frame(file.path(frame_dir, "dual_persons.parquet"))
periods$event <- as.integer(periods$event)
persons$event <- as.integer(persons$event)

# Concordance: one row per exposure visit (period) and cut, among observations with both measures
concordance <- do.call(rbind, lapply(cuts, function(cut) {
  do.call(rbind, lapply(1:4, function(p) {
    d <- periods[periods$period == p & !is.na(periods$crep) & !is.na(periods$exam), ]
    s2 <- d$crep >= cut
    exam <- d$exam == 1
    a <- sum(s2 & exam); b <- sum(!s2 & exam); c <- sum(s2 & !exam); n0 <- sum(!s2 & !exam)
    n <- nrow(d)
    k <- oaimodels::kappa_ci(s2, exam)
    auc <- oaimodels::auc_ci(d$crep, exam)
    data.frame(visit = exposure_visits[p], cut = cut, n = n, both = a, exam_only = b,
               s2_only = c, neither = n0, agreement = (a + n0) / n,
               kappa = k[["estimate"]], kappa_lo = k[["lo"]], kappa_hi = k[["hi"]],
               prevalence_index = (a - n0) / n, bias_index = (c - b) / n,
               auc_s2_for_exam = auc[["estimate"]], auc_lo = auc[["lo"]], auc_hi = auc[["hi"]])
  }))
}))
utils::write.csv(concordance, file.path(out_dir, "dual_concordance.csv"), row.names = FALSE)

gee <- function(d, rhs, term) {
  oaimodels::fit_knee_gee(d, rhs, outcome = "event", term = term, corstr = A[["model.corstr"]])
}
logit <- function(d, rhs, term) oaimodels::fit_logit(d, rhs, outcome = "event", term = term)
frames <- list(
  periods = list(data = periods, s2 = "crep", exam = "exam", fit = gee),
  persons = list(data = persons, s2 = "crep0", exam = "exam0", fit = logit)
)

row_of <- function(frame, cut, analysis, term, est, d) {
  data.frame(frame = frame, cut = cut, analysis = analysis, term = term,
             estimate = est[["or"]], lo = est[["lo"]], hi = est[["hi"]],
             n = nrow(d), events = sum(d$event))
}

prediction <- list()
for (frame in names(frames)) {
  f <- frames[[frame]]
  for (cut in cuts) {
    d <- f$data
    d$combo <- factor(d[[sprintf("combo_s2ge%d", cut)]], levels = combos)
    d$s2_pos <- as.integer(d[[f$s2]] >= cut)
    d$exam_pos <- as.integer(d[[f$exam]] == 1)
    d <- d[stats::complete.cases(d[, c("event", "combo", covariates)]), ]
    d <- d[order(d$ID), ]
    for (model in c("unadjusted", "adjusted")) {
      adjust <- if (model == "adjusted") covariates else character()
      for (level in combos[-1]) {
        est <- f$fit(d, paste(c("combo", adjust), collapse = " + "), paste0("combo", level))
        prediction[[length(prediction) + 1]] <- row_of(frame, cut, paste("combo", model), level, est, d)
      }
      rhs <- paste(c("s2_pos * exam_pos", adjust), collapse = " + ")
      for (term in c("s2_pos", "exam_pos", "s2_pos:exam_pos")) {
        est <- f$fit(d, rhs, term)
        prediction[[length(prediction) + 1]] <- row_of(frame, cut, paste("interaction", model), term, est, d)
      }
    }
  }
}
prediction <- do.call(rbind, prediction)
utils::write.csv(prediction, file.path(out_dir, "dual_prediction.csv"), row.names = FALSE)

# Classification of four-year incident SOA by each measure, both, and either
classification <- do.call(rbind, lapply(cuts, function(cut) {
  d <- persons[!is.na(persons$crep0) & !is.na(persons$exam0), ]
  s2 <- d$crep0 >= cut
  exam <- d$exam0 == 1
  tests <- list(s2 = s2, exam = exam, both = s2 & exam, either = s2 | exam)
  do.call(rbind, lapply(names(tests), function(t) {
    cbind(data.frame(cut = cut, test = t), oaimodels::classification(tests[[t]], d$event == 1))
  }))
}))
utils::write.csv(classification, file.path(out_dir, "dual_classification.csv"), row.names = FALSE)
cat("Dual-measure tables written to", out_dir, "\n")
