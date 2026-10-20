#!/usr/bin/env Rscript
# ============================================================================
# run_backwardz_models.R — Task 9.7 (R2): backward-looking (expanding-history)
# within-player standardization sensitivity.
# PONE-D-26-31950 (SoccerMon), R2 reproducibility freeze.
# Taxonomy: R2_REVIEWER_REQUESTED (manuscript-facing); _r90 fits are
# R2_INTERNAL_QA_ONLY.
#
# Primary soreness interaction model with ALL exposure z-scores replaced by
# expanding-history within-player versions (min 10 prior obs, SD>0):
#   onset_day ~ acute_load_7d_wp_z_hist * soreness_burden_recent3_wp_z_hist +
#     chronic_load_28d_wp_z_hist + prev_episode_ever + calendar_time + team +
#     season
# Complete-case per the new columns (asserted N=19,216, events=27,
# event players=9).
#
# Fits (R1 conventions, 04_run_reanalysis.R fit_modelA / run_firth):
#   soreness: A_hist (glmer ladder), A_hist_dropteam (ladder minus team),
#             F_hist / F_hist_dropteam (logistf)
#   fatigue / readiness: F_hist_dropteam ONLY (minimal directional check;
#             no estimator zoo)
#   QA (_r90 rolling-90-day columns, INTERNAL QA ONLY): A_hist_r90,
#             A_hist_dropteam_r90, F_hist_r90, F_hist_dropteam_r90 (soreness)
#
# Inputs  : FR/11_BACKWARD_STANDARDIZATION/modeling_dataset_backwardz.csv
# Outputs : FR/11_BACKWARD_STANDARDIZATION/BACKWARD_STANDARDIZATION_RESULTS.csv
#           FR/11_BACKWARD_STANDARDIZATION/backwardz_diagnostics.csv
# Log     : FR/18_LOGS/workstream_newmodels.log
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

FR   <- "D:/PLOS_ONE_R1_WORK/R2_FINAL_ANALYSIS_FREEZE"
OUT  <- file.path(FR, "11_BACKWARD_STANDARDIZATION")
LOGF <- file.path(FR, "18_LOGS", "workstream_newmodels.log")

log_msg <- function(...) {
  txt <- paste0(format(Sys.time(), "%Y-%m-%d %H:%M:%S"), " | [9.7 backwardz] ",
                paste(..., collapse = ""))
  cat(txt, "\n")
  cat(txt, "\n", file = LOGF, append = TRUE)
}

res_file  <- file.path(OUT, "BACKWARD_STANDARDIZATION_RESULTS.csv")
diag_file <- file.path(OUT, "backwardz_diagnostics.csv")
# Resume support: keep existing fit rows, strip derived CMP_*/SUMMARY rows so
# they are recomputed at the end of this run.
if (file.exists(res_file)) {
  .rr <- read.csv(res_file, stringsAsFactors = FALSE)
  .keep <- !(grepl("^CMP_", .rr$model_id) | .rr$model_id == "SUMMARY")
  write.csv(.rr[.keep, ], res_file, row.names = FALSE, quote = TRUE)
  log_msg("RESUME: kept ", sum(.keep), " existing fit rows; stripped ",
          sum(!.keep), " derived CMP/SUMMARY rows")
}

append_csv <- function(df, path)
  write.table(df, path, sep = ",", row.names = FALSE, quote = TRUE,
              append = file.exists(path), col.names = !file.exists(path))

add_diag <- function(model_id, variant, diagnostic, value)
  append_csv(data.frame(model_id = model_id, wellness_variant = variant,
                        diagnostic = diagnostic, value = as.character(value),
                        stringsAsFactors = FALSE), diag_file)

