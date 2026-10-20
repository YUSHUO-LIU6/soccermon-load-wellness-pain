#!/usr/bin/env Rscript
# ============================================================================
# run_drop_team.R — Task 9.5 (R2): team-separation targeted sensitivity
# PONE-D-26-31950 (SoccerMon), R2 reproducibility freeze.
# Taxonomy: R2_REVIEWER_REQUESTED (Reviewer 4 #7).
#
# On the IDENTICAL primary soreness complete-case sample as R1
# (n=19,758; players=49; events=28), re-fits the Model A machinery and
# Model F WITHOUT the team covariate, applying R1's exact diagnostic /
# fallback ladder (04_run_reanalysis.R: fit_modelA), to test whether
# removing team resolves the TeamB zero-event separation and restores the
# full interaction GLMM.
#
# Inputs  : FR/02_R1_REPRODUCTION/r1_sandbox/07_ANALYSIS_OUTPUTS/modeling_dataset.csv
#           FR/02_R1_REPRODUCTION/r1_sandbox/07_ANALYSIS_OUTPUTS/RUN_R2_REPRO/master_results.csv
# Outputs : FR/09_TEAM_SENSITIVITY/drop_team_model_rows.csv   (all fits incl. failures)
#           FR/09_TEAM_SENSITIVITY/drop_team_diagnostics.csv  (ladder diagnostics)
# ============================================================================

suppressPackageStartupMessages({
  library(lme4)
  library(clubSandwich)
  library(sandwich)
  library(lmtest)
  library(logistf)
})

SEED <- 20260722
set.seed(SEED)

FR  <- "D:/PLOS_ONE_R1_WORK/R2_FINAL_ANALYSIS_FREEZE"
SAN <- file.path(FR, "02_R1_REPRODUCTION", "r1_sandbox")
OUT <- file.path(FR, "09_TEAM_SENSITIVITY")
dir.create(OUT, recursive = TRUE, showWarnings = FALSE)
LOGF <- file.path(FR, "18_LOGS", "workstream_team_season.log")

log_msg <- function(...) {
  txt <- paste0(format(Sys.time(), "%Y-%m-%d %H:%M:%S"), " | [9.5 drop_team] ",
                paste(..., collapse = ""))
  cat(txt, "\n")
  cat(txt, "\n", file = LOGF, append = TRUE)
}

res_file  <- file.path(OUT, "drop_team_model_rows.csv")
diag_file <- file.path(OUT, "drop_team_diagnostics.csv")
for (f in c(res_file, diag_file)) if (file.exists(f)) file.remove(f)

append_csv <- function(df, path)
  write.table(df, path, sep = ",", row.names = FALSE, quote = TRUE,
              append = file.exists(path), col.names = !file.exists(path))

add_diag <- function(model_id, diagnostic, value)
  append_csv(data.frame(model_id = model_id, wellness_variant = "soreness",
                        diagnostic = diagnostic, value = as.character(value),
                        stringsAsFactors = FALSE), diag_file)

# ---- data: identical CC sample to R1 --------------------------------------
md <- read.csv(file.path(SAN, "07_ANALYSIS_OUTPUTS", "modeling_dataset.csv"),
               stringsAsFactors = FALSE)
md$date <- as.Date(md$date)
md$team   <- factor(md$team)
md$season <- factor(md$season)
md$player_id <- factor(md$player_id)

wcol <- "soreness_burden_recent3_wp_z"
cc_vars <- c("onset_day", "acute_load_7d_wp_z", wcol, "chronic_load_28d_wp_z",
             "prev_episode_ever", "calendar_time", "team", "season",
             "player_id", "date", "prev_episode_count")
d <- md[complete.cases(md[, cc_vars]), ]
log_msg("CC soreness sample: n=", nrow(d), " players=", length(unique(d$player_id)),
        " events=", sum(d$onset_day),
        " event_players=", length(unique(d$player_id[d$onset_day == 1])))
stopifnot(nrow(d) == 19758, sum(d$onset_day) == 28, length(unique(d$player_id)) == 49)
add_diag("DATA", "cc_events_TeamA",
         paste0(sum(d$onset_day[d$team == "TeamA"]), "/", sum(d$team == "TeamA")))
add_diag("DATA", "cc_events_TeamB",
         paste0(sum(d$onset_day[d$team == "TeamB"]), "/", sum(d$team == "TeamB")))

