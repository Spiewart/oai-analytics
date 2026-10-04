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