# --- resume helpers ----------------------------------------------------------
level_done <- function(model_id, variant, tag) {
  if (!file.exists(diag_file)) return(FALSE)
  dd <- tryCatch(read.csv(diag_file, stringsAsFactors = FALSE),
                 error = function(e) NULL)
  if (is.null(dd)) return(FALSE)
  any(dd$model_id == model_id & dd$wellness_variant == variant &
        dd$diagnostic == paste0("converged_", tag)) ||
    any(dd$model_id == model_id & dd$wellness_variant == variant &
          dd$diagnostic == paste0("glmer_error_level_", tag))
}
existing_fit <- function(model_id, variant) {
  if (!file.exists(res_file)) return(NULL)
  rr <- tryCatch(read.csv(res_file, stringsAsFactors = FALSE),
                 error = function(e) NULL)
  if (is.null(rr)) return(NULL)
  hit <- rr$notes[rr$model_id == model_id & rr$wellness_variant == variant &
                    !is.na(rr$OR)]
  if (length(hit) == 0) return(NULL)
  kind <- if (grepl("population-average fallback", hit[1])) "glm_crve" else "glmer"
  m <- regmatches(hit[1], regexpr("fallback_level=[a-z_]+", hit[1]))
  fb <- if (length(m) > 0 && nzchar(m)) sub("fallback_level=", "", m) else
    "population_average_crve"
  list(kind = kind, fallback = fb)
}

RES_COLS <- c("model_id", "wellness_variant", "term", "OR", "CI_low", "CI_high",
              "p", "se", "converged", "separation_flag", "n", "players",
              "events", "formula", "taxonomy", "notes")

add_row <- function(model_id, variant, term, OR, CI_low, CI_high, p, se,
                    converged, separation_flag, n, players, events, formula,
                    notes, taxonomy = "R2_REVIEWER_REQUESTED") {
  df <- data.frame(model_id = model_id, wellness_variant = variant, term = term,
                   OR = OR, CI_low = CI_low, CI_high = CI_high, p = p, se = se,
                   converged = converged, separation_flag = separation_flag,
                   n = n, players = players, events = events, formula = formula,
                   taxonomy = taxonomy, notes = notes, stringsAsFactors = FALSE)
  append_csv(df[, RES_COLS], res_file)
}

# ---- data ------------------------------------------------------------------
md <- read.csv(file.path(OUT, "modeling_dataset_backwardz.csv"),
               stringsAsFactors = FALSE)
md$date <- as.Date(md$date)
md$team      <- factor(md$team)
md$season    <- factor(md$season)
md$player_id <- factor(md$player_id)
log_msg("backwardz dataset: ", nrow(md), " rows; onset_day positives = ",
        sum(md$onset_day), "; players = ", length(unique(md$player_id)))

WELL_HIST <- c(soreness  = "soreness_burden_recent3_wp_z_hist",
               fatigue   = "fatigue_burden_recent3_wp_z_hist",
               readiness = "readiness_deficit_recent3_wp_z_hist")
ACUTE  <- "acute_load_7d_wp_z_hist"
CHRON  <- "chronic_load_28d_wp_z_hist"

mk_cc <- function(acute_col, wcol, chron_col) {
  vars <- c("onset_day", acute_col, wcol, chron_col, "prev_episode_ever",
            "calendar_time", "team", "season", "player_id", "date",
            "prev_episode_count")
  md[complete.cases(md[, vars]), ]
}

mkf <- function(acute_col, wcol, chron_col, interaction = TRUE,
                chronic = TRUE, team = TRUE) {
  rhs <- if (interaction)
    paste0(acute_col, " * ", wcol) else paste0(acute_col, " + ", wcol)
  if (chronic) rhs <- paste0(rhs, " + ", chron_col)
  as.formula(paste0("onset_day ~ ", rhs, " + prev_episode_ever + calendar_time + ",
                    if (team) "team + season" else "season"))
}

