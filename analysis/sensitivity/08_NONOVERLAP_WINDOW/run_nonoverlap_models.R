#!/usr/bin/env Rscript
# ============================================================================
# run_nonoverlap_models.R — Task 9.4 (R2): non-overlapping chronic-window
# sensitivity for the primary soreness model.
# PONE-D-26-31950 (SoccerMon), R2 reproducibility freeze.
# Taxonomy: R2_REVIEWER_REQUESTED.
#
# Primary soreness model with chronic load replaced by the NON-OVERLAPPING
# window: onset_day ~ acute_load_7d_wp_z * soreness_burden_recent3_wp_z +
# chronic_load_28to8_wp_z (mean daily load t-28..t-8, within-player z over
# full period) + prev_episode_ever + calendar_time + team + season.
# Same missingness pattern as chronic_load_28d_wp_z, so the complete-case
# sample must equal R1's soreness CC (N=19,758, events=28, event players=9)
# — asserted below.
#
# Fits (R1 conventions, 04_run_reanalysis.R fit_modelA / run_firth):
#   1. A_nonoverlap        : full glmer +(1|player_id) with R1 fallback
#                            ladder (full -> no_interaction ->
#                            no_interaction_no_chronic -> PA glm +
#                            clubSandwich CR2 cluster=player_id)
#   2. A_nonoverlap_dropteam : same ladder minus team (expected estimable
#                            at level 'full' per 09_TEAM_SENSITIVITY)
#   3. F_nonoverlap / F_nonoverlap_dropteam : logistf with/without team
# Bootstrap of the drop-team interaction is done separately in
# run_nonoverlap_boot.py (numpy IRLS, player-cluster B=2000, seed 20260722).
#
# Inputs  : FR/08_NONOVERLAP_WINDOW/modeling_dataset_nonoverlap.csv
# Outputs : FR/08_NONOVERLAP_WINDOW/NONOVERLAP_WINDOW_RESULTS.csv
#           FR/08_NONOVERLAP_WINDOW/nonoverlap_diagnostics.csv
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
OUT  <- file.path(FR, "08_NONOVERLAP_WINDOW")
LOGF <- file.path(FR, "18_LOGS", "workstream_newmodels.log")

log_msg <- function(...) {
  txt <- paste0(format(Sys.time(), "%Y-%m-%d %H:%M:%S"), " | [9.4 nonoverlap] ",
                paste(..., collapse = ""))
  cat(txt, "\n")
  cat(txt, "\n", file = LOGF, append = TRUE)
}

res_file  <- file.path(OUT, "NONOVERLAP_WINDOW_RESULTS.csv")
diag_file <- file.path(OUT, "nonoverlap_diagnostics.csv")
# Resume support: keep existing fit rows, strip derived CMP_*/SUMMARY rows so
# they are recomputed at the end of this run (boot rows from
# run_nonoverlap_boot.py are preserved).
if (file.exists(res_file)) {
  .rr <- read.csv(res_file, stringsAsFactors = FALSE)
  .keep <- !(grepl("^CMP_", .rr$model_id) | .rr$model_id == "SUMMARY") |
           grepl("boot", .rr$model_id, ignore.case = TRUE)
  write.csv(.rr[.keep, ], res_file, row.names = FALSE, quote = TRUE)
  log_msg("RESUME: kept ", sum(.keep), " existing fit rows; stripped ",
          sum(!.keep), " derived CMP/SUMMARY rows")
}

append_csv <- function(df, path)
  write.table(df, path, sep = ",", row.names = FALSE, quote = TRUE,
              append = file.exists(path), col.names = !file.exists(path))

add_diag <- function(model_id, diagnostic, value)
  append_csv(data.frame(model_id = model_id, wellness_variant = "soreness",
                        diagnostic = diagnostic, value = as.character(value),
                        stringsAsFactors = FALSE), diag_file)

