# Construct validity of the Walkers question: Walker contrasts on one measure across repeated
# visits, the size of those contrasts, and the divergence rule that judges them by size.

#' The Walker contrast on one measure's long rows, overall or for each period or visit.
#'
#' Gaussian: `nlme::lme` with a random intercept per person, fitted by ML. Estimates are
#' differences, with t-based 95% CIs and p from the model's denominator degrees of freedom.
#' Binomial: `geepack::geeglm`, clustered on person, rows sorted by person and visit. Estimates are
#' odds ratios, with robust Wald 95% CIs and p.
#'
#' Every model has `factor(visit)` and the covariates. "overall" adds one Walker term. "period" and
#' "visit" add one Walker term per period or visit with no main effect (the same model as
#' `walker_yes:period`), so each coefficient is that period's or visit's own contrast. A period or
#' visit with only one Walker group gets no term and no row; its rows stay in the fit, where they
#' still inform the covariates and the visit terms.
#'
#' The attribute `period_test` is the p-value for whether the Walker contrast differs by period, the
#' same whichever `structure` is asked for. Gaussian: a likelihood-ratio test of the
#' `walker_yes:period` model against the one-Walker-term model, both ML on the same rows. Binomial:
#' a joint Wald test, from the robust covariance matrix, that the per-period contrasts are equal.
#' It is NA with fewer than two periods holding both groups, or with no `periods`; if only its own
#' fit fails the attribute `period_test_error` holds the message.
#'
#' @param data Long rows with `ID`, `visit`, `value`, `walker_yes` (logical or 0/1) and the
#'   covariates. Rows with a null `value`, `walker_yes`, `visit` or covariate are dropped.
#' @param covariates Names of the covariate columns.
#' @param structure "overall", "period" or "visit".
#' @param family "gaussian" or "binomial" (`value` 0/1 or logical).
#' @param periods Named list mapping each period to its visits, in reporting order, e.g.
#'   `list(before = c("00", "01"), at = "10", after = c("13", "14"))`. Needed for "period"; any
#'   visit in `data` outside it is an error.
#' @param corstr Working correlation (geepack; ignored for gaussian).
#' @return Data frame with `term`, `estimate`, `lo`, `hi`, `p`, `scale` ("difference" or "or"),
#'   `n_people`, `n_obs` (of the model as fitted, so the same on every row) and `converged`. A fit
#'   that fails or does not converge gives one row with `converged` FALSE, NA estimates, `term` NA
#'   unless `structure` is "overall", and the message as attribute `fit_error`.
walker_model <- function(data, covariates = character(), structure = c("overall", "period", "visit"),
                         family = c("gaussian", "binomial"), periods = NULL,
                         corstr = "exchangeable") {
  structure <- match.arg(structure)
  family <- match.arg(family)
  covariates <- as.character(covariates)
  frame <- walker_frame(data, covariates, family, periods, structure)
  scale <- if (family == "gaussian") "difference" else "or"
  n_people <- length(unique(frame$ID))
  n_obs <- nrow(frame)

  fits <- list()
  fit_of <- function(s) {
    if (is.null(fits[[s]])) fits[[s]] <<- walker_fit(frame, covariates, s, family, corstr)
    fits[[s]]
  }

  fit <- tryCatch(fit_of(structure), error = function(e) e)
  if (inherits(fit, "error")) {
    failed <- data.frame(term = if (structure == "overall") "overall" else NA_character_,
                         estimate = NA_real_, lo = NA_real_, hi = NA_real_, p = NA_real_, scale = scale,
                         n_people = n_people, n_obs = n_obs, converged = FALSE)
    attr(failed, "period_test") <- NA_real_
    attr(failed, "fit_error") <- conditionMessage(fit)
    return(failed)
  }

  rows <- data.frame(term = fit$table$term, estimate = fit$table$estimate, lo = fit$table$lo,
                     hi = fit$table$hi, p = fit$table$p, scale = scale, n_people = n_people,
                     n_obs = n_obs, converged = TRUE)
  if (family == "binomial") rows[c("estimate", "lo", "hi")] <- exp(rows[c("estimate", "lo", "hi")])

  period_test <- NA_real_
  if (!is.null(periods) && length(walker_estimable(frame, ".period")) >= 2) {
    period_test <- tryCatch(walker_period_test(fit_of, family), error = function(e) e)
    if (inherits(period_test, "error")) {
      attr(rows, "period_test_error") <- conditionMessage(period_test)
      period_test <- NA_real_
    }
  }
  attr(rows, "period_test") <- period_test
  rows
}

