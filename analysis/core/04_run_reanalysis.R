#!/usr/bin/env Rscript
# ============================================================================
# 04_run_reanalysis.R — Phase 10/11 formal re-analysis per FROZEN SAP v1.0
# PONE-D-26-31950 (SoccerMon). Model set is fixed by
# 05_REVISION_SAP/model_candidate_matrix.csv — no p-value-based selection.
#
# Naming note (SAP-concordant): SAP §3 defines the PRIMARY wellness exposure
# as the most recent report within t-3..t-1 ("recent3"); the strict day t-1
# lag is a sensitivity. In modeling_dataset.csv the recent3 within-player z
# columns are *_recent3_wp_z and the strict-lag1 z columns are *_wp_z
# (built from *_burden_lag1). The SAP §5 formula label "soreness_burden_wp_z"
# is shorthand; the recent3 columns are used for all primary fits and the
# lag1 columns for sensitivity S4. This mapping is recorded in RESULTS_LOCK.md.
#
# Inputs  : 07_ANALYSIS_OUTPUTS/modeling_dataset.csv
#           07_ANALYSIS_OUTPUTS/episode_inventory.csv
#           RUN_ID.txt
#           <RUN>/sens_washout3d.csv, sens_washout14d.csv, sens_acwr.csv   (from 05 prep)
#           <RUN>/ipw_weights_<var>.csv                                     (from 05 ipw)
# Outputs : 07_ANALYSIS_OUTPUTS/<RUN_ID>/r_results.csv (+ inventories,
#           diagnostics, session info) — appended into master_results.* by
#           05_bootstrap_and_ipw.py finalize.
# Log     : logs/04_reanalysis.log
# ============================================================================

suppressPackageStartupMessages({
  library(survival)
  library(lme4)
  library(clubSandwich)
  library(sandwich)
  library(lmtest)
  library(logistf)
})

SEED <- 20260722
set.seed(SEED)

args_full <- commandArgs(trailingOnly = FALSE)
file_arg <- args_full[grepl("^--file=", args_full)]
if (length(file_arg) > 0) {
  SCRIPT_DIR <- dirname(normalizePath(sub("^--file=", "", file_arg[1]), mustWork = FALSE))
  REPO_ROOT <- normalizePath(file.path(SCRIPT_DIR, "..", ".."), mustWork = FALSE)
} else {
  REPO_ROOT <- normalizePath(getwd(), mustWork = FALSE)
}
WS <- Sys.getenv("SOCCERMON_WORKSPACE", unset = file.path(REPO_ROOT, "workspace"))
dir.create(WS, recursive = TRUE, showWarnings = FALSE)
RUN_FILE <- file.path(WS, "RUN_ID.txt")
if (file.exists(RUN_FILE)) {
  RUN <- trimws(readLines(RUN_FILE, warn = FALSE)[1])
} else {
  RUN <- Sys.getenv("SOCCERMON_RUN_ID", unset = "RUN_PUBLIC")
  writeLines(RUN, RUN_FILE)
}
OUT <- file.path(WS, "07_ANALYSIS_OUTPUTS", RUN)
dir.create(OUT, recursive = TRUE, showWarnings = FALSE)
LOGF <- file.path(WS, "logs", "04_reanalysis.log")
dir.create(dirname(LOGF), recursive = TRUE, showWarnings = FALSE)

log_msg <- function(...) {
  txt <- paste0(format(Sys.time(), "%H:%M:%S"), " | ", paste(..., collapse = ""))
  cat(txt, "\n")
  cat(txt, "\n", file = LOGF, append = TRUE)
}

# ---- incremental result stores (flushed after every model) -----------------
res_file   <- file.path(OUT, "r_results.csv")
inv_file   <- file.path(OUT, "model_inventory.csv")
ss_file    <- file.path(OUT, "sample_size_inventory.csv")
diag_file  <- file.path(OUT, "diagnostic_inventory.csv")

