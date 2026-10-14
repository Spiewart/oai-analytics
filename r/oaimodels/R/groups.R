# Comparing groups of people on one outcome: each group against a reference group.

#' Each level of `group` described on `y`: n, and the median with its quartiles (numeric `y`) or
#' the share with its Wilson 95% interval (logical `y`); for a numeric `y` also the mean with its
#' t-based 95% CI (mean, mean_lo, mean_hi; NA for a share). Missing values of `y` are left out.
group_summaries <- function(y, group) {
  check_groups(y, group)
  do.call(rbind, lapply(levels(group), function(lv) {
    v <- y[!is.na(y) & !is.na(group) & group == lv]
    if (is.logical(y)) {
      w <- if (length(v)) wilson(sum(v), length(v)) else c(estimate = NA_real_, lo = NA_real_, hi = NA_real_)
      data.frame(level = lv, n = length(v), estimate = w[["estimate"]], lo = w[["lo"]], hi = w[["hi"]],
                 mean = NA_real_, mean_lo = NA_real_, mean_hi = NA_real_)
    } else {
      q <- if (length(v)) unname(stats::quantile(v, c(0.5, 0.25, 0.75))) else rep(NA_real_, 3)
      m <- if (length(v) > 1) c(mean(v), stats::t.test(v)$conf.int) else c(if (length(v)) mean(v) else NA_real_, NA_real_, NA_real_)
      data.frame(level = lv, n = length(v), estimate = q[1], lo = q[2], hi = q[3],
                 mean = m[1], mean_lo = m[2], mean_hi = m[3])
    }
  }))
}

