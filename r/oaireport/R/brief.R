# Building blocks for a document that pitches results to another group (the walking-validation
# brief), shared with the technical report: colours, the estimate style, callout boxes, a
# sidebar beside a figure, a reading-guide box, numbered labels, the author line and Youden's J
# contours. Layout helpers return lines for a `results: asis` chunk; write them with
# cat(x, sep = "\n").

#' Colours shared by the brief and the report: the walking item, PASE, headings, tints for
#' reference groups, and the fills and rules of the callout boxes
brief_colours <- c(
  item = "#0072B2", pase = "#D55E00", navy = "#0b2e59", tint = "#eef4fb", muted = "#9fb6cf",
  pase_muted = "#f0b48e", note_fill = "#f5f9fd", warn = "#E69F00", warn_fill = "#fffaf0",
  warn_text = "#a86a00", label = "#34567a"
)

#' Escape text for Typst markup inside raw Typst blocks (Markdown is not processed there)
#'
#' "/" is escaped too, because "//" starts a Typst comment.
typst_text <- function(x) {
  if (!is.character(x)) stop("typst_text(): x must be character", call. = FALSE)
  x <- gsub("\\s+", " ", trimws(x))
  gsub("([\\\\#$*_`<>@~/\\[\\]])", "\\\\\\1", x, perl = TRUE)
}

#' An estimate with its 95% interval: "0.89 (0.86–0.91)"; " to " when a limit is negative
fmt_ci <- function(est, lo, hi, digits = 2) {
  n <- max(length(est), length(lo), length(hi))
  est <- rep_len(est, n)
  lo <- rep_len(lo, n)
  hi <- rep_len(hi, n)
  f <- function(x) formatC(x, format = "f", digits = digits, big.mark = ",")
  sep <- ifelse(!is.na(lo) & !is.na(hi) & (lo < 0 | hi < 0), " to ", "–")
  ifelse(is.na(est), "–",
         ifelse(is.na(lo) | is.na(hi), f(est), paste0(f(est), " (", f(lo), sep, f(hi), ")")))
}

#' A callout box: "note" (blue rule: points in our favour, the ask) or "warn" (amber rule:
#' limitations and open questions). `cite` takes bibliography keys, cited Typst-natively.
callout <- function(text, kind = c("note", "warn"), title = NULL, cite = NULL, size = 9.5) {
  kind <- match.arg(kind)
  if (!is.null(cite) && (!is.character(cite) || any(!grepl("^[A-Za-z0-9_:-]+$", cite)))) {
    stop("callout(): cite must be bibliography keys (letters, digits, _ : -)", call. = FALSE)
  }
  rule <- brief_colours[[if (kind == "note") "item" else "warn"]]
  fill <- brief_colours[[if (kind == "note") "note_fill" else "warn_fill"]]
  ink <- brief_colours[[if (kind == "note") "item" else "warn_text"]]
  head <- if (is.null(title)) "" else
    sprintf('#text(weight: "bold", fill: rgb("%s"))[%s] ', ink, typst_text(title))
  cites <- if (is.null(cite)) "" else paste0(" ", paste0("@", cite, collapse = " "))
  c("", "```{=typst}",
    sprintf('#block(width: 100%%, inset: (x: 8pt, y: 6pt), fill: rgb("%s"), stroke: (left: 3pt + rgb("%s")), breakable: false)[',
            fill, rule),
    sprintf("#set text(size: %spt)", format(size)),
    paste0(head, typst_text(text), cites),
    "]", "```", "")
}

#' Page-1 layout: a shaded sidebar of key results and the ask, beside a figure and its caption
#'
#' `results` is a data frame with columns `value` (short: it is set at 15 pt in a narrow column)
#' and `label`; `image` is the figure's path relative to the document.
sidebar_figure <- function(results, ask, image, caption, caption_title = "Figure 1.",
                           heading = "Key results", sidebar = 0.31) {
  if (!is.data.frame(results) || !all(c("value", "label") %in% names(results))) {
    stop("sidebar_figure(): results needs columns value and label", call. = FALSE)
  }
  keys <- sprintf('#text(size: 15pt, weight: "bold", fill: rgb("%s"))[%s] \\ #text(size: 8pt)[%s] #v(6pt)',
                  brief_colours[["navy"]], typst_text(as.character(results$value)),
                  typst_text(as.character(results$label)))
  c("", "```{=typst}",
    sprintf("#grid(columns: (%s%%, 1fr), gutter: 12pt,", format(round(100 * sidebar))),
    sprintf('  block(fill: rgb("%s"), inset: 9pt, radius: 4pt, width: 100%%)[', brief_colours[["tint"]]),
    sprintf('    #text(size: 7pt, fill: rgb("%s"))[%s] #v(4pt)', brief_colours[["label"]],
            typst_text(toupper(heading))),
    paste0("    ", keys),
    sprintf('    #block(width: 100%%, stroke: (left: 3pt + rgb("%s")), fill: white, inset: 6pt)[#text(size: 8.5pt)[#text(weight: "bold", fill: rgb("%s"))[The ask.] %s]]',
            brief_colours[["item"]], brief_colours[["item"]], typst_text(ask)),
    "  ],",
    sprintf('  [#image("%s", width: 100%%) #text(size: 8pt)[#text(weight: "bold")[%s] %s]]',
            image, typst_text(caption_title), typst_text(caption)),
    ")", "```", "")
}