append_csv <- function(df, path) {
  write.table(df, path, sep = ",", row.names = FALSE, quote = TRUE,
              append = file.exists(path), col.names = !file.exists(path))
}
# Resume support: with REANALYSIS_RESUME=1, keep existing output files and
# skip (model_id, variant) combos already recorded in model_inventory.csv.
RESUME <- Sys.getenv("REANALYSIS_RESUME", "0") == "1"
.done <- character(0)
if (RESUME && file.exists(inv_file)) {
  .inv0 <- tryCatch(read.csv(inv_file, stringsAsFactors = FALSE),
                    error = function(e) NULL)
  if (!is.null(.inv0))
    .done <- paste(.inv0$model_id, .inv0$wellness_variant)
  log_msg("RESUME mode: ", length(.done), " model entries already present")
} else {
  for (f in c(res_file, inv_file, ss_file, diag_file))
    if (file.exists(f)) file.remove(f)
}
already_done <- function(model_id, variant)
  RESUME && (paste(model_id, variant) %in% .done)

add_results <- function(rows) append_csv(as.data.frame(rows), res_file)
add_inventory <- function(model_id, variant, formula, data_desc, status, fail_reason = "") {
  append_csv(data.frame(model_id = model_id, wellness_variant = variant,
                        formula = formula, data = data_desc, status = status,
                        fail_reason = fail_reason, stringsAsFactors = FALSE), inv_file)
}
add_ss <- function(model_id, variant, d, n_param) {
  ev <- sum(d$onset_day)
  append_csv(data.frame(
    model_id = model_id, wellness_variant = variant,
    n = nrow(d), players = length(unique(d$player_id)),
    at_risk_days = nrow(d), onset_days = ev,
    event_players = length(unique(d$player_id[d$onset_day == 1])),
    n_parameters = n_param, events_per_parameter = round(ev / n_param, 2),
    stringsAsFactors = FALSE), ss_file)
}
add_diag <- function(model_id, variant, diagnostic, value) {
  append_csv(data.frame(model_id = model_id, wellness_variant = variant,
                        diagnostic = diagnostic, value = as.character(value),
                        stringsAsFactors = FALSE), diag_file)
}

# ============================================================================
# Data
# ============================================================================
md <- read.csv(file.path(WS, "07_ANALYSIS_OUTPUTS", "modeling_dataset.csv"),
               stringsAsFactors = FALSE)
md$date <- as.Date(md$date)
md$team   <- factor(md$team)
md$season <- factor(md$season)
md$player_id <- factor(md$player_id)
log_msg("modeling_dataset: ", nrow(md), " rows; onset_day positives = ",
        sum(md$onset_day), "; players = ", length(unique(md$player_id)))

WELL <- c(soreness  = "soreness_burden_recent3_wp_z",
          fatigue   = "fatigue_burden_recent3_wp_z",
          readiness = "readiness_deficit_recent3_wp_z")

mk_formula <- function(wcol, interaction = TRUE, chronic = TRUE) {
  rhs <- if (interaction)
    paste0("acute_load_7d_wp_z * ", wcol) else
    paste0("acute_load_7d_wp_z + ", wcol)
  if (chronic) rhs <- paste0(rhs, " + chronic_load_28d_wp_z")
  as.formula(paste0("onset_day ~ ", rhs,
    " + prev_episode_ever + calendar_time + team + season"))
}

cc_sample <- function(d, wcol, extra = character(0)) {
  # days_since_last_episode is NA by design when no previous episode and is
  # NOT a model covariate (PWP gap-time derives it conditionally) — exclude
  # it from the complete-case test.
  vars <- c("onset_day", "acute_load_7d_wp_z", wcol, "chronic_load_28d_wp_z",
            "prev_episode_ever", "calendar_time", "team", "season",
            "player_id", "date", "prev_episode_count", extra)
  d[complete.cases(d[, vars]), ]
}