# ---- glmer fallback ladder (R1 fit_modelA conventions) ---------------------
fit_ladder <- function(model_id, variant, d, acute_col, wcol, chron_col,
                       team = TRUE, taxonomy = "R2_REVIEWER_REQUESTED") {
  ex <- existing_fit(model_id, variant)
  if (!is.null(ex)) {
    log_msg(model_id, " [", variant, "]: RESUME — already fitted (kind=",
            ex$kind, ", fallback=", ex$fallback, "); skipping")
    return(ex)
  }
  n_cc <- nrow(d); pl_cc <- length(unique(d$player_id)); ev_cc <- sum(d$onset_day)
  ctrl <- glmerControl(optimizer = "bobyqa", optCtrl = list(maxfun = 2e5))
  lvls <- list(
    list(f = mkf(acute_col, wcol, chron_col, TRUE, TRUE, team),   tag = "full"),
    list(f = mkf(acute_col, wcol, chron_col, FALSE, TRUE, team),  tag = "no_interaction"),
    list(f = mkf(acute_col, wcol, chron_col, FALSE, FALSE, team), tag = "no_interaction_no_chronic"))
  for (lv in lvls) {
    if (level_done(model_id, variant, lv$tag)) {
      log_msg(model_id, " [", variant, "]: RESUME — level '", lv$tag,
              "' already processed; skipping refit")
      next
    }
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
      add_diag(model_id, variant, paste0("glmer_error_level_", lv$tag), conditionMessage(fit))
      add_row(paste0(model_id, "_REJECTED_", lv$tag), variant, "LEVEL (glmer ERROR)",
              NA, NA, NA, NA, NA, FALSE, NA, n_cc, pl_cc, ev_cc, f_str,
              paste0("glmer error at ladder level '", lv$tag, "': ",
                     conditionMessage(fit)), taxonomy)
      next
    }
    conv <- length(fit@optinfo$conv$lme4) == 0
    sing <- isSingular(fit, tol = 1e-4)
    sm <- summary(fit)$coefficients
    separation <- any(abs(sm[, "Estimate"]) > 10)
    add_diag(model_id, variant, paste0("formula_", lv$tag), f_str)
    add_diag(model_id, variant, paste0("converged_", lv$tag), conv)
    add_diag(model_id, variant, paste0("singular_", lv$tag), sing)
    add_diag(model_id, variant, paste0("separation_", lv$tag), separation)
    if (length(warns))
      add_diag(model_id, variant, paste0("warnings_", lv$tag),
               paste(unique(warns), collapse = " || "))
    if (conv && !separation) {
      log_msg(model_id, " [", variant, "]: accepted ladder level '", lv$tag, "'")
      for (i in seq_len(nrow(sm)))
        add_row(model_id, variant, rownames(sm)[i], exp(sm[i, "Estimate"]),
                exp(sm[i, "Estimate"] - 1.96 * sm[i, "Std. Error"]),
                exp(sm[i, "Estimate"] + 1.96 * sm[i, "Std. Error"]),
                sm[i, "Pr(>|z|)"], sm[i, "Std. Error"], TRUE, FALSE,
                n_cc, pl_cc, ev_cc, f_str,
                paste0("glmer nAGQ=1 bobyqa maxfun2e5", if (!team) " (team removed)" else "",
                       "; singular=", sing, "; fallback_level=", lv$tag,
                       "; accepted level"), taxonomy)
      return(list(kind = "glmer", fallback = lv$tag))
    }
    add_diag(model_id, variant, "fallback_trigger",
             paste0(lv$tag, ": converged=", conv, " separation=", separation))
    for (i in seq_len(nrow(sm)))
      add_row(paste0(model_id, "_REJECTED_", lv$tag), variant, rownames(sm)[i],
              exp(sm[i, "Estimate"]),
              exp(sm[i, "Estimate"] - 1.96 * sm[i, "Std. Error"]),
              exp(sm[i, "Estimate"] + 1.96 * sm[i, "Std. Error"]),
              sm[i, "Pr(>|z|)"], sm[i, "Std. Error"], conv, separation,
              n_cc, pl_cc, ev_cc, f_str,
              paste0("REJECTED ladder level '", lv$tag, "' (converged=", conv,
                     ", separation=", separation, ", singular=", sing,
                     "); recorded for transparency"), taxonomy)
  }
  # population-average fallback (R1): no-interaction glm + clubSandwich CR2
  f_pa <- mkf(acute_col, wcol, chron_col, FALSE, TRUE, team)
  f_str <- paste(deparse(f_pa), collapse = " ")
  g <- tryCatch(glm(f_pa, data = d, family = binomial), error = function(e) e)
  if (inherits(g, "error")) {
    add_diag(model_id, variant, "PA_glm_error", conditionMessage(g))
    add_row(model_id, variant, "MODEL (FAILED)", NA, NA, NA, NA, NA, FALSE, NA,
            n_cc, pl_cc, ev_cc, f_str, paste0("PA glm error: ", conditionMessage(g)), taxonomy)
    return(list(kind = "failed", fallback = "population_average_crve"))
  }
  V <- tryCatch(vcovCR(g, cluster = d$player_id, type = "CR2"), error = function(e) e)
  if (inherits(V, "error")) {
    add_diag(model_id, variant, "PA_CRVE_error", conditionMessage(V))
    add_row(model_id, variant, "MODEL (FAILED_CRVE)", NA, NA, NA, NA, NA, FALSE,
            NA, n_cc, pl_cc, ev_cc, f_str,
            paste0("PA CRVE error: ", conditionMessage(V)), taxonomy)
    return(list(kind = "failed", fallback = "population_average_crve"))
  }
  ct <- coeftest(g, vcov. = V)
  sep_pa <- any(abs(ct[, 1]) > 10)
  add_diag(model_id, variant, "separation_population_average", sep_pa)
  if (sep_pa)
    add_diag(model_id, variant, "separated_terms",
             paste(rownames(ct)[abs(ct[, 1]) > 10], collapse = " || "))
  for (i in seq_len(nrow(ct)))
    add_row(model_id, variant, rownames(ct)[i], exp(ct[i, 1]),
            exp(ct[i, 1] - 1.96 * ct[i, 2]), exp(ct[i, 1] + 1.96 * ct[i, 2]),
            ct[i, 4], ct[i, 2], TRUE, sep_pa, n_cc, pl_cc, ev_cc, f_str,
            paste0("population-average fallback (GLMM separation); player CRVE ",
                   "(glm + clubSandwich CR2)", if (!team) "; team removed" else "",
                   if (sep_pa) "; separation present (|beta|>10) — interpret with Firth" else ""),
            taxonomy)
  log_msg(model_id, " [", variant, "]: PA fallback accepted (sep=", sep_pa, ")")
  list(kind = "glm_crve", fallback = "population_average_crve")
}

