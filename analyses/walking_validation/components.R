# Step `components`: answer-level sub-analyses (spec amendment 12). PASE item 2's days and hours
# answers, separately and combined into estimated weekly walking, against the device wave of the
# same visit (12a); the 96-month item's amount answers as frequency-restricted walker definitions
# (12b); and the record-level correction factor each definition would bring (12c, descriptive).
A <- oaimodels::assumptions()
visits <- c("06", "08")
weekly <- c(purposeful_week = "purposeful_min", mv_week = "mv_min", light_week = "light_min")
persons <- oaimodels::read_frame(required = c(
  "ID", "walker", "in_lo", "device_walker", "bout_days_per_week",
  "amount_times", "amount_months", "amount_years",
  paste0("pase_days_", visits), paste0("pase_hours_", visits),
  paste0("device_walker_", visits), paste0("bout_days_per_week_", visits),
  as.vector(outer(unname(weekly), visits, paste, sep = "_"))
))
out_dir <- Sys.getenv("OAI_RESULTS_DIR")
reps <- A[["validity.bootstrap_reps"]]
perms <- A[["validity.jt_permutations"]]
seed <- A[["bias.seed"]]
scoring <- A[["pase.walking_scoring"]]
freq_cuts <- A[["components.pase_frequency_cuts"]]
hour_edges <- A[["components.pase_weekly_hours_bins"]]
guideline <- A[["reference.min_bout_minutes_per_week"]]
item_cuts <- list(times = A[["components.item_times_cuts"]], months = A[["components.item_months_cuts"]])
min_cell <- A[["components.min_cell_count"]]
n_codes <- c(times = 3, months = 3, years = 4)
q <- function(x, p) if (any(!is.na(x))) unname(stats::quantile(x, p, na.rm = TRUE)) else NA_real_
# Small or empty selections give NA rather than an error or a misleading p = 1
safe_rho <- function(x, y) {
  n <- sum(stats::complete.cases(x, y))
  if (n < 4) return(c(rho = NA_real_, lo = NA_real_, hi = NA_real_, n = n))
  oaimodels::spearman_ci(x, y)
}
safe_jt <- function(x, group) {
  ok <- !is.na(x) & !is.na(group)
  if (length(unique(group[ok])) < 2) return(NA_real_)
  oaimodels::jonckheere(x[ok], droplevels(group[ok]), permutations = perms, seed = seed)[["p"]]
}
# Between-wave Spearman correlation of a device measure among everyone valid at both waves; for a
# single wave's measure this is its reliability (wave_reliability(r, 0) = r).
between_wave <- function(m) {
  a <- persons[[paste0(m, "_06")]]
  b <- persons[[paste0(m, "_08")]]
  both <- !is.na(a) & !is.na(b)
  if (sum(both) < 4) return(NA_real_)
  stats::cor(a[both], b[both], method = "spearman")
}

pase <- list(); item <- list(); hex <- list()
add <- function(...) pase[[length(pase) + 1]] <<- data.frame(..., stringsAsFactors = FALSE)
add_item <- function(...) item[[length(item) + 1]] <<- data.frame(..., stringsAsFactors = FALSE)
add_rows <- function(adder, base, rows) {
  for (i in seq_len(nrow(rows))) {
    do.call(adder, c(base, list(statistic = rows$measure[i], estimate = rows$estimate[i],
                                lo = rows$lo[i], hi = rows$hi[i], n = rows$n[i])))
  }
}