# ============================================================================
# Model A — discrete-time GLMM with registered fallback order
# fallback: (1) drop interaction -> (2) drop chronic -> (3) population-average
# glm + player CRVE.  (SAP step "reduce wellness predictors fatigue then
# readiness" does not apply: each model carries a single wellness predictor.)
# ============================================================================
fit_modelA <- function(d, variant, role, model_id = "A") {
  wcol <- WELL[[variant]]
  ctrl <- glmerControl(optimizer = "bobyqa", optCtrl = list(maxfun = 2e5))
  lvls <- list(
    list(f = mk_formula(wcol, TRUE, TRUE),  tag = "full"),
    list(f = mk_formula(wcol, FALSE, TRUE), tag = "no_interaction"),
    list(f = mk_formula(wcol, FALSE, FALSE), tag = "no_interaction_no_chronic"))
  for (i in seq_along(lvls)) {
    warns <- character(0)
    f_re <- update(lvls[[i]]$f, . ~ . + (1 | player_id))
    fit <- tryCatch(
      withCallingHandlers(
        glmer(f_re, data = d, family = binomial, nAGQ = 1, control = ctrl),
        warning = function(w) { warns <<- c(warns, conditionMessage(w))
                                invokeRestart("muffleWarning") }),
      error = function(e) e)
    if (inherits(fit, "error")) {
      add_diag(model_id, variant, paste0("glmer_error_level_", lvls[[i]]$tag),
               conditionMessage(fit))
      next
    }
    conv <- length(fit@optinfo$conv$lme4) == 0
    sing <- isSingular(fit, tol = 1e-4)
    sm <- summary(fit)$coefficients
    separation <- any(abs(sm[, "Estimate"]) > 10)
    add_diag(model_id, variant, paste0("converged_", lvls[[i]]$tag), conv)
    add_diag(model_id, variant, paste0("singular_", lvls[[i]]$tag), sing)
    if (length(warns)) add_diag(model_id, variant,
                                paste0("warnings_", lvls[[i]]$tag),
                                paste(unique(warns), collapse = " || "))
    if (conv && !separation) {
      return(list(kind = "glmer", fit = fit, formula = paste(deparse(f_re), collapse = " "),
                  fallback = lvls[[i]]$tag, singular = sing))
    }
    add_diag(model_id, variant, "fallback_trigger",
             paste0(lvls[[i]]$tag, ": converged=", conv,
                    " separation=", separation))
  }
  # population-average fallback
  f_pa <- mk_formula(wcol, FALSE, TRUE)
  g <- tryCatch(glm(f_pa, data = d, family = binomial), error = function(e) e)
  if (inherits(g, "error"))
    return(list(kind = "failed", fail = conditionMessage(g)))
  V <- tryCatch(vcovCR(g, cluster = d$player_id, type = "CR2"),
                error = function(e) e)
  return(list(kind = "glm_crve", fit = g, vcov = V,
              formula = paste(deparse(f_pa), collapse = " "), fallback = "population_average_crve"))
}

extract_glmer <- function(fit, d, variant, model_id, role, fallback, singular) {
  sm <- summary(fit)$coefficients
  data.frame(
    analysis_role = role, model_id = model_id, wellness_variant = variant,
    term = rownames(sm), OR = exp(sm[, "Estimate"]),
    CI_low = exp(sm[, "Estimate"] - 1.96 * sm[, "Std. Error"]),
    CI_high = exp(sm[, "Estimate"] + 1.96 * sm[, "Std. Error"]),
    p = sm[, "Pr(>|z|)"], se = sm[, "Std. Error"],
    converged = TRUE, optimizer = paste0("bobyqa_maxfun2e5_fallback=", fallback),
    n = nrow(d), players = length(unique(d$player_id)), events = sum(d$onset_day),
    notes = paste0("glmer nAGQ=1; singular=", singular, "; fallback_level=", fallback),
    stringsAsFactors = FALSE)
}

