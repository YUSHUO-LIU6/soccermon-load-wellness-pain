# Install only missing analytical dependencies into a project-local library.
args <- commandArgs(trailingOnly=TRUE)
lib <- if (length(args)) args[1] else Sys.getenv("SOCCERMON_R_LIBRARY", unset="workspace/R/library")
dir.create(lib, recursive=TRUE, showWarnings=FALSE)
.libPaths(c(normalizePath(lib), .libPaths()))
needed <- c("lme4", "clubSandwich", "sandwich", "lmtest", "logistf", "survival", "boot", "coxme", "jsonlite", "numDeriv")
missing <- needed[!vapply(needed, requireNamespace, logical(1), quietly=TRUE)]
if (length(missing)) install.packages(missing, lib=lib, repos="https://cloud.r-project.org")
stopifnot(all(vapply(needed, requireNamespace, logical(1), quietly=TRUE)))
write.csv(data.frame(package=needed, version=vapply(needed, function(x) as.character(packageVersion(x)), character(1))),
          file.path(lib, "installed_versions.csv"), row.names=FALSE)
write.csv(data.frame(package=needed,
                    library=vapply(needed, function(x) dirname(find.package(x)), character(1)),
                    newly_installed=needed %in% missing),
          file.path(lib, "package_origins.csv"), row.names=FALSE)
capture.output(sessionInfo(), file=file.path(lib,"setup_session.txt"))
cat(R.version.string, "\nProject library:", normalizePath(lib), "\n")
