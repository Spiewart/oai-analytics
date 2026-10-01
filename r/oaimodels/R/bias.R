# Probabilistic bias analysis for a misclassified binary person-level exposure
# (Lash, Fox & MacLehose, record-level method). Reclassification always happens within outcome
# strata; "non-differential" shares one Se/Sp draw across strata, "differential" draws per stratum.

#' Beta(k + 1, n - k + 1) shapes for a proportion observed as k of n (uniform prior)
beta_shapes <- function(k, n) c(shape1 = k + 1, shape2 = n - k + 1)

#' True exposure prevalence implied by the observed prevalence, sensitivity and specificity
true_prevalence <- function(p_obs, se, sp) (p_obs + sp - 1) / (se + sp - 1)

#' P(truly exposed | classified exposed) and P(truly exposed | classified unexposed)
reclass_probs <- function(p_obs, se, sp) {
  p <- true_prevalence(p_obs, se, sp)
  list(p_true = p, ppv = se * p / p_obs, fom = (1 - se) * p / (1 - p_obs))
}

#' Corrected odds ratio from a 2x2 table with outcome-specific classification
#' a = exposed cases, b = unexposed cases, c = exposed non-cases, d = unexposed non-cases
correct_or_2x2 <- function(a, b, c, d, se_case, sp_case, se_ctrl = se_case, sp_ctrl = sp_case) {
  # Se + Sp <= 1 in either outcome stratum is worse than chance: the draw is discarded
  if (!isTRUE(all(se_case + sp_case > 1)) || !isTRUE(all(se_ctrl + sp_ctrl > 1))) return(NA_real_)
  n1 <- a + b
  n0 <- c + d
  A <- (a - (1 - sp_case) * n1) / (se_case + sp_case - 1)
  C <- (c - (1 - sp_ctrl) * n0) / (se_ctrl + sp_ctrl - 1)
  B <- n1 - A
  D <- n0 - C
  if (!all(is.finite(c(A, B, C, D))) || any(c(A, B, C, D) <= 0)) return(NA_real_)
  (A * D) / (B * C)
}

#' One reclassification of persons$observed within persons$stratum; NULL if impossible
#'
#' Probabilities within `tolerance` of 0 or 1 are rounding (Se = Sp = 1 gives ppv = 1 + 2.2e-16
#' for most proportions) and are clamped into [0, 1]; the true prevalence must lie strictly
#' inside (0, 1) up to the same tolerance, and Se + Sp <= 1 is always impossible.
reclassify <- function(persons, se, sp, tolerance = 1e-12) {
  out <- logical(nrow(persons))
  for (s in unique(persons$stratum)) {
    i <- persons$stratum == s
    p_obs <- mean(persons$observed[i])
    pr <- reclass_probs(p_obs, se[[s]], sp[[s]])
    probs <- c(pr$p_true, pr$ppv, pr$fom)
    if (se[[s]] + sp[[s]] <= 1 || !all(is.finite(probs)) ||
        pr$p_true <= tolerance || pr$p_true >= 1 - tolerance ||
        any(probs[2:3] < -tolerance | probs[2:3] > 1 + tolerance)) {
      return(NULL)
    }
    ppv <- min(max(pr$ppv, 0), 1)
    fom <- min(max(pr$fom, 0), 1)
    u <- stats::runif(sum(i))
    out[i] <- ifelse(persons$observed[i], u < ppv, u < fom)
  }
  out
}

