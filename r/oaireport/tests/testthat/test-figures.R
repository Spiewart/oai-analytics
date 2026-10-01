estimates <- data.frame(
  outcome = rep(c("New pain", "KL worse"), each = 2),
  source = rep(c("Published", "Ours"), 2),
  or = c(0.6, 0.66, 0.8, 0.82),
  lo = c(0.4, 0.47, 0.6, 0.62),
  hi = c(0.8, 0.94, 1.1, 1.10)
)

# Point colours keyed by odds ratio ("0.60", "0.66", ...); x is log10(or) on a log axis.
point_colours <- function(p, log_scale = TRUE) {
  points <- ggplot2::layer_data(p, 2)
  or <- if (log_scale) 10^points$x else points$x
  stats::setNames(points$colour, format(round(or, 2)))
}

test_that("forest_plot maps sources to fixed colours and shapes on a log axis", {
  p <- forest_plot(estimates)
  points <- ggplot2::layer_data(p, 2)
  expect_equal(sort(points$x), sort(log10(estimates$or)))
  colours <- point_colours(p)
  expect_equal(unname(colours[c("0.60", "0.66")]), oai_palette[1:2])
  expect_setequal(points$shape, c(16, 17))
  expect_equal(ggplot2::layer_data(p, 1)$xintercept, 0)
})

test_that("forest_plot puts the first outcome at the top", {
  points <- ggplot2::layer_data(forest_plot(estimates), 2)
  first <- round(10^points$x, 2) %in% c(0.6, 0.66)
  expect_gt(mean(points$y[first]), mean(points$y[!first]))
})

test_that("forest_plot honours a linear scale, facets in order and a given source order", {
  est <- rbind(transform(estimates, model = "Unadjusted"), transform(estimates, model = "Adjusted"))
  p <- forest_plot(est, log_scale = FALSE, facet = "model", sources = c("Ours", "Published"))
  expect_equal(ggplot2::layer_data(p, 1)$xintercept[1], 1)
  expect_s3_class(p$facet, "FacetWrap")
  expect_equal(levels(p$data$model), c("Unadjusted", "Adjusted"))
  expect_equal(levels(p$data$source), c("Ours", "Published"))
  expect_equal(unname(point_colours(p, log_scale = FALSE)[c("0.66", "0.60")]), oai_palette[1:2])
})

test_that("forest_plot rejects missing columns, unlisted sources and more than four sources", {
  expect_error(forest_plot(estimates[, -3]), "missing column\\(s\\): or")
  expect_error(forest_plot(estimates, sources = "Published"), "sources does not list: Ours")
  five <- data.frame(outcome = "x", source = letters[1:5], or = 1, lo = 0.5, hi = 2)
  expect_error(forest_plot(five), "at most 4 sources")
})

flow <- data.frame(
  step = c("all", "age50", "roa"),
  persons = c(4796, 4247, 2336),
  excluded_persons = c(0, 549, 1911),
  excluded_knees = c(0, 299, 0)
)

test_that("flow_diagram draws a box per step and side boxes for exclusions", {
  p <- flow_diagram(flow, labels = c(all = "Enrolled", age50 = "Age >= 50"))
  main <- ggplot2::layer_data(p, 4)$label
  side <- ggplot2::layer_data(p, 5)$label
  expect_equal(main, c("Enrolled\nn = 4,796", "Age >= 50\nn = 4,247", "roa\nn = 2,336"))
  expect_equal(side, c("Excluded: 549\n(299 knees)", "Excluded: 1,911"))
})

test_that("flow_diagram shows published counts in brackets", {
  p <- flow_diagram(
    flow,
    labels = c(roa = "Knee OA"),
    published = c(flow.roa.persons = 2356, flow.age50.excluded_knees = 300)
  )
  labels <- c(ggplot2::layer_data(p, 4)$label, ggplot2::layer_data(p, 5)$label)
  expect_true("Knee OA\nn = 2,336 [2,356]" %in% labels)
  expect_true("Excluded: 549\n(299 [300] knees)" %in% labels)
  expect_true("all\nn = 4,796" %in% labels)
})

test_that("counts keep thousands separators without scientific notation", {
  expect_equal(count_text(c(100000, 4796, 549)), c("100,000", "4,796", "549"))
})

test_that("flow_diagram handles a flow without exclusions and rejects bad input", {
  p <- flow_diagram(flow[1, ], labels = character())
  expect_length(ggplot2::layer_data(p, 4)$label, 1)
  expect_length(ggplot2::layer_data(p, 5)$label, 0)
  expect_error(flow_diagram(flow[, 1:2], labels = character()), "missing column")
  expect_error(flow_diagram(flow[0, ], labels = character()), "no steps")
})
