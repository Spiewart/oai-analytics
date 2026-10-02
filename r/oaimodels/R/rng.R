# Seeded work that leaves the caller's random-number stream alone.

# Evaluate `expr`, then put the global random-number state back as it was: the caller's
# .Random.seed is restored, or removed again if the caller had none.
preserve_rng <- function(expr) {
  had_seed <- exists(".Random.seed", envir = globalenv(), inherits = FALSE)
  if (had_seed) saved <- get(".Random.seed", envir = globalenv(), inherits = FALSE)
  on.exit({
    if (had_seed) {
      assign(".Random.seed", saved, envir = globalenv())
    } else if (exists(".Random.seed", envir = globalenv(), inherits = FALSE)) {
      rm(".Random.seed", envir = globalenv())
    }
  })
  expr
}

# Evaluate `expr` after set.seed(seed), without changing the caller's random-number state.
with_seed <- function(seed, expr) {
  preserve_rng({
    set.seed(seed)
    expr
  })
}