#' Each level of `group` against its first level (the reference) on `y`.
#'
#' Crude: for a numeric `y` the Hodges-Lehmann median difference with its 95% CI and a Wilcoxon
#' rank-sum p-value; for a logical `y` the risk difference with Newcombe's 95% CI and a Fisher
#' exact p-value. Adjusted, when `covariates` (a data.frame, one row per element of `y`) is given:
#' for a numeric `y` the group's coefficient in a median regression on group and the covariates
#' (one fit for all levels; `se` as in median_regression(), Wald p from that SE); for a logical
#' `y` the odds ratio from a logistic regression on the same terms, with its Wald 95% CI and p.
#' With `estimator = "mean"` (numeric `y` only) both contrasts compare means instead: the crude
#' difference with Welch's 95% CI and p (stats::t.test), the adjusted one a linear regression's
#' coefficient with its 95% CI and p.
#' p-values are adjusted across the levels with stats::p.adjust(method = adjust). A level with no
#' complete case gives NA. Returns one row per non-reference level; `n` and `n_ref` count the
#' level's and the reference's people with `y`, and `adj_n` the adjusted model's complete cases,
#' which span every level (one model for all).
group_contrasts <- function(y, group, covariates = NULL, se = c("boot", "nid"), reps = 1000, seed = 1,
                            adjust = "holm", estimator = c("median", "mean")) {
  se <- match.arg(se)
  estimator <- match.arg(estimator)
  check_groups(y, group)
  if (estimator == "mean" && !is.numeric(y)) {
    stop("group_contrasts(): estimator = 'mean' needs a numeric y", call. = FALSE)
  }
  means <- estimator == "mean"
  if (!is.null(covariates) && nrow(covariates) != length(y)) {
    stop("group_contrasts(): covariates must have one row per element of y (", length(y), " rows)",
         call. = FALSE)
  }
  binary <- is.logical(y)
  ref <- levels(group)[1]
  others <- levels(group)[-1]
  ok <- !is.na(y) & !is.na(group)
  crude <- do.call(rbind, lapply(others, function(lv) {
    a <- y[ok & group == lv]
    r <- y[ok & group == ref]
    if (means) {
      w <- if (length(a) > 1 && length(r) > 1) stats::t.test(a, r) else NULL
      est <- if (is.null(w)) rep(NA_real_, 4) else c(mean(a) - mean(r), w$conf.int, w$p.value)
    } else {
      est <- if (!length(a) || !length(r)) c(NA_real_, NA_real_, NA_real_) else if (binary) {
        unname(newcombe_diff(sum(a), length(a), sum(r), length(r)))
      } else unname(hodges_lehmann(a, r))
      est <- c(est, NA_real_)
    }
    data.frame(level = lv, n = length(a), n_ref = length(r), estimate = est[1], lo = est[2], hi = est[3],
               p = est[4])
  }))
  crude$effect <- if (means) "mean_difference" else if (binary) "risk_difference" else "median_difference"
  if (means) {
    crude$p_holm <- stats::p.adjust(crude$p, method = adjust)
  } else {
    marks <- vs_reference(y, group, test = if (binary) "fisher" else "wilcoxon", adjust = adjust)
    crude$p <- marks$p[match(crude$level, marks$level)]
    crude$p_holm <- marks$p_adj[match(crude$level, marks$level)]
  }
  adj <- data.frame(level = others, adj_estimate = NA_real_, adj_lo = NA_real_, adj_hi = NA_real_,
                    adj_p = NA_real_, adj_n = NA_integer_)
  if (!is.null(covariates)) {
    data <- data.frame(y = y, group = group, covariates)
    data <- data[stats::complete.cases(data), , drop = FALSE]
    present <- others[others %in% data$group]
    data$group <- factor(data$group, levels = c(ref, present))
    form <- stats::as.formula(paste("y ~ group +", paste(names(covariates), collapse = " + ")))
    if (length(present) && ref %in% data$group) {
      terms <- paste0("group", present)
      if (means) {
        fit <- stats::lm(form, data = data)
        s <- summary(fit)$coefficients[terms, , drop = FALSE]
        ci <- stats::confint(fit)[terms, , drop = FALSE]
        rows <- data.frame(level = present, adj_estimate = s[, 1], adj_lo = ci[, 1], adj_hi = ci[, 2],
                           adj_p = s[, 4], adj_n = nrow(data))
      } else if (binary) {
        fit <- stats::glm(form, family = stats::binomial(), data = data)
        s <- summary(fit)$coefficients[terms, , drop = FALSE]
        rows <- data.frame(level = present, adj_estimate = exp(s[, 1]), adj_lo = exp(s[, 1] - 1.96 * s[, 2]),
                           adj_hi = exp(s[, 1] + 1.96 * s[, 2]), adj_p = s[, 4], adj_n = nrow(data))
      } else {
        m <- median_regression_terms(form, data, terms, se = se, reps = reps, seed = seed)
        rows <- data.frame(level = present, adj_estimate = m$estimate, adj_lo = m$lo, adj_hi = m$hi,
                           adj_p = ifelse(m$se > 0, 2 * stats::pnorm(-abs(m$estimate / m$se)), NA_real_),
                           adj_n = m$n)
      }
      adj[match(rows$level, adj$level), names(rows)[-1]] <- rows[, -1]
    }
  }
  adj$adj_effect <- if (means) "mean_difference" else if (binary) "odds_ratio" else "median_difference"
  adj$adj_p_holm <- stats::p.adjust(adj$adj_p, method = adjust)
  out <- merge(crude, adj, by = "level", sort = FALSE)
  out <- out[match(others, out$level), , drop = FALSE]
  rownames(out) <- NULL
  out$n <- as.integer(out$n)
  out$n_ref <- as.integer(out$n_ref)
  out
}

check_groups <- function(y, group) {
  if (!is.factor(group)) stop("group must be a factor (its first level is the reference)", call. = FALSE)
  if (!(is.numeric(y) || is.logical(y))) stop("y must be numeric or logical", call. = FALSE)
  if (length(y) != length(group)) stop("y and group must have the same length", call. = FALSE)
}