run_A <- function(d, variant, role, model_id = "A") {
  if (already_done(model_id, variant)) {
    log_msg("skip (resume): ", model_id, " / ", variant)
    return(invisible(NULL))
  }
  r <- fit_modelA(d, variant, role, model_id)
  if (r$kind == "failed") {
    add_inventory(model_id, variant, "see SAP", "per-model complete case",
                  "FAILED", r$fail)
    return(invisible(NULL))
  }
  add_inventory(model_id, variant, r$formula, "per-model complete case",
                paste0("OK (", r$kind, ", fallback=", r$fallback, ")"))
  if (r$kind == "glmer") {
    add_results(extract_glmer(r$fit, d, variant, model_id, role,
                              r$fallback, r$singular))
    np <- nrow(summary(r$fit)$coefficients) + 1
  } else {
    if (inherits(r$vcov, "error")) {
      add_inventory(model_id, variant, r$formula, "CC", "FAILED_CRVE",
                    conditionMessage(r$vcov)); return(invisible(NULL))
    }
    ct <- coeftest(r$fit, vcov. = r$vcov)
    sep_pa <- any(abs(ct[, 1]) > 10)
    add_diag(model_id, variant, "separation_population_average", sep_pa)
    if (sep_pa)
      add_diag(model_id, variant, "separated_terms",
               paste(rownames(ct)[abs(ct[, 1]) > 10], collapse = " || "))
    add_results(data.frame(
      analysis_role = role, model_id = model_id, wellness_variant = variant,
      term = rownames(ct), OR = exp(ct[, 1]),
      CI_low = exp(ct[, 1] - 1.96 * ct[, 2]), CI_high = exp(ct[, 1] + 1.96 * ct[, 2]),
      p = ct[, 4], se = ct[, 2], converged = TRUE,
      optimizer = "glm+clubSandwich_CR2", n = nrow(d),
      players = length(unique(d$player_id)), events = sum(d$onset_day),
      notes = paste0("population-average fallback (GLMM separation); player CRVE",
                     if (sep_pa) "; separation present (|beta|>10) — interpret with Firth (Model F)" else ""),
      stringsAsFactors = FALSE))
    np <- nrow(ct)
  }
  add_ss(model_id, variant, d, np)
}

# ============================================================================
# Counting-process data for Cox models (B-E)
# ============================================================================
mk_cp <- function(d) {
  d <- d[order(d$player_id, d$calendar_time), ]
  d$tstart <- d$calendar_time - 1
  d$tstop  <- d$calendar_time
  entry <- tapply(d$calendar_time, d$player_id, min)
  d$entry <- entry[as.character(d$player_id)]
  d$gapstop <- ifelse(d$prev_episode_count > 0,
                      d$days_since_last_episode,
                      d$calendar_time - d$entry)
  d$gapstart <- d$gapstop - 1
  d$enum <- d$prev_episode_count
  d
}
cox_rhs <- function(wcol)
  paste0("acute_load_7d_wp_z * ", wcol,
         " + chronic_load_28d_wp_z + prev_episode_ever + calendar_time + team + season")

extract_cox <- function(fit, d, variant, model_id, role, note) {
  cs <- coef(summary(fit))
  se_col <- if ("robust se" %in% colnames(cs)) "robust se" else "se(coef)"
  dropped <- is.na(cs[, "coef"])
  if (any(dropped))
    add_diag(model_id, variant, "cox_terms_dropped_aliased",
             paste(rownames(cs)[dropped], collapse = " || "))
  OR <- exp(cs[, "coef"])
  CI_lo <- exp(cs[, "coef"] - 1.96 * cs[, se_col])
  CI_hi <- exp(cs[, "coef"] + 1.96 * cs[, se_col])
  pv <- cs[, grep("^Pr", colnames(cs))]
  pv[dropped] <- NA
  data.frame(
    analysis_role = role, model_id = model_id, wellness_variant = variant,
    term = rownames(cs), OR = OR,
    CI_low = CI_lo, CI_high = CI_hi,
    p = pv, se = cs[, se_col],
    converged = TRUE, optimizer = "coxph",
    n = nrow(d), players = length(unique(d$player_id)), events = sum(d$onset_day),
    notes = note, stringsAsFactors = FALSE)
}

