test_that("read_frame round-trips Parquet and checks required columns", {
  path <- tempfile(fileext = ".parquet")
  nanoparquet::write_parquet(data.frame(ID = 1000001:1000003, time_years = c(0, 1, 2)), path)
  frame <- read_frame(path, required = c("ID", "time_years"))
  expect_equal(nrow(frame), 3)
  expect_error(read_frame(path, required = "age0"), "missing required columns: age0")
})

test_that("read_frame explains a missing file", {
  expect_error(read_frame(tempfile()), "Frame not found")
})