# ---- Firth -----------------------------------------------------------------
fit_firth <- function(model_id, variant, d, acute_col, wcol, chron_col,
                      team = TRUE, taxonomy = "R2_REVIEWER_REQUESTED",
                      extra_note = "") {
  if (!is.null(existing_fit(model_id, variant))) {
    log_msg(model_id, " [", variant, "]: RESUME — logistf already fitted; skipping")
    return(invisible(NULL))
  }
  n_cc <- nrow(d); pl_cc <- length(unique(d$player_id)); ev_cc <- sum(d$onset_day)
  f <- mkf(acute_col, wcol, chron_col, TRUE, TRUE, team)
  f_str <- paste(deparse(f), collapse = " ")
  ff <- tryCatch(logistf(f, data = d), error = function(e) e)
  if (inherits(ff, "error")) {
    add_diag(model_id, variant, "logistf_error", conditionMessage(ff))
    add_row(model_id, variant, "MODEL (FAILED)", NA, NA, NA, NA, NA, FALSE, NA,
            n_cc, pl_cc, ev_cc, f_str,
            paste0("logistf error: ", conditionMessage(ff)), taxonomy)
    return(invisible(NULL))
  }
  ci_lo <- if (is.null(ff$ci.lower)) rep(NA_real_, length(ff$coefficients)) else ff$ci.lower
  ci_hi <- if (is.null(ff$ci.upper)) rep(NA_real_, length(ff$coefficients)) else ff$ci.upper
  sep <- any(abs(ff$coefficients) > 10)
  for (i in seq_along(ff$coefficients))
    add_row(model_id, variant, names(ff$coefficients)[i], exp(ff$coefficients[i]),
            exp(ci_lo[i]), exp(ci_hi[i]), ff$prob[i], NA, TRUE, sep,
            n_cc, pl_cc, ev_cc, f_str,
            paste0("Firth penalised logistic (logistf)", if (!team) " minus team" else "",
                   "; profile-likelihood CI", extra_note), taxonomy)
  inter <- paste0(acute_col, ":", wcol)
  log_msg(model_id, " [", variant, "]: logistf OK; interaction OR=",
          round(exp(ff$coefficients[inter]), 4))
}

