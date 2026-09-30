# Loaded via R_PROFILE_USER for every R step `oai run` launches from a checkout:
# activates the r/ renv library, then loads oaimodels from source so step scripts
# call oaimodels::fn() exactly as they will against the installed package in the enclave.
local({
  owd <- setwd(Sys.getenv("OAI_R_DIR"))
  on.exit(setwd(owd))
  source("renv/activate.R")
})
pkgload::load_all(file.path(Sys.getenv("OAI_R_DIR"), "oaimodels"), quiet = TRUE, export_all = FALSE)
