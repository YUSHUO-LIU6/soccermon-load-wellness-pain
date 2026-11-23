# A post-publication dependency diagnostic, separate from the reference rerun.
# Rscript --vanilla scripts/probe_frailty_version.R LIB DATASET OUTPUT.json
args <- commandArgs(trailingOnly=TRUE)
stopifnot(length(args)==3)
.libPaths(c(normalizePath(args[1]),normalizePath('workspace/R/library'),.libPaths()))
suppressPackageStartupMessages(library(survival))
suppressPackageStartupMessages(library(jsonlite))
if (grepl('/reproducibility/frozen/',normalizePath(args[3],mustWork=FALSE),fixed=TRUE))
  stop('Do not overwrite frozen evidence')
set.seed(20260722)
# Reuse the actual source definitions; do not execute its model suite.
e <- parse('analysis/core/04_run_reanalysis.R')
needed <- c('cc_sample','mk_cp','cox_rhs')
for (expr in e) {
  if (is.call(expr) && identical(expr[[1]],as.name('<-')) &&
      is.symbol(expr[[2]]) && as.character(expr[[2]]) %in% needed) eval(expr)
}
stopifnot(all(vapply(needed,exists,logical(1))))
d <- read.csv(args[2],stringsAsFactors=FALSE)
d$date <- as.Date(d$date)
d$team <- factor(d$team); d$season <- factor(d$season); d$player_id <- factor(d$player_id)
wcol <- 'readiness_deficit_recent3_wp_z'
cp <- mk_cp(cc_sample(d,wcol))
f <- as.formula(paste0('Surv(tstart, tstop, onset_day) ~ ',cox_rhs(wcol),' + frailty(player_id)'))
warns <- character()
fit <- tryCatch(withCallingHandlers(coxph(f,data=cp),warning=function(w) {
  warns <<- c(warns,conditionMessage(w));invokeRestart('muffleWarning')
}),error=function(e)e)
result <- list(scope='Post-publication controlled dependency probe; does not replace the full run',
 R=R.version.string,survival=as.character(packageVersion('survival')),seed=20260722,
 formula=paste(deparse(f),collapse=' '),n=nrow(cp),events=sum(cp$onset_day),
 gamma_status=if(inherits(fit,'error')) 'FAILED' else 'FITTED',
 gamma_error=if(inherits(fit,'error')) conditionMessage(fit) else NULL,
 warnings=warns)
if (inherits(fit,'error')) {
 f2 <- as.formula(paste0('Surv(tstart, tstop, onset_day) ~ ',cox_rhs(wcol),' + (1 | player_id)'))
 fallback <- tryCatch(coxme::coxme(f2,data=cp),error=function(e)e)
 result$fallback_status <- if(inherits(fallback,'error')) 'FAILED' else 'FITTED'
 result$fallback_error <- if(inherits(fallback,'error')) conditionMessage(fallback) else NULL
} else {
 result$coefficients <- as.list(coef(fit))
}
dir.create(dirname(args[3]),recursive=TRUE,showWarnings=FALSE)
write_json(result,args[3],pretty=TRUE,auto_unbox=TRUE,na='null',null='null',digits=16)
cat('survival',result$survival,'gamma',result$gamma_status,'fallback',result$fallback_status,'\n')