run_cox <- function(d, variant, model_id, role, surv_expr, extra_rhs, note) {
  wcol <- WELL[[variant]]
  if (already_done(model_id, variant)) {
    log_msg("skip (resume): ", model_id, " / ", variant)
    return(invisible(NULL))
  }
  f <- as.formula(paste(surv_expr, "~", cox_rhs(wcol),
                        if (nzchar(extra_rhs)) paste("+", extra_rhs) else ""))
  warns <- character(0)
  fit <- tryCatch(
    withCallingHandlers(
      coxph(f, data = d, cluster = player_id),
      warning = function(w) { warns <<- c(warns, conditionMessage(w))
                              invokeRestart("muffleWarning") }),
    error = function(e) e)
  if (inherits(fit, "error")) {
    add_inventory(model_id, variant, paste(deparse(f), collapse = " "), "CC counting-process", "FAILED",
                  conditionMessage(fit))
    add_diag(model_id, variant, "cox_error", conditionMessage(fit))
    return(invisible(NULL))
  }
  if (length(warns))
    add_diag(model_id, variant, "cox_warnings",
             paste(unique(warns), collapse = " || "))
  add_diag(model_id, variant, "possible_separation",
           any(grepl("beta may be infinite", warns)))
  add_inventory(model_id, variant, paste(deparse(f), collapse = " "),
                "CC counting-process", "OK")
  add_results(extract_cox(fit, d, variant, model_id, role, note))
  add_ss(model_id, variant, d, length(coef(fit)))
  add_diag(model_id, variant, "cox_converged", !is.null(fit$coef))
}

# ============================================================================
# Model F — Firth (logistf); cluster-bootstrap SEs added by 05 (firth_boot)
# ============================================================================
run_firth <- function(d, variant, role, model_id = "F") {
  if (already_done(model_id, variant)) {
    log_msg("skip (resume): ", model_id, " / ", variant)
    return(invisible(NULL))
  }
  wcol <- WELL[[variant]]
  f <- mk_formula(wcol, TRUE, TRUE)
  fit <- tryCatch(logistf(f, data = d), error = function(e) e)
  if (inherits(fit, "error")) {
    add_inventory(model_id, variant, paste(deparse(f), collapse = " "), "CC", "FAILED", conditionMessage(fit))
    return(invisible(NULL))
  }
  ci_lo <- fit$ci.lower
  ci_hi <- fit$ci.upper
  terms <- names(fit$coefficients)
  if (is.null(ci_lo) || is.null(ci_hi)) {
    ci_lo <- rep(NA_real_, length(terms))
    ci_hi <- rep(NA_real_, length(terms))
  }
  add_results(data.frame(
    analysis_role = role, model_id = model_id, wellness_variant = variant,
    term = terms, OR = exp(fit$coefficients),
    CI_low = exp(ci_lo), CI_high = exp(ci_hi),
    p = fit$prob, se = NA_real_, converged = TRUE,
    optimizer = "logistf (profile-likelihood CI shown; cluster-bootstrap CI in firth_boot rows)",
    n = nrow(d), players = length(unique(d$player_id)), events = sum(d$onset_day),
    notes = "Firth penalised logistic; SE/CI per SAP via player-cluster bootstrap B=2000",
    stringsAsFactors = FALSE))
  add_inventory(model_id, variant, paste(deparse(f), collapse = " "), "CC",
                "OK (logistf point estimates; bootstrap CI from 05_firth_boot)")
  add_ss(model_id, variant, d, length(fit$coefficients))
  # save design for Python-side bootstrap validation
  invisible(fit)
}

# ============================================================================
# RUN: Models A, B, C, D, E, F x 3 wellness variants
# ============================================================================
cc <- setNames(lapply(names(WELL), function(v) cc_sample(md, WELL[[v]])), names(WELL))
for (v in names(WELL))
  log_msg("CC sample [", v, "]: n=", nrow(cc[[v]]), " events=",
          sum(cc[[v]]$onset_day), " players=", length(unique(cc[[v]]$player_id)))

