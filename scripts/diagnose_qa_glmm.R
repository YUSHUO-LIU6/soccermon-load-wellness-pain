# Post-publication numerical diagnostics; not a replacement published model.
args <- commandArgs(trailingOnly=TRUE);stopifnot(length(args)==2)
.libPaths(c(normalizePath('workspace/R/library'),.libPaths()))
suppressPackageStartupMessages(library(lme4));suppressPackageStartupMessages(library(jsonlite))
set.seed(20260722)
d <- read.csv(args[1],stringsAsFactors=FALSE)
d$team<-factor(d$team);d$season<-factor(d$season);d$player_id<-factor(d$player_id)
reference<-read.csv('reproducibility/frozen/10_SEASON_SENSITIVITY/SEASON_STABILITY.csv',stringsAsFactors=FALSE)
reference<-reference[reference$model_id=='A_drop_team_season',]
f<-as.formula(reference$formula[1])
d<-d[complete.cases(d[,unique(c(all.vars(f),'prev_episode_count','team','season','date'))]),]
stopifnot(nrow(d)==reference$n[1],sum(d$onset_day)==reference$events[1])
ctrl<-glmerControl(optimizer='bobyqa',optCtrl=list(maxfun=2e5))
fits<-list();out<-list(scope='POST_PUBLICATION_VALIDATION: fixed QA formula, initialization diagnostics only',R=R.version.string,lme4=as.character(packageVersion('lme4')),n=nrow(d),events=sum(d$onset_day),fits=list())
for (tag in c('default','frozen_fixed_effect_start')) {
 warnings<-character()
 starting<-if(tag=='default') NULL else list(theta=getME(fits$default,'theta'),fixef=setNames(log(reference$OR),reference$term)[names(fixef(fits$default))])
 fit<-withCallingHandlers(glmer(f,data=d,family=binomial,nAGQ=1,control=ctrl,start=starting),warning=function(w){warnings<<-c(warnings,conditionMessage(w));invokeRestart('muffleWarning')})
 fits[[tag]]<-fit
 dir.create('workspace/qa_glmm_fits',recursive=TRUE,showWarnings=FALSE)
 saveRDS(fit,file.path('workspace/qa_glmm_fits',paste0(tag,'.rds')))
 cat(tag,'logLik',as.numeric(logLik(fit)),'previous episode beta',fixef(fit)['prev_episode_ever'],'\n')
 h<-fit@optinfo$derivs$Hessian;grad<-fit@optinfo$derivs$gradient
 scaled<-tryCatch(solve(chol(h),grad),error=function(e)NA_real_)
 max_grad<-if(is.numeric(grad) && length(grad)) max(abs(grad)) else NA_real_
 eigenvalues<-if(is.matrix(h) && is.numeric(h)) eigen(h,symmetric=TRUE,only.values=TRUE)$values else NA_real_
 out$fits[[tag]]<-list(formula=paste(deparse(f),collapse=' '),log_likelihood=as.numeric(logLik(fit)),theta=as.list(getME(fit,'theta')),coefficients=as.list(fixef(fit)),warnings=warnings,optimizer_code=fit@optinfo$conv$opt,lme4_convergence=fit@optinfo$conv$lme4,max_abs_gradient=max_grad,derivative_storage_class=class(fit@optinfo$derivs),max_abs_scaled_gradient=if(is.numeric(scaled)) max(abs(scaled)) else NA_real_,Hessian_eigenvalues=eigenvalues)
}
dir.create(dirname(args[2]),recursive=TRUE,showWarnings=FALSE)
write_json(out,args[2],pretty=TRUE,auto_unbox=TRUE,digits=16,na='null',null='null')