#' A reading-guide box: bold terms with their definitions, then a notation line
reading_guide <- function(definitions, notation, title = "How to read this report") {
  if (!is.character(definitions) || is.null(names(definitions)) || any(!nzchar(names(definitions)))) {
    stop("reading_guide(): definitions must be a named character vector", call. = FALSE)
  }
  items <- sprintf('#text(weight: "bold")[%s:] %s #v(3pt)', typst_text(names(definitions)),
                   typst_text(unname(definitions)))
  c("", "```{=typst}",
    sprintf('#block(width: 100%%, inset: 10pt, radius: 4pt, fill: rgb("%s"), breakable: false)[',
            brief_colours[["tint"]]),
    "#set text(size: 8.5pt)",
    sprintf('#text(size: 10pt, weight: "bold", fill: rgb("%s"))[%s] #v(4pt)', brief_colours[["navy"]],
            typst_text(title)),
    items, typst_text(notation), "]", "```", "")
}

#' Numbered labels: lab <- numberer("A"); lab("Table") gives "Table A1.", then "Table A2."
numberer <- function(prefix = "") {
  counts <- c(Table = 0L, Figure = 0L)
  function(kind = c("Table", "Figure")) {
    kind <- match.arg(kind)
    counts[[kind]] <<- counts[[kind]] + 1L
    sprintf("%s %s%d.", kind, prefix, counts[[kind]])
  }
}

#' The author and contact line from an untracked YAML file, or a neutral placeholder
#'
#' The file holds `authors` (entries with `name` and optional `affiliation`) and an optional
#' `contact` (`name`, `email`). It is never committed: *.local.yml is git-ignored.
author_block <- function(path, placeholder = "Authors and contact to be added") {
  if (!file.exists(path)) return(placeholder)
  info <- yaml::read_yaml(path)
  authors <- info$authors
  named <- function(a) is.list(a) && is.character(a$name) && length(a$name) == 1 && nzchar(a$name)
  if (!is.list(authors) || !length(authors) || !all(vapply(authors, named, logical(1)))) {
    stop("author_block(): ", path, " needs `authors`, a list of entries with a `name`", call. = FALSE)
  }
  who <- vapply(authors, function(a) {
    if (is.null(a$affiliation)) a$name else sprintf("%s (%s)", a$name, a$affiliation)
  }, character(1))
  line <- paste(who, collapse = ", ")
  contact <- info$contact
  if (!is.null(contact)) {
    if (!is.list(contact) || !is.character(contact$email) || !nzchar(contact$email)) {
      stop("author_block(): ", path, " has a `contact` without an `email`", call. = FALSE)
    }
    who_contact <- if (is.null(contact$name)) contact$email else sprintf("%s, %s", contact$name, contact$email)
    line <- sprintf("%s · Contact: %s", line, who_contact)
  }
  line
}

#' Lines of equal Youden's J on a sensitivity / (1 − specificity) plot
#'
#' Each line runs from (0, J) to (1 − J, 1); J = 0 is the chance diagonal. Its value is printed
#' just above the top edge where the line ends, so no label sits on a line or a point. Add to a
#' plot with `+`, together with coord_equal(xlim = c(0, 1), ylim = c(0, 1), clip = "off") and a
#' top margin of 14 pt or more.
youden_contours <- function(j = c(0, 0.1, 0.2, 0.3, 0.4)) {
  if (!is.numeric(j) || !length(j) || anyNA(j) || any(j < 0 | j >= 1)) {
    stop("youden_contours(): j must be numbers in [0, 1)", call. = FALSE)
  }
  lines <- do.call(rbind, lapply(j, function(x) data.frame(j = x, fpr = c(0, 1 - x), se = c(x, 1))))
  ends <- data.frame(j = j, fpr = 1 - j, se = 1,
                     label = ifelse(j == max(j), paste0("J = ", as.character(j)), as.character(j)))
  list(
    ggplot2::geom_line(data = lines, ggplot2::aes(fpr, se, group = j), inherit.aes = FALSE,
                       linewidth = 0.25, colour = "grey75", linetype = "dashed"),
    ggplot2::geom_text(data = ends, ggplot2::aes(fpr, se, label = label), inherit.aes = FALSE,
                       size = 2.2, colour = "grey45", vjust = -0.6, family = oai_font())
  )
}
