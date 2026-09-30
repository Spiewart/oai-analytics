#' Read an analysis frame written by the Python side
#'
#' @param path Parquet file. Defaults to `frame.parquet` in `OAI_FRAME_DIR`,
#'   which `oai run` sets for every step.
#' @param required Columns that must be present.
#' @return A data.frame.
read_frame <- function(path = file.path(Sys.getenv("OAI_FRAME_DIR"), "frame.parquet"),
                       required = character()) {
  if (!file.exists(path)) stop("Frame not found: ", path, call. = FALSE)
  frame <- as.data.frame(nanoparquet::read_parquet(path))
  missing <- setdiff(required, names(frame))
  if (length(missing)) {
    stop("Frame is missing required columns: ", paste(missing, collapse = ", "), call. = FALSE)
  }
  frame
}