# Checks the arguments and returns the rows to fit, with `.walker` 0/1 and `.period`.
walker_frame <- function(data, covariates, family, periods, structure) {
  needed <- c("ID", "visit", "value", "walker_yes")
  for (column in c(needed, covariates)) {
    if (!column %in% names(data)) stop("walker_model(): data has no column ", column, call. = FALSE)
  }
  reserved <- intersect(covariates, needed)
  if (length(reserved)) {
    stop("walker_model(): ", paste(reserved, collapse = ", "), " cannot be a covariate", call. = FALSE)
  }
  package <- if (family == "gaussian") "nlme" else "geepack"
  if (!requireNamespace(package, quietly = TRUE)) {
    stop("walker_model() needs the ", package, " package for family = '", family, "'", call. = FALSE)
  }
  missing_id <- sum(is.na(data$ID))
  if (missing_id) {
    stop("walker_model(): ", missing_id, " rows have no ID; drop them before fitting", call. = FALSE)
  }
  check_walker_yes(data$walker_yes, "walker_model")
  y <- data$value
  if (!all(is.na(y))) {
    if (family == "gaussian" && !is.numeric(y)) {
      stop("walker_model(): value must be numeric for family = 'gaussian'", call. = FALSE)
    }
    if (family == "binomial" && (!(is.numeric(y) || is.logical(y)) || !all(y[!is.na(y)] %in% c(0, 1)))) {
      stop("walker_model(): value must be 0/1 for family = 'binomial'", call. = FALSE)
    }
  }
  if (structure == "period" && is.null(periods)) {
    stop("walker_model(): structure = 'period' needs periods", call. = FALSE)
  }

  visit <- as.character(data$visit)
  period <- NA_character_
  if (!is.null(periods)) {
    if (!is.list(periods) || is.null(names(periods)) || any(names(periods) == "")) {
      stop("walker_model(): periods must be a named list of visits", call. = FALSE)
    }
    mapped <- as.character(unlist(periods, use.names = FALSE))
    repeated <- unique(mapped[duplicated(mapped)])
    if (length(repeated)) {
      stop("walker_model(): visits in more than one period: ", paste(repeated, collapse = ", "),
           call. = FALSE)
    }
    outside <- setdiff(visit[!is.na(visit)], mapped)
    if (length(outside)) {
      stop("walker_model(): visits not in periods: ", paste(sort(outside), collapse = ", "), call. = FALSE)
    }
    owner <- rep(names(periods), lengths(periods))
    period <- owner[match(visit, mapped)]
  }

  frame <- data.frame(ID = data$ID, visit = visit, value = as.numeric(y),
                      .walker = as.numeric(data$walker_yes), .period = period,
                      check.names = FALSE, stringsAsFactors = FALSE)
  # Internal names, since nlme does not cope with non-syntactic ones in a formula
  internal <- walker_covariate_names(length(covariates))
  frame[internal] <- data[covariates]
  keep <- stats::complete.cases(frame[c("ID", "visit", "value", ".walker", internal)])
  frame <- frame[keep, , drop = FALSE]
  frame$.period <- factor(frame$.period, levels = names(periods))
  frame <- frame[order(frame$ID, frame$visit), , drop = FALSE]
  # geepack reads the cluster with as.numeric(), which a character ID would turn into NA
  frame$.cluster <- match(frame$ID, unique(frame$ID))
  rownames(frame) <- NULL
  frame
}

walker_covariate_names <- function(n) if (n) paste0(".c", seq_len(n)) else character()

check_walker_yes <- function(x, caller) {
  if (!(is.numeric(x) || is.logical(x)) || !all(x[!is.na(x)] %in% c(0, 1))) {
    stop(caller, "(): walker_yes must be logical or 0/1", call. = FALSE)
  }
}

# Levels of `by`, in order, that hold both Walker groups in the fitted rows.
walker_estimable <- function(frame, by) {
  values <- frame[[by]]
  lvls <- if (is.factor(values)) levels(values) else sort(unique(values), method = "radix")
  lvls[vapply(lvls, function(lv) {
    length(unique(frame$.walker[which(values == lv)])) == 2L
  }, logical(1))]
}