# 12a: PASE item 2, at each visit with its own device wave
for (v in visits) {
  days <- persons[[paste0("pase_days_", v)]]
  hours <- persons[[paste0("pase_hours_", v)]]
  dw <- persons[[paste0("device_walker_", v)]]
  bout_days <- persons[[paste0("bout_days_per_week_", v)]]
  at <- !is.na(days) & !is.na(dw)  # a PASE answer and a valid device wave at this visit

  # Frequency alone
  freq <- factor(days[at], levels = 0:3)
  shares <- oaimodels::level_shares(dw[at], freq)
  for (i in seq_len(nrow(shares))) {
    add(visit = v, component = "frequency", comparator = "device_walker", level = shares$level[i],
        statistic = "share", estimate = shares$estimate[i], lo = shares$lo[i], hi = shares$hi[i], n = shares$n[i])
    b <- bout_days[at][which(freq == shares$level[i])]
    add(visit = v, component = "frequency", comparator = "bout_days_per_week", level = shares$level[i],
        statistic = "median", estimate = q(b, 0.5), lo = q(b, 0.25), hi = q(b, 0.75), n = sum(!is.na(b)))
  }
  add(visit = v, component = "frequency", comparator = "bout_days_per_week", level = "all",
      statistic = "jt_p", estimate = safe_jt(bout_days[at], freq), lo = NA, hi = NA, n = sum(at))
  rho <- safe_rho(days[at], bout_days[at])
  add(visit = v, component = "frequency", comparator = "bout_days_per_week", level = "all",
      statistic = "rho", estimate = rho[["rho"]], lo = rho[["lo"]], hi = rho[["hi"]], n = rho[["n"]])
  cuts <- oaimodels::cut_classification(days[at], dw[at], freq_cuts, reps = reps, seed = seed)
  for (k in unique(cuts$cut)) {
    add_rows(add, list(visit = v, component = "frequency", comparator = "device_walker", level = paste0("cut", k)),
             cuts[cuts$cut == k, ])
  }

  # Duration alone, among PASE walkers
  walking <- at & days >= 1 & !is.na(hours)
  dur <- factor(hours[walking], levels = 1:4)
  pm <- persons[[paste0("purposeful_min_", v)]][walking]
  for (lv in levels(dur)) {
    x <- pm[which(dur == lv)]
    add(visit = v, component = "duration", comparator = "purposeful_min", level = lv,
        statistic = "median", estimate = q(x, 0.5), lo = q(x, 0.25), hi = q(x, 0.75), n = sum(!is.na(x)))
  }
  add(visit = v, component = "duration", comparator = "purposeful_min", level = "all",
      statistic = "jt_p", estimate = safe_jt(pm, dur), lo = NA, hi = NA, n = sum(walking))
  rho <- safe_rho(hours[walking], pm)
  add(visit = v, component = "duration", comparator = "purposeful_min", level = "all",
      statistic = "rho", estimate = rho[["rho"]], lo = rho[["lo"]], hi = rho[["hi"]], n = rho[["n"]])

  # Combined: estimated weekly walking (days x hours/day at the ledgered midpoints), in min/week
  report_min <- ifelse(is.na(days), NA,
                       ifelse(days == 0, 0, scoring$days[days + 1] * scoring$hours[hours] * 60))
  for (comp in names(weekly)) {
    device_min <- persons[[paste0(weekly[[comp]], "_", v)]] * 7
    ok <- at & !is.na(report_min) & !is.na(device_min)
    reliability <- oaimodels::wave_reliability(between_wave(weekly[[comp]]), 0)
    add(visit = v, component = "weekly", comparator = comp, level = "all", statistic = "reliability",
        estimate = reliability, lo = NA, hi = NA, n = NA)
    for (who in c("all", "pase_walkers")) {
      sel <- ok & (who == "all" | days >= 1)
      rho <- safe_rho(report_min[sel], device_min[sel])
      add(visit = v, component = "weekly", comparator = comp, level = who, statistic = "rho",
          estimate = rho[["rho"]], lo = rho[["lo"]], hi = rho[["hi"]], n = rho[["n"]])
      add(visit = v, component = "weekly", comparator = comp, level = who, statistic = "rho_deattenuated",
          estimate = if (is.na(rho[["rho"]]) || is.na(reliability)) NA else
            oaimodels::deattenuate(rho[["rho"]], reliability_y = reliability),
          lo = NA, hi = NA, n = rho[["n"]])
    }
    bins <- oaimodels::weekly_bins(report_min[ok] / 60, hour_edges)
    for (lv in levels(bins)) {
      x <- device_min[ok][which(bins == lv)]
      add(visit = v, component = "weekly", comparator = comp, level = lv, statistic = "median",
          estimate = q(x, 0.5), lo = q(x, 0.25), hi = q(x, 0.75), n = sum(!is.na(x)))
    }
    add(visit = v, component = "weekly", comparator = comp, level = "all", statistic = "jt_p",
        estimate = safe_jt(device_min[ok], bins), lo = NA, hi = NA, n = sum(ok))
    a <- oaimodels::paired_agreement(report_min[ok], device_min[ok], reps = reps, seed = seed)
    add(visit = v, component = "weekly", comparator = comp, level = "all", statistic = "median_diff",
        estimate = a[["estimate"]], lo = a[["lo"]], hi = a[["hi"]], n = a[["n"]])
    add(visit = v, component = "weekly", comparator = comp, level = "all", statistic = "loa",
        estimate = NA, lo = a[["loa_lo"]], hi = a[["loa_hi"]], n = a[["n"]])
    if (comp == "purposeful_week") {
      self_meets <- report_min[ok] >= guideline
      device_meets <- device_min[ok] >= guideline
      cl <- oaimodels::classification(self_meets, device_meets)
      base <- list(visit = v, component = "weekly", comparator = comp, level = "guideline")
      add_rows(add, base, cl)
      j <- oaimodels::youden_ci(self_meets, device_meets, reps = reps, seed = seed)
      kap <- oaimodels::kappa_ci(self_meets, device_meets, reps = reps, seed = seed)
      add_rows(add, base, data.frame(measure = c("j", "kappa"), estimate = c(j[["estimate"]], kap[["estimate"]]),
                                     lo = c(j[["lo"]], kap[["lo"]]), hi = c(j[["hi"]], kap[["hi"]]),
                                     n = c(j[["n"]], kap[["n"]])))
      cells <- oaimodels::hex_cells((report_min[ok] + device_min[ok]) / 2, report_min[ok] - device_min[ok],
                                    bins = 30, min_count = min_cell)
      if (nrow(cells)) hex[[length(hex) + 1]] <- data.frame(visit = v, cells)
    }
  }
}

