# Step `models`: knee-level logistic GEE (clustered within person) for four outcomes
# (incident KL >= 2 and incident SOA by 48 and by 96 months).
#   G1  early-stage OA (Luyten 2018) vs other KL 0-1 knees: Mahmoudian 2021's enrichment
#   C1  Framing 1, within early OA: exam crepitus vs tenderness only; self-reported crepitus
#   C2  Framing 2, KL 0-1 knees meeting the KOOS criterion: exam crepitus vs none; self-report
# Model 1 adds age, sex and BMI; model 2 adds the other crepitus measure. A term whose level
# (or reference) has fewer than MIN_EVENTS events is written as NA, not fitted.

A <- oaimodels::assumptions()
frame_dir <- Sys.getenv("OAI_FRAME_DIR")
out_dir <- Sys.getenv("OAI_RESULTS_DIR")
covariates <- A[["model.covariates"]]
outcomes <- c("roa48", "roa96", "soa48", "soa96")
s2_levels <- c("never", "rarely", "sometimes", "often", "always")
MIN_EVENTS <- 5

knees <- oaimodels::read_frame(file.path(frame_dir, "knees.parquet"))
knees <- knees[order(knees$ID), , drop = FALSE]
if (identical(A[["exposure.s2_coding"]], "levels")) {
  knees$s2 <- factor(knees$s2_0, levels = 0:4)
  s2_terms <- setNames(sprintf("s2%d", 1:4), paste0("s2_", s2_levels[-1]))
} else {
  knees$s2 <- as.integer(knees$s2_0 >= 1)
  s2_terms <- c(s2_any = "s2")
}

metrics <- list()
put <- function(key, value) metrics[[key]] <<- value

# Events per level of the term's variable, so a sparse level is not fitted
too_sparse <- function(d, variable, outcome) {
  counts <- tapply(d[[outcome]], d[[variable]], sum)
  any(is.na(counts)) || any(counts < MIN_EVENTS) || length(counts) < 2
}

fit_rows <- function(table, d, variable, terms, other, outcome) {
  models <- list(or_unadj = variable, or_adj = c(variable, covariates))
  if (!is.null(other)) models$or_adj_other <- c(variable, covariates, other)
  rows <- list()
  for (model in names(models)) {
    needs <- unique(c(outcome, "ID", models[[model]]))
    dd <- d[stats::complete.cases(d[, needs, drop = FALSE]), , drop = FALSE]
    dd[[outcome]] <- as.integer(dd[[outcome]])
    sparse <- too_sparse(dd, variable, outcome)
    for (term in names(terms)) {
      est <- if (sparse) list(or = NA_real_, lo = NA_real_, hi = NA_real_) else
        tryCatch(oaimodels::fit_knee_gee(dd, paste(models[[model]], collapse = " + "),
                                         outcome = outcome, term = terms[[term]],
                                         corstr = A[["model.corstr"]]),
                 error = function(e) list(or = NA_real_, lo = NA_real_, hi = NA_real_))
      key <- sprintf("%s.%s.%s.%s", table, outcome, term, model)
      put(key, est[["or"]]); put(paste0(key, ".lo"), est[["lo"]]); put(paste0(key, ".hi"), est[["hi"]])
      rows[[length(rows) + 1]] <- data.frame(outcome = outcome, exposure = variable, model = model,
                                             term = term, n = nrow(dd), events = sum(dd[[outcome]]),
                                             or = est[["or"]], lo = est[["lo"]], hi = est[["hi"]])
    }
  }
  do.call(rbind, rows)
}

write_table <- function(rows, name) {
  utils::write.csv(do.call(rbind, rows), file.path(out_dir, sprintf("table_%s.csv", name)),
                   row.names = FALSE)
}

# G1: early OA vs controls (KL 0-1 knees in the denominator that are not early OA)
g1 <- knees[!is.na(knees$luyten) & knees$kl01 %in% TRUE, , drop = FALSE]
g1$early <- as.integer(g1$luyten)
write_table(lapply(outcomes, function(o) fit_rows("g1", g1, "early", c(early = "early"), NULL, o)), "g1")

# C1, C2: exam crepitus (binary) and self-reported crepitus, each adjusted for the other
framing <- function(table, exposure) {
  d <- knees[!is.na(knees[[exposure]]), , drop = FALSE]
  d$exam <- d[[exposure]]
  rows <- list()
  for (o in outcomes) {
    rows[[length(rows) + 1]] <- fit_rows(table, d, "exam", c(exam = "exam"), "s2", o)
    rows[[length(rows) + 1]] <- fit_rows(table, d, "s2", s2_terms, "exam", o)
  }
  rows
}
write_table(framing("c1", "f1_exposure"), "c1")
write_table(framing("c2", "f2_exposure"), "c2")

utils::write.csv(data.frame(metric = names(metrics), value = unlist(metrics)),
                 file.path(out_dir, "metrics_models.csv"), row.names = FALSE)
cat("Tables G1, C1 and C2 written to", out_dir, "\n")