# Fits one structure. Returns the contrast table on the model's own scale, the Walker coefficient
# names, and the model. Any failure is an error, which walker_model() catches.
walker_fit <- function(frame, covariates, structure, family, corstr) {
  if (!nrow(frame)) stop("no rows left to fit", call. = FALSE)
  if (length(unique(frame$.walker)) < 2L) {
    stop("walker_yes has only one group in the fitted rows", call. = FALSE)
  }
  by <- switch(structure, overall = NULL, period = ".period", visit = "visit")
  if (is.null(by)) {
    labels <- "overall"
    walker_columns <- ".walker"
  } else {
    labels <- walker_estimable(frame, by)
    if (!length(labels)) stop("no ", structure, " holds both walker_yes groups", call. = FALSE)
    walker_columns <- paste0(".w", seq_along(labels))
    for (i in seq_along(labels)) {
      frame[[walker_columns[i]]] <- frame$.walker * (as.character(frame[[by]]) == labels[i])
    }
  }
  # A single visit has no visit terms to estimate; factor() of one level cannot be coded
  controls <- c(if (length(unique(frame$visit)) > 1L) "factor(visit)",
                walker_covariate_names(length(covariates)))
  formula <- stats::as.formula(paste("value ~", paste(c(walker_columns, controls), collapse = " + ")))

  if (family == "gaussian") {
    model <- nlme::lme(fixed = formula, random = ~ 1 | ID, data = frame, method = "ML")
    coefs <- summary(model)$tTable[walker_columns, , drop = FALSE]
    half_width <- stats::qt(0.975, coefs[, "DF"]) * coefs[, "Std.Error"]
    p <- coefs[, "p-value"]
    estimate <- coefs[, "Value"]
  } else {
    model <- geepack::geeglm(formula, id = .cluster, data = frame, family = stats::binomial, corstr = corstr)
    if (!identical(as.integer(model$geese$error), 0L)) stop("geeglm did not converge", call. = FALSE)
    coefs <- summary(model)$coefficients[walker_columns, , drop = FALSE]
    half_width <- stats::qnorm(0.975) * coefs[, "Std.err"]
    p <- coefs[, "Pr(>|W|)"]
    estimate <- coefs[, "Estimate"]
  }
  if (!all(is.finite(c(estimate, half_width)))) stop("the Walker estimate is not finite", call. = FALSE)
  table <- data.frame(term = labels, estimate = unname(estimate), lo = unname(estimate - half_width),
                      hi = unname(estimate + half_width), p = unname(p))
  list(table = table, walker_columns = walker_columns, model = model)
}

walker_period_test <- function(fit_of, family) {
  alternative <- fit_of("period")
  if (family == "gaussian") {
    null <- fit_of("overall")
    ll_null <- stats::logLik(null$model)
    ll_alternative <- stats::logLik(alternative$model)
    statistic <- max(0, 2 * (as.numeric(ll_alternative) - as.numeric(ll_null)))
    df <- attr(ll_alternative, "df") - attr(ll_null, "df")
    return(stats::pchisq(statistic, df, lower.tail = FALSE))
  }
  # Wald: every per-period coefficient equal to the first
  beta <- stats::coef(alternative$model)
  vcov <- alternative$model$geese$vbeta
  at <- match(alternative$walker_columns, names(beta))
  contrast <- matrix(0, length(at) - 1L, length(beta))
  contrast[, at[1]] <- 1
  contrast[cbind(seq_len(nrow(contrast)), at[-1])] <- -1
  gap <- contrast %*% beta
  statistic <- drop(t(gap) %*% solve(contrast %*% vcov %*% t(contrast), gap))
  stats::pchisq(statistic, nrow(contrast), lower.tail = FALSE)
}

#' An adjusted difference over the pooled within-Walker-group SD of `value` at the earliest visit
#' with a value (visits sorted as strings), so a measure missing at enrollment starts where it
#' starts. NA if that SD is zero or undefined, including when only one group has values there.
#' @param estimate Adjusted differences, on the scale of `value`.
#' @param data Long rows with `visit`, `value` and `walker_yes`.
#' @param reference Only "first_visit".
#' @return Numeric, one per `estimate`.
standardized_difference <- function(estimate, data, reference = "first_visit") {
  reference <- match.arg(reference)
  for (column in c("visit", "value", "walker_yes")) {
    if (!column %in% names(data)) {
      stop("standardized_difference(): data has no column ", column, call. = FALSE)
    }
  }
  check_walker_yes(data$walker_yes, "standardized_difference")
  undefined <- rep(NA_real_, length(estimate))
  rows <- data[!is.na(data$value) & !is.na(data$walker_yes) & !is.na(data$visit), , drop = FALSE]
  if (!nrow(rows)) return(undefined)
  first <- sort(unique(as.character(rows$visit)), method = "radix")[1]
  rows <- rows[as.character(rows$visit) == first, , drop = FALSE]
  groups <- split(rows$value, as.logical(rows$walker_yes))
  if (length(groups) < 2L) return(undefined)
  df <- sum(lengths(groups) - 1L)
  if (df < 1L) return(undefined)
  sums <- vapply(groups, function(v) sum((v - mean(v))^2), numeric(1))
  pooled <- sqrt(sum(sums) / df)
  if (!is.finite(pooled) || pooled == 0) return(undefined)
  estimate / pooled
}

