# Comparing groups of people on one outcome: each group against a reference group.

#' Each level of `group` described on `y`: n, and the median with its quartiles (numeric `y`) or
#' the share with its Wilson 95% interval (logical `y`). Missing values of `y` are left out.
group_summaries <- function(y, group) {
  check_groups(y, group)
  do.call(rbind, lapply(levels(group), function(lv) {
    v <- y[!is.na(y) & !is.na(group) & group == lv]
    if (is.logical(y)) {
      w <- if (length(v)) wilson(sum(v), length(v)) else c(estimate = NA_real_, lo = NA_real_, hi = NA_real_)
      data.frame(level = lv, n = length(v), estimate = w[["estimate"]], lo = w[["lo"]], hi = w[["hi"]])
    } else {
      q <- if (length(v)) unname(stats::quantile(v, c(0.5, 0.25, 0.75))) else rep(NA_real_, 3)
      data.frame(level = lv, n = length(v), estimate = q[1], lo = q[2], hi = q[3])
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
#' p-values are adjusted across the levels with stats::p.adjust(method = adjust). A level with no
#' complete case gives NA. Returns one row per non-reference level; `n` and `n_ref` count the
#' level's and the reference's people with `y`, and `adj_n` the adjusted model's complete cases,
#' which span every level (one model for all).
group_contrasts <- function(y, group, covariates = NULL, se = c("boot", "nid"), reps = 1000, seed = 1,
                            adjust = "holm") {
  se <- match.arg(se)
  check_groups(y, group)
  if (!is.null(covariates) && nrow(covariates) != length(y)) {
    stop("group_contrasts(): covariates must have one row per element of y (", length(y), " rows)",
         call. = FALSE)
  }
  binary <- is.logical(y)
  ref <- levels(group)[1]
  others <- levels(group)[-1]
  ok <- !is.na(y) & !is.na(group)
  marks <- vs_reference(y, group, test = if (binary) "fisher" else "wilcoxon", adjust = adjust)
  crude <- do.call(rbind, lapply(others, function(lv) {
    a <- y[ok & group == lv]
    r <- y[ok & group == ref]
    est <- if (!length(a) || !length(r)) c(NA_real_, NA_real_, NA_real_) else if (binary) {
      unname(newcombe_diff(sum(a), length(a), sum(r), length(r)))
    } else unname(hodges_lehmann(a, r))
    data.frame(level = lv, n = length(a), n_ref = length(r), estimate = est[1], lo = est[2], hi = est[3])
  }))
  crude$effect <- if (binary) "risk_difference" else "median_difference"
  crude$p <- marks$p[match(crude$level, marks$level)]
  crude$p_holm <- marks$p_adj[match(crude$level, marks$level)]
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
      if (binary) {
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
  adj$adj_effect <- if (binary) "odds_ratio" else "median_difference"
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