for (v in names(WELL)) {
  role <- if (v == "soreness") "PRIMARY" else "SECONDARY_wellness_variant"
  log_msg("=== wellness variant: ", v, " ===")
  # separation diagnostics on this CC sample (data facts, recorded per SAP
  # reporting rules: failed/boundary behaviour must be documented)
  .d <- cc[[v]]
  for (.lv in levels(.d$team))
    add_diag("DATA", v, paste0("cc_events_", .lv),
             paste0(sum(.d$onset_day[.d$team == .lv]), "/",
                    sum(.d$team == .lv)))
  for (.lv in levels(.d$season))
    add_diag("DATA", v, paste0("cc_events_season", .lv),
             paste0(sum(.d$onset_day[.d$season == .lv]), "/",
                    sum(.d$season == .lv)))
  run_A(cc[[v]], v, role)
  cp <- mk_cp(cc[[v]])
  run_cox(cp, v, "B", "KEY_SENSITIVITY", "Surv(tstart, tstop, onset_day)",
          "", "Andersen-Gill; robust sandwich SE cluster(player)")
  run_cox(cp, v, "C", "SENSITIVITY", "Surv(tstart, tstop, onset_day)",
          "strata(enum)", "PWP total-time, strata by event order; cluster(player) CRVE")
  run_cox(cp, v, "D", "SENSITIVITY", "Surv(gapstart, gapstop, onset_day)",
          "strata(enum)", "PWP gap-time, strata by event order; cluster(player) CRVE")
  # E: shared frailty (gamma), coxme fallback
  if (already_done("E", v)) {
    log_msg("skip (resume): E / ", v)
  } else {
  wcol <- WELL[[v]]
  fE <- as.formula(paste0("Surv(tstart, tstop, onset_day) ~ ", cox_rhs(wcol),
                          " + frailty(player_id)"))
  warnsE <- character(0)
  fitE <- tryCatch(
    withCallingHandlers(
      coxph(fE, data = cp),
      warning = function(w) { warnsE <<- c(warnsE, conditionMessage(w))
                              invokeRestart("muffleWarning") }),
    error = function(e) e)
  if (inherits(fitE, "error")) {
    add_diag("E", v, "frailty_error", conditionMessage(fitE))
    fEm <- as.formula(paste0("Surv(tstart, tstop, onset_day) ~ ",
                             cox_rhs(wcol), " + (1 | player_id)"))
    fitE <- tryCatch(coxme::coxme(fEm, data = cp), error = function(e) e)
    if (inherits(fitE, "error")) {
      add_inventory("E", v, "frailty + coxme", "CC", "FAILED",
                    conditionMessage(fitE))
    } else {
      add_inventory("E", v, paste(deparse(fEm), collapse = " "), "CC",
                    "OK (coxme fallback)")
      sm <- coef(summary(fitE))
      add_results(data.frame(
        analysis_role = "SENSITIVITY", model_id = "E", wellness_variant = v,
        term = rownames(sm), OR = exp(sm[, "coef"]),
        CI_low = exp(sm[, "coef"] - 1.96 * sm[, "se(coef)"]),
        CI_high = exp(sm[, "coef"] + 1.96 * sm[, "se(coef)"]),
        p = sm[, "p"], se = sm[, "se(coef)"], converged = TRUE,
        optimizer = "coxme (frailty() failed — see diagnostics)",
        n = nrow(cp), players = length(unique(cp$player_id)),
        events = sum(cp$onset_day),
        notes = paste0("coxme fallback; player intercept var=",
                       signif(coxme::VarCorr(fitE)$player_id, 4)),
        stringsAsFactors = FALSE))
      add_ss("E", v, cp, length(fitE$coefficients))
      add_diag("E", v, "frailty_variance", coxme::VarCorr(fitE)$player_id)
    }
  } else {
    if (length(warnsE))
      add_diag("E", v, "frailty_warnings",
               paste(unique(warnsE), collapse = " || "))
    fvar <- tryCatch({
      fv <- fitE$history$frailty$history
      if (!is.null(fv) && "variance" %in% colnames(fv))
        tail(fv[, "variance"], 1) else NA_real_
    }, error = function(e) NA_real_)
    add_inventory("E", v, paste(deparse(fE), collapse = " "),
                  "CC counting-process", "OK (gamma frailty)")
    resE <- extract_cox(fitE, cp, v, "E", "SENSITIVITY",
                        paste0("shared gamma frailty(player); frailty var=",
                               signif(fvar, 4)))
    resE <- resE[!grepl("frailty\\(", resE$term), ]
    add_results(resE)
    add_ss("E", v, cp, length(coef(fitE)))
    add_diag("E", v, "frailty_variance", fvar)
  }
  }
  run_firth(cc[[v]], v, "SMALL_SAMPLE_SENSITIVITY")
}