# ============================================================================
# Soreness — manuscript-facing _hist fits
# ============================================================================
d_s <- mk_cc(ACUTE, WELL_HIST[["soreness"]], CHRON)
n_s <- nrow(d_s); ev_s <- sum(d_s$onset_day)
evp_s <- length(unique(d_s$player_id[d_s$onset_day == 1]))
pl_s <- length(unique(d_s$player_id))
log_msg("CC soreness _hist: n=", n_s, " players=", pl_s, " events=", ev_s,
        " event_players=", evp_s)
stopifnot(n_s == 19216, ev_s == 27, evp_s == 9)
add_diag("DATA", "soreness", "cc_sample_hist",
         sprintf("n=%d players=%d events=%d event_players=%d (asserted 19216/?/27/9)",
                 n_s, pl_s, ev_s, evp_s))
add_diag("DATA", "soreness", "cc_events_TeamA_hist",
         paste0(sum(d_s$onset_day[d_s$team == "TeamA"]), "/", sum(d_s$team == "TeamA")))
add_diag("DATA", "soreness", "cc_events_TeamB_hist",
         paste0(sum(d_s$onset_day[d_s$team == "TeamB"]), "/", sum(d_s$team == "TeamB")))

res_a  <- fit_ladder("A_hist", "soreness", d_s, ACUTE, WELL_HIST[["soreness"]], CHRON, team = TRUE)
res_ad <- fit_ladder("A_hist_dropteam", "soreness", d_s, ACUTE, WELL_HIST[["soreness"]], CHRON, team = FALSE)
fit_firth("F_hist", "soreness", d_s, ACUTE, WELL_HIST[["soreness"]], CHRON, team = TRUE)
fit_firth("F_hist_dropteam", "soreness", d_s, ACUTE, WELL_HIST[["soreness"]], CHRON, team = FALSE)

# ============================================================================
# Fatigue / readiness — drop-team Firth ONLY (minimal directional check)
# ============================================================================
for (v in c("fatigue", "readiness")) {
  d_v <- mk_cc(ACUTE, WELL_HIST[[v]], CHRON)
  log_msg("CC ", v, " _hist: n=", nrow(d_v), " players=",
          length(unique(d_v$player_id)), " events=", sum(d_v$onset_day),
          " event_players=", length(unique(d_v$player_id[d_v$onset_day == 1])))
  add_diag("DATA", v, "cc_sample_hist",
           sprintf("n=%d players=%d events=%d event_players=%d",
                   nrow(d_v), length(unique(d_v$player_id)), sum(d_v$onset_day),
                   length(unique(d_v$player_id[d_v$onset_day == 1]))))
  fit_firth("F_hist_dropteam", v, d_v, ACUTE, WELL_HIST[[v]], CHRON,
            team = FALSE,
            extra_note = "; MINIMAL DIRECTIONAL CHECK ONLY (drop-team Firth; estimator zoo intentionally not recreated for this variant)")
}

# ============================================================================
# INTERNAL QA ONLY: same soreness fits with _r90 columns
# ============================================================================
ACUTE_R90 <- "acute_load_7d_wp_z_r90"
WCOL_R90  <- "soreness_burden_recent3_wp_z_r90"
CHRON_R90 <- "chronic_load_28d_wp_z_r90"
d_r90 <- mk_cc(ACUTE_R90, WCOL_R90, CHRON_R90)
log_msg("CC soreness _r90 (INTERNAL QA ONLY): n=", nrow(d_r90), " players=",
        length(unique(d_r90$player_id)), " events=", sum(d_r90$onset_day),
        " event_players=", length(unique(d_r90$player_id[d_r90$onset_day == 1])))
