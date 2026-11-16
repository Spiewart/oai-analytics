#' Collect a step's metrics and write them as metrics_<name>.csv
#'
#' A run's metrics files (columns `metric`, `value`) are what `oai.replication` grades and
#' what `oaireport::load_results()` reads into `run$metrics`. The recorder keeps them in the
#' order they were put; putting a key again replaces its value (NULL removes it).
#'
#' @return A list of functions:
#'   `put(key, value)`;
#'   `put_est(key, est, value = "or")` puts `est[[value]]` as `key` and `est[["lo"]]`,
#'   `est[["hi"]]` as `key.lo`, `key.hi` (an estimate from `fit_knee_gee`, `fit_logit` or a
#'   one-row data.frame);
#'   `write(dir = OAI_RESULTS_DIR, name = "models")` writes `metrics_<name>.csv`;
#'   `values()` returns the named list.
metrics_recorder <- function() {
  values <- list()
  put <- function(key, value) {
    values[[key]] <<- value
    invisible(value)
  }
  put_est <- function(key, est, value = "or") {
    put(key, unname(est[[value]]))
    put(paste0(key, ".lo"), unname(est[["lo"]]))
    put(paste0(key, ".hi"), unname(est[["hi"]]))
  }
  write <- function(dir = Sys.getenv("OAI_RESULTS_DIR"), name = "models") {
    path <- file.path(dir, sprintf("metrics_%s.csv", name))
    utils::write.csv(data.frame(metric = names(values), value = unlist(values)), path,
                     row.names = FALSE)
    invisible(path)
  }
  list(put = put, put_est = put_est, write = write, values = function() values)
}

#' Write result rows as <name>.csv
#'
#' @param rows A data.frame, or a list of data.frames with the same columns (bound in order).
#' @param name File name without `.csv`.
#' @param dir Folder; defaults to the run's `OAI_RESULTS_DIR`.
write_rows <- function(rows, name, dir = Sys.getenv("OAI_RESULTS_DIR")) {
  if (!is.data.frame(rows)) rows <- do.call(rbind, rows)
  path <- file.path(dir, paste0(name, ".csv"))
  utils::write.csv(rows, path, row.names = FALSE)
  invisible(path)
}

#' Covariates for a model of GT1M device measures, from the run's ledger
#'
#' `model.covariates` for model "m1"; model "m2" adds the ledger's `second` set. A `wear_hr`
#' entry becomes one column per device wave the model spans (`wear_hr_48`, `wear_hr_72`), so a
#' model with activity at both waves adjusts for wear time at both.
#'
#' @param A The run's assumptions (`assumptions()`).
#' @param model "m1" or "m2".
#' @param waves Device waves in the model, as column suffixes ("48", "72").
#' @param second Ledger key of the extra covariates in model "m2".
device_covariates <- function(A, model, waves, second = "model.covariates_2") {
  base <- A[["model.covariates"]]
  wear <- if ("wear_hr" %in% base) sprintf("wear_hr_%s", waves) else character()
  out <- c(setdiff(base, "wear_hr"), wear)
  if (identical(model, "m2")) out <- c(out, A[[second]])
  out
}