# formula WITHOUT team (rest identical to R1 mk_formula)
mk_formula_noteam <- function(interaction = TRUE, chronic = TRUE) {
  rhs <- if (interaction)
    paste0("acute_load_7d_wp_z * ", wcol) else
    paste0("acute_load_7d_wp_z + ", wcol)
  if (chronic) rhs <- paste0(rhs, " + chronic_load_28d_wp_z")
  as.formula(paste0("onset_day ~ ", rhs,
    " + prev_episode_ever + calendar_time + season"))
}

add_result_row <- function(model_id, term, est, se, p, ci_lo, ci_hi, converged,
                           optimizer, notes, separation_flag) {
  append_csv(data.frame(
    model_id = model_id, wellness_variant = "soreness", term = term,
    OR = exp(est), CI_low = exp(ci_lo), CI_high = exp(ci_hi), p = p, se = se,
    converged = converged, separation_flag = separation_flag,
    n = nrow(d), players = length(unique(d$player_id)), events = sum(d$onset_day),
    taxonomy = "R2_REVIEWER_REQUESTED", optimizer = optimizer, notes = notes,
    stringsAsFactors = FALSE), res_file)
}

# ---- A_drop_team: R1 fallback ladder minus team ------------------------------
ctrl <- glmerControl(optimizer = "bobyqa", optCtrl = list(maxfun = 2e5))
lvls <- list(
  list(f = mk_formula_noteam(TRUE, TRUE),   tag = "full"),
  list(f = mk_formula_noteam(FALSE, TRUE),  tag = "no_interaction"),
  list(f = mk_formula_noteam(FALSE, FALSE), tag = "no_interaction_no_chronic"))

final <- NULL
for (lv in lvls) {
  warns <- character(0)
  f_re <- update(lv$f, . ~ . + (1 | player_id))
  f_str <- paste(deparse(f_re), collapse = " ")
  fit <- tryCatch(
    withCallingHandlers(
      glmer(f_re, data = d, family = binomial, nAGQ = 1, control = ctrl),
      warning = function(w) { warns <<- c(warns, conditionMessage(w))
                              invokeRestart("muffleWarning") }),
    error = function(e) e)
  if (inherits(fit, "error")) {
    add_diag("A_drop_team", paste0("glmer_error_level_", lv$tag), conditionMessage(fit))
    append_csv(data.frame(model_id = "A_drop_team", wellness_variant = "soreness",
      term = paste0("LEVEL_", lv$tag, " (FAILED)"), OR = NA, CI_low = NA, CI_high = NA,
      p = NA, se = NA, converged = FALSE, separation_flag = NA,
      n = nrow(d), players = length(unique(d$player_id)), events = sum(d$onset_day),
      taxonomy = "R2_REVIEWER_REQUESTED", optimizer = "glmer bobyqa maxfun2e5",
      notes = paste0("glmer error: ", conditionMessage(fit), " | formula: ", f_str),
      stringsAsFactors = FALSE), res_file)
    next
  }
  conv <- length(fit@optinfo$conv$lme4) == 0
  sing <- isSingular(fit, tol = 1e-4)
  sm <- summary(fit)$coefficients
  separation <- any(abs(sm[, "Estimate"]) > 10)
  add_diag("A_drop_team", paste0("formula_", lv$tag), f_str)
  add_diag("A_drop_team", paste0("converged_", lv$tag), conv)
  add_diag("A_drop_team", paste0("singular_", lv$tag), sing)
  add_diag("A_drop_team", paste0("separation_", lv$tag), separation)
  if (length(warns))
    add_diag("A_drop_team", paste0("warnings_", lv$tag),
             paste(unique(warns), collapse = " || "))
  if (conv && !separation) {
    final <- list(kind = "glmer", fit = fit, formula = f_str, fallback = lv$tag,
                  singular = sing)
    log_msg("A_drop_team: accepted level '", lv$tag, "' (glmer, no separation)")
    for (i in seq_len(nrow(sm)))
      add_result_row("A_drop_team", rownames(sm)[i], sm[i, "Estimate"],
                     sm[i, "Std. Error"], sm[i, "Pr(>|z|)"],
                     sm[i, "Estimate"] - 1.96 * sm[i, "Std. Error"],
                     sm[i, "Estimate"] + 1.96 * sm[i, "Std. Error"],
                     TRUE, "glmer nAGQ=1 bobyqa maxfun2e5",
                     paste0("glmer (team removed); singular=", sing,
                            "; fallback_level=", lv$tag, "; formula: ", f_str),
                     FALSE)
    break
  }
  add_diag("A_drop_team", "fallback_trigger",
           paste0(lv$tag, ": converged=", conv, " separation=", separation))
  # record rejected-level coefficients too (full transparency, esp. failures)
  for (i in seq_len(nrow(sm)))
    add_result_row(paste0("A_drop_team_REJECTED_", lv$tag), rownames(sm)[i],
                   sm[i, "Estimate"], sm[i, "Std. Error"], sm[i, "Pr(>|z|)"],
                   sm[i, "Estimate"] - 1.96 * sm[i, "Std. Error"],
                   sm[i, "Estimate"] + 1.96 * sm[i, "Std. Error"],
                   conv, "glmer nAGQ=1 bobyqa maxfun2e5",
                   paste0("REJECTED ladder level '", lv$tag, "' (converged=", conv,
                          ", separation=", separation, ", singular=", sing,
                          "); recorded for transparency; formula: ", f_str),
                   separation)
}