#' Record-level probabilistic bias analysis
#' @param persons data.frame(ID, observed, stratum)
#' @param knees rows passed to `fit` after `exposure` is replaced by each draw (matched by ID)
#' @param fit function(knees) -> c(log_or, se)
#' @param priors Beta shapes (stratum, se1, se2, sp1, sp2) or fixed values (stratum, se, sp)
#' @param differential One draw per stratum (TRUE) or one shared draw (FALSE; one prior row)
pba <- function(persons, knees, fit, priors, differential = FALSE, iterations = 1000, seed = 1,
                cores = 1, exposure = "walker") {
  strata <- unique(persons$stratum)
  fixed <- all(c("se", "sp") %in% names(priors))
  if (differential) {
    missing <- setdiff(strata, priors$stratum)
    if (length(missing)) stop("priors lack strata: ", paste(missing, collapse = ", "), call. = FALSE)
  } else if (nrow(priors) != 1) {
    stop("non-differential pba() takes one prior row", call. = FALSE)
  }
  draw <- function(rows) {
    if (fixed) return(list(se = rows$se, sp = rows$sp))
    list(se = stats::rbeta(nrow(rows), rows$se1, rows$se2),
         sp = stats::rbeta(nrow(rows), rows$sp1, rows$sp2))
  }
  one <- function(i) {
    set.seed(seed + i)
    if (differential) {
      rows <- priors[match(strata, priors$stratum), ]
      d <- draw(rows)
      se <- stats::setNames(d$se, strata)
      sp <- stats::setNames(d$sp, strata)
    } else {
      d <- draw(priors)
      se <- stats::setNames(rep(d$se, length(strata)), strata)
      sp <- stats::setNames(rep(d$sp, length(strata)), strata)
    }
    truth <- reclassify(persons, se, sp)
    if (is.null(truth)) return(discarded_row(i))
    knees[[exposure]] <- truth[match(knees$ID, persons$ID)]
    # A draw just inside the feasibility edge can reclassify every fitted knee to one level, and
    # no model can estimate an exposure effect from a constant exposure
    if (length(unique(knees[[exposure]])) < 2) return(discarded_row(i))
    est <- fit(knees)
    if (!is.finite(est[["log_or"]]) || !is.finite(est[["se"]])) return(discarded_row(i))
    data.frame(iter = i, log_or = est[["log_or"]], se = est[["se"]],
               log_or_total = stats::rnorm(1, est[["log_or"]], est[["se"]]), discarded = FALSE)
  }
  runs <- if (cores > 1) {
    parallel::mclapply(seq_len(iterations), one, mc.cores = cores)
  } else {
    lapply(seq_len(iterations), one)
  }
  failed <- vapply(runs, inherits, logical(1), what = "try-error")
  if (any(failed)) stop("pba() iteration failed: ", runs[[which(failed)[1]]], call. = FALSE)
  bind_runs(runs, iterations)
}

# The row recorded for an iteration that could not produce an estimate
discarded_row <- function(i) {
  data.frame(iter = i, log_or = NA_real_, se = NA_real_, log_or_total = NA_real_, discarded = TRUE)
}

# Row-bind the per-iteration results, refusing to return fewer iterations than were requested
# (a killed parallel worker returns NULL for its jobs, which rbind would silently drop).
bind_runs <- function(runs, iterations) {
  lost <- vapply(runs, is.null, logical(1))
  if (any(lost)) {
    stop("pba() lost ", sum(lost), " of ", iterations, " iterations ",
         "(a parallel worker was probably killed); rerun with fewer cores or more memory",
         call. = FALSE)
  }
  out <- do.call(rbind, runs)
  if (is.null(out) || nrow(out) != iterations) {
    stop("pba() returned ", if (is.null(out)) 0L else nrow(out), " rows for ", iterations,
         " iterations", call. = FALSE)
  }
  out
}

#' Median bias-adjusted OR with 95% simulation intervals, the share of iterations keeping the
#' published conclusion (same direction; CI excluding 1 when `significant`), and discards
summarise_pba <- function(draws, direction = NA, significant = NA) {
  kept <- draws[!draws$discarded, ]
  q <- function(x) {
    if (!length(x)) return(c(NA_real_, NA_real_, NA_real_))
    exp(stats::quantile(x, c(0.5, 0.025, 0.975), names = FALSE))
  }
  s <- q(kept$log_or)
  t <- q(kept$log_or_total)
  holds <- if (is.na(direction) || !nrow(kept)) NA_real_ else {
    same <- sign(kept$log_or) == direction
    sig <- if (isTRUE(significant)) abs(kept$log_or / kept$se) > 1.96 else TRUE
    mean(same & sig)
  }
  data.frame(or = s[1], lo_sys = s[2], hi_sys = s[3], lo_total = t[2], hi_total = t[3],
             conclusion_share = holds, discarded = mean(draws$discarded), n = nrow(draws))
}
