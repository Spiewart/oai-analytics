# Width and height in pixels from a PNG's IHDR chunk.
png_size <- function(path) {
  con <- file(path, "rb")
  on.exit(close(con))
  bytes <- readBin(con, "raw", 24)
  to_int <- function(b) sum(as.integer(b) * 256^(3:0))
  c(width = to_int(bytes[17:20]), height = to_int(bytes[21:24]))
}
