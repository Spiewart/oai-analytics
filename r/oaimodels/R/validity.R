# Measurement-validity statistics for comparing a self-report with a device reference.

#' Hodges-Lehmann shift (x minus y) with its 95% CI (Wilcoxon rank-sum inversion)
hodges_lehmann <- function(x, y) {
  x <- x[!is.na(x)]
  y <- y[!is.na(y)]
  w <- suppressWarnings(stats::wilcox.test(x, y, conf.int = TRUE, exact = FALSE))
  c(estimate = unname(w$estimate), lo = w$conf.int[1], hi = w$conf.int[2])
}

#' Rank-biserial correlation: P(x > y) - P(x < y), ties counting one half
rank_biserial <- function(x, y) {
  x <- x[!is.na(x)]
  y <- y[!is.na(y)]
  r <- rank(c(x, y))
  n1 <- length(x)
  u <- sum(r[seq_len(n1)]) - n1 * (n1 + 1) / 2
  2 * u / (n1 * length(y)) - 1
}

jt_statistic <- function(x, g) {
  levels <- sort(unique(g))
  s <- 0
  for (a in seq_along(levels)) for (b in seq_along(levels)) if (a < b) {
    xa <- x[g == levels[a]]
    xb <- x[g == levels[b]]
    r <- rank(c(xa, xb))
    nb <- length(xb)
    s <- s + sum(r[length(xa) + seq_len(nb)]) - nb * (nb + 1) / 2
  }
  s
}

#' Jonckheere-Terpstra statistic for an increasing trend across ordered groups, with a
#' one-sided permutation p-value
jonckheere <- function(x, group, permutations = 2000, seed = 1) {
  ok <- !is.na(x) & !is.na(group)
  x <- x[ok]
  g <- as.integer(group[ok])
  observed <- jt_statistic(x, g)
  set.seed(seed)
  perm <- replicate(permutations, jt_statistic(sample(x), g))
  c(statistic = observed, p = (1 + sum(perm >= observed)) / (permutations + 1))
}

# Muffle only quantreg's "Solution may be nonunique" warning; any other warning still surfaces.
quiet_nonunique <- function(expr) {
  withCallingHandlers(expr, warning = function(w) {
    if (grepl("nonunique", conditionMessage(w), fixed = TRUE)) invokeRestart("muffleWarning")
  })
}

#' Median (quantile 0.5) regression coefficient for one term, with a 95% CI
median_regression <- function(formula, data, term) {
  if (!requireNamespace("quantreg", quietly = TRUE)) {
    stop("median_regression() needs the quantreg package", call. = FALSE)
  }
  # Non-unique medians are expected with discrete covariates; the returned estimate is one
  # valid solution.
  fit <- quiet_nonunique(quantreg::rq(formula, tau = 0.5, data = data))
  s <- quiet_nonunique(summary(fit, se = "nid"))$coefficients
  if (!term %in% rownames(s)) {
    stop("term ", term, " is not in the model (", paste(rownames(s), collapse = ", "), ")",
         call. = FALSE)
  }
  est <- s[term, "Value"]
  se <- s[term, "Std. Error"]
  c(estimate = est, lo = est - 1.96 * se, hi = est + 1.96 * se)
}

#' Spearman rho with a Bonett-Wright 95% CI
spearman_ci <- function(x, y) {
  ok <- stats::complete.cases(x, y)
  x <- x[ok]
  y <- y[ok]
  n <- length(x)
  rho <- stats::cor(x, y, method = "spearman")
  se <- sqrt((1 + rho^2 / 2) / (n - 3))
  z <- atanh(rho)
  c(rho = rho, lo = tanh(z - 1.96 * se), hi = tanh(z + 1.96 * se), n = n)
}

#' A correlation corrected for unreliability, capped at +/-1
deattenuate <- function(rho, reliability_x = 1, reliability_y = 1) {
  pmax(pmin(rho / sqrt(reliability_x * reliability_y), 1), -1)
}

#' Reliability of a person's mean over one or two waves, from the between-wave correlation r
#' (the reliability of a single wave) and the share of people with two waves: the person-level
#' signal variance over signal plus the average error variance of the mean,
#' r / (r + (1 - r) * (1 - share_two_waves / 2)). It equals r with no second waves and the
#' Spearman-Brown value 2r / (1 + r) when everyone has two.
wave_reliability <- function(r, share_two_waves) {
  r / (r + (1 - r) * (1 - share_two_waves / 2))
}

#' Wilson 95% interval for k successes of n (NA when n is 0)
wilson <- function(k, n) {
  if (n == 0) return(c(estimate = NA_real_, lo = NA_real_, hi = NA_real_))
  p <- k / n
  z <- 1.96
  d <- 1 + z^2 / n
  centre <- (p + z^2 / (2 * n)) / d
  half <- z * sqrt(p * (1 - p) / n + z^2 / (4 * n^2)) / d
  c(estimate = p, lo = centre - half, hi = centre + half)
}