#' Judges overall Walker contrasts by size, never by p-value.
#'
#' `band` uses the magnitude, so an inverse association counts: max(OR, 1/OR) on the "or" scale and
#' |std_diff| on the "difference" scale. "little_or_none" is below or_little (d_little), "moderate"
#' runs from there up to and including or_moderate (d_moderate), and "larger" is above that. An NA
#' estimate, or an NA std_diff on the "difference" scale, gives an NA band.
#'
#' `narrows` is direction-specific where `band` is not: it counts only narrow_items with OR at or
#' above or_little, since the conclusion concerns generally active people, so an inverse association
#' gets its band but does not count. Every narrow item must be on the "or" scale.
#'
#' `relative_met`, on the koos_sport row when womac_walk is also present, says whether |std_diff| is
#' smaller for koos_sport than for womac_walk. It is NA on every other row.
#'
#' @param contrasts Data frame, one row per measure, with `measure`, `scale`, `estimate`, `std_diff`.
#' @param rule List with `or_little`, `or_moderate`, `d_little`, `d_moderate`, `narrow_items` and
#'   `narrow_min_items`.
#' @return `contrasts` with `band` and `relative_met` added, and attributes `narrows` (at least
#'   narrow_min_items of narrow_items have OR >= or_little), `narrow_count` (how many did) and `narrow_evaluable` (how many had an estimate). Items with no estimate do not count.
apply_divergence_rule <- function(contrasts, rule) {
  for (column in c("measure", "scale", "estimate", "std_diff")) {
    if (!column %in% names(contrasts)) {
      stop("apply_divergence_rule(): contrasts has no column ", column, call. = FALSE)
    }
  }
  for (key in c("or_little", "or_moderate", "d_little", "d_moderate", "narrow_items", "narrow_min_items")) {
    if (is.null(rule[[key]])) stop("apply_divergence_rule(): rule has no ", key, call. = FALSE)
  }
  unknown <- setdiff(contrasts$scale, c("or", "difference"))
  if (length(unknown) || anyNA(contrasts$scale)) {
    stop("apply_divergence_rule(): scale must be 'or' or 'difference', not ",
         paste(unknown, collapse = ", "), call. = FALSE)
  }
  repeated <- unique(contrasts$measure[duplicated(contrasts$measure)])
  if (length(repeated)) {
    stop("apply_divergence_rule(): more than one row for ", paste(repeated, collapse = ", "), call. = FALSE)
  }
  is_or <- contrasts$scale == "or"
  if (any(contrasts$estimate[is_or] < 0, na.rm = TRUE)) {
    stop("apply_divergence_rule(): an odds ratio must be positive", call. = FALSE)
  }

  magnitude <- rep(NA_real_, nrow(contrasts))
  magnitude[is_or] <- pmax(contrasts$estimate[is_or], 1 / contrasts$estimate[is_or])
  magnitude[!is_or] <- abs(contrasts$std_diff[!is_or])
  magnitude[is.na(contrasts$estimate)] <- NA_real_
  little <- ifelse(is_or, rule$or_little, rule$d_little)
  moderate <- ifelse(is_or, rule$or_moderate, rule$d_moderate)
  contrasts$band <- as.character(ifelse(magnitude < little, "little_or_none",
                                        ifelse(magnitude <= moderate, "moderate", "larger")))

  contrasts$relative_met <- NA
  koos <- match("koos_sport", contrasts$measure)
  womac <- match("womac_walk", contrasts$measure)
  if (!is.na(koos) && !is.na(womac)) {
    contrasts$relative_met[koos] <- abs(contrasts$std_diff[koos]) < abs(contrasts$std_diff[womac])
  }

  listed <- contrasts$measure %in% unlist(rule$narrow_items)
  not_or <- contrasts$measure[listed & !is_or]
  if (length(not_or)) {
    stop("apply_divergence_rule(): narrow items must be on the 'or' scale: ",
         paste(not_or, collapse = ", "), call. = FALSE)
  }
  listed <- listed & !is.na(contrasts$estimate)
  count <- sum(contrasts$estimate[listed] >= rule$or_little)
  attr(contrasts, "narrows") <- count >= rule$narrow_min_items
  attr(contrasts, "narrow_count") <- count
  attr(contrasts, "narrow_evaluable") <- sum(listed)
  contrasts
}
