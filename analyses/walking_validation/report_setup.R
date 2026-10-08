# Shared by the walking-validation documents (report.qmd, clinical.qmd, abstract.qmd): the run's
# results, the assumption accessor, number formatters, name maps, result lookups and the plain
# definitions of the walker, the device walker and the PASE walker. Source it first; nothing here
# prints.

run <- oaireport::load_results()$default
# A true minus sign for negatives, as oaireport::fmt_ci prints them
num <- function(x, digits = 2) sub("^-", "−", formatC(x, format = "f", digits = digits, big.mark = ","))
count <- function(x) formatC(x, format = "d", big.mark = ",")
pct <- function(x, digits = 0) paste0(num(100 * x, digits), "%")
pct_range <- function(x) {
  lo <- num(100 * min(x), 0)
  hi <- num(100 * max(x), 0)
  if (lo == hi) sprintf("%s%%", lo) else sprintf("%s–%s%%", lo, hi)
}
named <- function(key, map) ifelse(key %in% names(map), map[key], key)
# Odds ratios: "–" when every draw was discarded, "<0.01" for limits that collapse toward 0
or_text <- function(x) ifelse(is.na(x), "–", ifelse(x < 0.01, "<0.01", num(x)))
or_interval <- function(or, lo, hi) {
  ifelse(is.na(or), "–", sprintf("%s (%s–%s)", or_text(or), or_text(lo), or_text(hi)))
}
# Device measures: counts/day without decimals, minutes/day to 2 decimals
dnum <- function(x, measure) ifelse(measure == "counts_per_day", num(x, 0), num(x))
# An estimate with its 95% interval, in the device measure's digits (counts/day without decimals)
dnum_ci <- function(est, lo, hi, measure) {
  ifelse(measure == "counts_per_day", oaireport::fmt_ci(est, lo, hi, 0), oaireport::fmt_ci(est, lo, hi, 2))
}
class_names <- c(se = "Se", sp = "Sp", ppv = "PPV", npv = "NPV", auc = "AUC")  # as in the legends
measure_names <- c(purposeful_min = "Purposeful-bout min/day", counts_per_day = "Counts/day",
                   light_min = "Light min/day")
outcome_names <- c(new_pain = "New frequent knee pain", kl_worse = "KL grade worsening",
                   jsn_worse = "Medial JSN worsening", improved_pain = "Resolution of frequent knee pain")
model_names <- c(or_unadj = "Unadjusted", or_adj = "Adjusted")
sample_names <- c(validation = "Validation", lo_subset = "Lo 2022 subset")
wave_names <- c(`06` = "48 months", `08` = "72 months", `10` = "96 months")
wave <- function(x) named(sprintf("%02d", as.integer(x)), wave_names)
assumption <- function(key) run$assumptions$assumptions[[key]]$value
cls <- run$validity_classification
pick <- function(sample, measure, col = "estimate") cls[[col]][cls$sample == sample & cls$measure == measure]
youden <- function(sample) pick(sample, "se") + pick(sample, "sp") - 1
# Legends under the tables and figures, in plain words. Every number comes from the run's
# assumptions or results, so a variant run is described as it ran.
fmt <- function(x) format(x, trim = TRUE, big.mark = ",")
cap1 <- function(x) paste0(toupper(substr(x, 1, 1)), substring(x, 2))
combination <- assumption("device.wave_combination")
waves_at <- if (combination == "mean") "48 or 72 months" else wave(combination)
averaged <- if (combination == "mean") "averaged over a person's valid waves" else
  sprintf("at the %s wave", sub(" months", "-month", wave(combination)))
cutpoint <- assumption("device.mv_cutpoint")
purposeful_minutes <- fmt(assumption("device.purposeful_bout_minutes"))
valid_day <- sprintf("a valid day has at least %s wear hours and a valid wave at least %s valid days",
                     fmt(assumption("device.valid_day_hours")), fmt(assumption("device.min_valid_days")))

# The walking item, defined in full once, in the first legend that uses it
yes_without <- assumption("exposure.yes_without_amount_as")
item_def <- switch(yes_without,
  `non-walker` = "Walker: answered yes to the 96-month question on walking for exercise (at least 20 minutes a day, at least 10 times, at age 50 or older; V10WLKAR4) and gave at least one amount (years, months per year or times per month); non-walker: answered no, or yes with no amount.",
  walker = "Walker: answered yes to the 96-month question on walking for exercise (at least 20 minutes a day, at least 10 times, at age 50 or older; V10WLKAR4), with or without an amount; non-walker: answered no.",
  exclude = "Walker: answered yes to the 96-month question on walking for exercise (at least 20 minutes a day, at least 10 times, at age 50 or older; V10WLKAR4) and gave at least one amount (years, months per year or times per month); non-walker: answered no (a yes with no amount is left out).",
  stop("unknown exposure.yes_without_amount_as: ", yes_without))
