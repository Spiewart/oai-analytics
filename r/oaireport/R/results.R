# Run results for reports. `oai report` sets OAI_RESULTS_ROOT (<results_dir>/<analysis>)
# and OAI_REPORT_RUNS (the [report] runs, comma-separated).

reserved_parts <- c("metrics", "assumptions", "run_info")

load_results <- function(root = Sys.getenv("OAI_RESULTS_ROOT"),
                         labels = strsplit(Sys.getenv("OAI_REPORT_RUNS"), ",", fixed = TRUE)[[1]]) {
  if (!nzchar(root)) stop("no results root: pass `root` or render with `oai report`", call. = FALSE)
  if (!length(labels)) stop("no run labels: pass `labels` or render with `oai report`", call. = FALSE)
  stats::setNames(lapply(labels, function(label) load_run(file.path(root, label), label)), labels)
}

load_run <- function(dir, label) {
  how <- sprintf("run `oai report <analysis> --run` (or `oai run <analysis>%s`)",
                 if (identical(label, "default")) "" else paste(" --variant", label))
  info_path <- file.path(dir, "run_info.json")
  if (!file.exists(info_path)) {
    stop(sprintf("no run '%s' in %s; %s", label, dirname(dir), how), call. = FALSE)
  }
  run_info <- jsonlite::read_json(info_path)
  if (is.null(run_info$finished_utc)) {
    stop(sprintf("run '%s' did not finish; %s", label, how), call. = FALSE)
  }
  csvs <- list.files(dir, pattern = "\\.csv$", full.names = TRUE)
  stems <- sub("\\.csv$", "", basename(csvs))
  shadowed <- stems %in% reserved_parts
  if (any(shadowed)) {
    stop("run '", label, "' has ", paste0(stems[shadowed], ".csv", collapse = ", "),
         ", which would shadow load_results() parts", call. = FALSE)
  }
  run <- stats::setNames(lapply(csvs, utils::read.csv, na.strings = c("", "NA")), stems)
  metrics <- do.call(rbind, run[startsWith(stems, "metrics_")])
  run$metrics <- if (is.null(metrics)) numeric() else stats::setNames(as.numeric(metrics$value), metrics$metric)
  assumptions_path <- file.path(dir, "assumptions.resolved.json")
  run$assumptions <- if (file.exists(assumptions_path)) jsonlite::read_json(assumptions_path)
  run$run_info <- run_info
  run
}

# "0.6 (0.4-0.8) *" (oai.replication's odds-ratio text; * = significant) -> or, lo, hi, sig.
parse_or <- function(text) {
  pattern <- "^\\s*([0-9.]+) \\(([0-9.]+)-([0-9.]+)\\)( \\*)?\\s*$"
  text <- as.character(text)
  n <- length(text)
  out <- data.frame(or = rep(NA_real_, n), lo = rep(NA_real_, n), hi = rep(NA_real_, n),
                    sig = rep(NA, n))
  ok <- !is.na(text) & grepl(pattern, text)
  if (any(ok)) {
    parts <- do.call(rbind, regmatches(text[ok], regexec(pattern, text[ok])))
    out$or[ok] <- as.numeric(parts[, 2])
    out$lo[ok] <- as.numeric(parts[, 3])
    out$hi[ok] <- as.numeric(parts[, 4])
    out$sig[ok] <- nzchar(parts[, 5])
  }
  out
}