add_diag("DATA", "soreness", "cc_sample_r90_QA_ONLY",
         sprintf("n=%d players=%d events=%d event_players=%d",
                 nrow(d_r90), length(unique(d_r90$player_id)),
                 sum(d_r90$onset_day),
                 length(unique(d_r90$player_id[d_r90$onset_day == 1]))))
QA_TAX <- "R2_INTERNAL_QA_ONLY"
res_a_r90  <- fit_ladder("A_hist_r90", "soreness", d_r90, ACUTE_R90, WCOL_R90, CHRON_R90, team = TRUE,  taxonomy = QA_TAX)
res_ad_r90 <- fit_ladder("A_hist_dropteam_r90", "soreness", d_r90, ACUTE_R90, WCOL_R90, CHRON_R90, team = FALSE, taxonomy = QA_TAX)
fit_firth("F_hist_r90", "soreness", d_r90, ACUTE_R90, WCOL_R90, CHRON_R90, team = TRUE,  taxonomy = QA_TAX)
fit_firth("F_hist_dropteam_r90", "soreness", d_r90, ACUTE_R90, WCOL_R90, CHRON_R90, team = FALSE, taxonomy = QA_TAX)

# ============================================================================
# Comparison rows vs R1 (delta log-OR for focal terms) + SUMMARY
# ============================================================================
res_df <- read.csv(res_file, stringsAsFactors = FALSE)
get_or <- function(model_id, variant, term) {
  hit <- res_df$OR[res_df$model_id == model_id & res_df$term == term &
                     res_df$wellness_variant == variant]
  if (length(hit) == 0) NA_real_ else hit[1]
}
R1 <- list(
  A  = c(acute = 0.696293594529414, soreness = 0.744836277083393,
         chronic = 0.953461046548104, prev_ep = 6.48630000396862),
  F  = c(acute = 0.599094422804644, soreness = 0.823322219063635,
         chronic = 0.947219920255698, prev_ep = 6.12931772198318,
         inter = 0.629552028809833),
  Adt = c(acute = 0.648180508170986, soreness = 0.816143262679789,
          chronic = 0.881781773388409, inter = 0.693842622800896),
  Fdt = c(acute = 0.705458589333269, soreness = 0.852851943964097,
          chronic = 0.748505371829984, inter = 0.671036174270028))
INTER_H <- paste0(ACUTE, ":", WELL_HIST[["soreness"]])

cmp_row <- function(cmp_id, term_label, or_new, or_ref, ref_name, formula_str) {
  if (is.na(or_new) || is.na(or_ref)) {
    note <- sprintf("%s: delta not estimable (new OR=%s, ref %s OR=%s).",
                    cmp_id,
                    ifelse(is.na(or_new), "NA (term absent at accepted level)", sprintf("%.4f", or_new)),
                    ref_name, ifelse(is.na(or_ref), "NA", sprintf("%.4f", or_ref)))
    add_row(cmp_id, "soreness", term_label, or_new, NA, NA, NA, NA, NA, NA,
            n_s, pl_s, ev_s, formula_str, note)
    return(invisible(NULL))
  }
  dl <- log(or_new) - log(or_ref)
  pct <- if (abs(log(or_ref)) > 1e-8) 100 * dl / abs(log(or_ref)) else NA_real_
  note <- sprintf("%s vs %s: OR %.4f vs %.4f; delta log(OR)=%.4f (%s%% of |log(OR_ref)|). Materiality judged on log(OR) shift and direction, not p-values.",
                  cmp_id, ref_name, or_new, or_ref, dl,
                  ifelse(is.na(pct), "NA", sprintf("%.1f", pct)))
  add_row(cmp_id, "soreness", term_label, or_new, NA, NA, NA, NA, NA, NA,
          n_s, pl_s, ev_s, formula_str, note)
}