# The walkers with no lifetime-sessions score (an amount item is missing); a "yes" with no
# amount at all is one of them only under walker coding
no_amount_group <- if (yes_without == "walker") {
  "walkers who gave no amount or only some of the amount items"
} else "walkers who answered some but not all of the amount items"

# The device reference standard, defined in full once (Classification)
walker_rule <- assumption("reference.walker_rule")
rule_short <- switch(walker_rule,
  bout_days = sprintf("on average at least %s days a week with a purposeful bout", fmt(assumption("reference.min_bout_days_per_week"))),
  any_bout = "at least one purposeful bout",
  bout_minutes = sprintf("on average at least %s minutes a week in purposeful bouts", fmt(assumption("reference.min_bout_minutes_per_week"))),
  stop("unknown reference.walker_rule: ", walker_rule))
device_def <- sprintf("Device walker (the reference standard): defined from the accelerometer alone (ActiGraph GT1M, %s), as a person who shows %s; a purposeful bout is at least %s minutes of moderate-to-vigorous activity.",
                      waves_at, rule_short, purposeful_minutes)
per_week <- switch(walker_rule,
  bout_days = sprintf("Days a week = the share of a person's first %s valid days with a bout × 7, %s. ", fmt(assumption("device.max_valid_days")), averaged),
  bout_minutes = sprintf("Minutes a week = purposeful-bout minutes per valid day × 7, %s. ", averaged),
  "")
device_detail <- sprintf("A bout starts when %s of %s minutes reach %s counts/min and ends when %s minutes in the window fall below it. %s%s.",
                         fmt(assumption("device.bout_need")), fmt(assumption("device.bout_window")), fmt(cutpoint),
                         fmt(assumption("device.bout_stop_below")), per_week, cap1(valid_day))
measures_def <- sprintf("Device measures are averages per valid day: purposeful-bout min/day (minutes inside purposeful bouts), counts/day (total activity counts) and light min/day (minutes at %s–%s counts/min).",
                        fmt(assumption("device.light_floor")), fmt(cutpoint - 1))

# Plain-language definitions (clinical.qmd, abstract.qmd)
# The walker by the question, as the run codes a yes without an amount (as item_def)
walker_plain <- switch(yes_without,
  `non-walker` = , exclude = "answered yes to the 96-month question “walked for exercise since age 50” (at least 20 minutes a day, at least 10 times) and said how much they walk (years, months a year or times a month).",
  walker = "answered yes to the 96-month question “walked for exercise since age 50” (at least 20 minutes a day, at least 10 times), whether or not they said how much they walk.",
  stop("unknown exposure.yes_without_amount_as: ", yes_without, call. = FALSE))
nonwalker_plain <- switch(yes_without,
  `non-walker` = "said no, or said yes without saying how much they walk",
  walker = "said no",
  exclude = "said no (a yes without saying how much they walk is left out)",
  stop("unknown exposure.yes_without_amount_as: ", yes_without, call. = FALSE))
# The device rule and the valid-day rule in plain words, built from the assumptions
bout_plain <- sprintf("%s+ minutes of moderate-to-vigorous activity", purposeful_minutes)
rule_plain <- switch(walker_rule,
  bout_days = sprintf("on average at least %s days a week with a bout of %s", fmt(assumption("reference.min_bout_days_per_week")), bout_plain),
  any_bout = sprintf("at least one bout of %s", bout_plain),
  bout_minutes = sprintf("on average at least %s minutes a week in bouts of %s", fmt(assumption("reference.min_bout_minutes_per_week")), bout_plain),
  stop("unknown reference.walker_rule: ", walker_rule, call. = FALSE))
valid_day_plain <- sprintf("a valid day has at least %s wear hours and a usable visit at least %s valid days",
                           fmt(assumption("device.valid_day_hours")), fmt(assumption("device.min_valid_days")))

# PASE
pase_threshold <- assumption("pase.walker_threshold")
pase_def <- if (pase_threshold == 0) {
  "PASE (Physical Activity Scale for the Elderly) walker: a PASE walking subscore above 0, i.e. any walking outside the home in the past 7 days (PASE item 2), at that visit."
} else {
  sprintf("PASE (Physical Activity Scale for the Elderly) walker: a PASE walking subscore above %s (PASE item 2, walking outside the home in the past 7 days) at that visit.", fmt(pase_threshold))
}

# Models and tests
reps_text <- if (assumption("validity.median_regression_se") == "boot") {
  sprintf("bootstrap 95%% CI, %s resamples", fmt(assumption("validity.bootstrap_reps")))
} else "95% CI from sandwich standard errors"
adjusted_def <- sprintf("median regression adjusting for age, sex and body-mass index (BMI) (%s)", reps_text)