if (is.null(final)) {
  # population-average fallback (minus team), as in R1
  f_pa <- mk_formula_noteam(FALSE, TRUE)
  f_str <- paste(deparse(f_pa), collapse = " ")
  g <- tryCatch(glm(f_pa, data = d, family = binomial), error = function(e) e)
  if (inherits(g, "error")) {
    add_diag("A_drop_team", "PA_glm_error", conditionMessage(g))
  } else {
    V <- tryCatch(vcovCR(g, cluster = d$player_id, type = "CR2"), error = function(e) e)
    if (inherits(V, "error")) {
      add_diag("A_drop_team", "PA_CRVE_error", conditionMessage(V))
    } else {
      ct <- coeftest(g, vcov. = V)
      sep_pa <- any(abs(ct[, 1]) > 10)
      add_diag("A_drop_team", "separation_population_average", sep_pa)
      for (i in seq_len(nrow(ct)))
        add_result_row("A_drop_team", rownames(ct)[i], ct[i, 1], ct[i, 2], ct[i, 4],
                       ct[i, 1] - 1.96 * ct[i, 2], ct[i, 1] + 1.96 * ct[i, 2],
                       TRUE, "glm+clubSandwich_CR2",
                       paste0("population-average fallback minus team; player CRVE",
                              if (sep_pa) "; separation present (|beta|>10)" else ""),
                       sep_pa)
      log_msg("A_drop_team: PA fallback used (sep=", sep_pa, ")")
    }
  }
}

# ---- F_drop_team: logistf minus team -----------------------------------------
f_firth <- mk_formula_noteam(TRUE, TRUE)
f_str <- paste(deparse(f_firth), collapse = " ")
ff <- tryCatch(logistf(f_firth, data = d), error = function(e) e)
if (inherits(ff, "error")) {
  add_diag("F_drop_team", "logistf_error", conditionMessage(ff))
  append_csv(data.frame(model_id = "F_drop_team", wellness_variant = "soreness",
    term = "MODEL (FAILED)", OR = NA, CI_low = NA, CI_high = NA, p = NA, se = NA,
    converged = FALSE, separation_flag = NA, n = nrow(d),
    players = length(unique(d$player_id)), events = sum(d$onset_day),
    taxonomy = "R2_REVIEWER_REQUESTED", optimizer = "logistf",
    notes = paste0("logistf error: ", conditionMessage(ff), " | formula: ", f_str),
    stringsAsFactors = FALSE), res_file)
} else {
  ci_lo <- if (is.null(ff$ci.lower)) rep(NA_real_, length(ff$coefficients)) else ff$ci.lower
  ci_hi <- if (is.null(ff$ci.upper)) rep(NA_real_, length(ff$coefficients)) else ff$ci.upper
  for (i in seq_along(ff$coefficients))
    add_result_row("F_drop_team", names(ff$coefficients)[i], ff$coefficients[i],
                   NA, ff$prob[i], ci_lo[i], ci_hi[i], TRUE,
                   "logistf (profile-likelihood CI)",
                   paste0("Firth penalised logistic minus team; profile-likelihood CI; formula: ", f_str),
                   any(abs(ff$coefficients) > 10))
  log_msg("F_drop_team: logistf OK; interaction OR=",
          round(exp(ff$coefficients[paste0("acute_load_7d_wp_z:", wcol)]), 4))
}

log_msg("run_drop_team.R finished; rows in ", basename(res_file))
