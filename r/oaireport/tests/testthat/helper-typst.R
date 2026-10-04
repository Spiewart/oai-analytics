# Whether the [ ] and ( ) of generated Typst balance and nest properly. Escaped characters (a
# backslash and the character after it) are removed first, so only structural brackets count.
typst_balanced <- function(x) {
  chars <- strsplit(gsub("\\\\.", "", paste(x, collapse = "\n")), "")[[1]]
  closer <- c("[" = "]", "(" = ")")
  stack <- character()
  for (ch in chars[chars %in% c("[", "]", "(", ")")]) {
    if (ch %in% names(closer)) {
      stack <- c(stack, closer[[ch]])
    } else if (!length(stack) || stack[length(stack)] != ch) {
      return(FALSE)
    } else {
      stack <- stack[-length(stack)]
    }
  }
  !length(stack)
}

expect_typst_balanced <- function(x) {
  testthat::expect_true(typst_balanced(x), info = "unbalanced [ ] or ( ) in the generated Typst")
}

# The one line of `x` that contains `text` (found by content, so a change to a block's layout cannot
# make an assertion check another line)
line_with <- function(x, text) {
  hit <- x[grepl(text, x, fixed = TRUE)]
  testthat::expect_length(hit, 1)
  hit
}