f_with_h <- "onset_day ~ acute_load_7d_wp_z_hist * soreness_burden_recent3_wp_z_hist + chronic_load_28d_wp_z_hist + prev_episode_ever + calendar_time + team + season"
f_drop_h <- "onset_day ~ acute_load_7d_wp_z_hist * soreness_burden_recent3_wp_z_hist + chronic_load_28d_wp_z_hist + prev_episode_ever + calendar_time + season (+ (1|player_id) for glmer)"

cmp_row("CMP_A_hist_vs_R1_A", ACUTE,
        get_or("A_hist", "soreness", ACUTE), R1$A[["acute"]], "R1 A (PA fallback, full-period z)", f_with_h)
cmp_row("CMP_A_hist_vs_R1_A", WELL_HIST[["soreness"]],
        get_or("A_hist", "soreness", WELL_HIST[["soreness"]]), R1$A[["soreness"]], "R1 A (PA fallback)", f_with_h)
cmp_row("CMP_A_hist_vs_R1_A", CHRON,
        get_or("A_hist", "soreness", CHRON), R1$A[["chronic"]], "R1 A (PA fallback)", f_with_h)
cmp_row("CMP_A_hist_vs_R1_A", "prev_episode_ever",
        get_or("A_hist", "soreness", "prev_episode_ever"), R1$A[["prev_ep"]], "R1 A (PA fallback)", f_with_h)
cmp_row("CMP_A_hist_vs_R1_A", INTER_H,
        get_or("A_hist", "soreness", INTER_H), NA_real_, "R1 A (PA fallback; no interaction term)", f_with_h)

cmp_row("CMP_F_hist_vs_R1_F", INTER_H,
        get_or("F_hist", "soreness", INTER_H), R1$F[["inter"]], "R1 F (logistf, full-period z)", f_with_h)
cmp_row("CMP_F_hist_vs_R1_F", ACUTE,
        get_or("F_hist", "soreness", ACUTE), R1$F[["acute"]], "R1 F (logistf)", f_with_h)
cmp_row("CMP_F_hist_vs_R1_F", CHRON,
        get_or("F_hist", "soreness", CHRON), R1$F[["chronic"]], "R1 F (logistf)", f_with_h)

cmp_row("CMP_A_hist_dropteam_vs_R1_A_dropteam", INTER_H,
        get_or("A_hist_dropteam", "soreness", INTER_H), R1$Adt[["inter"]], "R2 A_drop_team (09_TEAM_SENSITIVITY, full-period z)", f_drop_h)
cmp_row("CMP_A_hist_dropteam_vs_R1_A_dropteam", ACUTE,
        get_or("A_hist_dropteam", "soreness", ACUTE), R1$Adt[["acute"]], "R2 A_drop_team", f_drop_h)

cmp_row("CMP_F_hist_dropteam_vs_R2_F_dropteam", INTER_H,
        get_or("F_hist_dropteam", "soreness", INTER_H), R1$Fdt[["inter"]], "R2 F_drop_team (09_TEAM_SENSITIVITY)", f_drop_h)

# ---- SUMMARY ----------------------------------------------------------------
res_df <- read.csv(res_file, stringsAsFactors = FALSE)
get_or <- function(model_id, variant, term) {
  hit <- res_df$OR[res_df$model_id == model_id & res_df$term == term &
                     res_df$wellness_variant == variant]
  if (length(hit) == 0) NA_real_ else hit[1]
}
or_acute_pa  <- get_or("A_hist", "soreness", ACUTE)
or_chron_pa  <- get_or("A_hist", "soreness", CHRON)
or_inter_F   <- get_or("F_hist", "soreness", INTER_H)
or_inter_dt  <- get_or("A_hist_dropteam", "soreness", INTER_H)
or_inter_Fdt <- get_or("F_hist_dropteam", "soreness", INTER_H)
or_acute_F   <- get_or("F_hist", "soreness", ACUTE)
or_chron_F   <- get_or("F_hist", "soreness", CHRON)
INTER_FAT <- paste0(ACUTE, ":", WELL_HIST[["fatigue"]])
INTER_RDY <- paste0(ACUTE, ":", WELL_HIST[["readiness"]])
or_inter_fat <- get_or("F_hist_dropteam", "fatigue", INTER_FAT)
or_inter_rdy <- get_or("F_hist_dropteam", "readiness", INTER_RDY)

