# Number formatting and result lookups shared by the reports' setup chunks.

#' A number to `digits` decimals with thousands separators: fmt_num(-1234.5, 1) is "−1,234.5"
#'
#' `minus = TRUE` prints negatives with a true minus (U+2212), as fmt_ci does; FALSE keeps the
#' ASCII hyphen.
fmt_num <- function(x, digits = 2, minus = TRUE) {
  out <- formatC(x, format = "f", digits = digits, big.mark = ",")
  if (minus) sub("^-", "−", out) else out
}

#' A whole number with thousands separators: "1,234"
fmt_count <- function(x) formatC(x, format = "d", big.mark = ",")

#' A share as a percentage: fmt_pct(0.256) is "26%"
fmt_pct <- function(x, digits = 0, minus = TRUE) paste0(fmt_num(100 * x, digits, minus), "%")

#' The text with its first character in lower case (a label used mid-sentence)
lower_first <- function(x) paste0(tolower(substr(x, 1, 1)), substring(x, 2))

#' `x` when it is a single non-missing value; otherwise stop, naming `what`
one_value <- function(x, what) {
  if (length(x) != 1 || is.na(x)) stop("no single value for ", what, call. = FALSE)
  x
}

#' The one row of `df` matching every column = value condition; stop when none or several match
#'
#' A row whose column is NA does not match. A changed results schema stops the report instead
#' of printing the wrong number.
one_row <- function(df, ...) {
  cond <- list(...)
  keep <- Reduce(`&`, Map(function(col, value) !is.na(df[[col]]) & df[[col]] == value,
                          names(cond), cond))
  row <- df[keep, , drop = FALSE]
  if (nrow(row) != 1) {
    stop("expected one row for ", paste(names(cond), unlist(cond), sep = " = ", collapse = ", "),
         ", found ", nrow(row), call. = FALSE)
  }
  row
}

#' A run's resolved value of an assumption (`run` from load_results())
run_assumption <- function(run, key) run$assumptions$assumptions[[key]]$value

#' A run's metric, which must exist and not be missing
run_metric <- function(run, key) one_value(unname(run$metrics[key]), key)