# ============================================================================
# Sensitivity analyses (primary soreness formula, Model A machinery)
# ============================================================================
HIGH_PLAYER <- "TeamA-4051bba7-1170-4c43-b912-8c38815a7625"  # 45 episodes (player_event_distribution.csv)

# S1a/S1b: washout 3d / 14d (datasets rebuilt by 05 prep from episode_inventory)
for (w in c(3, 14)) {
  f <- file.path(OUT, paste0("sens_washout", w, "d.csv"))
  if (!file.exists(f)) { add_inventory(paste0("S1_washout", w), "soreness", "",
      "rebuilt risk set", "SKIPPED", "prep dataset missing"); next }
  dw <- read.csv(f, stringsAsFactors = FALSE)
  dw$date <- as.Date(dw$date); dw$team <- factor(dw$team)
  dw$season <- factor(dw$season); dw$player_id <- factor(dw$player_id)
  d <- cc_sample(dw, WELL[["soreness"]])
  log_msg("S1 washout ", w, "d: n=", nrow(d), " events=", sum(d$onset_day))
  run_A(d, "soreness", "SENSITIVITY", paste0("S1_washout", w, "d"))
}

# S2: risk-set recovery rule end+1+washout
d2 <- cc_sample(md[md$at_risk_sens_end_plus_washout == 1, ], WELL[["soreness"]])
log_msg("S2 end+1+washout: n=", nrow(d2), " events=", sum(d2$onset_day))
run_A(d2, "soreness", "SENSITIVITY", "S2_end_plus_washout")

# S3: ACWR replacing acute load (prep-added acwr_7_28_wp_z)
facwr <- file.path(OUT, "sens_acwr.csv")
if (file.exists(facwr)) {
  da <- read.csv(facwr, stringsAsFactors = FALSE)
  da$date <- as.Date(da$date); da$team <- factor(da$team)
  da$season <- factor(da$season); da$player_id <- factor(da$player_id)
  vars_a <- c("onset_day", "acwr_7_28_wp_z", "soreness_burden_recent3_wp_z",
              "chronic_load_28d_wp_z", "prev_episode_ever", "calendar_time",
              "team", "season", "player_id", "date", "prev_episode_count")
  d3 <- da[complete.cases(da[, vars_a]), ]
  # swap acute -> acwr inside the same machinery via a renamed column copy
  d3$acute_load_7d_wp_z <- d3$acwr_7_28_wp_z
  log_msg("S3 ACWR: n=", nrow(d3), " events=", sum(d3$onset_day))
  run_A(d3, "soreness", "SENSITIVITY", "S3_ACWR_replaces_acute")
  add_diag("S3_ACWR_replaces_acute", "soreness", "note",
           "acwr_7_28_wp_z substituted for acute_load_7d_wp_z (incl. interaction); chronic retained per SAP 'replacing acute load'")
} else add_inventory("S3_ACWR", "soreness", "", "", "SKIPPED", "sens_acwr.csv missing")