# 12b and 12c: the 96-month item's amount answers
samples <- list(validation = rep(TRUE, nrow(persons)), lo_subset = persons$in_lo)
inv <- function(x) ifelse(!is.na(x) & x > 0, 1 / x, NA)
for (sample in names(samples)) {
  s <- samples[[sample]] & !is.na(persons$device_walker) & !is.na(persons$walker)
  for (component in names(n_codes)) {
    level <- oaimodels::answer_levels(persons$walker[s], persons[[paste0("amount_", component)]][s], n_codes[[component]])
    no_band <- sum(persons$walker[s] & is.na(level))
    add_item(sample = sample, component = component, level = "no_band", statistic = "count",
             estimate = no_band, lo = NA, hi = NA, n = no_band)
    shares <- oaimodels::level_shares(persons$device_walker[s], level)
    bd <- persons$bout_days_per_week[s]
    for (i in seq_len(nrow(shares))) {
      add_item(sample = sample, component = component, level = shares$level[i], statistic = "share",
               estimate = shares$estimate[i], lo = shares$lo[i], hi = shares$hi[i], n = shares$n[i])
      b <- bd[which(level == shares$level[i])]
      add_item(sample = sample, component = component, level = shares$level[i], statistic = "median",
               estimate = q(b, 0.5), lo = q(b, 0.25), hi = q(b, 0.75), n = sum(!is.na(b)))
    }
    if (component %in% names(item_cuts)) {
      add_item(sample = sample, component = component, level = "all", statistic = "jt_p",
               estimate = safe_jt(bd, level), lo = NA, hi = NA, n = sum(!is.na(level)))
      # A frequency-restricted walker: a walker whose band is at least k. Non-walkers are code 0
      # (always below the cut); walkers without a band are left out (NA).
      code <- rep(NA_real_, length(level))
      code[which(level == "none")] <- 0
      banded <- which(!is.na(level) & level != "none")
      code[banded] <- as.numeric(as.character(level[banded]))
      cuts <- oaimodels::cut_classification(code, persons$device_walker[s], item_cuts[[component]],
                                            reps = reps, seed = seed)
      for (k in unique(cuts$cut)) {
        add_rows(add_item, list(sample = sample, component = component, level = paste0("cut", k)),
                 cuts[cuts$cut == k, ])
      }
      if (sample == "lo_subset" && component == "times") {
        js <- cuts[cuts$measure == "j", ]
        for (i in seq_len(nrow(js))) {
          add_item(sample = sample, component = component, level = paste0("cut", js$cut[i]),
                   statistic = "correction", estimate = inv(js$estimate[i]), lo = inv(js$hi[i]),
                   hi = inv(js$lo[i]), n = js$n[i])
        }
      }
    }
  }
}

write <- function(rows, name, empty) {
  df <- if (length(rows)) do.call(rbind, rows) else empty
  utils::write.csv(df, file.path(out_dir, name), row.names = FALSE)
}
write(pase, "validity_components_pase.csv", NULL)
write(item, "validity_components_item.csv", NULL)
write(hex, "validity_components_hex.csv",
      data.frame(visit = character(), x = numeric(), y = numeric(), count = integer(), dx = numeric(), dy = numeric()))
cat(sprintf("components: %d PASE rows, %d item rows, %d hexagonal cells\n",
            length(pase), length(item), sum(vapply(hex, nrow, integer(1)))))
