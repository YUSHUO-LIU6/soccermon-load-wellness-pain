# Independent refits of two prespecified, manuscript-facing Firth models.
# Formulas and factor coding follow frozen 04_run_reanalysis.R and
# 11_BACKWARD_STANDARDIZATION/run_backwardz_models.R. No model selection.
lib <- Sys.getenv("SOCCERMON_R_LIBRARY", unset="workspace/R/library")
if (dir.exists(lib)) .libPaths(c(normalizePath(lib), .libPaths()))
suppressPackageStartupMessages(library(logistf))
set.seed(20260722)
ws <- Sys.getenv("SOCCERMON_WORKSPACE")
root <- normalizePath(".")
execution_root <- Sys.getenv("SOCCERMON_EXECUTION_ROOT", unset=file.path(root,"workspace"))
fr <- file.path(execution_root,"r2")
out <- file.path(execution_root,"validation")
dir.create(out,recursive=TRUE,showWarnings=FALSE)
rows <- list()
configs <- list(
 list(id="F",data=file.path(ws,"07_ANALYSIS_OUTPUTS/modeling_dataset.csv"),suffix="",
      source="reproducibility/frozen/r1/r_results.csv"),
 list(id="F_hist",data=file.path(fr,"11_BACKWARD_STANDARDIZATION/modeling_dataset_backwardz.csv"),suffix="_hist",
      source="reproducibility/frozen/11_BACKWARD_STANDARDIZATION/BACKWARD_STANDARDIZATION_RESULTS.csv")
)
for (cfg in configs) {
 d <- read.csv(cfg$data,stringsAsFactors=FALSE)
 d$team <- factor(d$team); d$season <- factor(d$season)
 a <- paste0("acute_load_7d_wp_z",cfg$suffix)
 w <- paste0("soreness_burden_recent3_wp_z",cfg$suffix)
 c <- paste0("chronic_load_28d_wp_z",cfg$suffix)
 f <- as.formula(paste("onset_day ~",a,"*",w,"+",c,"+ prev_episode_ever + calendar_time + team + season"))
 d <- d[complete.cases(d[,all.vars(f)]),]
  cat("Fitting",cfg$id,"N",nrow(d),"events",sum(d$onset_day),"\n")
 fit <- logistf(f,data=d)
  capture.output(print(fit),file=file.path(out,paste0("focal_",cfg$id,"_fit.txt")))
 ref <- read.csv(cfg$source,stringsAsFactors=FALSE)
 for (term in c(paste0(a,":",w),c)) {
  expected <- ref[ref$model_id==cfg$id & ref$wellness_variant=="soreness" & ref$term==term,]
  stopifnot(nrow(expected)==1)
  observed <- c(OR=exp(fit$coefficients[term]),low=exp(fit$ci.lower[term]),high=exp(fit$ci.upper[term]))
  target <- c(expected$OR,expected$CI_low,expected$CI_high)
  error <- max(abs(unname(observed)-target))
  sample_ok <- nrow(d)==expected$n && sum(d$onset_day)==expected$events
  rows[[length(rows)+1]] <- data.frame(model=cfg$id,term=term,n=nrow(d),events=sum(d$onset_day),
      OR=unname(observed[1]),CI_low=unname(observed[2]),CI_high=unname(observed[3]),
      frozen_OR=expected$OR,frozen_CI_low=expected$CI_low,frozen_CI_high=expected$CI_high,
      frozen_n=expected$n,frozen_events=expected$events,
      max_abs_difference=error,tolerance=0.001,
      status=if (is.finite(error) && error<=0.001 && sample_ok) "PASS" else "FAIL")
 }
}
write.csv(do.call(rbind,rows),file.path(out,"focal_refits.csv"),row.names=FALSE)
capture.output(sessionInfo(),file=file.path(out,"R_session.txt"))
stopifnot(all(vapply(rows,function(x) x$status=="PASS",logical(1))))