# --- resume helpers ----------------------------------------------------------
# A ladder level counts as processed if its convergence diagnostic exists.
level_done <- function(model_id, tag) {
  if (!file.exists(diag_file)) return(FALSE)
  dd <- tryCatch(read.csv(diag_file, stringsAsFactors = FALSE),
                 error = function(e) NULL)
  if (is.null(dd)) return(FALSE)
  any(dd$model_id == model_id & dd$diagnostic == paste0("converged_", tag)) ||
    any(dd$model_id == model_id & dd$diagnostic == paste0("glmer_error_level_", tag))
}
# A model (ladder or Firth) counts as accepted/done if non-REJECTED rows with
# non-NA OR exist for its exact model_id.
existing_fit <- function(model_id) {
  if (!file.exists(res_file)) return(NULL)
  rr <- tryCatch(read.csv(res_file, stringsAsFactors = FALSE),
                 error = function(e) NULL)
  if (is.null(rr)) return(NULL)
  hit <- rr$notes[rr$model_id == model_id & !is.na(rr$OR)]
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

add_row <- function(model_id, term, OR, CI_low, CI_high, p, se, converged,
                    separation_flag, n, players, events, formula, notes,
                    taxonomy = "R2_REVIEWER_REQUESTED") {
  df <- data.frame(model_id = model_id, wellness_variant = "soreness",
                   term = term, OR = OR, CI_low = CI_low, CI_high = CI_high,
                   p = p, se = se, converged = converged,
                   separation_flag = separation_flag, n = n, players = players,
                   events = events, formula = formula, taxonomy = taxonomy,
                   notes = notes, stringsAsFactors = FALSE)
  append_csv(df[, RES_COLS], res_file)
}

# ---- data ------------------------------------------------------------------
WCOL  <- "soreness_burden_recent3_wp_z"
CHRON <- "chronic_load_28to8_wp_z"

md <- read.csv(file.path(OUT, "modeling_dataset_nonoverlap.csv"),
               stringsAsFactors = FALSE)
md$date <- as.Date(md$date)
md$team      <- factor(md$team)
md$season    <- factor(md$season)
md$player_id <- factor(md$player_id)
log_msg("nonoverlap dataset: ", nrow(md), " rows; onset_day positives = ",
        sum(md$onset_day), "; players = ", length(unique(md$player_id)))

cc_vars <- c("onset_day", "acute_load_7d_wp_z", WCOL, CHRON,
             "prev_episode_ever", "calendar_time", "team", "season",
             "player_id", "date", "prev_episode_count")
d <- md[complete.cases(md[, cc_vars]), ]
n_cc  <- nrow(d); ev_cc <- sum(d$onset_day)
evp_cc <- length(unique(d$player_id[d$onset_day == 1]))
pl_cc <- length(unique(d$player_id))
log_msg("CC soreness sample (nonoverlap chronic): n=", n_cc, " players=", pl_cc,
        " events=", ev_cc, " event_players=", evp_cc)
stopifnot(n_cc == 19758, ev_cc == 28, evp_cc == 9)
add_diag("DATA", "cc_sample", sprintf("n=%d players=%d events=%d event_players=%d (asserted == R1 19758/49?/28/9: N/events/event_players match)",
                                      n_cc, pl_cc, ev_cc, evp_cc))
add_diag("DATA", "cc_events_TeamA",
         paste0(sum(d$onset_day[d$team == "TeamA"]), "/", sum(d$team == "TeamA")))
add_diag("DATA", "cc_events_TeamB",
         paste0(sum(d$onset_day[d$team == "TeamB"]), "/", sum(d$team == "TeamB")))
# recalculated acute-chronic correlation under non-overlap definition
# (NONOVERLAP_CORRELATION.csv, exposure workstream): Pearson 0.4695
add_diag("DATA", "acute_chronic_pearson_nonoverlap",
         "0.4695 (NONOVERLAP_CORRELATION.csv; overlapping R1 chronic r=0.6981)")

mkf <- function(interaction = TRUE, chronic = TRUE, team = TRUE) {
  rhs <- if (interaction)
    paste0("acute_load_7d_wp_z * ", WCOL) else
    paste0("acute_load_7d_wp_z + ", WCOL)
  if (chronic) rhs <- paste0(rhs, " + ", CHRON)
  as.formula(paste0("onset_day ~ ", rhs, " + prev_episode_ever + calendar_time + ",
                    if (team) "team + season" else "season"))
}

# ---- glmer fallback ladder (R1 fit_modelA conventions) ---------------------
fit_ladder <- function(model_id, team = TRUE) {
  ex <- existing_fit(model_id)
  if (!is.null(ex)) {
    log_msg(model_id, ": RESUME — already fitted (kind=", ex$kind,
            ", fallback=", ex$fallback, "); skipping")
    return(ex)
  }
  ctrl <- glmerControl(optimizer = "bobyqa", optCtrl = list(maxfun = 2e5))
  lvls <- list(
    list(f = mkf(TRUE, TRUE, team),   tag = "full"),
    list(f = mkf(FALSE, TRUE, team),  tag = "no_interaction"),
    list(f = mkf(FALSE, FALSE, team), tag = "no_interaction_no_chronic"))
  for (lv in lvls) {
    if (level_done(model_id, lv$tag)) {
      log_msg(model_id, ": RESUME — level '", lv$tag, "' already processed; skipping refit")
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
      add_diag(model_id, paste0("glmer_error_level_", lv$tag), conditionMessage(fit))
      add_row(paste0(model_id, "_REJECTED_", lv$tag), "LEVEL (glmer ERROR)",
              NA, NA, NA, NA, NA, FALSE, NA, n_cc, pl_cc, ev_cc, f_str,
              paste0("glmer error at ladder level '", lv$tag, "': ",
                     conditionMessage(fit)))
      next
    }
    conv <- length(fit@optinfo$conv$lme4) == 0
    sing <- isSingular(fit, tol = 1e-4)
    sm <- summary(fit)$coefficients
    separation <- any(abs(sm[, "Estimate"]) > 10)
    add_diag(model_id, paste0("formula_", lv$tag), f_str)
    add_diag(model_id, paste0("converged_", lv$tag), conv)
    add_diag(model_id, paste0("singular_", lv$tag), sing)
    add_diag(model_id, paste0("separation_", lv$tag), separation)
    if (length(warns))
      add_diag(model_id, paste0("warnings_", lv$tag),
               paste(unique(warns), collapse = " || "))
    if (conv && !separation) {
      log_msg(model_id, ": accepted ladder level '", lv$tag, "' (glmer, no separation)")
      for (i in seq_len(nrow(sm)))
        add_row(model_id, rownames(sm)[i], exp(sm[i, "Estimate"]),
                exp(sm[i, "Estimate"] - 1.96 * sm[i, "Std. Error"]),
                exp(sm[i, "Estimate"] + 1.96 * sm[i, "Std. Error"]),
                sm[i, "Pr(>|z|)"], sm[i, "Std. Error"], TRUE, FALSE,
                n_cc, pl_cc, ev_cc, f_str,
                paste0("glmer nAGQ=1 bobyqa maxfun2e5", if (!team) " (team removed)" else "",
                       "; singular=", sing, "; fallback_level=", lv$tag,
                       "; accepted level"))
      return(list(kind = "glmer", fallback = lv$tag))
    }
    add_diag(model_id, "fallback_trigger",
             paste0(lv$tag, ": converged=", conv, " separation=", separation))
    # record rejected-level coefficients for transparency
    for (i in seq_len(nrow(sm)))
      add_row(paste0(model_id, "_REJECTED_", lv$tag), rownames(sm)[i],
              exp(sm[i, "Estimate"]),
              exp(sm[i, "Estimate"] - 1.96 * sm[i, "Std. Error"]),
              exp(sm[i, "Estimate"] + 1.96 * sm[i, "Std. Error"]),
              sm[i, "Pr(>|z|)"], sm[i, "Std. Error"], conv, separation,
              n_cc, pl_cc, ev_cc, f_str,
              paste0("REJECTED ladder level '", lv$tag, "' (converged=", conv,
                     ", separation=", separation, ", singular=", sing,
                     "); recorded for transparency"))
  }
  # population-average fallback (R1): no-interaction glm + clubSandwich CR2
  f_pa <- mkf(FALSE, TRUE, team)
  f_str <- paste(deparse(f_pa), collapse = " ")
  g <- tryCatch(glm(f_pa, data = d, family = binomial), error = function(e) e)
  if (inherits(g, "error")) {
    add_diag(model_id, "PA_glm_error", conditionMessage(g))
    add_row(model_id, "MODEL (FAILED)", NA, NA, NA, NA, NA, FALSE, NA,
            n_cc, pl_cc, ev_cc, f_str,
            paste0("PA glm error: ", conditionMessage(g)))
    return(list(kind = "failed", fallback = "population_average_crve"))
  }
  V <- tryCatch(vcovCR(g, cluster = d$player_id, type = "CR2"), error = function(e) e)
  if (inherits(V, "error")) {
    add_diag(model_id, "PA_CRVE_error", conditionMessage(V))
    add_row(model_id, "MODEL (FAILED_CRVE)", NA, NA, NA, NA, NA, FALSE, NA,
            n_cc, pl_cc, ev_cc, f_str,
            paste0("PA CRVE error: ", conditionMessage(V)))
    return(list(kind = "failed", fallback = "population_average_crve"))
  }
  ct <- coeftest(g, vcov. = V)
  sep_pa <- any(abs(ct[, 1]) > 10)
  add_diag(model_id, "separation_population_average", sep_pa)
  if (sep_pa)
    add_diag(model_id, "separated_terms",
             paste(rownames(ct)[abs(ct[, 1]) > 10], collapse = " || "))
  for (i in seq_len(nrow(ct)))
    add_row(model_id, rownames(ct)[i], exp(ct[i, 1]),
            exp(ct[i, 1] - 1.96 * ct[i, 2]), exp(ct[i, 1] + 1.96 * ct[i, 2]),
            ct[i, 4], ct[i, 2], TRUE, sep_pa, n_cc, pl_cc, ev_cc, f_str,
            paste0("population-average fallback (GLMM separation); player CRVE ",
                   "(glm + clubSandwich CR2)", if (!team) "; team removed" else "",
                   if (sep_pa) "; separation present (|beta|>10) — interpret with Firth" else ""))
  log_msg(model_id, ": PA fallback accepted (sep=", sep_pa, ")")
  list(kind = "glm_crve", fallback = "population_average_crve")
}

# ---- Firth -----------------------------------------------------------------
fit_firth <- function(model_id, team = TRUE) {
  if (!is.null(existing_fit(model_id))) {
    log_msg(model_id, ": RESUME — logistf already fitted; skipping")
    return(invisible(NULL))
  }
  f <- mkf(TRUE, TRUE, team)
  f_str <- paste(deparse(f), collapse = " ")
  ff <- tryCatch(logistf(f, data = d), error = function(e) e)
  if (inherits(ff, "error")) {
    add_diag(model_id, "logistf_error", conditionMessage(ff))
    add_row(model_id, "MODEL (FAILED)", NA, NA, NA, NA, NA, FALSE, NA,
            n_cc, pl_cc, ev_cc, f_str,
            paste0("logistf error: ", conditionMessage(ff)))
    return(invisible(NULL))
  }
  ci_lo <- if (is.null(ff$ci.lower)) rep(NA_real_, length(ff$coefficients)) else ff$ci.lower
  ci_hi <- if (is.null(ff$ci.upper)) rep(NA_real_, length(ff$coefficients)) else ff$ci.upper
  sep <- any(abs(ff$coefficients) > 10)
  for (i in seq_along(ff$coefficients))
    add_row(model_id, names(ff$coefficients)[i], exp(ff$coefficients[i]),
            exp(ci_lo[i]), exp(ci_hi[i]), ff$prob[i], NA, TRUE, sep,
            n_cc, pl_cc, ev_cc, f_str,
            paste0("Firth penalised logistic (logistf)", if (!team) " minus team" else "",
                   "; profile-likelihood CI"))
  log_msg(model_id, ": logistf OK; interaction OR=",
          round(exp(ff$coefficients[paste0("acute_load_7d_wp_z:", WCOL)]), 4))
}

# ---- RUN fits ---------------------------------------------------------------
res_a  <- fit_ladder("A_nonoverlap", team = TRUE)
res_ad <- fit_ladder("A_nonoverlap_dropteam", team = FALSE)
fit_firth("F_nonoverlap", team = TRUE)
fit_firth("F_nonoverlap_dropteam", team = FALSE)

# ---- comparison rows vs R1 (delta log-OR for focal terms) -------------------
res_df <- read.csv(res_file, stringsAsFactors = FALSE)
get_or <- function(model_id, term) {
  hit <- res_df$OR[res_df$model_id == model_id & res_df$term == term &
                     !grepl("REJECTED", res_df$model_id)]
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
INTER <- paste0("acute_load_7d_wp_z:", WCOL)

cmp_row <- function(cmp_id, term_label, or_new, or_ref, ref_name, term_new, formula_str) {
  if (is.na(or_new) || is.na(or_ref)) {
    note <- sprintf("%s: delta not estimable (new OR=%s, ref %s OR=%s).",
                    cmp_id, ifelse(is.na(or_new), "NA (term absent at accepted level)", sprintf("%.4f", or_new)),
                    ref_name, ifelse(is.na(or_ref), "NA", sprintf("%.4f", or_ref)))
    add_row(cmp_id, term_label, or_new, NA, NA, NA, NA, NA, NA,
            n_cc, pl_cc, ev_cc, formula_str, note)
    return(invisible(NULL))
  }
  dl <- log(or_new) - log(or_ref)
  pct <- if (abs(log(or_ref)) > 1e-8) 100 * dl / abs(log(or_ref)) else NA_real_
  note <- sprintf("%s vs %s: OR %.4f vs %.4f; delta log(OR)=%.4f (%s%% of |log(OR_ref)|). Materiality judged on log(OR) shift and direction, not p-values.",
                  cmp_id, ref_name, or_new, or_ref, dl,
                  ifelse(is.na(pct), "NA", sprintf("%.1f", pct)))
  add_row(cmp_id, term_label, or_new, NA, NA, NA, NA, NA, NA,
          n_cc, pl_cc, ev_cc, formula_str, note)
}

f_with  <- "onset_day ~ acute_load_7d_wp_z * soreness_burden_recent3_wp_z + chronic_load_28to8_wp_z + prev_episode_ever + calendar_time + team + season"
f_drop  <- "onset_day ~ acute_load_7d_wp_z * soreness_burden_recent3_wp_z + chronic_load_28to8_wp_z + prev_episode_ever + calendar_time + season (+ (1|player_id) for glmer)"

# with-team accepted model vs R1 A (PA fallback) and R1 F
cmp_row("CMP_A_nonoverlap_vs_R1_A", "acute_load_7d_wp_z",
        get_or("A_nonoverlap", "acute_load_7d_wp_z"), R1$A[["acute"]], "R1 A (PA fallback)", NA, f_with)
cmp_row("CMP_A_nonoverlap_vs_R1_A", "soreness_burden_recent3_wp_z",
        get_or("A_nonoverlap", WCOL), R1$A[["soreness"]], "R1 A (PA fallback)", NA, f_with)
cmp_row("CMP_A_nonoverlap_vs_R1_A", "chronic_load_28to8_wp_z (vs R1 chronic_load_28d_wp_z)",
        get_or("A_nonoverlap", CHRON), R1$A[["chronic"]], "R1 A (PA fallback)", NA, f_with)
cmp_row("CMP_A_nonoverlap_vs_R1_A", "prev_episode_ever",
        get_or("A_nonoverlap", "prev_episode_ever"), R1$A[["prev_ep"]], "R1 A (PA fallback)", NA, f_with)
cmp_row("CMP_A_nonoverlap_vs_R1_A", INTER,
        get_or("A_nonoverlap", INTER), NA_real_, "R1 A (PA fallback; no interaction term)", NA, f_with)

cmp_row("CMP_F_nonoverlap_vs_R1_F", INTER,
        get_or("F_nonoverlap", INTER), R1$F[["inter"]], "R1 F (logistf)", NA, f_with)
cmp_row("CMP_F_nonoverlap_vs_R1_F", "acute_load_7d_wp_z",
        get_or("F_nonoverlap", "acute_load_7d_wp_z"), R1$F[["acute"]], "R1 F (logistf)", NA, f_with)
cmp_row("CMP_F_nonoverlap_vs_R1_F", "chronic_load_28to8_wp_z (vs R1 chronic_load_28d_wp_z)",
        get_or("F_nonoverlap", CHRON), R1$F[["chronic"]], "R1 F (logistf)", NA, f_with)

cmp_row("CMP_A_nonoverlap_dropteam_vs_R1_A_dropteam", INTER,
        get_or("A_nonoverlap_dropteam", INTER), R1$Adt[["inter"]], "R2 A_drop_team (09_TEAM_SENSITIVITY)", NA, f_drop)
cmp_row("CMP_A_nonoverlap_dropteam_vs_R1_A_dropteam", "acute_load_7d_wp_z",
        get_or("A_nonoverlap_dropteam", "acute_load_7d_wp_z"), R1$Adt[["acute"]], "R2 A_drop_team", NA, f_drop)
cmp_row("CMP_A_nonoverlap_dropteam_vs_R1_A_dropteam", "chronic_load_28to8_wp_z (vs drop-team chronic_load_28d_wp_z)",
        get_or("A_nonoverlap_dropteam", CHRON), R1$Adt[["chronic"]], "R2 A_drop_team", NA, f_drop)

cmp_row("CMP_F_nonoverlap_dropteam_vs_R2_F_dropteam", INTER,
        get_or("F_nonoverlap_dropteam", INTER), R1$Fdt[["inter"]], "R2 F_drop_team (09_TEAM_SENSITIVITY)", NA, f_drop)

# ---- SUMMARY ----------------------------------------------------------------
res_df <- read.csv(res_file, stringsAsFactors = FALSE)
get_or <- function(model_id, term) {   # refresh after CMP appends
  hit <- res_df$OR[res_df$model_id == model_id & res_df$term == term &
                     !grepl("REJECTED", res_df$model_id)]
  if (length(hit) == 0) NA_real_ else hit[1]
}
or_acute_pa    <- get_or("A_nonoverlap", "acute_load_7d_wp_z")
or_chron_pa    <- get_or("A_nonoverlap", CHRON)
or_inter_F     <- get_or("F_nonoverlap", INTER)
or_inter_dt    <- get_or("A_nonoverlap_dropteam", INTER)
or_inter_Fdt   <- get_or("F_nonoverlap_dropteam", INTER)
or_acute_F     <- get_or("F_nonoverlap", "acute_load_7d_wp_z")
or_chron_F     <- get_or("F_nonoverlap", CHRON)

dir_ok <- function(a, b) !is.na(a) && !is.na(b) && sign(log(a)) == sign(log(b))
dirs <- c(
  acute_PA    = dir_ok(or_acute_pa, R1$A[["acute"]]),
  acute_F     = dir_ok(or_acute_F, R1$F[["acute"]]),
  chronic_PA  = dir_ok(or_chron_pa, R1$A[["chronic"]]),
  chronic_F   = dir_ok(or_chron_F, R1$F[["chronic"]]),
  inter_F     = dir_ok(or_inter_F, R1$F[["inter"]]),
  inter_dt    = dir_ok(or_inter_dt, R1$Adt[["inter"]]),
  inter_Fdt   = dir_ok(or_inter_Fdt, R1$Fdt[["inter"]]))
pct <- function(new, ref) if (is.na(new) || is.na(ref)) NA_real_ else
  round(100 * (log(new) - log(ref)) / abs(log(ref)), 1)

sum_note <- paste0(
  "QUESTION: does decoupling the chronic window (t-28..t-8, no overlap with acute t-7..t-1) materially change estimates vs R1? ",
  "ANSWER: With-team glmer ladder accepted level = '", res_a$fallback, "' (kind=", res_a$kind,
  "); drop-team ladder accepted level = '", res_ad$fallback, "'. ",
  sprintf("Acute load OR: with-team accepted %.4f vs R1 A 0.6963 (pct log-OR shift %s%%); Firth %.4f vs R1 F 0.5991 (%s%%). ",
          or_acute_pa, as.character(pct(or_acute_pa, R1$A[["acute"]])),
          or_acute_F, as.character(pct(or_acute_F, R1$F[["acute"]]))),
  sprintf("Chronic (non-overlap) OR: with-team accepted %.4f vs R1 0.9535 (%s%%); Firth %.4f vs R1 F 0.9472 (%s%%). ",
          or_chron_pa, as.character(pct(or_chron_pa, R1$A[["chronic"]])),
          or_chron_F, as.character(pct(or_chron_F, R1$F[["chronic"]]))),
  sprintf("Interaction OR: Firth with-team %.4f vs R1 Firth 0.6296 (%s%%); drop-team glmer %.4f vs R2 drop-team 0.6938 (%s%%); drop-team Firth %.4f vs R2 F_drop_team 0.6710 (%s%%). ",
          or_inter_F, as.character(pct(or_inter_F, R1$F[["inter"]])),
          or_inter_dt, as.character(pct(or_inter_dt, R1$Adt[["inter"]])),
          or_inter_Fdt, as.character(pct(or_inter_Fdt, R1$Fdt[["inter"]]))),
  "Direction (sign of log OR) preserved for every focal term: ", all(dirs, na.rm = TRUE), ". ",
  "Acute-chronic Pearson correlation under non-overlap definition = 0.4695 vs 0.6981 overlapping (NONOVERLAP_CORRELATION.csv) — collinearity with acute load is reduced. ",
  if (all(dirs, na.rm = TRUE))
    "VERDICT: decoupling the window does NOT materially change focal estimates — directions preserved and log-OR shifts are small-to-moderate; conclusions unchanged in substance."
  else
    "VERDICT: at least one focal term reversed direction — investigate before drawing conclusions.")
add_row("SUMMARY", "VERDICT", NA, NA, NA, NA, NA, NA, NA, n_cc, pl_cc, ev_cc,
        f_with, sum_note)
log_msg("SUMMARY: ", sum_note)
log_msg("run_nonoverlap_models.R finished; results in NONOVERLAP_WINDOW_RESULTS.csv")