#' Difference between two proportions, k1/n1 minus k0/n0, with Newcombe's hybrid-score 95% CI
#' (method 10, built from the two Wilson intervals); NA when either denominator is 0
newcombe_diff <- function(k1, n1, k0, n0) {
  if (n1 == 0 || n0 == 0) return(c(estimate = NA_real_, lo = NA_real_, hi = NA_real_))
  a <- wilson(k1, n1)
  b <- wilson(k0, n0)
  diff <- a[["estimate"]] - b[["estimate"]]
  c(estimate = diff,
    lo = diff - sqrt((a[["estimate"]] - a[["lo"]])^2 + (b[["hi"]] - b[["estimate"]])^2),
    hi = diff + sqrt((a[["hi"]] - a[["estimate"]])^2 + (b[["estimate"]] - b[["lo"]])^2))
}

#' Sensitivity, specificity, PPV and NPV of a binary test against a binary reference
classification <- function(test, reference) {
  ok <- !is.na(test) & !is.na(reference)
  t <- as.logical(test[ok])
  r <- as.logical(reference[ok])
  tp <- sum(t & r)
  fn <- sum(!t & r)
  fp <- sum(t & !r)
  tn <- sum(!t & !r)
  counts <- list(se = c(tp, tp + fn), sp = c(tn, tn + fp), ppv = c(tp, tp + fp), npv = c(tn, tn + fn))
  do.call(rbind, lapply(names(counts), function(m) {
    k <- counts[[m]][1]
    n <- counts[[m]][2]
    w <- wilson(k, n)
    data.frame(measure = m, estimate = w[["estimate"]], lo = w[["lo"]], hi = w[["hi"]], k = k, n = n)
  }))
}

#' AUC of a score for a binary reference (Mann-Whitney), percentile bootstrap 95% CI
auc_ci <- function(score, reference, reps = 1000, seed = 1) {
  ok <- !is.na(score) & !is.na(reference)
  s <- score[ok]
  r <- as.logical(reference[ok])
  auc <- function(s, r) {
    n1 <- sum(r)
    n0 <- sum(!r)
    if (n1 == 0 || n0 == 0) return(NA_real_)
    (sum(rank(s)[r]) - n1 * (n1 + 1) / 2) / (n1 * n0)
  }
  set.seed(seed)
  boots <- replicate(reps, {
    i <- sample.int(length(s), replace = TRUE)
    auc(s[i], r[i])
  })
  q <- stats::quantile(boots, c(0.025, 0.975), na.rm = TRUE, names = FALSE)
  c(estimate = auc(s, r), lo = q[1], hi = q[2])
}

#' Sensitivity and specificity per stratum, each with its difference from the reference
#' stratum (the first level of sort(unique(stratum)); Newcombe 95% CI, NA for the reference rows
#' and wherever either estimate is NA), and a likelihood-ratio p-value for whether each differs
#' across strata (NA when it cannot be tested)
classification_by_stratum <- function(test, reference, stratum) {
  ok <- !is.na(test) & !is.na(reference) & !is.na(stratum)
  t <- as.logical(test[ok])
  r <- as.logical(reference[ok])
  s <- as.character(stratum[ok])
  rows <- lapply(sort(unique(s)), function(level) {
    cl <- classification(t[s == level], r[s == level])
    cl$stratum <- level
    cl[cl$measure %in% c("se", "sp"), ]
  })
  out <- do.call(rbind, rows)
  reference_level <- sort(unique(s))[1]
  diffs <- t(vapply(seq_len(nrow(out)), function(i) {
    ref <- out[out$measure == out$measure[i] & out$stratum == reference_level, ]
    if (out$stratum[i] == reference_level) return(c(NA_real_, NA_real_, NA_real_))
    unname(newcombe_diff(out$k[i], out$n[i], ref$k, ref$n))
  }, numeric(3)))
  out$difference <- diffs[, 1]
  out$difference_lo <- diffs[, 2]
  out$difference_hi <- diffs[, 3]
  lr_p <- function(subset) {
    correct <- (t == r)[subset]
    st <- factor(s[subset])
    if (nlevels(st) < 2 || length(unique(correct)) < 2) return(NA_real_)
    full <- stats::glm(correct ~ st, family = stats::binomial)
    null <- stats::glm(correct ~ 1, family = stats::binomial)
    stats::anova(null, full, test = "LRT")[2, "Pr(>Chi)"]
  }
  out$p_differs <- ifelse(out$measure == "se", lr_p(r), lr_p(!r))
  rownames(out) <- NULL
  out
}