combined_text <- if (combination == "mean") "the mean over each participant's valid device waves" else
  sprintf("the %s device wave", sub(" months", "-month", wave(combination)))
pairing <- assumption("pase.device_pairing")

jt_b <- assumption("validity.jt_permutations")
jt_floor <- 1 / (jt_b + 1)  # smallest attainable permutation p-value
round_up <- function(x, digits = 2) {  # round up to `digits` significant digits, so "<=" stays true
  if (x <= 0) return(0)
  step <- 10^(floor(log10(x)) - digits + 1)
  ceiling(x / step - 1e-9) * step
}

cp <- run$validity_components_pase
ci <- run$validity_components_item
hx <- run$validity_components_hex
cp$visit <- sprintf("%02d", as.integer(cp$visit))
if (nrow(hx)) hx$visit <- sprintf("%02d", as.integer(hx$visit))
answer_labels <- lapply(assumption("components.answer_labels"), unlist)
# Missing values show "–", never "NA"
num_na <- function(x, digits = 2) ifelse(is.na(x), "–", num(x, digits))
count_na <- function(x) ifelse(is.na(x), "–", count(x))
# Permutation p-values, floored as in the dose–response table (jt_floor, round_up)
comp_p <- function(p) {
  ifelse(is.na(p), "–", ifelse(p <= jt_floor * (1 + 1e-9), paste0("≤\u00a0", formatC(round_up(jt_floor), format = "g", digits = 2)),
                              formatC(p, format = "g", digits = 2)))
}
cp_get <- function(v, component, comparator, level, statistic, col = "estimate") {
  x <- cp[cp$visit == v & cp$component == component & cp$comparator == comparator &
          cp$level == level & cp$statistic == statistic, col]
  if (length(x) == 1) x else NA
}
ci_get <- function(sample, component, level, statistic, col = "estimate") {
  x <- ci[ci$sample == sample & ci$component == component & ci$level == level & ci$statistic == statistic, col]
  if (length(x) == 1) x else NA
}
est_ci <- function(est, lo, hi, digits = 2) oaireport::fmt_ci(est, lo, hi, digits)
pct_ci <- function(est, lo, hi) {
  ifelse(is.na(est), "–", sprintf("%s (%s–%s)", num(100 * est, 0), num(100 * lo, 0), num(100 * hi, 0)))
}
med_iqr <- function(m, lo, hi, digits = 1) ifelse(is.na(m), "–", sprintf("%s (%s–%s)", num(m, digits), num(lo, digits), num(hi, digits)))
comp_visits <- c("06", "08")
boot_text <- sprintf("person-level bootstrap 95%% CI, %s resamples", fmt(assumption("validity.bootstrap_reps")))
# The device reference and the PASE walker follow pase.device_pairing and pase.walker_threshold,
# as in the PASE benchmark section (pairing, combined_text, pase_threshold)
comp_paired <- pairing == "adjacent_wave"
comp_device <- if (comp_paired) "the device wave of the same visit" else combined_text
comp_population <- if (comp_paired) "at each visit with its own device wave" else sprintf("at each visit, against %s", combined_text)
comp_wave <- if (comp_paired) "that wave's " else ""
pase_walker_rule <- if (pase_threshold == 0) "at least one day of walking outside the home" else
  sprintf("a PASE walking subscore above %s", fmt(pase_threshold))

# Cut k of an answer means "answer at or above level cuts[k]", with each component's own cuts from
# the assumptions. The PASE days answer has levels 0 to 3 (answer_labels$pase_days[i + 1] names
# level i); the walking item's amount answers have levels 1 to 3 (answer_labels$times[i]), so the
# labels follow components.*_cuts and not a fixed position. oaireport::cut_labels() names the
# cuts: "<prefix> <label>", or the label alone at the top level.
component_cuts <- list(pase = "components.pase_frequency_cuts", times = "components.item_times_cuts",
                       months = "components.item_months_cuts")
cut_names <- function(component, ...) {
  pase <- component == "pase"
  oaireport::cut_labels(unlist(assumption(component_cuts[[component]])),
                        answer_labels[[if (pase) "pase_days" else component]],
                        first_level = if (pase) 0 else 1, ...)
}

# A figure another document saved; [report] documents must render that document first
figure_file <- function(name, width = "100%") {
  path <- file.path("figures", paste0(name, ".png"))
  if (!file.exists(path)) {
    stop(path, " is missing; the document that saves it must render before this one ([report] documents)", call. = FALSE)
  }
  c("", "```{=typst}", sprintf('#image("%s", width: %s)', path, width), "```", "")
}
