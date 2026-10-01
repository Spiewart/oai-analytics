# Loaded via R_PROFILE_USER for every R step `oai run` launches from a checkout:
# activates the r/ renv library, then loads oaimodels from source so step scripts
# call oaimodels::fn() exactly as they will against the installed package in the enclave.
# `oai report` renders with RENV_PROFILE=report (r/renv/profiles/report), whose library adds
# the reporting packages; only then is oaireport loaded too.
local({
  owd <- setwd(Sys.getenv("OAI_R_DIR"))
  on.exit(setwd(owd))
  source("renv/activate.R")
})
pkgload::load_all(file.path(Sys.getenv("OAI_R_DIR"), "oaimodels"), quiet = TRUE, export_all = FALSE)
if (identical(Sys.getenv("RENV_PROFILE"), "report")) {
  pkgload::load_all(file.path(Sys.getenv("OAI_R_DIR"), "oaireport"), quiet = TRUE, export_all = FALSE)
}
