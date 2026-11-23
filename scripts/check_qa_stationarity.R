# Inspect saved QA fits without rerunning their optimizer.
args<-commandArgs(trailingOnly=TRUE);stopifnot(length(args)==2)
.libPaths(c(normalizePath('workspace/R/library'),.libPaths()))
suppressPackageStartupMessages(library(lme4));suppressPackageStartupMessages(library(jsonlite))
files<-list.files(args[1],pattern='\\.rds$',full.names=TRUE)
result<-list(scope='POST_PUBLICATION_VALIDATION: finite-difference stationarity audit',fits=list())
for (path in files) {
 fit<-readRDS(path); f<-formula(fit); d<-model.frame(fit)
 dev<-glmer(f,data=d,family=binomial,nAGQ=1,
            control=glmerControl(optimizer='bobyqa',optCtrl=list(maxfun=2e5)),devFunOnly=TRUE)
 parameters<-c(getME(fit,'theta'),fixef(fit))
 at_fit<-dev(parameters); expected<- -2*as.numeric(logLik(fit))
 grad<-numDeriv::grad(dev,parameters)
 hessian<-numDeriv::hessian(dev,parameters)
 eigenvalues<-eigen(hessian,symmetric=TRUE,only.values=TRUE)$values
 result$fits[[tools::file_path_sans_ext(basename(path))]]<-list(
  stored_deviance=expected,recomputed_deviance=at_fit,deviance_matches=abs(at_fit-expected)<1e-5,
  max_abs_gradient=max(abs(grad)),gradient=grad,Hessian_eigenvalues=eigenvalues,
  scaled_gradient=tryCatch(solve(chol(hessian),grad),error=function(e)NULL))
}
write_json(result,args[2],pretty=TRUE,auto_unbox=TRUE,na='null',null='null',digits=16)