# S4: strict lag1 wellness (soreness_burden_wp_z = z of soreness_burden_lag1)
WELL_SAVE <- WELL
WELL[["soreness"]] <- "soreness_burden_wp_z"
d4 <- cc_sample(md, "soreness_burden_wp_z")
log_msg("S4 strict lag1: n=", nrow(d4), " events=", sum(d4$onset_day))
run_A(d4, "soreness", "SENSITIVITY", "S4_strict_lag1_wellness")
WELL <- WELL_SAVE

# S5: exclude highest contributor (45-episode player)
d5 <- cc_sample(md[md$player_id != HIGH_PLAYER, ], WELL[["soreness"]])
log_msg("S5 exclude high contributor: n=", nrow(d5), " events=", sum(d5$onset_day))
run_A(d5, "soreness", "SENSITIVITY", "S5_exclude_high_contributor")

# ============================================================================
# IPW sensitivity: stabilised-weighted marginal logit + player CRVE
# (weights from 05_bootstrap_and_ipw.py ipw stage; observation model
#  reproduces 03_missingness_ipw.py)
# ============================================================================
for (v in names(WELL)) {
  if (already_done("IPW", v)) {
    log_msg("skip (resume): IPW / ", v)
    next
  }
  wf <- file.path(OUT, paste0("ipw_weights_", v, ".csv"))
  if (!file.exists(wf)) {
    add_inventory("IPW", v, "", "CC + stabilised IPW", "SKIPPED", "weights csv missing")
    next
  }
  w <- read.csv(wf, stringsAsFactors = FALSE)
  d <- cc[[v]]
  key <- paste(d$player_id, d$date)
  wkey <- paste(w$player_id, w$date)
  d$ipw <- w$w_stab_trunc[match(key, wkey)]
  d <- d[!is.na(d$ipw), ]
  f <- mk_formula(WELL[[v]], TRUE, TRUE)
  g <- tryCatch(glm(f, data = d, family = binomial, weights = ipw),
                error = function(e) e)
  if (inherits(g, "error")) {
    add_inventory("IPW", v, paste(deparse(f), collapse = " "), "weighted CC", "FAILED", conditionMessage(g))
    next
  }
  V <- tryCatch(vcovCR(g, cluster = d$player_id, type = "CR2"), error = function(e) e)
  if (inherits(V, "error")) {
    add_inventory("IPW", v, paste(deparse(f), collapse = " "), "weighted CC", "FAILED_CRVE",
                  conditionMessage(V)); next
  }
  ct <- coeftest(g, vcov. = V)
  add_inventory("IPW", v, paste(deparse(f), collapse = " "), "CC + stabilised IPW (1/99 trunc)", "OK")
  add_results(data.frame(
    analysis_role = "SENSITIVITY_IPW", model_id = "IPW", wellness_variant = v,
    term = rownames(ct), OR = exp(ct[, 1]),
    CI_low = exp(ct[, 1] - 1.96 * ct[, 2]), CI_high = exp(ct[, 1] + 1.96 * ct[, 2]),
    p = ct[, 4], se = ct[, 2], converged = TRUE,
    optimizer = "glm binomial weighted + clubSandwich CR2 cluster(player)",
    n = nrow(d), players = length(unique(d$player_id)), events = sum(d$onset_day),
    notes = "stabilised IPW marginal logit; compare with complete-case Model A",
    stringsAsFactors = FALSE))
  add_ss("IPW", v, d, nrow(ct))
  ess <- sum(d$ipw)^2 / sum(d$ipw^2)
  add_diag("IPW", v, "ESS_truncated", round(ess, 1))
  add_diag("IPW", v, "ESS_over_n", round(ess / nrow(d), 3))
  add_diag("IPW", v, "max_weight", round(max(d$ipw), 3))
}

# ============================================================================
# Session info
# ============================================================================
sink(file.path(OUT, "session_info_R.txt"))
print(sessionInfo())
sink()
log_msg("04_run_reanalysis.R finished.")
