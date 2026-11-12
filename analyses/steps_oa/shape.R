# Shape helpers for steps_oa: Harrell's restricted cubic spline (as Hmisc::rcspline.eval with
# norm = 2) and the curve of odds ratios it implies against a reference value.

# Restricted cubic spline basis for k knots: k - 1 columns, x itself and k - 2 nonlinear terms.
# Each nonlinear term is 0 for x at or below the first knot and linear beyond the last; it is
# divided by (t_k - t_1)^2 so it stays on the scale of x.
rcs_basis <- function(x, knots) {
  t <- sort(as.numeric(knots))
  k <- length(t)
  if (k < 3) stop("rcs_basis(): needs at least 3 knots", call. = FALSE)
  pos3 <- function(u) pmax(u, 0)^3
  out <- matrix(x, ncol = 1)
  for (j in seq_len(k - 2)) {
    term <- pos3(x - t[j]) -
      pos3(x - t[k - 1]) * (t[k] - t[j]) / (t[k] - t[k - 1]) +
      pos3(x - t[k]) * (t[k - 1] - t[j]) / (t[k] - t[k - 1])
    out <- cbind(out, term / (t[k] - t[1])^2)
  }
  colnames(out) <- paste0("rcs", seq_len(k - 1))
  out
}

# Odds ratios (exp of the linear predictor difference) at `at` against `ref`, with 95% CIs from
# the covariance `V` of the spline coefficients `b` (in rcs_basis column order).
rcs_curve <- function(b, V, knots, at, ref) {
  d <- rcs_basis(at, knots) - matrix(rcs_basis(ref, knots), nrow = length(at), ncol = length(b),
                                     byrow = TRUE)
  eta <- as.vector(d %*% b)
  se <- sqrt(pmax(rowSums((d %*% V) * d), 0))
  data.frame(or = exp(eta), lo = exp(eta - 1.96 * se), hi = exp(eta + 1.96 * se))
}
