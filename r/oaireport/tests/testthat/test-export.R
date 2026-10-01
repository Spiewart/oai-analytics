point_plot <- function() {
  ggplot2::ggplot(data.frame(x = 1, y = 1), ggplot2::aes(x, y)) + ggplot2::geom_point()
}

test_that("save_figure writes a vector PDF and a 300 dpi PNG at ACR widths", {
  dir <- withr::local_tempdir()
  path <- save_figure(point_plot(), "two", "2col", dir = dir)
  expect_equal(path, file.path(dir, "two.pdf"))
  expect_gt(file.size(path), 0)
  expect_equal(png_size(file.path(dir, "two.png")), c(width = 2100, height = 1575))
  save_figure(point_plot(), "one", "1col", dir = dir)
  one <- png_size(file.path(dir, "one.png"))
  expect_equal(one[["width"]], 1050)
  expect_lte(abs(one[["height"]] - 787.5), 1)
})

test_that("save_figure caps the height at 9 inches", {
  dir <- withr::local_tempdir()
  save_figure(point_plot(), "tall", "1col", height = 20, dir = dir)
  expect_equal(png_size(file.path(dir, "tall.png"))[["height"]], 2700)
})

test_that("save_figure rejects names that are not plain file stems", {
  expect_error(save_figure(point_plot(), "../x", dir = withr::local_tempdir()), "figure name")
})

test_that("figure_dir follows OAI_REPORT_DIR", {
  withr::local_envvar(OAI_REPORT_DIR = file.path("tmp", "rep"))
  expect_equal(figure_dir(), file.path("tmp", "rep", "figures"))
  withr::local_envvar(OAI_REPORT_DIR = "")
  expect_equal(figure_dir(), tempdir())
})