dir_ok <- function(a, b) !is.na(a) && !is.na(b) && sign(log(a)) == sign(log(b))
dirs <- c(acute_PA = dir_ok(or_acute_pa, R1$A[["acute"]]),
          acute_F  = dir_ok(or_acute_F, R1$F[["acute"]]),
          chronic_PA = dir_ok(or_chron_pa, R1$A[["chronic"]]),
          chronic_F  = dir_ok(or_chron_F, R1$F[["chronic"]]),
          inter_F  = dir_ok(or_inter_F, R1$F[["inter"]]),
          inter_dt = dir_ok(or_inter_dt, R1$Adt[["inter"]]),
          inter_Fdt = dir_ok(or_inter_Fdt, R1$Fdt[["inter"]]))
pct <- function(new, ref) if (is.na(new) || is.na(ref)) NA_real_ else
  round(100 * (log(new) - log(ref)) / abs(log(ref)), 1)

sum_note <- paste0(
  "QUESTION: does expanding-history (backward-looking, leakage-free) within-player standardization materially change the primary soreness model vs R1 full-period z? ",
  "ANSWER: With-team glmer ladder accepted level = '", res_a$fallback, "' (kind=", res_a$kind,
  "); drop-team ladder accepted level = '", res_ad$fallback, "'. ",
  "CC sample N=", n_s, ", events=", ev_s, ", event players=", evp_s,
  " (vs R1 19758/28/9; 542 rows and 1 event lost to the min-10-prior-obs rule). ",
  sprintf("Acute load OR: with-team accepted %.4f vs R1 A 0.6963 (%s%%); Firth %.4f vs R1 F 0.5991 (%s%%). ",
          or_acute_pa, as.character(pct(or_acute_pa, R1$A[["acute"]])),
          or_acute_F, as.character(pct(or_acute_F, R1$F[["acute"]]))),
  sprintf("Chronic OR: with-team accepted %.4f vs R1 0.9535 (%s%%); Firth %.4f vs R1 F 0.9472 (%s%%). ",
          or_chron_pa, as.character(pct(or_chron_pa, R1$A[["chronic"]])),
          or_chron_F, as.character(pct(or_chron_F, R1$F[["chronic"]]))),
  sprintf("Interaction OR: Firth with-team %.4f vs R1 Firth 0.6296 (%s%%); drop-team glmer %.4f vs R2 drop-team 0.6938 (%s%%); drop-team Firth %.4f vs R2 F_drop_team 0.6710 (%s%%). ",
          or_inter_F, as.character(pct(or_inter_F, R1$F[["inter"]])),
          or_inter_dt, as.character(pct(or_inter_dt, R1$Adt[["inter"]])),
          or_inter_Fdt, as.character(pct(or_inter_Fdt, R1$Fdt[["inter"]]))),
  sprintf("Directional check (drop-team Firth only): fatigue interaction OR=%.4f, readiness interaction OR=%.4f. ",
          or_inter_fat, or_inter_rdy),
  "Direction (sign of log OR) preserved for all focal soreness terms: ", all(dirs, na.rm = TRUE), ". ",
  "_r90 QA fits (taxonomy R2_INTERNAL_QA_ONLY) are included as model_ids *_r90. ",
  if (all(dirs, na.rm = TRUE))
    "VERDICT: backward-looking standardization does NOT change conclusions directionally — focal directions preserved; log-OR shifts quantified in CMP rows."
  else
    "VERDICT: at least one focal term reversed direction under backward standardization — investigate before drawing conclusions.")
add_row("SUMMARY", "soreness", "VERDICT", NA, NA, NA, NA, NA, NA, NA,
        n_s, pl_s, ev_s, f_with_h, sum_note)
log_msg("SUMMARY: ", sum_note)
log_msg("run_backwardz_models.R finished; results in BACKWARD_STANDARDIZATION_RESULTS.csv")
